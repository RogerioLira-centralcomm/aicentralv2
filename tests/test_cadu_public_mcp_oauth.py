import base64
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from unittest.mock import MagicMock

import pytest
from flask import Flask

from aicentralv2.cadu_public_mcp import auth, oauth
from aicentralv2.cadu_public_mcp.routes import PUBLIC_MCP_PATH, bp


def _app():
    app = Flask(__name__, template_folder="../aicentralv2/templates")
    app.config.update(SECRET_KEY="test", WORKSPACE_URL="https://workspace.centralcomm.media")
    app.register_blueprint(bp)
    return app


def test_oauth_discovery_is_consistent_with_public_mcp_resource():
    client = _app().test_client()

    protected = client.get("/.well-known/oauth-protected-resource/mcp/cadu/v1")
    authorization = client.get("/.well-known/oauth-authorization-server")

    assert protected.status_code == 200
    assert protected.get_json()["resource"] == "https://workspace.centralcomm.media/mcp/cadu/v1"
    assert protected.get_json()["authorization_servers"] == ["https://workspace.centralcomm.media"]
    assert authorization.get_json()["code_challenge_methods_supported"] == ["S256"]
    assert authorization.get_json()["token_endpoint_auth_methods_supported"] == ["none"]
    assert authorization.get_json()["authorization_response_iss_parameter_supported"] is True
    assert authorization.headers["Cache-Control"] == "no-store"


def test_oauth_readiness_requires_every_table_used_by_the_flow():
    with patch("aicentralv2.cadu_public_mcp.oauth._table_available", return_value=True) as table:
        assert oauth.available() is True
    assert {call.args[0] for call in table.call_args_list} == {
        "cadu_oauth_clients", "cadu_oauth_grants", "cadu_oauth_authorization_codes",
        "cadu_oauth_access_tokens", "cadu_oauth_refresh_tokens",
    }
    with patch("aicentralv2.cadu_public_mcp.oauth._table_available",
               side_effect=lambda name: name != "cadu_oauth_refresh_tokens"):
        assert oauth.available() is False


def test_public_mcp_urls_have_branded_icon_and_browser_landing():
    client = _app().test_client()
    icon = client.get("/mcp/cadu/v1/icon.png")
    favicon = client.get("/mcp/cadu/v1/favicon.ico")
    landing = client.get(PUBLIC_MCP_PATH, headers={"Accept": "text/html"})
    transport_get = client.get(PUBLIC_MCP_PATH, headers={"Accept": "text/event-stream"})

    assert icon.status_code == 200 and icon.mimetype == "image/png"
    assert favicon.status_code == 200 and favicon.mimetype == "image/x-icon"
    assert landing.status_code == 200 and b"Cadu MCP" in landing.data
    assert transport_get.status_code == 405


def test_unauthenticated_mcp_challenge_points_to_protected_resource_metadata():
    client = _app().test_client()
    from aicentralv2.cadu_public_mcp.auth import PublicMcpAuthError
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate",
               side_effect=PublicMcpAuthError("invalid")):
        response = client.post(PUBLIC_MCP_PATH, json={"jsonrpc": "2.0", "id": "1",
                                                      "method": "tools/list", "params": {}})
    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["WWW-Authenticate"]
    assert "oauth2" in response.headers["X-Cadu-MCP-Auth"]
    challenge = response.get_json()["error"]["data"]["_meta"]["mcp/www_authenticate"]
    assert challenge and "resource_metadata=" in challenge[0]


def test_2026_transport_requires_routing_headers_before_authentication():
    client = _app().test_client()
    response = client.post(PUBLIC_MCP_PATH, headers={"MCP-Protocol-Version": "2026-07-28"},
                           json={"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {}})
    assert response.status_code == 400
    assert "Mcp-Method" in response.get_json()["error"]["message"]


def test_server_discover_preserves_stateless_public_capabilities():
    client = _app().test_client()
    principal = MagicMock()
    principal.context = MagicMock(capabilities=("workspace",))
    principal.scopes = ("contexts:read",)
    with patch("aicentralv2.cadu_public_mcp.routes.auth.authenticate", return_value=principal):
        response = client.post(PUBLIC_MCP_PATH, json={"jsonrpc": "2.0", "id": "1",
                                                      "method": "server/discover", "params": {}})
    assert response.status_code == 200
    assert response.get_json()["result"]["protocolVersion"] == "2026-07-28"


def test_explicit_empty_scopes_never_expand_to_defaults():
    assert auth.normalize_scopes([], allow_writes=True) == ()
    assert auth.normalize_scopes("", allow_writes=True) == ()
    assert set(auth.normalize_scopes(None, allow_writes=True)) == set(auth.DEFAULT_SCOPES)


@pytest.mark.parametrize("uri", [
    "javascript:alert(1)",
    "http://example.com/callback",
    "https://user:pass@example.com/callback",
    "https://example.com/callback#fragment",
])
def test_redirect_uri_rejects_unsafe_destinations(uri):
    with pytest.raises(oauth.OAuthError):
        oauth.validate_redirect_uri(uri)


def test_redirect_uri_accepts_https_and_native_loopback():
    assert oauth.validate_redirect_uri("https://client.example/callback") == "https://client.example/callback"
    assert oauth.validate_redirect_uri("http://127.0.0.1:32123/callback") == "http://127.0.0.1:32123/callback"
    assert oauth._redirect_matches("http://127.0.0.1/callback", "http://127.0.0.1:32123/callback")
    assert not oauth._redirect_matches("http://127.0.0.1/other", "http://127.0.0.1:32123/callback")


def test_dynamic_client_metadata_rejects_untrusted_logo_or_homepage_urls():
    with pytest.raises(oauth.OAuthError, match="HTTPS"):
        oauth._optional_https_url("data:image/svg+xml,unsafe", "logo_uri")
    assert oauth._optional_https_url("https://client.example/logo.svg", "logo_uri") == "https://client.example/logo.svg"


def test_dynamic_client_registration_enforces_per_origin_rate_limit():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = {"ip_recent": oauth.DCR_PER_IP_HOURLY_LIMIT, "global_recent": 10}
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch("aicentralv2.cadu_public_mcp.oauth.available", return_value=True), \
         patch("aicentralv2.cadu_public_mcp.oauth.get_db", return_value=connection), \
         pytest.raises(oauth.OAuthError) as error:
        oauth.register_client({
            "client_name": "Cliente de teste",
            "redirect_uris": ["https://client.example/callback"],
        }, registration_ip="203.0.113.10")
    assert error.value.status == 429
    assert error.value.error == "too_many_requests"
    assert "pg_advisory_xact_lock" in cursor.execute.call_args_list[0].args[0]
    connection.rollback.assert_called_once()


def test_dynamic_client_registration_rate_response_advertises_retry_window():
    client = _app().test_client()
    with patch("aicentralv2.cadu_public_mcp.routes.oauth.register_client",
               side_effect=oauth.OAuthError("too_many_requests", "Tente mais tarde.", 429)):
        response = client.post("/oauth/register", json={"redirect_uris": ["https://client.example/callback"]})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "3600"


def test_authorization_request_requires_pkce_s256_and_known_scopes():
    values = {
        "client_id": "client",
        "redirect_uri": "https://client.example/callback",
        "response_type": "code",
        "resource": "https://workspace.centralcomm.media/mcp/cadu/v1",
        "scope": "projects:read",
        "code_challenge": "a" * 43,
        "code_challenge_method": "S256",
    }
    with patch("aicentralv2.cadu_public_mcp.oauth.load_client", return_value={"id": "internal"}):
        result = oauth.validate_authorization_request(values)
        assert result["scopes"] == ("projects:read",)
        with pytest.raises(oauth.OAuthError, match="PKCE"):
            oauth.validate_authorization_request(values | {"code_challenge_method": "plain"})
        with pytest.raises(Exception, match="Escopo"):
            oauth.validate_authorization_request(values | {"scope": "root:all"})
        with pytest.raises(oauth.OAuthError) as empty:
            oauth.validate_authorization_request(values | {"scope": ""})
        assert empty.value.error == "invalid_scope"


def test_authorization_code_rejects_empty_effective_consent():
    with pytest.raises(oauth.OAuthError) as error:
        oauth.create_authorization_code(
            authorization={"scopes": ("account:write",)}, client_id=12, user_id=7, scopes=[]
        )
    assert error.value.error == "invalid_scope"


def test_access_token_rejects_empty_token_grant_scope_intersection():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = {
        "credential_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "grant_id": "ce777b36-a973-419c-802a-886bf1d125b0",
        "resource": "https://workspace.centralcomm.media/mcp/cadu/v1",
        "token_scopes": ["projects:read"],
        "grant_scopes": ["account:read"],
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        "revoked_at": None,
        "status": "active",
        "client_id": 12,
        "user_id": 7,
        "default_project_ref": None,
        "client_name": "Cliente",
        "oauth_client_id": "oauth-client",
    }
    connection = MagicMock()
    connection.cursor.return_value = cursor
    with patch("aicentralv2.cadu_public_mcp.oauth.available", return_value=True), \
         patch("aicentralv2.cadu_public_mcp.oauth.get_db", return_value=connection), \
         pytest.raises(auth.PublicMcpAuthError, match="sem permissões"):
        oauth.load_access_token("cadu_oauth_at_valid")


def test_pkce_challenge_matches_rfc_7636_computation():
    verifier = "codex-verifier-with-enough-entropy-1234567890"
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    assert oauth._pkce_challenge(verifier) == expected


def test_token_endpoint_dispatches_authorization_code_and_refresh_grants():
    client = _app().test_client()
    tokens = {"access_token": "access", "token_type": "Bearer", "expires_in": 900}
    with patch("aicentralv2.cadu_public_mcp.routes.oauth.exchange_code", return_value=tokens) as exchange:
        response = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": "code", "client_id": "client",
            "redirect_uri": "https://client.example/callback", "code_verifier": "verifier",
            "resource": "https://workspace.centralcomm.media/mcp/cadu/v1",
        })
    assert response.status_code == 200
    assert response.get_json()["access_token"] == "access"
    exchange.assert_called_once()

    with patch("aicentralv2.cadu_public_mcp.routes.oauth.refresh_tokens", return_value=tokens) as refresh:
        response = client.post("/oauth/token", data={
            "grant_type": "refresh_token", "refresh_token": "refresh", "client_id": "client",
            "resource": "https://workspace.centralcomm.media/mcp/cadu/v1",
        })
    assert response.status_code == 200
    refresh.assert_called_once()


def test_token_endpoint_normalizes_protocol_errors():
    client = _app().test_client()
    response = client.post("/oauth/token", data={"grant_type": "password"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "unsupported_grant_type"
    assert response.headers["Cache-Control"] == "no-store"


def test_revocation_reports_operational_failure():
    client = _app().test_client()
    with patch("aicentralv2.cadu_public_mcp.routes.oauth.revoke_token", side_effect=RuntimeError("db down")):
        response = client.post("/oauth/revoke", data={"token": "known"})
    assert response.status_code == 503
    assert response.get_json()["error"] == "temporarily_unavailable"
