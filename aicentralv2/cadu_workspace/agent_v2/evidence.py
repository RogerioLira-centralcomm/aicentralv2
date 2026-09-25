"""Provider-neutral checks for claims grounded in source text.

Discovery metadata is useful for finding pages, but only a successful read can
support a factual claim. These checks deliberately do not infer truth from an
LLM's confidence or from a URL appearing in a search result.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalized_text(value: Any) -> str:
    """Normalize harmless formatting differences for literal quote checks."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    return " ".join(text.split()).casefold()


def quote_in_source(quote: Any, content: Any) -> bool:
    """True only when a meaningful quoted span occurs in read content."""
    expected = normalized_text(quote)
    actual = normalized_text(content)
    return len(expected) >= 12 and bool(actual) and expected in actual


def read_status(source: dict) -> str:
    """Distinguish a page read from a search hit or failed extraction."""
    if not isinstance(source, dict):
        return "unavailable"
    if source.get("quality_gate") in {"failed", "rejected"}:
        return "unavailable"
    if str(source.get("content") or "").strip() or source.get("content_blocks"):
        return "read"
    return "discovered"


def grounded_claims(claims: Any, source_contents: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """Keep extracted claims only when their literal quote exists in that source."""
    accepted: list[dict] = []
    rejected: list[dict] = []
    for item in claims if isinstance(claims, list) else []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "")
        claim = str(item.get("claim") or "").strip()
        quote = str(item.get("quote") or "").strip()
        if source_id not in source_contents:
            reason = "source_not_read"
        elif not claim:
            reason = "empty_claim"
        elif not quote_in_source(quote, source_contents[source_id]):
            reason = "quote_not_found"
        else:
            accepted.append(item)
            continue
        rejected.append({"source_id": source_id, "reason": reason})
    return accepted, rejected
