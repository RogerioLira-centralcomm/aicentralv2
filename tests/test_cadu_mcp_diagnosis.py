from aicentralv2.cadu_public_mcp import diagnosis
from aicentralv2.cadu_public_mcp.routes import PUBLIC_TOOLS


def _status(result):
    return {step["id"]: step["status"] for step in result["steps"]}


def test_no_grants_waits_for_the_host():
    result = diagnosis.diagnose(oauth_ready=True, grants=[], public_tools=PUBLIC_TOOLS)
    assert _status(result) == {"infra": "concluida", "registered": "pendente", "consent": "pendente",
                               "tools": "pendente", "first_use": "pendente"}
    assert result["connected"] is False


def test_oauth_unavailable_blocks_with_a_recovery_action():
    result = diagnosis.diagnose(oauth_ready=False, grants=[], public_tools=PUBLIC_TOOLS)
    infra = result["steps"][0]
    assert infra["status"] == "falhou" and "migração" in infra["action"]


def test_active_grant_with_scopes_lists_tools_and_waits_for_first_use():
    grant = {"id": "g1", "status": "active", "scopes": ["projects:read", "resources:read"], "modules": None, "last_used_at": None}
    result = diagnosis.diagnose(oauth_ready=True, grants=[grant], public_tools=PUBLIC_TOOLS)
    assert _status(result)["consent"] == "concluida" and _status(result)["tools"] == "concluida"
    assert _status(result)["first_use"] == "pendente"
    assert result["connected"] is True and result["tool_count"] > 0 and result["grant_id"] == "g1"


def test_grant_without_scopes_reports_no_tools():
    grant = {"id": "g1", "status": "active", "scopes": [], "modules": None, "last_used_at": None}
    result = diagnosis.diagnose(oauth_ready=True, grants=[grant], public_tools=PUBLIC_TOOLS)
    assert _status(result)["tools"] == "falhou" and result["connected"] is False


def test_revoked_only_connection_fails_consent_and_never_exposes_secrets():
    grant = {"id": "g1", "status": "revoked", "scopes": ["projects:read"], "modules": None, "last_used_at": None}
    result = diagnosis.diagnose(oauth_ready=True, grants=[grant], public_tools=PUBLIC_TOOLS)
    assert _status(result)["consent"] == "falhou"
    assert "token" not in repr(result).lower()


def test_first_use_marks_the_journey_complete():
    grant = {"id": "g1", "status": "active", "scopes": ["projects:read"], "modules": None, "last_used_at": "2026-10-05T10:00:00"}
    assert _status(diagnosis.diagnose(oauth_ready=True, grants=[grant], public_tools=PUBLIC_TOOLS))["first_use"] == "concluida"


def test_page_limit_above_the_maximum_is_served_at_the_maximum():
    from aicentralv2.cadu_workspace.mcp.registry import _clamp_page_limits, _validate
    schema = {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
              "additionalProperties": False}
    arguments = {"limit": 100}
    _clamp_page_limits(arguments, schema)
    _validate(arguments, schema)
    assert arguments["limit"] == 50
    low = {"limit": 0}
    _clamp_page_limits(low, schema)
    assert low["limit"] == 0  # lower bounds are still enforced by validation


def test_server_instructions_only_name_tools_the_public_surface_exposes():
    import re
    from aicentralv2.cadu_public_mcp import guidance
    mentioned = set(re.findall(r"\b((?:projects|artifacts|resources|brands|media|workspace|intent|context|operations)\.[a-z_]+)\b",
                               guidance.SERVER_INSTRUCTIONS))
    assert {"projects.create_note", "media.start_studio_session", "brands.get_context"} <= mentioned
    assert mentioned - PUBLIC_TOOLS == set()


def test_external_media_capabilities_follow_what_the_connection_may_do():
    from aicentralv2.cadu_public_mcp import guidance
    internal = {"operations": {"image": {"required": ["request_id", "confirmed"]}},
                "generation_tools": {"image": "media.generate_image"}, "generation_available_via_mcp": ["image"],
                "image_cost_estimate": {"estimated_total": 1}, "video_plan_tool": "media.plan_video"}
    locked = guidance.external_media_capabilities(internal)
    assert locked["how_to_create"] == "media.start_studio_session"
    assert locked["generation_available_via_mcp"] == [] and "direct_generation" not in locked
    assert "generation_tools" not in locked and "operations" not in locked and "video_plan_tool" not in locked
    assert locked["image_cost_estimate"] == {"estimated_total": 1}
    granted = guidance.external_media_capabilities(internal, can_generate=True)
    assert granted["generation_available_via_mcp"] == ["image", "image_edit"]
    assert granted["direct_generation"]["image"] == "media.generate_image"


def test_studio_links_open_on_the_right_page_with_the_workspace_project():
    from urllib.parse import parse_qs, urlparse
    from unittest.mock import patch
    from aicentralv2.cadu_workspace import media_creation_service as service
    with patch.object(service, "product_url", side_effect=lambda product, path: f"https://studio.test{path}"):
        url = service.studio_session_url("/criar", 12, "sess-1", "ci:abc-123")
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        assert parsed.path == "/criar"
        assert query["project_id"] == ["abc-123"] and query["creative_client_id"] == ["12"]
        assert query["studio_session_id"] == ["sess-1"]
        assert "project_id" not in parse_qs(urlparse(service.studio_session_url("/criar", 12, "s", "workspace:x")).query)
        assert service._studio_url(12, "s", "https://img/x.png", "ci:p")


def test_signed_out_studio_visitor_returns_to_the_exact_page_after_login():
    from urllib.parse import parse_qs, urlparse
    from unittest.mock import patch
    from aicentralv2 import creative_modeling_routes as routes
    destination = "https://studio.centralcomm.media/criar?studio_session_id=s&creative_client_id=1&project_id=p"
    with patch.object(routes, "workspace_public_url", return_value="https://workspace.centralcomm.media/"):
        target = routes._workspace_login_for(destination)
    parsed = urlparse(target)
    assert (parsed.netloc, parsed.path) == ("workspace.centralcomm.media", "/login")
    assert parse_qs(parsed.query)["next"] == [destination]
    with patch.object(routes, "workspace_public_url", return_value="/workspace/"):
        assert routes._workspace_login_for(destination) == "/workspace/"


def test_consent_offers_paid_generation_unchecked_and_never_by_default():
    import re
    from pathlib import Path
    from aicentralv2.cadu_public_mcp import oauth
    from aicentralv2.cadu_public_mcp.auth import DEFAULT_SCOPES
    assert "media:generate" in oauth.OPTIONAL_CONSENT_SCOPES and "media:generate" not in DEFAULT_SCOPES
    template = (Path(__file__).resolve().parents[1] / "aicentralv2/templates/cadu_workspace/mcp_oauth_consent.html").read_text()
    default_line = re.search(r"set default_scopes = \[(.*?)\]", template).group(1)
    assert "media:generate" not in default_line
    assert "'media:generate':" in template  # has a readable label on the consent screen


def test_grant_without_modules_counts_tools_from_every_module():
    scopes = ["projects:read", "resources:read", "brands:write", "projects:content_write"]
    everything = diagnosis.tools_for_grant(PUBLIC_TOOLS, scopes, None)
    marketing_only = diagnosis.tools_for_grant(PUBLIC_TOOLS, scopes, ["marketing"])
    assert len(everything) > len(marketing_only)
