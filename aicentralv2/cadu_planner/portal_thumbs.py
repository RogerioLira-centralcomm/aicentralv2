"""Portal thumbnail composed from the portal's own approved print: no AI image, nothing invented.

The print is shown as captured; only the frame is added: a dark foot gradient tinted with the brand colour taken
from the favicon, the logo in a white badge, the name, the category and, when it applies, the Top 10 seal.
"""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = (1200, 675)
FONT_CANDIDATES = (
    ('/System/Library/Fonts/Helvetica.ttc', 1), ('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 0),
    ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 0), ('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 0),
)
DEFAULT_ACCENT = (29, 191, 115)  # Planner emerald


def _font(size):
    for path, index in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=index)
    return ImageFont.load_default()


def brand_color(icon):
    """Most present saturated colour of the favicon; the Planner emerald when it is grey, white or missing."""
    if icon is None:
        return DEFAULT_ACCENT
    small = icon.convert('RGBA').resize((48, 48))
    counts = {}
    for red, green, blue, alpha in small.getdata():
        if alpha < 200:
            continue
        high, low = max(red, green, blue), min(red, green, blue)
        if high - low < 40 or high > 245 or high < 40:
            continue
        key = (red // 32, green // 32, blue // 32)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return DEFAULT_ACCENT
    key = max(counts, key=counts.get)
    return tuple(min(255, value * 32 + 16) for value in key)


def _wrap(draw, text, font, width, lines=2):
    words, rows, current = str(text).split(), [], ''
    for word in words:
        trial = f'{current} {word}'.strip()
        if draw.textlength(trial, font=font) <= width or not current:
            current = trial
        else:
            rows.append(current)
            current = word
    rows.append(current)
    if len(rows) > lines:
        rows = rows[:lines]
        while rows[-1] and draw.textlength(rows[-1] + '…', font=font) > width:
            rows[-1] = rows[-1][:-1]
        rows[-1] = rows[-1].rstrip() + '…'
    return rows


def compose(print_bytes, icon_bytes, name, category, seal=''):
    """Return a 1200x675 RGB image."""
    shot = Image.open(io.BytesIO(print_bytes)).convert('RGB')
    scale = max(SIZE[0] / shot.width, SIZE[1] / shot.height)
    shot = shot.resize((round(shot.width * scale), round(shot.height * scale)), Image.LANCZOS).crop((0, 0, *SIZE))
    try:
        icon = Image.open(io.BytesIO(icon_bytes)).convert('RGBA') if icon_bytes else None
    except OSError:
        icon = None
    accent = brand_color(icon)

    canvas = shot.convert('RGBA')
    # Foot gradient: transparent at 32% of the height, brand-tinted near-black at the bottom.
    foot = Image.new('RGBA', SIZE, (0, 0, 0, 0))
    paint = ImageDraw.Draw(foot)
    base = tuple(int(value * 0.18) for value in accent)
    top = int(SIZE[1] * .32)
    for y in range(top, SIZE[1]):
        alpha = int(250 * min(1.0, ((y - top) / (SIZE[1] * .55)) ** 1.1))
        paint.line([(0, y), (SIZE[0], y)], fill=(*base, alpha))
    canvas = Image.alpha_composite(canvas, foot)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, SIZE[0], 10), fill=(*accent, 255))

    margin, badge = 44, 112
    y0 = SIZE[1] - margin - badge
    shadow = Image.new('RGBA', SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((margin, y0 + 6, margin + badge, y0 + badge + 6), 22, fill=(0, 0, 0, 120))
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(10)))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((margin, y0, margin + badge, y0 + badge), 22, fill=(255, 255, 255, 255))
    if icon is not None:
        inner = badge - 28
        ratio = min(inner / icon.width, inner / icon.height)
        glyph = icon.resize((max(1, round(icon.width * ratio)), max(1, round(icon.height * ratio))), Image.LANCZOS)
        canvas.alpha_composite(glyph, (margin + (badge - glyph.width) // 2, y0 + (badge - glyph.height) // 2))
    text_x = margin + badge + 28
    width = SIZE[0] - text_x - margin
    title_font, small_font = _font(52), _font(28)
    rows = _wrap(draw, name, title_font, width)
    block = len(rows) * 58 + 40
    y = y0 + (badge - block) // 2
    for row in rows:
        draw.text((text_x, y), row, font=title_font, fill=(255, 255, 255, 255))
        y += 58
    draw.text((text_x, y + 4), str(category or ''), font=small_font, fill=(255, 255, 255, 200))

    if seal:
        pill_font = _font(26)
        pill_w = int(draw.textlength(seal, font=pill_font)) + 40
        draw.rounded_rectangle((margin, 40, margin + pill_w, 40 + 50), 25, fill=(*accent, 255))
        draw.text((margin + 20, 40 + 10), seal, font=pill_font, fill=(255, 255, 255, 255))
    return canvas.convert('RGB')
