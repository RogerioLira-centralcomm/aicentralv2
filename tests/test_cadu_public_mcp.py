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
from aicentralv2.cadu_workspace.mcp.tools.resources import search_resources
from aicentralv2.cadu_workspace.project_resource_service import resource_capabilities


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
                             surface="workspace", project_ref=None, capabilities=("workspace",))
    principal = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="codex",
                                   label="Teste", scopes=tuple(DEFAULT_SCOPES), context=context)
    with patch("aicentralv2.cadu_public_mcp.auth.repository.actor", return_value={"organization_id": 12}), \
         patch("aicentralv2.cadu_public_mcp.auth.repository.account_role", return_value="member"):
        catalog = _public_catalog(principal)
    upload = next(item for item in catalog if item["name"] == "projects.prepare_source_upload")
    assert "project_ref" in upload["inputSchema"]["properties"]
    assert upload["securitySchemes"] == [{"type": "oauth2", "scopes": ["projects:content_write"]}]
    assert upload["_meta"]["securitySchemes"] == upload["securitySchemes"]
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


def test_non_ledger_write_receipt_does_not_promise_operations_get():
    assert "media.start_studio_session" not in RECOVERABLE_OPERATION_TOOLS
    assert "brands.start_audit" not in RECOVERABLE_OPERATION_TOOLS
    assert "projects.create_note" in RECOVERABLE_OPERATION_TOOLS

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


def test_semantic_resource_tools_are_registered_for_external_agents():
    context = RequestContext(
        organization_id=12, client_id=12, user_id=7, conversation_id=None,
        surface="workspace", project_ref="ci:project-1",
        capabilities=("workspace", "planner", "studio", "reports", "artifacts"),
    )
    names = {item["name"] for item in load_builtin_tools().list(context, "customer_agent")}
    assert {"resources.search", "resources.get", "resources.capabilities"} <= names


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
