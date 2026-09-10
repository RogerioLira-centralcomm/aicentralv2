"""Conversão operacional USD → BRL para custos da modelagem."""

from __future__ import annotations

import os
import time

FALLBACK_USD_BRL = 5.5
_CACHE = {"rate": None, "source": None, "expires": 0}


def reset_rate_cache():
    _CACHE.update(rate=None, source=None, expires=0)


def usd_brl_rate():
    cached = _CACHE
    now = time.time()
    if cached["rate"] and cached["expires"] > now:
        return cached["rate"], cached["source"]
    rate, source = _resolve_rate()
    cached.update(rate=rate, source=source, expires=now + 900)
    return rate, source


def brl_from_usd(amount, rate=None):
    if rate is None:
        rate, _source = usd_brl_rate()
    try:
        usd = float(amount or 0)
    except (TypeError, ValueError):
        usd = 0.0
    return round(max(0.0, usd) * rate, 2)


def annotate_cost(record, usd_value=None):
    data = dict(record or {})
    if usd_value is None:
        usd_value = (
            data.get("spent_usd")
            if data.get("spent_usd") not in (None, "")
            else data.get("actual_cost_usd")
        )
        if usd_value in (None, ""):
            usd_value = data.get("estimated_cost_usd") or 0
    rate, source = usd_brl_rate()
    data["cost_usd"] = float(usd_value or 0)
    data["spent_brl"] = brl_from_usd(usd_value, rate)
    data["usd_brl_rate"] = rate
    data["usd_brl_source"] = source
    return data


def _resolve_rate():
    env = os.getenv("USD_BRL_RATE", "").strip()
    if env:
        try:
            rate = float(env)
            if rate > 0:
                return rate, "env:USD_BRL_RATE"
        except ValueError:
            pass
    try:
        import requests

        response = requests.get(
            "https://economia.awesomeapi.com.br/json/last/USD-BRL",
            timeout=4,
        )
        if response.status_code == 200:
            bid = ((response.json() or {}).get("USDBRL") or {}).get("bid")
            rate = float(bid)
            if rate > 0:
                return rate, "awesomeapi.com.br"
    except Exception:
        pass
    return FALLBACK_USD_BRL, "fallback"
