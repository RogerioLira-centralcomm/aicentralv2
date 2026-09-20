"""Google Workspace OAuth, Drive discovery and project resource links."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode
from uuid import UUID, uuid4

import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, g
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from psycopg.types.json import Json

from ..db import get_db


AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_CHANGES_URL = "https://www.googleapis.com/drive/v3/changes"
DRIVE_START_PAGE_TOKEN_URL = "https://www.googleapis.com/drive/v3/changes/startPageToken"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
MEET_CONFERENCE_RECORDS_URL = "https://meet.googleapis.com/v2/conferenceRecords"
MEET_TRANSCRIPTS_SUFFIX = "/transcripts"
MEET_RECORDINGS_SUFFIX = "/recordings"
MEET_SMART_NOTES_SUFFIX = "/smartNotes"

# The consent is deliberately broad for the Workspace connector. The UI still
# exposes each capability separately, while one organization connection keeps
# the granted scopes and refresh token together.
SCOPES = (
    "openid",
    "email",
    "profile",
    # Full Drive access is intentional: the connector must be able to read,
    # organize and later write project files without another consent cycle.
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/meetings.space.created",
    "https://www.googleapis.com/auth/meetings.space.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/adwords",
)

# The matrix is intentionally kept beside the OAuth contract. This makes the
# Integrations screen explain the real activation requirements instead of
# presenting a static list of Google product names.
GOOGLE_SERVICE_CATALOG = (
    {
        "key": "drive",
        "name": "Google Drive",
        "icon": "fa-brands fa-google-drive",
        "description": "Arquivos, pastas e links podem ser indexados e associados a projetos.",
        "scopes": ("https://www.googleapis.com/auth/drive",),
        "api_url": "https://console.cloud.google.com/apis/library/drive.googleapis.com",
    },
    {
        "key": "calendar",
        "name": "Google Calendar",
        "icon": "fa-regular fa-calendar",
        "description": "Eventos e agenda entram no contexto de reuniões e entregas.",
        "scopes": (
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events",
        ),
        "api_url": "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com",
    },
    {
        "key": "meet",
        "name": "Google Meet",
        "icon": "fa-solid fa-video",
        "description": "Espaços de reunião e links do Meet ficam disponíveis para o projeto.",
        "scopes": (
            "https://www.googleapis.com/auth/meetings.space.created",
            "https://www.googleapis.com/auth/meetings.space.readonly",
        ),
        "api_url": "https://console.cloud.google.com/apis/library/meet.googleapis.com",
    },
    {
        "key": "analytics",
        "name": "Google Analytics",
        "icon": "fa-solid fa-chart-line",
        "description": "Propriedades e sinais de audiência podem alimentar o planejamento.",
        "scopes": ("https://www.googleapis.com/auth/analytics.readonly",),
        "api_url": "https://console.cloud.google.com/apis/library/analyticsadmin.googleapis.com",
    },
    {
        "key": "search_console",
        "name": "Search Console",
        "icon": "fa-solid fa-magnifying-glass-chart",
        "description": "Sites, consultas e presença orgânica ficam disponíveis para análise.",
        "scopes": ("https://www.googleapis.com/auth/webmasters.readonly",),
        "api_url": "https://console.cloud.google.com/apis/library/searchconsole.googleapis.com",
    },
    {
        "key": "ads",
        "name": "Google Ads",
        "icon": "fa-solid fa-bullhorn",
        "description": "Contas e campanhas podem ser descobertas para mídia e relatórios.",
        "scopes": ("https://www.googleapis.com/auth/adwords",),
        "api_url": "https://console.cloud.google.com/apis/library/googleads.googleapis.com",
        "requires_developer_token": True,
    },
)

_SERVICE_STATUS_LABELS = {
    "enabled": "Habilitado",
    "needs_authorization": "Autorizar conta",
    "needs_reauthorization": "Atualizar permissões",
    "needs_configuration": "Configuração pendente",
    "unavailable": "Indisponível",
    "error": "Requer atenção",
}

_SERVICE_CONFIG_LABELS = {
    "client_id": "Client ID do OAuth",
    "client_secret": "Client secret do OAuth",
    "redirect_uri": "URL de retorno do OAuth",
    "token_encryption_key": "chave de proteção dos tokens",
    "ads_developer_token": "developer token do Google Ads",
}


class GoogleWorkspaceError(RuntimeError):
    pass


def _configuration() -> dict:
    try:
        if not hasattr(g, "_google_workspace_configuration"):
            from . import integration_credentials
            g._google_workspace_configuration = integration_credentials.get_configuration(
                "google_workspace", include_secrets=True
            )
        config = g._google_workspace_configuration
    except Exception:
        config = {}
    if not config.get("configured"):
        raise GoogleWorkspaceError("Google Workspace ainda não foi configurado.")
    return config


def _encryption_key() -> str:
    value = str(current_app.config.get("GOOGLE_TOKEN_ENCRYPTION_KEY") or os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY", "")).strip()
    if not value:
        raise GoogleWorkspaceError("Configure GOOGLE_TOKEN_ENCRYPTION_KEY antes de conectar uma conta.")
    try:
        Fernet(value.encode())
    except (ValueError, TypeError) as exc:
        raise GoogleWorkspaceError("GOOGLE_TOKEN_ENCRYPTION_KEY não é uma chave Fernet válida.") from exc
    return value


def _configuration_state() -> dict:
    """Return safe configuration metadata for the Integrations console."""
    try:
        from . import integration_credentials

        config = integration_credentials.get_configuration(
            "google_workspace", include_secrets=True
        )
    except Exception as exc:
        return {
            "configured": False,
            "source": "unavailable",
            "missing": ["credenciais do Google Workspace"],
            "error": str(exc),
            "redirect_uri": "",
            "encryption_ready": False,
            "ads_ready": False,
        }

    missing = [
        _SERVICE_CONFIG_LABELS[field]
        for field in ("client_id", "client_secret", "redirect_uri")
        if not str(config.get(field) or "").strip()
    ]
    encryption_ready = True
    try:
        _encryption_key()
    except (GoogleWorkspaceError, RuntimeError):
        encryption_ready = False
        missing.append(_SERVICE_CONFIG_LABELS["token_encryption_key"])

    if not config.get("configured") and not missing:
        missing.append("credencial Google Workspace ativa")

    try:
        configured_ads_token = current_app.config.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    except RuntimeError:
        configured_ads_token = ""
    ads_developer_token = str(
        configured_ads_token or os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    ).strip()
    return {
        "configured": bool(config.get("configured")) and not missing,
        "source": config.get("source") or "environment",
        "missing": missing,
        "error": "",
        "redirect_uri": str(config.get("redirect_uri") or ""),
        "encryption_ready": encryption_ready,
        "ads_ready": bool(ads_developer_token),
    }


def service_matrix(organization_id: int) -> dict:
    """Describe every native Google capability without returning credentials.

    ``enabled`` means the server is configured, the organization has an
    active Google connection, and the connection granted the scopes needed by
    that capability. Google Cloud API enablement still belongs to the project
    owner, so every card exposes the exact API Library link for that last step.
    """
    config = _configuration_state()
    connection = None
    table_available = _available()
    if table_available:
        try:
            connection = get_connection(organization_id)
        except Exception:
            table_available = False

    granted = {
        scope.strip()
        for scope in str((connection or {}).get("granted_scopes") or "").split()
        if scope.strip()
    }
    connection_status = str((connection or {}).get("status") or "").lower()
    connection_needs_reauth = connection_status not in {"", "connected"}
    services = []
    for definition in GOOGLE_SERVICE_CATALOG:
        missing_scopes = [scope for scope in definition["scopes"] if scope not in granted]
        if not table_available:
            status = "unavailable"
            detail = "A tabela de conexões ainda não está disponível nesta instalação."
        elif not config["configured"]:
            status = "needs_configuration"
            detail = "Complete a configuração do OAuth e da proteção dos tokens no servidor."
        elif not connection:
            status = "needs_authorization"
            detail = "Autorize a conta Google da organização para liberar este serviço."
        elif connection_needs_reauth or missing_scopes:
            status = "needs_reauthorization"
            detail = "A conta está conectada, mas precisa renovar as permissões deste serviço."
        elif definition.get("requires_developer_token") and not config["ads_ready"]:
            status = "needs_configuration"
            detail = "O OAuth está pronto; falta o developer token do Google Ads."
        else:
            status = "enabled"
            detail = "OAuth, permissões e requisitos locais estão prontos para uso."

        services.append({
            **definition,
            "scopes": list(definition["scopes"]),
            "missing_scopes": missing_scopes,
            "status": status,
            "status_label": _SERVICE_STATUS_LABELS[status],
            "enabled": status == "enabled",
            "detail": detail,
        })

    enabled_count = sum(item["enabled"] for item in services)
    return {
        "services": services,
        "summary": {
            "enabled_count": enabled_count,
            "total_count": len(services),
            "pending_count": len(services) - enabled_count,
        },
        "configuration": config,
        "connection_status": connection_status or "disconnected",
        "cloud_console_url": "https://console.cloud.google.com/apis/credentials",
    }


def encrypt_refresh_token(refresh_token: str) -> str:
    if not refresh_token:
        raise GoogleWorkspaceError("O Google não forneceu acesso offline. Reautorize a conta.")
    return Fernet(_encryption_key().encode()).encrypt(refresh_token.encode()).decode()


def decrypt_refresh_token(encrypted_refresh_token: str) -> str:
    try:
        return Fernet(_encryption_key().encode()).decrypt(encrypted_refresh_token.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise GoogleWorkspaceError("Não foi possível acessar a conexão Google Workspace.") from exc


def authorization_url(state: str, *, login_hint: str = "", code_challenge: str = "") -> str:
    config = _configuration()
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    if login_hint:
        params["login_hint"] = login_hint
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return f"{AUTHORIZATION_URL}?{urlencode(params)}"


def exchange_code(code: str, *, code_verifier: str = "") -> dict:
    if not code:
        raise GoogleWorkspaceError("Código de autorização ausente.")
    config = _configuration()
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "redirect_uri": config["redirect_uri"],
                "grant_type": "authorization_code",
                **({"code_verifier": code_verifier} if code_verifier else {}),
            },
            timeout=20,
        )
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GoogleWorkspaceError("Não foi possível concluir a autorização Google.") from exc
    if not response.ok or not isinstance(payload, dict):
        raise GoogleWorkspaceError("O Google recusou a autorização da conta.")
    raw_id_token = payload.get("id_token")
    if not raw_id_token:
        raise GoogleWorkspaceError("O Google não retornou a identidade da conta.")
    try:
        identity = id_token.verify_oauth2_token(raw_id_token, GoogleAuthRequest(), config["client_id"])
    except Exception as exc:
        raise GoogleWorkspaceError("A identidade devolvida pelo Google não é válida.") from exc
    email = str(identity.get("email") or "").strip().lower()
    if not identity.get("sub") or not email or identity.get("email_verified") is not True:
        raise GoogleWorkspaceError("A conta Google precisa retornar uma identidade verificada.")
    return {
        "google_sub": str(identity["sub"]),
        "google_email": email,
        "google_domain": email.rsplit("@", 1)[-1] if "@" in email else "",
        "refresh_token": str(payload.get("refresh_token") or ""),
        "granted_scopes": str(payload.get("scope") or " ".join(SCOPES)),
    }


def _access_token(connection: dict) -> str:
    config = _configuration()
    try:
        credentials = Credentials(
            token=None,
            refresh_token=decrypt_refresh_token(connection["encrypted_refresh_token"]),
            token_uri=TOKEN_URL,
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            scopes=SCOPES,
        )
        credentials.refresh(GoogleAuthRequest())
    except Exception as exc:
        raise GoogleWorkspaceError("A conexão Google expirou ou foi revogada. Reautorize a conta.") from exc
    return credentials.token


def _available() -> bool:
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.google_workspace_connections') AS table_name")
            return bool(cursor.fetchone()["table_name"])
    except Exception:
        return False


def _connection_columns(cursor) -> set[str]:
    cursor.execute(
        """SELECT column_name FROM information_schema.columns
             WHERE table_schema='public' AND table_name='google_workspace_connections'"""
    )
    return {row["column_name"] for row in cursor.fetchall()}


def get_connection(organization_id: int, *, include_secret: bool = False) -> dict | None:
    if not _available():
        return None
    with get_db().cursor() as cursor:
        columns = _connection_columns(cursor)
        sync_state = "COALESCE(sync_state, '{}'::jsonb) AS sync_state" if "sync_state" in columns else "'{}'::jsonb AS sync_state"
        cursor.execute(
            f"""SELECT id, organization_id, client_id, google_sub, google_email,
                      google_domain, granted_scopes, status, last_sync_at,
                      last_error, created_at, updated_at, {sync_state}
                      {', encrypted_refresh_token' if include_secret else ''}
                 FROM google_workspace_connections
                WHERE organization_id = %s""",
            (int(organization_id),),
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def save_connection(*, organization_id: int, client_id: int, user_id: int, identity: dict, existing: dict | None = None) -> dict:
    refresh_token = identity.get("refresh_token")
    if not refresh_token and existing:
        encrypted = existing["encrypted_refresh_token"]
    else:
        encrypted = encrypt_refresh_token(refresh_token)
    connection_id = existing.get("id") if existing else uuid4()
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO google_workspace_connections
                    (id, organization_id, client_id, google_sub, google_email,
                     google_domain, encrypted_refresh_token, granted_scopes,
                     status, last_error, created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'connected',NULL,%s)
                ON CONFLICT (organization_id) DO UPDATE SET
                    client_id=EXCLUDED.client_id, google_sub=EXCLUDED.google_sub,
                    google_email=EXCLUDED.google_email, google_domain=EXCLUDED.google_domain,
                    encrypted_refresh_token=EXCLUDED.encrypted_refresh_token,
                    granted_scopes=EXCLUDED.granted_scopes, status='connected',
                    last_error=NULL, updated_at=NOW()
                RETURNING id, organization_id, client_id, google_sub, google_email,
                          google_domain, granted_scopes, status, last_sync_at,
                          last_error, created_at, updated_at""",
                (connection_id, int(organization_id), int(client_id), identity["google_sub"],
                 identity["google_email"], identity.get("google_domain"), encrypted,
                 identity.get("granted_scopes") or "", int(user_id)),
            )
            row = cursor.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return dict(row)


def disconnect(organization_id: int) -> bool:
    if not _available():
        return False
    connection = get_connection(organization_id, include_secret=True)
    if not connection:
        return False
    try:
        token = decrypt_refresh_token(connection["encrypted_refresh_token"])
        requests.post("https://oauth2.googleapis.com/revoke", data={"token": token}, timeout=15)
    except Exception:
        # Deleting the local connection is still the safe local outcome when
        # Google's revocation endpoint is unavailable.
        pass
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM google_workspace_connections WHERE organization_id=%s RETURNING id",
                (int(organization_id),),
            )
            deleted = bool(cursor.fetchone())
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise


def list_resources(organization_id: int, *, project_ref: str | None = None, limit: int = 100) -> list[dict]:
    if not _available():
        return []
    with get_db().cursor() as cursor:
        if project_ref:
            cursor.execute(
                """SELECT r.id, r.provider, r.external_id, r.name, r.mime_type,
                          r.external_url, r.parent_external_id, r.metadata,
                          r.status, r.source_updated_at, l.project_ref, l.purpose
                     FROM google_workspace_resources r
                     JOIN google_workspace_connections c ON c.id=r.connection_id
                     JOIN google_workspace_resource_links l ON l.resource_id=r.id
                    WHERE c.organization_id=%s AND l.project_ref=%s
                 ORDER BY r.source_updated_at DESC NULLS LAST, r.name LIMIT %s""",
                (int(organization_id), project_ref, min(int(limit), 500)),
            )
        else:
            cursor.execute(
                """SELECT r.id, r.provider, r.external_id, r.name, r.mime_type,
                          r.external_url, r.parent_external_id, r.metadata,
                          r.status, r.source_updated_at, NULL AS project_ref, NULL AS purpose
                     FROM google_workspace_resources r
                     JOIN google_workspace_connections c ON c.id=r.connection_id
                    WHERE c.organization_id=%s
                 ORDER BY r.source_updated_at DESC NULLS LAST, r.name LIMIT %s""",
                (int(organization_id), min(int(limit), 500)),
            )
        return [dict(row) for row in cursor.fetchall()]


def _sync_drive_full(organization_id: int, *, limit: int = 200, page_token: str | None = None) -> dict:
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de sincronizar o Drive.")
    token = _access_token({**connection, "encrypted_refresh_token": _encrypted_token(organization_id)})
    params = {
        "pageSize": min(max(int(limit), 1), 1000),
        "q": "trashed = false",
        "orderBy": "modifiedTime desc",
        "spaces": "drive",
        "includeItemsFromAllDrives": "true",
        "supportsAllDrives": "true",
        "fields": "files(id,name,mimeType,webViewLink,parents,createdTime,modifiedTime,driveId,description),nextPageToken",
    }
    files = []
    next_page_token = str(page_token or "") or None
    # A first snapshot can span many pages. Keep the snapshot bounded while
    # retaining a token so the next run can continue without losing files.
    for _ in range(100):
        if next_page_token:
            params["pageToken"] = next_page_token
        response = requests.get(
            DRIVE_FILES_URL,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30,
        )
        if not response.ok:
            raise GoogleWorkspaceError("Não foi possível consultar os arquivos do Google Drive.")
        payload = response.json() or {}
        files.extend(payload.get("files") or [])
        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            for item in files:
                cursor.execute(
                    """INSERT INTO google_workspace_resources
                        (id, connection_id, provider, external_id, name, mime_type,
                         external_url, parent_external_id, metadata, source_created_at,
                         source_updated_at, last_synced_at)
                    VALUES (%s,%s,'google_drive',%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    ON CONFLICT (connection_id, provider, external_id) DO UPDATE SET
                        name=EXCLUDED.name, mime_type=EXCLUDED.mime_type,
                        external_url=EXCLUDED.external_url, parent_external_id=EXCLUDED.parent_external_id,
                        metadata=EXCLUDED.metadata, source_created_at=EXCLUDED.source_created_at,
                        source_updated_at=EXCLUDED.source_updated_at, last_synced_at=NOW(),
                        updated_at=NOW(), status='active'""",
                    (uuid4(), connection["id"], str(item.get("id")), str(item.get("name") or "Arquivo Google")[:500],
                     item.get("mimeType"), item.get("webViewLink"), (item.get("parents") or [None])[0],
                     Json({"drive_id": item.get("driveId"), "description": item.get("description")}),
                     _timestamp(item.get("createdTime")), _timestamp(item.get("modifiedTime"))),
                )
            cursor.execute(
                "UPDATE google_workspace_connections SET last_sync_at=NOW(), last_error=NULL, updated_at=NOW() WHERE id=%s",
                (connection["id"],),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"provider": "google_drive", "synced": len(files), "next_page_token": next_page_token}


def _upsert_drive_changes(connection_id, files: list[dict], removed_ids: list[str]) -> None:
    """Apply a Drive changes page to the provider resource table."""
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            for item in files:
                cursor.execute(
                    """INSERT INTO google_workspace_resources
                        (id, connection_id, provider, external_id, name, mime_type,
                         external_url, parent_external_id, metadata, source_created_at,
                         source_updated_at, last_synced_at)
                    VALUES (%s,%s,'google_drive',%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    ON CONFLICT (connection_id, provider, external_id) DO UPDATE SET
                        name=EXCLUDED.name, mime_type=EXCLUDED.mime_type,
                        external_url=EXCLUDED.external_url, parent_external_id=EXCLUDED.parent_external_id,
                        metadata=EXCLUDED.metadata, source_created_at=EXCLUDED.source_created_at,
                        source_updated_at=EXCLUDED.source_updated_at, last_synced_at=NOW(),
                        updated_at=NOW(), status='active'""",
                    (uuid4(), connection_id, str(item.get("id")), str(item.get("name") or "Arquivo Google")[:500],
                     item.get("mimeType"), item.get("webViewLink"), (item.get("parents") or [None])[0],
                     Json({"drive_id": item.get("driveId"), "description": item.get("description")} ),
                     _timestamp(item.get("createdTime")), _timestamp(item.get("modifiedTime"))),
                )
            if removed_ids:
                cursor.execute(
                    """UPDATE google_workspace_resources SET status='archived', updated_at=NOW()
                          WHERE connection_id=%s AND provider='google_drive' AND external_id = ANY(%s)""",
                    (connection_id, removed_ids),
                )
            cursor.execute(
                "UPDATE google_workspace_connections SET last_sync_at=NOW(), last_error=NULL, updated_at=NOW() WHERE id=%s",
                (connection_id,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _persist_drive_sync_state(connection_id, state: dict) -> None:
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if "sync_state" not in _connection_columns(cursor):
                return
            cursor.execute(
                "UPDATE google_workspace_connections SET sync_state=%s, updated_at=NOW() WHERE id=%s",
                (Json(state), connection_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def sync_drive(organization_id: int, *, limit: int = 200) -> dict:
    """Synchronize Drive incrementally after the first bounded snapshot."""
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de sincronizar o Drive.")
    token = _access_token({**connection, "encrypted_refresh_token": _encrypted_token(organization_id)})
    headers = {"Authorization": f"Bearer {token}"}
    state = dict(connection.get("sync_state") or {})
    change_token = str(state.get("drive_change_token") or "")
    page_size = min(max(int(limit), 1), 1000)
    if not change_token:
        result = _sync_drive_full(
            organization_id,
            limit=page_size,
            page_token=state.get("drive_full_page_token"),
        )
        if result.get("next_page_token"):
            state["drive_full_page_token"] = str(result["next_page_token"])
            _persist_drive_sync_state(connection["id"], state)
            return {**result, "mode": "full_page"}
        state.pop("drive_full_page_token", None)
        if not result.get("next_page_token"):
            start = requests.get(
                DRIVE_START_PAGE_TOKEN_URL,
                headers=headers,
                params={"supportsAllDrives": "true"},
                timeout=30,
            )
            if start.ok and (start.json() or {}).get("startPageToken"):
                state["drive_change_token"] = str(start.json()["startPageToken"])
                _persist_drive_sync_state(connection["id"], state)
        return {**result, "mode": "full"}

    response = requests.get(
        DRIVE_CHANGES_URL,
        headers=headers,
        params={
            "pageToken": change_token, "pageSize": page_size,
            "includeRemoved": "true", "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "fields": "changes(fileId,removed,file(id,name,mimeType,webViewLink,parents,createdTime,modifiedTime,driveId,description)),nextPageToken,newStartPageToken",
        },
        timeout=30,
    )
    if not response.ok:
        if response.status_code in {400, 410}:
            state.pop("drive_change_token", None)
            _persist_drive_sync_state(connection["id"], state)
            return {**_sync_drive_full(organization_id, limit=page_size), "mode": "full_reset"}
        raise GoogleWorkspaceError("Não foi possível consultar as alterações do Google Drive.")
    payload = response.json() or {}
    changes = payload.get("changes") or []
    files = [item["file"] for item in changes if item.get("file") and not item.get("removed")]
    removed = [str(item.get("fileId")) for item in changes if item.get("removed") and item.get("fileId")]
    _upsert_drive_changes(connection["id"], files, removed)
    state["drive_change_token"] = str(payload.get("nextPageToken") or payload.get("newStartPageToken") or change_token)
    _persist_drive_sync_state(connection["id"], state)
    return {
        "provider": "google_drive", "mode": "incremental", "synced": len(files),
        "archived": len(removed), "next_page_token": payload.get("nextPageToken"),
    }


def list_calendar_events(organization_id: int, *, limit: int = 50, time_min: str | None = None) -> list[dict]:
    """Read upcoming primary-calendar events through the shared connection."""
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de consultar o Calendar.")
    token = _access_token({**connection, "encrypted_refresh_token": _encrypted_token(organization_id)})
    response = requests.get(
        CALENDAR_EVENTS_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={
            "maxResults": min(max(int(limit), 1), 100),
            "singleEvents": "true", "orderBy": "startTime",
            "timeMin": time_min or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "fields": "items(id,summary,description,htmlLink,start,end,attendees,conferenceData),nextSyncToken",
        },
        timeout=30,
    )
    if not response.ok:
        raise GoogleWorkspaceError("Não foi possível consultar os eventos do Google Calendar.")
    return (response.json() or {}).get("items") or []


def list_meet_conference_records(organization_id: int, *, limit: int = 50) -> list[dict]:
    """List recent Meet conference records without fetching transcript content."""
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de consultar o Meet.")
    token = _access_token({**connection, "encrypted_refresh_token": _encrypted_token(organization_id)})
    response = requests.get(
        MEET_CONFERENCE_RECORDS_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={"pageSize": min(max(int(limit), 1), 100), "orderBy": "startTime desc"},
        timeout=30,
    )
    if not response.ok:
        raise GoogleWorkspaceError("Não foi possível consultar os registros do Google Meet.")
    return (response.json() or {}).get("conferenceRecords") or []


def _list_meet_collection(
    organization_id: int,
    parent: str,
    suffix: str,
    response_key: str,
    *,
    limit: int = 50,
) -> list[dict]:
    """Read one Meet artifact collection using the shared org connection."""
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de consultar o Meet.")
    parent = str(parent or "").strip().strip("/")
    if not parent.startswith("conferenceRecords/"):
        raise GoogleWorkspaceError("Registro do Meet inválido.")
    token = _access_token({**connection, "encrypted_refresh_token": _encrypted_token(organization_id)})
    response = requests.get(
        f"https://meet.googleapis.com/v2/{parent}{suffix}",
        headers={"Authorization": f"Bearer {token}"},
        params={"pageSize": min(max(int(limit), 1), 100)},
        timeout=30,
    )
    if not response.ok:
        raise GoogleWorkspaceError("Não foi possível consultar os artefatos do Google Meet.")
    return (response.json() or {}).get(response_key) or []


def list_meet_transcripts(organization_id: int, conference_record: str, *, limit: int = 50) -> list[dict]:
    return _list_meet_collection(
        organization_id, conference_record, MEET_TRANSCRIPTS_SUFFIX, "transcripts", limit=limit,
    )


def list_meet_transcript_entries(organization_id: int, transcript: str, *, limit: int = 100) -> list[dict]:
    transcript = str(transcript or "").strip().strip("/")
    if not transcript.startswith("conferenceRecords/") or "/transcripts/" not in transcript:
        raise GoogleWorkspaceError("Transcrição do Meet inválida.")
    return _list_meet_collection(
        organization_id, transcript, "/entries", "transcriptEntries", limit=limit,
    )


def list_meet_recordings(organization_id: int, conference_record: str, *, limit: int = 50) -> list[dict]:
    return _list_meet_collection(
        organization_id, conference_record, MEET_RECORDINGS_SUFFIX, "recordings", limit=limit,
    )


def list_meet_smart_notes(organization_id: int, conference_record: str, *, limit: int = 50) -> list[dict]:
    return _list_meet_collection(
        organization_id, conference_record, MEET_SMART_NOTES_SUFFIX, "smartNotes", limit=limit,
    )


def discover_meet_artifacts(organization_id: int, *, limit: int = 25) -> dict:
    """Discover Meet transcripts, recordings and smart notes without content fetch."""
    records = list_meet_conference_records(organization_id, limit=limit)
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de consultar o Meet.")
    artifacts: list[dict] = []
    for record in records[: min(max(int(limit), 1), 50)]:
        conference = str(record.get("name") or "").strip()
        if not conference:
            continue
        collections = (
            ("transcript", list_meet_transcripts(organization_id, conference, limit=50)),
            ("recording", list_meet_recordings(organization_id, conference, limit=50)),
            ("smart_note", list_meet_smart_notes(organization_id, conference, limit=50)),
        )
        for artifact_type, values in collections:
            for item in values:
                name = str(item.get("name") or item.get("id") or "").strip()
                if not name:
                    continue
                artifact = _upsert_meet_artifact(
                    connection["id"], conference, artifact_type, item, name,
                )
                artifacts.append(artifact)
    return {"provider": "google_meet", "records": len(records), "artifacts": artifacts}


def list_meet_artifacts(organization_id: int, *, limit: int = 50) -> list[dict]:
    """Return discovered Meet artifacts and their canonical resource IDs."""
    if not _available():
        return []
    with get_db().cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.google_workspace_meeting_artifacts') AS table_name")
        if not (cursor.fetchone() or {}).get("table_name"):
            return []
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT a.id, a.conference_record, a.artifact_type, a.external_name,
                      a.title, a.locator, a.metadata, a.content, a.content_hash, a.status,
                      a.source_created_at, a.source_updated_at, r.id AS resource_id
                 FROM google_workspace_meeting_artifacts a
                 JOIN google_workspace_connections c ON c.id=a.connection_id
            LEFT JOIN google_workspace_resources r
                   ON r.connection_id=a.connection_id AND r.provider='google_meet'
                  AND r.external_id=a.external_name
                WHERE c.organization_id=%s AND a.status <> 'archived'
             ORDER BY a.source_created_at DESC NULLS LAST, a.updated_at DESC
                LIMIT %s""",
            (int(organization_id), min(max(int(limit), 1), 200)),
        )
        return [dict(row) for row in cursor.fetchall()]


def _upsert_meet_artifact(connection_id, conference_record: str, artifact_type: str, item: dict, external_name: str) -> dict:
    title = item.get("title") or item.get("displayName") or external_name.rsplit("/", 1)[-1]
    locator = item.get("webViewLink") or item.get("downloadUri") or item.get("uri")
    created = _timestamp(item.get("createTime") or item.get("startTime"))
    updated = _timestamp(item.get("updateTime") or item.get("endTime"))
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            """INSERT INTO google_workspace_meeting_artifacts
                (id, connection_id, conference_record, artifact_type, external_name,
                 title, locator, metadata, source_created_at, source_updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (connection_id, artifact_type, external_name) DO UPDATE SET
                title=EXCLUDED.title, locator=EXCLUDED.locator, metadata=EXCLUDED.metadata,
                source_created_at=EXCLUDED.source_created_at, source_updated_at=EXCLUDED.source_updated_at,
                updated_at=NOW()
            RETURNING id, connection_id, conference_record, artifact_type, external_name,
                      title, locator, metadata, content, content_hash, status,
                      source_created_at, source_updated_at""",
            (uuid4(), connection_id, conference_record, artifact_type, external_name,
             str(title)[:500], locator, Json(item), created, updated),
        )
        row = dict(cursor.fetchone())
        resource_id = uuid4()
        mime_type = {
            "transcript": "text/plain",
            "recording": "video/mp4",
            "smart_note": "text/markdown",
        }.get(artifact_type, "application/octet-stream")
        cursor.execute(
            """INSERT INTO google_workspace_resources
                (id, connection_id, provider, external_id, name, mime_type,
                 external_url, metadata, source_created_at, source_updated_at, last_synced_at)
            VALUES (%s,%s,'google_meet',%s,%s,%s,%s,%s,%s,%s,NOW())
            ON CONFLICT (connection_id, provider, external_id) DO UPDATE SET
                name=EXCLUDED.name, mime_type=EXCLUDED.mime_type, external_url=EXCLUDED.external_url,
                metadata=EXCLUDED.metadata, source_created_at=EXCLUDED.source_created_at,
                source_updated_at=EXCLUDED.source_updated_at, last_synced_at=NOW(),
                updated_at=NOW(), status='active'
            RETURNING id""",
            (resource_id, connection_id, external_name, str(title)[:500], mime_type, locator,
             Json({"meeting_artifact_id": str(row["id"]), "conference_record": conference_record, **item}),
             created, updated),
        )
        row["resource_id"] = str(cursor.fetchone()["id"])
    conn.commit()
    return row


def fetch_meet_transcript_content(organization_id: int, artifact_id: str, *, limit: int = 1000) -> dict:
    """Fetch transcript entries after an explicit indexing decision."""
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de consultar o Meet.")
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            """SELECT id, conference_record, artifact_type, external_name, metadata
                 FROM google_workspace_meeting_artifacts
                WHERE id=%s AND connection_id=%s""",
            (UUID(str(artifact_id)), connection["id"]),
        )
        artifact = cursor.fetchone()
    if not artifact or artifact["artifact_type"] != "transcript":
        raise GoogleWorkspaceError("Artefato de transcrição não encontrado.")
    entries = list_meet_transcript_entries(organization_id, artifact["external_name"], limit=limit)
    text_parts = []
    for entry in entries:
        text = entry.get("text") or entry.get("transcriptEntry", {}).get("text") or ""
        if text:
            text_parts.append(str(text).strip())
    content = "\n".join(part for part in text_parts if part)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE google_workspace_meeting_artifacts
                      SET content=%s, content_hash=%s, status='fetched', updated_at=NOW()
                    WHERE id=%s AND connection_id=%s""",
                (content, digest, artifact["id"], connection["id"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"artifact_id": str(artifact["id"]), "entries": len(entries), "characters": len(content), "content_hash": digest}


def sync_calendar_events(organization_id: int, *, limit: int = 100) -> dict:
    """Synchronize Calendar with the API sync token, preserving cancellations."""
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de sincronizar o Calendar.")
    token = _access_token({**connection, "encrypted_refresh_token": _encrypted_token(organization_id)})
    state = dict(connection.get("sync_state") or {})
    sync_token = str(state.get("calendar_sync_token") or "")
    params = {
        "maxResults": min(max(int(limit), 1), 2500),
        "singleEvents": "true",
        "fields": "items(id,status,summary,description,htmlLink,start,end,attendees,conferenceData,created,updated),nextPageToken,nextSyncToken",
    }
    if sync_token:
        params["syncToken"] = sync_token
    else:
        params.update({
            "orderBy": "startTime",
            "timeMin": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        })
    pages = []
    next_page = None
    for _ in range(20):
        if next_page:
            params["pageToken"] = next_page
        response = requests.get(
            CALENDAR_EVENTS_URL,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30,
        )
        if not response.ok:
            if response.status_code == 410 and sync_token:
                state.pop("calendar_sync_token", None)
                _persist_drive_sync_state(connection["id"], state)
                return {**sync_calendar_events(organization_id, limit=limit), "mode": "full_reset"}
            raise GoogleWorkspaceError("Não foi possível sincronizar os eventos do Google Calendar.")
        payload = response.json() or {}
        pages.extend(payload.get("items") or [])
        next_page = payload.get("nextPageToken")
        if not next_page:
            next_sync = payload.get("nextSyncToken")
            if next_sync:
                state["calendar_sync_token"] = str(next_sync)
            break
    _upsert_calendar_events(connection["id"], pages)
    _persist_drive_sync_state(connection["id"], state)
    return {
        "provider": "google_calendar",
        "mode": "incremental" if sync_token else "full",
        "synced": sum(1 for item in pages if item.get("status") != "cancelled"),
        "archived": sum(1 for item in pages if item.get("status") == "cancelled"),
    }


def _upsert_calendar_events(connection_id, events: list[dict]) -> None:
    if not events:
        return
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            for item in events:
                event_id = str(item.get("id") or "").strip()
                if not event_id:
                    continue
                status = "archived" if item.get("status") == "cancelled" else "active"
                cursor.execute(
                    """INSERT INTO google_workspace_resources
                        (id, connection_id, provider, external_id, name, mime_type,
                         external_url, metadata, source_created_at, source_updated_at,
                         status, last_synced_at)
                    VALUES (%s,%s,'google_calendar',%s,%s,'application/x-google-calendar-event',%s,%s,%s,%s,%s,NOW())
                    ON CONFLICT (connection_id, provider, external_id) DO UPDATE SET
                        name=EXCLUDED.name, external_url=EXCLUDED.external_url,
                        metadata=EXCLUDED.metadata, source_created_at=EXCLUDED.source_created_at,
                        source_updated_at=EXCLUDED.source_updated_at, status=EXCLUDED.status,
                        last_synced_at=NOW(), updated_at=NOW()""",
                    (uuid4(), connection_id, event_id, str(item.get("summary") or "Evento Google Calendar")[:500],
                     item.get("htmlLink"), Json(item), _timestamp(item.get("created")),
                     _timestamp(item.get("updated")), status),
                )
            cursor.execute(
                "UPDATE google_workspace_connections SET last_sync_at=NOW(), last_error=NULL, updated_at=NOW() WHERE id=%s",
                (connection_id,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def sync_ads(organization_id: int, *, limit: int = 100) -> dict:
    """Discover Ads customers available to the authorized Google account."""
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de sincronizar o Ads.")
    token = _access_token({**connection, "encrypted_refresh_token": _encrypted_token(organization_id)})
    version = str(current_app.config.get("GOOGLE_ADS_API_VERSION") or "v25")
    headers = {"Authorization": f"Bearer {token}"}
    developer_token = str(current_app.config.get("GOOGLE_ADS_DEVELOPER_TOKEN") or os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")).strip()
    login_customer_id = str(current_app.config.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")).replace("-", "").strip()
    if developer_token:
        headers["developer-token"] = developer_token
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id
    base_url = f"https://googleads.googleapis.com/{version}"
    response = requests.get(f"{base_url}/customers:listAccessibleCustomers", headers=headers, timeout=30)
    if not response.ok:
        raise GoogleWorkspaceError("Não foi possível descobrir as contas acessíveis no Google Ads.")
    names = (response.json() or {}).get("resourceNames") or []
    customers = []
    for resource_name in names[: max(1, int(limit))]:
        customer_id = str(resource_name).rsplit("/", 1)[-1].replace("-", "")
        detail = requests.post(
            f"{base_url}/customers/{customer_id}/googleAds:searchStream",
            headers={**headers, "Content-Type": "application/json"},
            json={"query": "SELECT customer.id, customer.descriptive_name, customer.manager, customer.status FROM customer LIMIT 1"},
            timeout=30,
        )
        if not detail.ok:
            customers.append({"id": customer_id, "name": f"Conta Google Ads {customer_id}"})
            continue
        batches = detail.json() or []
        row = ((batches[0] if batches else {}).get("results") or [{}])[0]
        customer = row.get("customer") or {}
        customers.append({"id": customer_id, "name": customer.get("descriptiveName") or f"Conta Google Ads {customer_id}", "manager": bool(customer.get("manager")), "status": customer.get("status")})
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            for customer in customers:
                cursor.execute(
                    """INSERT INTO google_workspace_resources
                        (id, connection_id, provider, external_id, name, mime_type,
                         external_url, metadata, last_synced_at)
                    VALUES (%s,%s,'google_ads',%s,%s,'application/x-google-ads-account',%s,%s,NOW())
                    ON CONFLICT (connection_id, provider, external_id) DO UPDATE SET
                        name=EXCLUDED.name, external_url=EXCLUDED.external_url,
                        metadata=EXCLUDED.metadata, last_synced_at=NOW(), updated_at=NOW(), status='active'""",
                    (uuid4(), connection["id"], customer["id"], customer["name"],
                     f"https://ads.google.com/aw/overview?ocid={customer['id']}", Json(customer)),
                )
            cursor.execute("UPDATE google_workspace_connections SET last_sync_at=NOW(), last_error=NULL, updated_at=NOW() WHERE id=%s", (connection["id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"provider": "google_ads", "synced": len(customers)}


def _encrypted_token(organization_id: int) -> str:
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT encrypted_refresh_token FROM google_workspace_connections WHERE organization_id=%s",
            (int(organization_id),),
        )
        row = cursor.fetchone()
    if not row:
        raise GoogleWorkspaceError("Conexão Google não encontrada.")
    return row["encrypted_refresh_token"]


def link_resource(*, organization_id: int, client_id: int, resource_id: str, project_ref: str, user_id: int, purpose: str = "project_knowledge") -> dict:
    if not str(project_ref or "").startswith("ci:"):
        raise GoogleWorkspaceError("Selecione um projeto do Workspace.")
    try:
        resource_uuid = UUID(str(resource_id))
    except (TypeError, ValueError) as exc:
        raise GoogleWorkspaceError("Recurso Google inválido.") from exc
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM cadu_ci_projetos WHERE id=%s AND id_cliente=%s", (project_ref[3:], int(client_id)))
            if not cursor.fetchone():
                raise GoogleWorkspaceError("Projeto indisponível para esta conta.")
            cursor.execute(
                """SELECT r.id, r.provider, r.external_id, r.name, r.mime_type,
                          r.external_url, r.metadata, r.source_created_at, r.source_updated_at
                     FROM google_workspace_resources r
                    JOIN google_workspace_connections c ON c.id=r.connection_id
                   WHERE r.id=%s AND c.organization_id=%s""",
                (resource_uuid, int(organization_id)),
            )
            resource = cursor.fetchone()
            if not resource:
                raise GoogleWorkspaceError("Recurso não pertence a esta organização.")
            cursor.execute(
                """INSERT INTO google_workspace_resource_links
                    (id, resource_id, client_id, project_ref, linked_by, purpose)
                   VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (resource_id, project_ref) DO UPDATE SET
                    linked_by=EXCLUDED.linked_by, purpose=EXCLUDED.purpose""",
                (uuid4(), resource_uuid, int(client_id), project_ref, int(user_id), purpose),
            )
            cursor.execute("SELECT to_regclass('public.cadu_project_resources') AS table_name")
            if cursor.fetchone()["table_name"]:
                from ..cadu_workspace.project_resource_service import resource_id_for_source
                registry_id = resource_id_for_source(
                    int(client_id), project_ref, str(resource["provider"]), str(resource["external_id"])
                )
                resource_type = "link" if str(resource["mime_type"] or "").startswith("text/uri") else "file"
                cursor.execute(
                    """INSERT INTO cadu_project_resources
                        (id, organization_id, client_id, project_ref, source_system,
                         source_id, resource_type, title, mime_type, purpose,
                         category, status, version, locator, metadata, created_by,
                         source_created_at, source_updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',1,%s,%s,%s,%s,%s)
                    ON CONFLICT (client_id, project_ref, source_system, source_id) DO UPDATE SET
                        title=EXCLUDED.title, mime_type=EXCLUDED.mime_type,
                        locator=EXCLUDED.locator, metadata=EXCLUDED.metadata,
                        source_updated_at=EXCLUDED.source_updated_at, last_seen_at=NOW(),
                        status='active'""",
                    (registry_id, int(organization_id), int(client_id), project_ref,
                     resource["provider"], resource["external_id"], resource_type,
                     resource["name"], resource["mime_type"], purpose,
                     "google_meet" if resource["provider"] == "google_meet" else "google_drive", resource["external_url"],
                     Json({"google_resource_id": str(resource["id"]), **(resource["metadata"] or {})}),
                     int(user_id), resource["source_created_at"], resource["source_updated_at"]),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"resource_id": str(resource_uuid), "project_ref": project_ref, "purpose": purpose}


def _timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
