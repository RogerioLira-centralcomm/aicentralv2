"""Agente de placement — recusa combinação inválida."""

from ..creative_format_registry import compatibility, default_zone, entry


def run(payload):
    payload = payload if isinstance(payload, dict) else {}
    catalog = payload.get("catalog") or {}
    format_key = catalog.get("format_key") or payload.get("format_key")
    result = compatibility(
        format_key,
        channel=payload.get("channel"),
        device=payload.get("device"),
        zone=payload.get("zone") or payload.get("placement_zone"),
        viewer_slug=payload.get("viewer_slug"),
    )
    if result["status"] == "ok" and result.get("zone") is None:
        result["zone"] = default_zone(format_key, payload.get("device"))
    item = entry(format_key)
    if item:
        result["fit"] = item["fit"]
        result["width"] = item["width"]
        result["height"] = item["height"]
    return result
