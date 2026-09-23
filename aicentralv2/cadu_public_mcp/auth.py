"""API-key authentication and tenant context for the public Cadu MCP."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from flask import request
from psycopg.types.json import Json

from ..cadu_family import repository
from ..cadu_workspace.agent_v2.contracts import ActiveObject, RequestContext, SURFACES
from ..db import get_db


KEY_PREFIX = "cadu_mcp_"
CLIENT_TYPES = ("gpt", "codex", "cursor", "vscode", "generic")
CLIENT_SCOPES = ("resources:read", "projects:read", "projects:content_write", "projects:write", "brands:write",
                 "artifacts:write", "account:read", "account:write", "credits:read",
                 "google:read", "google:write", "contexts:read", "contexts:write", "operations:read")
DEFAULT_SCOPES = frozenset(("resources:read", "projects:read", "projects:content_write", "account:read", "credits:read", "google:read", "contexts:read", "contexts:write", "operations:read"))


class PublicMcpAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublicMcpPrincipal:
    key_id: str
    client_id: int
    user_id: int
    client_type: str
    label: str
    scopes: tuple[str, ...]
    context: RequestContext
    credential_type: str = "api_key"
    grant_id: str | None = None


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _available() -> bool:
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.cadu_public_mcp_keys') AS table_name")
            return bool((cursor.fetchone() or {}).get("table_name"))
    except Exception:
        return False


def normalize_scopes(scopes=None, *, allow_writes: bool = False) -> tuple[str, ...]:
    use_defaults = scopes is None
    if isinstance(scopes, str):
        scopes = scopes.split()
    source = DEFAULT_SCOPES if use_defaults else scopes
    values = {str(item).strip().lower() for item in (source or ()) if str(item).strip()}
    # Preserve keys issued before purchases became role-based.
    values.discard("credits:purchase")
    unknown = values - set(CLIENT_SCOPES)
    if unknown:
        raise PublicMcpAuthError("Escopo MCP inválido.")
    if not allow_writes:
        values.discard("projects:content_write")
        values.discard("projects:write")
        values.discard("brands:write")
        values.discard("artifacts:write")
        values.discard("account:write")
        values.discard("google:write")
        values.discard("contexts:write")
    return tuple(sorted(values))


def create_key(*, client_id: int, user_id: int, label: str, client_type: str,
               default_project_ref: str | None = None, scopes=None) -> dict:
    if not _available():
        raise PublicMcpAuthError("A camada pública do MCP ainda não foi ativada no banco.")
    client_type = str(client_type or "generic").strip().lower()
    if client_type not in CLIENT_TYPES:
        raise PublicMcpAuthError("Cliente MCP inválido.")
    label = " ".join(str(label or "").split())[:120] or client_type.title()
    scopes = normalize_scopes(scopes, allow_writes=True)
    if default_project_ref:
        items = {item["ref"]: item for item in repository.entities(int(client_id))}
        if default_project_ref not in items or items[default_project_ref]["kind"] != "project":
            raise PublicMcpAuthError("O projeto padrão não pertence a esta conta.")
    raw_key = f"{KEY_PREFIX}{client_type}_{secrets.token_urlsafe(32)}"
    key_id = uuid4()
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_public_mcp_keys
                    (id, client_id, user_id, client_type, label, default_project_ref,
                     scopes, key_prefix, key_hash, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')
                RETURNING id, client_id, user_id, client_type, label, key_prefix,
                          default_project_ref, scopes, status, created_at, last_used_at, revoked_at""",
                (key_id, int(client_id), int(user_id), client_type, label, default_project_ref,
                 Json(list(scopes)), raw_key[:20], _hash_key(raw_key)),
            )
            row = dict(cursor.fetchone())
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {**row, "id": str(row["id"]), "secret": raw_key, "one_time_secret": True}


def list_keys(*, client_id: int, user_id: int) -> list[dict]:
    if not _available():
        return []
    with get_db().cursor() as cursor:
        cursor.execute(
                """SELECT id, client_id, user_id, client_type, label, default_project_ref, key_prefix,
                      scopes, status, created_at, last_used_at, revoked_at
                 FROM cadu_public_mcp_keys
                WHERE client_id=%s AND user_id=%s
             ORDER BY created_at DESC""",
            (int(client_id), int(user_id)),
        )
        return [dict(row) | {"id": str(row["id"])} for row in cursor.fetchall()]


def revoke_key(*, key_id: str, client_id: int, user_id: int) -> bool:
    try:
        parsed = UUID(str(key_id))
    except (TypeError, ValueError) as exc:
        raise PublicMcpAuthError("Chave MCP inválida.") from exc
    if not _available():
        return False
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_public_mcp_keys
                      SET status='revoked', revoked_at=NOW()
                    WHERE id=%s AND client_id=%s AND user_id=%s AND status='active'
                RETURNING id""",
                (parsed, int(client_id), int(user_id)),
            )
            changed = bool(cursor.fetchone())
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return changed


def _bearer() -> str:
    header = str(request.headers.get("Authorization") or "").strip()
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return str(request.headers.get("X-Cadu-MCP-Key") or "").strip()


def _load_key(raw_key: str) -> dict:
    if not raw_key or not raw_key.startswith(KEY_PREFIX):
        raise PublicMcpAuthError("Chave pública do MCP ausente.")
    if not _available():
        raise PublicMcpAuthError("A autenticação pública do MCP ainda não está disponível.")
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id, client_id, user_id, client_type, label, default_project_ref,
                         scopes, status, expires_at
                 FROM cadu_public_mcp_keys
                WHERE key_hash=%s""",
            (_hash_key(raw_key),),
        )
        row = cursor.fetchone()
    if not row:
        raise PublicMcpAuthError("Chave pública do MCP inválida.")
    row = dict(row)
    if row.get("status") != "active":
        raise PublicMcpAuthError("Esta chave pública do MCP foi revogada.")
    expires_at = row.get("expires_at")
    if expires_at and expires_at <= datetime.now(timezone.utc):
        raise PublicMcpAuthError("Esta chave pública do MCP expirou.")
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE cadu_public_mcp_keys SET last_used_at=NOW() WHERE id=%s", (row["id"],))
        connection.commit()
    except Exception:
        connection.rollback()
    return row


def required_scope(tool_name: str) -> str:
    name = str(tool_name or "")
    if name == "operations.get":
        return "operations:read"
    if name in {"context.update", "context.close"}:
        return "contexts:write"
    if name.startswith("context."):
        return "contexts:read"
    if name in {"media.start_studio_session", "media.generate_image", "media.edit_image", "media.plan_video"}:
        return "projects:content_write"
    if name.startswith("credits."):
        return "credits:read"
    if name in {"account.update_profile", "account.update_agency", "account.invite_team_member"}:
        return "account:write"
    if name.startswith("account."):
        return "account:read"
    if name in {"brands.create", "brands.update_identity", "brands.prepare_logo_upload", "brands.use_asset_as_logo", "brands.start_audit"}:
        return "brands:write"
    if name in {"artifacts.create_draft", "artifacts.update_draft", "artifacts.finalize_to_project"}:
        return "artifacts:write"
    if name.startswith("artifacts."):
        return "projects:read"
    if name in {"projects.create_note", "projects.prepare_source_upload", "projects.create_link_reference"}:
        return "projects:content_write"
    if name in {"workspace.create_project", "workspace.update_project_context", "workspace.set_project_status",
                "workspace.link_current_brand", "workspace.set_project_visibility",
                "workspace.share_project_with_people", "workspace.share_project_with_team",
                "projects.reindex_source"}:
        return "projects:write"
    if name == "google.link_resource_to_project":
        return "google:write"
    if name.startswith("google."):
        return "google:read"
    if name.startswith("resources."):
        return "resources:read"
    if name.startswith("media."):
        return "resources:read"
    if name.startswith("web."):
        return "resources:read"
    return "projects:read"


def ensure_scope(principal: PublicMcpPrincipal, tool_name: str) -> None:
    scope = required_scope(tool_name)
    if not has_scope(principal, scope):
        raise PublicMcpAuthError(f"A chave não possui o escopo necessário: {scope}.")
    if tool_name == "credits.purchase_package" and not can_purchase_credits(principal):
        raise PublicMcpAuthError("Somente administradores da conta podem comprar créditos.")


def has_scope(principal: PublicMcpPrincipal, scope: str) -> bool:
    """Accept pre-context grants during the OAuth migration window."""
    scopes = set(principal.scopes)
    if scope in scopes:
        return True
    if scope == "projects:content_write" and "projects:write" in scopes:
        return True
    if scope in {"contexts:read", "operations:read"} and "projects:read" in scopes:
        return True
    if scope == "contexts:write" and scopes.intersection({"projects:content_write", "projects:write"}):
        return True
    return False


def can_purchase_credits(principal: PublicMcpPrincipal) -> bool:
    actor = repository.actor(int(principal.user_id)) or {}
    return (int(actor.get("organization_id") or 0) == int(principal.client_id)
            and repository.account_role(actor) == "admin")


def _public_context(row: dict, params: dict) -> RequestContext:
    surface = str(params.get("surface") or "conversations")
    if surface not in SURFACES:
        raise PublicMcpAuthError("Superfície Cadu inválida.")
    project_ref = params.get("project_ref") or row.get("default_project_ref")
    brand_ref = params.get("brand_ref")
    if project_ref is not None and not isinstance(project_ref, str):
        raise PublicMcpAuthError("Projeto inválido.")
    if brand_ref is not None and not isinstance(brand_ref, str):
        raise PublicMcpAuthError("Marca inválida.")
    items = {item["ref"]: item for item in repository.entities(int(row["client_id"]))}
    if project_ref and (project_ref not in items or items[project_ref]["kind"] != "project"):
        raise PublicMcpAuthError("O projeto não pertence a esta conta.")
    if brand_ref and (brand_ref not in items or items[brand_ref]["kind"] != "brand"):
        raise PublicMcpAuthError("A marca não pertence a esta conta.")
    active_object = params.get("active_object")
    active = ActiveObject(str(active_object["type"]), str(active_object["id"])) if isinstance(active_object, dict) and active_object.get("type") and active_object.get("id") else None
    try:
        return RequestContext(
            organization_id=int(row["client_id"]), client_id=int(row["client_id"]),
            user_id=int(row["user_id"]), conversation_id=params.get("conversation_id"),
            surface=surface, project_ref=project_ref, brand_ref=brand_ref,
            active_object=active, capabilities=("workspace", "planner", "studio", "reports", "artifacts"),
        )
    except (TypeError, ValueError) as exc:
        raise PublicMcpAuthError("O contexto público do MCP é inválido.") from exc


def authenticate(params: dict) -> PublicMcpPrincipal:
    raw_token = _bearer()
    credential_type = "api_key"
    if raw_token.startswith(KEY_PREFIX):
        row = _load_key(raw_token)
    else:
        from . import oauth
        row = oauth.load_access_token(raw_token)
        credential_type = "oauth"
    context = _public_context(row, params)
    return PublicMcpPrincipal(
        key_id=str(row.get("credential_id") or row.get("id")), client_id=int(row["client_id"]), user_id=int(row["user_id"]),
        client_type=str(row["client_type"]), label=str(row["label"]),
        scopes=normalize_scopes(row.get("scopes"), allow_writes=True), context=context,
        credential_type=credential_type,
        grant_id=str(row.get("grant_id")) if row.get("grant_id") else None,
    )
