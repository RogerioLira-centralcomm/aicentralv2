"""Custo das gerações do Smart Planner, em reais."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from ..creative_modeling_fx import brl_from_usd, usd_brl_rate
from .helpers import as_dict, as_list, text

logger = logging.getLogger(__name__)

_STATE: ContextVar[dict | None] = ContextVar("smart_planner_cost", default=None)


MODEL_PRICING_PER_MILLION = {
    "gpt-5.4": {"input": 2.50, "cached": 0.25, "output": 15.00},
    "gpt-5-mini": {"input": 0.25, "cached": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached": 0.005, "output": 0.40},
}


def _pricing(model: str) -> dict | None:
    slug = text(model).lower().split("/")[-1]
    for prefix, pricing in MODEL_PRICING_PER_MILLION.items():
        if slug == prefix or slug.startswith(prefix + "-"):
            return pricing
    return None


def usage_usd(usage: Any, *, model: str = "") -> float | None:
    if not isinstance(usage, dict):
        return None
    for key in ("cost", "total_cost", "cost_usd"):
        value = usage.get(key)
        if value is None:
            continue
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    pricing = _pricing(model)
    if not pricing:
        return None
    try:
        input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        details = as_dict(usage.get("input_tokens_details") or usage.get("prompt_tokens_details"))
        cached_tokens = min(input_tokens, int(details.get("cached_tokens") or 0))
    except (TypeError, ValueError):
        return None
    if input_tokens <= 0 and output_tokens <= 0:
        return None
    uncached_tokens = max(0, input_tokens - cached_tokens)
    return (
        uncached_tokens * pricing["input"]
        + cached_tokens * pricing["cached"]
        + output_tokens * pricing["output"]
    ) / 1_000_000


def format_brl(amount: Any, *, usd: Any = 0) -> str:
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        value = 0.0
    if value <= 0:
        try:
            if float(usd or 0) > 0:
                value = 0.01
            else:
                return ""
        except (TypeError, ValueError):
            return ""
    integer, frac = f"{value:.2f}".split(".")
    groups: list[str] = []
    while integer:
        groups.append(integer[-3:])
        integer = integer[:-3]
    return "R$ " + ".".join(reversed(groups)) + "," + frac


def cost_from_dados(dados: Any) -> dict:
    ledger = as_dict(as_dict(dados).get("cost"))
    try:
        usd = max(0.0, float(ledger.get("usd") or 0))
    except (TypeError, ValueError):
        usd = 0.0
    try:
        brl = max(0.0, float(ledger.get("brl") or 0))
    except (TypeError, ValueError):
        brl = 0.0
    return {
        "usd": usd,
        "brl": brl,
        "label": format_brl(brl, usd=usd),
    }


def apply_charge(
    ledger: Any,
    usage: Any,
    *,
    kind: str = "",
    model: str = "",
    rate: float | None = None,
    source: str = "",
) -> dict:
    usd = usage_usd(usage, model=model)
    existing = as_dict(ledger)
    items = [item for item in as_list(existing.get("items")) if isinstance(item, dict)]
    if usd is None or usd <= 0:
        return _finalize(existing, items, rate=rate, source=source or text(existing.get("source")))
    if rate is None:
        rate, resolved = usd_brl_rate()
        source = source or resolved
    items.append({
        "kind": text(kind) or "chat",
        "model": text(model),
        "usd": round(usd, 6),
        "brl": brl_from_usd(usd, rate),
    })
    return _finalize(existing, items, rate=rate, source=source)


def _finalize(existing: dict, items: list[dict], *, rate: float | None, source: str) -> dict:
    if rate is None:
        try:
            rate = float(existing.get("rate") or 0) or None
        except (TypeError, ValueError):
            rate = None
        if rate is None:
            rate, resolved = usd_brl_rate()
            source = source or resolved
    total_usd = 0.0
    for item in items:
        try:
            total_usd += float(item.get("usd") or 0)
        except (TypeError, ValueError):
            continue
    return {
        "usd": round(max(0.0, total_usd), 6),
        "brl": brl_from_usd(total_usd, rate),
        "rate": rate,
        "source": source or text(existing.get("source")),
        "items": items[-40:],
    }


def record(usage: Any, *, kind: str = "", model: str = "") -> dict | None:
    state = _STATE.get()
    if not state:
        return None
    usd = usage_usd(usage, model=model)
    if usd is None or usd <= 0:
        return state.get("ledger")
    state["ledger"] = apply_charge(
        state.get("ledger"),
        usage,
        kind=kind,
        model=model,
        rate=state.get("rate"),
        source=state.get("source") or "",
    )
    _persist(state)
    return state["ledger"]


@contextmanager
def bound_session(token: str) -> Iterator[dict]:
    from .repository import get_by_token

    token = text(token)
    row = get_by_token(token) if token else None
    dados = as_dict((row or {}).get("dados_detectados"))
    rate, source = usd_brl_rate()
    state = {
        "token": token,
        "ledger": as_dict(dados.get("cost")),
        "rate": rate,
        "source": source,
    }
    handle = _STATE.set(state)
    try:
        yield state
        _persist(state)
    finally:
        _STATE.reset(handle)


def _persist(state: dict) -> None:
    token = text(state.get("token"))
    ledger = as_dict(state.get("ledger"))
    if not token or not ledger:
        return
    from .repository import merge_dados

    try:
        merge_dados(token, {"cost": ledger})
    except Exception:
        logger.exception("Não foi possível gravar o custo do Smart Planner.")
