"""Catálogo global de custos técnicos e metadados de cobrança do Cadu.

O cliente sempre recebe uma única unidade comercial: Token Cadu. Cada
provedor/modelo pode ter unidade e custo técnico diferentes; a conversão para
Tokens Cadu acontece depois do custo técnico ser calculado.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class CostMetadata:
    provider: str
    model: str
    modality: str
    operation: str
    unit: str
    technical_unit_cost_usd: Decimal
    rule_version: str = "cadu-commercial-v1"


def _decimal(value, default="0") -> Decimal:
    try:
        return max(Decimal("0"), Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _env_cost(name: str, default: str) -> Decimal:
    return _decimal(os.getenv(name, default), default)


_CATALOG = {
    "firecrawl": CostMetadata("firecrawl", "firecrawl", "web", "scrape", "credit", _env_cost("CADU_FIRECRAWL_USD_PER_CREDIT", "0.0025")),
    "perplexity": CostMetadata("perplexity", "perplexity", "text", "research", "provider_unit", _env_cost("CADU_PERPLEXITY_USD_PER_UNIT", "1")),
    "openai/text": CostMetadata("openai", "text", "text", "completion", "token", _env_cost("CADU_OPENAI_TEXT_USD_PER_UNIT", "0.00001")),
    "openai/image": CostMetadata("openai", "image", "image", "generation", "generation", _env_cost("CADU_OPENAI_IMAGE_USD_PER_GENERATION", "0.22")),
    "video": CostMetadata("bytedance", "video", "video", "generation", "second", _env_cost("CADU_VIDEO_USD_PER_SECOND", "1.271")),
    "audio/tts": CostMetadata("google", "tts", "audio", "synthesis", "token", _env_cost("CADU_AUDIO_TTS_USD_PER_TOKEN", "0.00002")),
    "audio/transcription": CostMetadata("openai", "transcription", "audio", "transcription", "minute", _env_cost("CADU_AUDIO_TRANSCRIPTION_USD_PER_MINUTE", "0.006")),
}


def cost_metadata(model: str = "", *, modality: str = "", operation: str = "") -> CostMetadata:
    """Resolve metadados sem exigir que o chamador conheça o provedor."""
    value = str(model or "").strip().lower()
    if "firecrawl" in value:
        key = "firecrawl"
    elif "perplexity" in value:
        key = "perplexity"
    elif modality == "audio" and operation in {"transcription", "transcribe"}:
        key = "audio/transcription"
    elif modality == "audio":
        key = "audio/tts"
    elif modality == "image":
        key = "openai/image"
    elif modality == "video":
        key = "video"
    else:
        key = "openai/text"
    base = _CATALOG[key]
    return CostMetadata(base.provider, value or base.model, modality or base.modality,
                        operation or base.operation, base.unit,
                        base.technical_unit_cost_usd, base.rule_version)


def usage_metadata(*, model: str = "", provider: str = "", modality: str = "",
                   operation: str = "", technical_units: int = 0,
                   technical_cost_usd=0, exchange_rate=None,
                   cadu_tokens_charged: int = 0, idempotency_key: str = "") -> dict:
    """Contrato único persistido junto de cada cobrança."""
    resolved = cost_metadata(model, modality=modality, operation=operation)
    return {
        "provider": provider or resolved.provider,
        "model": model or resolved.model,
        "modality": modality or resolved.modality,
        "operation": operation or resolved.operation,
        "technical_units": max(0, int(technical_units or 0)),
        "technical_unit": resolved.unit,
        "technical_unit_cost_usd": str(resolved.technical_unit_cost_usd),
        "technical_cost_usd": str(_decimal(technical_cost_usd)),
        "exchange_rate": exchange_rate,
        "cadu_tokens_charged": max(0, int(cadu_tokens_charged or 0)),
        "commercial_rule_version": resolved.rule_version,
        "idempotency_key": str(idempotency_key or ""),
    }


__all__ = ["CostMetadata", "cost_metadata", "usage_metadata"]


def normalize_charge_metadata(*, tool: str, stage: str, model: str = "",
                              provider: str = "", modality: str = "",
                              operation: str = "", technical_units: int = 0,
                              technical_cost_usd=0, cadu_tokens_charged: int = 0,
                              idempotency_key: str = "", metadata=None) -> dict:
    """Contrato único de cobrança para todos os produtos CADU."""
    value = usage_metadata(
        model=model, provider=provider, modality=modality, operation=operation,
        technical_units=technical_units, technical_cost_usd=technical_cost_usd,
        cadu_tokens_charged=cadu_tokens_charged, idempotency_key=idempotency_key,
    )
    value.update({
        "tool": str(tool or "unknown"),
        "stage": str(stage or "unknown"),
        "metadata_version": "cadu-charge-v1",
        "legacy_metadata": dict(metadata or {}),
    })
    return value


__all__.append("normalize_charge_metadata")
