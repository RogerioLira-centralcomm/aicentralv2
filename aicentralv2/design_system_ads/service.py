"""Fachada: preset CentralComm, persistência na marca, refine e approve."""

from __future__ import annotations

from .adapt import MIN_LAYERS, MAX_LAYERS, adapt_system, list_iab_formats
from .campaign import (
    CENTRALCOMM_CAMPAIGN_SLUG,
    centralcomm_campaign_brief,
    ensure_campaign_design_system,
    is_campaign_preset_id,
    layer_count_from_elements,
)
from .centralcomm import CENTRALCOMM_SLUG, centralcomm_preset
from .materialize import ensure_brand_design_system
from .refine import refine_design_system
from .render import render_specimen, table_html, tailwind_theme
from .schema import dump_system, parse_system


def payload_for(system, *, format_key=None, layer_count=None, swaps=None):
    parsed = parse_system(system)
    stack = None
    if format_key:
        if layer_count in (None, "") and parsed.elements:
            layer_count = layer_count_from_elements(parsed.elements)
        parsed, stack = adapt_system(
            parsed, format_key, layer_count or MIN_LAYERS, swaps=swaps
        )
    parsed.specimen_html = render_specimen(parsed, standalone=False, stack=stack)
    data = dump_system(parsed)
    data["table_html"] = table_html(parsed)
    data["tailwind"] = tailwind_theme(parsed)
    if parsed.scope == "campaign":
        data["specimen_url"] = specimen_campaign_path(
            parsed.id.replace("dsa-campaign-", "") if parsed.id else CENTRALCOMM_CAMPAIGN_SLUG,
            format_key,
            layer_count,
        )
    else:
        data["specimen_url"] = specimen_path(parsed.client_id, format_key, layer_count)
    data["iab_formats"] = list_iab_formats()
    data["layers"] = {
        "min": MIN_LAYERS,
        "max": MAX_LAYERS,
        "count": int((stack or {}).get("layer_count") or MIN_LAYERS),
    }
    data["elements"] = list(parsed.elements or [])
    data["creative_line"] = parsed.creative_line or ""
    if stack:
        data["adapt"] = stack
    return data


def specimen_path(client_id, format_key=None, layer_count=None):
    slug = client_id if client_id not in (None, "") else CENTRALCOMM_SLUG
    path = f"/lab/design-system/marca/{slug}"
    return _with_query(path, format_key, layer_count)


def specimen_campaign_path(campaign_id, format_key=None, layer_count=None):
    slug = campaign_id if campaign_id not in (None, "") else CENTRALCOMM_CAMPAIGN_SLUG
    path = f"/lab/design-system/campanha/{slug}"
    return _with_query(path, format_key, layer_count)


def _with_query(path, format_key, layer_count):
    query = []
    if format_key:
        query.append(f"format={format_key}")
    if layer_count:
        query.append(f"layers={layer_count}")
    return f"{path}?{'&'.join(query)}" if query else path


def is_preset_id(client_id):
    return str(client_id or "").strip().lower() == CENTRALCOMM_SLUG


def read_preset():
    return payload_for(centralcomm_preset(status="approved"))


def read_campaign_preset():
    system, _elements = ensure_campaign_design_system(
        centralcomm_preset(status="approved"),
        centralcomm_campaign_brief(),
    )
    system.status = "approved"
    return payload_for(system, format_key="iab-billboard")


def materialize_client(client, existing=None):
    return ensure_brand_design_system(client, existing=existing)


def run_refine(system, *, attempts=4, text_callable=None, reference_urls=None):
    refined, reports = refine_design_system(
        system,
        attempts=attempts,
        text_callable=text_callable,
        reference_urls=reference_urls,
    )
    return refined, reports


def mark_approved(system):
    data = dump_system(system)
    data["status"] = "approved"
    return parse_system(data)
