"""Small, deterministic controls for a brand-scoped market radar search."""

from __future__ import annotations

import re

from .evidence import read_status


def requested_recency(message: str) -> str:
    """Map common Portuguese windows to the search adapter's supported enum."""
    text = str(message or "").casefold()
    if re.search(r"\b(?:hoje|últim[ao]s?\s+24\s*h(?:oras)?|ultim[ao]s?\s+24\s*h(?:oras)?)\b", text):
        return "day"
    if re.search(r"\b(?:esta semana|últim[ao]s?\s+(?:7\s+dias|semana)|ultim[ao]s?\s+(?:7\s+dias|semana))\b", text):
        return "week"
    if re.search(r"\b(?:este mês|este mes|últim[ao]s?\s+(?:30\s+dias|m[eê]s)|ultim[ao]s?\s+(?:30\s+dias|m[eê]s))\b", text):
        return "month"
    return "year"


def fallback_query(brand: dict) -> str:
    """Broaden one public search without sending private project context."""
    name = " ".join(str(brand.get("name") or "").split())[:100]
    market = brand.get("market") if isinstance(brand.get("market"), dict) else {}
    competitors = market.get("competitors") or []
    if isinstance(competitors, str):
        competitors = re.split(r"[,;\n]+", competitors)
    names = [" ".join(str(item.get("name") if isinstance(item, dict) else item or "").split())[:60]
             for item in competitors[:3]]
    entities = [item for item in [name, *names] if item]
    return (" ".join([*entities, "campanha lançamento notícia estudo de mercado"])[:400]
            if name else "")


def relevant_read_sources(brand: dict, search_result: dict) -> list[dict]:
    """Keep read pages naming the brand or a registered competitor."""
    market = brand.get("market") if isinstance(brand.get("market"), dict) else {}
    competitors = market.get("competitors") or []
    if isinstance(competitors, str):
        competitors = re.split(r"[,;\n]+", competitors)
    entities = [brand.get("name"), *(
        item.get("name") if isinstance(item, dict) else item for item in competitors
    )]
    patterns = [re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.I)
                for item in entities if (name := " ".join(str(item or "").split())) and len(name) >= 3]
    if not patterns:
        return []
    relevant = []
    for item in search_result.get("sources") or []:
        if not isinstance(item, dict) or read_status(item) != "read":
            continue
        body = " ".join(str(item.get(key) or "") for key in ("title", "excerpt", "content"))[:20_000]
        if any(pattern.search(body) for pattern in patterns):
            relevant.append(item)
    return relevant
