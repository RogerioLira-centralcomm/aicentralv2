"""OAuth por usuário e sincronização CRM → Google Calendar/Meet."""

import os
import secrets
import uuid
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, g
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_URL = "https://www.googleapis.com/calendar/v3"
SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.events",
)


class GoogleCalendarError(RuntimeError):
    pass


def _config(name):
    integration_fields = {
        "GOOGLE_OAUTH_CLIENT_ID": "client_id",
        "GOOGLE_OAUTH_CLIENT_SECRET": "client_secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "redirect_uri",
    }
    if name in integration_fields:
        try:
            if not hasattr(g, "_google_integration_configuration"):
                from . import integration_credentials
                g._google_integration_configuration = (
                    integration_credentials.get_configuration(
                        "google_calendar", include_secrets=True
                    )
                )
            integration = g._google_integration_configuration
            if integration.get("configured"):
                return integration.get(integration_fields[name]) or ""
        except (RuntimeError, ImportError):
            pass
    return current_app.config.get(name) or os.getenv(name, "")


def configured():
    return bool(
        _config("GOOGLE_OAUTH_CLIENT_ID")
        and _config("GOOGLE_OAUTH_CLIENT_SECRET")
        and _config("GOOGLE_OAUTH_REDIRECT_URI")
        and _config("GOOGLE_TOKEN_ENCRYPTION_KEY")
    )


def new_oauth_state():
    return secrets.token_urlsafe(32)


def authorization_url(state):
    if not configured():
        raise GoogleCalendarError("Integração Google ainda não configurada.")
    return AUTH_URL + "?" + urlencode({
        "client_id": _config("GOOGLE_OAUTH_CLIENT_ID"),
        "redirect_uri": _config("GOOGLE_OAUTH_REDIRECT_URI"),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    })


def exchange_authorization_code(code):
    if not code:
        raise GoogleCalendarError("Código de autorização ausente.")
    response = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": _config("GOOGLE_OAUTH_CLIENT_ID"),
            "client_secret": _config("GOOGLE_OAUTH_CLIENT_SECRET"),
            "redirect_uri": _config("GOOGLE_OAUTH_REDIRECT_URI"),
            "grant_type": "authorization_code",
        },
        timeout=_timeout(),
    )
    _raise_google_error(response, "Não foi possível concluir a conexão Google")
    tokens = response.json()
    raw_id_token = tokens.get("id_token")
    if not raw_id_token:
        raise GoogleCalendarError("O Google não retornou a identidade da conta.")
    identity = id_token.verify_oauth2_token(
        raw_id_token,
        GoogleAuthRequest(),
        _config("GOOGLE_OAUTH_CLIENT_ID"),
    )
    if not identity.get("email_verified"):
        raise GoogleCalendarError("A conta Google precisa ter e-mail verificado.")
    return {
        "google_sub": identity["sub"],
        "google_email": identity["email"],
        "refresh_token": tokens.get("refresh_token"),
        "granted_scopes": tokens.get("scope") or " ".join(SCOPES),
    }


def encrypt_refresh_token(refresh_token):
    if not refresh_token:
        raise GoogleCalendarError("O Google não forneceu acesso offline. Reconecte a conta.")
    try:
        return Fernet(_config("GOOGLE_TOKEN_ENCRYPTION_KEY").encode()).encrypt(
            refresh_token.encode()
        ).decode()
    except (ValueError, TypeError) as exc:
        raise GoogleCalendarError("Chave de criptografia Google inválida.") from exc


def decrypt_refresh_token(encrypted_token):
    try:
        return Fernet(_config("GOOGLE_TOKEN_ENCRYPTION_KEY").encode()).decrypt(
            encrypted_token.encode()
        ).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise GoogleCalendarError("Não foi possível acessar a conexão Google.") from exc


def revoke_refresh_token(encrypted_token):
    token = decrypt_refresh_token(encrypted_token)
    response = requests.post(
        "https://oauth2.googleapis.com/revoke",
        data={"token": token},
        timeout=_timeout(),
    )
    if response.status_code not in (200, 400):
        _raise_google_error(response, "Não foi possível revogar a conta Google")


def _access_token(encrypted_refresh_token):
    credentials = Credentials(
        token=None,
        refresh_token=decrypt_refresh_token(encrypted_refresh_token),
        token_uri=TOKEN_URL,
        client_id=_config("GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=_config("GOOGLE_OAUTH_CLIENT_SECRET"),
        scopes=SCOPES,
    )
    try:
        credentials.refresh(GoogleAuthRequest())
    except Exception as exc:
        raise GoogleCalendarError(
            "A conexão Google expirou ou foi revogada. Reconecte pelo perfil."
        ) from exc
    return credentials.token


def build_event_payload(activity, meeting, create_meet=False):
    payload = {
        "summary": activity.get("titulo") or "Reunião CentralComm",
        "description": activity.get("descricao") or "",
        "start": {
            "dateTime": _iso_datetime(meeting["starts_at"]),
            "timeZone": meeting.get("timezone") or "America/Sao_Paulo",
        },
        "end": {
            "dateTime": _iso_datetime(meeting["ends_at"]),
            "timeZone": meeting.get("timezone") or "America/Sao_Paulo",
        },
        "attendees": [
            {"email": item["email"]}
            for item in meeting.get("attendees") or []
        ],
        "guestsCanInviteOthers": False,
        "guestsCanModify": False,
    }
    if create_meet:
        payload["conferenceData"] = {
            "createRequest": {
                "requestId": uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"centralx:crm-activity:{meeting['activity_id']}",
                ).hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
    return payload


def sync_event(activity, meeting, encrypted_refresh_token):
    token = _access_token(encrypted_refresh_token)
    calendar_id = meeting.get("google_calendar_id") or "primary"
    event_id = meeting.get("google_event_id")
    payload = build_event_payload(activity, meeting, create_meet=not event_id)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    params = {"conferenceDataVersion": 1, "sendUpdates": "all"}
    if event_id:
        url = f"{CALENDAR_URL}/calendars/{requests.utils.quote(calendar_id, safe='')}/events/{requests.utils.quote(event_id, safe='')}"
        response = requests.patch(
            url, headers=headers, params=params, json=payload, timeout=_timeout()
        )
    else:
        url = f"{CALENDAR_URL}/calendars/{requests.utils.quote(calendar_id, safe='')}/events"
        response = requests.post(
            url, headers=headers, params=params, json=payload, timeout=_timeout()
        )
    _raise_google_error(response, "Não foi possível sincronizar a reunião")
    event = response.json()
    return {
        "event_id": event.get("id"),
        "meet_url": _meet_url(event),
        "html_link": event.get("htmlLink"),
    }


def cancel_event(meeting, encrypted_refresh_token):
    if not meeting.get("google_event_id"):
        return
    token = _access_token(encrypted_refresh_token)
    calendar_id = requests.utils.quote(
        meeting.get("google_calendar_id") or "primary", safe=""
    )
    event_id = requests.utils.quote(meeting["google_event_id"], safe="")
    response = requests.delete(
        f"{CALENDAR_URL}/calendars/{calendar_id}/events/{event_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"sendUpdates": "all"},
        timeout=_timeout(),
    )
    if response.status_code not in (204, 404, 410):
        _raise_google_error(response, "Não foi possível cancelar a reunião")


def _meet_url(event):
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    for entry in ((event.get("conferenceData") or {}).get("entryPoints") or []):
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return entry["uri"]
    return None


def _iso_datetime(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _timeout():
    return int(_config("GOOGLE_CALENDAR_TIMEOUT") or 20)


def _raise_google_error(response, fallback):
    if response.ok:
        return
    detail = ""
    try:
        detail = ((response.json().get("error") or {}).get("message") or "").strip()
    except (ValueError, AttributeError):
        detail = ""
    raise GoogleCalendarError(detail or fallback)
