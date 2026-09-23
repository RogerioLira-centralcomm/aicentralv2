"""Brand-library and audit-selection contracts shared by both MCP transports."""

import json
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_public_mcp.auth import DEFAULT_SCOPES, PublicMcpPrincipal, required_scope
from aicentralv2.cadu_public_mcp.routes import PUBLIC_TOOLS, _public_catalog, _request_context_for_auth
from aicentralv2.cadu_workspace import brand_mcp_service as brands
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools


def _context(brand_ref="studio:81"):
    return RequestContext(organization_id=12, client_id=12, user_id=7,
                          conversation_id=None, surface="conversations", project_ref=None,
                          brand_ref=brand_ref, capabilities=("workspace",))


def test_brand_library_and_logo_tools_are_public_and_scope_separated():
    tools = {item["name"]: item for item in load_builtin_tools().list(_context(), "customer_agent")}
    assert {"brands.list_assets", "brands.prepare_asset_upload", "brands.use_asset_as_logo",
            "brands.delete_asset"} <= PUBLIC_TOOLS
    assert "brand_id" not in tools["brands.list_assets"]["inputSchema"].get("required", [])
    assert required_scope("brands.list_assets") == "projects:read"
    assert required_scope("brands.use_asset_as_logo") == "brands:write"
    assert required_scope("brands.prepare_asset_upload") == "brands:write"
    assert required_scope("brands.delete_asset") == "brands:write"
    assert tools["brands.start_audit"]["inputSchema"]["properties"]["analysis_mode"]["enum"] == ["complete", "deep"]
    assert "existing_asset_ids" in tools["brands.start_audit"]["inputSchema"]["properties"]
    assert "additional_sources" in tools["brands.start_audit"]["inputSchema"]["properties"]
    assert "excluded_sources" in tools["brands.start_audit"]["inputSchema"]["properties"]


def test_brand_asset_mutations_require_admin(monkeypatch):
    monkeypatch.setattr(brands.family_repository, "actor", lambda *_: {
        "id": 7, "organization_id": 12,
    })
    monkeypatch.setattr(brands.family_repository, "account_role", lambda *_: "member")
    with pytest.raises(Exception) as upload_error:
        brands.prepare_asset_upload(_context(), 81, "reference")
    with pytest.raises(Exception) as delete_error:
        brands.delete_asset(_context(), brand_id=81, asset_id=35)
    assert upload_error.value.code == 403
    assert delete_error.value.code == 403


def test_public_brand_context_can_be_passed_in_normal_tool_arguments():
    principal = PublicMcpPrincipal(key_id="key", client_id=12, user_id=7, client_type="codex",
                                   label="Teste", scopes=tuple(DEFAULT_SCOPES), context=_context(None))
    with patch("aicentralv2.cadu_public_mcp.auth.repository.actor", return_value={"organization_id": 12}), \
         patch("aicentralv2.cadu_public_mcp.auth.repository.account_role", return_value="member"):
        catalog = _public_catalog(principal)
    assets = next(item for item in catalog if item["name"] == "brands.list_assets")
    assert "brand_ref" in assets["inputSchema"]["properties"]
    assert _request_context_for_auth({"name": "brands.list_assets",
                                      "arguments": {"brand_ref": "studio:81"}})["brand_ref"] == "studio:81"


def test_current_brand_library_only_returns_approved_assets_of_owned_brand():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = [{"id": 35, "role": "creative", "is_primary": False,
                                    "asset_path": "/static/uploads/image.png", "source_url": None,
                                    "mime_type": "image/png", "metadata": {"display_name": "Imagem da campanha"}}]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch.object(brands, "_brand", return_value={"id": 81}), \
         patch.object(brands, "get_db", return_value=connection), \
         patch("aicentralv2.cadu_workspace.routes._existing_brand_asset_url", return_value="/image.png"):
        result = brands.list_assets(_context())
    assert result["brand_id"] == 81
    assert result["assets"][0]["asset_id"] == 35
    assert result["assets"][0]["preview_url"] == "/image.png"
    assert cursor.execute.call_args.args[1] == (81, 50)
    assert "status='approved'" in cursor.execute.call_args.args[0]


def test_project_context_resolves_only_one_linked_current_brand():
    current = RequestContext(organization_id=12, client_id=12, user_id=7,
                             conversation_id=None, surface="conversations", project_ref="ci:42",
                             capabilities=("workspace",))
    with patch.object(brands.family_repository, "project_brand_links",
                      return_value=[{"project_ref": "ci:42", "brand_ref": "studio:81"},
                                    {"project_ref": "ci:99", "brand_ref": "studio:22"}]):
        assert brands._current_brand_id(current) == 81
    with patch.object(brands.family_repository, "project_brand_links",
                      return_value=[{"project_ref": "ci:42", "brand_ref": "studio:81"},
                                    {"project_ref": "ci:42", "brand_ref": "studio:22"}]), \
         pytest.raises(BadRequest, match="brand_id"):
        brands._current_brand_id(current)


def test_library_image_can_be_promoted_to_logo_without_reupload():
    with patch.object(brands, "_require_admin"), patch.object(brands, "_brand", return_value={"id": 81}), \
         patch("aicentralv2.creative_modeling_service.CreativeModelingService") as service, \
         patch("aicentralv2.cadu_workspace.routes._existing_brand_asset_url", return_value="/logo.png"):
        service.return_value.promote_client_brand_asset_to_logo.return_value = {"id": 35, "asset_path": "/logo.png"}
        result = brands.use_asset_as_logo(_context(), brand_id=None, asset_id=35)
    service.return_value.promote_client_brand_asset_to_logo.assert_called_once_with(81, 35)
    assert result["logo_url"] == "/logo.png"


def test_logo_selection_rejects_unapproved_or_foreign_asset():
    from aicentralv2.creative_modeling_repository import CreativeNotFoundError

    with patch.object(brands, "_require_admin"), patch.object(brands, "_brand", return_value={"id": 81}), \
         patch("aicentralv2.creative_modeling_service.CreativeModelingService") as service:
        service.return_value.promote_client_brand_asset_to_logo.side_effect = CreativeNotFoundError("not found")
        with pytest.raises(BadRequest, match="biblioteca desta marca"):
            brands.use_asset_as_logo(_context(), brand_id=81, asset_id=999)


def test_audit_rejects_assets_from_another_brand_before_queueing():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = []
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch.object(brands, "_require_admin"), \
         patch.object(brands, "_brand", return_value={"id": 81, "website_url": "https://example.com"}), \
         patch.object(brands, "get_db", return_value=connection), \
         patch("aicentralv2.cadu_workspace.routes._start_brand_review_job") as queued:
        with pytest.raises(BadRequest, match="não pertence"):
            brands.start_audit(_context(), request_id="be777b36-a973-419c-802a-886bf1d125b0",
                               brand_id=81, analysis_mode="deep", confirmed_cost=True,
                               existing_asset_ids=[999])
    queued.assert_not_called()


def test_deep_audit_uses_selected_library_image_and_primary_logo():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = [{"id": 35}]
    cursor.fetchone.side_effect = [{"id": 12}, {"analysis_metadata": {}}, {"id": 81}]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch.object(brands, "_require_admin"), \
         patch.object(brands, "_brand", return_value={"id": 81, "website_url": "https://example.com",
                                                       "analysis_metadata": {}}), \
         patch.object(brands, "get_db", return_value=connection), \
         patch("aicentralv2.cadu_workspace.routes._ensure_brand_audit_credit"), \
         patch("aicentralv2.cadu_workspace.routes._start_brand_review_job") as queued:
        result = brands.start_audit(_context(), request_id="be777b36-a973-419c-802a-886bf1d125b0",
                                    brand_id=81, analysis_mode="deep", confirmed_cost=True,
                                    existing_asset_ids=[35],
                                    additional_sources=["https://news.example/interview"],
                                    excluded_sources=["https://reseller.example"])
    assert result["analysis_mode"] == "deep"
    assert result["existing_asset_ids"] == [35, 12]
    assert result["estimated_credits"] == 150000
    assert queued.call_args.kwargs["existing_asset_ids"] == [35, 12]
    assert queued.call_args.kwargs["additional_sources"] == ["https://news.example/interview"]
    assert queued.call_args.kwargs["excluded_sources"] == ["https://reseller.example"]
    update = next(call for call in cursor.execute.call_args_list if "UPDATE cx_clients" in call.args[0])
    metadata = json.loads(update.args[1][1])
    assert metadata["review_pack"]["input"]["existing_asset_ids"] == [35, 12]
    assert metadata["review_pack"]["input"]["additional_sources"] == ["https://news.example/interview"]
    assert metadata["review_pack"]["input"]["excluded_sources"] == ["https://reseller.example"]


def test_complete_audit_automatically_uses_approved_brand_library():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [{"analysis_metadata": {}}, {"id": 81}]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    brand = {"id": 81, "website_url": "https://example.com", "analysis_metadata": {},
             "assets": [{"id": 12, "status": "approved", "is_primary": True,
                         "role": "logo", "asset_path": "/logo.png"},
                        {"id": 35, "status": "approved", "is_primary": False,
                         "role": "creative", "asset_path": "/campaign.png"},
                        {"id": 99, "status": "pending", "asset_path": "/unapproved.png"}]}
    with patch.object(brands, "_require_admin"), patch.object(brands, "_brand", return_value=brand), \
         patch.object(brands, "get_db", return_value=connection), \
         patch("aicentralv2.cadu_workspace.routes._ensure_brand_audit_credit"), \
         patch("aicentralv2.cadu_workspace.routes._start_brand_review_job") as queued:
        result = brands.start_audit(_context(), request_id="be777b36-a973-419c-802a-886bf1d125b0",
                                    brand_id=81, analysis_mode="complete", confirmed_cost=True)
    assert result["existing_asset_ids"] == [12, 35]
    assert queued.call_args.kwargs["existing_asset_ids"] == [12, 35]
