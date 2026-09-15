from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from flask import Flask, session

from aicentralv2.cadu_identity.google_oidc import GoogleLoginError, SCOPES, authorization_url, exchange_code
from aicentralv2.cadu_identity.routes import _resolve_google_user


def _app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    return app


class GoogleIdentityTest(TestCase):
    @patch("aicentralv2.cadu_identity.routes.db.obter_contato_por_email")
    def test_cadu_registration_is_owned_by_php(self, _by_email):
        with self.assertRaisesRegex(GoogleLoginError, "aplicativo Cadu"):
            _resolve_google_user({
                "realm": "cadu",
                "email": "pessoa@gmail.com",
                "name": "Pessoa Nova",
            })

    @patch("aicentralv2.cadu_identity.routes.db.obter_contato_por_email", return_value=None)
    def test_centralx_google_login_never_auto_registers(self, _by_email):
        with self.assertRaisesRegex(GoogleLoginError, "@centralcomm.media"):
            _resolve_google_user({
                "realm": "centralx",
                "email": "pessoa@gmail.com",
                "name": "Pessoa Externa",
            })

    def test_login_scope_is_separate_and_minimal(self):
        self.assertEqual(SCOPES, "openid email profile")
        self.assertNotIn("calendar", SCOPES)

    def test_authorization_uses_state_nonce_and_pkce(self):
        app = _app()
        with app.test_request_context("/"):
            config = {"configured": True, "client_id": "login-client.apps.googleusercontent.com", "client_secret": "secret", "redirect_uri": "https://auth.centralcomm.media/auth/google/callback", "allowed_domain": "centralcomm.media"}
            with patch("aicentralv2.cadu_identity.google_oidc._configuration", return_value=config):
                target = authorization_url("centralx")
            query = parse_qs(urlparse(target).query)
            self.assertEqual(query["scope"], ["openid email profile"])
            self.assertEqual(query["redirect_uri"], ["https://auth.centralcomm.media/auth/google/callback"])
            self.assertEqual(query["code_challenge_method"], ["S256"])
            self.assertEqual(query["hd"], ["centralcomm.media"])
            self.assertTrue(session["google_auth_state"])
            self.assertTrue(session["google_auth_nonce"])
            self.assertTrue(session["google_auth_pkce"])

    def test_state_mismatch_stops_before_token_exchange(self):
        app = _app()
        with app.test_request_context("/"):
            session.update(
                google_auth_state="expected",
                google_auth_nonce="nonce",
                google_auth_pkce="verifier",
                google_auth_realm="centralx",
            )
            with patch("aicentralv2.cadu_identity.google_oidc.requests.post") as post:
                with self.assertRaises(GoogleLoginError):
                    exchange_code("code", "different")
                post.assert_not_called()

    def test_verified_google_identity_is_returned_without_api_scopes(self):
        app = _app()
        response = Mock(ok=True)
        response.json.return_value = {"id_token": "signed-token"}
        identity = {
            "sub": "google-user-1",
            "email": "apolo@centralcomm.media",
            "email_verified": True,
            "name": "Apolo",
            "picture": "https://lh3.googleusercontent.com/a/photo",
            "nonce": "nonce",
        }
        with app.test_request_context("/"):
            session.update(
                google_auth_state="state",
                google_auth_nonce="nonce",
                google_auth_pkce="verifier",
                google_auth_realm="centralx",
            )
            config = {"configured": True, "client_id": "login-client.apps.googleusercontent.com", "client_secret": "secret", "redirect_uri": "https://auth.centralcomm.media/auth/google/callback"}
            with patch("aicentralv2.cadu_identity.google_oidc._configuration", return_value=config), patch("aicentralv2.cadu_identity.google_oidc.requests.post", return_value=response) as post, patch(
                "aicentralv2.cadu_identity.google_oidc.id_token.verify_oauth2_token",
                return_value=identity,
            ):
                result = exchange_code("code", "state")
            self.assertEqual(result["email"], "apolo@centralcomm.media")
            self.assertEqual(result["picture"], "https://lh3.googleusercontent.com/a/photo")
            sent = post.call_args.kwargs["data"]
            self.assertEqual(sent["grant_type"], "authorization_code")
            self.assertEqual(sent["code_verifier"], "verifier")
