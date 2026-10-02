"""Typography drawn by code on top of a text-free visual.

Used where the image model cannot be trusted with letters: banners wider than 3:1 (728x90, 320x50,
970x250, 160x600) are generated without text and the Studio sets the headline and the CTA in the mask's
zones with the brand font, at exact pixel size. The text stays editable: the layers are returned and
saved next to the image together with the text-free base.
"""
from __future__ import annotations

import base64
import colorsys
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .brand_fonts import resolve_font

_HEADLINE = re.compile(r"(?:t[ií]tulo|headline|chamada)\s*:\s*(.+?)(?=\s*(?:bot[aã]o|cta|button)\s*:|\n|$)", re.I | re.S)
_CTA = re.compile(r"(?:bot[aã]o|cta|button)\s*:\s*(.+?)(?=\s*(?:t[ií]tulo|headline|chamada)\s*:|\n|$)", re.I | re.S)


def extract_copy(text):
    """Literal headline and CTA written in the briefing ("Título: ... Botão: ...")."""
    def clean(match, strip_dot):
        value = match.group(1).strip().strip("\"“”'") if match else ""
        value = value.rstrip(". ").strip("\"“”'") if strip_dot else value.strip()
        return " ".join(value.split())[:140]
    raw = str(text or "")
    return clean(_HEADLINE.search(raw), False), clean(_CTA.search(raw), True)[:40]


def _hex(value):
    value = str(value or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _luma(rgb):
    return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255


def accent_color(palette):
    """Most vivid official color; falls back to a neutral dark."""
    best, score = None, -1.0
    for value in palette or []:
        rgb = _hex(value)
        if not rgb:
            continue
        _, lightness, saturation = colorsys.rgb_to_hls(*(channel / 255 for channel in rgb))
        current = saturation * (1 - abs(lightness - 0.5))
        if current > score:
            best, score = rgb, current
    return best or (17, 24, 39)


def _region_luma(image, box):
    region = image.crop(box).convert("L").resize((24, 24))
    data = list(region.getdata())
    return sum(data) / max(1, len(data)) / 255


def _wrap(draw, text, font, width):
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit(draw, text, font_path, box_w, box_h, max_lines=3, line_gap=1.08, max_size=None):
    """Largest font size whose wrapped text fits the box."""
    low, high, best = 6, max(8, int(min(box_h, max_size or box_h))), None
    while low <= high:
        size = (low + high) // 2
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap(draw, text, font, box_w)
        height = size * line_gap * len(lines)
        widest = max((draw.textlength(line, font=font) for line in lines), default=0)
        if len(lines) <= max_lines and height <= box_h and widest <= box_w:
            best, low = (font, lines, size), size + 1
        else:
            high = size - 1
    if best is None:
        font = ImageFont.truetype(str(font_path), 6)
        best = (font, _wrap(draw, text, font, box_w)[:max_lines], 6)
    return best


def _px(rect, size):
    x, y, w, h = rect
    return round(x * size[0]), round(y * size[1]), round(w * size[0]), round(h * size[1])


def render_text_layers(image, spec, headline, cta, brand_context, palette):
    """Draw headline and CTA into the mask zones; returns (image, layers)."""
    canvas = image.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    zones = spec["zones"]
    layers = []
    headline_size = None
    display = resolve_font(brand_context, "display", bold=True)
    body = resolve_font(brand_context, "body", bold=True)
    if headline and "headline" in zones:
        x, y, w, h = _px(zones["headline"], canvas.size)
        wide = spec["class"] == "wide"
        narrow = spec["width"] / spec["height"] < 0.45
        font, lines, size = _fit(draw, headline, display["path"], w, h, max_lines=2 if wide else 5 if narrow else 3)
        headline_size = size
        light_ground = _region_luma(canvas, (x, y, x + w, y + h)) > 0.55
        color = (17, 24, 39) if light_ground else (255, 255, 255)
        total = size * 1.08 * len(lines)
        top = y + (h - total) / 2 if wide else y
        for index, line in enumerate(lines):
            draw.text((x, top + index * size * 1.08), line, font=font, fill=color)
        layers.append({
            "type": "headline", "text": headline, "box": list(zones["headline"]),
            "font_family": display["family"], "font_source": display["source"], "size_px": size,
            "color": "#%02x%02x%02x" % color, "align": "left",
        })
    if cta and "cta" in zones:
        x, y, w, h = _px(zones["cta"], canvas.size)
        fill = accent_color(palette)
        ink = (17, 24, 39) if _luma(fill) > 0.55 else (255, 255, 255)
        pad = max(4, round(h * 0.18))
        # the button never shouts louder than the headline
        font, lines, size = _fit(draw, cta, body["path"], w - pad * 4, h - pad * 2, max_lines=1,
                                 max_size=round(headline_size * 0.75) if headline_size else None)
        label = lines[0] if lines else cta
        text_w = draw.textlength(label, font=font)
        pill_w = min(w, round(text_w + pad * 4))
        center = abs((zones["cta"][0] + zones["cta"][2] / 2) - 0.5) < 0.1
        left = x + (w - pill_w) // 2 if center else x
        draw.rounded_rectangle((left, y, left + pill_w, y + h), radius=h // 2, fill=fill)
        ascent, descent = font.getmetrics()
        draw.text((left + (pill_w - text_w) / 2, y + (h - (ascent + descent)) / 2), label, font=font, fill=ink)
        layers.append({
            "type": "cta", "text": label, "box": [left / canvas.width, zones["cta"][1], pill_w / canvas.width, zones["cta"][3]],
            "font_family": body["family"], "font_source": body["source"], "size_px": size,
            "color": "#%02x%02x%02x" % ink, "fill": "#%02x%02x%02x" % fill,
        })
    return canvas, layers


def encode(image, output_format):
    buffer = io.BytesIO()
    if str(output_format).lower() in {"jpg", "jpeg"}:
        image.convert("RGB").save(buffer, "JPEG", quality=92)
    elif str(output_format).lower() == "webp":
        image.save(buffer, "WEBP", quality=92)
    else:
        image.save(buffer, "PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def decode(encoded):
    image = Image.open(io.BytesIO(base64.b64decode(str(encoded), validate=True)))
    image.load()
    return image


def save_layers(image_url, base_encoded, layers, spec):
    """Keep the text-free base and the layers beside the delivered image, so the text can be edited."""
    from flask import current_app
    if not str(image_url).startswith("/static/uploads/creative_generated/"):
        return None
    static_root = Path(current_app.static_folder).resolve()
    path = (static_root / str(image_url).removeprefix("/static/")).resolve()
    stem = path.with_suffix("")
    base_path = stem.parent / f"{stem.name}.base.png"
    base_path.write_bytes(base64.b64decode(base_encoded))
    document = {"version": 1, "mask": spec["id"], "base_url": f"/static/uploads/creative_generated/{base_path.name}", "layers": layers}
    (stem.parent / f"{stem.name}.layers.json").write_text(json.dumps(document, ensure_ascii=False))
    return document
