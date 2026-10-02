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


def image_generation_usd() -> Decimal:
    """Provider cost of one image generation, from the cost catalog."""
    return Decimal(str(cost_metadata(modality="image").technical_unit_cost_usd))


def image_generation_usd_with_references(reference_count: int = 0) -> Decimal:
    return image_generation_usd() * (Decimal("1") + REFERENCE_IMAGE_COST_FACTOR * max(0, int(reference_count or 0)))


def image_credits(reference_count: int = 0) -> int:
    """Credits one image generation is worth, at the global connector's base rate."""
    return cost_token_equivalent(image_generation_usd_with_references(reference_count), margin_multiplier=1)


def media_tokens_for_cost(cost_usd, provider_tokens: int = 0) -> int:
    """Credits to charge for a media call: its USD cost at the base rate, minus tokens already billed."""
    return max(0, cost_token_equivalent(cost_usd or 0, margin_multiplier=1) - max(0, int(provider_tokens or 0)))
