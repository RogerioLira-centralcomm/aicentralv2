"""One size plan per delivery format: what to ask the image model for and how to deliver it.

Every part of the Studio that deals with pixels (composition mask, prompt, provider call, trim, export)
reads the same plan, so the picture the model composes is the picture that is delivered.

gpt-image-2 limits, confirmed by probing the API on 2026-10-02:
  - both sides divisible by 16 (1000x1000 rejected)
  - aspect ratio at most 3:1 either way (2000x640 rejected, 1920x640 accepted)
  - a minimum pixel budget between 0.59 and 0.65 MP (768x768 rejected, 1024x640 accepted)
  - 3840x1280 accepted
"""
from __future__ import annotations

import math

STEP = 16
MAX_RATIO = 3.0
MIN_PIXELS = 655_360
MAX_SIDE = 3840
# Target area per provider quality: enough detail for 2x delivery without paying for unused pixels.
TARGET_PIXELS = {"low": 1_500_000, "medium": 1_500_000, "high": 3_000_000}
# Initial-load weight budget for display units; social formats are just kept as small as possible.
DISPLAY_WEIGHT_KB = 150
DISPLAY_SIZES = {(300, 250), (300, 300), (300, 600), (160, 600), (970, 250), (728, 90), (320, 50), (336, 280), (320, 100)}


def generation_size(width, height, quality="medium", floor=None):
    """Closest provider size (multiples of 16, ratio within 3:1) for a delivery size.

    ``floor`` is the smallest size worth delivering (W, H); the generation never goes below it when the
    provider limits allow, so nothing is upscaled.
    """
    target_ratio = width / height
    ratio = min(MAX_RATIO, max(1 / MAX_RATIO, target_ratio))
    floor_w, floor_h = floor or (0, 0)
    area = max(TARGET_PIXELS.get(str(quality or "medium").lower(), TARGET_PIXELS["medium"]), floor_w * floor_h)
    best = None
    ideal_h = math.sqrt(area / ratio)
    for gh in range(max(STEP, int(ideal_h * 0.8) // STEP * STEP), int(ideal_h * 1.6) + STEP, STEP):
        gw = max(STEP, round(gh * ratio / STEP) * STEP)
        if gw * gh < MIN_PIXELS or max(gw, gh) > MAX_SIDE or not (1 / MAX_RATIO <= gw / gh <= MAX_RATIO):
            continue
        error = abs(math.log((gw / gh) / ratio))
        # the floor only binds the side that survives the trim
        short = (gw < floor_w and target_ratio >= ratio) or (gh < floor_h and target_ratio <= ratio)
        score = (short, round(error, 4), abs(gw * gh - area))
        if best is None or score < best[0]:
            best = (score, (gw, gh))
    if best is None:
        raise ValueError("Não há tamanho de geração válido para este formato.")
    return best[1]


def frame_in(generation, width, height):
    """Where the delivered canvas sits inside the generated one, as fractions (x, y, w, h)."""
    source, target = generation[0] / generation[1], width / height
    if abs(math.log(source / target)) < 0.01:
        return (0.0, 0.0, 1.0, 1.0)
    if source < target:
        h = source / target
        return (0.0, (1 - h) / 2, 1.0, h)
    w = target / source
    return ((1 - w) / 2, 0.0, w, 1.0)


def plan(width, height, quality="medium"):
    width, height = int(width), int(height)
    display = (width, height) in DISPLAY_SIZES
    # Display units ship 1x and 2x (high-density screens); social formats ship at the platform's own size.
    floor = (width * 2, height * 2) if display else (width, height)
    generation = generation_size(width, height, quality, floor)
    frame = frame_in(generation, width, height)
    return {
        "delivery": (width, height),
        "delivery_2x": (width * 2, height * 2) if display else None,
        "generation": generation,
        "frame": frame,
        "strategy": "native" if frame == (0.0, 0.0, 1.0, 1.0) else "composed",
        "weight_budget_kb": DISPLAY_WEIGHT_KB if display else None,
    }
