"""Small, deterministic controls for a brand-scoped market radar search."""

from __future__ import annotations

import re


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
