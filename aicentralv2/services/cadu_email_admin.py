"""Consultas e ações do painel de e-mails do CentralX (/admin/emails).

Lê dois registros: ``cadu_email_log`` (sequência e envios novos) e
``cadu_workspace_email_events`` (transacionais antigos, Radar, boas-vindas),
normalizados num único formato. Ações em massa só mexem na sequência e nas
preferências; nenhuma ação envia e-mail na hora (o worker envia no próximo ciclo).
"""
from __future__ import annotations

from typing import Iterable, Optional

from .cadu_email_sequence import SEQUENCE_KEY, SEQUENCE_STEPS, enroll_contact, set_opt_out

PAGE_SIZE = 50
STATUS_LABELS = {
    "sent": "Enviado", "delivered": "Entregue", "opened": "Aberto", "clicked": "Clicou",
    "failed": "Falhou", "bounced": "Devolvido", "complained": "Spam", "unsubscribed": "Descadastrou",
    "skipped": "Ignorado", "deferred": "Adiado",
}
SEQUENCE_STATUS_LABELS = {"active": "Ativa", "paused": "Pausada", "completed": "Concluída", "cancelled": "Cancelada"}
ACTIONS = {
    "pause": "Pausar", "resume": "Retomar", "send_now": "Enviar o próximo agora",
    "skip": "Pular o próximo passo", "restart": "Recomeçar do passo 1", "cancel": "Cancelar a sequência",
    "unsubscribe": "Descadastrar", "resubscribe": "Reativar dicas", "enroll": "Inscrever na sequência",
}


def _db():
    from ..db import get_db
    return get_db()


def tables_ready() -> dict:
    with _db().cursor() as cursor:
        cursor.execute("""SELECT to_regclass('public.cadu_email_log') IS NOT NULL AS log,
                                 to_regclass('public.cadu_email_sequence_state') IS NOT NULL AS seq,
                                 to_regclass('public.cadu_workspace_email_events') IS NOT NULL AS legacy""")
        row = cursor.fetchone() or {}
    return {"log": bool(row.get("log")), "seq": bool(row.get("seq")), "legacy": bool(row.get("legacy"))}


def _events_union(ready: dict) -> Optional[str]:
    parts = []
    if ready["log"]:
        parts.append("""SELECT 'log' AS source, l.id, l.contato_id, l.id_cliente, l.recipient_email, l.kind, l.event_type,
                               l.step, l.subject, l.status, l.provider_error, l.sent_at, l.last_event_at,
                               l.open_count, l.click_count
                          FROM cadu_email_log l""")
    if ready["legacy"]:
        parts.append("""SELECT 'transacional' AS source, w.id, NULL::integer AS contato_id, w.id_cliente, w.recipient_email,
                               'transactional' AS kind, w.event_type, NULL::integer AS step, w.subject, w.status,
                               w.provider_error, w.created_at AS sent_at, w.last_event_at, 0 AS open_count, 0 AS click_count
                          FROM cadu_workspace_email_events w""")
    return " UNION ALL ".join(parts) if parts else None


def overview(days: int = 7) -> dict:
    ready = tables_ready()
    data = {"ready": ready, "days": days, "by_status": {}, "total": 0, "funnel": [], "sequence": {}, "opt_outs": 0}
    union = _events_union(ready)
    with _db().cursor() as cursor:
        if union:
            cursor.execute(f"""SELECT status, COUNT(*) AS n FROM ({union}) e
                                WHERE e.sent_at >= NOW() - (%s || ' days')::interval GROUP BY status""", (str(int(days)),))
            data["by_status"] = {r["status"]: int(r["n"]) for r in cursor.fetchall()}
            data["total"] = sum(data["by_status"].values())
        if ready["seq"]:
            cursor.execute("""SELECT status, COUNT(*) AS n FROM cadu_email_sequence_state
                               WHERE sequence_key = %s GROUP BY status""", (SEQUENCE_KEY,))
            data["sequence"] = {r["status"]: int(r["n"]) for r in cursor.fetchall()}
            cursor.execute("""SELECT next_step, COUNT(*) AS n FROM cadu_email_sequence_state
                               WHERE sequence_key = %s AND status = 'active' GROUP BY next_step""", (SEQUENCE_KEY,))
            waiting = {int(r["next_step"]): int(r["n"]) for r in cursor.fetchall()}
            data["funnel"] = [{"step": i, "model": key, "waiting": waiting.get(i, 0)}
                              for i, key in enumerate(SEQUENCE_STEPS, 1)]
            cursor.execute("SELECT COUNT(*) AS n FROM cadu_email_preferences WHERE marketing_opt_out")
            data["opt_outs"] = int((cursor.fetchone() or {}).get("n") or 0)
    sent = data["total"] or 0
    failed = sum(data["by_status"].get(k, 0) for k in ("failed", "bounced", "complained"))
    data["failure_rate"] = round(100 * failed / sent, 1) if sent else 0.0
    return data


def list_events(*, q: str = "", status: str = "", kind: str = "", days: int = 30, page: int = 1) -> dict:
    ready = tables_ready()
    union = _events_union(ready)
    if not union:
        return {"ready": ready, "rows": [], "total": 0, "page": 1, "pages": 1}
    where, params = ["e.sent_at >= NOW() - (%s || ' days')::interval"], [str(int(days))]
    if q:
        where.append("(e.recipient_email ILIKE %s OR e.subject ILIKE %s OR e.event_type ILIKE %s)")
        params += [f"%{q}%"] * 3
    if status:
        where.append("e.status = %s"); params.append(status)
    if kind:
        where.append("e.kind = %s"); params.append(kind)
    clause = " AND ".join(where)
    page = max(1, int(page))
    with _db().cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS n FROM ({union}) e WHERE {clause}", params)
        total = int((cursor.fetchone() or {}).get("n") or 0)
        cursor.execute(f"""SELECT e.*, c.nome_completo, c.id_contato_cliente AS contact_ref
                             FROM ({union}) e
                        LEFT JOIN tbl_contato_cliente c ON LOWER(c.email) = LOWER(e.recipient_email)
                            WHERE {clause} ORDER BY e.sent_at DESC LIMIT %s OFFSET %s""",
                       [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE])
        rows = [dict(r) for r in cursor.fetchall()]
    return {"ready": ready, "rows": rows, "total": total, "page": page, "pages": max(1, -(-total // PAGE_SIZE))}


def _sequence_filter(q: str, status: str, step: str) -> tuple[str, list]:
    where, params = ["s.sequence_key = %s"], [SEQUENCE_KEY]
    if q:
        where.append("(c.email ILIKE %s OR c.nome_completo ILIKE %s)"); params += [f"%{q}%"] * 2
    if status:
        where.append("s.status = %s"); params.append(status)
    if step:
        where.append("s.next_step = %s"); params.append(int(step))
    return " AND ".join(where), params


def list_sequence(*, q: str = "", status: str = "", step: str = "", page: int = 1) -> dict:
    ready = tables_ready()
    if not ready["seq"]:
        return {"ready": ready, "rows": [], "total": 0, "page": 1, "pages": 1}
    clause, params = _sequence_filter(q, status, step)
    page = max(1, int(page))
    base = f"""FROM cadu_email_sequence_state s
               JOIN tbl_contato_cliente c ON c.id_contato_cliente = s.contato_id
          LEFT JOIN cadu_email_preferences p ON p.contato_id = s.contato_id
              WHERE {clause}"""
    with _db().cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS n {base}", params)
        total = int((cursor.fetchone() or {}).get("n") or 0)
        cursor.execute(f"""SELECT s.*, c.nome_completo, c.email, COALESCE(p.marketing_opt_out, FALSE) AS opt_out,
                                  (SELECT MAX(l.sent_at) FROM cadu_email_log l WHERE l.contato_id = s.contato_id) AS last_sent_at
                             {base} ORDER BY s.next_send_at NULLS LAST, s.id LIMIT %s OFFSET %s""",
                       [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE])
        rows = [dict(r) for r in cursor.fetchall()]
    return {"ready": ready, "rows": rows, "total": total, "page": page, "pages": max(1, -(-total // PAGE_SIZE))}


def user_history(contato_id: int) -> Optional[dict]:
    ready = tables_ready()
    with _db().cursor() as cursor:
        cursor.execute("""SELECT id_contato_cliente AS id, nome_completo, email, pk_id_tbl_cliente AS client_id, status
                            FROM tbl_contato_cliente WHERE id_contato_cliente = %s""", (contato_id,))
        contact = cursor.fetchone()
        if not contact:
            return None
        contact = dict(contact)
        state = prefs = None
        if ready["seq"]:
            cursor.execute("SELECT * FROM cadu_email_sequence_state WHERE contato_id = %s AND sequence_key = %s",
                           (contato_id, SEQUENCE_KEY))
            state = cursor.fetchone()
            cursor.execute("SELECT * FROM cadu_email_preferences WHERE contato_id = %s", (contato_id,))
            prefs = cursor.fetchone()
        events = []
        union = _events_union(ready)
        if union:
            cursor.execute(f"""SELECT e.* FROM ({union}) e
                                WHERE e.contato_id = %s OR LOWER(e.recipient_email) = LOWER(%s)
                                ORDER BY e.sent_at DESC LIMIT 200""", (contato_id, contact["email"] or ""))
            events = [dict(r) for r in cursor.fetchall()]
    return {"ready": ready, "contact": contact, "state": dict(state) if state else None,
            "prefs": dict(prefs) if prefs else None, "events": events}


def resolve_targets(*, contato_ids: Iterable = (), filters: Optional[dict] = None) -> list[int]:
    """IDs explícitos, ou todos os contatos que casam com o filtro da aba Sequência."""
    if filters is not None:
        clause, params = _sequence_filter(filters.get("q", ""), filters.get("status", ""), filters.get("step", ""))
        with _db().cursor() as cursor:
            cursor.execute(f"""SELECT s.contato_id FROM cadu_email_sequence_state s
                                 JOIN tbl_contato_cliente c ON c.id_contato_cliente = s.contato_id
                                WHERE {clause}""", params)
            return [int(r["contato_id"]) for r in cursor.fetchall()]
    ids = []
    for value in contato_ids or ():
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(ids))


_STATE_UPDATES = {
    "pause": ("status = 'paused', paused_reason = 'admin', next_send_at = NULL", "status = 'active'"),
    "resume": ("status = 'active', paused_reason = NULL, attempts = 0, next_send_at = COALESCE(next_send_at, NOW())",
               "status = 'paused'"),
    "send_now": ("next_send_at = NOW()", "status = 'active'"),
    "skip": (f"next_step = next_step + 1, status = CASE WHEN next_step + 1 > {len(SEQUENCE_STEPS)} THEN 'completed' ELSE status END",
             "status IN ('active', 'paused')"),
    "restart": ("next_step = 1, status = 'active', attempts = 0, paused_reason = NULL, next_send_at = NOW() + INTERVAL '1 hour'",
                "TRUE"),
    "cancel": ("status = 'cancelled', paused_reason = 'admin', next_send_at = NULL", "status IN ('active', 'paused')"),
}


def apply_action(action: str, contato_ids: list[int]) -> int:
    """Aplica a ação a cada contato e devolve quantos foram afetados."""
    if action not in ACTIONS:
        raise ValueError("Ação desconhecida.")
    if not contato_ids:
        return 0
    if action == "unsubscribe":
        for contato_id in contato_ids:
            set_opt_out(contato_id, "admin")
        return len(contato_ids)
    if action == "resubscribe":
        for contato_id in contato_ids:
            set_opt_out(contato_id, "admin", opted_out=False)
        return len(contato_ids)
    if action == "enroll":
        return sum(1 for contato_id in contato_ids if enroll_contact(contato_id))
    sets, guard = _STATE_UPDATES[action]
    conn = _db()
    with conn.cursor() as cursor:
        cursor.execute(f"""UPDATE cadu_email_sequence_state SET {sets}, updated_at = NOW()
                            WHERE sequence_key = %s AND contato_id = ANY(%s) AND {guard}""",
                       (SEQUENCE_KEY, list(contato_ids)))
        affected = cursor.rowcount or 0
    conn.commit()
    return affected
