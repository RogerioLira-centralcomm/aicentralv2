"""Valida a cena 2.0. O iframe só recebe este JSON, nunca HTML do modelo."""

from __future__ import annotations

import re

from ..schemas import IMAGE_ROLES, TEXT_ROLES

SCHEMA_VERSION = "2.0"
LAYER_TYPES = ("image", "text")
BACKGROUND_TYPES = (
    "solid_color",
    "gradient",
    "original_image",
    "leftover_image",
    "generated_empty_well",
)
OPERATIONS = ("update", "hide", "show", "move", "resize", "replace", "reorder", "set_canvas")
TEXT_ALIGNS = ("left", "center", "right", "justify")
ASSET_PREFIX = "/static/uploads/camadas/"
_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_FONT = re.compile(r"^[A-Za-z0-9 ,.\-']+$")
_LAYER_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")

_TEXT_PROPS = ("text", "x", "y", "width", "height", "z_index", "visible", "rotation", "label", "style")
_IMAGE_PROPS = ("x", "y", "width", "height", "z_index", "visible", "rotation", "label", "asset_path", "asset_id")
_STYLE_PROPS = (
    "font_family",
    "font_size",
    "font_weight",
    "line_height",
    "letter_spacing",
    "color",
    "text_align",
)
_CANVAS_PROPS = ("width", "height", "aspect_ratio", "background", "background_type")


def sanitize_scene(raw):
    data = raw if isinstance(raw, dict) else {}
    canvas = sanitize_canvas(data.get("canvas"))
    return {
        "schema_version": SCHEMA_VERSION,
        "creative_id": _plain(data.get("creative_id"), 80),
        "canvas": canvas,
        "layers": sanitize_layers(data.get("layers")),
    }


def sanitize_canvas(raw):
    data = raw if isinstance(raw, dict) else {}
    background = _background(data.get("background"))
    kind = str(data.get("background_type") or "").strip()
    if kind not in BACKGROUND_TYPES:
        kind = "solid_color" if _COLOR.match(background or "") else "leftover_image"
    width = _int(data.get("width"), 0, 0, 20000)
    height = _int(data.get("height"), 0, 0, 20000)
    ratio = str(data.get("aspect_ratio") or "").strip()
    if ratio not in {"16:9", "9:16", "1:1", "4:5"}:
        ratio = "16:9" if width > height else "9:16" if height > width else "1:1"
    return {
        "width": width,
        "height": height,
        "aspect_ratio": ratio,
        "background": background,
        "background_type": kind,
    }


def sanitize_layers(raw):
    layers = []
    seen = set()
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        layer = sanitize_layer(item)
        if not layer or layer["id"] in seen:
            continue
        seen.add(layer["id"])
        layers.append(layer)
    return sorted(layers, key=lambda item: int(item.get("z_index") or 0))


def sanitize_layer(raw):
    data = raw if isinstance(raw, dict) else {}
    layer_id = str(data.get("id") or "").strip()
    if not _LAYER_ID.match(layer_id):
        return None
    layer_type = data.get("type") if data.get("type") in LAYER_TYPES else None
    role = str(data.get("role") or "").strip()
    if layer_type == "text" and role not in TEXT_ROLES:
        return None
    if layer_type == "image" and role not in IMAGE_ROLES:
        return None
    if not layer_type:
        return None
    layer = {
        "id": layer_id,
        "type": layer_type,
        "role": role,
        "label": _plain(data.get("label"), 200),
        "x": _optional_pct(data.get("x")),
        "y": _optional_pct(data.get("y")),
        "width": _optional_pct(data.get("width")),
        "height": _optional_pct(data.get("height")),
        "z_index": _int(data.get("z_index"), 0, -1000, 10000),
        "visible": data.get("visible") is not False,
        "rotation": _number(data.get("rotation"), 0, -180, 180),
    }
    if layer_type == "text":
        layer["text"] = _plain(data.get("text"), 2000)
        layer["layout_status"] = "placed" if _placed(layer) else "unplaced"
        layer["style"] = sanitize_style(data.get("style"))
    else:
        layer["asset_path"] = _asset_path(data.get("asset_path"))
        layer["asset_id"] = _plain(data.get("asset_id"), 80)
    return layer


def sanitize_style(raw):
    data = raw if isinstance(raw, dict) else {}
    family = str(data.get("font_family") or "Arial, sans-serif")
    if not _FONT.match(family) or re.search(r"url|expression|@import", family, re.I):
        family = "Arial, sans-serif"
    align = data.get("text_align") if data.get("text_align") in TEXT_ALIGNS else "left"
    color = str(data.get("color") or "#FFFFFF")
    if not _COLOR.match(color):
        color = "#FFFFFF"
    return {
        "font_family": family[:80],
        "font_size": _number(data.get("font_size"), 32, 8, 240),
        "font_weight": _int(data.get("font_weight"), 400, 100, 900),
        "line_height": _number(data.get("line_height"), 1.05, 0.7, 2.5),
        "letter_spacing": _number(data.get("letter_spacing"), 0, -0.2, 1),
        "color": color,
        "text_align": align,
    }


def sanitize_operations(raw):
    operations = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("operation") or "").strip()
        if kind not in OPERATIONS:
            raise ValueError("Operação da cena inválida.")
        layer_id = str(item.get("layer_id") or "").strip()
        if kind != "set_canvas" and not _LAYER_ID.match(layer_id):
            raise ValueError("Camada da cena inválida.")
        properties = item.get("properties") if isinstance(item.get("properties"), dict) else {}
        operations.append({
            "operation": kind,
            "layer_id": layer_id,
            "properties": _operation_props(kind, properties),
        })
    if not operations:
        raise ValueError("Envie operações da cena.")
    return operations


def _operation_props(kind, properties):
    if kind == "set_canvas":
        return {key: properties[key] for key in _CANVAS_PROPS if key in properties}
    if kind in {"hide", "show"}:
        return {}
    allowed = _IMAGE_PROPS + _TEXT_PROPS
    clean = {}
    for key, value in properties.items():
        if key == "style" and isinstance(value, dict):
            clean["style"] = {item: value[item] for item in _STYLE_PROPS if item in value}
            continue
        if key in allowed:
            clean[key] = value
    return clean


def _plain(value, limit):
    return str(value or "").replace("\x00", "")[:limit]


def _background(value):
    text = str(value or "").strip()
    if _COLOR.match(text):
        return text.upper() if len(text) == 7 else text
    if text.startswith(ASSET_PREFIX) and ".." not in text:
        return text
    return "#000000"


def _asset_path(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(ASSET_PREFIX) and ".." not in text and "<" not in text:
        return text
    return ""


def _optional_pct(value):
    if value in (None, ""):
        return None
    return _number(value, None, 0, 100)


def _placed(layer):
    return any(layer.get(key) not in (None, "") for key in ("x", "y", "width", "height"))


def _int(value, default, minimum, maximum):
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _number(value, default, minimum, maximum):
    if value in (None, ""):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))
