"""Design System Ads — contrato de anúncio compilado em CSS e Tailwind."""

from .adapt import adapt_system, clamp_layer_count, list_iab_formats, swap_layer_positions
from .campaign import (
    CENTRALCOMM_CAMPAIGN_SLUG,
    ensure_campaign_design_system,
    is_campaign_preset_id,
)
from .cutouts import paint_white_background, white_to_transparent
from .centralcomm import CENTRALCOMM_SLUG, centralcomm_preset, is_centralcomm_client
from .materialize import ensure_brand_design_system
from .refine import apply_token_patches, clamp_passes, refine_design_system
from .render import render_specimen, table_html, tailwind_theme
from .schema import DesignSystemAds, dump_system, parse_system

__all__ = (
    "CENTRALCOMM_CAMPAIGN_SLUG",
    "CENTRALCOMM_SLUG",
    "DesignSystemAds",
    "adapt_system",
    "apply_token_patches",
    "centralcomm_preset",
    "clamp_layer_count",
    "clamp_passes",
    "dump_system",
    "ensure_brand_design_system",
    "ensure_campaign_design_system",
    "is_campaign_preset_id",
    "is_centralcomm_client",
    "list_iab_formats",
    "paint_white_background",
    "parse_system",
    "refine_design_system",
    "render_specimen",
    "swap_layer_positions",
    "table_html",
    "tailwind_theme",
    "white_to_transparent",
)
