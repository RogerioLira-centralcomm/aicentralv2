"""DS Ads adaptativo: formatos IAB + pilha de 4 a 40 camadas sobrepostas."""

from __future__ import annotations

from ..creative_format_lab.catalog import FORMATS, decorate_format, format_entry
from .components import component_of, density_for, should_park
from .layouts import (
    box_from_recipe,
    fan_in_well,
    recipe_for,
)
from .schema import dump_system, parse_system

MIN_LAYERS = 4
MAX_LAYERS = 40
REF_CANVAS = (1920, 1080)
MIN_SAFE_PX = 8
COPY_ROLES = {"logo", "headline", "support", "cta", "legal", "icon", "chip"}
BLEED_ROLES = {"ground", "visual", "product"}

COMPOSE_FAMILY = {
    "iab-horizontal": "wide_banner",
    "iab-box": "rectangle",
    "iab-vertical": "half_page",
    "horizontal-15": "slate_16x9",
    "social-square": "square_1x1",
    "social-portrait": "portrait_4x5",
    "social-story": "story_9x16",
    "social-landscape": "landscape_social",
}

CORE_ROLES = ("visual", "logo", "headline", "cta")
EXTRA_ROLES = (
    "visual",
    "support",
    "product",
    "legal",
    "icon",
    "chip",
)
ORNAMENT_ROLES = tuple(f"ornament-{index}" for index in range(1, 32))

ROLE_LABELS = {
    "ground": "fundo",
    "visual": "visual",
    "logo": "logo",
    "headline": "headline",
    "cta": "cta",
    "support": "apoio",
    "product": "produto",
    "legal": "legal",
    "icon": "ícone",
    "chip": "selo",
}


def clamp_layer_count(value):
    try:
        return max(MIN_LAYERS, min(MAX_LAYERS, int(value)))
    except (TypeError, ValueError):
        return MIN_LAYERS


def list_iab_formats():
    rows = []
    for item in FORMATS:
        if item.get("kind") != "banner" and not str(item.get("key") or "").startswith("iab-"):
            continue
        entry = decorate_format(item)
        canvas = entry.get("canvas") or {}
        rows.append(
            {
                "key": entry["key"],
                "label": entry.get("label") or entry["key"],
                "size_label": entry.get("size_label") or "",
                "family": entry.get("family"),
                "compose_family": compose_family_of(entry),
                "width": int(canvas.get("width") or 0),
                "height": int(canvas.get("height") or 0),
                "orientation": entry.get("orientation"),
            }
        )
    return rows


def compose_family_of(entry):
    item = entry if isinstance(entry, dict) else {}
    mapped = COMPOSE_FAMILY.get(str(item.get("family") or ""))
    if mapped:
        return mapped
    adapter = str(item.get("adapter") or "")
    if adapter == "iab_horizontal":
        return "wide_banner"
    if adapter == "iab_vertical":
        return "half_page"
    if adapter == "iab_box":
        return "rectangle"
    return "wide_banner"


def resolve_iab_format(format_key):
    entry = format_entry(format_key)
    if not entry:
        entry = format_entry("iab-billboard")
    return decorate_format(entry) if entry else None


def roles_for_count(count):
    number = clamp_layer_count(count)
    roles = list(CORE_ROLES)
    for role in EXTRA_ROLES + ORNAMENT_ROLES:
        if len(roles) >= number:
            break
        if role not in roles:
            roles.append(role)
    return roles[:number]


def adapt_type_scale(tokens, format_entry_data, recipe=None):
    tokens = tokens if isinstance(tokens, dict) else {}
    canvas = (format_entry_data or {}).get("canvas") or {}
    width = int(canvas.get("width") or REF_CANVAS[0])
    height = int(canvas.get("height") or REF_CANVAS[1])
    family = compose_family_of(format_entry_data)
    recipe = recipe or recipe_for((format_entry_data or {}).get("key"), family)
    floors = recipe.get("type") or {"headline": 16, "support": 11, "cta": 12, "legal": 9}
    adapted = dict(tokens)
    for key in ("headline", "support", "cta", "legal"):
        box = box_from_recipe(recipe.get(key))
        ceiling = floors[key]
        if box:
            box_px = height * box["h"] / 100
            lines = 1 if recipe.get("density") == "thin" or key in {"cta", "legal"} else 2
            ceiling = min(ceiling, max(8, int(box_px / (1.15 * lines))))
        adapted[f"type-{key}"] = f"{max(8, ceiling)}px"
    inset = safe_inset(width, height, family)
    adapted["safe"] = f"{inset['pct']}%"
    return adapted


def safe_inset(width, height, family="wide_banner"):
    width = max(1, int(width or 1))
    height = max(1, int(height or 1))
    if height <= 50:
        pct = 3.0
    elif height <= 90:
        pct = 4.0
    elif width <= 160:
        pct = 5.0
    elif family in {"slate_16x9", "story_9x16"}:
        pct = 6.0
    else:
        pct = 5.0
    pad_x = max(MIN_SAFE_PX / width * 100, pct)
    pad_y = max(MIN_SAFE_PX / height * 100, pct)
    return {
        "pct": round(min(pad_x, pad_y), 2),
        "x": round(pad_x, 2),
        "y": round(pad_y, 2),
    }


def _clamp_box(box, min_size=1.2):
    width = min(100.0, max(min_size, float(box["w"])))
    height = min(100.0, max(min_size, float(box["h"])))
    x = min(100.0 - width, max(0.0, float(box["x"])))
    y = min(100.0 - height, max(0.0, float(box["y"])))
    return {"x": round(x, 2), "y": round(y, 2), "w": round(width, 2), "h": round(height, 2)}


def build_layer_stack(system, format_key, layer_count=MIN_LAYERS):
    parsed = parse_system(system)
    entry = resolve_iab_format(format_key)
    if not entry:
        raise ValueError("Formato IAB não encontrado.")
    canvas = entry.get("canvas") or {}
    width = int(canvas.get("width") or 0)
    height = int(canvas.get("height") or 0)
    family = compose_family_of(entry)
    inset = safe_inset(width, height, family)
    recipe = recipe_for(entry.get("key"), family)
    density = density_for(entry.get("key"), recipe.get("density"))
    parked = set(recipe.get("park") or ())
    well = box_from_recipe(recipe["well"])
    copy = parsed.ad_copy or {}
    count = clamp_layer_count(layer_count)
    roles = roles_for_count(count)
    extras = [role for role in roles if role.startswith("ornament") or role == "product"]
    layers = []
    ornament_index = 0
    for order, role in enumerate(roles):
        parked_role = role in parked or (
            should_park(role, density) and role not in CORE_ROLES
        )
        text = ""
        if role == "ground":
            box, z = {"x": 0, "y": 0, "w": 100, "h": 100}, 1
        elif role == "visual":
            box, z = box_from_recipe(recipe["visual"]), 2
        elif role == "product":
            box, z = fan_in_well(well, ornament_index, max(len(extras), 1)), 4
            ornament_index += 1
        elif role == "logo":
            box, z = box_from_recipe(recipe["logo"]), 40
        elif role == "headline":
            box, z = box_from_recipe(recipe["headline"]), 41
            text = copy.get("headline") or ""
        elif role == "support":
            box, z = box_from_recipe(recipe["support"]), 42
            text = "" if parked_role else (copy.get("support") or "")
        elif role == "cta":
            box, z = box_from_recipe(recipe["cta"]), 43
            text = copy.get("cta") or ""
        elif role == "legal":
            box, z = box_from_recipe(recipe["legal"]), 44
            text = "" if parked_role else (copy.get("legal") or "")
        elif role == "icon":
            box, z = box_from_recipe(recipe["icon"]), 18
        elif role == "chip":
            box, z = box_from_recipe(recipe["chip"]), 19
        else:
            box, z = fan_in_well(well, ornament_index, max(len(extras), 1)), 5 + min(ornament_index, 14)
            ornament_index += 1
        if parked_role:
            box = fan_in_well(well, ornament_index, max(len(extras) + 4, 1))
            z = min(z, 16)
            ornament_index += 1
            text = ""
        layer = {
            "id": f"layer-{role}",
            "role": role,
            "label": ROLE_LABELS.get(role, "recorte"),
            "z": z,
            "overlap": role not in {"ground", "logo", "headline", "cta"},
            "text": text,
            "parked": parked_role,
            "priority": component_of(role).get("priority", 3),
            **_clamp_box(box),
        }
        layer["order"] = order
        if role in BLEED_ROLES:
            layer["bleed"] = True
        layers.append(layer)
    return {
        "format": {
            "key": entry["key"],
            "label": entry.get("label") or entry["key"],
            "size_label": entry.get("size_label") or f"{width}×{height}",
            "family": entry.get("family"),
            "compose_family": family,
            "width": width,
            "height": height,
            "density": recipe.get("density") or "wide",
            "density_tier": density,
        },
        "safe": inset,
        "well": well,
        "layer_count": count,
        "layers": layers,
        "tokens": adapt_type_scale(parsed.tokens, entry, recipe),
    }


def swap_layer_positions(stack, first_id, second_id):
    data = dict(stack or {})
    layers = [dict(item) for item in (data.get("layers") or [])]
    left = next((item for item in layers if item.get("id") == first_id), None)
    right = next((item for item in layers if item.get("id") == second_id), None)
    if not left or not right:
        raise ValueError("Escolha duas camadas para trocar de posição.")
    for key in ("x", "y", "w", "h"):
        left[key], right[key] = right[key], left[key]
    data["layers"] = layers
    return data


def apply_layer_swaps(stack, swaps):
    current = dict(stack or {})
    for pair in swaps or []:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        current = swap_layer_positions(current, pair[0], pair[1])
    return current


def adapt_system(system, format_key="iab-billboard", layer_count=MIN_LAYERS, swaps=None):
    parsed = parse_system(system)
    if layer_count in (None, "") and parsed.elements:
        from .campaign import layer_count_from_elements

        layer_count = layer_count_from_elements(parsed.elements)
    stack = build_layer_stack(parsed, format_key, layer_count)
    if parsed.elements:
        from .campaign import apply_elements_to_stack

        stack = apply_elements_to_stack(stack, parsed.elements)
    if swaps:
        stack = apply_layer_swaps(stack, swaps)
    data = dump_system(parsed)
    data["tokens"] = stack["tokens"]
    adapted = parse_system(data)
    return adapted, stack
