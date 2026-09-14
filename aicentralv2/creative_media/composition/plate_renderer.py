"""Still sem textos, logos e camadas ocultas."""

from __future__ import annotations

from io import BytesIO

from .bbox import pixel_box


def render_plate(still_bytes, snapshot) -> bytes:
    from PIL import Image, ImageDraw

    source = Image.open(BytesIO(still_bytes)).convert("RGB")
    canvas = source.copy()
    draw = ImageDraw.Draw(canvas)
    for item in (snapshot or {}).get("elements") or []:
        if not isinstance(item, dict):
            continue
        if item.get("intent") not in {"protect", "hide"}:
            continue
        box = pixel_box(item.get("bbox"), canvas.width, canvas.height)
        if box is None:
            continue
        draw.rectangle(box, fill=_fill_color(source, box))
    out = BytesIO()
    canvas.save(out, format="JPEG", quality=92)
    return out.getvalue()


def _fill_color(image, box):
    left, top, right, bottom = box
    ring = []
    pad = 8
    sample = image.crop((
        max(0, left - pad),
        max(0, top - pad),
        min(image.width, right + pad),
        min(image.height, bottom + pad),
    ))
    pixels = list(sample.getdata())
    # Mediana do anel; se o recorte for só o bbox, cai no restante da peça.
    for index, pixel in enumerate(pixels):
        x = index % sample.width
        y = index // sample.width
        abs_x = max(0, left - pad) + x
        abs_y = max(0, top - pad) + y
        inside = left <= abs_x < right and top <= abs_y < bottom
        if not inside:
            ring.append(pixel)
    if not ring:
        ring = list(image.resize((1, 1)).getdata())
    if not ring:
        return (18, 18, 20)
    count = len(ring)
    return (
        sorted(p[0] for p in ring)[count // 2],
        sorted(p[1] for p in ring)[count // 2],
        sorted(p[2] for p in ring)[count // 2],
    )
