"""Conector único de créditos para as aplicações Cadu.

Aplicações não devem escrever em lotes ou no ledger diretamente. Este conector
mantém a identidade de cobrança, a autorização e o débito idempotente no mesmo
contrato, independentemente de o consumo vir de Chat, Studio ou Planner.
"""
from __future__ import annotations

import math
import os
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from typing import Any

from .cadu_tool_billing import ToolTokenLedger, charge_from_provider, cost_token_equivalent


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

    def estimate_firecrawl_tokens(self, operation: str, *, pages: int = 0, results: int = 0) -> int:
        credits = firecrawl_credit_cost(operation, pages=pages, results=results)
        return cost_token_equivalent(Decimal(credits) * firecrawl_usd_per_credit())

    def authorize_firecrawl(self, actor: CreditActor, operation: str, *, pages: int = 0, results: int = 0) -> int:
        return self.authorize(actor, self.estimate_firecrawl_tokens(operation, pages=pages, results=results))

    def charge_firecrawl(
        self, *, actor: CreditActor, idempotency_key: str, operation: str,
        pages: int = 0, results: int = 0, app: str, stage: str, metadata: dict | None = None,
    ) -> dict | None:
        credits = firecrawl_credit_cost(operation, pages=pages, results=results)
        cost_usd = Decimal(credits) * firecrawl_usd_per_credit()
        return self.charge_provider(
            actor=actor, idempotency_key=idempotency_key, app=app, stage=stage,
            provider_result={"model": f"firecrawl/{operation}", "usage": {}, "actual_cost_usd": str(cost_usd)},
            metadata={**(metadata or {}), "provider": "firecrawl", "operation": operation,
                      "firecrawl_credits": credits, "usd_per_firecrawl_credit": str(firecrawl_usd_per_credit())},
        )

    def charge_provider(
        self, *, actor: CreditActor, idempotency_key: str, app: str, stage: str,
        provider_result: dict | None, model: str = "", fallback_cost_usd=0,
        media_tokens: int | None = None, metadata: dict | None = None, margin_multiplier: int = 1,
    ) -> dict | None:
        """Registra e debita uma execução já concluída pelo provedor."""
        return charge_from_provider(
            ledger=self.ledger,
            idempotency_key=str(idempotency_key),
            client_id=actor.client_id,
            user_id=actor.user_id,
            tool=str(app),
            stage=str(stage),
            provider_result=provider_result or {},
            model=str(model),
            fallback_cost_usd=fallback_cost_usd,
            media_tokens=media_tokens,
            metadata=metadata or {},
            margin_multiplier=margin_multiplier,
        )

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
