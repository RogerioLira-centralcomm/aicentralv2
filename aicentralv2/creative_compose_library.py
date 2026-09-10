"""Biblioteca viva do Estúdio: schema fechado, variação e promoção."""

from __future__ import annotations


APPROVE_PROMOTE_MIN = 3
APPROVE_PROMOTE_RATE = 0.60
REJECT_ARCHIVE_MIN = 3
REJECT_ARCHIVE_RATE = 0.40

LIBRARY_FAMILIES = frozenset({
    "square_1x1",
    "sequence_16x9",
    "rectangle",
    "wide_banner",
    "half_page",
    "story_9x16",
    "landscape_social",
    "slate_16x9",
})

LAYOUT_SQUARE_SCHEMA = {
    "headline_font_size": {"min": 22, "max": 32, "step": 2},
    "photo_side": ["left", "right"],
    "cta_gap": {"min": 8, "max": 16},
}
LAYOUT_STUDIO_SCHEMA = {
    "headline_font_size": {"min": 14, "max": 32, "step": 2},
    "cta_gap": {"min": 6, "max": 16},
}
SCRIPT_SEQUENCE_SCHEMA = {
    "scenography": ["line", "change"],
    "cast_count": [1, 2],
    "copy_on_last_only": [True, False],
}

FAMILY_SPECS = {
    "square_1x1": {
        "kind": "layout",
        "html_key": "square_1x1.html",
        "adjust_schema": LAYOUT_SQUARE_SCHEMA,
        "default_params": {
            "headline_font_size": 26,
            "photo_side": "right",
            "cta_gap": 12,
        },
    },
    "sequence_16x9": {
        "kind": "script",
        "html_key": "sequence_16x9.html",
        "adjust_schema": SCRIPT_SEQUENCE_SCHEMA,
        "default_params": {
            "scenography": "line",
            "cast_count": 1,
            "copy_on_last_only": True,
        },
    },
    "rectangle": {
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "default_params": {"headline_font_size": 18, "cta_gap": 8},
    },
    "wide_banner": {
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "default_params": {"headline_font_size": 16, "cta_gap": 6},
    },
    "half_page": {
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "default_params": {"headline_font_size": 20, "cta_gap": 10},
    },
    "story_9x16": {
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "default_params": {"headline_font_size": 28, "cta_gap": 12},
    },
    "landscape_social": {
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "default_params": {"headline_font_size": 22, "cta_gap": 10},
    },
    "slate_16x9": {
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "default_params": {"headline_font_size": 26, "cta_gap": 12},
    },
}

SEED_VARIATIONS = {
    "seed-square-right": {
        "id": "seed-square-right",
        "template_slug": "square-feed-v1",
        "name": "Foto à direita",
        "family": "square_1x1",
        "kind": "layout",
        "html_key": "square_1x1.html",
        "adjust_schema": LAYOUT_SQUARE_SCHEMA,
        "params": {
            "headline_font_size": 26,
            "photo_side": "right",
            "cta_gap": 12,
        },
        "status": "experimental",
        "approve_count": 0,
        "reject_count": 0,
        "preview_asset_url": None,
    },
    "seed-sequence-line": {
        "id": "seed-sequence-line",
        "template_slug": "netflix-script-v1",
        "name": "Gancho → Fechamento",
        "family": "sequence_16x9",
        "kind": "script",
        "html_key": "sequence_16x9.html",
        "adjust_schema": SCRIPT_SEQUENCE_SCHEMA,
        "params": {
            "scenography": "line",
            "cast_count": 1,
            "copy_on_last_only": True,
        },
        "status": "experimental",
        "approve_count": 0,
        "reject_count": 0,
        "preview_asset_url": None,
    },
    "seed-rectangle": {
        "id": "seed-rectangle",
        "template_slug": "iab-rectangle-v1",
        "name": "Mapa 300×250",
        "family": "rectangle",
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "params": {"headline_font_size": 18, "cta_gap": 8},
        "status": "experimental",
        "approve_count": 0,
        "reject_count": 0,
        "preview_asset_url": None,
    },
    "seed-wide-banner": {
        "id": "seed-wide-banner",
        "template_slug": "iab-banner-v1",
        "name": "Mapa faixa",
        "family": "wide_banner",
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "params": {"headline_font_size": 16, "cta_gap": 6},
        "status": "experimental",
        "approve_count": 0,
        "reject_count": 0,
        "preview_asset_url": None,
    },
    "seed-half-page": {
        "id": "seed-half-page",
        "template_slug": "iab-half-page-v1",
        "name": "Mapa 300×600",
        "family": "half_page",
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "params": {"headline_font_size": 20, "cta_gap": 10},
        "status": "experimental",
        "approve_count": 0,
        "reject_count": 0,
        "preview_asset_url": None,
    },
    "seed-story": {
        "id": "seed-story",
        "template_slug": "story-v1",
        "name": "Mapa 9:16",
        "family": "story_9x16",
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "params": {"headline_font_size": 28, "cta_gap": 12},
        "status": "experimental",
        "approve_count": 0,
        "reject_count": 0,
        "preview_asset_url": None,
    },
    "seed-landscape": {
        "id": "seed-landscape",
        "template_slug": "landscape-v1",
        "name": "Mapa paisagem",
        "family": "landscape_social",
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "params": {"headline_font_size": 22, "cta_gap": 10},
        "status": "experimental",
        "approve_count": 0,
        "reject_count": 0,
        "preview_asset_url": None,
    },
    "seed-slate": {
        "id": "seed-slate",
        "template_slug": "slate-v1",
        "name": "Mapa slate",
        "family": "slate_16x9",
        "kind": "layout",
        "html_key": "studio.html",
        "adjust_schema": LAYOUT_STUDIO_SCHEMA,
        "params": {"headline_font_size": 26, "cta_gap": 12},
        "status": "experimental",
        "approve_count": 0,
        "reject_count": 0,
        "preview_asset_url": None,
    },
}


def schema_for_family(family):
    spec = FAMILY_SPECS.get(str(family or ""))
    return dict((spec or {}).get("adjust_schema") or {})


def default_params_for_family(family):
    spec = FAMILY_SPECS.get(str(family or "")) or {}
    return dict(spec.get("default_params") or {})


def _as_number(value, default=0):
    try:
        if isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp_params(schema, params=None):
    schema = schema if isinstance(schema, dict) else {}
    incoming = params if isinstance(params, dict) else {}
    clamped = {}
    for key, rule in schema.items():
        raw = incoming.get(key)
        if isinstance(rule, dict) and "min" in rule and "max" in rule:
            minimum = _as_number(rule.get("min"))
            maximum = _as_number(rule.get("max"), minimum)
            step = _as_number(rule.get("step") or 1, 1) or 1
            current = _as_number(raw, minimum)
            current = min(maximum, max(minimum, current))
            steps = round((current - minimum) / step)
            current = minimum + steps * step
            current = min(maximum, max(minimum, current))
            clamped[key] = int(current) if float(current).is_integer() else current
        elif isinstance(rule, (list, tuple)) and rule:
            if raw in rule:
                clamped[key] = raw
            elif isinstance(raw, str) and raw.lower() in {
                str(item).lower() for item in rule if not isinstance(item, bool)
            }:
                clamped[key] = next(
                    item for item in rule
                    if str(item).lower() == raw.lower()
                )
            elif isinstance(raw, bool) and raw in rule:
                clamped[key] = raw
            else:
                clamped[key] = rule[0]
        else:
            clamped[key] = raw
    regions = sanitize_compose_regions(incoming.get("regions"))
    if regions:
        clamped["regions"] = regions
    return clamped


def sanitize_compose_regions(raw):
    """Mantém o mapa extraído (x/y/w/h em %) fora do schema numérico."""
    slots = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        tipo = str(item.get("tipo") or "").strip().lower()
        if not tipo:
            continue
        try:
            x = max(0.0, min(100.0, float(item.get("x") or 0)))
            y = max(0.0, min(100.0, float(item.get("y") or 0)))
            w = max(0.0, min(100.0, float(item.get("w") or 0)))
            h = max(0.0, min(100.0, float(item.get("h") or 0)))
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        slots.append({"tipo": tipo, "x": x, "y": y, "w": w, "h": h})
    return slots


def next_variation_status(approve_count, reject_count, current="experimental"):
    if current == "archived":
        return "archived"
    try:
        approved = int(approve_count or 0)
        rejected = int(reject_count or 0)
    except (TypeError, ValueError):
        approved, rejected = 0, 0
    total = approved + rejected
    if (
        rejected >= REJECT_ARCHIVE_MIN
        and total
        and (approved / total) < REJECT_ARCHIVE_RATE
    ):
        return "archived"
    if (
        approved >= APPROVE_PROMOTE_MIN
        and total
        and (approved / total) >= APPROVE_PROMOTE_RATE
    ):
        return "approved"
    return current if current in {"experimental", "approved"} else "experimental"


def suggest_variation(variations, family=None):
    rows = [item for item in (variations or []) if isinstance(item, dict)]
    if family:
        rows = [item for item in rows if item.get("family") == family]
    rows = [item for item in rows if item.get("status") != "archived"]
    if not rows:
        seed = next(
            (
                dict(item)
                for item in SEED_VARIATIONS.values()
                if not family or item["family"] == family
            ),
            None,
        )
        return seed
    rows.sort(
        key=lambda item: (
            0 if item.get("status") == "approved" else 1,
            -int(item.get("approve_count") or 0),
            str(item.get("id") or ""),
        )
    )
    return dict(rows[0])


def propose_variation_adjust(schema, params=None):
    schema = schema if isinstance(schema, dict) else {}
    current = clamp_params(schema, params)
    adjusted = dict(current)
    enums = [
        (key, rule) for key, rule in schema.items()
        if isinstance(rule, (list, tuple)) and len(rule) > 1
    ]
    ranges = [
        (key, rule) for key, rule in schema.items()
        if isinstance(rule, dict) and "min" in rule and "max" in rule
    ]
    for key, rule in enums + ranges:
        if isinstance(rule, (list, tuple)):
            value = current.get(key, rule[0])
            try:
                index = list(rule).index(value)
            except ValueError:
                index = 0
            adjusted[key] = rule[(index + 1) % len(rule)]
            return clamp_params(schema, adjusted)
        step = _as_number(rule.get("step") or 1, 1) or 1
        nxt = _as_number(current.get(key), rule.get("min")) + step
        if nxt > _as_number(rule.get("max"), nxt):
            nxt = _as_number(rule.get("min"))
        adjusted[key] = nxt
        return clamp_params(schema, adjusted)
    return current


def apply_script_params(design, params, scene_count=4):
    from .creative_construct_params import normalize_context_design

    merged = normalize_context_design(design, scene_count)
    clamped = clamp_params(SCRIPT_SEQUENCE_SCHEMA, params)
    merged["scenography"] = clamped["scenography"]
    merged["cast_count"] = clamped["cast_count"]
    if clamped.get("copy_on_last_only"):
        total = len(merged["scenes"])
        for scene in merged["scenes"]:
            scene["copy_on_frame"] = int(scene.get("position") or 0) >= total
    return merged


def tokens_from_brand_profile(profile):
    profile = profile if isinstance(profile, dict) else {}
    line = profile.get("creative_line") if isinstance(profile.get("creative_line"), dict) else {}
    palette = line.get("color_palette") or profile.get("color_palette") or []
    if not isinstance(palette, list):
        palette = []
    colors = []
    for item in palette[:8]:
        if isinstance(item, dict) and item.get("hex"):
            colors.append(str(item["hex"]))
        elif isinstance(item, str) and item.strip():
            colors.append(item.strip())
    fonts_raw = profile.get("fonts") or []
    if not isinstance(fonts_raw, list):
        fonts_raw = []
    display = None
    body = None
    for item in fonts_raw:
        if not isinstance(item, dict):
            continue
        family = str(item.get("family") or "").strip()
        role = str(item.get("role") or "").strip().lower()
        if not family:
            continue
        if role in {"display", "heading", "headline", "title"} and not display:
            display = family
        elif not body:
            body = family
        elif not display:
            display = family
    if not display and fonts_raw:
        first = fonts_raw[0]
        display = first.get("family") if isinstance(first, dict) else None
    return {
        "palette": colors or ["#1E4D4F"],
        "fonts": {"display": display, "body": body or display},
        "spacing": {"unit": 8, "cta_gap_max": 16},
    }


def normalize_compose_choice(variation, family=None):
    data = variation if isinstance(variation, dict) else {}
    resolved_family = str(data.get("family") or family or "")
    if resolved_family not in LIBRARY_FAMILIES:
        return None
    spec = FAMILY_SPECS[resolved_family]
    schema = data.get("adjust_schema") or spec["adjust_schema"]
    params = clamp_params(schema, data.get("params") or spec["default_params"])
    return {
        "variation_id": data.get("id"),
        "template_id": data.get("template_id"),
        "template_slug": data.get("template_slug") or "",
        "name": data.get("name") or "",
        "family": resolved_family,
        "kind": data.get("kind") or spec["kind"],
        "html_key": data.get("html_key") or spec["html_key"],
        "params": params,
        "status": data.get("status") or "experimental",
    }


def catalog_variations(family=None):
    rows = [dict(item) for item in SEED_VARIATIONS.values()]
    if family:
        rows = [item for item in rows if item["family"] == family]
    return rows


def resolve_variation(variation_id, family=None, repository=None):
    key = str(variation_id or "").strip()
    if key in SEED_VARIATIONS:
        return dict(SEED_VARIATIONS[key])
    if repository is not None and key.isdigit():
        getter = getattr(repository, "get_compose_variation", None)
        if callable(getter):
            try:
                row = getter(int(key))
            except Exception:
                row = None
            if isinstance(row, dict) and row.get("id") is not None:
                return row
    if repository is not None:
        suggester = getattr(repository, "suggest_compose_variation", None)
        if callable(suggester):
            try:
                row = suggester(family)
            except Exception:
                row = None
            if isinstance(row, dict) and row.get("id") is not None:
                return row
    return suggest_variation(catalog_variations(family), family)


def persisted_variation_id(variation_id):
    try:
        value = int(variation_id)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
