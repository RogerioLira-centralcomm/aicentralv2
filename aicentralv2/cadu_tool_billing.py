"""Ledger transacional de tokens para ferramentas de IA do CADU.

O saldo comercial vive em ``cadu_credits_extras``. Cada chamada de provedor
gera exatamente uma linha idempotente em ``cadu_tools_token_usage`` e consome
os lotes válidos em ordem de expiração (FEFO).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from psycopg.types.json import Json


class InsufficientToolCredits(ValueError):
    pass


def _integer(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _money(value):
    try:
        return max(Decimal("0"), Decimal(str(value or 0)))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def usage_tokens(usage=None):
    data = usage if isinstance(usage, dict) else {}
    incoming = _integer(data.get("input_tokens") or data.get("prompt_tokens"))
    outgoing = _integer(data.get("output_tokens") or data.get("completion_tokens"))
    total = _integer(data.get("total_tokens")) or incoming + outgoing
    return incoming, outgoing, max(total, incoming + outgoing)


def cost_token_equivalent(cost_usd, *, usd_per_credit_token=None, margin_multiplier=1):
    """Converte custo adicional de mídia em tokens comerciais configuráveis."""
    rate = usd_per_credit_token
    if rate is None:
        rate = os.getenv("CADU_USD_PER_CREDIT_TOKEN", "0.00001")
    value = _money(rate)
    if value <= 0:
        raise ValueError("CADU_USD_PER_CREDIT_TOKEN deve ser maior que zero.")
    cost = _money(cost_usd)
    try:
        multiplier = max(1, int(margin_multiplier or 1))
    except (TypeError, ValueError):
        multiplier = 1
    return int(math.ceil(float((cost / value) * multiplier))) if cost else 0


def estimated_credit_tokens(*, provider_tokens=0, cost_usd=0, media_tokens=None, margin_multiplier=1):
    """Estimativa pública em tokens; nunca converte para BRL."""
    try:
        multiplier = max(1, int(margin_multiplier or 1))
    except (TypeError, ValueError):
        multiplier = 1
    # O multiplicador é comercial: deve abranger tanto o consumo medido pelo
    # provedor quanto custos adicionais (por exemplo, mídia). Antes disto ele
    # incidia apenas sobre USD adicional e deixava agentes textuais sem margem.
    tokens = _integer(provider_tokens) * multiplier
    if media_tokens is not None:
        return tokens + _integer(media_tokens)
    return tokens + cost_token_equivalent(cost_usd, margin_multiplier=multiplier)


@dataclass(frozen=True)
class ToolCharge:
    idempotency_key: str
    client_id: int
    user_id: int
    tool: str
    stage: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    provider_total_tokens: int = 0
    charged_tokens: int = 0
    internal_cost_usd: Decimal = Decimal("0")
    additional_cost_usd: Decimal = Decimal("0")
    metadata: dict | None = None


class ToolTokenLedger:
    def __init__(self, connection_factory=None):
        if connection_factory is None:
            from .db import get_db
            connection_factory = get_db
        self.connection_factory = connection_factory

    def available(self, client_id):
        conn = self.connection_factory()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(tokens_amount - tokens_used), 0) AS available
                  FROM cadu_credits_extras
                 WHERE id_cliente = %s
                   AND status = 'active'
                   AND tokens_used < tokens_amount
                   AND (expires_at IS NULL OR expires_at > NOW())
                """,
                (client_id,),
            )
            row = cursor.fetchone() or {}
        return _integer(row.get("available"))

    def assert_available(self, client_id, estimated_tokens):
        required = _integer(estimated_tokens)
        balance = self.available(client_id)
        if balance < required:
            raise InsufficientToolCredits(
                f"Saldo insuficiente: esta execução estima {required} tokens e há {balance} disponíveis."
            )
        return balance

    def charge(self, charge: ToolCharge):
        if not str(charge.idempotency_key or "").strip():
            raise ValueError("A execução precisa de uma chave idempotente.")
        if not charge.client_id or not charge.user_id:
            raise ValueError("Cliente e usuário são obrigatórios para registrar consumo.")
        required = _integer(charge.charged_tokens)
        conn = self.connection_factory()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO cadu_tools_token_usage (
                        idempotency_key, id_cliente, id_contato_cliente,
                        ferramenta, etapa, modelo, tokens_entrada, tokens_saida,
                        total_tokens, tokens_cobrados, custo_interno,
                        custo_adicional, moeda, metadata, status
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'USD',%s,'pending')
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING id
                    """,
                    (
                        charge.idempotency_key,
                        charge.client_id,
                        charge.user_id,
                        charge.tool,
                        charge.stage,
                        charge.model,
                        _integer(charge.input_tokens),
                        _integer(charge.output_tokens),
                        _integer(charge.provider_total_tokens),
                        required,
                        charge.internal_cost_usd,
                        charge.additional_cost_usd,
                        Json(charge.metadata or {}),
                    ),
                )
                inserted = cursor.fetchone()
                if not inserted:
                    conn.rollback()
                    return self._existing(charge.idempotency_key)

                cursor.execute(
                    """
                    SELECT id, tokens_amount, tokens_used
                      FROM cadu_credits_extras
                     WHERE id_cliente = %s
                       AND status = 'active'
                       AND tokens_used < tokens_amount
                       AND (expires_at IS NULL OR expires_at > NOW())
                     ORDER BY expires_at NULLS LAST, purchased_at, id
                     FOR UPDATE
                    """,
                    (charge.client_id,),
                )
                lots = [dict(row) for row in cursor.fetchall()]
                available = sum(_integer(row["tokens_amount"]) - _integer(row["tokens_used"]) for row in lots)
                if available < required:
                    raise InsufficientToolCredits(
                        f"Saldo insuficiente: a execução usou {required} tokens e há {available} disponíveis."
                    )
                remaining = required
                allocations = []
                for lot in lots:
                    if remaining <= 0:
                        break
                    room = _integer(lot["tokens_amount"]) - _integer(lot["tokens_used"])
                    used = min(room, remaining)
                    if not used:
                        continue
                    cursor.execute(
                        "UPDATE cadu_credits_extras SET tokens_used = tokens_used + %s WHERE id = %s",
                        (used, lot["id"]),
                    )
                    allocations.append({"lot_id": lot["id"], "tokens": used})
                    remaining -= used
                cursor.execute(
                    """
                    UPDATE cadu_tools_token_usage
                       SET status = 'charged', charged_at = NOW(),
                           metadata = metadata || %s::jsonb
                     WHERE id = %s
                    RETURNING *
                    """,
                    (Json({"allocations": allocations}), inserted["id"]),
                )
                row = dict(cursor.fetchone())
            conn.commit()
            # Notification work happens only after the debit is durable; an
            # unavailable mail provider must never alter the commercial ledger.
            try:
                from .cadu_credit_alerts import notify_balance
                notify_balance(charge.client_id, usage_id=row.get("id"))
            except Exception:
                pass
            return row
        except Exception:
            conn.rollback()
            raise

    def _existing(self, key):
        conn = self.connection_factory()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM cadu_tools_token_usage WHERE idempotency_key = %s",
                (key,),
            )
            row = cursor.fetchone()
        return dict(row) if row else None


def charge_from_provider(
    *, ledger, idempotency_key, client_id, user_id, tool, stage,
    provider_result=None, model="", fallback_cost_usd=0, media_tokens=None,
    metadata=None, margin_multiplier=1,
):
    result = provider_result if isinstance(provider_result, dict) else {}
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    incoming, outgoing, total = usage_tokens(usage)
    actual_cost = _money(
        result.get("actual_cost_usd")
        or usage.get("cost")
        or usage.get("total_cost")
        or usage.get("cost_usd")
        or fallback_cost_usd
    )
    charged = estimated_credit_tokens(
        provider_tokens=total,
        cost_usd=actual_cost if media_tokens is None else 0,
        media_tokens=media_tokens,
        margin_multiplier=margin_multiplier,
    )
    return ledger.charge(ToolCharge(
        idempotency_key=idempotency_key,
        client_id=int(client_id),
        user_id=int(user_id),
        tool=tool,
        stage=stage,
        model=str(result.get("model") or model or "unknown"),
        input_tokens=incoming,
        output_tokens=outgoing,
        provider_total_tokens=total,
        charged_tokens=charged,
        internal_cost_usd=actual_cost,
        additional_cost_usd=actual_cost,
        metadata={**(metadata or {}), "margin_multiplier": max(1, int(margin_multiplier or 1))},
    ))
