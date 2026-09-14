"""Agente de anatomia — quatro eixos, sem inventar marca."""

from ..creative_format_registry import entry


CONCEPTS = {
    "product-kv": ("logo", "product", "headline"),
    "lifestyle": ("lifestyle", "headline"),
    "packshot": ("product",),
    "event-kv": ("headline", "logo"),
}

TEMPLATES = {
    "product-left-type": ("product", "headline"),
    "overlay-card": ("headline", "cta"),
    "isolated-product": ("product",),
    "full-bleed-type": ("headline",),
}


def run(payload):
    payload = payload if isinstance(payload, dict) else {}
    catalog = payload.get("catalog") or {}
    item = entry(catalog.get("format_key") or payload.get("format_key"))
    found = list(payload.get("elements_found") or [])
    if not found:
        found = list((item or {}).get("required_elements") or [])
        if payload.get("has_piece"):
            found = list(found)
        else:
            found = []
    required = list((item or {}).get("required_elements") or [])
    missing = [role for role in required if role not in found]
    concept = _match(found, CONCEPTS) or payload.get("concept") or "product-kv"
    template = _match(found, TEMPLATES) or payload.get("template") or "product-left-type"
    level = "L1"
    if "lifestyle" in found:
        level = "L3"
    elif "product" in found and "headline" in found:
        level = "L2"
    if payload.get("network_chrome"):
        level = "L5"
    return {
        "status": "ok",
        "concept": concept,
        "template": template,
        "training_level": level,
        "elements_found": found,
        "missing_required": missing,
        "optional_missing": [
            role for role in (item or {}).get("optional_elements") or []
            if role not in found
        ],
        "reading_order": found or required,
        "defects": (
            [f"Falta {role}" for role in missing]
            if payload.get("has_piece")
            else []
        ),
    }


def _match(found, table):
    found_set = set(found)
    for name, needs in table.items():
        if set(needs).issubset(found_set):
            return name
    return None
