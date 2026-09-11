"""Conceito 15s em duas passagens — sem gerar o filme."""

from __future__ import annotations

from ..creative_modeling_fx import annotate_cost
from ..creative_modeling_generation import OpenRouterError
from ..creative_skills.loader import load_bundle
from .brand_context import build_brand_context, reference_images
from .campaign_models import apply_brand_to_campaign, apply_key_visuals, campaign_from_brand, expand_campaign_scenes, load_campaign_model
from .catalog import ROLE_MAP
from .mockup import MOCKUP_ESTIMATE_USD, MOCKUP_PASSES, scene_logo_visible
from .engineer import apply_copy_locks, build_spec, normalize_knobs, refine_spec
from .router import route_format

PROMPT_ESTIMATE_USD = 0.02
SCENE_VERSIONS = 3
STORYBOARD_PASSES = 2


def quote_concept(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    knobs = normalize_knobs(payload)
    kind = str(payload.get("kind") or "full").strip().lower()
    if kind == "storyboard":
        estimated = PROMPT_ESTIMATE_USD * STORYBOARD_PASSES
        versions = 0
        passes = STORYBOARD_PASSES
    elif kind == "mockup":
        estimated = MOCKUP_ESTIMATE_USD * MOCKUP_PASSES
        versions = MOCKUP_PASSES
        passes = MOCKUP_PASSES
    elif kind == "scene":
        estimated = PROMPT_ESTIMATE_USD * SCENE_VERSIONS
        versions = SCENE_VERSIONS
        passes = SCENE_VERSIONS
    elif kind in {"html", "implement"}:
        versions = knobs["scene_count"] * SCENE_VERSIONS
        passes = versions
        estimated = PROMPT_ESTIMATE_USD * passes
    elif kind == "patch":
        estimated = PROMPT_ESTIMATE_USD
        versions = 1
        passes = 1
    else:
        versions = knobs["scene_count"] * SCENE_VERSIONS
        passes = STORYBOARD_PASSES + MOCKUP_PASSES + versions
        estimated = (
            PROMPT_ESTIMATE_USD * (STORYBOARD_PASSES + versions)
            + MOCKUP_ESTIMATE_USD * MOCKUP_PASSES
        )
    return annotate_cost(
        {
            "estimated_cost_usd": estimated,
            "passes": passes,
            "storyboard_passes": STORYBOARD_PASSES,
            "mockup_passes": MOCKUP_PASSES,
            "scene_versions": SCENE_VERSIONS,
            "versions": versions,
            "scene_count": knobs["scene_count"],
            "duration": 15,
            "later": {"image": False, "video": False},
        },
        estimated,
    )


def build_storyboard(payload, *, client=None, text_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    client = client if isinstance(client, dict) else {}
    extra_assets = [
        {"role": "reference", "asset_url": url}
        for url in (payload.get("images") or payload.get("references") or [])
        if url
    ]
    brand = build_brand_context(client, extra_assets=extra_assets)
    knobs = normalize_knobs(payload)
    user_images = [item["asset_url"] for item in extra_assets]
    images = reference_images(brand, user_images)
    campaign = load_campaign_model(payload.get("campaign_slug"))
    if campaign:
        campaign = apply_brand_to_campaign(campaign, brand)
    elif brand.get("name"):
        campaign = campaign_from_brand(
            brand,
            payload.get("format") or "video-linear-15",
            scene_count=knobs["scene_count"],
        )
    if campaign:
        campaign = expand_campaign_scenes(campaign, knobs["scene_count"])
        campaign = apply_key_visuals(
            campaign,
            user_images,
            knobs.get("key_visuals"),
        )
    format_key = payload.get("format") or payload.get("format_key") or (campaign or {}).get("format")
    variant = str(payload.get("variant") or (campaign or {}).get("variant") or "A").upper()
    route = route_format(
        knobs.get("offer") or (campaign or {}).get("title") or "",
        format_key,
        payload.get("files"),
        text_callable=None,
    )
    images = [url for url in images if isinstance(url, str) and url.startswith("https://")]
    create_bundle = load_bundle("create", route["format"], has_reference=bool(images))
    spec, provider = _storyboard_spec(
        route=route,
        variant=variant,
        brand=brand,
        campaign=campaign,
        images=images,
        knobs=knobs,
        payload=payload,
        text_callable=text_callable,
        create_bundle=create_bundle,
    )
    refine_bundle = load_bundle("refine", route["format"], has_reference=bool(images))
    spec = apply_copy_locks(spec, knobs.get("storyboard"))
    cards = [
        {
            "id": scene.id,
            "position": index,
            "purpose": scene.purpose,
            "role": ROLE_MAP.get(scene.purpose, "unico"),
            "headline": scene.headline,
            "support": scene.support,
            "cta": scene.cta,
            "set_note": scene.set_note,
            "action_note": scene.action_note,
            "duration": scene.duration,
            "timecode": scene.timecode,
            "image_prompt": _scene_prompt(campaign, scene.id),
            "key_visual": _scene_visual(campaign, scene.id, knobs.get("key_visuals")),
            "logo_visible": scene_logo_visible(
                scene.purpose,
                scene.id,
                knobs,
                scene_count=knobs.get("scene_count") or len(spec.scenes),
                scene_flag=getattr(scene, "logo_visible", None),
            ),
        }
        for index, scene in enumerate(spec.scenes, start=1)
    ]
    quote = quote_concept({**payload, "kind": "storyboard", "scene_count": knobs["scene_count"]})
    return {
        "intent": "create",
        "format": spec.format,
        "variant": spec.variant,
        "adapter": spec.adapter,
        "platform_label": spec.platform_label,
        "brand_name": spec.brand_name,
        "brand": brand,
        "brand_dna": brand.get("brand_dna"),
        "campaign": {
            "slug": (campaign or {}).get("slug"),
            "title": (campaign or {}).get("title") or knobs.get("offer") or spec.brand_name,
            "offer": knobs.get("offer") or (campaign or {}).get("offer") or (campaign or {}).get("title"),
            "product": (campaign or {}).get("product"),
            "objective": knobs.get("objective") or (campaign or {}).get("objective"),
            "name": payload.get("name") or (campaign or {}).get("title") or spec.brand_name,
        },
        "knobs": knobs,
        "spec": spec.model_dump(),
        "storyboard": cards,
        "scene_count": len(cards),
        "duration": 15,
        "passes": [
            {"id": "create", "label": "Conceito", "status": "done"},
            {"id": "refine", "label": "Melhor roteiro", "status": "done"},
        ],
        "skills": create_bundle["skills"] + [item for item in refine_bundle["skills"] if item["id"] == "refine"],
        "quote": quote,
        "status": "concept",
        "provider": provider,
    }


def _storyboard_spec(
    *,
    route,
    variant,
    brand,
    campaign,
    images,
    knobs,
    payload,
    text_callable,
    create_bundle,
):
    common = {
        "route": route,
        "intent": "create",
        "variant": variant,
        "user_message": knobs.get("offer") or (campaign or {}).get("title") or "",
        "brand_name": brand.get("name") or payload.get("brand_name") or "",
        "dna": brand.get("brand_dna"),
        "brand_context": brand,
        "campaign": campaign,
        "images": images,
        "knobs": knobs,
        "bundle": create_bundle,
    }
    fallback = build_spec(text_callable=None, **common)
    if text_callable is None:
        return fallback, "campaign"
    try:
        spec = build_spec(text_callable=text_callable, **common)
    except (OpenRouterError, ValueError):
        return fallback, "campaign"
    try:
        spec = refine_spec(
            spec,
            route=route,
            brand_context=brand,
            campaign=campaign,
            knobs=knobs,
            images=images,
            text_callable=text_callable,
            bundle=load_bundle("refine", route["format"], has_reference=bool(images)),
        )
    except (OpenRouterError, ValueError):
        return spec, "llm"
    return spec, "llm"


def _scene_prompt(campaign, scene_id):
    if not isinstance(campaign, dict):
        return ""
    for item in campaign.get("scenes") or []:
        if item.get("id") == scene_id:
            return item.get("image_prompt") or ""
    return ""


def _scene_visual(campaign, scene_id, mapping=None):
    pinned = mapping if isinstance(mapping, dict) else {}
    if pinned.get(scene_id):
        return pinned[scene_id]
    if not isinstance(campaign, dict):
        return ""
    for item in campaign.get("scenes") or []:
        if item.get("id") == scene_id:
            return item.get("key_visual") or ""
    return ""
