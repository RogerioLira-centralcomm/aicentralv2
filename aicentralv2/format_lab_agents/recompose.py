"""Recomposição: o que permanece, some ou é reescrito. Sem resize."""

from ..creative_format_registry import entry


DENSITY_DROP = {
    "compact": ("product", "lifestyle", "support", "legal"),
    "standard": ("legal",),
    "rich": (),
}


def run(payload):
    payload = payload if isinstance(payload, dict) else {}
    item = entry((payload.get("catalog") or {}).get("format_key") or payload.get("format_key"))
    if not item:
        return {"status": "blocked", "code": "PLACEMENT_NOT_DEFINED"}
    drop = list(DENSITY_DROP.get(item["density"], ()))
    preserve = [
        role for role in item["required_elements"] + item["optional_elements"]
        if role not in drop
    ]
    return {
        "status": "ok",
        "format_key": item["format_key"],
        "density": item["density"],
        "preserve": preserve,
        "drop": drop,
        "rewrite": ["headline"] if item["density"] == "compact" else [],
        "siblings": list((item.get("recomposition_rules") or {}).get("siblings") or []),
        "resize": False,
    }
