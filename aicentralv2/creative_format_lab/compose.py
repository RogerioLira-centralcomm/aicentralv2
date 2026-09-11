"""Python fecha a cena: fundo + camadas no 1920×1080."""

from __future__ import annotations

import base64
import io
from urllib.request import urlopen

from .guidelines import CANVAS, percent_box

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageFont = None


def compose_stack(stack, assets=None):
    if Image is None:
        raise RuntimeError("Pillow é necessário para fechar a cena.")
    stack = stack if isinstance(stack, dict) else {}
    assets = assets if isinstance(assets, dict) else {}
    width = int((stack.get("canvas") or {}).get("width") or CANVAS[0])
    height = int((stack.get("canvas") or {}).get("height") or CANVAS[1])
    canvas = _paint_background(stack.get("background") or {}, width, height, assets)
    placed = []
    for item in sorted(stack.get("layers") or [], key=lambda row: int(row.get("z") or 0)):
        if not isinstance(item, dict) or item.get("visible") is False:
            continue
        box = percent_box(item["x"], item["y"], item["w"], item["h"], width, height)
        layer = _layer_image(item, assets, box)
        if layer is None:
            continue
        canvas.alpha_composite(layer, (box["x"], box["y"]))
        placed.append({**item, "px": box})
    buffer = io.BytesIO()
    canvas.convert("RGB").save(buffer, format="PNG")
    png = buffer.getvalue()
    return {
        "png": png,
        "png_data_url": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
        "width": width,
        "height": height,
        "placed": placed,
    }


def knockout_background(image, threshold=28):
    image = image.convert("RGBA")
    pixels = image.load()
    width, height = image.size
    samples = [
        pixels[0, 0],
        pixels[width - 1, 0],
        pixels[0, height - 1],
        pixels[width - 1, height - 1],
    ]
    key = tuple(sum(channel[index] for channel in samples) // 4 for index in range(3))
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            distance = abs(red - key[0]) + abs(green - key[1]) + abs(blue - key[2])
            if distance <= threshold * 3:
                pixels[x, y] = (red, green, blue, 0)
    return image


def load_image(source):
    if source is None:
        return None
    if isinstance(source, Image.Image):
        return source.convert("RGBA")
    raw = source
    if isinstance(source, str):
        if source.startswith("data:image"):
            raw = base64.b64decode(source.split(",", 1)[-1])
        elif source.startswith("http://") or source.startswith("https://"):
            raw = urlopen(source, timeout=12).read()
        else:
            return None
    if not isinstance(raw, (bytes, bytearray)):
        return None
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGBA")
    except (OSError, ValueError):
        return None
    extrema = image.getextrema()
    if len(extrema) == 4 and extrema[3][0] >= 250:
        image = knockout_background(image)
    return image


def _paint_background(background, width, height, assets):
    color = _hex_rgb(background.get("color") or "#0E0D0C")
    canvas = Image.new("RGBA", (width, height), color + (255,))
    kind = str(background.get("kind") or "wash")
    photo = load_image(assets.get("background") or background.get("png") or background.get("image_url"))
    if photo is not None and kind in {"image", "wash"}:
        fitted = _fit(photo, width, height, "cover")
        if kind == "wash":
            fitted = Image.blend(canvas, fitted, 0.38)
        canvas = fitted
    if str(background.get("effect") or "") == "soft-wash":
        shade = Image.new("RGBA", (width, height), (14, 13, 12, 90))
        canvas = Image.alpha_composite(canvas, shade)
    if str(background.get("effect") or "") == "veil-left":
        veil = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(veil)
        draw.rectangle((0, 0, int(width * 0.46), height), fill=(14, 13, 12, 150))
        canvas = Image.alpha_composite(canvas, veil)
    return canvas


def _layer_image(item, assets, box):
    key = item.get("id") or item.get("role")
    source = (
        assets.get(key)
        or assets.get(item.get("role"))
        or item.get("png")
        or item.get("asset_url")
    )
    image = load_image(source)
    if image is None and item.get("text"):
        return _text_card(item["text"], box["w"], box["h"], item.get("role") == "cta")
    if image is None:
        return None
    return _fit(image, box["w"], box["h"], item.get("fit") or "contain")


def _text_card(text, width, height, accent=False):
    card = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    font = _font(42 if height > 80 else 28)
    fill = (237, 230, 214, 255)
    draw.text((0, 0), str(text), font=font, fill=fill)
    if accent:
        draw.line((0, height - 6, min(width, 220), height - 6), fill=(196, 165, 116, 255), width=3)
    return card


def _fit(image, width, height, mode):
    width = max(1, int(width))
    height = max(1, int(height))
    image = image.convert("RGBA")
    if mode == "cover":
        scale = max(width / image.width, height / image.height)
    else:
        scale = min(width / image.width, height / image.height)
    size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.NEAREST)
    resized = image.resize(size, resample)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.paste(resized, ((width - size[0]) // 2, (height - size[1]) // 2), resized)
    return canvas


def _font(size):
    candidates = (
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _hex_rgb(value):
    raw = str(value or "#0E0D0C").lstrip("#")
    if len(raw) != 6:
        return (14, 13, 12)
    try:
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return (14, 13, 12)
