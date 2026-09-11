"""Campanhas-modelo CTV em texto + ligação com a marca de Marcas."""

from __future__ import annotations

import json
from pathlib import Path

CAMPAIGN_DIR = Path(__file__).resolve().parent / "campaigns"


def list_campaign_models():
    models = []
    for path in sorted(CAMPAIGN_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        models.append(_public(data))
    return models


def load_campaign_model(slug):
    key = str(slug or "").strip()
    if not key:
        return None
    path = CAMPAIGN_DIR / f"{key}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def match_campaign_for_brand(brand_name):
    name = str(brand_name or "").strip().lower()
    if not name:
        return None
    for item in list_campaign_models():
        full = load_campaign_model(item["slug"])
        needles = [str(full.get("brand_name") or "").lower(), *(full.get("brand_match") or [])]
        if any(needle and needle in name for needle in needles):
            return full
    return None


def apply_brand_to_campaign(model, brand_context):
    model = dict(model or {})
    brand = brand_context if isinstance(brand_context, dict) else {}
    name = brand.get("name") or model.get("brand_name") or ""
    opportunity = (brand.get("campaign_opportunities") or [None])[0]
    product = (brand.get("products_services") or [None])[0]
    proof = (brand.get("proof_points") or brand.get("differentiators") or [None])[0]
    model["brand_name"] = name
    model["objective"] = (
        model.get("objective")
        or opportunity
        or brand.get("brand_summary")
        or ""
    )
    scenes = []
    for scene in model.get("scenes") or []:
        item = dict(scene)
        purpose = item.get("purpose")
        if not item.get("support"):
            if purpose in {"product", "benefit"} and product:
                item["support"] = product
            elif purpose in {"proof", "lifestyle"} and proof:
                item["support"] = proof
            elif purpose == "cta" and (brand.get("mandatory_elements") or [None])[0]:
                item["support"] = brand["mandatory_elements"][0]
        if purpose == "cta" and not item.get("cta"):
            item["cta"] = model.get("cta") or "Saiba mais"
        scenes.append(item)
    model["scenes"] = scenes
    model["offer"] = model.get("offer") or model.get("title") or opportunity or ""
    model["product"] = model.get("product") or product or ""
    model["audience"] = model.get("audience") or brand.get("target_audience") or ""
    model["tone"] = model.get("tone") or brand.get("tone_of_voice") or ""
    model["brand"] = {
        "id": brand.get("id"),
        "name": name,
        "tone": brand.get("tone_of_voice"),
        "summary": brand.get("brand_summary"),
        "audience": brand.get("target_audience"),
        "palette": brand.get("palette"),
        "logo_url": brand.get("logo_url"),
        "forbidden": brand.get("forbidden_elements"),
        "mandatory": brand.get("mandatory_elements"),
        "guidelines": brand.get("creative_guidelines"),
        "line": (brand.get("creative_line") or {}).get("signature_summary"),
    }
    return model


def expand_campaign_scenes(model, scene_count=4):
    model = dict(model or {})
    count = 5 if int(scene_count or 4) == 5 else 4
    scenes = [dict(item) for item in (model.get("scenes") or []) if isinstance(item, dict)]
    if count == 5 and len(scenes) == 4:
        hook = dict(scenes[0])
        context = {
            "id": "scene_02",
            "purpose": "context",
            "headline": hook.get("support") or "O contexto entra.",
            "support": model.get("objective") or "",
            "image_prompt": hook.get("image_prompt") or "",
        }
        rebuilt = [hook, context]
        for index, item in enumerate(scenes[1:], start=3):
            row = dict(item)
            row["id"] = f"scene_0{index}"
            rebuilt.append(row)
        scenes = rebuilt
    elif count == 4 and len(scenes) > 4:
        scenes = scenes[:3] + [scenes[-1]]
        for index, item in enumerate(scenes, start=1):
            item["id"] = f"scene_0{index}"
    model["scenes"] = scenes
    model["scene_count"] = len(scenes)
    return model


def campaign_from_brand(brand_context, format_key="video-linear-15", scene_count=4):
    brand = brand_context if isinstance(brand_context, dict) else {}
    matched = match_campaign_for_brand(brand.get("name"))
    if matched:
        return expand_campaign_scenes(apply_brand_to_campaign(matched, brand), scene_count)
    opportunity = (brand.get("campaign_opportunities") or ["Campanha CTV"])[0]
    product = (brand.get("products_services") or [brand.get("brand_summary") or ""])[0]
    proof = (brand.get("proof_points") or brand.get("differentiators") or [""])[0]
    motif = (brand.get("visual_motifs") or [""])[0]
    name = brand.get("name") or "Marca"
    tone = brand.get("tone_of_voice") or ""
    cta = "Saiba mais"
    canvas = "cinematic 16:9, TV viewing distance, no invented logos"
    base = {
        "slug": f"brand-{brand.get('id') or 'lab'}-ctv",
        "brand_name": name,
        "format": format_key,
        "variant": "A",
        "intent": "create",
        "title": opportunity,
        "objective": brand.get("brand_summary") or opportunity,
        "cta": cta,
        "scenes": [
            {
                "id": "scene_01",
                "purpose": "hook",
                "headline": opportunity,
                "support": brand.get("target_audience") or tone,
                "image_prompt": f"{motif or opportunity}, {canvas}, {name} palette.",
            },
            {
                "id": "scene_02",
                "purpose": "benefit",
                "headline": product or "O que muda.",
                "support": (brand.get("differentiators") or [""])[0],
                "image_prompt": f"{product or motif}, product in use, {canvas}.",
            },
            {
                "id": "scene_03",
                "purpose": "proof",
                "headline": proof or "Prova na tela.",
                "support": brand.get("creative_guidelines") or "",
                "image_prompt": f"{proof or motif}, documentary still, {canvas}.",
            },
            {
                "id": "scene_04",
                "purpose": "cta",
                "headline": name,
                "support": (brand.get("mandatory_elements") or ["Uma ação. Distância de TV."])[0],
                "cta": cta,
                "image_prompt": f"End card, {name} colors, large type, CTA pill, {canvas}.",
            },
        ],
        "generated_from_marcas": True,
        "scene_count": 4,
    }
    return expand_campaign_scenes(base, scene_count)


def apply_key_visuals(model, urls=None, mapping=None):
    model = dict(model or {})
    urls = [str(url) for url in (urls or []) if url]
    pinned = mapping if isinstance(mapping, dict) else {}
    scenes = []
    for index, scene in enumerate(model.get("scenes") or []):
        item = dict(scene) if isinstance(scene, dict) else {}
        scene_id = item.get("id") or f"scene_0{index + 1}"
        visual = pinned.get(scene_id) or (urls[index] if index < len(urls) else "")
        if visual:
            item["key_visual"] = visual
        scenes.append(item)
    model["scenes"] = scenes
    return model


def _public(data):
    return {
        "slug": data.get("slug"),
        "brand_name": data.get("brand_name"),
        "title": data.get("title"),
        "format": data.get("format"),
        "variant": data.get("variant"),
        "intent": data.get("intent") or "create",
        "objective": data.get("objective"),
        "offer": data.get("offer") or data.get("title"),
        "product": data.get("product"),
        "scenes": [
            {
                "id": scene.get("id"),
                "purpose": scene.get("purpose"),
                "headline": scene.get("headline"),
            }
            for scene in (data.get("scenes") or [])
        ],
    }
