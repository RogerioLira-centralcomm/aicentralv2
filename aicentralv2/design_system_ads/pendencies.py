"""Pendências por formato. Lista derivada — não é job."""

from __future__ import annotations

from .adapt import list_iab_formats
from .copy import compute_needs_input, is_house_copy_system, needs_input_label
from .fidelity import missing_required_tracks
from .provenance import needs_confirmation
from .schema import parse_system
from .validate import build_validation_report

STATES = ("needs_input", "missing_track", "needs_confirm", "stale", "ok")
DETAILS = {
    "needs_input": "Falta dado da marca.",
    "missing_track": "Falta trilha.",
    "needs_confirm": "Confirme a tinta.",
    "stale": "Contrato mudou.",
    "ok": "",
}


def brand_blocker(system):
    parsed = parse_system(system)
    waiting = compute_needs_input(parsed)
    if waiting:
        return "needs_input", needs_input_label(waiting)
    if not is_house_copy_system(parsed):
        missing = missing_required_tracks(parsed)
        if missing:
            return "missing_track", f"Falta a trilha {missing[0]}."
    if needs_confirmation(parsed):
        return "needs_confirm", DETAILS["needs_confirm"]
    return "", ""


def format_pendency(system, format_key, *, report=None):
    parsed = parse_system(system)
    waiting = compute_needs_input(parsed)
    if waiting:
        return "needs_input", needs_input_label(waiting)
    current = report or build_validation_report(parsed)
    key = str(format_key or "")
    state = (current.formats or {}).get(key) or "unchecked"
    checked = key in set(current.checked_formats or [])
    if current.render == "failed" and checked:
        return "stale", "O specimen falhou."
    if state == "stale":
        return "stale", DETAILS["stale"]
    blocker, detail = brand_blocker(parsed)
    if blocker and blocker != "needs_input":
        return blocker, detail
    if state == "ok":
        return "ok", ""
    return "", ""


def list_pendencies(system, *, report=None):
    parsed = parse_system(system)
    current = report or build_validation_report(parsed)
    items = []
    for row in list_iab_formats():
        key = str(row.get("key") or "")
        if not key:
            continue
        state, detail = format_pendency(parsed, key, report=current)
        if not state or state == "ok":
            continue
        items.append(
            {
                "format": key,
                "label": row.get("label") or row.get("size_label") or key,
                "size_label": row.get("size_label") or "",
                "state": state,
                "detail": detail,
            }
        )
    return items


def attach_pendencies(payload, system, *, report=None):
    data = payload if isinstance(payload, dict) else {}
    items = list_pendencies(system, report=report)
    data["pendencies"] = items
    catalog = data.get("catalog")
    if isinstance(catalog, dict):
        catalog["pendencies"] = items
    by_key = {item["format"]: item["state"] for item in items}
    if isinstance(catalog, dict) and isinstance(catalog.get("iab_formats"), list):
        catalog["iab_formats"] = [
            {
                **item,
                "pending": by_key.get(item.get("key"))
                or ("ok" if item.get("valid") == "ok" else ""),
            }
            for item in catalog["iab_formats"]
            if isinstance(item, dict)
        ]
        data["iab_formats"] = catalog["iab_formats"]
    return data
