"""Compact cross-product projection for native Cadu projects."""

from collections import defaultdict

from ..db import get_db


def _native_ids(records: list[dict]) -> list[str]:
    ids = []
    for row in records:
        ref = str(row.get("ref") or "")
        if ref.startswith("ci:"):
            ids.append(ref[3:])
    return ids


def _relation_exists(cursor, name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS available", (f"public.{name}",))
    return bool(cursor.fetchone()["available"])


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute("""SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
    ) AS available""", (table, column))
    return bool(cursor.fetchone()["available"])


def project_summaries(client_id: int, records: list[dict]) -> dict[str, dict]:
    """Return bounded counts only; detailed content remains lazy-loaded."""
    project_ids = _native_ids(records)
    summaries = defaultdict(lambda: {
        "knowledge_sources": 0, "attachments": 0, "artifacts": 0,
        "media_plans": 0, "reports": 0, "studio_images": 0,
        "studio_videos": 0,
    })
    if not project_ids:
        return summaries

    refs = [f"ci:{value}" for value in project_ids]
    for ref in refs:
        summaries[ref]  # Keep a stable zero-filled contract for empty projects.
    with get_db().cursor() as cursor:
        if (_relation_exists(cursor, "cadu_ci_projeto_arquivos")
                and _column_exists(cursor, "cadu_ci_projeto_arquivos", "purpose")):
            cursor.execute("""SELECT projeto_id::text AS project_id,
                       COUNT(*) FILTER (WHERE purpose = 'knowledge_source') AS knowledge_sources,
                       COUNT(*) FILTER (WHERE purpose = 'project_attachment') AS attachments
                  FROM cadu_ci_projeto_arquivos
                 WHERE id_cliente = %s AND projeto_id = ANY(%s::uuid[])
              GROUP BY projeto_id""", (client_id, project_ids))
            for row in cursor.fetchall():
                summary = summaries[f"ci:{row['project_id']}"]
                summary["knowledge_sources"] = int(row["knowledge_sources"] or 0)
                summary["attachments"] = int(row["attachments"] or 0)

        for table, field in (
            ("cadu_workspace_artifacts", "artifacts"),
            ("cadu_planner_plans", "media_plans"),
            ("cadu_connect_report_workspaces", "reports"),
        ):
            if not _relation_exists(cursor, table):
                continue
            extra = " AND archived_at IS NULL" if table == "cadu_planner_plans" else ""
            cursor.execute(f"""SELECT project_ref, COUNT(*) AS total FROM {table}
                                WHERE client_id = %s AND project_ref = ANY(%s){extra}
                             GROUP BY project_ref""", (client_id, refs))
            for row in cursor.fetchall():
                summaries[row["project_ref"]][field] = int(row["total"])

        if _relation_exists(cursor, "cx_studio_projects") and _relation_exists(cursor, "cx_studio_project_items"):
            cursor.execute("""SELECT 'ci:' || sp.document->>'external_project_id' AS project_ref,
                       COUNT(*) FILTER (WHERE item.kind = 'image') AS studio_images,
                       COUNT(*) FILTER (WHERE item.kind = 'video') AS studio_videos
                  FROM cx_studio_projects sp
             LEFT JOIN cx_studio_project_items item ON item.project_id = sp.id
                 WHERE sp.client_id = %s
                   AND sp.document->>'external_project_id' = ANY(%s)
              GROUP BY sp.document->>'external_project_id'""", (client_id, project_ids))
            for row in cursor.fetchall():
                summary = summaries[row["project_ref"]]
                summary["studio_images"] = int(row["studio_images"] or 0)
                summary["studio_videos"] = int(row["studio_videos"] or 0)
    return summaries


def attach_summaries(client_id: int, records: list[dict]) -> list[dict]:
    summaries = project_summaries(client_id, records)
    return [dict(row, summary=dict(summaries.get(str(row.get("ref") or ""), {}))) for row in records]
