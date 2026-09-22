"""Durable, owner-scoped pending turns for Conversations V2."""

from uuid import uuid4

from psycopg.types.json import Json

from ...cadu_family import repository

MAX_ITEMS = 5
MODES = {"fast", "analysis", "agentic"}


def _owned(conversation_id, current):
    return repository.rows("""SELECT id FROM cadu_conversations
        WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s
          AND status IN ('ativa','active')""",
        (conversation_id, current.user_id, current.client_id))


def list_items(conversation_id, current):
    if not _owned(conversation_id, current):
        raise ValueError("Conversa não encontrada.")
    return repository.rows("""SELECT id, prompt, execution_mode, selected_context, position,
                                      created_at, updated_at
        FROM cadu_agent_turn_queue
        WHERE conversation_id=%s AND user_id=%s AND client_id=%s
        ORDER BY position, created_at""", (conversation_id, current.user_id, current.client_id))


def create(conversation_id, current, data):
    if not _owned(conversation_id, current):
        raise ValueError("Conversa não encontrada.")
    prompt = str(data.get("prompt") or "").strip()
    mode = str(data.get("execution_mode") or "analysis")
    selected = data.get("selected_context") if isinstance(data.get("selected_context"), dict) else None
    if not prompt or len(prompt) > 20000 or mode not in MODES:
        raise ValueError("Pedido da fila inválido.")
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id FROM cadu_conversations
                WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s FOR UPDATE""",
                (conversation_id, current.user_id, current.client_id))
            cur.execute("""SELECT COUNT(*) AS total FROM cadu_agent_turn_queue
                WHERE conversation_id=%s AND user_id=%s AND client_id=%s""",
                (conversation_id, current.user_id, current.client_id))
            total = int(cur.fetchone()["total"])
            if total >= MAX_ITEMS:
                raise OverflowError("A fila já possui cinco pedidos.")
            item_id = str(uuid4())
            cur.execute("""INSERT INTO cadu_agent_turn_queue
                (id, conversation_id, user_id, client_id, position, prompt, execution_mode, selected_context)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id, prompt, execution_mode, selected_context, position, created_at, updated_at""",
                (item_id, conversation_id, current.user_id, current.client_id, total, prompt, mode, Json(selected) if selected else None))
            result = dict(cur.fetchone())
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


def replace(conversation_id, current, items):
    if not _owned(conversation_id, current):
        raise ValueError("Conversa não encontrada.")
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise ValueError("Fila inválida.")
    ids = [str(item.get("id") or "") for item in items]
    if any(not item_id for item_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("Fila inválida.")
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SET CONSTRAINTS cadu_agent_turn_queue_position DEFERRED")
            for position, item in enumerate(items):
                prompt = str(item.get("prompt") or "").strip()
                if not prompt or len(prompt) > 20000:
                    raise ValueError("Pedido da fila inválido.")
                cur.execute("""UPDATE cadu_agent_turn_queue SET position=%s, prompt=%s, updated_at=NOW()
                    WHERE id=%s AND conversation_id=%s AND user_id=%s AND client_id=%s""",
                    (position, prompt, ids[position], conversation_id, current.user_id, current.client_id))
                if cur.rowcount != 1:
                    raise ValueError("Item da fila não encontrado.")
        conn.commit()
        return list_items(conversation_id, current)
    except Exception:
        conn.rollback()
        raise


def remove(conversation_id, item_id, current):
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""DELETE FROM cadu_agent_turn_queue
                WHERE id=%s AND conversation_id=%s AND user_id=%s AND client_id=%s RETURNING id""",
                (item_id, conversation_id, current.user_id, current.client_id))
            removed = cur.fetchone()
            if not removed:
                return False
            cur.execute("""WITH ordered AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY position, created_at)-1 AS next_position
                FROM cadu_agent_turn_queue WHERE conversation_id=%s AND user_id=%s AND client_id=%s)
                UPDATE cadu_agent_turn_queue q SET position=ordered.next_position
                FROM ordered WHERE q.id=ordered.id""", (conversation_id, current.user_id, current.client_id))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
