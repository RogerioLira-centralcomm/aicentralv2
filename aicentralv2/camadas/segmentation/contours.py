"""Contorno e micropontos derivados da máscara raster."""

from __future__ import annotations


def contours_from_mask(mask, step=6):
    if mask is None or mask.getbbox() is None:
        return {"contours": [], "points": []}
    width, height = mask.size
    marks = mask.load()
    boundary = []
    box = mask.getbbox()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if marks[x, y] < 128:
                continue
            if _is_edge(marks, x, y, width, height):
                boundary.append((x, y))
    if not boundary:
        return {"contours": [], "points": []}
    step = max(1, int(step or 6))
    sampled = boundary[::step]
    contour = [_to_percent(x, y, width, height) for x, y in sampled]
    return {"contours": [contour], "points": contour}


def density_step(zoom):
    zoom = float(zoom or 1)
    if zoom < 0.5:
        return 0
    if zoom < 1:
        return 12
    if zoom < 2:
        return 6
    return 3


def _is_edge(marks, x, y, width, height):
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if nx < 0 or ny < 0 or nx >= width or ny >= height:
            return True
        if marks[nx, ny] < 128:
            return True
    return False


def _to_percent(x, y, width, height):
    return {
        "x": round(100.0 * x / max(1, width), 3),
        "y": round(100.0 * y / max(1, height), 3),
    }
