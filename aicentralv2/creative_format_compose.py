"""Compositor determinístico da peça nativa no retângulo-alvo."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .creative_format_geometry import OVERLAY_SLOTS, get_safe_areas

APP_FONT = Path(__file__).resolve().parent / "static" / "fonts" / "OpenSans-Regular.ttf"
FONT_CANDIDATES = (
    APP_FONT,
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
)
BITMAP_FALLBACK = "bitmap_5x7"


_FONT_5X7 = {
    " ": "00000000000000000000000000000000000",
    "A": "01110100011000111111100011000110001",
    "B": "11110100011111010001100011111000000",
    "C": "01111100001000010000100000111100000",
    "D": "11110100011000110001100011111000000",
    "E": "11111100001111010000100001111100000",
    "F": "11111100001111010000100001000000000",
    "G": "01111100001000010111100010111100000",
    "H": "10001100011111110001100011000100000",
    "I": "11111001000010000100001000111110000",
    "J": "00111000100001000010100010111000000",
    "K": "10001100101110010100100011000100000",
    "L": "10000100001000010000100001111100000",
    "M": "10001110111010110001100011000100000",
    "N": "10001110011010110011100011000100000",
    "O": "01110100011000110001100010111000000",
    "P": "11110100011111010000100001000000000",
    "Q": "01110100011000110001101010111100000",
    "R": "11110100011111010010100011000100000",
    "S": "01111100000111000001100011111000000",
    "T": "11111001000010000100001000010000000",
    "U": "10001100011000110001100010111000000",
    "V": "10001100011000110001010100010000000",
    "W": "10001100011000110101110111000100000",
    "X": "10001010100010001010001011000100000",
    "Y": "10001010100010000100001000010000000",
    "Z": "11111000010001000100010001111100000",
    "0": "01110100011000110001100010111000000",
    "1": "00100011000010000100001000111110000",
    "2": "01110100010000100100010001111100000",
    "3": "01110100010011000001100010111000000",
    "4": "00010001100101011111000100001000000",
    "5": "11111100001111000001100011111000000",
    "6": "01111100001111010001100010111000000",
    "7": "11111000010001000100010000100000000",
    "8": "01110100010111010001100010111000000",
    "9": "01110100011000101111000010111000000",
    "-": "00000000000111100000000000000000000",
    ".": "00000000000000000000000000010000000",
    "!": "00100001000010000100000000010000000",
    "?": "01110100010001000100000000010000000",
}


def png_size(data):
    if not data or len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", data[16:24])
    if width < 1 or height < 1:
        return None
    return width, height


def resolve_compose_font():
    for path in FONT_CANDIDATES:
        if path.is_file():
            return str(path), path.name
    return None, BITMAP_FALLBACK


def wipe_safe_areas(source_bytes, geometry, brand_color="#1E4D4F"):
    """Limpa headline/CTA/legal/logo no still. OpenRouter /images não expõe máscara."""
    geometry = geometry if isinstance(geometry, dict) else {}
    size = geometry.get("size")
    family = geometry.get("family")
    if not size or not family:
        return source_bytes
    brand = _hex_rgb(brand_color)
    canvas = _still_canvas(source_bytes, size, family, brand)
    _wipe_overlay_slots(canvas, get_safe_areas(family, size), brand)
    return canvas.to_png()


def crop_safe_area_collage(source_bytes, geometry):
    geometry = geometry if isinstance(geometry, dict) else {}
    size = geometry.get("size")
    family = geometry.get("family")
    if not size or not family:
        return source_bytes
    brand = _hex_rgb("#1E4D4F")
    canvas = _still_canvas(source_bytes, size, family, brand)
    layout = get_safe_areas(family, size)
    tiles = []
    for key in OVERLAY_SLOTS:
        box = layout.get(key)
        if not box:
            continue
        tiles.append(_crop_box(canvas, box))
    return _stack_tiles(tiles)


def compose_native_piece(source_bytes, geometry, copy=None, logo_bytes=None):
    return compose_native_result(source_bytes, geometry, copy, logo_bytes)["png"]


def compose_native_result(source_bytes, geometry, copy=None, logo_bytes=None):
    geometry = geometry if isinstance(geometry, dict) else {}
    size = geometry.get("size")
    family = geometry.get("family")
    if not size or not family:
        raise ValueError("Geometria nativa incompleta para composição.")
    width, height = size
    copy = copy if isinstance(copy, dict) else {}
    brand = _hex_rgb(copy.get("brand_color") or "#1E4D4F")
    ink = (255, 255, 255)
    layout = get_safe_areas(family, size)
    canvas = _still_canvas(source_bytes, size, family, brand)
    _wipe_overlay_slots(canvas, layout, brand)
    font_path, font_name = resolve_compose_font()
    logo_applied = False
    if logo_bytes:
        logo = _contain_pixels(logo_bytes, layout["logo"][2], layout["logo"][3])
        if logo is not None:
            canvas.paste(layout["logo"][0], layout["logo"][1], logo)
            logo_applied = True
    if family != "slate_16x9":
        canvas.fill_rect(*layout["headline"], _mix(brand, (0, 0, 0), 0.28))
    _draw_fitted_text(
        canvas,
        layout["headline"],
        copy.get("headline") or "",
        ink if family != "slate_16x9" else brand,
        font_path,
    )
    cta = str(copy.get("cta") or "").strip()
    if not cta and not copy.get("omit_cta"):
        cta = "SAIBA MAIS"
    if cta:
        canvas.fill_rect(*layout["cta"], brand)
        _draw_fitted_text(canvas, layout["cta"], cta, ink, font_path)
    legal = str(copy.get("legal") or "").strip()
    if legal and layout.get("legal"):
        _draw_fitted_text(
            canvas, layout["legal"], legal, _mix(ink, brand, 0.25), font_path
        )
    return {
        "png": canvas.to_png(),
        "logo_applied": logo_applied,
        "composed": True,
        "font": font_name,
        "require_logo": bool(copy.get("require_logo")),
        "size": (width, height),
    }


class _Canvas:
    def __init__(self, width, height, fill):
        self.width = width
        self.height = height
        self.pixels = bytearray(fill * (width * height))

    def fill_rect(self, x, y, width, height, color):
        for row in range(max(0, y), min(self.height, y + height)):
            start = (row * self.width + max(0, x)) * 3
            end = (row * self.width + min(self.width, x + width)) * 3
            self.pixels[start:end] = color * ((end - start) // 3)

    def paste(self, x, y, other):
        if other is None:
            return
        src_w, src_h, src = other
        for row in range(src_h):
            dest_y = y + row
            if dest_y < 0 or dest_y >= self.height:
                continue
            src_start = row * src_w * 3
            dest_x = max(0, x)
            skip = dest_x - x
            count = min(src_w - skip, self.width - dest_x)
            if count <= 0:
                continue
            dest_start = (dest_y * self.width + dest_x) * 3
            self.pixels[dest_start:dest_start + count * 3] = src[
                src_start + skip * 3:src_start + (skip + count) * 3
            ]

    def draw_text(self, box, text, color):
        x, y, width, height = box
        glyphs = _glyph_rows(_normalize_copy(text), width, height)
        if not glyphs:
            return
        text_w = len(glyphs[0])
        text_h = len(glyphs)
        origin_x = x + max(0, (width - text_w) // 2)
        origin_y = y + max(0, (height - text_h) // 2)
        for row, line in enumerate(glyphs):
            dest_y = origin_y + row
            if dest_y < 0 or dest_y >= self.height:
                continue
            for col, bit in enumerate(line):
                if bit != "1":
                    continue
                dest_x = origin_x + col
                if dest_x < 0 or dest_x >= self.width:
                    continue
                offset = (dest_y * self.width + dest_x) * 3
                self.pixels[offset:offset + 3] = bytes(color)

    def to_png(self):
        return _encode_png(self.width, self.height, self.pixels)


def _still_canvas(source_bytes, size, family, brand):
    width, height = size
    canvas = _Canvas(width, height, _mix(brand, (18, 36, 38), 0.35))
    layout = get_safe_areas(family, size)
    visual = layout["visual"]
    still = _cover_pixels(source_bytes, visual[2], visual[3], brand)
    canvas.paste(visual[0], visual[1], still)
    return canvas


def _wipe_overlay_slots(canvas, layout, brand):
    for key in OVERLAY_SLOTS:
        box = layout.get(key)
        if not box:
            continue
        fill = _neighborhood_fill(canvas, box, brand)
        canvas.fill_rect(*box, fill)


def _neighborhood_fill(canvas, box, brand):
    x, y, width, height = box
    samples = []
    for px, py in (
        (x - 2, y + height // 2),
        (x + width + 1, y + height // 2),
        (x + width // 2, y - 2),
        (x + width // 2, y + height + 1),
    ):
        if 0 <= px < canvas.width and 0 <= py < canvas.height:
            offset = (py * canvas.width + px) * 3
            samples.append(bytes(canvas.pixels[offset:offset + 3]))
    if not samples:
        return brand
    channels = [0, 0, 0]
    for sample in samples:
        channels[0] += sample[0]
        channels[1] += sample[1]
        channels[2] += sample[2]
    count = len(samples)
    return bytes(value // count for value in channels)


def _crop_box(canvas, box):
    x, y, width, height = box
    width = max(1, min(width, canvas.width))
    height = max(1, min(height, canvas.height))
    pixels = bytearray(width * height * 3)
    for row in range(height):
        src_y = min(canvas.height - 1, max(0, y + row))
        src_x = min(canvas.width - 1, max(0, x))
        count = min(width, canvas.width - src_x)
        src = (src_y * canvas.width + src_x) * 3
        dest = row * width * 3
        pixels[dest:dest + count * 3] = canvas.pixels[src:src + count * 3]
    return width, height, pixels


def _stack_tiles(tiles):
    tiles = [tile for tile in tiles if tile]
    if not tiles:
        return _encode_png(1, 1, bytearray(b"\x00\x00\x00"))
    width = max(tile[0] for tile in tiles)
    height = sum(tile[1] for tile in tiles) + 4 * max(0, len(tiles) - 1)
    canvas = _Canvas(width, height, b"\x10\x10\x10")
    top = 0
    for tile_w, tile_h, pixels in tiles:
        canvas.paste(0, top, (tile_w, tile_h, pixels))
        top += tile_h + 4
    return canvas.to_png()


def _draw_fitted_text(canvas, box, text, color, font_path):
    if font_path:
        glyph = _ttf_glyph_rows(box, text, color, font_path)
        if glyph is not None:
            canvas.paste(box[0], box[1], glyph)
            return
    canvas.draw_text(box, text, color)


def _ttf_glyph_rows(box, text, color, font_path):
    text = str(text or "").strip()
    _x, _y, width, height = box
    if not text or width < 8 or height < 8:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    size = max(8, min(height, 64))
    rgb = tuple(color) if len(color) == 3 else (255, 255, 255)
    lines = []
    font = None
    while size >= 8:
        try:
            font = ImageFont.truetype(font_path, size)
        except OSError:
            return None
        lines = _wrap_ttf(text, font, width - 4, draw)
        box_w, box_h = _measure_ttf(lines, font, draw)
        if box_w <= width - 2 and box_h <= height - 2:
            break
        size -= 1
    if font is None or not lines:
        return None
    box_w, box_h = _measure_ttf(lines, font, draw)
    origin_x = max(0, (width - box_w) // 2)
    origin_y = max(0, (height - box_h) // 2)
    line_h = max(1, box_h // len(lines))
    for index, line in enumerate(lines):
        draw.text((origin_x, origin_y + index * line_h), line, font=font, fill=rgb + (255,))
    pixels = bytearray(width * height * 3)
    raw = image.tobytes()
    for index in range(width * height):
        alpha = raw[index * 4 + 3]
        if alpha < 16:
            continue
        dest = index * 3
        pixels[dest:dest + 3] = raw[index * 4:index * 4 + 3]
    return width, height, pixels


def _wrap_ttf(text, font, max_width, draw):
    words = str(text).split()
    if not words:
        return []
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    while lines and draw.textlength(lines[-1], font=font) > max_width and len(lines[-1]) > 1:
        lines[-1] = lines[-1][:-1]
    return [line for line in lines if line]


def _measure_ttf(lines, font, draw):
    widths = [draw.textlength(line, font=font) for line in lines] or [0]
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    return int(max(widths)), int(line_h * len(lines))


def _cover_pixels(source_bytes, width, height, fallback):
    decoded = _decode_png(source_bytes)
    if decoded is None:
        return width, height, bytearray(fallback * (width * height))
    src_w, src_h, src = decoded
    scale = max(width / src_w, height / src_h)
    scaled_w = max(1, int(round(src_w * scale)))
    scaled_h = max(1, int(round(src_h * scale)))
    scaled = _scale_nearest(src_w, src_h, src, scaled_w, scaled_h)
    left = max(0, (scaled_w - width) // 2)
    top = max(0, (scaled_h - height) // 2)
    cropped = bytearray(width * height * 3)
    for row in range(height):
        src_row = min(scaled_h - 1, top + row)
        src_start = (src_row * scaled_w + left) * 3
        cropped[row * width * 3:(row + 1) * width * 3] = scaled[
            src_start:src_start + width * 3
        ]
    return width, height, cropped


def _contain_pixels(source_bytes, width, height):
    decoded = _decode_png(source_bytes)
    if decoded is None or width < 1 or height < 1:
        return None
    src_w, src_h, src = decoded
    scale = min(width / src_w, height / src_h)
    dest_w = max(1, int(round(src_w * scale)))
    dest_h = max(1, int(round(src_h * scale)))
    return dest_w, dest_h, _scale_nearest(src_w, src_h, src, dest_w, dest_h)


def _scale_nearest(src_w, src_h, src, dest_w, dest_h):
    dest = bytearray(dest_w * dest_h * 3)
    for row in range(dest_h):
        src_y = min(src_h - 1, int(row * src_h / dest_h))
        for col in range(dest_w):
            src_x = min(src_w - 1, int(col * src_w / dest_w))
            src_i = (src_y * src_w + src_x) * 3
            dest_i = (row * dest_w + col) * 3
            dest[dest_i:dest_i + 3] = src[src_i:src_i + 3]
    return dest


def _encode_png(width, height, pixels):
    raw = bytearray()
    row_width = width * 3
    for row in range(height):
        raw.append(0)
        raw.extend(pixels[row * row_width:(row + 1) * row_width])
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def _chunk(tag, data):
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _decode_png(data):
    if not data or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    offset = 8
    width = height = color_type = None
    idat = bytearray()
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        tag = data[offset + 4:offset + 8]
        start = offset + 8
        end = start + length
        if end + 4 > len(data):
            return None
        chunk = data[start:end]
        offset = end + 4
        if tag == b"IHDR":
            width, height, depth, color_type = struct.unpack(">IIBB", chunk[:10])
            if depth != 8 or color_type not in (2, 6) or width < 1 or height < 1:
                return None
        elif tag == b"IDAT":
            idat.extend(chunk)
        elif tag == b"IEND":
            break
    if width is None:
        return None
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        return None
    channels = 3 if color_type == 2 else 4
    stride = width * channels
    expected = height * (stride + 1)
    if len(raw) < expected:
        return None
    pixels = bytearray(width * height * 3)
    prev = bytearray(stride)
    cursor = 0
    for row in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scan = bytearray(raw[cursor:cursor + stride])
        cursor += stride
        recon = _paeth_scan(filter_type, scan, prev, channels)
        prev = recon
        dest = row * width * 3
        if channels == 3:
            pixels[dest:dest + width * 3] = recon
        else:
            for col in range(width):
                src = col * 4
                pixels[dest + col * 3:dest + col * 3 + 3] = recon[src:src + 3]
    return width, height, pixels


def _paeth_scan(filter_type, scan, prev, bpp):
    recon = bytearray(len(scan))
    for index, value in enumerate(scan):
        left = recon[index - bpp] if index >= bpp else 0
        up = prev[index]
        up_left = prev[index - bpp] if index >= bpp else 0
        if filter_type == 1:
            value = (value + left) & 255
        elif filter_type == 2:
            value = (value + up) & 255
        elif filter_type == 3:
            value = (value + ((left + up) // 2)) & 255
        elif filter_type == 4:
            value = (value + _paeth(left, up, up_left)) & 255
        recon[index] = value
    return recon


def _paeth(left, up, up_left):
    estimate = left + up - up_left
    distances = (
        abs(estimate - left),
        abs(estimate - up),
        abs(estimate - up_left),
    )
    return (left, up, up_left)[distances.index(min(distances))]


def _normalize_copy(value):
    table = str.maketrans({
        "Á": "A", "À": "A", "Â": "A", "Ã": "A",
        "É": "E", "Ê": "E",
        "Í": "I",
        "Ó": "O", "Ô": "O", "Õ": "O",
        "Ú": "U",
        "Ç": "C",
        "á": "A", "à": "A", "â": "A", "ã": "A",
        "é": "E", "ê": "E",
        "í": "I",
        "ó": "O", "ô": "O", "õ": "O",
        "ú": "U",
        "ç": "C",
    })
    return str(value or "").translate(table).upper()


def _glyph_rows(text, max_width, max_height):
    text = "".join(char if char in _FONT_5X7 else " " for char in text).strip()
    if not text or max_width < 8 or max_height < 8:
        return []
    scale = 1
    if max_height >= 28 and max_width >= 160:
        scale = 2
    glyph_w = 6 * scale
    glyph_h = 7 * scale
    while text and (len(text) * glyph_w) > max_width - 4:
        text = text[:-1]
    if not text:
        return []
    rows = ["0" * (len(text) * glyph_w) for _ in range(glyph_h)]
    for index, char in enumerate(text):
        bits = _FONT_5X7.get(char) or _FONT_5X7[" "]
        for row in range(7):
            for col in range(5):
                if bits[row * 5 + col] != "1":
                    continue
                for dy in range(scale):
                    line = list(rows[row * scale + dy])
                    start = index * glyph_w + col * scale
                    for dx in range(scale):
                        line[start + dx] = "1"
                    rows[row * scale + dy] = "".join(line)
    return rows


def _hex_rgb(value):
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#"):
        try:
            return bytes.fromhex(text[1:])
        except ValueError:
            pass
    return b"\x1e\x4d\x4f"


def _mix(left, right, amount):
    return bytes(
        int(left[index] * (1 - amount) + right[index] * amount)
        for index in range(3)
    )
