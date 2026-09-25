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


def simulate(message: str) -> dict:
    """Return three transparent examples; no rate or outcome is inferred."""
    budget = _amount(message)
    scenarios = []
    for name, weights in _SCENARIOS:
        allocations = []
        remaining = budget
        for index, (channel, percent) in enumerate(zip(_CHANNELS, weights)):
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
        "scenarios": scenarios,
        "assumptions": [
            "Distribuições exemplificativas, sem previsão de alcance, conversão ou retorno.",
            "Canais e percentuais devem ser ajustados ao objetivo, público, inventário e dados reais.",
            "Sem orçamento informado, os valores permanecem em percentuais.",
        ],
    }
