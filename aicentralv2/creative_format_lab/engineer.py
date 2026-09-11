"""Monta o CreativeFormatSpec a partir da marca + campanha + skills."""

from __future__ import annotations

import json
import os

from ..creative_modeling_generation import _json_content
from ..creative_skills.loader import combined_system_prompt, load_bundle
from ..creative_skills.visual import load_visual_brief, normalize_selected_skills
from .catalog import (
    COMPOSITIONS,
    CTA_DEFAULTS,
    DEFAULT_COPY,
    clamp_scene_count,
    composition_purposes,
    format_entry,
    is_cta_format,
    is_qr_format,
    scene_duration,
    scene_timecode,
)
from .spec import CreativeFormatSpec, parse_format_spec

ENGINEER_MODEL = os.getenv("CREATIVE_FORMAT_ENGINEER_MODEL", "openai/gpt-5.4")


def normalize_knobs(payload=None, campaign=None):
    payload = payload if isinstance(payload, dict) else {}
    campaign = campaign if isinstance(campaign, dict) else {}
    scene_count = clamp_scene_count(
        payload.get("scene_count") or campaign.get("scene_count") or 4
    )
    density = str(payload.get("density") or "tv").strip().lower()
    if density not in {"low", "tv"}:
        density = "tv"
    try:
        tension = max(0.0, min(1.0, float(payload.get("hook_tension") or 0.55)))
    except (TypeError, ValueError):
        tension = 0.55
    scenography = str(payload.get("scenography") or "line").strip().lower()
    if scenography not in {"line", "change"}:
        scenography = "line"
    return {
        "scene_count": scene_count,
        "duration": 15,
        "objective": str(payload.get("objective") or campaign.get("objective") or "").strip(),
        "density": density,
        "hook_tension": tension,
        "cast_lock": bool(payload.get("cast_lock", True)),
        "product_lock": bool(payload.get("product_lock", True)),
        "scenography": scenography,
        "offer": str(payload.get("offer") or payload.get("message") or "").strip(),
        "cta_lock": str(payload.get("cta_text") or payload.get("cta") or "").strip(),
        "campaign_url": str(payload.get("campaign_url") or "").strip(),
        "key_visuals": _key_visual_map(payload),
        "storyboard": [
            item for item in (payload.get("storyboard") or payload.get("edits") or [])
            if isinstance(item, dict)
        ],
        "selected_skills": normalize_selected_skills(payload),
    }


def build_spec(
    *,
    route,
    intent="create",
    variant="A",
    user_message="",
    brand_name="",
    dna=None,
    brand_context=None,
    campaign=None,
    images=None,
    knobs=None,
    text_callable=None,
    bundle=None,
):
    variant = str(variant or (campaign or {}).get("variant") or "A").upper()
    if variant not in COMPOSITIONS:
        variant = "A"
    allowed = {"reconstruct", "create", "adapt", "refine", "html", "vary"}
    intent = intent if intent in allowed else "create"
    knobs = knobs or normalize_knobs({"message": user_message}, campaign)
    fallback = _fallback_spec(route, intent, variant, brand_name, campaign, brand_context, knobs)
    if text_callable is None:
        return fallback
    bundle = bundle or load_bundle(intent, route["format"], has_reference=bool(images))
    create_packs = [pack for pack in bundle["packs"] if pack in {"create", "reconstruct", "refine"}]
    system = combined_system_prompt(bundle, create_packs)
    user = _user_payload(
        route, intent, variant, user_message, brand_name, dna, brand_context, campaign, knobs
    )
    raw = _call_engineer(system, bundle["texts"]["format"], user, images, text_callable)
    try:
        spec = parse_format_spec(raw)
        if len(spec.scenes) != knobs["scene_count"]:
            return apply_copy_locks(fallback, payload_locks(campaign, knobs))
        return apply_copy_locks(spec, payload_locks(campaign, knobs))
    except Exception:
        return apply_copy_locks(fallback, payload_locks(campaign, knobs))


def refine_spec(
    spec,
    *,
    route,
    brand_context=None,
    campaign=None,
    knobs=None,
    images=None,
    text_callable=None,
    bundle=None,
):
    if text_callable is None or spec is None:
        return spec
    knobs = knobs or normalize_knobs({}, campaign)
    bundle = bundle or load_bundle("refine", route["format"], has_reference=bool(images))
    system = combined_system_prompt(bundle, ["refine"])
    user = json.dumps(
        {
            "task": "Pass 2: best 15s concept for this brand and these knobs.",
            "draft": spec.model_dump() if hasattr(spec, "model_dump") else spec,
            "brand": brand_context or {},
            "campaign": campaign or {},
            "knobs": knobs,
            "rules": [
                "Return JSON only matching CreativeFormatSpec.",
                f"Keep exactly {knobs['scene_count']} scenes.",
                "Do not return HTML.",
                "Do not draw player chrome.",
                "Keep the brand alive in every frame.",
                "Reject generic hooks and website CTAs.",
            ],
        },
        ensure_ascii=False,
    )
    raw = _call_engineer(system, bundle["texts"]["format"], user, images, text_callable)
    try:
        refined = parse_format_spec(raw)
        if len(refined.scenes) != knobs["scene_count"]:
            return apply_copy_locks(spec, payload_locks(campaign, knobs))
        return apply_copy_locks(refined, payload_locks(campaign, knobs))
    except Exception:
        return apply_copy_locks(spec, payload_locks(campaign, knobs))


def _fallback_spec(route, intent, variant, brand_name, campaign=None, brand_context=None, knobs=None):
    campaign = campaign if isinstance(campaign, dict) else {}
    brand_context = brand_context if isinstance(brand_context, dict) else {}
    knobs = knobs or normalize_knobs({}, campaign)
    name = brand_name or campaign.get("brand_name") or brand_context.get("name") or ""
    count = knobs["scene_count"]
    purposes = composition_purposes(variant, count)
    if is_qr_format(route["format"]) and len(purposes) >= 2:
        purposes[-2] = "response"
    cta = knobs.get("cta_lock") or campaign.get("cta") or CTA_DEFAULTS.get(route["format"]) or "Saiba mais"
    campaign_scenes = {item.get("id"): item for item in (campaign.get("scenes") or []) if isinstance(item, dict)}
    scenes = []
    for index, purpose in enumerate(purposes, start=1):
        scene_id = f"scene_0{index}"
        model = campaign_scenes.get(scene_id) or {}
        headline, support = DEFAULT_COPY.get(purpose, DEFAULT_COPY["hook"])
        headline = model.get("headline") or headline
        support = model.get("support") or support
        last = index == count
        scene_cta = model.get("cta") or (cta if (last or is_cta_format(route["format"])) else "")
        timecode, _progress = scene_timecode(scene_id, count, qr=is_qr_format(route["format"]))
        scenes.append({
            "id": scene_id,
            "duration": scene_duration(index, count),
            "purpose": model.get("purpose") or purpose,
            "headline": headline,
            "support": support,
            "cta": scene_cta,
            "tip": model.get("tip") or ("Aponte a câmera" if is_qr_format(route["format"]) and index >= count - 1 else ""),
            "timecode": model.get("timecode") or timecode,
            "set_note": model.get("set_note") or "",
            "action_note": model.get("action_note") or "",
        })
    spec = CreativeFormatSpec.model_validate({
        "intent": intent if intent in {"reconstruct", "create", "adapt", "refine", "vary", "html"} else "create",
        "format": route["format"],
        "variant": variant,
        "adapter": route["adapter"],
        "platform_label": route["platform_label"],
        "brand_name": name,
        "canvas": {"width": 1920, "height": 1080},
        "scenes": scenes,
        "output": {"type": "html", "layers": True, "animation_ready": True},
    })
    return apply_copy_locks(spec, payload_locks(campaign, knobs))


def _user_payload(route, intent, variant, user_message, brand_name, dna, brand_context, campaign, knobs):
    entry = format_entry(route["format"]) or {}
    dna = dna if isinstance(dna, dict) else {}
    return json.dumps(
        {
            "intent": intent,
            "format": route["format"],
            "variant": variant,
            "adapter": route["adapter"],
            "platform_label": route["platform_label"],
            "brand_name": brand_name,
            "user_message": user_message,
            "format_label": entry.get("label"),
            "knobs": knobs,
            "brand": brand_context or {},
            "campaign": campaign or {},
            "brand_dna": {
                "id": dna.get("id"),
                "colors": dna.get("colors"),
                "fonts": dna.get("fonts"),
                "voice_tone": dna.get("voice_tone"),
                "text_limits": dna.get("text_limits"),
            },
            "rules": [
                "Return JSON only matching CreativeFormatSpec.",
                f"Exactly {knobs['scene_count']} scenes: scene_01 to scene_0{knobs['scene_count']}.",
                "Duration is 15 seconds. Do not write a 30s film.",
                "Do not return HTML.",
                "Do not draw player chrome.",
                "Use Marcas payload for tone, forbidden, palette and logo.",
                "Keep the brand alive in every frame (color, type, tone) even when the logo is off.",
                "Set logo_visible per scene. The last scene (CTA) always has the logo on, centered.",
                "Opening and middle scenes may set logo_visible true or false. Default off unless the beat is brand.",
                "Use campaign model headlines, set_note and action_note when present.",
                "Keep user-locked offer, headline, support, CTA and key visuals.",
                "Refuse generic hooks such as sua história, viva o momento, conheça agora.",
            ],
            "selected_skills": knobs.get("selected_skills") or [],
            "visual_skill": load_visual_brief(knobs.get("selected_skills"), stage="html"),
        },
        ensure_ascii=False,
    )


def apply_copy_locks(spec, locks):
    if spec is None or not locks:
        return spec
    mapping = {
        str(item.get("id") or item.get("scene_key") or ""): item
        for item in locks
        if isinstance(item, dict)
    }
    for scene in spec.scenes:
        lock = mapping.get(scene.id)
        if not lock:
            continue
        for field in ("headline", "support", "cta", "tip", "set_note", "action_note"):
            value = lock.get(field)
            if value not in (None, ""):
                setattr(scene, field, str(value))
        if "logo_visible" in lock:
            scene.logo_visible = bool(lock.get("logo_visible"))
    return spec


def payload_locks(campaign=None, knobs=None):
    campaign = campaign if isinstance(campaign, dict) else {}
    knobs = knobs if isinstance(knobs, dict) else {}
    locks = []
    for item in campaign.get("scenes") or []:
        if isinstance(item, dict) and item.get("id"):
            locks.append(item)
    for item in knobs.get("storyboard") or []:
        if isinstance(item, dict) and item.get("id"):
            locks.append(item)
    return locks


def _key_visual_map(payload):
    payload = payload if isinstance(payload, dict) else {}
    raw = payload.get("key_visuals") or {}
    if isinstance(raw, dict):
        return {
            str(key): str(url)
            for key, url in raw.items()
            if url
        }
    mapping = {}
    if isinstance(raw, list):
        for index, url in enumerate(raw, start=1):
            if url:
                mapping[f"scene_0{index}"] = str(url)
    return mapping


def _call_engineer(system, format_skill, user, images, text_callable):
    content = user
    if images:
        blocks = [{"type": "text", "text": user}]
        for url in images or []:
            if url:
                blocks.append({"type": "image_url", "image_url": {"url": url}})
        content = blocks
    response = text_callable(
        [
            {"role": "system", "content": system},
            {"role": "developer", "content": format_skill},
            {"role": "user", "content": content},
        ],
        model=ENGINEER_MODEL,
        max_tokens=1800,
        temperature=0.15,
    )
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raw = json.dumps(raw, ensure_ascii=False)
    try:
        return _json_content(raw)
    except Exception:
        return json.loads(raw)
