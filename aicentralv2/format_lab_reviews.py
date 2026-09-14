"""Snapshots R1–R5. Versão aprovada não é sobrescrita."""

from copy import deepcopy
from json import dumps

from .format_lab_agents.review import STATUSES, plan_rounds, snapshot

_STORE = {}


def create_revision(variant_id, payload, revision_index=1):
    key = str(variant_id or "").strip()
    if not key:
        raise ValueError("Variante inválida.")
    history = list_revisions(key)
    previous = history[-1] if history else None
    if previous and previous.get("status") in {"approved", "showcase"}:
        return dict(previous)
    record = snapshot(payload, revision_index, previous)
    record["variant_id"] = key
    record["status"] = "analysis"
    record["comment"] = str((payload or {}).get("comment") or "").strip()
    record["format_key"] = str((payload or {}).get("format_key") or record.get("payload", {}).get("format_key") or "")
    _STORE.setdefault(key, []).append(record)
    _insert_db(record, payload)
    return dict(record)


def approve_revision(variant_id, revision_index):
    return _set_status(variant_id, revision_index, "approved", {"analysis", "internal_review", "draft"})


def showcase_revision(variant_id, revision_index):
    return _set_status(variant_id, revision_index, "showcase", {"approved"})


def list_revisions(variant_id):
    key = str(variant_id or "").strip()
    loaded = _load_db(key)
    if loaded is not None:
        _STORE[key] = loaded
        return [dict(item) for item in loaded]
    return [dict(item) for item in _STORE.get(key) or []]


def planned(count):
    return plan_rounds(count)


def statuses():
    return list(STATUSES)


def clone_approved(variant_id):
    items = list_revisions(variant_id)
    approved = [item for item in items if item.get("status") in {"approved", "showcase"}]
    return deepcopy(approved[-1]) if approved else None


def _set_status(variant_id, revision_index, status, allowed_from):
    key = str(variant_id or "").strip()
    history = list_revisions(key)
    for item in history:
        if item.get("revision") != revision_index:
            continue
        if item.get("status") == status:
            return dict(item)
        if item.get("status") not in allowed_from and item.get("status") != status:
            if status == "approved" and item.get("status") == "showcase":
                return dict(item)
            if status == "showcase" and item.get("status") != "approved":
                raise ValueError("Aprove a revisão antes do showcase.")
            if status == "approved":
                item["status"] = "approved"
                _update_db(item)
                _sync_store(key, item)
                return dict(item)
            raise ValueError("Revisão não pode mudar de status.")
        item["status"] = status
        _update_db(item)
        _sync_store(key, item)
        return dict(item)
    raise ValueError("Revisão não encontrada.")


def _sync_store(key, record):
    rows = _STORE.setdefault(key, [])
    for index, item in enumerate(rows):
        if item.get("revision") == record.get("revision"):
            rows[index] = dict(record)
            return
    rows.append(dict(record))


def _conn():
    try:
        from flask import has_app_context
        if not has_app_context():
            return None
        from .db import get_db
        return get_db()
    except Exception:
        return None


def _load_db(variant_id):
    conn = _conn()
    if not conn:
        return None
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT variant_id, campaign_id, format_key, revision, focus,
                       status, snapshot, comment
                  FROM cx_format_variant_revisions
                 WHERE variant_id = %s
                 ORDER BY revision
                """,
                (variant_id,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        return [_record_from_row(row) for row in rows]
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None


def _insert_db(record, payload):
    conn = _conn()
    if not conn:
        return
    snapshot = {
        "payload": record.get("payload") or {},
        "comment": record.get("comment") or "",
        "immutable": True,
    }
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_format_variant_revisions
                    (variant_id, campaign_id, format_key, revision, focus, status, snapshot, comment)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (variant_id, revision) DO NOTHING
                """,
                (
                    record.get("variant_id"),
                    str((payload or {}).get("campaign_id") or "") or None,
                    record.get("format_key") or "",
                    record.get("revision"),
                    list(record.get("focus") or []),
                    record.get("status") or "analysis",
                    dumps(snapshot, ensure_ascii=False),
                    record.get("comment") or "",
                ),
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def _update_db(record):
    conn = _conn()
    if not conn:
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_variant_revisions
                   SET status = %s, comment = %s
                 WHERE variant_id = %s AND revision = %s
                """,
                (
                    record.get("status"),
                    record.get("comment") or "",
                    record.get("variant_id"),
                    record.get("revision"),
                ),
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def _record_from_row(row):
    snap = row.get("snapshot") or {}
    if isinstance(snap, str):
        from json import loads
        snap = loads(snap)
    payload = snap.get("payload") if isinstance(snap, dict) else {}
    return {
        "variant_id": row.get("variant_id"),
        "revision": row.get("revision"),
        "focus": list(row.get("focus") or []),
        "status": row.get("status"),
        "immutable": True,
        "comment": row.get("comment") or (snap.get("comment") if isinstance(snap, dict) else "") or "",
        "payload": payload or snap,
        "format_key": row.get("format_key") or "",
    }
