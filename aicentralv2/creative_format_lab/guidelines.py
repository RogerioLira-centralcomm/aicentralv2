"""Margem segura de TV e regras do still que será enviado."""

from __future__ import annotations

CANVAS = (1920, 1080)
SAFE_PCT = 6
REQUIRED = {
    "hook": ("background", "headline"),
    "brand": ("background", "logo", "headline"),
    "benefit": ("background", "headline"),
    "product": ("background", "product"),
    "proof": ("background", "headline"),
    "lifestyle": ("background", "headline"),
    "cta": ("background", "logo", "cta"),
}


def safe_rect(width=None, height=None, inset=SAFE_PCT):
    width = int(width or CANVAS[0])
    height = int(height or CANVAS[1])
    pad_x = int(round(width * inset / 100))
    pad_y = int(round(height * inset / 100))
    return {
        "x": pad_x,
        "y": pad_y,
        "w": width - pad_x * 2,
        "h": height - pad_y * 2,
        "inset": inset,
        "canvas": [width, height],
    }


def percent_box(x, y, w, h, width=None, height=None):
    width = int(width or CANVAS[0])
    height = int(height or CANVAS[1])
    return {
        "x": int(round(width * float(x) / 100)),
        "y": int(round(height * float(y) / 100)),
        "w": int(round(width * float(w) / 100)),
        "h": int(round(height * float(h) / 100)),
    }


def protect_box(x, y, w, h, inset=SAFE_PCT, bleed=False):
    if bleed:
        return _clamp_canvas(x, y, w, h)
    left = inset
    top = inset
    right = 100 - inset
    bottom = 100 - inset
    x = max(left, min(float(x), right - 1))
    y = max(top, min(float(y), bottom - 1))
    w = max(1.0, min(float(w), right - x))
    h = max(1.0, min(float(h), bottom - y))
    return round(x, 2), round(y, 2), round(w, 2), round(h, 2)


def _clamp_canvas(x, y, w, h):
    x = max(0.0, min(float(x), 99.0))
    y = max(0.0, min(float(y), 99.0))
    w = max(1.0, min(float(w), 100 - x))
    h = max(1.0, min(float(h), 100 - y))
    return round(x, 2), round(y, 2), round(w, 2), round(h, 2)


def box_inside_safe(x, y, w, h, inset=SAFE_PCT, tolerance=0.4):
    return (
        x >= inset - tolerance
        and y >= inset - tolerance
        and x + w <= 100 - inset + tolerance
        and y + h <= 100 - inset + tolerance
    )


def check_stack(stack):
    stack = stack if isinstance(stack, dict) else {}
    purpose = str(stack.get("purpose") or "hook")
    defects = []
    notes = []
    canvas = stack.get("canvas") or {}
    width = int(canvas.get("width") or CANVAS[0])
    height = int(canvas.get("height") or CANVAS[1])
    if (width, height) != CANVAS:
        defects.append(f"Canvas {width}×{height} — o envio é {CANVAS[0]}×{CANVAS[1]}.")
    background = stack.get("background") if isinstance(stack.get("background"), dict) else {}
    if not background.get("kind"):
        defects.append("A cena precisa de fundo: cor, wash ou imagem.")
    roles = {
        str(item.get("role") or "")
        for item in stack.get("layers") or []
        if isinstance(item, dict) and item.get("visible") is not False
    }
    if background.get("kind"):
        roles.add("background")
    for role in REQUIRED.get(purpose, ("background",)):
        if role not in roles:
            defects.append(f"Falta a camada {role} nesta cena.")
    for item in stack.get("layers") or []:
        if not isinstance(item, dict) or item.get("visible") is False:
            continue
        role = str(item.get("role") or "layer")
        if item.get("bleed"):
            continue
        if not box_inside_safe(item.get("x", 0), item.get("y", 0), item.get("w", 0), item.get("h", 0)):
            defects.append(f"{role} ultrapassa a margem segura de {SAFE_PCT}%.")
    if purpose == "cta" and "cta" in roles:
        notes.append("CTA dentro da margem. A cena pode ser enviada.")
    return {
        "passed": not defects,
        "defects": defects,
        "notes": notes,
        "safe": safe_rect(width, height),
        "purpose": purpose,
    }
