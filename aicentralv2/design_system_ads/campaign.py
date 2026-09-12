"""DS da campanha: herda a marca, aplica a linha criativa e empilha até 40 recortes."""

from __future__ import annotations

from .adapt import MAX_LAYERS, MIN_LAYERS, clamp_layer_count
from .schema import DesignSystemAds, dump_system, parse_system

MAX_ELEMENTS = MAX_LAYERS
CENTRALCOMM_CAMPAIGN_SLUG = "centralcomm-verao"

ROLE_HINTS = (
    ("product", ("produto", "product", "pack", "sku")),
    ("icon", ("icone", "ícone", "icon", "badge")),
    ("chip", ("chip", "selo", "tag")),
    ("visual", ("visual", "key", "hero", "fundo", "bg")),
)


def is_campaign_preset_id(campaign_id):
    return str(campaign_id or "").strip().lower() == CENTRALCOMM_CAMPAIGN_SLUG


def centralcomm_campaign_brief():
    return {
        "id": CENTRALCOMM_CAMPAIGN_SLUG,
        "name": "Verao",
        "headline": "Verao na linha certa",
        "cta_text": "Reservar",
        "objective": "Calor no visual, teal no CTA, ouro so no destaque.",
        "campaign_text": "Verao na linha certa",
        "legal": "CentralComm Ads",
        "creative_line": "Calor no visual, teal no CTA, ouro so no destaque.",
    }


def ensure_campaign_design_system(brand, campaign=None, elements=None, existing=None):
    brand = parse_system(brand)
    campaign = campaign if isinstance(campaign, dict) else {}
    items = collect_campaign_elements(campaign, elements)
    from .fidelity import bind_evidence_tracks
    from .policy import stamp_inheritance
    from .provenance import ensure_provenance

    track_assets = [
        {
            "url": item.get("asset_url"),
            "role": item.get("role") or "",
            "label": item.get("label") or "",
        }
        for item in items
    ]
    if existing is not None:
        stored = parse_system(existing)
        data = dump_system(stored)
        data["scope"] = "campaign"
        data["source"] = "campaign"
        if items:
            data["elements"] = items
            data["tracks"] = bind_evidence_tracks(data.get("tracks") or stored.tracks, track_assets)
        data["ad_copy"] = _campaign_copy(stored, campaign) or stored.ad_copy
        from .copy import prune_format_copy

        data["ad_copy_by_format"] = prune_format_copy(
            data["ad_copy"],
            getattr(stored, "ad_copy_by_format", None) or getattr(brand, "ad_copy_by_format", None) or {},
        )
        line = _creative_line(campaign)
        if line:
            data["creative_line"] = line
        data["tokens"] = dict(stored.tokens or {})
        data["dna"] = dict(stored.dna or brand.dna or {})
        system = stamp_inheritance(DesignSystemAds.model_validate(data), brand, existing=True)
        return ensure_provenance(system), items

    name = str(campaign.get("name") or brand.name or "Campanha").strip()[:80]
    line = _creative_line(campaign)
    data = dump_system(brand)
    data.update(
        {
            "id": f"dsa-campaign-{campaign.get('id') or 'draft'}",
            "scope": "campaign",
            "name": f"{name} Ads",
            "source": "campaign",
            "status": "draft",
            "client_id": brand.client_id,
            "inherits_brand_id": brand.id,
            "creative_line": line,
            "elements": items,
        }
    )
    data["ad_copy"] = _campaign_copy(brand, campaign)
    from .copy import prune_format_copy

    data["ad_copy_by_format"] = prune_format_copy(
        data["ad_copy"],
        getattr(brand, "ad_copy_by_format", None) or {},
    )
    data["tokens"] = dict(brand.tokens or {})
    data["tracks"] = bind_evidence_tracks(
        data.get("tracks") or brand.tracks,
        track_assets,
    )
    system = stamp_inheritance(DesignSystemAds.model_validate(data), brand, existing=False)
    return ensure_provenance(system), items


def collect_campaign_elements(campaign, extras=None):
    campaign = campaign if isinstance(campaign, dict) else {}
    brief = campaign.get("creative_brief") if isinstance(campaign.get("creative_brief"), dict) else {}
    stored = {}
    if isinstance(brief.get("design_system_ads"), dict):
        stored = brief["design_system_ads"]
    pack = brief.get("campaign_pack") if isinstance(brief.get("campaign_pack"), dict) else {}
    if not pack and isinstance(campaign.get("campaign_pack"), dict):
        pack = campaign["campaign_pack"]
    rows = []
    if extras:
        rows.extend(extras if isinstance(extras, list) else [])
    elif isinstance(stored.get("elements"), list) and stored.get("elements"):
        rows.extend(stored["elements"])
    else:
        for item in pack.get("sources") or []:
            if isinstance(item, dict) and item.get("asset_url"):
                rows.append(
                    {
                        "asset_url": item.get("asset_url"),
                        "label": item.get("name") or "recorte",
                        "role": "visual",
                    }
                )
        for item in campaign.get("assets") or []:
            if isinstance(item, dict) and (item.get("asset_url") or item.get("url")):
                rows.append(item)
    return _normalize_elements(rows)


def layer_count_from_elements(elements):
    extras = len(elements or [])
    return clamp_layer_count(max(MIN_LAYERS, extras + 3))


def apply_elements_to_stack(stack, elements):
    data = dict(stack or {})
    layers = [dict(item) for item in (data.get("layers") or [])]
    remaining = [dict(item) for item in (elements or [])]
    for layer in layers:
        match = _take_element(remaining, str(layer.get("role") or ""))
        if not match:
            continue
        layer["asset_url"] = match.get("asset_url")
        layer["element_id"] = match.get("id")
        layer["cutout"] = bool(match.get("transparent", True))
        if match.get("label"):
            layer["label"] = match["label"]
    data["layers"] = layers
    data["elements"] = list(elements or [])
    return data


def _campaign_copy(brand, campaign):
    brand_copy = brand.ad_copy or {}
    brief = campaign.get("creative_brief") if isinstance(campaign.get("creative_brief"), dict) else {}
    pack = brief.get("campaign_pack") if isinstance(brief.get("campaign_pack"), dict) else {}
    if not pack and isinstance(campaign.get("campaign_pack"), dict):
        pack = campaign["campaign_pack"]
    extracted = pack.get("extracted") if isinstance(pack.get("extracted"), dict) else {}
    bancada = brief.get("bancada") if isinstance(brief.get("bancada"), dict) else {}
    headline = (
        campaign.get("headline")
        or extracted.get("headline")
        or bancada.get("title")
        or _first_line(campaign.get("campaign_text"))
        or campaign.get("name")
        or ""
    )
    support = (
        campaign.get("support")
        or extracted.get("subhead")
        or extracted.get("offer")
        or campaign.get("objective")
        or campaign.get("creative_line")
        or campaign.get("objective")
        or ""
    )
    cta = campaign.get("cta_text") or extracted.get("cta") or "Reservar"
    legal = campaign.get("legal") or brand_copy.get("legal") or str(campaign.get("name") or "")
    return {
        key: str(value).strip()
        for key, value in {
            "headline": headline,
            "support": support,
            "cta": cta,
            "legal": legal,
        }.items()
        if value
    }


def _creative_line(campaign):
    brief = campaign.get("creative_brief") if isinstance(campaign.get("creative_brief"), dict) else {}
    pack = brief.get("campaign_pack") if isinstance(brief.get("campaign_pack"), dict) else {}
    extracted = pack.get("extracted") if isinstance(pack.get("extracted"), dict) else {}
    return str(
        campaign.get("creative_line")
        or extracted.get("offer")
        or campaign.get("objective")
        or ""
    ).strip()[:240]


def _first_line(value):
    text = str(value or "").strip()
    if not text:
        return ""
    return text.splitlines()[0].strip()[:180]


def _normalize_elements(items):
    rows = []
    for index, item in enumerate(items or []):
        if len(rows) >= MAX_ELEMENTS:
            break
        if isinstance(item, str):
            item = {"asset_url": item}
        if not isinstance(item, dict):
            continue
        url = str(item.get("asset_url") or item.get("url") or "").strip()
        if not url:
            continue
        role = classify_role(item, index)
        rows.append(
            {
                "id": item.get("id") or f"element-{index + 1}",
                "role": role,
                "label": item.get("label") or item.get("title") or item.get("name") or role,
                "asset_url": url,
                "transparent": bool(item.get("transparent", True)),
                "z": int(item.get("z") or index + 2),
            }
        )
    return rows


def classify_role(item, index=0):
    raw = str((item or {}).get("role") or "").strip().lower()
    if raw in {"logo"}:
        return "icon"
    if raw and raw not in {"auto", "element", "recorte"}:
        return raw
    hint = " ".join(
        str((item or {}).get(key) or "")
        for key in ("label", "title", "name", "caption", "asset_url")
    ).lower()
    for role, words in ROLE_HINTS:
        if any(word in hint for word in words):
            return role
    return "visual" if index == 0 else f"ornament-{index}"


def _take_element(remaining, role):
    for index, item in enumerate(remaining):
        if item.get("role") == role:
            return remaining.pop(index)
    if role in {"visual", "product"} or role.startswith("ornament"):
        for index, item in enumerate(remaining):
            item_role = str(item.get("role") or "")
            if item_role in {"visual", "product"} or item_role.startswith("ornament"):
                return remaining.pop(index)
    return None
