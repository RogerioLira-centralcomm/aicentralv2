"""Reports associated with a Workspace project: campaigns, sites, flows and user reports."""

from __future__ import annotations

from ..db import get_db

# kind -> (table, link column, title column, Reports route)
LINKABLE = {
    "campaign": ("cadu_reports_campaigns", "campaign_id", "name", "campaigns"),
    "site": ("cadu_reports_supertag_sites", "site_id", "label", "supertag/sites"),
    "flow": ("cadu_reports_flow_registry", "flow_id", "name", "flows"),
}


def _relation(cursor, table: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) IS NOT NULL AS available", (f"public.{table}",))
    return bool(cursor.fetchone()["available"])


def _href(kind: str, route: str, client_id: int, resource_id: str) -> str:
    if kind == "campaign":
        return f"/connect/app/{route}?client_id={client_id}&campaign_id={resource_id}"
    return f"/connect/app/{route}/{resource_id}?client_id={client_id}"


def list_project_reports(client_id: int, project_ref: str, reports_url: str) -> dict:
    """Return linked items by kind plus candidates that can still be linked."""
    result = {"linked": {kind: [] for kind in LINKABLE}, "available": {kind: [] for kind in LINKABLE},
              "reports": [], "available_module": False}
    with get_db().cursor() as cursor:
        if not _relation(cursor, "cadu_reports_workspace_links"):
            return result
        result["available_module"] = True
        for kind, (table, column, title_column, route) in LINKABLE.items():
            cursor.execute(f"""SELECT r.id::text AS id, r.{title_column} AS title,
                                      (l.project_ref IS NOT NULL) AS linked
                                 FROM {table} r
                                 LEFT JOIN cadu_reports_workspace_links l
                                   ON l.{column}=r.id AND l.client_id=r.client_id AND l.project_ref=%s
                                WHERE r.client_id=%s
                                ORDER BY (l.project_ref IS NOT NULL) DESC, lower(r.{title_column}) LIMIT 300""",
                           (project_ref, client_id))
            for row in cursor.fetchall():
                item = {"id": row["id"], "kind": kind, "title": row["title"] or "Sem nome"}
                if row["linked"]:
                    item["href"] = _href(kind, route, client_id, row["id"])
                    result["linked"][kind].append(item)
                else:
                    result["available"][kind].append(item)
        if _relation(cursor, "cadu_connect_report_workspaces"):
            cursor.execute("""SELECT id::text AS id, campaign_name AS title, revision, updated_at
                                FROM cadu_connect_report_workspaces
                               WHERE client_id=%s AND project_ref=%s ORDER BY updated_at DESC LIMIT 100""",
                           (client_id, project_ref))
            result["reports"] = [{"id": row["id"], "kind": "report", "title": row["title"] or "Relatório",
                                  "revision": row["revision"], "updatedAt": row["updated_at"],
                                  "href": reports_url} for row in cursor.fetchall()]
    return result


def set_link(client_id: int, project_ref: str, user_id: int, kind: str, resource_id: str, linked: bool) -> bool:
    """Link or unlink one Reports item. Returns False when the item is not in this tenant."""
    if kind not in LINKABLE:
        raise ValueError("Tipo de relatório inválido.")
    table, column, _title, _route = LINKABLE[kind]
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT 1 AS ok FROM {table} WHERE client_id=%s AND id::text=%s", (client_id, resource_id))
            if not cursor.fetchone():
                return False
            if linked:
                cursor.execute(f"""INSERT INTO cadu_reports_workspace_links(client_id,{column},project_ref,created_by)
                                   SELECT %s, id, %s, %s FROM {table} WHERE client_id=%s AND id::text=%s
                                   ON CONFLICT DO NOTHING""", (client_id, project_ref, user_id, client_id, resource_id))
            else:
                cursor.execute(f"""DELETE FROM cadu_reports_workspace_links
                                    WHERE client_id=%s AND project_ref=%s AND {column}::text=%s""",
                               (client_id, project_ref, resource_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return True
