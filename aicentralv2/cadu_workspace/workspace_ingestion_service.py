"""Durable intake coordinator built on the existing project pipelines.

This service records the user's gesture, delegates persistence to the current
source/link services, and leaves indexing and Registry reconciliation to their
existing durable workers. It is the internal MCP boundary; external MCP tools
can keep stable contracts while this coordinator evolves.
"""

from __future__ import annotations

from uuid import uuid4

from flask import current_app
from psycopg.types.json import Json

from ..db import get_db
from .agent_v2.contracts import RequestContext
from . import project_source_service
from .reference_context import reference_context


def _relation(cursor, table: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS available", (f"public.{table}",))
    return bool((cursor.fetchone() or {}).get("available"))


def _preserve_external_reference(context: RequestContext, descriptor: dict, *, external_id: str = "",
                                 platform: str = "", description: str = "", tags=None,
                                 ingestion_item_id: str = "", meeting: dict | None = None,
                                 context_data: dict | None = None, origin: str = "chat") -> dict:
    """Upsert the provider-neutral source of truth without requiring a connector."""
    connection = get_db()
    reference_id = str(uuid4())
    metadata = {
        "title": descriptor.get("title"),
        "platform": str(platform or "")[:120] or descriptor.get("provider"),
        "external_id": str(external_id or "")[:512] or None,
        "description": str(description or "")[:4000] or None,
        "tags": list(tags or [])[:20],
        "resource_kind": descriptor.get("resource_kind"),
        "access_type": descriptor.get("access_type"),
        "connector_recommended": bool(descriptor.get("connector_recommended")),
        "meeting": dict(meeting or {}) or None,
        "user_message": (context_data or {}).get("user_message"),
        "context_summary": (context_data or {}).get("context_summary"),
        "project_item_kind": (context_data or {}).get("project_item_kind") or "reference",
        "timeline": (context_data or {}).get("timeline"),
        "origin": str(origin or "chat")[:32],
    }
    sync_status = "needs_authorization" if descriptor.get("connector_recommended") else "pending"
    try:
        with connection.cursor() as cursor:
            if not _relation(cursor, "cadu_workspace_external_references"):
                connection.rollback()
                return {"available": False}
            cursor.execute("""SELECT pg_get_constraintdef(oid) AS definition
                                FROM pg_constraint
                               WHERE conrelid='cadu_workspace_external_references'::regclass
                                 AND conname='cadu_workspace_external_references_reference_type_check'""")
            type_constraint = str((cursor.fetchone() or {}).get("definition") or "")
            stored_kind = descriptor["resource_kind"]
            if type_constraint and f"'{stored_kind}'" not in type_constraint:
                stored_kind = stored_kind if stored_kind in {"drive_file", "meeting", "web_page"} else "external_document"
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (
                f"cadu-external-reference:{context.client_id}:{context.project_ref}:{descriptor['url']}",
            ))
            cursor.execute(
                """SELECT id::text FROM cadu_workspace_external_references
                    WHERE client_id=%s AND project_ref=%s AND locator=%s
                    ORDER BY created_at LIMIT 1""",
                (context.client_id, context.project_ref, descriptor["url"]),
            )
            existing = cursor.fetchone()
            if existing:
                reference_id = str(existing["id"])
                created = False
                cursor.execute(
                    """UPDATE cadu_workspace_external_references SET
                         provider=%s, external_id=COALESCE(%s,external_id), reference_type=%s,
                         ingestion_item_id=COALESCE(%s,ingestion_item_id), metadata=metadata || %s,
                         archived_at=NULL,updated_at=NOW()
                       WHERE id=%s RETURNING id::text,sync_status""",
                    (descriptor["provider"], str(external_id or "")[:512] or None,
                     stored_kind, ingestion_item_id or None, Json(metadata), reference_id),
                )
            else:
                created = True
                cursor.execute(
                    """INSERT INTO cadu_workspace_external_references
                       (id,client_id,project_ref,ingestion_item_id,provider,external_id,locator,
                        connection_ref,reference_type,sync_status,metadata,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,NOW(),NOW())
                       RETURNING id::text,sync_status""",
                    (reference_id, context.client_id, context.project_ref, ingestion_item_id or None,
                     descriptor["provider"], str(external_id or "")[:512] or None, descriptor["url"],
                     stored_kind, sync_status, Json(metadata)),
                )
            row = dict(cursor.fetchone())
        connection.commit()
        return {"available": True, "reference_id": row["id"], "sync_status": row["sync_status"],
                "created": created}
    except Exception:
        connection.rollback()
        raise


def ingest_link(context: RequestContext, *, url: str, title: str = "", resource_kind: str = "",
                platform: str = "", external_id: str = "", description: str = "",
                tags: list[str] | None = None, meeting: dict | None = None,
                user_message: str = "", project_item_kind: str = "",
                origin: str = "chat", request_id: str = "") -> dict:
    """Preserve a project link and record its enrichment lifecycle.

    The link remains useful even when the ingestion migration has not yet been
    deployed. In that rollout state the existing link pipeline still succeeds.
    """
    descriptor = project_source_service.describe_link(url, title)
    resource_kind = str(resource_kind or "").strip().lower()
    if resource_kind and resource_kind not in project_source_service.EXTERNAL_RESOURCE_KINDS:
        raise ValueError("Tipo de recurso externo inválido.")
    if tags is not None and not isinstance(tags, list):
        raise ValueError("As etiquetas do recurso devem ser enviadas como uma lista.")
    tags = list(dict.fromkeys(
        str(item or "").strip()[:64] for item in (tags or []) if str(item or "").strip()
    ))[:20]
    platform = str(platform or "").strip()[:120]
    external_id = str(external_id or "").strip()[:512]
    context_data = reference_context(message=user_message, url=descriptor["url"], descriptor=descriptor,
                                     meeting=meeting, requested_kind=project_item_kind)
    if not title and context_data.get("suggested_title"):
        title = context_data["suggested_title"]
        descriptor = project_source_service.describe_link(url, title)
    description = str(description or context_data.get("context_summary") or "")[:4000]
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
                     Json({"input_type": "url", "provider": descriptor["provider"],
                           "user_message": context_data.get("user_message"),
                           "context_summary": context_data.get("context_summary"),
                           "project_item_kind": context_data.get("project_item_kind"), "timeline": context_data.get("timeline")})),
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
                         Json({**{key: value for key, value in descriptor.items() if key != "url"},
                               "user_message": context_data.get("user_message"),
                               "context_summary": context_data.get("context_summary"),
                               "project_item_kind": context_data.get("project_item_kind"), "timeline": context_data.get("timeline")})),
                    )
                    tracked = True
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    external = _preserve_external_reference(
        context, {**descriptor, "resource_kind": resource_kind or descriptor["resource_kind"]},
        external_id=external_id, platform=platform, description=description, tags=tags,
        ingestion_item_id=item_id if tracked else "", meeting=meeting,
        context_data=context_data, origin=origin,
    )
    if not external.get("reference_id"):
        if tracked:
            _finish(session_id, item_id, status="failed", error="A base canônica de referências não está disponível.")
        raise RuntimeError("A base canônica de referências do projeto não está disponível.")
    result = {
        "link_id": external["reference_id"], "reference_id": external["reference_id"],
        "status": "created" if external.get("created") else "updated",
        "resource_created": bool(external.get("created")), "canonical": True,
        "url": descriptor["url"], "title": descriptor["title"],
        "provider": descriptor["provider"],
        "resource_kind": resource_kind or descriptor["resource_kind"],
        "access_type": descriptor["access_type"], "embed_type": descriptor["embed_type"],
        "connector_recommended": descriptor["connector_recommended"],
        "created": bool(external.get("created")),
        "platform": platform or descriptor["provider"], "external_id": external_id or None,
        "description": description or None, "tags": list(tags or []), "meeting": meeting or None,
        "purpose": "project_attachment", "indexing": "not_requested",
        "access": "not_checked", "content": "not_read", "registry_sync": "queued",
    }
    if tracked:
        _finish(session_id, item_id, status="completed", link_id=result["link_id"])
    if external.get("reference_id"):
        try:
            from . import project_resource_service
            project_resource_service.notify_change(
                context.client_id, context.project_ref, "linked",
                source_system="external_reference", source_id=external["reference_id"],
                actor_id=context.user_id,
            )
        except Exception:
            current_app.logger.exception(
                "Falha ao enfileirar referência externa %s", external["reference_id"],
            )
    return {**result, "context_summary": context_data.get("context_summary"),
            "project_item_kind": context_data.get("project_item_kind"),
            "user_message": context_data.get("user_message"), "timeline": context_data.get("timeline"),
            "external_reference": external, "ingestion": {
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
                          metadata=COALESCE(metadata,'{}'::jsonb) || %s::jsonb, updated_at=NOW()
                    WHERE id=%s AND session_id=%s""",
                ("skipped" if status == "completed" else "failed", error or None,
                 Json({"project_link_id": link_id} if link_id else {}), item_id, session_id),
            )
            cursor.execute(
                """UPDATE cadu_workspace_ingestion_sessions
                      SET status=%s, completed_at=CASE WHEN %s='completed' THEN NOW() ELSE completed_at END,
                          updated_at=NOW(), metadata=COALESCE(metadata,'{}'::jsonb) || %s::jsonb
                    WHERE id=%s""",
                (status, status, Json({"error": error} if error else {}), session_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
