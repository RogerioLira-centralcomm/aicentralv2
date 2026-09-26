"""Persisted planning references; catalog rows remain the single source of truth."""
from psycopg.types.json import Json
from werkzeug.exceptions import BadRequest, NotFound

from ..cadu_family import repository
from ..db import get_db
from . import catalog, places

KINDS = {"audiencias", "canais", "formatos", "interativos", "places", "portais"}


def _record(kind, resource_id):
    if kind not in KINDS:
        raise BadRequest("Tipo de seleção inválido.")
    if kind == "places":
        return places.detail(resource_id)
    if kind == "portais":
        from .portals import detail
        return detail(resource_id)
    return catalog.detail(kind, resource_id)


def list_selected(client_id, actor_id):
    available = repository.rows("SELECT to_regclass('public.cadu_planner_selections') IS NOT NULL AS available")
    if not available or not available[0]["available"]:
        return []
    return repository.rows('''SELECT kind, resource_id, snapshot, created_at
                                FROM cadu_planner_selections
                               WHERE client_id=%s AND actor_id=%s ORDER BY kind, created_at DESC''', (client_id, actor_id))


def toggle(client_id, actor_id, payload):
    available = repository.rows("SELECT to_regclass('public.cadu_planner_selections') IS NOT NULL AS available")
    if not available or not available[0]["available"]:
        raise BadRequest("As seleções serão habilitadas após a atualização do Planner.")
    kind, resource_id = str(payload.get("kind") or ""), str(payload.get("resource_id") or "")
    record = _record(kind, resource_id)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''DELETE FROM cadu_planner_selections
                            WHERE client_id=%s AND actor_id=%s AND kind=%s AND resource_id=%s RETURNING id''',
                        (client_id, actor_id, kind, resource_id))
            removed = cur.fetchone()
            if removed:
                selected = False
            else:
                cur.execute('''INSERT INTO cadu_planner_selections
                    (client_id, actor_id, kind, resource_id, snapshot) VALUES (%s,%s,%s,%s,%s)''',
                    (client_id, actor_id, kind, resource_id, Json(record)))
                selected = True
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"selected": selected, "record": record}
