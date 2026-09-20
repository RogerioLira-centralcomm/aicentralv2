"""Canonical project resource registry shared by the UI and MCP."""

from collections import Counter
from hashlib import sha256
import json
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Json

from ..db import get_db
from .agent_v2.contracts import RequestContext


RESOURCE_TYPES = {
    "file": "Arquivo", "artifact": "Artifact", "media_plan": "Plano de mídia",
    "report": "Relatório", "image": "Imagem", "video": "Vídeo",
    "analysis": "Análise", "link": "Link",
}


def _project_id(project_ref: str) -> str:
    if not str(project_ref or "").startswith("ci:"):
        raise ValueError("O registro de recursos exige um projeto nativo do Cadu.")
    return str(project_ref)[3:]


def resource_id_for_source(client_id: int, project_ref: str, source_system: str, source_id: str) -> str:
    """Return the deterministic ID used by the materialized resource registry."""
    return str(uuid5(
        NAMESPACE_URL,
        f"cadu:{client_id}:{project_ref}:{source_system}:{source_id}",
    ))


def _relation(cursor, table: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS available", (f"public.{table}",))
    return bool(cursor.fetchone()["available"])


def _columns(cursor, table: str) -> set[str]:
    cursor.execute("""SELECT column_name FROM information_schema.columns
                       WHERE table_schema = 'public' AND table_name = %s""", (table,))
    return {row["column_name"] for row in cursor.fetchall()}


def _record(source_system, source_id, resource_type, title, **values):
    return {
        "source_system": source_system, "source_id": str(source_id),
        "resource_type": resource_type, "title": str(title or RESOURCE_TYPES.get(resource_type, "Recurso"))[:500],
        "mime_type": values.get("mime_type"), "purpose": values.get("purpose") or "project_resource",
        "category": values.get("category") or "other", "status": values.get("status") or "active",
        "version": max(1, int(values.get("version") or 1)), "content_hash": values.get("content_hash"),
        "locator": values.get("locator"), "metadata": values.get("metadata") or {},
        "created_by": values.get("created_by"), "source_created_at": values.get("source_created_at"),
        "source_updated_at": values.get("source_updated_at") or values.get("source_created_at"),
    }


def _collect(cursor, client_id: int, project_ref: str) -> list[dict]:
    project_id = _project_id(project_ref)
    records = []
    if _relation(cursor, "cadu_ci_projeto_arquivos"):
        columns = _columns(cursor, "cadu_ci_projeto_arquivos")
        purpose = "purpose" if "purpose" in columns else "CASE WHEN indexing_status='completed' THEN 'knowledge_source' ELSE 'project_attachment' END AS purpose"
        category = "category" if "category" in columns else "'other' AS category"
        metadata = "classification_metadata" if "classification_metadata" in columns else "'{}'::jsonb AS classification_metadata"
        chunk_count = "(SELECT COUNT(*) FROM cadu_ci_chunks ch WHERE ch.arquivo_id = a.id)" if _relation(cursor, "cadu_ci_chunks") else "0"
        cursor.execute(f"""SELECT a.id, a.nome_arquivo, a.mime, a.storage_path, a.indexing_status, {purpose}, {category}, {metadata},
                                   {chunk_count} AS chunk_count,
                                   a.criado_por, a.created_at, a.updated_at
                              FROM cadu_ci_projeto_arquivos
                             AS a WHERE a.id_cliente=%s AND a.projeto_id=%s""", (client_id, project_id))
        for row in cursor.fetchall():
            records.append(_record("workspace", f"file:{row['id']}", "file", row["nome_arquivo"],
                mime_type=row.get("mime"), purpose=row.get("purpose"), category=row.get("category"),
                status=row.get("indexing_status"), content_hash=(row.get("classification_metadata") or {}).get("sha256"),
                locator=row.get("storage_path"), created_by=row.get("criado_por"),
                source_created_at=row.get("created_at"), source_updated_at=row.get("updated_at"),
                metadata={"chunk_count": int(row.get("chunk_count") or 0),
                          "indexing_status": row.get("indexing_status")}))

    queries = (
        ("cadu_workspace_artifacts", """SELECT id::text AS id, type, title, status, current_version AS version,
             created_by, created_at, updated_at FROM cadu_workspace_artifacts
             WHERE client_id=%s AND project_ref=%s""", "artifact"),
        ("cadu_planner_plans", """SELECT id::text AS id, title, status, 1 AS version, created_by,
             created_at, updated_at FROM cadu_planner_plans WHERE client_id=%s AND project_ref=%s
             AND archived_at IS NULL""", "media_plan"),
        ("cadu_connect_report_workspaces", """SELECT id::text AS id, campaign_name AS title,
             'active' AS status, 1 AS version, created_at, updated_at
             FROM cadu_connect_report_workspaces WHERE client_id=%s AND project_ref=%s""", "report"),
    )
    for table, query, resource_type in queries:
        if not _relation(cursor, table):
            continue
        cursor.execute(query, (client_id, project_ref))
        for row in cursor.fetchall():
            category = row.get("type") or resource_type
            records.append(_record(table, row["id"], resource_type, row.get("title"), category=category,
                status=row.get("status"), version=row.get("version"), created_by=row.get("created_by"),
                source_created_at=row.get("created_at"), source_updated_at=row.get("updated_at")))

    if _relation(cursor, "cadu_artifacts"):
        cursor.execute("""SELECT id::text AS id, titulo, tipo, status, created_at, updated_at
                            FROM cadu_artifacts WHERE id_cliente=%s AND projeto_id=%s""", (client_id, project_id))
        for row in cursor.fetchall():
            records.append(_record("planner_docs", row["id"], "artifact", row.get("titulo"),
                category=row.get("tipo") or "document", status=row.get("status"),
                source_created_at=row.get("created_at"), source_updated_at=row.get("updated_at")))

    if _relation(cursor, "cadu_docs_client_images"):
        cursor.execute("""SELECT id::text AS id, title, source, mime, file_path, created_at
                            FROM cadu_docs_client_images
                           WHERE id_cliente=%s AND projeto_id=%s AND ativo=true""", (client_id, project_id))
        for row in cursor.fetchall():
            records.append(_record("workspace_images", row["id"], "image", row.get("title"),
                mime_type=row.get("mime"), category="reference", locator=row.get("file_path"),
                metadata={"source": row.get("source")}, source_created_at=row.get("created_at")))

    if _relation(cursor, "studio_creative_analyses"):
        cursor.execute("""SELECT public_id::text AS id, original_name, media_type, status, created_at
                            FROM studio_creative_analyses WHERE client_id=%s AND project_ref=%s""",
                       (client_id, project_ref))
        for row in cursor.fetchall():
            records.append(_record("studio_analyzer", row["id"], "analysis", row.get("original_name"),
                category=f"{row.get('media_type') or 'creative'}_analysis", status=row.get("status"),
                source_created_at=row.get("created_at")))

    if _relation(cursor, "cadu_ci_projeto_links"):
        cursor.execute("""SELECT id::text AS id, titulo, provider, url, criado_por, created_at, updated_at
                            FROM cadu_ci_projeto_links WHERE id_cliente=%s AND projeto_id=%s""", (client_id, project_id))
        for row in cursor.fetchall():
            records.append(_record("workspace", f"link:{row['id']}", "link", row["titulo"], category="reference",
                locator=row.get("url"), metadata={"provider": row.get("provider")}, created_by=row.get("criado_por"),
                source_created_at=row.get("created_at"), source_updated_at=row.get("updated_at")))

    if _relation(cursor, "cadu_planner_link_test_runs"):
        columns = _columns(cursor, "cadu_planner_link_test_runs")
        if "project_ref" in columns:
            cursor.execute("""SELECT id::text AS id, mode, original_url, final_url, score,
                                      status_label, created_by, created_at
                                 FROM cadu_planner_link_test_runs
                                WHERE client_id=%s AND project_ref=%s""", (client_id, project_ref))
            for row in cursor.fetchall():
                records.append(_record(
                    "planner_link_tester", row["id"], "analysis",
                    f"Link Tester · {row.get('final_url') or row.get('original_url')}",
                    category=f"link_test_{row.get('mode') or 'destination'}", status="active",
                    locator=row.get("final_url"), created_by=row.get("created_by"),
                    metadata={"score": row.get("score"), "status_label": row.get("status_label")},
                    source_created_at=row.get("created_at"),
                ))

    if _relation(cursor, "cx_studio_projects") and _relation(cursor, "cx_studio_project_items"):
        cursor.execute("""SELECT item.id::text AS id, item.kind, item.title, item.asset_url, item.source_type,
                                   item.user_id, item.metadata, item.created_at, item.updated_at
                              FROM cx_studio_project_items item
                              JOIN cx_studio_projects project ON project.id=item.project_id
                             WHERE project.client_id=%s AND project.document->>'external_project_id'=%s""",
                       (client_id, project_id))
        for row in cursor.fetchall():
            kind = row.get("kind") if row.get("kind") in {"image", "video"} else "file"
            records.append(_record("studio", row["id"], kind, row.get("title"), category=row.get("kind"),
                locator=row.get("asset_url"), metadata={"source_type": row.get("source_type"), **(row.get("metadata") or {})},
                created_by=row.get("user_id"), source_created_at=row.get("created_at"), source_updated_at=row.get("updated_at")))
    return records


def reconcile(client_id: int, project_ref: str, actor_id=None) -> dict:
    project_id = _project_id(project_ref)
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM cadu_ci_projetos WHERE id=%s AND id_cliente=%s", (project_id, client_id))
            if not cursor.fetchone():
                raise ValueError("Projeto indisponível.")
            if not _relation(cursor, "cadu_project_resources"):
                return {"available": False, "resources": [], "summary": {}}
            cursor.execute("SELECT clock_timestamp() AS started_at")
            started_at = cursor.fetchone()["started_at"]
            records = _collect(cursor, client_id, project_ref)
            for item in records:
                resource_id = resource_id_for_source(client_id, project_ref, item["source_system"], item["source_id"])
                fingerprint = sha256(json.dumps(item, default=str, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                cursor.execute("""INSERT INTO cadu_project_resources
                (id, organization_id, client_id, project_ref, source_system, source_id, resource_type,
                 title, mime_type, purpose, category, status, version, content_hash, locator, metadata,
                 created_by, source_created_at, source_updated_at, first_seen_at, last_seen_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                ON CONFLICT (client_id, project_ref, source_system, source_id) DO UPDATE SET
                 resource_type=EXCLUDED.resource_type,title=EXCLUDED.title,mime_type=EXCLUDED.mime_type,
                 purpose=EXCLUDED.purpose,category=EXCLUDED.category,status=EXCLUDED.status,
                 version=EXCLUDED.version,content_hash=EXCLUDED.content_hash,locator=EXCLUDED.locator,
                 metadata=EXCLUDED.metadata,source_updated_at=EXCLUDED.source_updated_at,last_seen_at=NOW()
                    RETURNING id""", (resource_id, client_id, client_id, project_ref, item["source_system"], item["source_id"],
                     item["resource_type"], item["title"], item["mime_type"], item["purpose"], item["category"], item["status"],
                     item["version"], item["content_hash"], item["locator"], Json(item["metadata"]), item["created_by"],
                     item["source_created_at"], item["source_updated_at"]))
                persisted_id = str(cursor.fetchone()["id"])
                cursor.execute("""INSERT INTO cadu_project_resource_events
                (resource_id, client_id, project_ref, event_type, fingerprint, actor_id, details)
                VALUES (%s,%s,%s,'reconciled',%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (persisted_id, client_id, project_ref, fingerprint, actor_id,
                     Json({"source_system": item["source_system"], "source_id": item["source_id"]})))
            cursor.execute("""UPDATE cadu_project_resources SET status='archived', last_seen_at=NOW()
                                WHERE client_id=%s AND project_ref=%s AND last_seen_at < %s
                                  AND status <> 'archived'""", (client_id, project_ref, started_at))
            _rebuild_relations(cursor, client_id, project_ref)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"available": True, **list_resources(client_id, project_ref, reconcile_first=False)}


def list_resources(client_id: int, project_ref: str, *, reconcile_first=True, actor_id=None) -> dict:
    if reconcile_first:
        return reconcile(client_id, project_ref, actor_id)
    with get_db().cursor() as cursor:
        if not _relation(cursor, "cadu_project_resources"):
            return {"resources": [], "summary": {}}
        cursor.execute("""SELECT id::text, source_system, source_id, resource_type, title, mime_type,
                                  purpose, category, status, version, content_hash, locator, metadata,
                                  source_created_at, source_updated_at, last_seen_at
                             FROM cadu_project_resources
                            WHERE client_id=%s AND project_ref=%s AND status <> 'archived'
                         ORDER BY COALESCE(source_updated_at, source_created_at, last_seen_at) DESC, title""",
                       (client_id, project_ref))
        resources = [dict(row) for row in cursor.fetchall()]
        relations = []
        if _relation(cursor, "cadu_project_resource_relations"):
            cursor.execute("""SELECT source_resource_id::text, target_resource_id::text,
                                      relation_type, confidence, metadata
                                 FROM cadu_project_resource_relations
                                WHERE client_id=%s AND project_ref=%s
                             ORDER BY relation_type, source_resource_id""", (client_id, project_ref))
            relations = [dict(row) for row in cursor.fetchall()]
    counts = Counter(item["resource_type"] for item in resources)
    hashes = Counter(item["content_hash"] for item in resources if item.get("content_hash"))
    for item in resources:
        item["possible_duplicate"] = bool(item.get("content_hash") and hashes[item["content_hash"]] > 1)
    return {"resources": resources, "relations": relations, "summary": {
        "total": len(resources), "possible_duplicates": sum(1 for item in resources if item["possible_duplicate"]),
        **dict(counts),
    }}


def list_recent_resources(client_id: int, project_refs: list[str], *, limit: int = 24) -> list[dict]:
    """Return a bounded, cross-project Registry timeline for operational surfaces.

    The workspace home must not reconcile projects or perform one query per
    project merely to render its continuity feed.  This read is deliberately
    small and leaves resource detail, relations and reconciliation to the
    project surface that the user opens next.
    """
    refs = [str(project_ref) for project_ref in project_refs if str(project_ref).startswith("ci:")]
    if not refs or limit < 1:
        return []
    with get_db().cursor() as cursor:
        if not _relation(cursor, "cadu_project_resources"):
            return []
        cursor.execute(
            """SELECT id::text, project_ref, source_system, source_id, resource_type,
                      title, mime_type, purpose, category, status, version, locator,
                      source_created_at, source_updated_at, last_seen_at
                 FROM cadu_project_resources
                WHERE client_id = %s
                  AND project_ref = ANY(%s)
                  AND status <> 'archived'
             ORDER BY COALESCE(source_updated_at, source_created_at, last_seen_at) DESC, id DESC
                LIMIT %s""",
            (client_id, refs, min(int(limit), 100)),
        )
        return [dict(row) for row in cursor.fetchall()]


def list_for_context(context: RequestContext) -> dict:
    # MCP reads use the materialized registry. Mutations enqueue reconciliation;
    # the project-detail UI retains an explicit repair-on-open path for rollout.
    return list_resources(context.client_id, context.project_ref or "", reconcile_first=False,
                          actor_id=context.user_id)


def notify_change(client_id: int, project_ref: str, event_type: str, *, source_system="", source_id="", actor_id=None) -> None:
    """Persist a movement for the supervised worker; reads may still reconcile on demand."""
    from uuid import uuid4
    connection = get_db()
    job_id = str(uuid4())
    try:
        with connection.cursor() as cursor:
            if not _relation(cursor, "cadu_project_resource_jobs"):
                return
            cursor.execute("""INSERT INTO cadu_project_resource_jobs
                (id,client_id,project_ref,event_type,source_system,source_id,actor_id,status,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'queued',NOW())""",
                (job_id, client_id, project_ref, event_type, source_system or None,
                 str(source_id or "") or None, actor_id))
        connection.commit()
    except Exception as exc:
        connection.rollback()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""UPDATE cadu_project_resource_jobs SET status='failed',error_message=%s,finished_at=NOW()
                                    WHERE id=%s""", (str(exc)[:500], job_id))
            connection.commit()
        except Exception:
            connection.rollback()
        raise


def _rebuild_relations(cursor, client_id: int, project_ref: str) -> None:
    if not _relation(cursor, "cadu_project_resource_relations"):
        return
    cursor.execute("DELETE FROM cadu_project_resource_relations WHERE client_id=%s AND project_ref=%s",
                   (client_id, project_ref))
    cursor.execute("""INSERT INTO cadu_project_resource_relations
        (client_id,project_ref,source_resource_id,target_resource_id,relation_type,confidence,metadata)
        SELECT %s,%s,a.id,b.id,'possible_duplicate',1,'{}'::jsonb
          FROM cadu_project_resources a JOIN cadu_project_resources b
            ON a.client_id=b.client_id AND a.project_ref=b.project_ref
           AND a.content_hash=b.content_hash AND a.id < b.id
         WHERE a.client_id=%s AND a.project_ref=%s AND a.content_hash IS NOT NULL
           AND a.status<>'archived' AND b.status<>'archived'
        ON CONFLICT DO NOTHING""", (client_id, project_ref, client_id, project_ref))
    cursor.execute("""INSERT INTO cadu_project_resource_relations
        (client_id,project_ref,source_resource_id,target_resource_id,relation_type,confidence,metadata)
        SELECT %s,%s,report.id,plan.id,'evaluates',0.85,'{"reason":"report_to_media_plan"}'::jsonb
          FROM cadu_project_resources report CROSS JOIN cadu_project_resources plan
         WHERE report.client_id=%s AND report.project_ref=%s AND report.resource_type='report'
           AND plan.client_id=report.client_id AND plan.project_ref=report.project_ref
           AND plan.resource_type='media_plan' AND report.status<>'archived' AND plan.status<>'archived'
        ON CONFLICT DO NOTHING""", (client_id, project_ref, client_id, project_ref))
