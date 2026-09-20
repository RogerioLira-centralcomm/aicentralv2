"""Provider contract for the future Slack connector.

This module deliberately contains the security-critical protocol pieces first:
OAuth URL construction and signed Events API verification. Token persistence and
project indexing will be added behind the same connector registry contract.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


SLACK_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_API_URL = "https://slack.com/api"
DEFAULT_SCOPES = ("channels:history", "channels:read", "files:read", "groups:history", "groups:read")


class SlackConnectorError(RuntimeError):
    pass


def authorization_url(*, client_id: str, redirect_uri: str, state: str, scopes=DEFAULT_SCOPES) -> str:
    if not client_id or not redirect_uri or not state:
        raise SlackConnectorError("Client ID, redirect URI e state são obrigatórios.")
    return SLACK_AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": ",".join(str(item) for item in scopes),
    })


def exchange_code(*, code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    if not code or not client_id or not client_secret or not redirect_uri:
        raise SlackConnectorError("Código e credenciais Slack são obrigatórios.")
    response = requests.post(
        SLACK_TOKEN_URL,
        data={"code": code, "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri},
        timeout=20,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise SlackConnectorError("Resposta inválida do Slack.") from exc
    if not response.ok or not payload.get("ok"):
        raise SlackConnectorError(str(payload.get("error") or "O Slack recusou a autorização."))
    return payload


def _encryption_key() -> bytes:
    raw = str(current_app.config.get("CADU_CONNECTOR_ENCRYPTION_KEY") or os.getenv("CADU_CONNECTOR_ENCRYPTION_KEY") or current_app.config.get("GOOGLE_TOKEN_ENCRYPTION_KEY") or os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY") or "").strip()
    if not raw:
        raise SlackConnectorError("Configure a chave de proteção dos conectores.")
    try:
        Fernet(raw.encode())
    except (ValueError, TypeError) as exc:
        raise SlackConnectorError("A chave de proteção dos conectores é inválida.") from exc
    return raw.encode()


def encrypt_secret(value: str) -> str:
    if not value:
        raise SlackConnectorError("Segredo Slack ausente.")
    return Fernet(_encryption_key()).encrypt(str(value).encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return Fernet(_encryption_key()).decrypt(str(value).encode()).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise SlackConnectorError("Não foi possível acessar o segredo Slack.") from exc


def verify_signature(*, signing_secret: str, timestamp: str, body: bytes, signature: str, now: float | None = None, tolerance: int = 300) -> bool:
    """Validate Slack's v0 HMAC and reject replayed requests."""
    if not signing_secret or not timestamp or not signature:
        return False
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        return False
    current = time.time() if now is None else float(now)
    if abs(current - sent_at) > int(tolerance):
        return False
    base = f"v0:{timestamp}:".encode("utf-8") + (body or b"")
    expected = "v0=" + hmac.new(signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(signature))


def normalize_event(payload: dict) -> dict:
    """Map Slack Events API payloads to a provider-neutral Cadu envelope."""
    event = payload.get("event") if isinstance(payload, dict) else {}
    event = event if isinstance(event, dict) else {}
    return {
        "event_id": str(payload.get("event_id") or payload.get("event_ts") or ""),
        "type": str(event.get("type") or payload.get("type") or "unknown"),
        "team_id": str(payload.get("team_id") or ""),
        "channel_id": str(event.get("channel") or ""),
        "user_id": str(event.get("user") or ""),
        "thread_id": str(event.get("thread_ts") or event.get("ts") or ""),
        "text": str(event.get("text") or ""),
        "file_ids": [str(item.get("id")) for item in (event.get("files") or []) if item.get("id")],
        "raw": payload,
    }
