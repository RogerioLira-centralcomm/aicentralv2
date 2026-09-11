"""Recorte sem IA: fundo branco, depois transparente, para montar camadas."""

from __future__ import annotations

import io

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def _require_pillow():
    if Image is None:
        raise RuntimeError("Pillow é necessário para recortar camadas.")


def paint_white_background(image):
    """Recorte em fundo branco — etapa depois do corte da caixa."""
    _require_pillow()
    source = image.convert("RGBA")
    canvas = Image.new("RGBA", source.size, (255, 255, 255, 255))
    canvas.alpha_composite(source)
    return canvas.convert("RGB")


def white_to_transparent(image, threshold=28):
    """Tira o branco do recorte. Sem modelo, só distância de cor."""
    _require_pillow()
    source = image.convert("RGBA")
    pixels = source.load()
    width, height = source.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            distance = abs(red - 255) + abs(green - 255) + abs(blue - 255)
            if distance <= threshold * 3:
                pixels[x, y] = (red, green, blue, 0)
    return source


def cutout_bytes(raw, *, transparent=True, threshold=28):
    _require_pillow()
    image = Image.open(io.BytesIO(raw)).convert("RGBA")
    if transparent:
        image = white_to_transparent(image, threshold=threshold)
    else:
        image = paint_white_background(image)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
