"""Typography drawn by code on top of a text-free visual.

Used where the image model cannot be trusted with letters: banners wider than 3:1 (728x90, 320x50,
970x250, 160x600) and every IAB display unit (300x250, 300x600, 300x300) are generated without text and
the Studio sets the headline, the support line and the CTA in the mask's zones with the brand font, at
exact pixel size, inside the safe margin. A soft scrim keeps the text legible on a busy picture. The text
stays editable: the layers are returned and saved next to the image together with the text-free base.
"""
from __future__ import annotations

import base64
import colorsys
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

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


def _distance(first, second):
    return sum((a - b) ** 2 for a, b in zip(first, second)) ** 0.5


def ground_color(palette):
    """The brand color for a text panel: the darkest official color when it is dark enough, else a deep neutral."""
    colors = [rgb for rgb in (_hex(value) for value in palette or []) if rgb]
    dark = sorted((rgb for rgb in colors if _luma(rgb) < 0.3), key=_luma)
    if dark:
        return dark[0]
    deep = sorted((rgb for rgb in colors if _luma(rgb) < 0.55), key=_luma)
    return deep[0] if deep else (17, 24, 39)


def _region_luma(image, box):
    region = image.crop(box).convert("L").resize((24, 24))
    data = list(region.getdata())
    return sum(data) / max(1, len(data)) / 255


def _wrap(draw, text, font, width):
    """Word wrap; a newline starts a new paragraph (each support string keeps its own line)."""
    lines = []
    for paragraph in str(text).split("\n"):
        current = ""
        for word in paragraph.split():
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


SUPPORT_MIN_PX = 9


def renders_support(spec):
    """Wide strips have no room for a support line; every other layout sets it under the headline."""
    return spec.get("class") != "wide" and "headline" in spec.get("zones", {})


def _busy(image, box):
    """Mean luma and contrast of a region (0-1), to decide whether text needs a scrim."""
    region = image.crop(box).convert("L").resize((48, 48))
    stat = ImageStat.Stat(region)
    return stat.mean[0] / 255, stat.stddev[0] / 255


def _scrim(canvas, box, light_text, radius):
    """A soft translucent plate behind the text block: dark under white text, light under dark text."""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    color = (8, 12, 20, 150) if light_text else (255, 255, 255, 170)
    ImageDraw.Draw(overlay).rounded_rectangle(box, radius=radius, fill=color)
    canvas.alpha_composite(overlay)


def render_text_layers(image, spec, headline, cta, brand_context, palette, support=None):
    """Draw headline, support and CTA into the mask zones; returns (image, layers)."""
    canvas = image.convert("RGBA")
    zones = spec["zones"]
    layers = []
    headline_size = None
    display = resolve_font(brand_context, "display", bold=True)
    body = resolve_font(brand_context, "body", bold=True)
    support_text = "\n".join(item for item in (support or []) if item) if renders_support(spec) else ""
    safe_right = 1 - spec["zones"].get("headline", (0.067,))[0] if spec.get("zones") else 0.93
    ground, panel_right = None, None
    if "panel" in zones and (headline or cta):
        # The text panel is painted by code in the brand's ground color: contrast and layout no longer depend on the
        # model leaving that area calm (it often puts the subject there).
        ground = ground_color(palette)
        px, py, pw, ph = _px(zones["panel"], canvas.size)
        radius = max(4, round(min(canvas.size) * 0.03))
        ImageDraw.Draw(canvas).rounded_rectangle((px, py, px + pw, py + ph), radius=radius, fill=ground + (255,))
        panel_right = zones["panel"][0] + zones["panel"][2]
    if headline and "headline" in zones:
        x, y, w, h = _px(zones["headline"], canvas.size)
        wide = spec["class"] == "wide"
        narrow = spec["width"] / spec["height"] < 0.45
        luma, contrast = _busy(canvas, (x, y, x + w, y + h))
        light_ground = luma > 0.55
        color = (17, 24, 39) if light_ground else (255, 255, 255)
        # A mid-tone or busy picture behind the copy gets a scrim, so the text never fights the image.
        if ground is None and (contrast > 0.16 or 0.38 < luma < 0.62):
            pad = max(4, round(min(canvas.size) * 0.02))
            light_text = luma <= 0.5
            color = (255, 255, 255) if light_text else (17, 24, 39)
            _scrim(canvas, (x - pad, y - pad, x + w + pad, y + h + pad), light_text, radius=pad * 2)
        draw = ImageDraw.Draw(canvas)
        head_h = round(h * 0.64) if support_text else h
        font, lines, size = _fit(draw, headline, display["path"], w, head_h, max_lines=2 if wide else 5 if narrow else 3)
        headline_size = size
        total = size * 1.08 * len(lines)
        top = y + (head_h - total) / 2 if wide else y
        for index, line in enumerate(lines):
            draw.text((x, top + index * size * 1.08), line, font=font, fill=color)
        layers.append({
            "type": "headline", "text": headline, "box": list(zones["headline"]),
            "font_family": display["family"], "font_source": display["source"], "size_px": size,
            "color": "#%02x%02x%02x" % color, "align": "left",
        })
        if support_text:
            body_regular = resolve_font(brand_context, "body", bold=False)
            support_top = round(top + total + size * 0.25)
            room = y + h - support_top
            # Legible or absent: all support strings, else only the first one, never below SUPPORT_MIN_PX.
            minimum = max(SUPPORT_MIN_PX, round(canvas.height * 0.036))
            fitted = None
            for candidate in (support_text, support_text.split("\n")[0]):
                if room < minimum:
                    break
                attempt = _fit(draw, candidate, body_regular["path"], w, room, max_lines=4, line_gap=1.15,
                               max_size=round(size * 0.6))
                if attempt[2] >= minimum and "\n".join(attempt[1]).replace("\n", " ").split() == candidate.split():
                    fitted, support_text = attempt, candidate
                    break
            if fitted:
                s_font, s_lines, s_size = fitted
                for index, line in enumerate(s_lines):
                    draw.text((x, support_top + index * s_size * 1.15), line, font=s_font, fill=color)
                layers.append({
                    "type": "support", "text": support_text, "box": [zones["headline"][0], support_top / canvas.height,
                                                                     zones["headline"][2], room / canvas.height],
                    "font_family": body_regular["family"], "font_source": body_regular["source"], "size_px": s_size,
                    "color": "#%02x%02x%02x" % color, "align": "left",
                })
    draw = ImageDraw.Draw(canvas)
    if cta and "cta" in zones:
        x, y, w, h = _px(zones["cta"], canvas.size)
        if spec.get("class") != "wide":
            # A button under ~8.5% of the height reads as a label, not a button: grow it upwards inside its zone.
            minimum = round(canvas.height * 0.085)
            if h < minimum:
                y, h = max(0, y - (minimum - h)), minimum
        fill = accent_color(palette)
        if ground is not None and _distance(fill, ground) < 60:
            fill = (255, 255, 255) if _luma(ground) < 0.5 else (17, 24, 39)
        ink = (17, 24, 39) if _luma(fill) > 0.55 else (255, 255, 255)
        pad = max(4, round(h * 0.18))
        # The whole label always shows: the pill may grow up to the safe frame (or the panel), then the font shrinks.
        limit_right = round((panel_right if panel_right else safe_right) * canvas.width)
        room_w = max(w, limit_right - x)
        cap = round(headline_size * 0.75) if headline_size else h - pad * 2  # never louder than the headline
        size = max(7, min(h - pad * 2, cap))
        font = ImageFont.truetype(str(body["path"]), size)
        while size > 7 and draw.textlength(cta, font=font) + pad * 4 > room_w:
            size -= 1
            font = ImageFont.truetype(str(body["path"]), size)
        label = cta
        text_w = draw.textlength(label, font=font)
        pill_w = min(room_w, round(text_w + pad * 4))
        center = abs((zones["cta"][0] + zones["cta"][2] / 2) - 0.5) < 0.1
        left = x + (w - pill_w) // 2 if center and pill_w <= w else x
        draw.rounded_rectangle((left, y, left + pill_w, y + h), radius=h // 2, fill=fill)
        ascent, descent = font.getmetrics()
        draw.text((left + (pill_w - text_w) / 2, y + (h - (ascent + descent)) / 2), label, font=font, fill=ink)
        layers.append({
            "type": "cta", "text": label, "box": [left / canvas.width, y / canvas.height, pill_w / canvas.width, h / canvas.height],
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
