"""Bbox percentual da Camadas → pixels."""


def pixel_box(bbox, width, height):
    box = bbox if isinstance(bbox, dict) else {}
    try:
        left = int(width * float(box.get("x") or 0) / 100)
        top = int(height * float(box.get("y") or 0) / 100)
        right = int(width * (float(box.get("x") or 0) + float(box.get("w") or 0)) / 100)
        bottom = int(height * (float(box.get("y") or 0) + float(box.get("h") or 0)) / 100)
    except (TypeError, ValueError):
        return None
    left = max(0, min(width, left))
    top = max(0, min(height, top))
    right = max(0, min(width, right))
    bottom = max(0, min(height, bottom))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom
