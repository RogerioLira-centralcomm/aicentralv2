"""One source for what a Studio image costs.

The cost catalog (cadu_cost_catalog) holds the provider cost of one image generation. Credits are
that cost converted with the global connector's base rate, which is how the Workspace estimates and
charges media. Criar, Editar and the Workspace tools all read it here so they never disagree.
"""

from __future__ import annotations

from decimal import Decimal

from ..cadu_cost_catalog import cost_metadata
from ..cadu_tool_billing import cost_token_equivalent

# Each extra visual reference adds this share to the generation cost.
REFERENCE_IMAGE_COST_FACTOR = Decimal("0.12")

# OpenAI image models are billed per token. The catalog price above is a flat worst case; the real cost of
# a generation follows the tokens it used, which depend on quality, area and references.
USD_PER_TOKEN = {"input_text": Decimal("0.000005"), "input_image": Decimal("0.000008"), "output_image": Decimal("0.00003")}
OUTPUT_TOKENS_PER_MEGAPIXEL = {"low": 272, "medium": 1056, "high": 4160}
PROMPT_TOKENS = 450
REFERENCE_TOKENS = 1100
TYPICAL_SIZE = (1536, 1024)
QUALITY_LABELS = {"econômica": "low", "padrão": "medium", "alta": "high"}


def usage_cost_usd(usage):
    """Real cost of a token-billed image call from its ``usage``; None when the provider reported no tokens."""
    if not isinstance(usage, dict):
        return None
    details = usage.get("input_tokens_details") or usage.get("prompt_tokens_details") or {}
    image_in = int(details.get("image_tokens") or 0)
    total_in = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    text_in = details.get("text_tokens")
    text_in = max(0, total_in - image_in) if text_in is None else int(text_in or 0)
    out = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    if not out:
        return None
    return float(text_in * USD_PER_TOKEN["input_text"] + image_in * USD_PER_TOKEN["input_image"]
                 + out * USD_PER_TOKEN["output_image"])


def image_estimate_usd(quality="medium", size=TYPICAL_SIZE, reference_count=0) -> Decimal:
    """Best estimate before the call: output tokens by quality scaled by area, plus prompt and references."""
    width, height = size
    megapixels = Decimal(int(width) * int(height)) / Decimal(1024 * 1024)
    output = Decimal(OUTPUT_TOKENS_PER_MEGAPIXEL.get(quality, OUTPUT_TOKENS_PER_MEGAPIXEL["medium"])) * megapixels
    return (output * USD_PER_TOKEN["output_image"] + PROMPT_TOKENS * USD_PER_TOKEN["input_text"]
            + max(0, int(reference_count or 0)) * REFERENCE_TOKENS * USD_PER_TOKEN["input_image"])


def image_credits_by_quality() -> dict:
    """What the desk shows before generating: credits per image at the typical size, for each quality."""
    return {label: cost_token_equivalent(image_estimate_usd(quality), margin_multiplier=1)
            for label, quality in QUALITY_LABELS.items()}


def reference_share(quality="medium") -> float:
    base = image_estimate_usd(quality)
    return float(REFERENCE_TOKENS * USD_PER_TOKEN["input_image"] / base)


def image_generation_usd() -> Decimal:
    """Provider cost of one image generation, from the cost catalog."""
    return Decimal(str(cost_metadata(modality="image").technical_unit_cost_usd))


def image_generation_usd_with_references(reference_count: int = 0) -> Decimal:
    return image_generation_usd() * (Decimal("1") + REFERENCE_IMAGE_COST_FACTOR * max(0, int(reference_count or 0)))


def image_credits(reference_count: int = 0) -> int:
    """Credits one image generation is worth, at the global connector's base rate."""
    return cost_token_equivalent(image_generation_usd_with_references(reference_count), margin_multiplier=1)


def media_tokens_for_cost(cost_usd) -> int:
    """Credits to charge for a media call: its full USD cost at the base rate.

    The provider's own usage tokens are not subtracted: nothing else bills them for a media call, and subtracting
    them made a real image cost about 45% less than the estimate the desk shows (measured 2026-10-06).
    """
    return max(0, cost_token_equivalent(cost_usd or 0, margin_multiplier=1))
