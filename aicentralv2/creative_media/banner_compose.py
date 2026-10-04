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

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

from .brand_fonts import resolve_font

# Each label ends at the next one or at a line break: briefings also arrive flattened to a single line.
_LABELS = r"(?:t[ií]tulo|headline|chamada|texto de apoio|apoio|subt[ií]tulo|bot[aã]o|cta|button)\s*:"
_HEADLINE = re.compile(r"(?:t[ií]tulo|headline|chamada)\s*:\s*(.+?)(?=\s*" + _LABELS + r"|\n|$)", re.I | re.S)
_CTA = re.compile(r"(?:bot[aã]o|cta|button)\s*:\s*(.+?)(?=\s*" + _LABELS + r"|\n|$)", re.I | re.S)


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


def _saturation(rgb):
    return colorsys.rgb_to_hls(*(channel / 255 for channel in rgb))[2]


def _deepen(rgb, target=0.2):
    """The same hue, darkened until its luma reaches ``target``."""
    factor = min(1.0, target / max(_luma(rgb), 1e-3))
    return tuple(round(channel * factor) for channel in rgb)


def ground_color(palette, image=None):
    """The text panel's color, in harmony with the brand and the scene.

    A dark brand color with some hue first (Cemig's deep green); a brand that only has black as its dark color gets
    its own hue deepened instead (Reserva's brown, not a black slab); an all-neutral palette takes a deep tone of the
    picture itself.
    """
    colors = [rgb for rgb in (_hex(value) for value in palette or []) if rgb]
    chromatic = [rgb for rgb in colors if _saturation(rgb) >= 0.15 and _luma(rgb) > 0.02]
    dark = sorted((rgb for rgb in chromatic if _luma(rgb) < 0.3), key=_luma)
    if dark:
        return dark[0]
    if chromatic:
        return _deepen(min(chromatic, key=_luma))
    if image is not None:
        small = image.convert("RGB").resize((48, 48))
        tones = [rgb for _, rgb in sorted(small.quantize(colors=5).convert("RGB").getcolors(48 * 48) or [], reverse=True)]
        vivid = [rgb for rgb in tones if _saturation(rgb) >= 0.12]
        if vivid:
            return _deepen(vivid[0])
    darkest = sorted((rgb for rgb in colors if _luma(rgb) < 0.55), key=_luma)
    return darkest[0] if darkest else (17, 24, 39)


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


# Mean edge density + half the luma spread inside the copy zones: under ~0.07 the picture is calm enough for text.
CALM_LIMIT = 0.07


# A panel may cover background or clothing; above this it is covering the subject (a face, a phone).
PANEL_LIMIT = 0.16


def _zone_busyness(image, rect):
    gray = image.convert("L")
    box = _px(rect, image.size)
    box = (box[0], box[1], box[0] + max(1, box[2]), box[1] + max(1, box[3]))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return ImageStat.Stat(edges.crop(box)).mean[0] / 255 + ImageStat.Stat(gray.crop(box)).stddev[0] / 255 / 2


def busyness(image, spec):
    """How busy the picture is where this layout puts its copy (0 calm, ~0.2+ a face, a hand or a phone)."""
    gray = image.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    scores = []
    for name in ("headline", "cta"):
        if name not in spec["zones"]:
            continue
        box = _px(spec["zones"][name], image.size)
        box = (box[0], box[1], box[0] + max(1, box[2]), box[1] + max(1, box[3]))
        scores.append(ImageStat.Stat(edges.crop(box)).mean[0] / 255 + ImageStat.Stat(gray.crop(box)).stddev[0] / 255 / 2)
    return max(scores) if scores else 0.0


def _mirror(spec):
    """The same layout flipped left-right (the model often puts the subject on the other side)."""
    zones = {name: (round(1 - x - w, 4), y, w, h) for name, (x, y, w, h) in spec["zones"].items() if name != "logo"}
    if "headline" in zones and "cta" in zones:
        # Copy stays left-aligned: the button starts where the headline starts, not flush to the right.
        x, y, w, h = zones["cta"]
        zones["cta"] = (zones["headline"][0], y, w, h)
    return {**spec, "id": spec["id"] + ":espelhado", "zones": zones, "mirrored": True}


def _with_logo(candidate, spec):
    """A candidate's copy zones with the original logo slot (the logo is applied there), or None when they collide."""
    zones = {name: rect for name, rect in candidate["zones"].items() if name != "logo"}
    if "logo" in spec["zones"]:
        logo = spec["zones"]["logo"]
        if any(_overlaps(zones[name], logo) for name in ("headline", "cta") if name in zones):
            return None
        zones["logo"] = logo
    return {**candidate, "zones": zones, "logo": spec["logo"]}


def _overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def choose_layout(image, spec):
    """Place the copy where the generated picture is calm, instead of trusting the model to keep the zone free.

    Candidates are the format's layouts with the same CTA need, as drawn and mirrored, each keeping the original
    logo slot. A layout without panel scores the busyness under its copy; a layout with panel scores what the panel
    would cover (it must not hide the subject). The requested layout wins whenever it is calm enough.
    """
    from . import ad_masks

    def score(item):
        if "panel" in item["zones"]:
            return _zone_busyness(image, item["zones"]["panel"]) - (PANEL_LIMIT - CALM_LIMIT)
        return busyness(image, item)

    if score(spec) <= CALM_LIMIT:
        return spec
    pool = [item for item in ad_masks.served_specs() if item["format"] == spec["format"] and "headline" in item["zones"]
            and (item["cta"] or not spec["cta"])]
    candidates = []
    for item in pool + [_mirror(item) for item in pool]:
        hybrid = _with_logo(item, spec)
        if hybrid is not None:
            candidates.append((score(hybrid), hybrid))
    if not candidates:
        return spec
    best_score, best = min(candidates, key=lambda pair: pair[0])
    return best if best_score < score(spec) else spec


_OFFER_SPAN = re.compile(r"((?:R\$\s*)?[+-]?\d[\d.,]*\s*%?(?:\s*(?:OFF|EXTRA|DE DESCONTO|MAIS|GR[ÁA]TIS))?)", re.I)


def split_offer(headline):
    """'Outlet com +20% EXTRA' -> ('Outlet com', '+20% EXTRA'): the offer is the hero of the piece."""
    text = " ".join(str(headline or "").split())
    match = _OFFER_SPAN.search(text)
    if not match or len(match.group(1).strip()) < 2:
        return text, ""
    hero = match.group(1).strip()
    before, after = text[:match.start()].strip(), text[match.end():].strip()
    if before and after:
        return text, ""  # an offer in the middle of a sentence stays in the sentence: never reorder the copy
    return (before, hero) if before else (after, hero)


def offer_first(headline):
    """True when the headline opens with the offer ('50% OFF em tudo'): the hero is drawn above the rest."""
    text = " ".join(str(headline or "").split())
    match = _OFFER_SPAN.search(text)
    return bool(match) and not text[:match.start()].strip()


def _contrast(first, second):
    def lum(rgb):
        values = []
        for channel in rgb:
            value = channel / 255
            values.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]
    a, b = sorted((lum(first), lum(second)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _flat(image, box):
    """A clean field: little tone variation and almost no edges, measured at full resolution (averaging hides grain)."""
    region = image.convert("L").crop(box)
    edges = region.filter(ImageFilter.FIND_EDGES)
    return ImageStat.Stat(region).stddev[0] / 255 < 0.05 and ImageStat.Stat(edges).mean[0] / 255 < 0.02


def _mean_color(image, box):
    stat = ImageStat.Stat(image.convert("RGB").crop(box).resize((16, 16)))
    return tuple(round(value) for value in stat.mean[:3])


def _flush(spec, box, size):
    """Extend a panel to the canvas edge on each side where it reaches the safe frame."""
    left, top, sw, sh = spec.get("safe") or (0.08, 0.08, 0.84, 0.84)
    x0, y0, x1, y1 = box
    tol_x, tol_y = size[0] * 0.012, size[1] * 0.012
    if x0 <= left * size[0] + tol_x:
        x0 = 0
    if x1 >= (left + sw) * size[0] - tol_x:
        x1 = size[0]
    if y0 <= top * size[1] + tol_y:
        y0 = 0
    if y1 >= (top + sh) * size[1] - tol_y:
        y1 = size[1]
    return (x0, y0, x1, y1)


def _gradient_scrim(canvas, box, light_text):
    x0, y0, x1, y1 = box
    pad = round((y1 - y0) * 0.35)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    top, bottom = max(0, y0 - pad), min(canvas.height, y1 + pad)
    tone = (8, 12, 20) if light_text else (255, 255, 255)
    for row in range(top, bottom):
        middle = 1 - abs((row - (top + bottom) / 2) / max(1, (bottom - top) / 2))
        draw.line((0, row, canvas.width, row), fill=tone + (round(150 * min(1, middle * 1.6)),))
    canvas.alpha_composite(overlay)


def _font(info, size):
    return ImageFont.truetype(str(info["path"]), max(6, int(size)))


def _stack(draw, display, body, kicker, hero, support, width, height, wide, hero_first=False):
    """Kicker (caps), hero offer (~2.3x) and support, scaled together to fill the zone without overflowing."""
    display_font = display if display.get("source") != "fallback" else {**display, "path": _MONTSERRAT_BOLD or display["path"]}
    kicker_text = kicker.upper() if kicker else ""
    regular = resolve_font({}, "body", bold=False)

    def build(base):
        lines, cursor = [], 0.0
        sizes = {"kicker": 0, "hero": 0}

        def add_kicker():
            nonlocal cursor
            size = base if hero else base * 1.35
            font = _font(display_font, size)
            for text in _wrap(draw, kicker_text, font, width):
                lines.append({"text": text, "font": font, "y": cursor, "role": "kicker"})
                cursor += size * 1.05
            sizes["kicker"] = round(size)

        def add_hero():
            nonlocal cursor
            size = base * (2.3 if kicker_text else 2.6)
            font = _font(display_font, size)
            for text in _wrap(draw, hero, font, width):
                lines.append({"text": text, "font": font, "y": cursor, "role": "hero"})
                cursor += size * 1.0
            sizes["hero"] = round(size)

        for part in (("hero", "kicker") if hero_first else ("kicker", "hero")):
            if part == "kicker" and kicker_text:
                add_kicker()
            elif part == "hero" and hero:
                add_hero()
        support_y, support_size = cursor, 0
        if support:
            size = max(SUPPORT_MIN_PX, base * 0.55)
            font = _font(regular, size)
            cursor += size * 0.4
            support_y = cursor
            for text in _wrap(draw, support, font, width):
                lines.append({"text": text, "font": font, "y": cursor, "role": "support"})
                cursor += size * 1.2
            support_size = round(size)
        widest = max((draw.textlength(line["text"], font=line["font"]) for line in lines), default=0)
        return lines, cursor, widest, sizes, support_y, support_size

    low, high, best = 4.0, float(height), None
    for _ in range(18):
        base = (low + high) / 2
        lines, total, widest, sizes, support_y, support_size = build(base)
        too_many = sum(1 for line in lines if line["role"] in ("kicker", "hero")) > (2 if wide else 4)
        if total <= height and widest <= width and not too_many:
            best, low = (lines, total, sizes, support_y, support_size), base
        else:
            high = base
    if best is None or (support and best[4] < SUPPORT_MIN_PX):
        if support:
            return _stack(draw, display, body, kicker, hero, "", width, height, wide, hero_first)
        best = (build(6)[0], build(6)[1], build(6)[3], 0, 0)
    lines, total, sizes, support_y, support_size = best
    return {"lines": lines, "height": total, "kicker_size": sizes["kicker"], "hero_size": sizes["hero"],
            "support_size": support_size, "support_y": support_y, "support_text": support if support_size else "",
            "support_family": regular["family"]}


_MONTSERRAT_BOLD = next(iter(sorted((Path(__file__).resolve().parents[1] / "static" / "fonts" / "brand").glob("Montserrat-Bold.ttf"))), None)


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
        px, py, pw, ph = _px(zones["panel"], canvas.size)
        if _flat(canvas, (px, py, px + pw, py + ph)):
            # The model already left a clean field there: the copy goes straight onto it, nothing painted over it.
            ground = _mean_color(canvas, (px, py, px + pw, py + ph))
        else:
            # A brand-color field, square and flush to the edges it reaches (a floating rounded card reads as a template).
            ground = ground_color(palette, canvas)
            ImageDraw.Draw(canvas).rectangle(_flush(spec, (px, py, px + pw, py + ph), canvas.size), fill=ground + (255,))
        panel_right = zones["panel"][0] + zones["panel"][2]
    if headline and "headline" in zones:
        x, y, w, h = _px(zones["headline"], canvas.size)
        wide = spec["class"] == "wide"
        luma, contrast = _busy(canvas, (x, y, x + w, y + h))
        if ground is not None:
            luma, contrast = _luma(ground), 0.0
        color = (17, 24, 39) if luma > 0.55 else (255, 255, 255)
        if ground is None and (contrast > 0.16 or 0.38 < luma < 0.62):
            # A soft gradient behind the copy (not a box): the picture stays, the text reads.
            light_text = luma <= 0.5
            color = (255, 255, 255) if light_text else (17, 24, 39)
            _gradient_scrim(canvas, (x, y, x + w, y + h), light_text)
        accent = accent_color(palette)
        hero_color = accent if _contrast(accent, ground or ((17, 24, 39) if color == (255, 255, 255) else (255, 255, 255))) >= 3 else color
        kicker, hero = split_offer(headline)
        hero_first = bool(hero) and offer_first(headline)
        draw = ImageDraw.Draw(canvas)
        block = _stack(draw, display, body, kicker, hero, support_text if renders_support(spec) else "", w, h, wide,
                       hero_first=hero_first)
        top = y + (h - block["height"]) / 2 if wide else y
        for line in block["lines"]:
            fill = hero_color if line["role"] == "hero" else color
            draw.text((x, top + line["y"]), line["text"], font=line["font"], fill=fill)
        headline_size = block["hero_size"] or block["kicker_size"]
        layers.append({
            # The copy as drawn (the kicker in caps is a typographic choice; the words are the client's).
            "type": "headline", "text": " ".join(item for item in ((hero, kicker.upper()) if hero_first else (kicker.upper(), hero)) if item),
            "box": list(zones["headline"]),
            "font_family": display["family"], "font_source": display["source"], "size_px": headline_size,
            "kicker_size_px": block["kicker_size"], "hero": hero,
            "lines": [line["text"] for line in block["lines"] if line["role"] in ("kicker", "hero")],
            "color": "#%02x%02x%02x" % color, "hero_color": "#%02x%02x%02x" % hero_color, "align": "left",
        })
        if block["support_size"]:
            layers.append({
                "type": "support", "text": block["support_text"],
                "lines": [line["text"] for line in block["lines"] if line["role"] == "support"],
                "box": [zones["headline"][0], (top + block["support_y"]) / canvas.height, zones["headline"][2],
                        (block["height"] - block["support_y"]) / canvas.height],
                "font_family": block["support_family"], "font_source": "studio", "size_px": block["support_size"],
                "color": "#%02x%02x%02x" % color, "align": "left",
            })
    draw = ImageDraw.Draw(canvas)
    if cta and "cta" in zones:
        x, y, w, h = _px(zones["cta"], canvas.size)
        if spec.get("class") != "wide":
            # A button under ~8.5% of the short side reads as a label, not a button: grow it upwards inside its zone.
            minimum = round(min(canvas.size) * 0.085)
            if h < minimum:
                y, h = max(0, y - (minimum - h)), minimum
        fill = accent_color(palette)
        if ground is not None and _distance(fill, ground) < 60:
            fill = (255, 255, 255) if _luma(ground) < 0.5 else (17, 24, 39)
        ink = (17, 24, 39) if _luma(fill) > 0.55 else (255, 255, 255)
        pad = max(4, round(h * 0.18))
        # The whole label always shows: the pill may grow up to the safe frame (or the panel), then the font shrinks.
        limit_right = round((panel_right if panel_right else safe_right) * canvas.width)
        if "logo" in zones:
            # Never grow under the official logo on the same row.
            lx, ly, lw, lh = _px(zones["logo"], canvas.size)
            if ly < y + h and y < ly + lh and lx > x:
                limit_right = min(limit_right, lx - max(4, round(canvas.width * 0.02)))
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
