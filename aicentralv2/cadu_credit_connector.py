"""Conector único de créditos para as aplicações Cadu.

Aplicações não devem escrever em lotes ou no ledger diretamente. Este conector
mantém a identidade de cobrança, a autorização e o débito idempotente no mesmo
contrato, independentemente de o consumo vir de Chat, Studio ou Planner.
"""
from __future__ import annotations

import math
import os
from psycopg.types.json import Json
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from typing import Any

from .cadu_tool_billing import ToolCharge, ToolTokenLedger, charge_from_provider, cost_token_equivalent


# Firecrawl Standard: US$5 para 2.000 créditos. Mantemos configurável porque
# upgrades e contratos enterprise podem ter uma taxa diferente.
FIRECRAWL_STANDARD_USD_PER_CREDIT = Decimal("0.0025")


def firecrawl_usd_per_credit() -> Decimal:
    try:
        value = Decimal(os.getenv("CADU_FIRECRAWL_USD_PER_CREDIT", str(FIRECRAWL_STANDARD_USD_PER_CREDIT)))
    except (InvalidOperation, TypeError, ValueError):
        value = FIRECRAWL_STANDARD_USD_PER_CREDIT
    return max(Decimal("0"), value)


def firecrawl_credit_cost(operation: str, *, pages: int = 0, results: int = 0) -> int:
    """Pricing units documented by Firecrawl for the Standard contract."""
    operation = str(operation or "").strip().lower()
    if operation in {"scrape", "crawl"}:
        return max(1, int(pages or 1))
    if operation == "map":
        return 1
    if operation == "search":
        return max(2, 2 * math.ceil(max(1, int(results or 10)) / 10))
    raise ValueError("Operação Firecrawl sem política de crédito configurada.")


def commercial_token_price_brl(client_id: int) -> Decimal:
    """Preço unitário comercial do token do cliente, em BRL."""
    from .db import get_db

    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            """SELECT COALESCE(pd.price_monthly, 0) AS price,
                              COALESCE(pd.tokens_monthly_limit, cp.tokens_monthly_limit, 0) AS tokens
                         FROM cadu_client_plans cp
                         JOIN cadu_plan_definitions pd ON pd.id = cp.id_plan_definition
                        WHERE cp.id_cliente = %s AND cp.plan_status = 'active'
                        ORDER BY cp.created_at DESC LIMIT 1""",
            (int(client_id),),
        )
        row = cursor.fetchone() or {}
    price = Decimal(str(row.get("price") or 0))
    tokens = int(row.get("tokens") or 0)
    if price <= 0 or tokens <= 0:
        raise ValueError("Preço comercial de Tokens Cadu indisponível para este cliente.")
    return price / Decimal(tokens)


@dataclass(frozen=True)
class CreditActor:
    client_id: int
    user_id: int

    @classmethod
    def from_values(cls, client_id: Any, user_id: Any) -> "CreditActor":
        try:
            client = int(client_id)
            user = int(user_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Cliente e usuário são obrigatórios para cobrança.") from exc
        if client <= 0 or user <= 0:
            raise ValueError("Cliente e usuário são obrigatórios para cobrança.")
        return cls(client_id=client, user_id=user)


class CaduCreditConnector:
    """Gateway de saldo compartilhado, com dependência injetável para testes."""

    def __init__(self, ledger: ToolTokenLedger | None = None):
        self.ledger = ledger or ToolTokenLedger()

    def authorize(self, actor: CreditActor, estimated_tokens: int) -> int:
        """Valida saldo antes de iniciar uma chamada paga."""
        return self.ledger.assert_available(actor.client_id, max(1, int(estimated_tokens or 0)))

    def balance(self, client_id: int) -> int:
        return self.ledger.available(int(client_id))

    def claim_generation(self, *, actor: CreditActor, idempotency_key: str,
                         app: str, stage: str, model: str = "", metadata=None) -> dict:
        return self.ledger.claim_generation(ToolCharge(
            idempotency_key=str(idempotency_key), client_id=actor.client_id,
            user_id=actor.user_id, tool=str(app), stage=str(stage),
            model=str(model or "unknown"), metadata=metadata or {},
        ))

    def fail_generation(self, *, actor: CreditActor, idempotency_key: str, error) -> dict | None:
        return self.ledger.fail_generation(
            str(idempotency_key), actor.client_id, actor.user_id, error
        )

    def estimate_firecrawl_tokens(self, operation: str, *, client_id: int | None = None, pages: int = 0, results: int = 0) -> int:
        credits = firecrawl_credit_cost(operation, pages=pages, results=results)
        if client_id is None:
            return cost_token_equivalent(Decimal(credits) * firecrawl_usd_per_credit())
        from .creative_modeling_fx import usd_brl_rate
        price_brl = commercial_token_price_brl(client_id)
        exchange, _source = usd_brl_rate()
        return cost_token_equivalent(
            Decimal(credits) * firecrawl_usd_per_credit() * Decimal(str(exchange)),
            usd_per_credit_token=price_brl,
        )

    def authorize_firecrawl(self, actor: CreditActor, operation: str, *, pages: int = 0, results: int = 0) -> int:
        return self.authorize(actor, self.estimate_firecrawl_tokens(operation, client_id=actor.client_id, pages=pages, results=results))

    def charge_firecrawl(
        self, *, actor: CreditActor, idempotency_key: str, operation: str,
        pages: int = 0, results: int = 0, app: str, stage: str, metadata: dict | None = None,
    ) -> dict | None:
        credits = firecrawl_credit_cost(operation, pages=pages, results=results)
        cost_usd = Decimal(credits) * firecrawl_usd_per_credit()
        return self.charge_provider(
            actor=actor, idempotency_key=idempotency_key, app=app, stage=stage,
            provider_result={"model": f"firecrawl/{operation}", "usage": {}, "actual_cost_usd": str(cost_usd)},
            commercial_token_price_usd=self._commercial_token_price_usd(actor.client_id),
            metadata={**(metadata or {}), "provider": "firecrawl", "operation": operation,
                      "firecrawl_credits": credits, "usd_per_firecrawl_credit": str(firecrawl_usd_per_credit())},
        )

    def charge_provider(
        self, *, actor: CreditActor, idempotency_key: str, app: str, stage: str,
        provider_result: dict | None, model: str = "", fallback_cost_usd=0,
        media_tokens: int | None = None, metadata: dict | None = None, margin_multiplier: int = 1,
        commercial_token_price_usd: Decimal | None = None,
    ) -> dict | None:
        """Registra e debita uma execução já concluída pelo provedor."""
        result = provider_result or {}
        billing_metadata = dict(metadata or {})
        provider = str(result.get("provider") or "").strip()
        attempts = result.get("provider_attempts")
        if provider:
            billing_metadata.setdefault("provider", provider)
        if isinstance(attempts, (list, tuple)) and attempts:
            billing_metadata.setdefault("provider_attempts", [str(item) for item in attempts if str(item).strip()])
        if commercial_token_price_usd is None:
            raw_cost = result.get("actual_cost_usd") or (result.get("usage") or {}).get("cost")
            if raw_cost:
                commercial_token_price_usd = self._commercial_token_price_usd(actor.client_id)
        return charge_from_provider(
            ledger=self.ledger,
            idempotency_key=str(idempotency_key),
            client_id=actor.client_id,
            user_id=actor.user_id,
            tool=str(app),
            stage=str(stage),
            provider_result=result,
            model=str(model),
            fallback_cost_usd=fallback_cost_usd,
            media_tokens=media_tokens,
            metadata=billing_metadata,
            margin_multiplier=margin_multiplier,
            usd_per_credit_token=commercial_token_price_usd,
        )

    def _commercial_token_price_usd(self, client_id: int) -> Decimal:
        from .creative_modeling_fx import usd_brl_rate
        exchange, _source = usd_brl_rate()
        return commercial_token_price_brl(client_id) / Decimal(str(exchange))

    def charge_tokens(
        self, *, actor: CreditActor, idempotency_key: str, app: str, stage: str,
        charged_tokens: int, model: str = "cadu", input_tokens: int = 0,
        output_tokens: int = 0, provider_total_tokens: int = 0,
        internal_cost_usd=0, additional_cost_usd=0, metadata: dict | None = None,
    ) -> dict | None:
        """Debit a fixed token amount through the shared Cadu boundary.

        This covers reservations and media quotes whose providers do not
        return a standard usage payload. Product modules must not write a
        ``ToolCharge`` to the ledger directly.
        """
        from .cadu_tool_billing import ToolCharge

        return self.ledger.charge(ToolCharge(
            idempotency_key=str(idempotency_key),
            client_id=actor.client_id,
            user_id=actor.user_id,
            tool=str(app),
            stage=str(stage),
            model=str(model or "cadu"),
            input_tokens=max(0, int(input_tokens or 0)),
            output_tokens=max(0, int(output_tokens or 0)),
            provider_total_tokens=max(0, int(provider_total_tokens or 0)),
            charged_tokens=max(0, int(charged_tokens or 0)),
            internal_cost_usd=internal_cost_usd,
            additional_cost_usd=additional_cost_usd,
            metadata={**(metadata or {}), "margin_multiplier": 1},
        ))

    def charge_tokens_in_transaction(
        self, cursor, *, actor: CreditActor, idempotency_key: str, app: str,
        stage: str, charged_tokens: int, model: str = "cadu",
        metadata: dict | None = None,
    ) -> dict:
        """Debit the global token lots through an existing caller transaction.

        Used by atomic ingestion/indexing flows where the debit must commit or
        roll back with the source write. The public and regular API paths keep
        using ``charge_tokens``/``charge_provider`` on this same connector.
        """
        required = max(0, int(charged_tokens or 0))
        if not str(idempotency_key or '').strip():
            raise ValueError('A execução precisa de uma chave idempotente.')
        cursor.execute(
            """INSERT INTO cadu_tools_token_usage
                (idempotency_key, id_cliente, id_contato_cliente, ferramenta,
                 etapa, modelo, tokens_entrada, tokens_saida, total_tokens,
                 tokens_cobrados, metadata, status, charged_at)
               VALUES (%s,%s,%s,%s,%s,%s,0,0,0,%s,%s::jsonb,'charged',NOW())
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING *""",
            (str(idempotency_key), actor.client_id, actor.user_id, str(app),
             str(stage), str(model or 'cadu'), required, Json(metadata or {})),
        )
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                'SELECT * FROM cadu_tools_token_usage WHERE idempotency_key = %s',
                (str(idempotency_key),),
            )
            existing = cursor.fetchone()
            return dict(existing or {})
        if required <= 0:
            return dict(row)

        cursor.execute(
            """SELECT id, tokens_amount, tokens_used
                  FROM cadu_credits_extras
                 WHERE id_cliente=%s AND status='active'
                   AND tokens_used < tokens_amount
                   AND (expires_at IS NULL OR expires_at > NOW())
              ORDER BY expires_at NULLS LAST, purchased_at, id
                 FOR UPDATE""",
            (actor.client_id,),
        )
        lots = [dict(item) for item in cursor.fetchall()]
        available = sum(max(0, int(item.get('tokens_amount') or 0) - int(item.get('tokens_used') or 0)) for item in lots)
        if available < required:
            raise ValueError(f'Saldo insuficiente: são necessários {required} tokens e há {available} disponíveis.')
        remaining = required
        allocations = []
        for lot in lots:
            if remaining <= 0:
                break
            room = max(0, int(lot.get('tokens_amount') or 0) - int(lot.get('tokens_used') or 0))
            used = min(room, remaining)
            if not used:
                continue
            cursor.execute(
                'UPDATE cadu_credits_extras SET tokens_used=tokens_used+%s WHERE id=%s AND id_cliente=%s',
                (used, lot['id'], actor.client_id),
            )
            allocations.append({'lot_id': lot['id'], 'tokens': used})
            remaining -= used
        cursor.execute(
            """UPDATE cadu_tools_token_usage
                  SET metadata = metadata || %s::jsonb
                WHERE id = %s
            RETURNING *""",
            (Json({'allocations': allocations}), row['id']),
        )
        return dict(cursor.fetchone() or row)
