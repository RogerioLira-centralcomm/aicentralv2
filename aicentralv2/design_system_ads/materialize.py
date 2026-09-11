"""Compila o DS Ads a partir da marca. CentralComm usa o preset Tailwind."""

from __future__ import annotations

from ..creative_brand_dna import materialize_brand_dna
from .centralcomm import centralcomm_preset, is_centralcomm_client
from .ingest import merge_extracted_tokens
from .refine import heal_contrast
from .schema import FRAMEWORK, DesignSystemAds, normalize_hex, parse_system


def _text(value, default="", limit=80):
    text = str(value or "").strip()
    return (text or default)[:limit]


def _hexes(items):
    colors = []
    for item in items or []:
        if isinstance(item, dict):
            color = normalize_hex(item.get("hex") or item.get("color") or item.get("value"))
        else:
            color = normalize_hex(item)
        if color and color not in colors:
            colors.append(color)
        if len(colors) >= 8:
            break
    return colors


def _fonts(profile, line, dna):
    fonts = profile.get("fonts") if isinstance(profile.get("fonts"), list) else []
    display = ""
    body = ""
    for item in fonts:
        if not isinstance(item, dict):
            family = _text(item, limit=80)
            if family and not display:
                display = family
            continue
        family = _text(item.get("family"), limit=80)
        role = str(item.get("role") or "").strip().lower()
        if not family:
            continue
        if role in {"display", "heading", "headline", "title", "primary"} and not display:
            display = family
        elif not body:
            body = family
    if not display:
        display = _text((dna.get("fonts") or {}).get("primary"), limit=80)
    if not body:
        typography = ((line.get("copy_system") or {}).get("typography") or {})
        body = _text(
            (dna.get("fonts") or {}).get("fallback") or typography.get("family"),
            default=display,
            limit=80,
        )
    return display or "Inter", body or display or "Inter"


def _existing_system(client, profile):
    stored = profile.get("design_system_ads")
    if isinstance(stored, dict) and (
        stored.get("framework") == FRAMEWORK or stored.get("tokens")
    ):
        parsed = parse_system(stored)
        if client.get("id") and not parsed.client_id:
            parsed.client_id = client.get("id")
        return parsed
    return None


def ensure_brand_design_system(client=None, *, existing=None):
    client = client if isinstance(client, dict) else {}
    profile = client.get("brand_profile") if isinstance(client.get("brand_profile"), dict) else {}
    line = profile.get("creative_line") if isinstance(profile.get("creative_line"), dict) else {}
    found = existing if existing is not None else _existing_system(client, profile)
    if found:
        return parse_system(found)

    if is_centralcomm_client(client) or is_centralcomm_client(client.get("name")):
        preset = centralcomm_preset(client_id=client.get("id") or "centralcomm")
        logo = (
            client.get("logo_upload_path")
            or client.get("logo_url")
            or preset.logo_url
        )
        tokens = dict(preset.tokens)
        tokens["logo"] = logo
        return DesignSystemAds.model_validate(
            {
                **preset.model_dump(),
                "client_id": client.get("id") or preset.client_id,
                "logo_url": logo,
                "tokens": tokens,
            }
        )

    dna = materialize_brand_dna(client, profile, profile.get("brand_dna"))
    palette = _hexes(
        profile.get("color_palette")
        or line.get("color_palette")
        or (dna.get("colors") or {}).get("palette")
    )
    if client.get("primary_color"):
        palette = _hexes([client.get("primary_color"), *palette])
    if client.get("secondary_color"):
        palette = _hexes([*palette, client.get("secondary_color")])
    ink = palette[0] if palette else "#1E4D4F"
    highlight = palette[1] if len(palette) > 1 else "#F3B71B"
    display, body = _fonts(profile, line, dna)
    logo = (
        (dna.get("logo") or {}).get("asset_url")
        or client.get("logo_upload_path")
        or client.get("logo_url")
        or ""
    )
    name = _text(client.get("name"), default="Design System Ads", limit=80)
    client_id = client.get("id") or "marca"
    tokens = {
        "paper": "#FFFFFF",
        "ink": ink,
        "accent": ink,
        "muted": "#3D4451",
        "cta_ink": "#FFFFFF",
        "highlight": highlight,
        "logo": logo,
        "font-display": display,
        "font-body": body,
    }
    extracted = (
        profile.get("extracted_design_system")
        or profile.get("extract_design_system")
        or client.get("extracted_design_system")
    )
    source = "brand"
    evidence = {}
    if extracted:
        tokens, evidence = merge_extracted_tokens(tokens, extracted, client=client)
        tokens["logo"] = logo or tokens.get("logo") or ""
        source = "extract-design-system"
    system = DesignSystemAds.model_validate(
        {
            "id": f"dsa-{client_id}-v1",
            "scope": "brand",
            "name": f"{name} Ads" if name != "Design System Ads" else name,
            "source": source,
            "status": "draft",
            "client_id": client_id,
            "logo_url": logo,
            "tokens": tokens,
            "evidence": evidence,
            "ad_copy": {
                "headline": "A peça na tinta certa",
                "support": f"O anúncio herda o Design System Ads de {name}."
                if name != "Design System Ads"
                else "O anúncio herda o Design System Ads da marca.",
                "cta": "Ver o sistema",
                "legal": f"{name} · Design System Ads",
            },
        }
    )
    if extracted:
        system, _patches = heal_contrast(system)
    return system
