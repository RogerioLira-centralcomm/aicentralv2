"""Pilha da cena: fundo + camadas posicionadas. Motion entra depois."""

from __future__ import annotations

from .catalog import is_end_card, logo_visible_for, plate_for
from .guidelines import CANVAS, protect_box

PLATE_BOXES = {
    "split": {
        "product": (42, 8, 56, 84, True),
        "logo": (6, 7, 22, 10, False),
        "headline": (6, 22, 38, 28, False),
        "support": (6, 54, 34, 12, False),
        "cta": (6, 80, 24, 8, False),
    },
    "hero": {
        "product": (0, 0, 100, 100, True),
        "logo": (6, 8, 22, 10, False),
        "headline": (6, 26, 40, 28, False),
        "support": (6, 58, 36, 12, False),
        "cta": (6, 82, 24, 8, False),
    },
    "center": {
        "product": (34, 54, 32, 24, True),
        "logo": (30, 28, 40, 22, False),
        "headline": (12, 8, 76, 12, False),
        "support": (22, 80, 56, 6, False),
        "cta": (38, 88, 24, 7, False),
    },
    "cast": {
        "ground": (0, 0, 100, 100, True),
        "cast": (10, 34, 80, 50, True),
        "logo": (5, 88, 28, 8, False),
        "headline": (5, 10, 56, 22, False),
        "meta": (66, 8, 28, 16, False),
        "support": (5, 28, 40, 8, False),
        "cta": (5, 80, 24, 6, False),
    },
}


def build_stack(scene, *, brand=None, assets=None, plate=None):
    scene = scene if isinstance(scene, dict) else _scene_dict(scene)
    brand = brand if isinstance(brand, dict) else {}
    assets = assets if isinstance(assets, dict) else {}
    purpose = str(scene.get("purpose") or "hook")
    layout = plate or plate_for(purpose)
    if assets.get("cast_url"):
        layout = "cast"
    boxes = PLATE_BOXES.get(layout) or PLATE_BOXES["split"]
    color = _brand_color(brand)
    photo = assets.get("scene_image") or scene.get("key_visual") or ""
    background = _background(layout, color, photo)
    layers = []
    if is_end_card(purpose, scene.get("id"), scene.get("scene_count")):
        logo_on = True
    elif scene.get("logo_visible") is not None:
        logo_on = bool(scene.get("logo_visible"))
    else:
        logo_on = logo_visible_for(purpose, scene.get("id"), scene.get("scene_count"))
    show_cta = bool(scene.get("cta")) or purpose == "cta"
    product_url = assets.get("product_url") or (photo if layout != "hero" else "")
    if layout == "hero":
        product_url = ""
    if layout == "cast":
        product_url = ""
    plan = (
        ("ground", "fundo", assets.get("ground_url") or "", "", layout == "cast"),
        ("cast", "elenco", assets.get("cast_url") or "", "", layout == "cast"),
        ("product", "product", product_url, "", layout != "cast"),
        ("logo", "logo", assets.get("logo_url") or brand.get("logo_url"), "", logo_on),
        ("headline", "texto", "", scene.get("headline") or "", True),
        ("meta", "texto", "", scene.get("set_note") or "", layout == "cast"),
        ("support", "texto", "", scene.get("support") or "", bool(scene.get("support"))),
        ("cta", "cta", "", scene.get("cta") or "", show_cta),
    )
    for role, tipo, url, text, visible in plan:
        if role not in boxes or not visible:
            continue
        x, y, w, h, bleed = boxes[role]
        x, y, w, h = protect_box(x, y, w, h, bleed=bleed)
        layers.append({
            "id": f"{scene.get('id') or 'scene'}-{role}",
            "role": role,
            "tipo": tipo,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "z": 1 if role == "ground" else 4 if role in {"product", "cast"} else 12,
            "visible": True,
            "bleed": bleed,
            "fit": "cover" if role == "product" and layout == "hero" else "contain",
            "asset_url": url or "",
            "text": text,
            "generate": bool(role == "product" and not url),
            "prompt": _layer_prompt(role, scene, brand),
            "motion": {"in": "hold", "out": "hold"},
        })
    return {
        "id": scene.get("id") or "scene_01",
        "purpose": purpose,
        "plate": layout,
        "canvas": {"width": CANVAS[0], "height": CANVAS[1]},
        "background": background,
        "layers": layers,
        "ready_for_motion": True,
    }


def _scene_dict(scene):
    data = {
        "id": getattr(scene, "id", "scene_01"),
        "purpose": getattr(scene, "purpose", "hook"),
        "headline": getattr(scene, "headline", ""),
        "support": getattr(scene, "support", ""),
        "cta": getattr(scene, "cta", ""),
    }
    flag = getattr(scene, "logo_visible", None)
    if flag is not None:
        data["logo_visible"] = bool(flag)
    return data


def _brand_color(brand):
    dna = brand.get("brand_dna") if isinstance(brand.get("brand_dna"), dict) else {}
    colors = dna.get("colors") if isinstance(dna.get("colors"), dict) else {}
    palette = colors.get("palette") or brand.get("palette") or []
    return (
        colors.get("accent")
        or brand.get("primary_color")
        or (palette[0] if palette else "#0E0D0C")
    )


def _background(layout, color, photo):
    if layout == "cast":
        return {"kind": "field", "color": color or "#7c4dff", "image_url": "", "effect": "pennant"}
    if layout == "hero" and photo:
        return {"kind": "image", "color": color, "image_url": photo, "effect": "veil-left"}
    if photo:
        return {"kind": "wash", "color": color, "image_url": photo, "effect": "soft-wash"}
    return {"kind": "wash", "color": color or "#0E0D0C", "image_url": "", "effect": "soft-wash"}


def _layer_prompt(role, scene, brand):
    name = brand.get("name") or "the brand"
    headline = scene.get("headline") or ""
    if role == "cast":
        return (
            f"Group cutout of the people in this {name} poster, {headline}. "
            "Transparent PNG. No background, no type, no flags, no logos."
        )
    if role == "ground":
        return (
            f"Empty field of the {name} poster: flat color and pennant bunting only. "
            "No people, no type, no logos."
        )
    if role == "product":
        return (
            f"Isolated product cutout for {name}, {headline}. "
            "Studio still, no text, no environment, transparent background, PNG."
        )
    if role == "logo":
        return f"Official {name} logo lockup, isolated, transparent background, PNG, no tagline."
    return ""
