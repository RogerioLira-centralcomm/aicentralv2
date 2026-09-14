"""Agente de catálogo — só o registry."""

from ..creative_format_registry import catalog_entries, entry, resolve_format_key


def run(payload):
    raw = (payload or {}).get("format_key") or (payload or {}).get("slug")
    key = resolve_format_key(raw)
    item = entry(key)
    if not item:
        return {
            "status": "blocked",
            "code": "PLACEMENT_NOT_DEFINED",
            "format_key": str(raw or ""),
            "message": "Formato sem registro canônico.",
        }
    data = dict(item)
    data["status"] = "ok"
    data["format_alias_received"] = str(raw or "")
    data["catalog_size"] = len(catalog_entries())
    return data
