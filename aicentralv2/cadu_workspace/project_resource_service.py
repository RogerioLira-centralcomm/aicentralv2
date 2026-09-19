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
        cursor.execute(f"""SELECT id, nome_arquivo, mime, storage_path, indexing_status, {purpose}, {category}, {metadata},
                                   criado_por, created_at, updated_at
                              FROM cadu_ci_projeto_arquivos
                             WHERE id_cliente=%s AND projeto_id=%s""", (client_id, project_id))
        for row in cursor.fetchall():
            records.append(_record("workspace", f"file:{row['id']}", "file", row["nome_arquivo"],
                mime_type=row.get("mime"), purpose=row.get("purpose"), category=row.get("category"),
                status=row.get("indexing_status"), content_hash=(row.get("classification_metadata") or {}).get("sha256"),
                locator=row.get("storage_path"), created_by=row.get("criado_por"),
                source_created_at=row.get("created_at"), source_updated_at=row.get("updated_at")))

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
                resource_id = str(uuid5(NAMESPACE_URL, f"cadu:{client_id}:{project_ref}:{item['source_system']}:{item['source_id']}"))
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
    counts = Counter(item["resource_type"] for item in resources)
    hashes = Counter(item["content_hash"] for item in resources if item.get("content_hash"))
    for item in resources:
        item["possible_duplicate"] = bool(item.get("content_hash") and hashes[item["content_hash"]] > 1)
    return {"resources": resources, "summary": {
        "total": len(resources), "possible_duplicates": sum(1 for item in resources if item["possible_duplicate"]),
        **dict(counts),
    }}


def list_for_context(context: RequestContext) -> dict:
    return list_resources(context.client_id, context.project_ref or "", actor_id=context.user_id)
