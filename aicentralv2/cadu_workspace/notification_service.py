"""Durable Workspace notification inbox with safe rollout fallback."""
from __future__ import annotations

from uuid import UUID

from aicentralv2.db import get_db


def _available(cursor) -> bool:
    cursor.execute("SELECT to_regclass('public.cadu_workspace_notifications') IS NOT NULL AS available")
    return bool(cursor.fetchone()['available'])


def list_notifications(client_id: int, user_id: int, *, project_ref: str | None = None, limit: int = 60) -> dict:
    try:
        with get_db().cursor() as cursor:
            if not _available(cursor):
                return {'available': False, 'items': [], 'unread': 0}
            params = [client_id, user_id]
            project_clause = ''
            if project_ref:
                project_clause = ' AND (project_ref = %s OR project_ref IS NULL)'
                params.append(project_ref)
            params.append(max(1, min(int(limit), 100)))
            cursor.execute(
                f"""SELECT id::text, project_ref, brand_ref, conversation_id, run_id::text,
                           long_job_id::text, source_id, notification_type, status, title, detail,
                           action_payload, created_at, updated_at, read_at
                      FROM cadu_workspace_notifications
                     WHERE client_id = %s AND user_id = %s AND archived_at IS NULL
                           {project_clause}
                  ORDER BY CASE WHEN status = 'waiting_user' THEN 0 WHEN status = 'failed' THEN 1 ELSE 2 END,
                           created_at DESC LIMIT %s""",
                tuple(params),
            )
            items = [dict(row) for row in cursor.fetchall()]
            return {'available': True, 'items': items,
                    'unread': sum(1 for item in items if item.get('status') in {'unread', 'waiting_user', 'failed'})}
    except Exception:
        return {'available': False, 'items': [], 'unread': 0}


def update_notification(client_id: int, user_id: int, notification_id: str, action: str) -> bool:
    UUID(str(notification_id))
    assignments = {
        'read': "status = CASE WHEN status = 'unread' THEN 'read' ELSE status END, read_at = COALESCE(read_at, NOW())",
        'resolve': "status = 'resolved', resolved_at = NOW(), read_at = COALESCE(read_at, NOW())",
        'archive': "status = 'archived', archived_at = NOW(), read_at = COALESCE(read_at, NOW())",
    }
    if action not in assignments:
        raise ValueError('Ação de notificação inválida.')
    connection = get_db()
    with connection.cursor() as cursor:
        if not _available(cursor):
            return False
        cursor.execute(
            f"""UPDATE cadu_workspace_notifications SET {assignments[action]}, updated_at = NOW()
                  WHERE id = %s AND client_id = %s AND user_id = %s AND archived_at IS NULL""",
            (notification_id, client_id, user_id),
        )
        changed = cursor.rowcount > 0
    connection.commit()
    return changed
