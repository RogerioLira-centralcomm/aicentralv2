"""PNG RGBA das camadas protegidas, no tamanho da peça."""

from __future__ import annotations

from io import BytesIO

from .bbox import pixel_box


def render_overlay(still_bytes, snapshot, *, open_image=None) -> bytes:
    from PIL import Image

    source = Image.open(BytesIO(still_bytes)).convert("RGBA")
    canvas = Image.new("RGBA", source.size, (0, 0, 0, 0))
    loader = open_image or _default_open
    for item in _protected(snapshot):
        box = pixel_box(item.get("bbox"), canvas.width, canvas.height)
        if box is None:
            continue
        left, top, right, bottom = box
        layer = None
        path = item.get("png_path") or ""
        if path:
            try:
                layer = loader(path)
            except Exception:
                layer = None
        if layer is None:
            layer = source.crop((left, top, right, bottom))
        else:
            layer = layer.convert("RGBA").resize((right - left, bottom - top))
        canvas.paste(layer, (left, top), layer)
    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def compose_still(base_bytes, overlay_png) -> bytes:
    from PIL import Image

    base = Image.open(BytesIO(base_bytes)).convert("RGBA")
    overlay = Image.open(BytesIO(overlay_png)).convert("RGBA")
    if overlay.size != base.size:
        overlay = overlay.resize(base.size)
    base.alpha_composite(overlay)
    out = BytesIO()
    base.convert("RGB").save(out, format="JPEG", quality=92)
    return out.getvalue()


def _protected(snapshot):
    rows = []
    for item in (snapshot or {}).get("elements") or []:
        if isinstance(item, dict) and item.get("intent") == "protect":
            rows.append(item)
    rows.sort(key=lambda item: item.get("z_index") or 0)
    return rows


def _default_open(public_path):
    from ...camadas.storage import CamadasStorage

    return CamadasStorage().open_image(public_path)
