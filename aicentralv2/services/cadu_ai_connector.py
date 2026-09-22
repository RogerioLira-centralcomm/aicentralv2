"""Boundary compartilhada para geração de IA e cobrança por cliente."""
from __future__ import annotations

import hashlib
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
        raw_key = str(idempotency_key or "").strip()
        if not raw_key:
            raise ValueError("A chamada de IA precisa de uma chave idempotente.")
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        key = f"ai:{actor.client_id}:{actor.user_id}:{digest}"
        estimate = max(1, int(estimated_tokens or 0))
        claim = self.credits.claim_generation(
            actor=actor, idempotency_key=key, app=str(app), stage=str(stage),
            model=str(model or ""), metadata={
                **(metadata or {}), "source_idempotency_key": raw_key,
                "estimated_tokens": estimate,
            },
        )
        if not claim.get("claim_acquired"):
            status = str(claim.get("status") or "pending")
            if status == "charged":
                snapshot = (claim.get("metadata") or {}).get("ai_response")
                if isinstance(snapshot, dict):
                    return {**snapshot, "cadu_charge": claim, "idempotent_replay": True}
            raise ValueError(
                "Esta geração já está em processamento." if status == "pending"
                else "Esta geração anterior falhou; envie o pedido novamente."
            )
        try:
            self.credits.authorize(actor, estimate)
            result = self.completion(messages, model=model, **provider_options)
        except Exception as exc:
            self.credits.fail_generation(actor=actor, idempotency_key=key, error=exc)
            raise
        provider = str(result.get("provider") or "unknown")
        snapshot = {
            "message": result.get("message"), "model": result.get("model"),
            "provider": provider,
            "provider_attempts": list(result.get("provider_attempts") or [provider]),
            "usage": result.get("usage") or {},
        }
        try:
            charge = self.credits.charge_provider(
                actor=actor, idempotency_key=key, app=str(app), stage=str(stage),
                provider_result=result, model=str(result.get("model") or model or ""),
                metadata={
                    **(metadata or {}), "provider": provider,
                    "provider_attempts": snapshot["provider_attempts"],
                    "ai_response": snapshot,
                },
            )
        except Exception as exc:
            self.credits.fail_generation(actor=actor, idempotency_key=key, error=exc)
            raise
        return {**result, "cadu_charge": charge}


__all__ = ["CaduAIConnector"]
