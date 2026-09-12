"""Receitas IAB: copy na área segura, recortes só no poço visual."""

from __future__ import annotations

# x, y, w, h em % do canvas. well = onde as camadas extras se sobrepõem.
RECIPES = {
    "iab-billboard": {
        "logo": (5.2, 18, 8.2, 62),
        "visual": (0, 0, 24, 100),
        "headline": (32, 18, 40, 36),
        "support": (32, 58, 36, 16),
        "cta": (78.5, 36, 16.5, 28),
        "legal": (32, 86, 28, 8),
        "icon": (16, 8, 6, 16),
        "chip": (4, 8, 8, 14),
        "well": (0, 0, 24, 100),
        "type": {"headline": 34, "support": 14, "cta": 15, "legal": 10},
        "density": "wide",
        "park": {"chip"},
    },
    "iab-leaderboard": {
        "logo": (4.2, 16, 7.4, 66),
        "visual": (0, 0, 13, 100),
        "headline": (16.5, 20, 52, 58),
        "support": (0, 8, 10, 36),
        "cta": (75, 18, 21, 64),
        "legal": (0, 12, 10, 28),
        "icon": (1, 20, 8, 40),
        "chip": (1, 28, 8, 32),
        "well": (0, 0, 13, 100),
        "type": {"headline": 16, "support": 10, "cta": 12, "legal": 8},
        "density": "thin",
        "park": {"support", "legal", "icon", "chip"},
    },
    "iab-mobile": {
        "logo": (3.2, 16, 9.5, 68),
        "visual": (0, 0, 11, 100),
        "headline": (15, 22, 50, 56),
        "support": (0, 10, 8, 36),
        "cta": (69, 16, 28, 68),
        "legal": (0, 14, 8, 28),
        "icon": (0.5, 22, 7, 40),
        "chip": (0.5, 30, 7, 32),
        "well": (0, 0, 11, 100),
        "type": {"headline": 11, "support": 8, "cta": 10, "legal": 8},
        "density": "thin",
        "park": {"support", "legal", "icon", "chip"},
    },
    "iab-medium": {
        "logo": (5.2, 5.2, 16, 14),
        "visual": (0, 0, 100, 48),
        "headline": (6, 54, 88, 16),
        "support": (6, 72, 50, 9),
        "cta": (58, 83, 37, 12),
        "legal": (6, 90, 48, 5),
        "icon": (80, 6, 12, 10),
        "chip": (78, 72, 16, 8),
        "well": (0, 0, 100, 48),
        "type": {"headline": 18, "support": 12, "cta": 13, "legal": 9},
        "density": "box",
    },
    "iab-halfpage": {
        "logo": (7, 5.2, 22, 8),
        "visual": (0, 0, 100, 42),
        "headline": (7, 48, 86, 14),
        "support": (7, 64, 86, 9),
        "cta": (7, 80, 86, 8),
        "legal": (7, 90, 86, 5),
        "icon": (74, 5.2, 18, 7),
        "chip": (7, 74, 30, 4.8),
        "well": (0, 0, 100, 42),
        "type": {"headline": 22, "support": 13, "cta": 14, "legal": 10},
        "density": "tall",
    },
    "iab-skyscraper": {
        "logo": (10, 5.2, 42, 8),
        "visual": (0, 0, 100, 38),
        "headline": (8, 46, 84, 16),
        "support": (8, 64, 84, 9),
        "cta": (8, 78, 84, 9),
        "legal": (8, 90, 84, 5),
        "icon": (58, 5.2, 32, 7),
        "chip": (8, 74, 42, 3.8),
        "well": (0, 0, 100, 38),
        "type": {"headline": 16, "support": 11, "cta": 12, "legal": 9},
        "density": "tall",
    },
    "feed-1x1": {
        "logo": (6, 6, 20, 8),
        "visual": (0, 0, 100, 100),
        "headline": (6, 58, 88, 14),
        "support": (6, 74, 88, 8),
        "cta": (18, 85, 64, 7),
        "legal": (6, 94, 88, 4),
        "icon": (78, 6, 14, 8),
        "chip": (6, 50, 28, 6),
        "well": (0, 0, 100, 54),
        "type": {"headline": 36, "support": 16, "cta": 16, "legal": 11},
        "density": "square",
    },
    "feed-4x5": {
        "logo": (7, 5, 22, 7),
        "visual": (0, 0, 100, 100),
        "headline": (7, 60, 86, 14),
        "support": (7, 76, 86, 7),
        "cta": (12, 86, 76, 6.5),
        "legal": (7, 94.5, 86, 3.5),
        "icon": (76, 5, 16, 7),
        "chip": (7, 52, 30, 5),
        "well": (0, 0, 100, 56),
        "type": {"headline": 32, "support": 15, "cta": 15, "legal": 11},
        "density": "tall",
    },
    "story-9x16": {
        "logo": (8, 8, 28, 6),
        "visual": (0, 0, 100, 100),
        "headline": (8, 58, 84, 16),
        "support": (8, 76, 84, 6),
        "cta": (12, 84, 76, 6),
        "legal": (8, 93, 84, 4),
        "icon": (70, 8, 22, 6),
        "chip": (8, 50, 36, 5),
        "well": (0, 0, 100, 52),
        "type": {"headline": 34, "support": 14, "cta": 16, "legal": 11},
        "density": "tall",
        "park": {"support", "chip", "icon"},
    },
    "linkedin-landscape": {
        "logo": (5.2, 12, 10, 28),
        "visual": (0, 0, 36, 100),
        "headline": (40, 16, 36, 36),
        "support": (40, 56, 34, 16),
        "cta": (78, 36, 17, 28),
        "legal": (40, 86, 30, 8),
        "icon": (16, 8, 8, 14),
        "chip": (5.2, 8, 10, 12),
        "well": (0, 0, 36, 100),
        "type": {"headline": 28, "support": 14, "cta": 14, "legal": 10},
        "density": "wide",
        "park": {"chip"},
    },
}

FAMILY_FALLBACK = {
    "wide_banner": "iab-billboard",
    "rectangle": "iab-medium",
    "half_page": "iab-halfpage",
    "square_1x1": "feed-1x1",
    "portrait_4x5": "feed-4x5",
    "story_9x16": "story-9x16",
    "landscape_social": "linkedin-landscape",
}

RECIPE_ALIASES = {
    "reels-9x16": "story-9x16",
    "shorts-9x16": "story-9x16",
}

VISIBLE_COPY = ("logo", "headline", "cta")
LANE_COPY = ("headline", "support", "cta", "legal")
WELL_ROLES = {"product", "visual"}


def recipe_for(format_key, family="wide_banner"):
    key = RECIPE_ALIASES.get(str(format_key or ""), str(format_key or ""))
    if key in RECIPES:
        return dict(RECIPES[key])
    return dict(RECIPES[FAMILY_FALLBACK.get(family, "iab-billboard")])


def box_from_recipe(slot):
    if not slot or len(slot) != 4:
        return None
    x, y, w, h = slot
    return {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}


def fan_in_well(well, index, total):
    well = well if isinstance(well, dict) else {"x": 0, "y": 0, "w": 24, "h": 100}
    cols = 2 if well["w"] >= 18 else 1
    col = index % cols
    row = index // cols
    rows = max(1, (max(total, 1) + cols - 1) // cols)
    cell_w = well["w"] / cols
    cell_h = well["h"] / rows
    overlap_x = cell_w * 0.28
    overlap_y = cell_h * 0.38
    width = max(3.2, cell_w + overlap_x)
    height = max(4.0, cell_h + overlap_y)
    x = well["x"] + col * (cell_w - overlap_x * 0.45)
    y = well["y"] + row * (cell_h - overlap_y * 0.45)
    return clamp_inside({"x": x, "y": y, "w": width, "h": height}, well)


def clamp_inside(box, well):
    right = well["x"] + well["w"]
    bottom = well["y"] + well["h"]
    width = min(box["w"], well["w"])
    height = min(box["h"], well["h"])
    x = min(max(box["x"], well["x"]), right - width)
    y = min(max(box["y"], well["y"]), bottom - height)
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "w": round(width, 2),
        "h": round(height, 2),
    }


def inside_safe(box, inset, slack=0.08):
    pad_x = float(inset.get("x") or 0)
    pad_y = float(inset.get("y") or 0)
    return (
        box["x"] + slack >= pad_x
        and box["y"] + slack >= pad_y
        and box["x"] + box["w"] <= 100 - pad_x + slack
        and box["y"] + box["h"] <= 100 - pad_y + slack
    )


def inside_well(box, well, slack=0.08):
    return (
        box["x"] + slack >= well["x"]
        and box["y"] + slack >= well["y"]
        and box["x"] + box["w"] <= well["x"] + well["w"] + slack
        and box["y"] + box["h"] <= well["y"] + well["h"] + slack
    )


def boxes_overlap(left, right, slack=0.35):
    return not (
        left["x"] + left["w"] <= right["x"] + slack
        or right["x"] + right["w"] <= left["x"] + slack
        or left["y"] + left["h"] <= right["y"] + slack
        or right["y"] + right["h"] <= left["y"] + slack
    )


def in_canvas(box, slack=0.08):
    return (
        box["x"] >= -slack
        and box["y"] >= -slack
        and box["x"] + box["w"] <= 100 + slack
        and box["y"] + box["h"] <= 100 + slack
        and box["w"] > 0
        and box["h"] > 0
    )


def validate_stack(stack):
    issues = []
    inset = (stack or {}).get("safe") or {}
    well = (stack or {}).get("well") or {"x": 0, "y": 0, "w": 24, "h": 100}
    layers = list((stack or {}).get("layers") or [])
    by_role = {item["role"]: item for item in layers}
    for role in VISIBLE_COPY:
        box = by_role.get(role)
        if not box:
            issues.append(f"{role} ausente")
            continue
        if not inside_safe(box, inset):
            issues.append(f"{role} fora da área segura")
        if not in_canvas(box):
            issues.append(f"{role} sai do canvas")
    lanes = []
    for role in LANE_COPY:
        box = by_role.get(role)
        if not box or box.get("parked"):
            continue
        lanes.append((role, box))
    for index, (role, box) in enumerate(lanes):
        for other_role, other in lanes[index + 1 :]:
            if boxes_overlap(box, other):
                issues.append(f"{role} cobre {other_role}")
    for item in layers:
        role = str(item.get("role") or "")
        if not in_canvas(item):
            issues.append(f"{role} sai do canvas")
        if item.get("parked") or role.startswith("ornament") or role == "product":
            if not inside_well(item, well):
                issues.append(f"{role} fora do poço visual")
    return issues
