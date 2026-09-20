"""Google Workspace OAuth, Drive discovery and project resource links."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime
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


def get_connection(organization_id: int, *, include_secret: bool = False) -> dict | None:
    if not _available():
        return None
    with get_db().cursor() as cursor:
        cursor.execute(
            f"""SELECT id, organization_id, client_id, google_sub, google_email,
                      google_domain, granted_scopes, status, last_sync_at,
                      last_error, created_at, updated_at
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


def sync_drive(organization_id: int, *, limit: int = 200) -> dict:
    connection = get_connection(organization_id)
    if not connection:
        raise GoogleWorkspaceError("Conecte uma conta Google antes de sincronizar o Drive.")
    token = _access_token({**connection, "encrypted_refresh_token": _encrypted_token(organization_id)})
    response = requests.get(
        DRIVE_FILES_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={
            "pageSize": min(max(int(limit), 1), 1000),
            "q": "trashed = false",
            "orderBy": "modifiedTime desc",
            "spaces": "drive",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "fields": "files(id,name,mimeType,webViewLink,parents,createdTime,modifiedTime,driveId,description),nextPageToken",
        },
        timeout=30,
    )
    if not response.ok:
        raise GoogleWorkspaceError("Não foi possível consultar os arquivos do Google Drive.")
    files = (response.json() or {}).get("files") or []
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
    return {"provider": "google_drive", "synced": len(files), "next_page_token": (response.json() or {}).get("nextPageToken")}


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
                     "google_drive", resource["external_url"],
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
