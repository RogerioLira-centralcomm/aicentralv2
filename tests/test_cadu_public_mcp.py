from unittest.mock import MagicMock, Mock, patch
from io import BytesIO

from flask import Flask

from aicentralv2.cadu_public_mcp.auth import PublicMcpAuthError, PublicMcpPrincipal, _public_context, ensure_scope
from aicentralv2.cadu_public_mcp import usage
from aicentralv2.cadu_public_mcp.routes import PUBLIC_MCP_PATH, PUBLIC_TOOLS, bp
from aicentralv2.cadu_public_mcp.usage import tool_cost
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


def test_public_transport_is_separate_and_requires_bearer_auth():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WORKSPACE_URL="https://workspace.centralcomm.media")
    app.register_blueprint(bp)
    client = app.test_client()

    metadata = client.get("/.well-known/cadu-mcp-public")
    assert metadata.status_code == 200
    assert metadata.get_json()["endpoint"].endswith(PUBLIC_MCP_PATH)
    assert metadata.get_json()["authentication"]["type"] == "bearer_api_key"

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

def test_public_catalog_is_allowlisted_and_metered():
    assert "google.sync_workspace" not in PUBLIC_TOOLS
    assert "google.link_resource_to_project" in PUBLIC_TOOLS
    assert {"resources.search", "resources.get", "resources.capabilities"} <= PUBLIC_TOOLS
    assert tool_cost("google.get_connector_status") == 1
    assert tool_cost("reports.compare_report_to_plan") == 3


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


def test_public_key_scopes_require_project_write_for_link_references():
    principal = PublicMcpPrincipal(
        key_id="key", client_id=12, user_id=7, client_type="cursor", label="Cursor",
        scopes=("resources:read", "projects:read", "google:read"), context=RequestContext(
            organization_id=12, client_id=12, user_id=7, conversation_id=None,
            surface="workspace", project_ref="ci:project-1", capabilities=("workspace",),
        ),
    )
    try:
        ensure_scope(principal, "projects.create_link_reference")
    except PublicMcpAuthError as exc:
        assert "projects:write" in str(exc)
    else:
        raise AssertionError("projects:write deveria ser exigido para referências")


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
