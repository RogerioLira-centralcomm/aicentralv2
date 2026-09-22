"""Boundary compartilhada para geração de IA e cobrança por cliente."""
from __future__ import annotations

from typing import Any, Callable

from ..cadu_credit_connector import CaduCreditConnector, CreditActor
from .openrouter_service import chat_completion


class CaduAIConnector:
    """Autoriza, executa com failover e debita uma geração idempotente."""

    def __init__(
        self,
        credits: CaduCreditConnector | None = None,
        completion: Callable[..., dict] | None = None,
    ):
        self.credits = credits or CaduCreditConnector()
        self.completion = completion or chat_completion

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        client_id: int,
        user_id: int,
        idempotency_key: str,
        app: str,
        stage: str,
        estimated_tokens: int,
        model: str | None = None,
        metadata: dict | None = None,
        **provider_options,
    ) -> dict:
        actor = CreditActor.from_values(client_id, user_id)
        key = str(idempotency_key or "").strip()
        if not key:
            raise ValueError("A chamada de IA precisa de uma chave idempotente.")
        self.credits.authorize(actor, max(1, int(estimated_tokens or 0)))
        result = self.completion(messages, model=model, **provider_options)
        provider = str(result.get("provider") or "unknown")
        charge = self.credits.charge_provider(
            actor=actor,
            idempotency_key=key,
            app=str(app),
            stage=str(stage),
            provider_result=result,
            model=str(result.get("model") or model or ""),
            metadata={
                **(metadata or {}),
                "provider": provider,
                "provider_attempts": list(result.get("provider_attempts") or [provider]),
            },
        )
        return {**result, "cadu_charge": charge}


__all__ = ["CaduAIConnector"]
