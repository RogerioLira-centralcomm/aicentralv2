"""Monta o CreativeFormatSpec a partir da marca + campanha + skills."""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from ..creative_modeling_generation import OpenRouterError, _json_content
from ..creative_skills.loader import combined_system_prompt, load_bundle
from ..creative_skills.visual import load_visual_brief, normalize_selected_skills
from .lab_models import ENGINEER_TEMPERATURE, JSON_OBJECT, lab_chat_model
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

logger = logging.getLogger(__name__)
_MAX_DATA_IMAGE = 2_500_000


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
        "offer": _resolve_offer(payload, campaign),
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
        spec = parse_format_spec(raw, expected_format=route["format"])
    except (ValidationError, ValueError) as exc:
        raise ValueError("O provedor devolveu um conceito inválido.") from exc
    if len(spec.scenes) != knobs["scene_count"]:
        raise ValueError("O conceito não veio com o número certo de cenas.")
    return apply_copy_locks(spec, payload_locks(campaign, knobs))


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
            "task": "Pass 2: improve only weak beats. Do not rewrite locked copy.",
            "draft": _draft_scenes(spec),
            "locked": _locked_copy(campaign, knobs),
            "improve": _improve_beats(spec),
            "brand": _refine_brand(brand_context),
            "campaign": _refine_campaign(campaign),
            "knobs": _refine_knobs(knobs),
            "rules": [
                "Return JSON only matching CreativeFormatSpec.",
                f"Keep exactly {knobs['scene_count']} scenes as a JSON array: scene_01 to scene_0{knobs['scene_count']}.",
                "Do not return HTML.",
                "Do not draw player chrome.",
                "Do not replace locked headline, support, CTA or key visual.",
                "Improve set_note and action_note only. Headlines stay verbatim.",
                "Keep the brand alive in every frame (color, type, tone) even when the logo is off.",
                "Set logo_visible per scene. The last scene (CTA) always has the logo on, centered.",
                "Reject generic hooks and website CTAs.",
            ],
        },
        ensure_ascii=False,
    )
    raw = _call_engineer(system, bundle["texts"]["format"], user, images, text_callable)
    try:
        refined = parse_format_spec(raw, expected_format=route["format"])
    except (ValidationError, ValueError) as exc:
        raise ValueError("O provedor devolveu um conceito inválido.") from exc
    if len(refined.scenes) != knobs["scene_count"]:
        raise ValueError("O conceito refinado não veio com o número certo de cenas.")
    return apply_copy_locks(refined, payload_locks(campaign, knobs))


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
        "canvas": (format_entry(route["format"]) or {}).get("canvas")
        or {"width": 1920, "height": 1080},
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
            "canvas": entry.get("canvas") or {"width": 1920, "height": 1080},
            "size_label": entry.get("size_label") or route.get("platform_label"),
            "orientation": entry.get("orientation") or "horizontal",
            "kind": entry.get("kind") or "video",
            "knobs": knobs,
            "brand": _slim_brand(brand_context),
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
                f"Exactly {knobs['scene_count']} scenes as a JSON array: scene_01 to scene_0{knobs['scene_count']}.",
                "Duration is 15 seconds. Do not write a 30s film.",
                "Do not return HTML.",
                "Do not draw player chrome.",
                f"Write for canvas {entry.get('size_label') or route.get('platform_label') or '1920×1080'}.",
                "Banner units keep the same 4 or 5 beats. Horizontal reads left to right. Vertical reads top to bottom.",
                "Use Marcas payload for tone, forbidden, palette and logo.",
                "Keep the brand alive in every frame (color, type, tone) even when the logo is off.",
                "Set logo_visible per scene. The last scene (CTA) always has the logo on, centered.",
                "Opening and middle scenes may set logo_visible true or false. Default off unless the beat is brand.",
                "Copy campaign headlines, support and CTA verbatim when present. Do not paraphrase locked lines.",
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


_GENERIC_HOOKS = ("sua história", "viva o momento", "conheça agora")


def _resolve_offer(payload, campaign=None):
    payload = payload if isinstance(payload, dict) else {}
    campaign = campaign if isinstance(campaign, dict) else {}
    offer = str(payload.get("offer") or payload.get("message") or "").strip()
    locked = str(campaign.get("offer") or "").strip()
    title = str(campaign.get("title") or "").strip()
    if locked and (not offer or offer == title):
        return locked
    return offer or locked or title


def _improve_beats(spec):
    hints = []
    for scene in getattr(spec, "scenes", None) or []:
        scene_id = getattr(scene, "id", "") or "scene"
        headline = str(getattr(scene, "headline", "") or "").lower()
        if any(hook in headline for hook in _GENERIC_HOOKS):
            hints.append(f"{scene_id}: generic hook")
        if not str(getattr(scene, "set_note", "") or "").strip():
            hints.append(f"{scene_id}: set_note empty")
        if not str(getattr(scene, "action_note", "") or "").strip():
            hints.append(f"{scene_id}: action_note empty")
    if not hints:
        hints.append("Tighten set_note and action_note for TV distance. Keep locked headlines.")
    return hints[:8]


def _draft_scenes(spec):
    scenes = getattr(spec, "scenes", None) or []
    cards = []
    for scene in scenes:
        cards.append({
            "id": getattr(scene, "id", ""),
            "purpose": getattr(scene, "purpose", ""),
            "headline": getattr(scene, "headline", ""),
            "support": getattr(scene, "support", ""),
            "cta": getattr(scene, "cta", ""),
            "set_note": getattr(scene, "set_note", ""),
            "action_note": getattr(scene, "action_note", ""),
            "logo_visible": getattr(scene, "logo_visible", None),
        })
    return {
        "format": getattr(spec, "format", ""),
        "variant": getattr(spec, "variant", ""),
        "brand_name": getattr(spec, "brand_name", ""),
        "scenes": cards,
    }


def _locked_copy(campaign=None, knobs=None):
    locked = []
    for item in payload_locks(campaign, knobs):
        fields = {
            field: item.get(field)
            for field in ("headline", "support", "cta", "set_note", "action_note")
            if item.get(field) not in (None, "")
        }
        if item.get("id") and fields:
            locked.append({"id": item["id"], **fields})
    return locked


def _refine_campaign(campaign):
    campaign = campaign if isinstance(campaign, dict) else {}
    return {
        "slug": campaign.get("slug") or "",
        "title": campaign.get("title") or "",
        "offer": campaign.get("offer") or "",
        "objective": campaign.get("objective") or "",
        "cta": campaign.get("cta") or "",
        "forbidden": list(campaign.get("forbidden") or [])[:8],
    }


def _refine_knobs(knobs):
    knobs = knobs if isinstance(knobs, dict) else {}
    return {
        "scene_count": knobs.get("scene_count"),
        "offer": knobs.get("offer") or "",
        "objective": knobs.get("objective") or "",
        "density": knobs.get("density") or "tv",
        "hook_tension": knobs.get("hook_tension"),
    }


def _refine_brand(brand):
    slim = _slim_brand(brand)
    dna = brand.get("brand_dna") if isinstance((brand or {}).get("brand_dna"), dict) else {}
    return {
        "name": slim.get("name") or "",
        "tone_of_voice": str(dna.get("voice_tone") or slim.get("tone_of_voice") or "")[:240],
        "palette": slim.get("palette") or [],
        "forbidden_elements": slim.get("forbidden_elements") or [],
        "mandatory_elements": slim.get("mandatory_elements") or [],
        "logo_url": slim.get("logo_url") or "",
    }


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


def _usable_image_url(url):
    if not isinstance(url, str):
        return False
    if url.startswith("data:image/") and 32 < len(url) < _MAX_DATA_IMAGE:
        return True
    if url.startswith("https://"):
        return True
    if url.startswith("http://") and "localhost" not in url and "127.0.0.1" not in url:
        return True
    return False


def _slim_brand(brand):
    brand = brand if isinstance(brand, dict) else {}
    assets = brand.get("assets") if isinstance(brand.get("assets"), dict) else {}
    line = brand.get("creative_line") if isinstance(brand.get("creative_line"), dict) else {}
    return {
        "name": brand.get("name") or "",
        "sector": brand.get("sector") or "",
        "tone_of_voice": brand.get("tone_of_voice") or "",
        "primary_color": brand.get("primary_color") or "",
        "secondary_color": brand.get("secondary_color") or "",
        "palette": list(brand.get("palette") or [])[:8],
        "forbidden_elements": list(brand.get("forbidden_elements") or [])[:8],
        "mandatory_elements": list(brand.get("mandatory_elements") or [])[:8],
        "visual_motifs": list(brand.get("visual_motifs") or [])[:8],
        "products_services": list(brand.get("products_services") or [])[:8],
        "creative_guidelines": str(brand.get("creative_guidelines") or "")[:400],
        "brand_summary": str(brand.get("brand_summary") or "")[:400],
        "logo_url": brand.get("logo_url") if _usable_image_url(brand.get("logo_url")) else "",
        "creative_line": {
            "signature_summary": str(line.get("signature_summary") or "")[:240],
            "copy_patterns": list(line.get("copy_patterns") or [])[:6],
            "composition_rules": list(line.get("composition_rules") or [])[:6],
        },
        "assets": {
            "logo": [url for url in (assets.get("logo") or []) if _usable_image_url(url)][:2],
            "references": [url for url in (assets.get("references") or []) if _usable_image_url(url)][:4],
        },
    }


def _call_engineer(system, format_skill, user, images, text_callable):
    if text_callable is None:
        return None
    content = user
    usable = [url for url in (images or []) if _usable_image_url(url)][:4]
    if usable:
        content = [{"type": "text", "text": user}]
        content.extend({"type": "image_url", "image_url": {"url": url}} for url in usable)
    try:
        response = text_callable(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            model=lab_chat_model("storyboard"),
            max_tokens=2400,
            temperature=ENGINEER_TEMPERATURE,
            response_format=JSON_OBJECT,
        )
    except OpenRouterError:
        raise
    except Exception as exc:
        logger.exception("Engenheiro do lab não consultou o provedor")
        raise OpenRouterError("Não foi possível consultar o provedor de IA.") from exc
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raw = json.dumps(raw, ensure_ascii=False)
    try:
        return _json_content(raw)
    except Exception:
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise OpenRouterError("O provedor não devolveu o conceito em JSON.") from exc
        if not isinstance(parsed, dict):
            raise OpenRouterError("O provedor não devolveu o conceito em JSON.")
        return parsed
