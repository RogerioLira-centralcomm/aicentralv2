"""Illustrative media allocations calculated without an LLM."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP


_BUDGET = re.compile(r"R\$\s*(\d[\d.,\s]*?)(?=\s*(?:milh[oõ]es?|mil\b|[,.;]|$))\s*(milh[oõ]es?|mil)?", re.I)
_SCENARIOS = (
    ("equilibrado", (40, 35, 25)),
    ("maior descoberta", (55, 30, 15)),
    ("maior captura de demanda", (25, 30, 45)),
)
_CHANNELS = ("social", "vídeo", "busca")
_CHANNEL_PATTERNS = (
    (r"\bgoogle\s+ads\b", "Google Ads"),
    (r"\bmeta\s+ads\b", "Meta Ads"),
    (r"\blinkedin\b", "LinkedIn"),
    (r"\binstagram\b", "Instagram"),
    (r"\byoutube\b", "YouTube"),
    (r"\btiktok\b", "TikTok"),
    (r"\bbusca\b", "busca"),
    (r"\bsocial\b", "social"),
    (r"\bv[ií]deo\b", "vídeo"),
)


def _amount(message: str) -> Decimal | None:
    match = _BUDGET.search(str(message or ""))
    if not match:
        return None
    raw = "".join(match.group(1).split())
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") >= 1 and len(raw.rsplit(".", 1)[-1]) == 3:
        raw = raw.replace(".", "")
    try:
        amount = Decimal(raw)
    except Exception:
        return None
    multiplier = (Decimal("1000000") if (match.group(2) or "").lower().startswith("milh")
                  else Decimal("1000") if match.group(2) else Decimal("1"))
    amount *= multiplier
    return amount if Decimal("0") < amount <= Decimal("1000000000") else None


def _channels(message: str) -> tuple[str, ...]:
    matches = []
    for pattern, label in _CHANNEL_PATTERNS:
        for match in re.finditer(pattern, message, re.I):
            if not any(match.start() < end and match.end() > start for start, end, _ in matches):
                matches.append((match.start(), match.end(), label))
    ordered = [label for _, _, label in sorted(matches)]
    return tuple(dict.fromkeys(ordered[:4])) or _CHANNELS


def _scenario_weights(count: int, explicit_channels: bool):
    if count == 1:
        return (("canal informado", (100,)),)
    if count == 2:
        return (("equilibrado", (50, 50)), ("foco no primeiro canal", (70, 30)),
                ("foco no segundo canal", (30, 70)))
    if count == 4:
        return (("equilibrado", (25, 25, 25, 25)), ("foco no primeiro canal", (45, 25, 20, 10)),
                ("foco no último canal", (10, 20, 25, 45)))
    if explicit_channels:
        return (("equilibrado", (40, 35, 25)), ("foco no primeiro canal", (55, 30, 15)),
                ("foco no último canal", (25, 30, 45)))
    return _SCENARIOS


def simulate(message: str) -> dict:
    """Return transparent examples for the requested channels, without forecasting."""
    budget = _amount(message)
    channels = _channels(message)
    scenarios_spec = _scenario_weights(len(channels), channels != _CHANNELS)
    scenarios = []
    for name, weights in scenarios_spec:
        allocations = []
        remaining = budget
        for index, (channel, percent) in enumerate(zip(channels, weights)):
            amount = None
            if budget is not None:
                amount = ((budget * Decimal(percent) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                          if index < len(weights) - 1 else remaining)
                remaining -= amount
            allocations.append({"channel": channel, "percent": percent,
                                "amount_brl": str(amount) if amount is not None else None})
        scenarios.append({"name": name, "allocations": allocations,
                          "total_percent": sum(weights),
                          "total_amount_brl": str(budget) if budget is not None else None})
    return {
        "status": "illustrative",
        "budget_brl": str(budget) if budget is not None else None,
        "channels": list(channels),
        "scenarios": scenarios,
        "assumptions": [
            "Distribuições exemplificativas, sem previsão de alcance, conversão ou retorno.",
            "Canais e percentuais devem ser ajustados ao objetivo, público, inventário e dados reais.",
            "Sem orçamento informado, os valores permanecem em percentuais.",
        ],
    }
