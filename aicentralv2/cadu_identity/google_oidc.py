"""Google OpenID Connect client used only for authentication."""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import requests
from flask import current_app, session
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token


AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "openid email profile"
REALM_PROVIDERS = {
    "centralx": "google_login_centralx",
    "cadu": "google_login_cadu",
}


class GoogleLoginError(RuntimeError):
    pass


def _configuration(realm: str) -> dict:
    provider = REALM_PROVIDERS.get(realm)
    if not provider:
        raise GoogleLoginError("Destino de autenticação desconhecido.")
    from ..services.integration_credentials import get_configuration
    config = get_configuration(provider, include_secrets=True)
    if not config.get("configured"):
        raise GoogleLoginError("O login com Google ainda não foi configurado para este produto.")
    return config


def authorization_url(realm: str) -> str:
    config = _configuration(realm)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    session["google_auth_state"] = state
    session["google_auth_nonce"] = nonce
    session["google_auth_pkce"] = verifier
    session["google_auth_realm"] = realm
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    allowed_domain = str(config.get("allowed_domain") or "").strip()
    if allowed_domain:
        params["hd"] = allowed_domain
    return f"{AUTHORIZATION_URL}?{urlencode(params)}"


def exchange_code(code: str, state: str) -> dict:
    expected_state = str(session.pop("google_auth_state", ""))
    expected_nonce = str(session.pop("google_auth_nonce", ""))
    verifier = str(session.pop("google_auth_pkce", ""))
    realm = str(session.pop("google_auth_realm", ""))
    if not expected_state or not secrets.compare_digest(expected_state, str(state or "")):
        raise GoogleLoginError("A validação de segurança do login expirou.")
    if not code or not expected_nonce or not verifier:
        raise GoogleLoginError("A resposta do Google está incompleta.")
    config = _configuration(realm)

    response = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uri": config["redirect_uri"],
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
        timeout=20,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise GoogleLoginError("O Google não devolveu uma resposta válida.") from exc
    if not response.ok or not payload.get("id_token"):
        raise GoogleLoginError("Não foi possível confirmar o login com Google.")

    try:
        identity = id_token.verify_oauth2_token(
            payload["id_token"],
            GoogleRequest(),
            config["client_id"],
        )
    except Exception as exc:
        raise GoogleLoginError("A identidade devolvida pelo Google não é válida.") from exc
    if not secrets.compare_digest(str(identity.get("nonce") or ""), expected_nonce):
        raise GoogleLoginError("A confirmação do Google não pertence a este login.")
    if identity.get("email_verified") is not True:
        raise GoogleLoginError("O email desta conta Google não está verificado.")
    email = str(identity.get("email") or "").strip().lower()
    allowed_domain = str(config.get("allowed_domain") or "").strip().lower()
    if allowed_domain and not email.endswith(f"@{allowed_domain}"):
        raise GoogleLoginError("Use uma conta Google autorizada pela organização.")
    return {"email": email, "name": str(identity.get("name") or ""), "sub": str(identity.get("sub") or ""), "realm": realm}
