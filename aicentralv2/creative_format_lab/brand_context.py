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


def _fonts(value):
    """Normalize the small font contract shared by Workspace and Studio.

    A family is only treated as approved when it was entered or approved by a
    person. Visual analysis can still contribute a *classification* (for
    example, ``sans geométrica``) without pretending it discovered the
    licensed font used by a wordmark.
    """
    items = value if isinstance(value, list) else []
    fonts = []
    for index, item in enumerate(items[:6]):
        raw = item if isinstance(item, dict) else {"family": item}
        family = str(raw.get("family") or "").strip()[:100]
        classification = str(raw.get("classification") or "").strip()[:100]
        if not family and not classification:
            continue
        role = str(raw.get("role") or ("display" if index == 0 else "body")).strip().lower()[:24]
        if role not in {"display", "body", "accent", "legal", "ui"}:
            role = "body"
        source = str(raw.get("source") or "manual").strip().lower()[:32]
        try:
            confidence = max(0.0, min(float(raw.get("confidence", 1)), 1.0))
        except (TypeError, ValueError):
            confidence = 1.0
        fonts.append({
            "family": family,
            "classification": classification,
            "role": role,
            "weight": str(raw.get("weight") or "").strip()[:32],
            "style": str(raw.get("style") or "").strip()[:32],
            "source": source,
            "confidence": confidence,
        })
    return fonts


def _asset_url(asset):
    if not isinstance(asset, dict):
        return ""
    return str(
        asset.get("asset_url")
        or asset.get("asset_path")
        or asset.get("stored_url")
        or asset.get("source_url")
        or ""
    )


def _asset_exists(url):
    """Do not expose local creative uploads that disappeared after a deploy."""
    value = str(url or "")
    if not value.startswith("/static/uploads/creative_references/"):
        return bool(value)
    try:
        from ..creative_modeling_storage import CreativeAssetStorage
        return bool(CreativeAssetStorage().absolute_reference_path(value))
    except Exception:
        return False


def _logo_pixel_evidence(url):
    """Read local logo pixels when possible; external assets stay metadata-only."""
    raw = str(url or "")
    if not raw.startswith("/static/"):
        return {}
    try:
        from pathlib import Path
        from flask import current_app
        from PIL import Image

        static_root = Path(current_app.static_folder).resolve()
        path = (static_root / raw.removeprefix("/static/")).resolve()
        path.relative_to(static_root)
        if not path.is_file():
            return {}
        image = Image.open(path).convert("RGBA")
        image.thumbnail((96, 96))
        pixels = list(image.getdata())
        visible = [pixel for pixel in pixels if pixel[3] > 24]
        if not visible:
            return {"transparent": True}
        transparent = (len(pixels) - len(visible)) / len(pixels) > .04
        luminance = sum(.2126 * red + .7152 * green + .0722 * blue for red, green, blue, _ in visible) / len(visible)
        return {"transparent": transparent, "luminance": luminance}
    except Exception:
        return {}


def _logo_classification(asset):
    """Classify a stored logo without inventing visual evidence.

    Asset dimensions and names are durable evidence at ingest time.  We expose
    a concise description to the Studio so people can choose among several
    approved files and the director never has to guess which variant to use.
    """
    item = asset if isinstance(asset, dict) else {}
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    name = " ".join(str(value or "") for value in (
        metadata.get("original_name"), item.get("asset_path"), item.get("source_url"),
    )).lower()
    try:
        width, height = float(item.get("width") or 0), float(item.get("height") or 0)
    except (TypeError, ValueError):
        width, height = 0, 0
    ratio = width / height if width > 0 and height > 0 else 0
    if "favicon" in name or "fav-icon" in name or (width and height and max(width, height) <= 64):
        shape = "favicon"
    elif "icon" in name or "symbol" in name or (ratio and .78 <= ratio <= 1.28):
        shape = "ícone"
    elif ratio >= 1.45 or any(token in name for token in ("horizontal", "landscape", "wordmark")):
        shape = "horizontal"
    elif ratio and ratio <= .72 or any(token in name for token in ("vertical", "stacked", "portrait")):
        shape = "vertical"
    else:
        shape = "logo"
    pixels = _logo_pixel_evidence(_asset_url(item))
    luminance = pixels.get("luminance")
    if luminance is not None and luminance >= 210:
        variant = "branca"
    elif luminance is not None and luminance <= 70:
        variant = "preta"
    elif any(token in name for token in ("white", "branco", "light", "claro")):
        variant = "branca"
    elif any(token in name for token in ("black", "preto", "dark", "escuro")):
        variant = "preta"
    else:
        variant = "colorida"
    if pixels.get("transparent"):
        background = "transparente"
    elif variant == "branca":
        background = "fundo escuro"
    elif variant == "preta":
        background = "fundo claro"
    elif any(token in name for token in ("transparent", "transparente", ".png", ".svg", ".webp")):
        background = "transparente"
    else:
        background = "fundo neutro"
    return {"shape": shape, "variant": variant, "background": background}


def _logo_asset(asset, index):
    item = asset if isinstance(asset, dict) else {}
    url = _asset_url(item)
    classification = _logo_classification(item)
    return {
        "id": str(item.get("id") or f"brand:logo:{index}"),
        "url": url,
        "label": str((item.get("metadata") or {}).get("original_name") or f"Logo {index + 1}"),
        "width": item.get("width") or 0,
        "height": item.get("height") or 0,
        "is_primary": bool(item.get("is_primary")),
        "classification": classification,
    }


def _is_logo_asset(asset):
    """Recognize legacy logo uploads without treating every reference as one."""
    item = asset if isinstance(asset, dict) else {}
    if item.get("role") == "logo" or item.get("is_logo") is True:
        return True
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    evidence = " ".join(str(value or "") for value in (
        metadata.get("original_name"), metadata.get("asset_type"), metadata.get("kind"),
        item.get("asset_path"), item.get("source_url"),
    )).lower()
    return any(token in evidence for token in (
        "logo", "logotipo", "wordmark", "brandmark", "brand-mark", "favicon", "fav-icon",
    ))


def select_brand_logo(brand_context, selected_logo_id=None):
    """Apply only a known approved logo selection to a brand context."""
    context = dict(brand_context or {})
    assets = dict(context.get("assets") or {})
    logos = [dict(item) for item in assets.get("logos", []) if isinstance(item, dict)]
    selected = next((item for item in logos if str(item.get("id")) == str(selected_logo_id or "")), None)
    if not selected:
        selected = next((item for item in logos if item.get("is_primary")), None)
    if not selected and logos:
        selected = logos[0]
    if selected and selected.get("url"):
        context["logo_url"] = selected["url"]
        context["selected_logo_id"] = selected["id"]
        assets["logo"] = [selected["url"], *[item["url"] for item in logos if item.get("url") and item["url"] != selected["url"]]]
    assets["logos"] = logos
    context["assets"] = assets
    return context


def identity_readiness(logo_url="", palette=None, assets=None):
    """Expose whether a brand can be rendered without making identity up.

    A name alone identifies the project but is not enough to draw a logo or
    claim a color system. Keep this small status with the brand context so
    every Studio surface can warn before a generation instead of discovering
    the gap after an invented mark reaches the canvas.
    """
    asset_map = assets if isinstance(assets, dict) else {}
    has_logo = bool(str(logo_url or "").strip() or any(asset_map.get("logo") or []))
    has_palette = bool(_hexes(palette))
    missing = []
    if not has_logo:
        missing.append("logo")
    if not has_palette:
        missing.append("cores")
    return {
        "status": "ready" if not missing else "partial" if len(missing) == 1 else "missing",
        "has_logo": has_logo,
        "has_palette": has_palette,
        "missing": missing,
    }


def build_brand_context(client=None, extra_assets=None):
    client = hydrate_client_from_creative_line(client if isinstance(client, dict) else {})
    profile = client.get("brand_profile") if isinstance(client.get("brand_profile"), dict) else {}
    line = profile.get("creative_line") if isinstance(profile.get("creative_line"), dict) else {}
    dna = materialize_brand_dna(client, profile, profile.get("brand_dna"))
    assets = list(client.get("brand_assets") or [])
    if extra_assets:
        assets.extend(item for item in extra_assets if isinstance(item, dict))
    logos = [item for item in assets if _is_logo_asset(item)]
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
    fonts = _fonts(profile.get("fonts"))
    if not fonts and (line.get("copy_system") or {}).get("typography", {}).get("family"):
        fonts = _fonts([{"family": line["copy_system"]["typography"]["family"], "role": "display", "source": "creative_line"}])
    logo_options = [_logo_asset(item, index) for index, item in enumerate(logos) if _asset_url(item)]
    if logo_url and not any(item["url"] == logo_url for item in logo_options):
        logo_options.insert(0, {
            "id": "brand:primary-logo", "url": logo_url, "label": "Logo principal",
            "width": 0, "height": 0, "is_primary": True,
            "classification": {"shape": "logo", "variant": "colorida", "background": "fundo neutro"},
        })
    asset_context = {
        "logo": [item["url"] for item in logo_options][:8],
        "logos": logo_options[:8],
        "references": [url for item in references
                       for url in [_asset_url(item)]
                       if _asset_exists(url)][:8],
    }
    return select_brand_logo({
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
        "assets": asset_context,
        "readiness": identity_readiness(logo_url, palette, asset_context),
        "source": "marcas",
    })


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
