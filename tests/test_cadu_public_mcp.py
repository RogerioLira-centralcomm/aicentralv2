from unittest.mock import MagicMock, Mock, patch
from io import BytesIO
from pathlib import Path

import pytest
from flask import Flask

from aicentralv2.cadu_public_mcp.auth import DEFAULT_SCOPES, PublicMcpAuthError, PublicMcpPrincipal, _public_context, ensure_scope, normalize_scopes
from aicentralv2.cadu_public_mcp import usage
from aicentralv2.cadu_public_mcp.routes import PUBLIC_MCP_PATH, PUBLIC_TOOLS, RECOVERABLE_OPERATION_TOOLS, _public_catalog, _request_context_for_auth, bp
from aicentralv2.cadu_public_mcp.usage import tool_cost
from aicentralv2.cadu_tool_billing import InsufficientToolCredits
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools
from aicentralv2.cadu_workspace.mcp.tools.resources import (
    _image_suffix, add_resource, create_editable_copy, inspect_input, list_versions as list_resource_versions,
    relate as relate_resources, search_resources, set_archived, start_image_edit, update_metadata,
)
from aicentralv2.cadu_workspace.project_resource_service import resource_capabilities
from aicentralv2.cadu_workspace import project_resource_service
from aicentralv2.cadu_workspace.workspace_ingestion_service import _preserve_external_reference
from aicentralv2.creative_modeling_storage import CreativeAssetStorage, GENERATED_PREFIX, REFERENCE_PREFIX
from aicentralv2.creative_media.studio_maintenance import PostgresStudioMaintenance


def test_public_context_is_tenant_bound_and_uses_default_project():
    row = {
        "client_id": 12,
        "user_id": 7,
        "default_project_ref": "ci:project-1",
    }
    with patch(
        "aicentralv2.cadu_public_mcp.auth.repository.entities",
        return_value=[{"ref": "ci:project-1", "kind": "project"}],
    ):
        context = _public_context(row, {"surface": "workspace"})

    assert isinstance(context, RequestContext)
    assert context.organization_id == context.client_id == 12
    assert context.user_id == 7
    assert context.project_ref == "ci:project-1"


def test_legacy_purchase_scope_does_not_break_existing_keys():
    assert normalize_scopes(["credits:read", "credits:purchase"], allow_writes=True) == ("credits:read",)


def test_empty_effective_scope_does_not_restore_default_permissions():
    assert normalize_scopes([], allow_writes=True) == ()


def test_read_only_scope_removes_context_mutation():
    assert normalize_scopes(["contexts:read", "contexts:write"], allow_writes=False) == ("contexts:read",)


def test_project_ref_is_selectable_in_public_tool_arguments_without_changing_internal_schema():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref=None, capabilities=("workspace", "artifacts"))
    principal = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="codex",
                                   label="Teste", scopes=tuple(DEFAULT_SCOPES | {"artifacts:write"}), context=context)
    with patch("aicentralv2.cadu_public_mcp.auth.repository.actor", return_value={"organization_id": 12}), \
         patch("aicentralv2.cadu_public_mcp.auth.repository.account_role", return_value="member"):
        catalog = _public_catalog(principal)
    upload = next(item for item in catalog if item["name"] == "projects.prepare_source_upload")
    external = next(item for item in catalog if item["name"] == "projects.create_link_reference")
    html = next(item for item in catalog if item["name"] == "artifacts.create_draft")
    unified = next(item for item in catalog if item["name"] == "resources.add")
    task_batch = next(item for item in catalog if item["name"] == "projects.create_tasks")
    initial_tasks = next(item for item in catalog if item["name"] == "projects.create_initial_task_list")
    task_update = next(item for item in catalog if item["name"] == "projects.update_task")
    assert "project_ref" in upload["inputSchema"]["properties"]
    assert {"resource_kind", "platform", "external_id", "description", "tags"} <= \
        external["inputSchema"]["properties"].keys()
    assert "html" in html["inputSchema"]["properties"]["type"]["enum"]
    assert "HTML" in html["description"]
    assert "Não envie HTML em summary" in html["inputSchema"]["properties"]["content"]["description"]
    assert "project_ref" in unified["inputSchema"]["properties"]
    assert set(unified["inputSchema"]["properties"]["mode"]["enum"]) == {
        "editable", "external_link", "file_upload",
    }
    assert upload["securitySchemes"] == [{"type": "oauth2", "scopes": ["projects:content_write"]}]
    assert upload["_meta"]["securitySchemes"] == upload["securitySchemes"]
    assert task_batch["inputSchema"]["properties"]["tasks"]["maxItems"] == 50
    assert "context_summary" in initial_tasks["inputSchema"]["required"]
    assert initial_tasks["securitySchemes"] == [{"type": "oauth2", "scopes": ["projects:content_write"]}]
    assert task_update["inputSchema"]["properties"]["assignee_id"]["type"] == ["integer", "null"]
    internal = next(item for item in load_builtin_tools().list(context) if item["name"] == "projects.prepare_source_upload")
    assert "project_ref" not in internal["inputSchema"]["properties"]
    params = _request_context_for_auth({"name": "projects.prepare_source_upload",
                                        "arguments": {"project_ref": "ci:project-2"}})
    with patch("aicentralv2.cadu_public_mcp.auth.repository.entities",
               return_value=[{"ref": "ci:project-2", "kind": "project"}]):
        assert _public_context({"client_id": 12, "user_id": 7}, params).project_ref == "ci:project-2"


def test_public_transport_is_separate_and_requires_bearer_auth():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WORKSPACE_URL="https://workspace.centralcomm.media")
    app.register_blueprint(bp)
    client = app.test_client()

    metadata = client.get("/.well-known/cadu-mcp-public")
    assert metadata.status_code == 200
    assert metadata.get_json()["endpoint"].endswith(PUBLIC_MCP_PATH)
    assert metadata.get_json()["authentication"]["type"] == "bearer_api_key"
    assert metadata.get_json()["icon_url"].endswith("/static/images/cadu/products/cadu-mcp-icon.svg")
    assert metadata.get_json()["icons"][0]["mimeType"] == "image/svg+xml"

    with patch(
        "aicentralv2.cadu_public_mcp.routes.auth.authenticate",
        side_effect=PublicMcpAuthError("invalid"),
    ):
        response = client.post(
            PUBLIC_MCP_PATH,
            json={"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}},
        )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer")


def test_agent_setup_exposes_native_installers_without_overpromising_codex():
    template = Path("aicentralv2/templates/cadu_workspace/mcp_agents.html").read_text()

    assert "vscode:mcp/install?" in template
    assert "https://cursor.com/en-US/install-mcp" in template
    assert "O Codex ainda não oferece um link público de instalação" in template
    assert "data-install-client" in template
    assert "O instalador do Cursor receberá a URL e a chave privada" in template


def test_public_mcp_insufficient_credits_points_to_workspace():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WORKSPACE_URL="https://workspace.centralcomm.media")
    app.register_blueprint(bp)
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref=None, capabilities=("workspace",))
    principal = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="codex",
                                   label="Teste", scopes=tuple(DEFAULT_SCOPES), context=context)
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=principal), \
         patch("aicentralv2.cadu_public_mcp.routes.auth.ensure_scope"), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.authorize_credits",
               side_effect=InsufficientToolCredits("Saldo insuficiente.")):
        response = app.test_client().post(PUBLIC_MCP_PATH, json={"jsonrpc": "2.0", "id": "1",
            "method": "tools/call", "params": {"name": "credits.get_balance", "arguments": {}}})
    assert response.status_code == 402
    error = response.get_json()["error"]
    assert error["data"]["credits_url"] == "https://workspace.centralcomm.media/creditos"
    assert "https://workspace.centralcomm.media/creditos" in error["message"]


def test_initialize_advertises_cadu_icon_to_mcp_clients():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WORKSPACE_URL="https://workspace.centralcomm.media")
    app.register_blueprint(bp)
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref=None, capabilities=("workspace",))
    principal = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="codex",
                                   label="Teste", scopes=("projects:read",), context=context)
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=principal), \
         patch("aicentralv2.cadu_public_mcp.routes.load_builtin_tools"):
        response = app.test_client().post(PUBLIC_MCP_PATH, json={"jsonrpc": "2.0", "id": "1",
            "method": "initialize", "params": {}})
    assert response.status_code == 200
    info = response.get_json()["result"]["serverInfo"]
    assert info["title"] == "Cadu"
    assert info["icons"][0]["src"].endswith("/static/images/cadu/products/cadu-mcp-icon.svg")


def test_mcp_purchase_requires_authenticated_page_confirmation():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as saved:
        saved.update(user_id=7, cliente_id=12, family_csrf="csrf-test")
    purchase = {"id": 31, "status": "pending", "package_name": "Extra Essencial",
                "tokens_amount": 100_000, "price_brl": 49.0, "billing_mode": "prepaid", "note": ""}
    with patch("aicentralv2.cadu_workspace.credit_purchase_service.pending_extra", return_value=purchase), \
         patch("aicentralv2.cadu_workspace.credit_purchase_service.purchase_extra",
               return_value={"credits_released": 100_000}) as approve, \
         patch("aicentralv2.cadu_public_mcp.routes.render_template", return_value="ok"):
        assert client.get("/workspace/app/integracoes/agents/compras/31").status_code == 200
        approve.assert_not_called()
        assert client.post("/workspace/app/integracoes/agents/compras/31").status_code == 403
        approve.assert_not_called()
        response = client.post("/workspace/app/integracoes/agents/compras/31", data={"_csrf": "csrf-test"})
        assert response.status_code == 200
        approve.assert_called_once()
        assert approve.call_args.kwargs["pending_request_id"] == 31


def test_public_multipart_upload_requires_key_scope_and_project_editor():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    app.register_blueprint(bp)
    client = app.test_client()
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="conversations", project_ref="ci:42", capabilities=("workspace",))
    principal = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="gpt",
                                   label="Teste", scopes=("projects:write",), context=context)
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=principal), \
         patch("aicentralv2.cadu_public_mcp.routes.repository.project_user_can_view", return_value=True), \
         patch("aicentralv2.cadu_public_mcp.routes.repository.actor", return_value={"organization_id":12}), \
         patch("aicentralv2.cadu_public_mcp.routes.repository.account_role", return_value="member"), \
         patch("aicentralv2.cadu_public_mcp.routes.repository.project_access", return_value=[]), \
         patch("aicentralv2.cadu_workspace.project_source_service.save_upload") as save:
        response = client.post(f"{PUBLIC_MCP_PATH}/uploads", data={"upload_token":"signed",
            "project_ref":"ci:42", "file":(BytesIO(b"brief"), "brief.txt")})
        assert response.status_code == 403
        save.assert_not_called()

    no_scope = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="gpt",
                                  label="Teste", scopes=("projects:read",), context=context)
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=no_scope), \
         patch("aicentralv2.cadu_workspace.project_source_service.save_upload") as save:
        response = client.post(f"{PUBLIC_MCP_PATH}/uploads", data={"upload_token":"signed",
            "project_ref":"ci:42", "file":(BytesIO(b"brief"), "brief.txt")})
        assert response.status_code == 401
        save.assert_not_called()


def test_public_upload_intent_returns_public_companion_url():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WORKSPACE_URL="https://workspace.centralcomm.media")
    app.register_blueprint(bp)
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="conversations", project_ref="ci:42", capabilities=("workspace",))
    principal = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="gpt",
                                   label="Teste", scopes=("projects:write",), context=context)
    registry = MagicMock()
    registry.execute.return_value = {"upload_token":"signed", "upload_url":"/workspace/mcp/uploads"}
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=principal), \
         patch("aicentralv2.cadu_public_mcp.routes.load_builtin_tools", return_value=registry), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.authorize_credits"), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.charge_credits"), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.record"):
        response = app.test_client().post(PUBLIC_MCP_PATH, json={"jsonrpc":"2.0", "id":"1",
            "method":"tools/call", "params":{"name":"projects.prepare_source_upload",
                "arguments":{"request_id":"be777b36-a973-419c-802a-886bf1d125b0", "use_as_knowledge":True}}})
    assert response.status_code == 200
    assert response.get_json()["result"]["structuredContent"]["upload_url"] == \
        "https://workspace.centralcomm.media/mcp/cadu/v1/uploads"
    receipt = response.get_json()["result"]["structuredContent"]["_receipt"]
    assert receipt == {
        "operation_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "tool": "projects.prepare_source_upload",
        "status": "completed",
        "recover_with": "operations.get",
    }

def test_public_catalog_is_allowlisted_and_metered():
    assert "google.sync_workspace" not in PUBLIC_TOOLS
    assert "google.link_resource_to_project" in PUBLIC_TOOLS
    assert {"resources.search", "resources.get", "resources.capabilities"} <= PUBLIC_TOOLS
    assert "operations.get" in PUBLIC_TOOLS
    assert tool_cost("operations.get") == 0
    assert tool_cost("resources.start_image_edit") == 0
    assert tool_cost("google.get_connector_status") == 1
    assert tool_cost("reports.compare_report_to_plan") == 3


def test_public_transport_generates_command_uuid_independent_from_jsonrpc_id():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WORKSPACE_URL="https://workspace.centralcomm.media")
    app.register_blueprint(bp)
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref=None, capabilities=("workspace",))
    principal = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="codex",
                                   label="Teste", scopes=("projects:write",), context=context)
    registry = MagicMock()
    registry.execute.return_value = {"project_ref": "ci:new"}
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=principal), \
         patch("aicentralv2.cadu_public_mcp.routes.load_builtin_tools", return_value=registry), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.authorize_credits"), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.charge_credits"), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.record"):
        response = app.test_client().post(PUBLIC_MCP_PATH, json={"jsonrpc": "2.0", "id": "rpc-1",
            "method": "tools/call", "params": {"name": "workspace.create_project", "arguments": {}}})
    operation_id = response.get_json()["result"]["structuredContent"]["_receipt"]["operation_id"]
    assert operation_id != "rpc-1"
    assert len(operation_id) == 36
    assert registry.execute.call_args.args[1]["request_id"] == operation_id


def test_public_create_project_contract_exposes_direction_brand_and_custom_fields():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", capabilities=("workspace",))
    tools = load_builtin_tools().list(context, "customer_agent")
    definition = next(item for item in tools if item["name"] == "workspace.create_project")
    properties = definition["inputSchema"]["properties"]

    assert {"confirmed", "brand_ref", "brand_name", "tone_of_voice", "audience",
            "positioning", "color", "custom_fields"} <= set(properties)
    assert "confirmed" in definition["inputSchema"]["required"]


def test_public_create_brand_contract_requires_market_seed_and_accepts_optional_assets():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", capabilities=("workspace",))
    tools = load_builtin_tools().list(context, "customer_agent")
    definition = next(item for item in tools if item["name"] == "brands.create")

    assert {"name", "website_url", "sector", "confirmed"} <= set(definition["inputSchema"]["required"])
    assert {"official_logo_url", "reference_urls"} <= set(definition["inputSchema"]["properties"])


def test_non_ledger_write_receipt_does_not_promise_operations_get():
    assert "media.start_studio_session" not in RECOVERABLE_OPERATION_TOOLS
    assert "brands.start_audit" not in RECOVERABLE_OPERATION_TOOLS
    assert "projects.create_note" in RECOVERABLE_OPERATION_TOOLS
    assert {"projects.create_task", "projects.create_tasks", "projects.create_initial_task_list",
            "projects.update_task"} <= RECOVERABLE_OPERATION_TOOLS

    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WORKSPACE_URL="https://workspace.centralcomm.media")
    app.register_blueprint(bp)
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref=None, capabilities=("workspace",))
    principal = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="codex",
                                   label="Teste", scopes=("projects:content_write",), context=context)
    registry = MagicMock()
    registry.execute.return_value = {"session_id": "session-1", "status": "draft"}
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=principal), \
         patch("aicentralv2.cadu_public_mcp.routes.load_builtin_tools", return_value=registry), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.authorize_credits"), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.charge_credits"), \
         patch("aicentralv2.cadu_public_mcp.routes.usage.record"):
        response = app.test_client().post(PUBLIC_MCP_PATH, json={"jsonrpc": "2.0", "id": "rpc-2",
            "method": "tools/call", "params": {"name": "media.start_studio_session",
                                                   "arguments": {"kind": "image", "prompt": "Produto"}}})
    receipt = response.get_json()["result"]["structuredContent"]["_receipt"]
    assert receipt["status"] == "completed"
    assert "recover_with" not in receipt


def test_resource_capabilities_do_not_overpromise_provider_writes():
    result = resource_capabilities({
        "id": "resource-1",
        "source_system": "google_drive",
        "resource_type": "file",
        "mime_type": "application/pdf",
        "status": "active",
        "version": 2,
    })
    assert result["actions"]["read"] is True
    assert result["actions"]["index"] is True
    assert result["actions"]["native_edit"] is False
    assert result["actions"]["share"] is False
    assert result["edit_mode"] == "read_only"
    assert result["actions"]["create_editable_copy"] is True
    assert any("PDF" in item for item in result["limitations"])


def test_unconnected_external_resource_is_strictly_reference_only():
    result = resource_capabilities({
        "id": "resource-2", "source_system": "external_reference", "resource_type": "link",
        "category": "document", "status": "needs_authorization", "metadata": {
            "provider": "google_drive", "connection_ref": None,
        },
    })
    assert result["actions"]["read"] is False
    assert result["actions"]["edit_content"] is False
    assert result["actions"]["push_to_source"] is False
    assert result["actions"]["create_editable_copy"] is False
    assert result["actions"]["derive_artifact"] is False
    assert result["recommended_tool"] is None


def test_native_html_and_studio_image_advertise_the_correct_editor():
    html = resource_capabilities({
        "id": "html-1", "source_system": "cadu_workspace_artifacts",
        "resource_type": "artifact", "category": "html", "status": "draft", "version": 3,
    })
    image = resource_capabilities({
        "id": "image-1", "source_system": "studio", "resource_type": "image",
        "mime_type": "image/png", "status": "active", "version": 2,
    })
    assert html["edit_mode"] == "native"
    assert html["editor"] == "html"
    assert html["actions"]["create_revision"] is True
    assert image["editor"] == "studio"
    assert image["actions"]["native_edit"] is True
    assert image["recommended_tool"] == "resources.start_image_edit"


def test_semantic_resource_tools_are_registered_for_external_agents():
    context = RequestContext(
        organization_id=12, client_id=12, user_id=7, conversation_id=None,
        surface="workspace", project_ref="ci:project-1",
        capabilities=("workspace", "planner", "studio", "reports", "artifacts"),
    )
    names = {item["name"] for item in load_builtin_tools().list(context, "customer_agent")}
    assert {
        "resources.search", "resources.add", "resources.get", "resources.capabilities", "resources.create_editable_copy",
        "resources.inspect_input", "resources.list_versions", "resources.list_relations",
        "resources.relate", "resources.update_metadata", "resources.set_archived", "resources.start_image_edit",
    } <= names


def test_start_image_edit_materializes_base_without_charging_or_mutating_source():
    context = RequestContext(
        organization_id=12, client_id=12, user_id=7, conversation_id="conversation-1",
        surface="workspace", project_ref="ci:project-1", capabilities=("workspace",),
    )
    arguments = {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "resource_id": "resource-1",
        "prompt": "Remova apenas o fundo", "title": "Ajuste da campanha",
    }
    store = MagicMock()
    with patch("aicentralv2.cadu_workspace.mcp.tools.resources._project_resource",
               return_value={"id": "resource-1", "title": "original.png", "resource_type": "image"}), \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_resource_service.resource_capabilities",
               return_value={"editor": "studio", "actions": {"open_in_editor": True}}), \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources._studio_image_reference",
               return_value={"asset_path": "/static/uploads/creative_references/base.png",
                             "title": "original.png", "source_resource_id": "resource-1"}), \
         patch("aicentralv2.cadu_workspace.mcp.tools.media.start_studio_session",
               return_value={"session_id": "session-1", "creative_client_id": 44,
                             "studio_url": "https://studio.test/imagem", "generation_status": "not_started"}), \
         patch("aicentralv2.creative_media.studio._session_store", return_value=store), \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.operations.execute",
               side_effect=lambda request_id, ctx, name, payload, operation: operation()):
        result = start_image_edit(context, arguments)

    assert result["preserved_original"] is True
    assert result["credits_consumed"] is False
    assert result["generation_status"] == "not_started"
    store.accept.assert_called_once()
    accepted = store.accept.call_args.args[3]
    assert accepted["role"] == "base"
    assert accepted["source_id"] == "resource-1"


def test_studio_image_format_uses_signature_not_filename():
    assert _image_suffix(b"\x89PNG\r\n\x1a\nrest") == ".png"
    assert _image_suffix(b"\xff\xd8\xffrest") == ".jpg"
    assert _image_suffix(b"RIFF1234WEBPrest") == ".webp"
    with pytest.raises(Exception, match="imagem PNG, JPG ou WebP"):
        _image_suffix(b"not-an-image")


def test_creative_asset_delete_handles_reference_and_generated_files(tmp_path, monkeypatch):
    import aicentralv2.creative_modeling_storage as storage_module

    monkeypatch.setattr(storage_module, "_root", lambda folder="client_logos": tmp_path / folder)
    reference = tmp_path / "creative_references" / "reference.png"
    generated = tmp_path / "creative_generated" / "generated.png"
    reference.parent.mkdir(parents=True)
    generated.parent.mkdir(parents=True)
    reference.write_bytes(b"png")
    generated.write_bytes(b"png")

    storage = CreativeAssetStorage()
    assert storage.delete(f"{REFERENCE_PREFIX}reference.png") is True
    assert storage.delete(f"{GENERATED_PREFIX}generated.png") is True
    assert not reference.exists()
    assert not generated.exists()
    assert storage.delete("/tmp/not-owned.png") is False


def test_studio_maintenance_dispatches_cleanup_to_creative_storage():
    with patch.object(CreativeAssetStorage, "delete", return_value=True) as delete:
        assert PostgresStudioMaintenance._delete_asset(
            f"{REFERENCE_PREFIX}reference.png"
        ) is True
    delete.assert_called_once_with(f"{REFERENCE_PREFIX}reference.png")


def test_resources_add_file_upload_is_preparation_not_false_completion():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref="ci:project-1", capabilities=("workspace",))
    arguments = {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "mode": "file_upload", "category": "reference", "description": "Arquivo original",
    }
    with patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_source_service.prepare_upload",
               return_value={"upload_url": "/workspace/mcp/uploads", "upload_token": "signed"}) as prepare, \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.operations.execute") as execute:
        result = add_resource(context, arguments)
    assert result["status"] == "awaiting_upload"
    assert result["resource_created"] is False
    execute.assert_not_called()
    prepare.assert_called_once_with(
        context, request_id=arguments["request_id"], use_as_knowledge=None,
        category="reference", description="Arquivo original",
    )


def test_external_reference_rolls_back_when_optional_table_is_absent():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref="ci:project-1", capabilities=("workspace",))
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"available": False}
    with patch("aicentralv2.cadu_workspace.workspace_ingestion_service.get_db", return_value=connection):
        result = _preserve_external_reference(context, {
            "url": "https://example.com/item", "title": "Item", "provider": "web",
            "resource_kind": "web_page", "access_type": "public", "connector_recommended": False,
        })
    assert result == {"available": False}
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()


def test_resources_inspect_input_routes_text_without_persisting_it():
    with patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_source_service.classify_intake",
               return_value={"input_type": "text", "purpose": "artifact"}) as classify:
        result = inspect_input(Mock(), {"text": "Transforme este conteúdo em documento"})
    assert result["recommended_tool"] == "resources.add"
    assert result["recommended_mode"] == "editable"
    classify.assert_called_once_with(text="Transforme este conteúdo em documento")


def test_update_resource_metadata_uses_canonical_service_and_operation_receipt():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref="ci:project-1", capabilities=("workspace",))
    arguments = {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "resource_id": "resource-1",
        "changes": {"title": "Página da campanha", "tags": ["campanha", "site"]},
    }
    with patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_resource_service.update_resource_metadata",
               return_value={"id": "resource-1", "title": "Página da campanha"}) as update, \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.operations.execute",
               side_effect=lambda request_id, ctx, name, payload, operation: operation()):
        result = update_metadata(context, arguments)
    assert result["title"] == "Página da campanha"
    update.assert_called_once_with(context, "resource-1", arguments["changes"])


def test_set_archived_is_explicit_recoverable_and_source_aware():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref="ci:project-1", capabilities=("workspace",))
    arguments = {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "confirmed": True,
        "resource_id": "resource-1", "archived": True,
    }
    with patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_resource_service.set_resource_archived",
               return_value={"resource_id": "resource-1", "archived": True, "recoverable": True}) as archive, \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.operations.execute",
               side_effect=lambda request_id, ctx, name, payload, operation: operation()):
        result = set_archived(context, arguments)
    assert result["archived"] is True
    assert result["recoverable"] is True
    archive.assert_called_once_with(context, "resource-1", True)


def test_artifact_restore_returns_its_previous_status():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref="ci:project-1", capabilities=("workspace",))
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.rowcount = 1
    with patch.object(project_resource_service, "get_db", return_value=connection), \
         patch.object(project_resource_service, "get_resource", side_effect=[
             {"id": "resource-1", "source_system": "cadu_workspace_artifacts", "source_id": "artifact-1"},
             {"id": "resource-1", "status": "draft"},
         ]), patch.object(project_resource_service, "reconcile"):
        result = project_resource_service.set_resource_archived(context, "resource-1", False)
    assert result["status"] == "draft"
    statement = " ".join(cursor.execute.call_args_list[0].args[0].split())
    assert "COALESCE(archived_from_status,'active')" in statement


def test_archived_native_resource_advertises_restore_not_edit():
    result = resource_capabilities({
        "id": "artifact-1", "source_system": "cadu_workspace_artifacts",
        "resource_type": "artifact", "category": "document", "status": "archived", "version": 4,
    })
    assert result["actions"]["archive"] is False
    assert result["actions"]["restore"] is True
    assert result["actions"]["edit_content"] is False


def test_create_editable_copy_preserves_source_and_registers_relation():
    context = RequestContext(
        organization_id=12, client_id=12, user_id=7, conversation_id="conversation-1",
        surface="workspace", project_ref="ci:project-1", capabilities=("workspace",),
    )
    arguments = {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "source_resource_id": "76a6326b-1f99-4d20-9db8-ab0142262934",
        "type": "document", "title": "Versão editável", "content": {"html": "<p>Conteúdo</p>"},
    }
    with patch("aicentralv2.cadu_workspace.mcp.tools.resources._project_resource",
               return_value={"id": arguments["source_resource_id"]}), \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_resource_service.resource_capabilities",
               return_value={"editor": None, "actions": {"create_editable_copy": True}}), \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.artifact_service.create_draft",
               return_value={"id": "artifact-1", "current_version": 1}) as create, \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_resource_service.reconcile"), \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_resource_service.resource_id_for_source",
               return_value="201ad8fe-f482-4c81-bd75-f3105fc4bd31"), \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_resource_service.relate_resources",
               return_value={"id": 9, "relation_type": "derived_from"}) as relate, \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.operations.execute",
               side_effect=lambda request_id, ctx, name, payload, operation: operation()):
        result = create_editable_copy(context, arguments)

    assert result["preserved_original"] is True
    assert result["source_resource_id"] == arguments["source_resource_id"]
    assert result["edit_mode"] == "native"
    assert create.call_args.kwargs["artifact_id"]
    relate.assert_called_once_with(
        12, "ci:project-1", "201ad8fe-f482-4c81-bd75-f3105fc4bd31",
        arguments["source_resource_id"], "derived_from",
        metadata={"artifact_id": create.call_args.kwargs["artifact_id"], "preserved_original": True},
    )


def test_resource_versions_use_artifact_history_without_inventing_provider_versions():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref="ci:project-1", capabilities=("workspace",))
    with patch("aicentralv2.cadu_workspace.mcp.tools.resources._project_resource",
               return_value={"source_system": "cadu_workspace_artifacts", "source_id": "artifact-1"}), \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.artifact_service.list_versions",
               return_value=[{"version": 2}, {"version": 1}]) as versions:
        result = list_resource_versions(context, {"resource_id": "resource-1", "limit": 10})
    assert result["complete"] is True
    assert result["version_source"] == "cadu"
    versions.assert_called_once_with(context, "artifact-1", limit=10)


def test_relate_resources_is_idempotent_and_does_not_mutate_content():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", project_ref="ci:project-1", capabilities=("workspace",))
    arguments = {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "source_resource_id": "76a6326b-1f99-4d20-9db8-ab0142262934",
        "target_resource_id": "201ad8fe-f482-4c81-bd75-f3105fc4bd31",
        "relation_type": "uses", "description": "Imagem usada na página",
    }
    with patch("aicentralv2.cadu_workspace.mcp.tools.resources._project_resource", return_value={"id": "ok"}) as get, \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.project_resource_service.relate_resources",
               return_value={"id": 4, "relation_type": "uses"}) as relate, \
         patch("aicentralv2.cadu_workspace.mcp.tools.resources.operations.execute",
               side_effect=lambda request_id, ctx, name, payload, operation: operation()):
        result = relate_resources(context, arguments)
    assert result["relation_type"] == "uses"
    assert get.call_count == 2
    relate.assert_called_once_with(
        12, "ci:project-1", arguments["source_resource_id"], arguments["target_resource_id"], "uses",
        metadata={"description": "Imagem usada na página"},
    )


def test_public_key_scopes_require_explicit_google_write_permission():
    principal = PublicMcpPrincipal(
        key_id="key", client_id=12, user_id=7, client_type="cursor", label="Cursor",
        scopes=("resources:read", "projects:read", "google:read"), context=RequestContext(
            organization_id=12, client_id=12, user_id=7, conversation_id=None,
            surface="workspace", project_ref="ci:project-1", capabilities=("workspace",),
        ),
    )
    ensure_scope(principal, "google.list_meet_artifacts")
    try:
        ensure_scope(principal, "google.link_resource_to_project")
    except PublicMcpAuthError as exc:
        assert "google:write" in str(exc)
    else:
        raise AssertionError("google:write deveria ser exigido para vínculos")


def test_public_key_scopes_separate_project_content_from_admin_writes():
    principal = PublicMcpPrincipal(
        key_id="key", client_id=12, user_id=7, client_type="cursor", label="Cursor",
        scopes=("resources:read", "projects:read", "google:read"), context=RequestContext(
            organization_id=12, client_id=12, user_id=7, conversation_id=None,
            surface="workspace", project_ref="ci:project-1", capabilities=("workspace",),
        ),
    )
    with pytest.raises(PublicMcpAuthError, match="projects:content_write"):
        ensure_scope(principal, "projects.create_link_reference")
    assert "projects:content_write" in DEFAULT_SCOPES
    content_principal = PublicMcpPrincipal(
        key_id="key", client_id=12, user_id=7, client_type="cursor", label="Cursor",
        scopes=tuple(DEFAULT_SCOPES), context=principal.context,
    )
    ensure_scope(content_principal, "projects.create_link_reference")
    ensure_scope(content_principal, "projects.create_note")
    ensure_scope(content_principal, "projects.prepare_source_upload")
    with pytest.raises(PublicMcpAuthError, match="projects:write"):
        ensure_scope(content_principal, "workspace.update_project_context")
    with patch("aicentralv2.cadu_public_mcp.auth.repository.actor", return_value={"organization_id": 12}), \
         patch("aicentralv2.cadu_public_mcp.auth.repository.account_role", return_value="member"), \
         pytest.raises(PublicMcpAuthError, match="administradores"):
        ensure_scope(content_principal, "credits.purchase_package")


def test_public_usage_record_commits_telemetry():
    connection = MagicMock()
    with patch.object(usage, "available", return_value=True), patch.object(usage, "get_db", return_value=connection):
        usage.record(
            key_id="key", client_id=12, user_id=7, client_type="cursor",
            method="tools/call", tool_name="resources.search", status="completed",
        )
    connection.commit.assert_called_once_with()


def test_resource_search_returns_registry_metadata_and_indexed_evidence():
    context = RequestContext(
        organization_id=12, client_id=12, user_id=7, conversation_id=None,
        surface="workspace", project_ref="ci:project-1", capabilities=("workspace",),
    )
    with patch(
        "aicentralv2.cadu_workspace.mcp.tools.resources.project_resource_service.search_resources",
        return_value=[{"id": "resource-1", "title": "Briefing"}],
    ), patch(
        "aicentralv2.cadu_workspace.mcp.tools.resources.project_knowledge_context",
        return_value='{"fontes_verificadas":[{"resource_id":"resource-1","trecho":"Aprovado"}]}',
    ):
        result = search_resources(context, {"query": "briefing"})

    assert result["resources"] == [{"id": "resource-1", "title": "Briefing"}]
    assert result["indexed_content"][0]["resource_id"] == "resource-1"
    assert result["search_mode"] == "resource_metadata_plus_hybrid_index"


def test_public_catalog_exposes_safe_brand_site_inspection():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id=None,
                             surface="workspace", capabilities=("workspace",))
    tools = {item["name"]: item for item in load_builtin_tools().list(context, "customer_agent")}
    assert "brands.inspect_site" in PUBLIC_TOOLS
    definition = tools["brands.inspect_site"]
    assert {"website_url", "logo_url", "brand_id"} <= set(definition["inputSchema"]["properties"])
