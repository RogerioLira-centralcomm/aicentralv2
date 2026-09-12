"""Campos que a campanha pode mudar. Identidade da marca fica travada."""

from __future__ import annotations

from datetime import datetime, timezone

from .schema import dump_system, parse_system

PROTECTED_TOKEN_IDS = (
    "paper",
    "ink",
    "accent",
    "highlight",
    "cta_ink",
    "muted",
    "font-display",
    "font-body",
    "logo",
    "type-headline",
    "type-support",
    "type-cta",
    "type-legal",
    "cta-radius",
    "cta-pad",
    "cta-shadow",
    "weight-display",
    "weight-cta",
    "tracking",
    "hairline",
)
MUTABLE_TRACKS = ("kv", "lifestyle")
PROTECTED_ROOT = ("dna", "status", "client_id", "logo_url", "framework")


def campaign_may_edit(path):
    text = str(path or "")
    if text in {"ad_copy", "creative_line", "archetype", "elements"}:
        return True
    if text.startswith("ad_copy."):
        return True
    if text in {"tokens.ground-kind", "tokens.ground", "tokens.overlay", "tokens.ground-fit"}:
        return True
    if text.startswith("tracks.") and any(f".{item}" in text or text.endswith(item) for item in MUTABLE_TRACKS):
        return True
    return False


def protected_token_ids():
    return PROTECTED_TOKEN_IDS


def drop_protected_token_payload(tokens):
    incoming = tokens if isinstance(tokens, dict) else {}
    kept = {}
    for key, value in incoming.items():
        if key in PROTECTED_TOKEN_IDS:
            continue
        if key in {"ground-kind", "ground", "overlay", "ground-fit", "wash-strength", "grain"}:
            kept[key] = value
    return kept


def lock_campaign_tokens(base_tokens, incoming=None):
    """Identidade da marca permanece. Só fundo/lavagem entram do incoming."""
    locked = dict(base_tokens or {})
    extra = drop_protected_token_payload(incoming)
    if extra.get("ground-kind") or extra.get("ground") is not None:
        from .components import apply_background

        locked = apply_background(
            locked,
            extra.get("ground-kind") or locked.get("ground-kind") or "paper",
            image_url=extra.get("ground"),
        )
    for key in ("overlay", "wash-strength", "grain", "ground-fit"):
        if extra.get(key) not in (None, ""):
            locked[key] = extra[key]
    return locked


def stamp_inheritance(system, brand, *, existing=False):
    parsed = parse_system(system)
    brand = parse_system(brand)
    data = dump_system(parsed)
    evidence = dict(data.get("evidence") or {})
    if existing:
        if not data.get("inherits_brand_id"):
            data["inherits_brand_id"] = brand.id
        if data.get("inherits_brand_version") in (None, ""):
            data["inherits_brand_version"] = "unknown"
        if data.get("inherits_brand_revision") in (None, ""):
            data["inherits_brand_revision"] = "unknown"
        link = "unknown" if str(data.get("inherits_brand_version") or "") == "unknown" else "snapshot"
        inherited_at = (evidence.get("inheritance") or {}).get("inherited_at") or ""
    else:
        from .revision import read_revision

        data["inherits_brand_id"] = brand.id
        data["inherits_brand_version"] = brand.version
        data["inherits_brand_revision"] = read_revision(brand)
        inherited_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        link = "snapshot"
    evidence["inheritance"] = {
        "brand_id": data.get("inherits_brand_id"),
        "brand_version": data.get("inherits_brand_version"),
        "brand_revision": data.get("inherits_brand_revision"),
        "inherited_at": inherited_at,
        "link": link,
    }
    data["evidence"] = evidence
    return parse_system(data)
