"""Clique: flood colorido quando não há máscara no ponto."""

from __future__ import annotations

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

from .matting import _pixel


def flood_from_points(source, positive_points, negative_points=None, threshold=48):
    if Image is None or source is None or not positive_points:
        return None
    rgb = source.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    mask = Image.new("L", (width, height), 0)
    marks = mask.load()
    seed = positive_points[0]
    sx, sy = _pixel(seed.get("x"), seed.get("y"), width, height)
    target = pixels[sx, sy]
    stack = [(sx, sy)]
    seen = set(stack)
    while stack:
        x, y = stack.pop()
        color = pixels[x, y]
        if _distance(color, target) > threshold:
            continue
        marks[x, y] = 255
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            if (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    for point in negative_points or []:
        px, py = _pixel(point.get("x"), point.get("y"), width, height)
        _clear_blob(marks, px, py, width, height)
    if mask.getbbox() is None:
        return None
    return mask


def _clear_blob(marks, x, y, width, height):
    if marks[x, y] < 128:
        return
    stack = [(x, y)]
    while stack:
        cx, cy = stack.pop()
        if marks[cx, cy] < 128:
            continue
        marks[cx, cy] = 0
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < width and 0 <= ny < height and marks[nx, ny] >= 128:
                stack.append((nx, ny))


def _distance(color, target):
    return abs(color[0] - target[0]) + abs(color[1] - target[1]) + abs(color[2] - target[2])
