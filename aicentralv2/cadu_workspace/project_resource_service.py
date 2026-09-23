"""Canonical project resource registry shared by the UI and MCP."""

from __future__ import annotations

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
    purpose = values.get("purpose") or "project_resource"
    status = values.get("status") or "active"
    metadata = values.get("metadata") or {}
    return {
        "source_system": source_system, "source_id": str(source_id),
        "resource_type": resource_type, "title": str(title or RESOURCE_TYPES.get(resource_type, "Recurso"))[:500],
        "mime_type": values.get("mime_type"), "purpose": purpose,
        "category": values.get("category") or "other", "status": status,
        "version": max(1, int(values.get("version") or 1)), "content_hash": values.get("content_hash"),
        "locator": values.get("locator"), "metadata": metadata,
        "permission_snapshot": values.get("permission_snapshot") or {},
        "capability_snapshot": values.get("capability_snapshot") or {},
        "index_status": values.get("index_status") or ("indexed" if purpose == "knowledge_source" and status in {"completed", "indexed"} else "not_requested"),
        "ocr_status": values.get("ocr_status") or metadata.get("ocr_status") or "not_requested",
        "embedding_status": values.get("embedding_status") or ("ready" if purpose == "knowledge_source" and status in {"completed", "indexed"} else "not_requested"),
        "created_by": values.get("created_by"), "source_created_at": values.get("source_created_at"),
        "source_updated_at": values.get("source_updated_at") or values.get("source_created_at"),
    }


def public_link_icon(metadata: dict | None) -> dict:
    """Stable icon contract; never expose prompts, job IDs or worker errors."""
    data = metadata if isinstance(metadata, dict) else {}
    status = str(data.get("icon_status") or "missing")
    if status not in {"missing", "queued", "running", "generating", "ready", "failed"}:
        status = "missing"
    url = str(data.get("icon_url") or "") if status == "ready" else ""
    if url and not (url.startswith("/static/") or url.startswith("https://")):
        url = ""
    return {"status": status, "url": url, "source": str(data.get("icon_source") or "") if url else "",
            "mime_type": "image/webp" if url.lower().split("?", 1)[0].endswith(".webp") else ""}


def _refresh_link_icons(cursor, client_id: int, project_ref: str, resources: list[dict]) -> None:
    """Overlay live icon state while the materialized registry catches up."""
    links = {str(item.get("source_id") or "")[5:]: item for item in resources
             if item.get("source_system") == "workspace" and str(item.get("source_id") or "").startswith("link:")}
    if not links or not _relation(cursor, "cadu_ci_projeto_links") or "icon_metadata" not in _columns(cursor, "cadu_ci_projeto_links"):
        return
    cursor.execute("""SELECT id::text AS id, icon_metadata FROM cadu_ci_projeto_links
                       WHERE id_cliente=%s AND projeto_id=%s AND id::text=ANY(%s)""",
                   (client_id, _project_id(project_ref), list(links)))
    for row in cursor.fetchall():
        item = links.get(str(row["id"]))
        if item is not None:
            item["metadata"] = {**(item.get("metadata") or {}), "icon": public_link_icon(row.get("icon_metadata"))}


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
                             AS a WHERE a.id_cliente=%s AND a.projeto_id=%s
                               AND a.indexing_status <> 'superseded'""", (client_id, project_id))
        for row in cursor.fetchall():
            classification_metadata = row.get("classification_metadata") or {}
            records.append(_record("workspace", f"file:{row['id']}", "file",
                classification_metadata.get("display_title") or row["nome_arquivo"],
                mime_type=row.get("mime"), purpose=row.get("purpose"), category=row.get("category"),
                status=row.get("indexing_status"), content_hash=classification_metadata.get("sha256"),
                locator=row.get("storage_path"), created_by=row.get("criado_por"),
                source_created_at=row.get("created_at"), source_updated_at=row.get("updated_at"),
                metadata={"chunk_count": int(row.get("chunk_count") or 0),
                          "indexing_status": row.get("indexing_status"),
                          "original_name": row.get("nome_arquivo"),
                          "description": classification_metadata.get("description"),
                          "tags": classification_metadata.get("tags") or []}))

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

    external_locators = set()
    if _relation(cursor, "cadu_workspace_external_references"):
        external_columns = _columns(cursor, "cadu_workspace_external_references")
        archived_sql = "archived_at" if "archived_at" in external_columns else "NULL::timestamptz AS archived_at"
        cursor.execute(f"""SELECT id::text AS id,provider,external_id,locator,connection_ref,
                                  reference_type,sync_status,metadata,last_synced_at,created_at,updated_at,{archived_sql}
                             FROM cadu_workspace_external_references
                            WHERE client_id=%s AND project_ref=%s""", (client_id, project_ref))
        for row in cursor.fetchall():
            metadata = row.get("metadata") or {}
            external_locators.add(str(row.get("locator") or ""))
            if row.get("archived_at"):
                continue
            records.append(_record(
                "external_reference", row["id"], "link",
                metadata.get("title") or metadata.get("platform") or row.get("provider") or "Recurso externo",
                category=metadata.get("resource_kind") or row.get("reference_type") or "reference",
                locator=row.get("locator"), metadata={
                    "provider": row.get("provider"), "platform": metadata.get("platform") or row.get("provider"),
                    "resource_kind": metadata.get("resource_kind") or row.get("reference_type") or "web_page",
                    "external_id": row.get("external_id"), "description": metadata.get("description"),
                    "tags": metadata.get("tags") or [], "connection_ref": row.get("connection_ref"),
                    "sync_status": row.get("sync_status"), "access_type": metadata.get("access_type"),
                    "connector_recommended": bool(metadata.get("connector_recommended")),
                    "meeting": metadata.get("meeting"),
                    "user_message": metadata.get("user_message"),
                    "context_summary": metadata.get("context_summary"),
                    "project_item_kind": metadata.get("project_item_kind") or "reference",
                    "timeline": metadata.get("timeline"), "origin": metadata.get("origin"),
                    "last_synced_at": row.get("last_synced_at"),
                }, capability_snapshot=metadata.get("capabilities") or {},
                permission_snapshot=metadata.get("permissions") or {},
                source_created_at=row.get("created_at"), source_updated_at=row.get("updated_at"),
            ))

    if _relation(cursor, "cadu_ci_projeto_links"):
        columns = _columns(cursor, "cadu_ci_projeto_links")
        icon_sql = "icon_metadata" if "icon_metadata" in columns else "'{}'::jsonb AS icon_metadata"
        cursor.execute(f"""SELECT id::text AS id, titulo, provider, url, criado_por, created_at, updated_at, {icon_sql}
                            FROM cadu_ci_projeto_links WHERE id_cliente=%s AND projeto_id=%s""", (client_id, project_id))
        for row in cursor.fetchall():
            if str(row.get("url") or "") in external_locators:
                continue
            records.append(_record("workspace", f"link:{row['id']}", "link", row["titulo"],
                category="reference",
                locator=row.get("url"), metadata={"provider": row.get("provider"),
                    "platform": row.get("provider"), "resource_kind": "web_page",
                    "icon": public_link_icon(row.get("icon_metadata"))}, created_by=row.get("criado_por"),
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


def reconcile(client_id: int, project_ref: str, actor_id=None, *, include_archived=False) -> dict:
    project_id = _project_id(project_ref)
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM cadu_ci_projetos WHERE id=%s AND id_cliente=%s", (project_id, client_id))
            if not cursor.fetchone():
                raise ValueError("Projeto indisponível.")
            if not _relation(cursor, "cadu_project_resources"):
                return {"available": False, "resources": [], "summary": {}}
            registry_columns = _columns(cursor, "cadu_project_resources")
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
                state_columns = {
                    "permission_snapshot", "capability_snapshot", "index_status",
                    "ocr_status", "embedding_status",
                } & registry_columns
                if state_columns:
                    assignments = ", ".join(f"{column}=%s" for column in sorted(state_columns))
                    state_values = []
                    for column in sorted(state_columns):
                        value = item[column]
                        state_values.append(Json(value) if column.endswith("_snapshot") else value)
                    cursor.execute(
                        f"UPDATE cadu_project_resources SET {assignments} WHERE id=%s",
                        tuple(state_values) + (persisted_id,),
                    )
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
    return {"available": True, **list_resources(
        client_id, project_ref, reconcile_first=False, include_archived=include_archived,
    )}


def list_resources(client_id: int, project_ref: str, *, reconcile_first=True, actor_id=None,
                   include_archived=False) -> dict:
    if reconcile_first:
        return reconcile(client_id, project_ref, actor_id, include_archived=include_archived)
    with get_db().cursor() as cursor:
        if not _relation(cursor, "cadu_project_resources"):
            return {"resources": [], "summary": {}}
        columns = _columns(cursor, "cadu_project_resources")
        optional = [column for column in (
            "permission_snapshot", "capability_snapshot", "index_status",
            "ocr_status", "embedding_status", "deleted_at",
        ) if column in columns]
        optional_sql = ", " + ", ".join(optional) if optional else ""
        status_filter = "" if include_archived else " AND status <> 'archived'"
        cursor.execute(f"""SELECT id::text, source_system, source_id, resource_type, title, mime_type,
                                  purpose, category, status, version, content_hash, locator, metadata,
                                  source_created_at, source_updated_at, last_seen_at{optional_sql}
                             FROM cadu_project_resources
                            WHERE client_id=%s AND project_ref=%s{status_filter}
                         ORDER BY COALESCE(source_updated_at, source_created_at, last_seen_at) DESC, title""",
                       (client_id, project_ref))
        resources = [dict(row) for row in cursor.fetchall()]
        _refresh_link_icons(cursor, client_id, project_ref, resources)
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


def list_for_context(context: RequestContext, *, include_archived=False) -> dict:
    # MCP reads use the materialized registry. Mutations enqueue reconciliation;
    # the project-detail UI retains an explicit repair-on-open path for rollout.
    return list_resources(context.client_id, context.project_ref or "", reconcile_first=False,
                          actor_id=context.user_id, include_archived=include_archived)


def get_resource(client_id: int, project_ref: str, resource_id: str) -> dict | None:
    """Read one canonical resource without reaching back to its provider."""
    if not str(project_ref or "").startswith("ci:"):
        raise ValueError("O registro de recursos exige um projeto nativo do Cadu.")
    with get_db().cursor() as cursor:
        if not _relation(cursor, "cadu_project_resources"):
            return None
        cursor.execute(
            """SELECT * FROM cadu_project_resources
                WHERE id=%s AND client_id=%s AND project_ref=%s""",
            (str(resource_id), int(client_id), project_ref),
        )
        row = cursor.fetchone()
        result = dict(row) if row else None
        if result:
            _refresh_link_icons(cursor, client_id, project_ref, [result])
    return result


def search_resources(client_id: int, project_ref: str, query: str, *, limit: int = 20,
                     resource_type: str | None = None, include_archived=False) -> list[dict]:
    """Search canonical resource metadata within one project boundary."""
    query = " ".join(str(query or "").split()).casefold()
    if len(query) < 2:
        raise ValueError("Informe o que deve ser pesquisado nos recursos do projeto.")
    result = list_resources(
        client_id, project_ref, reconcile_first=False, include_archived=include_archived,
    ).get("resources", [])
    terms = [item for item in query.split() if item]
    if resource_type:
        result = [item for item in result if str(item.get("resource_type") or "") == resource_type]

    def matches(item: dict) -> bool:
        haystack = " ".join(
            str(item.get(key) or "") for key in
            ("title", "resource_type", "category", "purpose", "source_system", "locator")
        ).casefold()
        metadata = item.get("metadata") or {}
        haystack = f"{haystack} {json.dumps(metadata, ensure_ascii=False, default=str)}".casefold()
        return all(term in haystack for term in terms)

    return [item for item in result if matches(item)][:max(1, min(int(limit), 100))]


def resource_capabilities(resource: dict) -> dict:
    """Resolve honest edit capabilities from ownership, format and connector state."""
    source = str(resource.get("source_system") or "")
    status = str(resource.get("status") or "")
    mime = str(resource.get("mime_type") or "").lower()
    kind = str(resource.get("category") or "")
    metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
    snapshot = resource.get("capability_snapshot") if isinstance(resource.get("capability_snapshot"), dict) else {}
    provider_actions = snapshot.get("actions") if isinstance(snapshot.get("actions"), dict) else {}
    active = status not in {"archived", "deleted", "permission_lost"}
    is_google = source in {"google_drive", "google_docs", "google_sheets", "google_slides"}
    is_external_reference = source == "external_reference"
    is_artifact = source == "cadu_workspace_artifacts"
    is_studio_image = source == "studio" or (
        str(resource.get("resource_type") or "") == "image" and source.startswith("studio")
    )
    is_pdf = mime == "application/pdf" or kind == "pdf"
    is_image = mime.startswith("image/") or str(resource.get("resource_type") or "") == "image"
    text_capable = mime.startswith(("text/", "application/json")) or is_pdf
    connected = bool(metadata.get("connection_ref")) or (
        not is_external_reference and source not in {"workspace", ""}
    )
    provider_read = bool(provider_actions.get("read")) or (is_google and active) or is_artifact
    provider_write = bool(snapshot.get("write_authorized") and provider_actions.get("edit"))

    editor = None
    edit_mode = "read_only"
    native_edit = False
    if is_artifact:
        native_edit = active and kind != "link_reader"
        edit_mode = "native" if native_edit else "read_only"
        editor = "html" if kind == "html" else "document"
    elif is_studio_image:
        native_edit, edit_mode, editor = active, "native" if active else "read_only", "studio"
    elif is_image and source in {"workspace", "workspace_images"}:
        edit_mode, editor = "imported_copy", "studio"
    elif active and provider_write:
        edit_mode = "external_editable"

    can_read_content = active and (not is_external_reference or connected and provider_read)
    copyable_format = text_capable or is_image or kind in {
        "document", "spreadsheet", "presentation", "design", "drive_file", "web_page",
    }
    can_create_copy = active and copyable_format and (not is_external_reference or can_read_content)
    can_derive = active and (can_read_content or not is_external_reference)
    can_index = active and not is_external_reference and (text_capable or is_google)
    can_sync = active and connected and (is_external_reference or is_google)
    lifecycle_supported = source in {"external_reference", "cadu_workspace_artifacts"}
    metadata_fields = (
        ["title", "description", "tags"] if is_external_reference or (source == "workspace" and str(resource.get("source_id") or "").startswith("file:"))
        else ["title"] if is_artifact or (source == "workspace" and str(resource.get("source_id") or "").startswith("link:"))
        else []
    )
    limitations = []
    if not active:
        limitations.append("O recurso não está ativo na origem.")
    elif is_pdf:
        limitations.append("PDF é preservado como fonte somente leitura; alterações exigem uma entrega derivada.")
    elif is_external_reference and not connected:
        limitations.append("Sem integração autorizada, o Cadu preserva apenas a referência e não lê nem altera a origem.")
    elif (is_external_reference or is_google) and not provider_write:
        limitations.append("A integração atual não autoriza escrita na plataforma de origem.")
    return {
        "resource_id": str(resource.get("id") or ""),
        "source_system": source,
        "edit_mode": edit_mode,
        "editor": editor,
        "actions": {
            "read": can_read_content,
            "preview": active and (can_read_content or bool(resource.get("locator"))),
            "search": active and (can_index or bool(resource.get("title"))),
            "link_to_project": active,
            "index": can_index,
            "native_edit": native_edit,
            "edit_content": active and (native_edit or provider_write),
            "create_revision": native_edit and edit_mode == "native",
            "create_editable_copy": can_create_copy,
            "derive_artifact": can_derive,
            "open_in_editor": active and bool(editor),
            "sync": can_sync,
            "push_to_source": provider_write,
            "update_metadata": active and bool(metadata_fields),
            "archive": active and lifecycle_supported,
            "restore": not active and status == "archived" and lifecycle_supported,
            "move": False,
            "share": bool(provider_write and provider_actions.get("share")),
            "comments": bool(provider_write and provider_actions.get("comments")),
            "versions": bool(resource.get("version")),
            "export_pdf": bool(is_artifact or (is_google and mime != "application/pdf")),
        },
        "recommended_tool": "resources.start_image_edit"
        if editor == "studio" else (
            "artifacts.update_draft" if is_artifact and native_edit else (
                "resources.create_editable_copy" if can_create_copy else (
                    "artifacts.create_draft" if can_derive else None
                )
            )
        ),
        "editable_metadata": metadata_fields,
        "limitations": limitations,
    }


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
    cursor.execute("""DELETE FROM cadu_project_resource_relations
                        WHERE client_id=%s AND project_ref=%s
                          AND relation_type IN ('possible_duplicate','evaluates')""",
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


def relate_resources(client_id: int, project_ref: str, source_resource_id: str,
                     target_resource_id: str, relation_type: str, *, metadata=None) -> dict:
    """Persist an explicit project relation without allowing cross-tenant edges."""
    relation_type = str(relation_type or "").strip()[:40]
    if relation_type not in {"derived_from", "references", "uses", "revises", "exports"}:
        raise ValueError("Relação de recurso inválida.")
    if str(source_resource_id) == str(target_resource_id):
        raise ValueError("Um recurso não pode se relacionar consigo mesmo.")
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            if not _relation(cursor, "cadu_project_resource_relations"):
                raise ValueError("Relações de projeto indisponíveis.")
            cursor.execute("""SELECT id::text FROM cadu_project_resources
                                WHERE client_id=%s AND project_ref=%s AND id=ANY(%s::uuid[])
                                  AND status<>'archived'""",
                           (client_id, project_ref, [str(source_resource_id), str(target_resource_id)]))
            found = {str(row["id"]) for row in cursor.fetchall()}
            if found != {str(source_resource_id), str(target_resource_id)}:
                raise ValueError("Um dos recursos não pertence ao projeto selecionado.")
            cursor.execute("""INSERT INTO cadu_project_resource_relations
                (client_id,project_ref,source_resource_id,target_resource_id,relation_type,confidence,metadata)
                VALUES (%s,%s,%s,%s,%s,1,%s)
                ON CONFLICT (source_resource_id,target_resource_id,relation_type) DO UPDATE SET
                    metadata=EXCLUDED.metadata,updated_at=NOW()
                RETURNING id,relation_type""",
                (client_id, project_ref, str(source_resource_id), str(target_resource_id),
                 relation_type, Json(metadata or {})))
            row = dict(cursor.fetchone())
        connection.commit()
        return row
    except Exception:
        connection.rollback()
        raise


def list_resource_relations(client_id: int, project_ref: str, resource_id: str) -> list[dict]:
    """List both directions of one resource graph node inside its project."""
    if not str(project_ref or "").startswith("ci:"):
        raise ValueError("O registro de recursos exige um projeto nativo do Cadu.")
    with get_db().cursor() as cursor:
        if not _relation(cursor, "cadu_project_resource_relations"):
            return []
        cursor.execute("""SELECT relation.id,relation.source_resource_id::text,
                                  relation.target_resource_id::text,relation.relation_type,
                                  relation.confidence,relation.metadata,relation.created_at,
                                  source.title AS source_title,target.title AS target_title
                             FROM cadu_project_resource_relations relation
                             JOIN cadu_project_resources source ON source.id=relation.source_resource_id
                             JOIN cadu_project_resources target ON target.id=relation.target_resource_id
                            WHERE relation.client_id=%s AND relation.project_ref=%s
                              AND (relation.source_resource_id=%s OR relation.target_resource_id=%s)
                         ORDER BY relation.updated_at DESC,relation.id DESC""",
                       (client_id, project_ref, str(resource_id), str(resource_id)))
        return [dict(row) for row in cursor.fetchall()]


def update_resource_metadata(context: RequestContext, resource_id: str, changes: dict) -> dict:
    """Update the canonical source object, never the rebuildable Registry row."""
    resource = get_resource(context.client_id, context.project_ref or "", resource_id)
    if not resource:
        raise ValueError("Recurso indisponível neste projeto.")
    title = " ".join(str(changes.get("title") or "").split())[:180] if "title" in changes else None
    description = str(changes.get("description") or "").strip()[:4000] if "description" in changes else None
    tags = None
    if "tags" in changes:
        if not isinstance(changes.get("tags"), list):
            raise ValueError("As etiquetas precisam ser uma lista.")
        tags = list(dict.fromkeys(
            str(item or "").strip()[:64] for item in changes["tags"] if str(item or "").strip()
        ))[:20]
    if title is not None and not title:
        raise ValueError("O título do recurso não pode ficar vazio.")
    source, source_id = str(resource.get("source_system") or ""), str(resource.get("source_id") or "")
    connection = get_db()
    updated = False
    try:
        with connection.cursor() as cursor:
            if source == "external_reference":
                metadata = {}
                if title is not None:
                    metadata["title"] = title
                if description is not None:
                    metadata["description"] = description
                if tags is not None:
                    metadata["tags"] = tags
                cursor.execute("""UPDATE cadu_workspace_external_references
                                      SET metadata=metadata || %s,updated_at=NOW()
                                    WHERE id=%s AND client_id=%s AND project_ref=%s""",
                               (Json(metadata), source_id, context.client_id, context.project_ref))
                updated = cursor.rowcount == 1
            elif source == "cadu_workspace_artifacts":
                if title is None or description is not None or tags is not None:
                    raise ValueError("Artefatos aceitam somente alteração de título por esta ferramenta.")
                cursor.execute("""UPDATE cadu_workspace_artifacts SET title=%s,updated_at=NOW()
                                    WHERE id=%s AND client_id=%s AND project_ref=%s""",
                               (title, source_id, context.client_id, context.project_ref))
                updated = cursor.rowcount == 1
            elif source == "workspace" and source_id.startswith("link:"):
                if title is None or description is not None or tags is not None:
                    raise ValueError("Links legados aceitam somente alteração de título.")
                cursor.execute("""UPDATE cadu_ci_projeto_links SET titulo=%s,updated_at=NOW()
                                    WHERE id=%s AND id_cliente=%s AND projeto_id=%s""",
                               (title, source_id[5:], context.client_id, _project_id(context.project_ref or "")))
                updated = cursor.rowcount == 1
            elif source == "workspace" and source_id.startswith("file:"):
                metadata = {}
                if title is not None:
                    metadata["display_title"] = title
                if description is not None:
                    metadata["description"] = description
                if tags is not None:
                    metadata["tags"] = tags
                cursor.execute("""UPDATE cadu_ci_projeto_arquivos
                                      SET classification_metadata=COALESCE(classification_metadata,'{}'::jsonb) || %s,
                                          updated_at=NOW()
                                    WHERE id=%s AND id_cliente=%s AND projeto_id=%s""",
                               (Json(metadata), source_id[5:], context.client_id, _project_id(context.project_ref or "")))
                updated = cursor.rowcount == 1
            else:
                raise ValueError("A origem deste recurso ainda não permite editar metadados pelo Cadu.")
        if not updated:
            raise ValueError("Recurso indisponível para alteração.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    reconcile(context.client_id, context.project_ref or "", context.user_id)
    return get_resource(context.client_id, context.project_ref or "", resource_id) or {}


def set_resource_archived(context: RequestContext, resource_id: str, archived: bool) -> dict:
    """Archive or restore supported source objects without deleting their history."""
    resource = get_resource(context.client_id, context.project_ref or "", resource_id)
    if not resource:
        raise ValueError("Recurso indisponível neste projeto.")
    source, source_id = str(resource.get("source_system") or ""), str(resource.get("source_id") or "")
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            if source == "external_reference":
                if "archived_at" not in _columns(cursor, "cadu_workspace_external_references"):
                    raise ValueError("A migração de arquivamento de referências ainda não foi aplicada.")
                cursor.execute("""UPDATE cadu_workspace_external_references
                                      SET archived_at=CASE WHEN %s THEN NOW() ELSE NULL END,updated_at=NOW()
                                    WHERE id=%s AND client_id=%s AND project_ref=%s""",
                               (bool(archived), source_id, context.client_id, context.project_ref))
            elif source == "cadu_workspace_artifacts":
                cursor.execute("""UPDATE cadu_workspace_artifacts
                                      SET archived_from_status=CASE
                                              WHEN %s AND status<>'archived' THEN status
                                              ELSE archived_from_status END,
                                          status=CASE WHEN %s THEN 'archived'
                                              ELSE COALESCE(archived_from_status,'active') END,
                                          updated_at=NOW()
                                    WHERE id=%s AND client_id=%s AND project_ref=%s""",
                               (bool(archived), bool(archived), source_id,
                                context.client_id, context.project_ref))
            else:
                raise ValueError("A origem deste recurso ainda não oferece arquivamento recuperável.")
            if cursor.rowcount != 1:
                raise ValueError("Recurso indisponível para arquivamento.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    reconcile(context.client_id, context.project_ref or "", context.user_id)
    restored = get_resource(context.client_id, context.project_ref or "", resource_id) or {}
    return {"resource_id": str(resource_id), "archived": bool(archived),
            "status": restored.get("status") or ("archived" if archived else "active"),
            "recoverable": True}
