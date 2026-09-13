"""Refino de máscara: pontos, pincel, expandir, suavizar, halo."""

from __future__ import annotations

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    Image = None
    ImageDraw = None
    ImageFilter = None


def refine_mask(
    mask,
    source=None,
    *,
    positive_points=None,
    negative_points=None,
    brush_strokes=None,
    expand_px=0,
    feather_px=0,
    remove_halo=False,
):
    if Image is None or mask is None:
        return mask
    work = mask.convert("L")
    width, height = work.size
    radius = max(4, min(width, height) // 40)
    for point in positive_points or []:
        _stamp(work, point, width, height, 255, radius)
    for point in negative_points or []:
        _stamp(work, point, width, height, 0, radius)
    for stroke in brush_strokes or []:
        if not isinstance(stroke, dict):
            continue
        value = 255 if str(stroke.get("mode") or "include") != "erase" else 0
        size = int(stroke.get("r") or stroke.get("radius") or radius)
        _stamp(work, stroke, width, height, value, size)
    expand = int(expand_px or 0)
    if expand > 0 and ImageFilter is not None:
        work = work.filter(ImageFilter.MaxFilter(_odd(expand)))
    if expand < 0 and ImageFilter is not None:
        work = work.filter(ImageFilter.MinFilter(_odd(-expand)))
    if remove_halo and ImageFilter is not None:
        work = work.filter(ImageFilter.MinFilter(3))
    feather = float(feather_px or 0)
    if feather > 0 and ImageFilter is not None:
        work = work.filter(ImageFilter.GaussianBlur(feather))
    return work


def mask_contains(mask, x, y):
    if mask is None:
        return False
    width, height = mask.size
    px, py = _pixel(x, y, width, height)
    return mask.getpixel((px, py)) >= 128


def _stamp(mask, point, width, height, value, radius):
    if ImageDraw is None or not isinstance(point, dict):
        return
    px, py = _pixel(point.get("x"), point.get("y"), width, height)
    radius = max(1, int(radius or 4))
    draw = ImageDraw.Draw(mask)
    draw.ellipse([px - radius, py - radius, px + radius, py + radius], fill=value)


def _pixel(x, y, width, height):
    try:
        fx = float(x)
        fy = float(y)
    except (TypeError, ValueError):
        return 0, 0
    if fx <= 1 and fy <= 1:
        px = int(round(fx * max(0, width - 1)))
        py = int(round(fy * max(0, height - 1)))
    else:
        px = int(round(fx))
        py = int(round(fy))
    return max(0, min(width - 1, px)), max(0, min(height - 1, py))


def _odd(value):
    number = max(1, int(value or 1))
    return number if number % 2 else number + 1
