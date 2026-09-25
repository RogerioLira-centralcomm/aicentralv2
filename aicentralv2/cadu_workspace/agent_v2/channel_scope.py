"""Deterministic parsing and enforcement for user-selected media channels."""

from __future__ import annotations

import re
import unicodedata


_SCOPE_PATTERNS = (
    re.compile(r"\b(?:audi[eê]ncias?|p[uú]blicos?)\s+(?:(?:do|da|no|na)\s+)?(?!para\b)(.+?)"
               r"(?=\s+(?:para|por|com|em|entre|nas|nos)\b|[,;.!?]|$)", re.I),
    re.compile(r"\b(?:canal|plataforma)\s+(?:do|da|de)?\s*(.+?)"
               r"(?=\s+(?:para|por|com|em|entre|nas|nos)\b|[,;.!?]|$)", re.I),
    re.compile(r"\b(?:dentro|somente|apenas)\s+(?:do|da|no|na)\s+(.+?)"
               r"(?=\s+(?:para|por|com|em|entre|nas|nos)\b|[,;.!?]|$)", re.I),
)


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def requested_channel_scope(text: str) -> list[str]:
    """Extract channel(s) when the wording explicitly binds audiences to them."""
    text = str(text or "")
    candidates = []
    for pattern in _SCOPE_PATTERNS:
        candidates.extend((match.start(), match.group(1)) for match in pattern.finditer(text))
    for _position, candidate in sorted(candidates, key=lambda item: item[0], reverse=True):
        raw = re.sub(r"\s+(?:e|and)\s+", ",", candidate, flags=re.I)
        values = [part.strip(" \t\n\r:()[]{}\"'") for part in re.split(r"[,/&+]", raw)]
        values = [value[:60].strip() for value in values
                  if value and _normalized(value)
                  and _normalized(value) not in {"canais", "publico", "audiencia", "marca", "projeto"}
                  and not _normalized(value).startswith(("e canais", "da marca", "do projeto", "para a marca", "marca "))]
        if values:
            return list(dict.fromkeys(values))[:5]
    return []


def _matches_channel(name: str, requested: str) -> bool:
    actual, wanted = _normalized(name), _normalized(requested)
    if not actual or not wanted:
        return False
    return actual == wanted or actual.startswith(wanted + " ") or wanted.startswith(actual + " ")


def filter_channel_records(records: list[dict], requested: list[str]) -> tuple[list[dict], str]:
    """Keep only catalog records matching explicit user scope; never substitute."""
    if not requested:
        return records, "unrestricted"
    filtered = [row for row in records if any(_matches_channel(str(row.get("name") or ""), item)
                                               for item in requested)]
    return filtered, "matched" if filtered else "requested_channel_not_found"


def filter_scoped_records(records: list[dict], requested: list[str], fields: tuple[str, ...]) -> list[dict]:
    """Filter records that declare a platform, retaining unassociated generic rows."""
    if not requested:
        return records
    result = []
    for row in records:
        declared = [str(row.get(key) or "") for key in fields if row.get(key)]
        if not declared or any(_matches_channel(value, channel)
                               for value in declared for channel in requested):
            result.append(row)
    return result
