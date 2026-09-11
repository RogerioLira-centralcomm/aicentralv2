"""Payload completo da mesa Marcas → contexto do lab CTV."""

from __future__ import annotations

from ..creative_brand_dna import materialize_brand_dna
from ..creative_modeling_service import hydrate_client_from_creative_line


def _list(value, limit=12):
    if isinstance(value, str):
        items = [line.strip() for line in value.splitlines() if line.strip()]
    elif isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        return []
    return items[:limit]


def _hexes(palette):
    colors = []
    for item in palette or []:
        if isinstance(item, dict) and item.get("hex"):
            colors.append(str(item["hex"]))
        elif isinstance(item, str) and item.startswith("#"):
            colors.append(item)
    return colors[:8]


def _asset_url(asset):
    if not isinstance(asset, dict):
        return ""
    return str(
        asset.get("asset_url")
        or asset.get("stored_url")
        or asset.get("source_url")
        or ""
    )


def build_brand_context(client=None, extra_assets=None):
    client = hydrate_client_from_creative_line(client if isinstance(client, dict) else {})
    profile = client.get("brand_profile") if isinstance(client.get("brand_profile"), dict) else {}
    line = profile.get("creative_line") if isinstance(profile.get("creative_line"), dict) else {}
    dna = materialize_brand_dna(client, profile, profile.get("brand_dna"))
    assets = list(client.get("brand_assets") or [])
    if extra_assets:
        assets.extend(item for item in extra_assets if isinstance(item, dict))
    logos = [item for item in assets if item.get("role") == "logo"]
    references = [item for item in assets if item.get("role") in {"reference", "creative"}]
    logo_url = (
        dna.get("logo", {}).get("asset_url")
        or client.get("logo_upload_path")
        or client.get("logo_url")
        or _asset_url(logos[0] if logos else {})
    )
    palette = _hexes(profile.get("color_palette") or line.get("color_palette"))
    if client.get("primary_color") and client["primary_color"] not in palette:
        palette = [client["primary_color"], *palette]
    if client.get("secondary_color") and client["secondary_color"] not in palette:
        palette.append(client["secondary_color"])
    fonts = profile.get("fonts") if isinstance(profile.get("fonts"), list) else []
    if not fonts and (line.get("copy_system") or {}).get("typography", {}).get("family"):
        fonts = [{"family": line["copy_system"]["typography"]["family"]}]
    return {
        "id": client.get("id"),
        "name": client.get("name") or "",
        "sector": client.get("sector") or "",
        "tone_of_voice": client.get("tone_of_voice") or " ".join(_list(line.get("copy_patterns"), 2)),
        "website_url": client.get("website_url") or "",
        "logo_url": logo_url,
        "primary_color": client.get("primary_color") or (palette[0] if palette else ""),
        "secondary_color": client.get("secondary_color") or (palette[1] if len(palette) > 1 else ""),
        "palette": palette,
        "fonts": fonts,
        "brand_summary": profile.get("brand_summary") or line.get("signature_summary") or "",
        "target_audience": profile.get("target_audience") or "",
        "ad_segments": _list(profile.get("ad_segments")),
        "campaign_opportunities": _list(profile.get("campaign_opportunities")),
        "products_services": _list(profile.get("products_services")),
        "differentiators": _list(profile.get("differentiators")),
        "proof_points": _list(profile.get("proof_points")),
        "visual_motifs": _list(profile.get("visual_motifs") or line.get("graphic_devices")),
        "mandatory_elements": _list(profile.get("mandatory_elements") or line.get("must_preserve")),
        "forbidden_elements": _list(profile.get("forbidden_elements") or line.get("avoid")),
        "creative_guidelines": profile.get("creative_guidelines") or " ".join(_list(line.get("composition_rules"), 3)),
        "creative_line": {
            "signature_summary": line.get("signature_summary") or "",
            "copy_patterns": _list(line.get("copy_patterns"), 6),
            "composition_rules": _list(line.get("composition_rules"), 6),
            "gpt_image_instruction": line.get("gpt_image_instruction") or "",
        },
        "brand_dna": dna,
        "design_system_ads": profile.get("design_system_ads") if isinstance(profile.get("design_system_ads"), dict) else {},
        "analysis_metadata": client.get("analysis_metadata") or {},
        "assets": {
            "logo": [_asset_url(item) for item in logos if _asset_url(item)][:3],
            "references": [_asset_url(item) for item in references if _asset_url(item)][:8],
        },
        "source": "marcas",
    }


def _collect_urls(*groups):
    urls = []
    for group in groups:
        for url in group or []:
            if url and url not in urls:
                urls.append(url)
    return urls


def reference_images(brand_context, user_images=None):
    assets = brand_context.get("assets") if isinstance(brand_context, dict) else {}
    return _collect_urls(
        user_images,
        (assets or {}).get("logo"),
        (assets or {}).get("references"),
    )[:8]


def scene_photos(brand_context, user_images=None):
    """Fotos de cena: arquivos da mesa primeiro, depois referências de Marcas. Logo não vira fundo."""
    assets = brand_context.get("assets") if isinstance(brand_context, dict) else {}
    return _collect_urls(user_images, (assets or {}).get("references"))[:4]
