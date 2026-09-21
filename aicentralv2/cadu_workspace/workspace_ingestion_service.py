"""Durable intake coordinator built on the existing project pipelines.

This service records the user's gesture, delegates persistence to the current
source/link services, and leaves indexing and Registry reconciliation to their
existing durable workers. It is the internal MCP boundary; external MCP tools
can keep stable contracts while this coordinator evolves.
"""

from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from ..db import get_db
from .agent_v2.contracts import RequestContext
from . import project_source_service


def _relation(cursor, table: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS available", (f"public.{table}",))
    return bool((cursor.fetchone() or {}).get("available"))


def ingest_link(context: RequestContext, *, url: str, title: str = "",
                origin: str = "chat", request_id: str = "") -> dict:
    """Preserve a project link and record its enrichment lifecycle.

    The link remains useful even when the ingestion migration has not yet been
    deployed. In that rollout state the existing link pipeline still succeeds.
    """
    descriptor = project_source_service.describe_link(url, title)
    session_id, item_id = str(uuid4()), str(uuid4())
    connection = get_db()
    tracked = False
    try:
        with connection.cursor() as cursor:
            if (_relation(cursor, "cadu_workspace_ingestion_sessions")
                    and _relation(cursor, "cadu_workspace_ingestion_items")):
                cursor.execute(
                    """INSERT INTO cadu_workspace_ingestion_sessions
                       (id,organization_id,client_id,user_id,project_ref,surface,origin,status,
                        requested_purpose,idempotency_key,metadata,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,'conversations',%s,'processing',
                               'project_attachment',%s,%s,NOW(),NOW())
                       ON CONFLICT (client_id,user_id,idempotency_key)
                         WHERE idempotency_key IS NOT NULL DO NOTHING""",
                    (session_id, context.organization_id, context.client_id, context.user_id,
                     context.project_ref, origin, request_id or None,
                     Json({"input_type": "url", "provider": descriptor["provider"]})),
                )
                if cursor.rowcount:
                    cursor.execute(
                        """INSERT INTO cadu_workspace_ingestion_items
                           (id,session_id,client_id,item_type,original_name,original_url,provider,
                            purpose,category,classification_status,classification_confidence,
                            classification_reason,extraction_status,metadata,created_at,updated_at)
                           VALUES (%s,%s,%s,'url',%s,%s,%s,'project_attachment','reference',
                                   'classified',1,%s,'not_requested',%s,NOW(),NOW())""",
                        (item_id, session_id, context.client_id, descriptor["title"], descriptor["url"],
                         descriptor["provider"], "Plataforma e tipo classificados pela URL.",
                         Json({key: value for key, value in descriptor.items() if key != "url"})),
                    )
                    tracked = True
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    try:
        result = project_source_service.create_link_reference(context, url=url, title=title)
    except Exception:
        if tracked:
            _finish(session_id, item_id, status="failed", error="Não foi possível preservar o link.")
        raise

    if tracked:
        _finish(session_id, item_id, status="completed", link_id=result["link_id"])
    return {**result, "ingestion": {
        "tracked": tracked, "session_id": session_id if tracked else None,
        "item_id": item_id if tracked else None,
        "status": "completed", "next": _next_step(result),
    }}


def list_recent(context: RequestContext, *, limit: int = 20) -> dict:
    """Return real intake progress for chat and project surfaces."""
    limit = max(1, min(int(limit or 20), 100))
    connection = get_db()
    with connection.cursor() as cursor:
        if not (_relation(cursor, "cadu_workspace_ingestion_sessions")
                and _relation(cursor, "cadu_workspace_ingestion_items")):
            return {"available": False, "sessions": [], "summary": {}}
        cursor.execute(
            """SELECT session.id::text,session.origin,session.status,session.created_at,
                      session.updated_at,session.completed_at,
                      COUNT(item.id)::int AS total,
                      COUNT(item.id) FILTER (WHERE item.classification_status='classified')::int AS classified,
                      COUNT(item.id) FILTER (WHERE item.extraction_status IN ('queued','extracting'))::int AS extracting,
                      COUNT(item.id) FILTER (WHERE item.extraction_status='completed')::int AS extracted,
                      COUNT(item.id) FILTER (WHERE item.classification_status='needs_review'
                                               OR item.extraction_status='failed')::int AS needs_review
                 FROM cadu_workspace_ingestion_sessions session
            LEFT JOIN cadu_workspace_ingestion_items item ON item.session_id=session.id
                WHERE session.client_id=%s AND session.project_ref=%s
             GROUP BY session.id
             ORDER BY session.created_at DESC LIMIT %s""",
            (context.client_id, context.project_ref, limit),
        )
        sessions = [dict(row) for row in cursor.fetchall()]
    summary = {
        "sessions": len(sessions),
        "items": sum(int(item.get("total") or 0) for item in sessions),
        "classified": sum(int(item.get("classified") or 0) for item in sessions),
        "extracting": sum(int(item.get("extracting") or 0) for item in sessions),
        "extracted": sum(int(item.get("extracted") or 0) for item in sessions),
        "needs_review": sum(int(item.get("needs_review") or 0) for item in sessions),
    }
    return {"available": True, "sessions": sessions, "summary": summary}


def _next_step(result: dict) -> str:
    if result.get("access_type") == "authenticated" or result.get("connector_recommended"):
        return "connect_or_keep_reference"
    if result.get("access_type") == "public":
        return "eligible_for_public_extraction"
    return "inspect_access"


def _finish(session_id: str, item_id: str, *, status: str, link_id: str = "", error: str = "") -> None:
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_workspace_ingestion_items
                      SET extraction_status=%s, extraction_error=%s,
                          metadata=metadata || %s, updated_at=NOW()
                    WHERE id=%s AND session_id=%s""",
                ("skipped" if status == "completed" else "failed", error or None,
                 Json({"project_link_id": link_id} if link_id else {}), item_id, session_id),
            )
            cursor.execute(
                """UPDATE cadu_workspace_ingestion_sessions
                      SET status=%s, completed_at=CASE WHEN %s='completed' THEN NOW() ELSE completed_at END,
                          updated_at=NOW(), metadata=metadata || %s
                    WHERE id=%s""",
                (status, status, Json({"error": error} if error else {}), session_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
