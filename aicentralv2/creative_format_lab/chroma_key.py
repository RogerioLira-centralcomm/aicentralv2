"""Real transparency for "remove background".

GPT Image 2 cannot return an alpha channel; asked for a transparent background it paints a checkerboard
into the pixels. Instead the model places the subject on a flat chroma green, and this module keys that
colour out into a real alpha channel, with a soft edge and green spill removed from the borders.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

CHROMA_HEX = "#00FF00"
_CHROMA = np.array([0, 255, 0], dtype=np.float32)


def _background_colour(rgb):
    """The keyed colour actually used, read from the image border (models drift a little from #00FF00)."""
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).astype(np.float32)
    greenish = border[(border[:, 1] > border[:, 0] + 60) & (border[:, 1] > border[:, 2] + 60)]
    return np.median(greenish, axis=0) if len(greenish) >= max(8, len(border) // 10) else _CHROMA


def chroma_key_png(png_bytes, *, inner=60.0, outer=150.0):
    """Return PNG bytes with the chroma background turned transparent.

    Pixels within ``inner`` (RGB distance) of the background colour become fully transparent, pixels
    beyond ``outer`` stay opaque, and the band between gets a smooth alpha. Edge pixels lose their green
    cast (despill) so they do not glow green on a dark layout.
    """
    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    pixels = np.asarray(image).astype(np.float32)
    rgb, alpha = pixels[..., :3], pixels[..., 3]
    key = _background_colour(rgb[..., :3])
    distance = np.sqrt(((rgb - key) ** 2).sum(axis=-1))
    # Strongly green pixels also count as background even if shaded (soft shadows on the green).
    green_excess = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
    keyed = np.clip((distance - inner) / max(1.0, outer - inner), 0.0, 1.0)
    keyed = np.where(green_excess > 90, np.minimum(keyed, np.clip((150 - green_excess) / 60, 0.0, 1.0)), keyed)
    new_alpha = np.minimum(alpha, keyed * 255.0)
    # Despill: on the soft edge, pull green down to the strongest of red and blue.
    edge = (keyed < 1.0) & (green_excess > 0)
    rgb[..., 1] = np.where(edge, np.maximum(rgb[..., 0], rgb[..., 2]) + np.maximum(0, green_excess) * keyed * 0.15, rgb[..., 1])
    out = np.dstack([np.clip(rgb, 0, 255), np.clip(new_alpha, 0, 255)]).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(out, "RGBA").save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def has_real_transparency(png_bytes, minimum_share=0.02):
    """True when at least ``minimum_share`` of the pixels are fully transparent."""
    image = Image.open(io.BytesIO(png_bytes))
    if "A" not in image.getbands():
        return False
    alpha = np.asarray(image.getchannel("A"))
    return float((alpha == 0).mean()) >= minimum_share
