"""Filtro leve da biblioteca da marca."""

from __future__ import annotations

from ..schemas import ASSET_KINDS


def filter_assets(rows, query="", kind="", provenance=""):
    wanted_kind = str(kind or "").strip()
    wanted_prov = str(provenance or "").strip()
    needle = str(query or "").strip().lower()
    found = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        if item.get("archived"):
            continue
        if wanted_kind and item.get("kind") != wanted_kind:
            continue
        if wanted_prov and item.get("provenance") != wanted_prov:
            continue
        if needle:
            hay = " ".join(
                [
                    str(item.get("name") or ""),
                    str(item.get("kind") or ""),
                    " ".join(item.get("tags") or []),
                ]
            ).lower()
            if needle not in hay:
                continue
        found.append(item)
    return found


def group_counts(rows):
    counts = {key: 0 for key in ASSET_KINDS}
    for item in rows or []:
        kind = item.get("kind")
        if kind in counts and not item.get("archived"):
            counts[kind] += 1
    return counts
