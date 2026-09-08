"""Persistência de conversas e chamadas do Agente CentralX."""

import json

from .. import db


class AgentStorageUnavailable(RuntimeError):
    pass


REQUIRED_COLUMNS = {
    "agent_conversations": {
        "id", "user_id", "title", "context_module", "context_screen",
        "context_entity_type", "context_entity_id", "context_entity_label",
        "created_at", "updated_at",
    },
    "agent_messages": {
        "id", "conversation_id", "role", "content", "display_payload",
        "model", "prompt_tokens", "completion_tokens", "created_at",
    },
    "agent_tool_calls": {
        "id", "conversation_id", "message_id", "tool_name", "operation_type",
        "arguments_sanitized", "result_summary", "status", "duration_ms",
        "request_id", "created_at",
    },
}


def _ensure_tables():
    conn = db.get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (list(REQUIRED_COLUMNS),),
        )
        rows = cur.fetchall() or []
    found = {table: set() for table in REQUIRED_COLUMNS}
    for row in rows:
        found.setdefault(row.get("table_name"), set()).add(row.get("column_name"))
    missing = {
        table: sorted(columns - found.get(table, set()))
        for table, columns in REQUIRED_COLUMNS.items()
        if columns - found.get(table, set())
    }
    if missing:
        raise AgentStorageUnavailable(
            "Schema do agente incompleto; execute upgrade_agent_tables_20260908.sql. "
            f"Ausências: {missing}"
        )


def rollback_failed_transaction():
    """Libera a conexão após uma consulta de tool falhar no PostgreSQL."""
    try:
        conn = db.get_db()
        if not conn.closed:
            conn.rollback()
    except Exception:
        pass


def list_conversations(user_id, limit=30, page=1):
    _ensure_tables()
    conn = db.get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, context_module, context_screen, context_entity_type,
                   context_entity_id, context_entity_label, created_at, updated_at
            FROM agent_conversations
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
            """,
            (
                user_id,
                max(1, min(int(limit or 30), 100)),
                (max(1, int(page or 1)) - 1) * max(1, min(int(limit or 30), 100)),
            ),
        )
        return cur.fetchall() or []


def create_conversation(user_id, context=None, title=None):
    _ensure_tables()
    context = context or {}
    conn = db.get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_conversations (
                user_id, title, context_module, context_screen,
                context_entity_type, context_entity_id, context_entity_label
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                user_id,
                (title or "Nova conversa")[:160],
                context.get("module"),
                context.get("screen"),
                context.get("entity_type"),
                str(context.get("entity_id") or "") or None,
                (context.get("entity_label") or "")[:200] or None,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return row


def get_conversation(conversation_id, user_id):
    _ensure_tables()
    conn = db.get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM agent_conversations WHERE id = %s AND user_id = %s",
            (conversation_id, user_id),
        )
        conversation = cur.fetchone()
        if not conversation:
            return None
        cur.execute(
            """
            SELECT id, role, content, display_payload, model,
                   prompt_tokens, completion_tokens, created_at
            FROM agent_messages
            WHERE conversation_id = %s
            ORDER BY created_at, id
            """,
            (conversation_id,),
        )
        messages = cur.fetchall() or []
    return {"conversation": conversation, "messages": messages}


def add_message(conversation_id, user_id, role, content, display=None, model=None, usage=None):
    owned = get_conversation(conversation_id, user_id)
    if not owned:
        return None
    usage = usage or {}
    conn = db.get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_messages (
                conversation_id, role, content, display_payload, model,
                prompt_tokens, completion_tokens
            ) VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
            RETURNING *
            """,
            (
                conversation_id, role, content,
                json.dumps(display or {}, ensure_ascii=False, default=str),
                model, usage.get("prompt_tokens"), usage.get("completion_tokens"),
            ),
        )
        row = cur.fetchone()
        if role == "user":
            title = content.strip().replace("\n", " ")[:70]
            cur.execute(
                """
                UPDATE agent_conversations
                SET updated_at = NOW(),
                    title = CASE WHEN title = 'Nova conversa' THEN %s ELSE title END
                WHERE id = %s AND user_id = %s
                """,
                (title, conversation_id, user_id),
            )
        else:
            cur.execute(
                """
                UPDATE agent_conversations
                SET updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )
    conn.commit()
    return row


def recent_messages(conversation_id, user_id, limit=12):
    owned = get_conversation(conversation_id, user_id)
    if not owned:
        return None
    return owned["messages"][-max(1, min(int(limit or 12), 20)):]


def record_tool_call(
    conversation_id, message_id, tool_name, arguments, result,
    status, duration_ms, request_id,
):
    _ensure_tables()
    conn = db.get_db()
    summary = {
        "success": bool(result.get("success")) if isinstance(result, dict) else False,
        "count": ((result.get("metadata") or {}).get("count") if isinstance(result, dict) else None),
        "error": (result.get("error") if isinstance(result, dict) else None),
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_tool_calls (
                conversation_id, message_id, tool_name, operation_type,
                arguments_sanitized, result_summary, status, duration_ms, request_id
            ) VALUES (%s, %s, %s, 'read', %s::jsonb, %s::jsonb, %s, %s, %s)
            RETURNING id
            """,
            (
                conversation_id, message_id, tool_name,
                json.dumps(arguments or {}, ensure_ascii=False, default=str),
                json.dumps(summary, ensure_ascii=False, default=str),
                status, duration_ms, request_id,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return row


def count_recent_user_messages(user_id, minutes=5):
    _ensure_tables()
    conn = db.get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM agent_messages m
            JOIN agent_conversations c ON c.id = m.conversation_id
            WHERE c.user_id = %s
              AND m.role = 'user'
              AND m.created_at >= NOW() - (%s * INTERVAL '1 minute')
            """,
            (user_id, minutes),
        )
        row = cur.fetchone() or {}
    return int(row.get("total") or 0)
