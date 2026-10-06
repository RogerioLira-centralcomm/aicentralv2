"""Franquia mensal do plano como lote de tokens (modelo "plano de telefonia").

Regras (decisões do dono, 2026-10-06):
- a franquia do plano é liberada automaticamente no início de cada ciclo;
- ao liberar a franquia nova, a sobra da franquia anterior expira;
- tokens extras comprados não expiram;
- o consumo debita primeiro a franquia, depois os extras.

Tudo fica atrás de ``CADU_PLAN_ALLOWANCE_ENABLED`` (default desligado) e exige
a migração ``add_cadu_credit_lot_source_v1.sql`` (colunas ``source`` e
``cycle_start`` + índice único). Sem as duas coisas, nada muda: as funções de
integração viram no-op e o ledger mantém a ordem de débito atual.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Optional

from .cadu_billing_catalog import current_cycle, cycle_anchor_day

logger = logging.getLogger(__name__)

ALLOWANCE_SOURCE = "plan_allowance"


class InsufficientAllowanceBalance(ValueError):
    pass


def allowance_enabled() -> bool:
    return os.getenv("CADU_PLAN_ALLOWANCE_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _cycle_start_of(lot: dict) -> Optional[date]:
    value = lot.get("cycle_start")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def plan_allowance_actions(*, today: date, anchor_day: int, tokens_monthly: int,
                           lots: Iterable[dict]) -> dict:
    """Decide (sem banco) o que fazer com as franquias de um cliente hoje.

    Devolve ``{"cycle": (start, end), "expire": [ids], "grant": dict | None}``.
    É idempotente: chamado de novo no mesmo ciclo, não concede nem expira nada.
    """
    start, end = current_cycle(today, anchor_day)
    allowance_lots = [dict(lot) for lot in lots or () if str(lot.get("source") or "") == ALLOWANCE_SOURCE]
    has_current = any(_cycle_start_of(lot) == start for lot in allowance_lots)
    expire = [lot["id"] for lot in allowance_lots
              if _cycle_start_of(lot) != start and str(lot.get("status") or "active") == "active"]
    grant = None
    tokens = _int(tokens_monthly)
    if not has_current and tokens > 0:
        grant = {"tokens": tokens, "cycle_start": start,
                 "expires_at": datetime.combine(end + timedelta(days=1), time.min)}
    return {"cycle": (start, end), "expire": expire, "grant": grant}


def debit_sort_key(lot: dict) -> tuple:
    """Franquia primeiro; depois quem vence antes; sem vencimento por último."""
    expires = lot.get("expires_at")
    if isinstance(expires, date) and not isinstance(expires, datetime):
        expires = datetime.combine(expires, time.min)
    purchased = lot.get("purchased_at")
    return (
        0 if str(lot.get("source") or "") == ALLOWANCE_SOURCE else 1,
        expires is None,
        expires or datetime.max,
        purchased or datetime.min,
        _int(lot.get("id")),
    )


def allocate_debit(lots: Iterable[dict], required: int) -> list[dict]:
    """Distribui ``required`` tokens entre os lotes, na ordem de débito.

    Levanta ``InsufficientAllowanceBalance`` sem alterar nada quando o saldo
    total não cobre a execução.
    """
    required = _int(required)
    ordered = sorted((dict(lot) for lot in lots or ()), key=debit_sort_key)
    available = sum(max(0, _int(lot.get("tokens_amount")) - _int(lot.get("tokens_used"))) for lot in ordered)
    if available < required:
        raise InsufficientAllowanceBalance(
            f"Saldo insuficiente: são necessários {required} tokens e há {available} disponíveis.")
    allocations, remaining = [], required
    for lot in ordered:
        if remaining <= 0:
            break
        room = max(0, _int(lot.get("tokens_amount")) - _int(lot.get("tokens_used")))
        used = min(room, remaining)
        if used:
            allocations.append({"lot_id": lot.get("id"), "tokens": used})
            remaining -= used
    return allocations


# ----------------------------------------------------------------- integração com o banco

_SOURCE_COLUMN: dict = {}


def _has_source_column(cursor) -> bool:
    if "value" not in _SOURCE_COLUMN:
        cursor.execute("""SELECT COUNT(*) AS n FROM information_schema.columns
                           WHERE table_name = 'cadu_credits_extras'
                             AND column_name IN ('source', 'cycle_start')""")
        row = cursor.fetchone() or {}
        _SOURCE_COLUMN["value"] = _int(row.get("n") if isinstance(row, dict) else row[0]) == 2
    return _SOURCE_COLUMN["value"]


def active() -> bool:
    """Chave ligada; a checagem da coluna acontece no cursor da transação."""
    return allowance_enabled()


def debit_order_sql(cursor) -> str:
    """ORDER BY usado pelo ledger; muda só com a chave ligada e a migração aplicada."""
    try:
        if allowance_enabled() and _has_source_column(cursor):
            return "ORDER BY (source = 'plan_allowance') DESC, expires_at NULLS LAST, purchased_at, id"
    except Exception:
        logger.warning("Não foi possível verificar a coluna source dos lotes", exc_info=True)
    return "ORDER BY expires_at NULLS LAST, purchased_at, id"


def _plan_tokens(plan: dict) -> int:
    from .cadu_billing_catalog import commercial_plans

    slug_matches = [item for item in commercial_plans([plan], plan) if item.get("current")]
    if slug_matches and slug_matches[0].get("tokens_monthly"):
        return _int(slug_matches[0]["tokens_monthly"])
    return _int(plan.get("tokens_monthly_limit"))


def ensure_plan_allowance(cursor, client_id: int, today: Optional[date] = None) -> Optional[dict]:
    """Libera a franquia do ciclo e expira a anterior, dentro da transação do chamador.

    No-op (devolve ``None``) com a chave desligada, sem a migração ou sem plano
    ativo. Usa SAVEPOINT para nunca abortar a transação de cobrança.
    """
    if not allowance_enabled():
        return None
    today = today or date.today()
    cursor.execute("SAVEPOINT cadu_plan_allowance")
    try:
        if not _has_source_column(cursor):
            cursor.execute("RELEASE SAVEPOINT cadu_plan_allowance")
            return None
        cursor.execute(
            """SELECT cp.id AS client_plan_id, cp.valid_from, cp.plan_start_date,
                      pd.plan_type, pd.plan_name, pd.plan_name AS plan_definition_name,
                      COALESCE(pd.tokens_monthly_limit, cp.tokens_monthly_limit, 0) AS tokens_monthly_limit
                 FROM cadu_client_plans cp
            LEFT JOIN cadu_plan_definitions pd ON pd.id = cp.id_plan_definition
                WHERE cp.id_cliente = %s AND cp.plan_status = 'active'
             ORDER BY cp.created_at DESC LIMIT 1""",
            (int(client_id),),
        )
        plan = dict(cursor.fetchone() or {})
        if not plan:
            cursor.execute("RELEASE SAVEPOINT cadu_plan_allowance")
            return None
        cursor.execute(
            """SELECT id, source, cycle_start, status FROM cadu_credits_extras
                WHERE id_cliente = %s AND source = 'plan_allowance' AND status = 'active'
                FOR UPDATE""",
            (int(client_id),),
        )
        lots = [dict(row) for row in cursor.fetchall()]
        actions = plan_allowance_actions(today=today, anchor_day=cycle_anchor_day(plan),
                                         tokens_monthly=_plan_tokens(plan), lots=lots)
        if actions["expire"]:
            cursor.execute(
                "UPDATE cadu_credits_extras SET status = 'expired' WHERE id = ANY(%s) AND id_cliente = %s",
                (list(actions["expire"]), int(client_id)),
            )
        grant = actions["grant"]
        if grant:
            cursor.execute(
                """INSERT INTO cadu_credits_extras
                       (id_cliente, tokens_amount, tokens_used, purchased_at, expires_at, status,
                        source, label, cycle_start, client_plan_id)
                   VALUES (%s, %s, 0, NOW(), %s, 'active', 'plan_allowance', %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (int(client_id), grant["tokens"], grant["expires_at"],
                 f"Franquia {grant['cycle_start'].strftime('%m/%Y')}", grant["cycle_start"],
                 plan.get("client_plan_id")),
            )
        cursor.execute("RELEASE SAVEPOINT cadu_plan_allowance")
        return actions
    except Exception:
        logger.warning("Franquia do plano não liberada para o cliente %s", client_id, exc_info=True)
        cursor.execute("ROLLBACK TO SAVEPOINT cadu_plan_allowance")
        return None


# ------------------------------------------------------- serviço único de planos (API pública)

def balance_from_rows(*, plan: Optional[dict], lots: Iterable[dict], today: date,
                      enabled: Optional[bool] = None) -> dict:
    """Saldo unificado (puro): franquia do ciclo + extras + total disponível.

    Com a chave desligada, a franquia é só informativa (``active=False``) e o
    total disponível continua sendo a soma dos lotes, exatamente como hoje.
    """
    enabled = allowance_enabled() if enabled is None else enabled
    plan = plan or {}
    start, end = current_cycle(today, cycle_anchor_day(plan))
    lots = [dict(lot) for lot in lots or ()]

    def room(lot: dict) -> int:
        return max(0, _int(lot.get("tokens_amount")) - _int(lot.get("tokens_used")))

    allowance = next((lot for lot in lots if str(lot.get("source") or "") == ALLOWANCE_SOURCE
                      and _cycle_start_of(lot) == start), None)
    extras = [lot for lot in lots if str(lot.get("source") or "") != ALLOWANCE_SOURCE]
    if enabled and allowance:
        franchise = {"active": True, "total": _int(allowance.get("tokens_amount")),
                     "used": _int(allowance.get("tokens_used")), "available": room(allowance)}
    else:
        franchise = {"active": False, "total": _plan_tokens(plan) if plan else 0, "used": None, "available": 0}
    franchise["renews_on"] = (end + timedelta(days=1)).isoformat()
    franchise["cycle_start"] = start.isoformat()
    extras_available = sum(room(lot) for lot in extras)
    return {"franchise": franchise, "extras": {"available": extras_available,
                                                "lots": sum(1 for lot in extras if room(lot))},
            "total_available": extras_available + franchise["available"], "enabled": bool(enabled)}


def get_balance(client_id: int, today: Optional[date] = None) -> dict:
    """Ponto único para Workspace, chat, MCP, Studio e admin lerem o saldo do plano."""
    from .db import get_db

    today = today or date.today()
    conn = get_db()
    with conn.cursor() as cursor:
        if allowance_enabled():
            ensure_plan_allowance(cursor, client_id, today)
        has_source = allowance_enabled() and _has_source_column(cursor)
        cursor.execute(
            f"""SELECT id, tokens_amount, tokens_used, expires_at,
                       {'source, cycle_start' if has_source else 'NULL::varchar AS source, NULL::date AS cycle_start'}
                  FROM cadu_credits_extras
                 WHERE id_cliente = %s AND status = 'active'
                   AND (expires_at IS NULL OR expires_at > NOW())""",
            (int(client_id),),
        )
        lots = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """SELECT cp.valid_from, cp.plan_start_date, pd.plan_type, pd.plan_name,
                      pd.plan_name AS plan_definition_name,
                      COALESCE(pd.tokens_monthly_limit, cp.tokens_monthly_limit, 0) AS tokens_monthly_limit
                 FROM cadu_client_plans cp
            LEFT JOIN cadu_plan_definitions pd ON pd.id = cp.id_plan_definition
                WHERE cp.id_cliente = %s AND cp.plan_status = 'active'
             ORDER BY cp.created_at DESC LIMIT 1""",
            (int(client_id),),
        )
        plan = dict(cursor.fetchone() or {})
    if allowance_enabled():
        conn.commit()
    return balance_from_rows(plan=plan, lots=lots, today=today)


# Nomes do contrato do serviço de planos.
ensure_cycle = ensure_plan_allowance
debit_plan = allocate_debit
