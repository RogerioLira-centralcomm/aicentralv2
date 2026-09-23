"""Persistent application context shared by internal and public MCP transports."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import secrets
from uuid import uuid4
from uuid import UUID

from psycopg.types.json import Json

from ...db import get_db
from ..agent_v2.contracts import ActiveObject, RequestContext
from .registry import ToolInputError


HANDLE_PREFIX = "cadu_ctx_"


def _identity(principal, exposure: str) -> dict:
    credential_type = str(getattr(principal, "credential_type", "internal") or "internal")
    credential_id = (getattr(principal, "grant_id", None) if credential_type == "oauth"
                     else getattr(principal, "key_id", None))
    return {
        "client_id": int(principal.context.client_id),
        "user_id": int(principal.context.user_id),
        "credential_type": credential_type,
        "credential_id": str(credential_id or ""),
        "client_type": str(getattr(principal, "client_type", "internal") or "internal"),
        "exposure": exposure,
    }


def _hash(handle: str) -> str:
    return sha256(handle.encode("utf-8")).hexdigest()


def _row(handle: str, principal, exposure: str, *, lock: bool = False) -> dict:
    if not isinstance(handle, str) or not handle.startswith(HANDLE_PREFIX) or len(handle) > 180:
        raise ToolInputError("context_handle inválido.")
    identity = _identity(principal, exposure)
    suffix = " FOR UPDATE" if lock else ""
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT * FROM cadu_mcp_contexts
             WHERE handle_hash=%s AND client_id=%s AND user_id=%s AND exposure=%s
               AND expires_at > NOW()""" + suffix,
                       (_hash(handle), identity["client_id"], identity["user_id"], exposure))
        value = cursor.fetchone()
    if not value:
        raise ToolInputError("Contexto MCP não encontrado para esta conta.")
    value = dict(value)
    if value["status"] != "active" or value["expires_at"] is None:
        raise ToolInputError("O contexto MCP não está mais ativo.")
    if identity["credential_id"] and value.get("credential_id") and value["credential_id"] != identity["credential_id"]:
        raise ToolInputError("O contexto MCP pertence a outra conexão autorizada.")
    return value


def _public(row: dict, handle: str, *, events=None) -> dict:
    result = {
        "context_handle": handle,
        "conversation_id": str(row["conversation_id"]) if row.get("conversation_id") else None,
        "project_ref": row.get("project_ref"), "brand_ref": row.get("brand_ref"),
        "active_object": row.get("active_object"), "surface": row.get("surface"),
        "label": row.get("label"), "sequence": int(row.get("sequence") or 0),
        "expires_at": row.get("expires_at"), "status": row.get("status"),
    }
    if events is not None:
        result["recent_operations"] = events
    return result


def open_context(principal, arguments: dict, exposure: str) -> dict:
    context = principal.context
    conversation_id = arguments.get("conversation_id") or context.conversation_id
    project_ref = arguments.get("project_ref") or context.project_ref
    brand_ref = arguments.get("brand_ref") or context.brand_ref
    # Reuse the exact canonical conversation for this credential; parallel host
    # conversations without a conversation_id receive independent handles.
    identity = _identity(principal, exposure)
    from ...cadu_family import repository
    entities = {item["ref"]: item for item in repository.entities(context.client_id)}
    if project_ref and (project_ref not in entities or entities[project_ref]["kind"] != "project"):
        raise ToolInputError("O projeto não pertence a esta conta.")
    if (project_ref and str(project_ref).startswith("ci:")
            and not repository.project_user_can_view(context.client_id, project_ref, context.user_id)):
        raise ToolInputError("Você não tem acesso a este projeto.")
    if brand_ref and (brand_ref not in entities or entities[brand_ref]["kind"] != "brand"):
        raise ToolInputError("A marca não pertence a esta conta.")
    if conversation_id:
        try:
            conversation_id = str(UUID(str(conversation_id)))
        except (TypeError, ValueError) as exc:
            raise ToolInputError("conversation_id inválido.") from exc
        with get_db().cursor() as cursor:
            cursor.execute("""SELECT id FROM cadu_conversations
                WHERE id=%s AND id_cliente=%s AND id_contato_cliente=%s""",
                           (conversation_id, identity["client_id"], identity["user_id"]))
            if not cursor.fetchone():
                raise ToolInputError("A conversa informada não pertence a esta conta.")
    raw = HANDLE_PREFIX + secrets.token_urlsafe(32)
    context_id = uuid4()
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO cadu_mcp_contexts
                (id,handle_hash,client_id,user_id,credential_type,credential_id,client_type,exposure,
                 conversation_id,surface,project_ref,brand_ref,active_object,label)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (context_id, _hash(raw), identity["client_id"], identity["user_id"],
                 identity["credential_type"], identity["credential_id"] or None,
                 identity["client_type"], exposure, conversation_id, context.surface,
                 project_ref, brand_ref,
                 Json(context.active_object.to_dict()) if context.active_object else None,
                 str(arguments.get("label") or "")[:120] or None))
            row = dict(cursor.fetchone())
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return _public(row, raw, events=[])


def get_context(principal, arguments: dict, exposure: str) -> dict:
    handle = str(arguments.get("context_handle") or "")
    row = _row(handle, principal, exposure)
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT sequence,operation_id::text,tool_name,event_type,result_summary,
                                  terminal_state,created_at
                             FROM cadu_mcp_context_events WHERE context_id=%s
                         ORDER BY sequence DESC LIMIT 12""", (row["id"],))
        events = [dict(item) for item in cursor.fetchall()]
    return _public(row, handle, events=events)


def update_context(principal, arguments: dict, exposure: str) -> dict:
    handle = str(arguments.get("context_handle") or "")
    row = _row(handle, principal, exposure, lock=True)
    changes = {key: arguments[key] for key in ("project_ref", "brand_ref", "active_object", "label") if key in arguments}
    if not changes:
        raise ToolInputError("Informe ao menos uma alteração de contexto.")
    context = principal.context
    project_ref = changes.get("project_ref", row.get("project_ref"))
    brand_ref = changes.get("brand_ref", row.get("brand_ref"))
    # Reuse the authoritative public/internal resolver validations by ensuring
    # selected entities are present in the principal's tenant inventory.
    from ...cadu_family import repository
    entities = {item["ref"]: item for item in repository.entities(context.client_id)}
    if project_ref and (project_ref not in entities or entities[project_ref]["kind"] != "project"):
        raise ToolInputError("O projeto não pertence a esta conta.")
    if (project_ref and str(project_ref).startswith("ci:")
            and not repository.project_user_can_view(context.client_id, project_ref, context.user_id)):
        raise ToolInputError("Você não tem acesso a este projeto.")
    if brand_ref and (brand_ref not in entities or entities[brand_ref]["kind"] != "brand"):
        raise ToolInputError("A marca não pertence a esta conta.")
    active = changes.get("active_object", row.get("active_object"))
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_mcp_contexts SET project_ref=%s,brand_ref=%s,
                active_object=%s,label=%s,last_used_at=NOW() WHERE id=%s RETURNING *""",
                (project_ref, brand_ref, Json(active) if active else None,
                 str(changes.get("label", row.get("label")) or "")[:120] or None, row["id"]))
            updated = dict(cursor.fetchone())
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return _public(updated, handle)


def close_context(principal, arguments: dict, exposure: str) -> dict:
    handle = str(arguments.get("context_handle") or "")
    row = _row(handle, principal, exposure, lock=True)
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""UPDATE cadu_mcp_contexts SET status='closed',closed_at=NOW(),last_used_at=NOW()
                               WHERE id=%s""", (row["id"],))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"context_handle": handle, "status": "closed"}


def _request_context(row: dict, base: RequestContext) -> RequestContext:
    active = row.get("active_object")
    active_object = ActiveObject(str(active["type"]), str(active["id"])) if isinstance(active, dict) and active.get("type") and active.get("id") else None
    return replace(base, conversation_id=str(row["conversation_id"]) if row.get("conversation_id") else None,
                   surface=row.get("surface") or base.surface, project_ref=row.get("project_ref"),
                   brand_ref=row.get("brand_ref"), active_object=active_object)


def resolve_context(principal, handle: str, exposure: str) -> RequestContext:
    """Resolve a handle for non-JSON-RPC companion requests such as uploads."""
    if not handle:
        return principal.context
    return _request_context(_row(str(handle), principal, exposure), principal.context)


def _record(row: dict, tool_name: str, result, state="completed") -> None:
    if isinstance(result, dict):
        safe_keys = {"id", "status", "title", "name", "project_ref", "brand_ref", "artifact_id",
                     "job_id", "operation_id", "source_id", "resource_ref", "created", "updated"}
        summary = {key: value for key, value in result.items() if key in safe_keys and isinstance(value, (str, int, float, bool, type(None)))}
        summary["result_keys"] = sorted(str(key) for key in result)[:40]
    else:
        summary = {"result_type": type(result).__name__}
    encoded = json.dumps(summary, ensure_ascii=False, default=str)
    if len(encoded) > 8000:
        summary = {"truncated": True, "keys": sorted(summary)[:40] if isinstance(summary, dict) else []}
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE cadu_mcp_contexts SET sequence=sequence+1,last_used_at=NOW() WHERE id=%s RETURNING sequence", (row["id"],))
            sequence = int(cursor.fetchone()["sequence"])
            cursor.execute("""INSERT INTO cadu_mcp_context_events
                (context_id,sequence,tool_name,event_type,result_summary,terminal_state)
                VALUES (%s,%s,%s,'tool_call',%s,%s)""",
                (row["id"], sequence, tool_name, Json(summary), state))
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def execute(principal, name: str, arguments: dict, exposure: str, registry):
    if name == "context.open":
        return open_context(principal, arguments, exposure)
    if name == "context.get":
        return get_context(principal, arguments, exposure)
    if name == "context.update":
        return update_context(principal, arguments, exposure)
    if name == "context.close":
        return close_context(principal, arguments, exposure)
    arguments = dict(arguments or {})
    handle = str(arguments.pop("context_handle", "") or "")
    row = _row(handle, principal, exposure) if handle else None
    context = _request_context(row, principal.context) if row else principal.context
    try:
        value = registry.execute(name, arguments, context, exposure)
        if row:
            _record(row, name, value)
            if isinstance(value, dict):
                value = {**value, "_context": {"context_handle": handle, "conversation_id": context.conversation_id}}
        return value
    except Exception as exc:
        if row:
            _record(row, name, {"error": type(exc).__name__}, "failed")
        raise
