"""Rascunho barato vs publicável no GPT Image 2 — só raster, não montagem."""

from __future__ import annotations

import os

from .creative_modeling_fx import annotate_cost, brl_from_usd


DRAFT = "draft"
PUBLISH = "publish"

# Preços OpenRouter + 5,5% em USD, alinhados à tabela low/high do Image 2.
# A montagem (compositor, LOCK, geometria) não muda com o tier.
IMAGE_TIERS = {
    DRAFT: {
        "name": DRAFT,
        "label_pt": "Rascunho",
        "quality": "low",
        "resolution": "1K",
        "estimated_usd": 0.006,
    },
    PUBLISH: {
        "name": PUBLISH,
        "label_pt": "Publicável",
        "quality": "high",
        "resolution": "2K",
        "estimated_usd": 0.22,
    },
}

PUBLISH_UPGRADE_RULES = """RESOLUTION UPGRADE ONLY
The first attached image is the approved draft of this exact advertisement.
Reproduce the same composition at the higher output resolution.
Do not restyle, recrop, rewrite, translate or omit locked copy.
Do not change CTA, logo mark, hierarchy, crop or camera.
Do not invent a new claim, a second CTA or extra chrome.
This is a resolution conversion, not a new layout."""


def resolve_image_tier(value, default=DRAFT):
    key = str(value or default).strip().lower()
    aliases = {
        "rascunho": DRAFT,
        "low": DRAFT,
        "1k": DRAFT,
        "publicavel": PUBLISH,
        "publicável": PUBLISH,
        "high": PUBLISH,
        "2k": PUBLISH,
    }
    key = aliases.get(key, key)
    if key not in IMAGE_TIERS:
        key = default if default in IMAGE_TIERS else DRAFT
    return dict(IMAGE_TIERS[key])


def image_tier_estimate_usd(value, default=DRAFT):
    tier = resolve_image_tier(value, default)
    env_key = f"CREATIVE_IMAGE_{tier['name'].upper()}_ESTIMATED_COST_USD"
    raw = os.getenv(env_key, "").strip()
    if not raw and tier["name"] == PUBLISH:
        raw = os.getenv("CREATIVE_IMAGE_ESTIMATED_COST_USD", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return float(tier["estimated_usd"])


def describe_image_tiers():
    rows = []
    for name in (DRAFT, PUBLISH):
        tier = resolve_image_tier(name)
        usd = image_tier_estimate_usd(name)
        rows.append(annotate_cost({
            **tier,
            "estimated_usd": usd,
            "estimated_brl": brl_from_usd(usd),
        }, usd))
    return rows


def quote_image_publish(count, fidelity=PUBLISH):
    count = max(0, int(count or 0))
    usd = image_tier_estimate_usd(fidelity)
    total = round(usd * count, 6)
    return annotate_cost({
        "fidelity": resolve_image_tier(fidelity)["name"],
        "count": count,
        "unit_usd": usd,
        "unit_brl": brl_from_usd(usd),
        "total_usd": total,
        "total_brl": brl_from_usd(total),
        "quality": resolve_image_tier(fidelity)["quality"],
        "resolution": resolve_image_tier(fidelity)["resolution"],
    }, total)


def apply_publish_upgrade(prompt):
    text = str(prompt or "").strip()
    if "RESOLUTION UPGRADE ONLY" in text:
        return text
    return f"{text}\n\n{PUBLISH_UPGRADE_RULES}".strip()
