"""Monta a cena 2.0 a partir da leitura. Sem HTML arbitrário."""

from __future__ import annotations

from .sanitizer import sanitize_scene
from ..schemas import TEXT_ROLES

_ROLE_LABELS = {
    "headline": "Headline",
    "support": "Apoio",
    "subtitle": "Subtítulo",
    "price": "Preço",
    "cta": "CTA",
    "legal": "Texto legal",
    "date": "Data",
    "venue": "Local",
    "person_label": "Selo",
    "logo_text": "Logo",
}

_OCR_FIELDS = (
    ("headline", "headline"),
    ("support", "support"),
    ("subtitle", "subtitle"),
    ("price", "price"),
    ("cta", "cta"),
    ("disclaimer", "legal"),
    ("dates", "date"),
    ("venue", "venue"),
    ("logo_text", "logo_text"),
)


def empty_scene(creative_id, width=0, height=0, background="#000000"):
    return {
        "schema_version": "2.0",
        "creative_id": creative_id,
        "canvas": {
            "width": int(width or 0),
            "height": int(height or 0),
            "aspect_ratio": aspect_ratio(width, height),
            "background": background or "#000000",
        },
        "layers": [],
    }


def aspect_ratio(width, height):
    width = int(width or 0)
    height = int(height or 0)
    if width <= 0 or height <= 0:
        return "1:1"
    ratio = width / height
    if ratio >= 1.45:
        return "16:9"
    if ratio <= 0.75:
        return "9:16"
    return "1:1"


def build_scene(creative_id, reading=None, elements=None, width=0, height=0):
    parsed = reading if isinstance(reading, dict) else {}
    scene = empty_scene(creative_id, width, height, background="#000000")
    layers = []
    z_index = 10
    for item in elements or []:
        if not isinstance(item, dict):
            continue
        if item.get("layer_type") == "image":
            layers.append(_image_layer(item))
            if item.get("role") == "background":
                meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                if meta.get("field"):
                    scene["canvas"]["background"] = meta["field"]
            continue
        if item.get("layer_type") != "text":
            continue
        text = str(item.get("text_content") or "").strip()
        if not text:
            continue
        layers.append(
            _text_layer(
                item.get("role") or "support",
                text,
                item.get("z_index") or z_index,
                box=item.get("bbox") if isinstance(item.get("bbox"), dict) else {},
                layer_id=item.get("public_id"),
                label=item.get("label"),
                visible=item.get("visible") is not False,
            )
        )
        z_index += 10
    for field, role in _OCR_FIELDS:
        text = str(parsed.get(field) or "").strip()
        if not text or role not in TEXT_ROLES:
            continue
        if _has_text_role(layers, role):
            continue
        layers.append(_text_layer(role, text, z_index, box=_box_from_read(parsed, role)))
        z_index += 10
    for item in parsed.get("elements") or []:
        if not isinstance(item, dict) or item.get("role") != "person":
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if any(layer.get("role") == "person_label" and layer.get("text") == text for layer in layers):
            continue
        layers.append(
            _text_layer(
                "person_label",
                text,
                z_index,
                box=_box_from_item(item),
                label="Selo",
            )
        )
        z_index += 10
    scene["layers"] = layers
    return sanitize_scene(scene)


def merge_scene(existing, built):
    incoming = sanitize_scene(built if isinstance(built, dict) else {})
    previous = existing if isinstance(existing, dict) else {}
    by_id = {
        item["id"]: item
        for item in previous.get("layers") or []
        if isinstance(item, dict) and item.get("id")
    }
    merged = []
    for layer in incoming.get("layers") or []:
        prev = by_id.get(layer["id"])
        if not prev:
            merged.append(layer)
            continue
        keep = dict(layer)
        keep["x"] = prev.get("x", layer.get("x"))
        keep["y"] = prev.get("y", layer.get("y"))
        keep["width"] = prev.get("width", layer.get("width"))
        keep["height"] = prev.get("height", layer.get("height"))
        keep["rotation"] = prev.get("rotation", layer.get("rotation"))
        keep["visible"] = prev.get("visible", layer.get("visible"))
        if layer.get("type") == "text":
            keep["text"] = prev.get("text", layer.get("text"))
            keep["style"] = prev.get("style") or layer.get("style")
        else:
            keep["asset_path"] = layer.get("asset_path") or prev.get("asset_path")
        merged.append(keep)
    canvas = dict(incoming.get("canvas") or {})
    prev_canvas = previous.get("canvas") if isinstance(previous.get("canvas"), dict) else {}
    if prev_canvas.get("background"):
        canvas["background"] = prev_canvas["background"]
    if prev_canvas.get("background_type"):
        canvas["background_type"] = prev_canvas["background_type"]
    incoming["canvas"] = canvas
    incoming["layers"] = merged
    return sanitize_scene(incoming)


def text_elements_from_reading(reading):
    parsed = reading if isinstance(reading, dict) else {}
    rows = []
    z_index = 10
    for field, role in _OCR_FIELDS:
        text = str(parsed.get(field) or "").strip()
        if not text:
            continue
        rows.append(
            {
                "role": role,
                "label": _ROLE_LABELS.get(role, role),
                "layer_type": "text",
                "text_content": text,
                "bbox": _box_from_read(parsed, role),
                "quality": "unplaced" if not _has_box(_box_from_read(parsed, role)) else "placed",
                "provenance": "html",
                "z_index": z_index,
            }
        )
        z_index += 10
    for item in parsed.get("elements") or []:
        if not isinstance(item, dict) or item.get("role") != "person":
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        box = _box_from_item(item)
        rows.append(
            {
                "role": "person_label",
                "label": "Selo",
                "layer_type": "text",
                "text_content": text,
                "bbox": box,
                "quality": "unplaced" if not _has_box(box) else "placed",
                "provenance": "html",
                "z_index": z_index,
            }
        )
        z_index += 10
    return rows


def _image_layer(item):
    box = item.get("bbox") if isinstance(item.get("bbox"), dict) else {}
    return {
        "id": item.get("public_id") or f"layer-{item.get('role')}-{item.get('z_index')}",
        "type": "image",
        "role": item.get("role"),
        "label": item.get("label") or "",
        "asset_id": item.get("public_id") or "",
        "asset_path": item.get("png_path") or "",
        "x": box.get("x", 0),
        "y": box.get("y", 0),
        "width": box.get("w") or box.get("width") or 100,
        "height": box.get("h") or box.get("height") or 100,
        "z_index": int(item.get("z_index") or 0),
        "visible": item.get("visible") is not False,
        "rotation": 0,
    }


def _text_layer(role, text, z_index, box=None, layer_id=None, label=None, visible=True):
    box = box if isinstance(box, dict) else {}
    placed = _has_box(box)
    return {
        "id": layer_id or f"layer-{role}-{z_index}",
        "type": "text",
        "role": role,
        "label": label or _ROLE_LABELS.get(role, role),
        "text": text,
        "x": box.get("x"),
        "y": box.get("y"),
        "width": box.get("w") or box.get("width"),
        "height": box.get("h") or box.get("height"),
        "z_index": int(z_index or 0),
        "visible": visible is not False,
        "rotation": 0,
        "layout_status": "placed" if placed else "unplaced",
        "style": {
            "font_family": "Arial, sans-serif",
            "font_size": 32,
            "font_weight": 700 if role in {"headline", "price", "cta"} else 400,
            "line_height": 1.05,
            "letter_spacing": 0,
            "color": "#FFFFFF",
            "text_align": "left",
        },
    }


def _box_from_read(parsed, role):
    boxes = parsed.get("boxes") if isinstance(parsed.get("boxes"), dict) else {}
    raw = boxes.get(role)
    return raw if isinstance(raw, dict) else {}


def _box_from_item(item):
    if isinstance(item.get("bbox"), dict):
        return item["bbox"]
    bbox_px = item.get("bbox_px")
    if isinstance(bbox_px, (list, tuple)) and len(bbox_px) == 4:
        return {"bbox_px": list(bbox_px)}
    return {}


def _has_text_role(layers, role):
    return any(layer.get("type") == "text" and layer.get("role") == role for layer in layers)


def _has_box(box):
    if not isinstance(box, dict):
        return False
    return any(box.get(key) not in (None, "") for key in ("x", "y", "w", "width", "h", "height", "bbox_px"))
