"""Conservative extraction of campaign metrics supplied in the current turn."""

from __future__ import annotations

import re


_METRIC = re.compile(
    r"\b(?P<name>impress[oõ]es|cliques?|ctr|cpc|cpm|convers[oõ]es|roas|"
    r"investimento|or[cç]amento|receita|vendas?|alcance|leads?)\b",
    re.IGNORECASE,
)
_VALUE = re.compile(r"(?<!\w)(?:R\$\s*)?(?P<number>\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)(?P<unit>\s*[%x])?(?!\w)", re.IGNORECASE)


def supplied_metrics(message: str) -> list[dict[str, str]]:
    """Find metric/value pairs; a campaign year alone is not performance data."""
    text = str(message or "")
    found = []
    for metric in _METRIC.finditer(text):
        tail = text[metric.end():metric.end() + 45]
        candidate = re.match(r"^\s*(?:[:=–—-]\s*|de\s+|foi\s+|em\s+)?", tail, re.I)
        offset = candidate.end() if candidate else 0
        value = _VALUE.match(tail[offset:])
        if not value:
            continue
        number = value.group("number").replace(" ", "")
        unit = (value.group("unit") or "").strip()
        if re.fullmatch(r"20\d{2}", number) and not unit and metric.group("name").lower() not in {"impressões", "impressoes", "cliques", "conversões", "conversoes", "vendas", "leads"}:
            continue
        found.append({"name": metric.group("name").lower(), "value": number, "unit": unit})
    return found
