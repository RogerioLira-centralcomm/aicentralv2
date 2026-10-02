"""Delivery files: the lightest encoding that keeps the piece clean.

Display units have an initial-load weight budget (150 KB); social formats have none and are simply kept
as small as possible. JPEG wins for photographs, PNG for flat artwork or real transparency.
"""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

JPEG_QUALITIES = (88, 82, 76, 70, 64, 58)


def _has_transparency(image):
    if image.mode not in {"RGBA", "LA", "P"}:
        return False
    alpha = image.convert("RGBA").getchannel("A")
    return alpha.getextrema()[0] < 250


def _jpeg(image, quality):
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True, progressive=True)
    return buffer.getvalue()


def _png(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def smallest_encoding(encoded, budget_kb=None):
    """Return (base64, format, size_kb) for the lightest acceptable file."""
    image = Image.open(io.BytesIO(base64.b64decode(str(encoded), validate=True)))
    image.load()
    png = _png(image)
    if _has_transparency(image):
        return base64.b64encode(png).decode("ascii"), "png", round(len(png) / 1024, 1)
    budget = budget_kb * 1024 if budget_kb else None
    choice = None
    for quality in JPEG_QUALITIES:
        content = _jpeg(image, quality)
        if budget is None or len(content) <= budget:
            choice = ("jpeg", content)
            break
    if choice is None:
        content = _jpeg(image, JPEG_QUALITIES[-1])
        logger.warning("Studio export above weight budget size_kb=%.0f budget_kb=%s", len(content) / 1024, budget_kb)
        choice = ("jpeg", content)
    if len(png) < len(choice[1]):  # flat artwork compresses better losslessly
        choice = ("png", png)
    return base64.b64encode(choice[1]).decode("ascii"), choice[0], round(len(choice[1]) / 1024, 1)


def save_sibling(image_url, suffix, encoded, output_format):
    """Write a companion file (e.g. the 2x) next to a delivered image; returns its URL."""
    from flask import current_app
    if not str(image_url).startswith("/static/uploads/creative_generated/"):
        return None
    static_root = Path(current_app.static_folder).resolve()
    path = (static_root / str(image_url).removeprefix("/static/")).resolve()
    extension = ".jpg" if output_format in {"jpg", "jpeg"} else f".{output_format}"
    target = path.with_name(f"{path.stem}{suffix}{extension}")
    target.write_bytes(base64.b64decode(encoded))
    return f"/static/uploads/creative_generated/{target.name}"
