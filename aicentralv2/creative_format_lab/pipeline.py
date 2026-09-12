"""Orquestra marca + campanha + skills → HTML → QA → camadas."""

from __future__ import annotations

import secrets

from ..creative_modeling_generation import OpenRouterError
from ..creative_skills.loader import load_bundle
from .brand_context import build_brand_context, reference_images, scene_photos
from .campaign_models import apply_brand_to_campaign, apply_key_visuals, campaign_from_brand, expand_campaign_scenes, load_campaign_model, offer_hint
from .catalog import ROLE_MAP, composition_purposes
from .engineer import (
    _first_still,
    _usable_image_url,
    apply_still_read,
    build_copy_origin,
    build_spec,
    finalize_spec,
    normalize_knobs,
    pack_still_record,
)
from .html_builder import build_scene_html
from .layer_export import export_layers, export_scene_cards
from .guidelines import check_stack
from .stack import build_stack
from .mockup import build_base_mockup, scene_logo_visible
from .router import route_format
from .spec import parse_format_spec
from .storyboard import SCENE_VERSIONS
from ..creative_skills.visual import load_visual_brief
from .visual_qa import clamp_renders, run_qa_loop


def new_session_id():
    return f"flab-{secrets.token_hex(6)}"


def _should_read_still(payload):
    """OCR só no conceito. Mockup, QA e cena já têm spec."""
    stage = str(payload.get("stage") or "").strip().lower()
    if payload.get("spec") or stage in {"mockup", "qa", "close", "scene"}:
        return False
    return True


def _step(skill_id, label, status, note=""):
    return {"id": skill_id, "label": label, "status": status, "note": note}


def run_session(
    payload,
    *,
    client=None,
    text_callable=None,
    screenshot=None,
    persisted_read=None,
    reread=False,
    accept_inline=True,
    session_id="",
):
    payload = payload if isinstance(payload, dict) else {}
    client = client if isinstance(client, dict) else {}
    user_images = _payload_images(payload)
    extra_assets = [{"role": "reference", "asset_url": url} for url in user_images]
    brand = build_brand_context(client, extra_assets=extra_assets)
    brand_name = str(payload.get("brand_name") or brand.get("name") or "").strip()
    intent = str(payload.get("intent") or "create")
    user_message = str(payload.get("message") or payload.get("user_message") or "").strip()
    images = reference_images(brand, user_images)
    photos = scene_photos(brand, user_images)
    knobs = normalize_knobs(payload)
    if _should_read_still(payload):
        knobs = apply_still_read(
            knobs,
            user_images,
            text_callable,
            persisted=persisted_read,
            reread=reread,
            accept_inline=accept_inline,
        )
    elif persisted_read:
        knobs = apply_still_read(
            knobs,
            user_images,
            None,
            persisted=persisted_read,
            reread=False,
            accept_inline=False,
        )
    campaign = payload.get("campaign") if isinstance(payload.get("campaign"), dict) else None
    if not campaign:
        campaign = load_campaign_model(payload.get("campaign_slug"))
        if campaign:
            campaign = apply_brand_to_campaign(campaign, brand)
            campaign["lock_copy"] = True
        elif brand.get("name"):
            campaign = campaign_from_brand(
                brand,
                payload.get("format") or "video-linear-15",
                scene_count=knobs["scene_count"],
                hint=offer_hint(payload, knobs),
                has_reference=any(_usable_image_url(url) for url in user_images)
                or any(_usable_image_url(url) for url in (knobs.get("key_visuals") or {}).values()),
            )
    if campaign:
        campaign = expand_campaign_scenes(campaign, knobs["scene_count"])
        campaign = apply_key_visuals(campaign, user_images, knobs.get("key_visuals"))
    scene_id = str(payload.get("scene_id") or "").strip()
    existing = {
        item.get("id"): dict(item)
        for item in (payload.get("scenes") or [])
        if isinstance(item, dict) and item.get("id")
    }
    format_key = payload.get("format") or payload.get("format_key") or (campaign or {}).get("format")
    variant = str(payload.get("variant") or (campaign or {}).get("variant") or "A").upper()
    route = route_format(
        user_message or (campaign or {}).get("title") or "",
        format_key,
        payload.get("files"),
        text_callable=None,
    )
    bundle = load_bundle(intent, route["format"], has_reference=bool(images))
    steps = [_step(item["id"], item["label"], "queued") for item in bundle["skills"]]
    steps.append(_step("render", "Chromium", "queued"))
    _mark(steps, "orchestrator", "done", bundle["intent_label"])
    _mark(steps, bundle["format_skill"], "running", route["format"])

    spec = None
    if payload.get("spec"):
        try:
            spec = parse_format_spec(payload.get("spec"))
        except Exception:
            spec = None
    if spec is None:
        llm = None if str(payload.get("stage") or "") == "mockup" else text_callable
        try:
            spec = build_spec(
                route=route,
                intent=bundle["intent"],
                variant=variant,
                user_message=user_message or (campaign or {}).get("title") or "",
                brand_name=brand_name,
                dna=brand.get("brand_dna"),
                brand_context=brand,
                campaign=campaign,
                images=images,
                knobs=knobs,
                text_callable=llm,
                bundle=bundle,
            )
        except (OpenRouterError, ValueError):
            spec = build_spec(
                route=route,
                intent=bundle["intent"],
                variant=variant,
                user_message=user_message or (campaign or {}).get("title") or "",
                brand_name=brand_name,
                dna=brand.get("brand_dna"),
                brand_context=brand,
                campaign=campaign,
                images=images,
                knobs=knobs,
                text_callable=None,
                bundle=bundle,
            )
    spec = finalize_spec(spec, campaign, knobs)
    _mark(steps, "create", "done", "spec")
    _mark(steps, "reconstruct", "done", "spec")
    _mark(steps, bundle["format_skill"], "done", spec.format)

    mockup = payload.get("mockup") if isinstance(payload.get("mockup"), dict) else {}
    base_html = payload.get("base_html") or mockup.get("html")
    if not base_html:
        _mark(steps, "implement", "running", "mockup")
        mockup = build_base_mockup(
            spec,
            brand=brand,
            campaign=campaign or {},
            knobs=knobs,
            images=images,
            assets={
                "logo_url": brand.get("logo_url"),
                "scene_image": photos[0] if photos else "",
            },
            brand_prototypes=(client.get("brand_profile") or {}).get("format_prototypes")
            if isinstance(client.get("brand_profile"), dict)
            else None,
            text_callable=text_callable,
            screenshot=screenshot,
            passes=payload.get("mockup_passes") or knobs.get("mockup_passes"),
        )
        base_html = mockup.get("html")
    if str(payload.get("stage") or "") == "mockup":
        return _mockup_payload(
            payload, spec, brand, campaign, knobs, images, bundle, steps, mockup, user_message
        )

    scenes = []
    purposes = composition_purposes(spec.variant, knobs["scene_count"])
    _mark(steps, "implement", "running")
    pending = []
    for index, scene in enumerate(spec.scenes):
        purpose = scene.purpose or purposes[index]
        visual = _scene_visual(campaign, scene.id, knobs.get("key_visuals"), photos, index)
        if scene_id and scene.id != scene_id:
            kept = existing.get(scene.id) or {
                "id": scene.id,
                "label": f"0{index + 1} {purpose}",
                "duration": scene.duration,
                "purpose": purpose,
                "role": ROLE_MAP.get(purpose, "unico"),
                "headline": scene.headline,
                "html": "",
                "image_prompt": _scene_prompt(campaign, scene.id),
                "key_visual": visual,
                "layers": [],
            }
            scenes.append(kept)
            continue
        poster = payload.get("assets") if isinstance(payload.get("assets"), dict) else {}
        assets = {
            "logo_url": brand.get("logo_url") if _logo_on(scene, knobs) else "",
            "qr_url": payload.get("qr_url"),
            "scene_image": visual,
            "cast_url": payload.get("cast_url") or poster.get("cast_url"),
            "ground_url": payload.get("ground_url") or poster.get("ground_url"),
            "field": payload.get("field") or poster.get("field"),
            "chips": payload.get("chips") or poster.get("chips"),
            "meta": payload.get("meta") or poster.get("meta"),
            "lockup": payload.get("lockup") or poster.get("lockup"),
        }
        html_text = build_scene_html(
            spec,
            scene,
            dna=brand.get("brand_dna"),
            assets=assets,
            brand_prototypes=(client.get("brand_profile") or {}).get("format_prototypes")
            if isinstance(client.get("brand_profile"), dict)
            else None,
            base_html=base_html,
            logo_visible=_logo_on(scene, knobs),
        )
        built = {
            "id": scene.id,
            "label": f"0{index + 1} {purpose}",
            "duration": scene.duration,
            "purpose": purpose,
            "role": ROLE_MAP.get(purpose, "unico"),
            "headline": scene.headline,
            "support": scene.support,
            "cta": scene.cta,
            "set_note": scene.set_note,
            "action_note": scene.action_note,
            "html": html_text,
            "image_prompt": _scene_prompt(campaign, scene.id),
            "key_visual": visual,
            "logo_visible": _logo_on(scene, knobs),
            "layers": export_layers(html_text, scene.id),
            "stack": _scene_stack(scene, purpose, brand, visual, knobs, assets),
        }
        scenes.append(built)
        pending.append(scene.id)
    _mark(steps, "implement", "done", f"{len(pending) or len(scenes)} cenas")
    _mark(steps, "render", "running")
    qa_bundle = run_qa_loop(
        spec=spec,
        scenes=scenes,
        renders=clamp_renders(
            payload.get("renders") or payload.get("attempts") or SCENE_VERSIONS
        ),
        reference_urls=images,
        text_callable=text_callable,
        screenshot=screenshot,
        scene_id=scene_id or None,
        brand=brand,
    )
    _mark(steps, "validate", "done" if qa_bundle["qa"].get("passed") else "review", "QA")
    scenes = qa_bundle["scenes"]
    for item in scenes:
        item["layers"] = export_layers(item["html"], item["id"])
    cards = export_scene_cards(scenes)
    qa = qa_bundle["qa"]
    status = "ready" if qa.get("passed") else "review"
    still_read = pack_still_record(
        knobs,
        image=_first_still(user_images),
        persisted=persisted_read or payload.get("still_read"),
        session_id=session_id or str(payload.get("session_id") or ""),
        reread=reread,
    )
    knobs["still_read_id"] = still_read.get("read_id") or ""
    copy_origin = build_copy_origin(spec, campaign, knobs)
    copy_origin["read_id"] = still_read.get("read_id") or ""
    copy_origin["qa_passed"] = bool(qa.get("passed"))
    return {
        "id": str(payload.get("session_id") or new_session_id()),
        "intent": spec.intent,
        "format": spec.format,
        "variant": spec.variant,
        "adapter": spec.adapter,
        "platform_label": spec.platform_label,
        "brand_name": spec.brand_name,
        "brand": brand,
        "brand_dna": brand.get("brand_dna"),
        "campaign": {
            "slug": (campaign or {}).get("slug"),
            "title": (campaign or {}).get("title"),
            "objective": (campaign or {}).get("objective"),
        } if campaign else None,
        "spec": spec.model_dump(),
        "scenes": scenes,
        "layers": cards[0]["layers"] if cards else [],
        "cards": cards,
        "renders": qa_bundle["renders"],
        "versions": _merge_versions(
            payload.get("versions"), qa_bundle.get("versions"), scene_id
        ),
        "qa": qa,
        "attempts": qa_bundle.get("attempts") or [],
        "status": status,
        "message": user_message,
        "skills": bundle["skills"],
        "selected_skills": knobs.get("selected_skills") or [],
        "trace": {
            "intent": bundle["intent"],
            "packs": bundle["packs"],
            "skills": bundle["skills"],
            "selected_skills": knobs.get("selected_skills") or [],
            "steps": steps,
        },
        "references": images,
        "knobs": knobs,
        "copy_bind": knobs.get("still_bind") or {},
        "still_read": still_read,
        "copy_origin": copy_origin,
        "scene_count": len(scenes),
        "duration": 15,
        "base_html": base_html,
        "mockup": mockup,
    }


def apply_manual_patch(session, payload, *, text_callable=None, screenshot=None):
    session = dict(session or {})
    payload = payload if isinstance(payload, dict) else {}
    from .html_builder import apply_patches
    from .spec import parse_format_spec

    patches = payload.get("patches") or []
    scene_id = str(payload.get("scene_id") or "")
    scenes = [dict(item) for item in session.get("scenes") or []]
    for item in scenes:
        if scene_id and item.get("id") != scene_id:
            continue
        item["html"] = apply_patches(item.get("html"), patches)
        item["layers"] = export_layers(item["html"], item["id"])
    spec = parse_format_spec(session.get("spec"))
    qa_bundle = run_qa_loop(
        spec=spec,
        scenes=scenes,
        renders=clamp_renders(payload.get("renders") or 1),
        reference_urls=payload.get("images") or session.get("references") or [],
        text_callable=text_callable,
        screenshot=screenshot,
        scene_id=scene_id or None,
        brand=session.get("brand") if isinstance(session.get("brand"), dict) else {},
    )
    scenes = qa_bundle["scenes"]
    for item in scenes:
        item["layers"] = export_layers(item["html"], item["id"])
    cards = export_scene_cards(scenes)
    qa = qa_bundle["qa"]
    session.update({
        "scenes": scenes,
        "layers": cards[0]["layers"] if cards else [],
        "cards": cards,
        "renders": qa_bundle["renders"],
        "versions": _merge_versions(session.get("versions"), qa_bundle.get("versions"), scene_id),
        "qa": qa,
        "status": "ready" if qa.get("passed") else "review",
    })
    session.setdefault("attempts", []).extend(qa_bundle.get("attempts") or [])
    return session


def _logo_on(scene, knobs):
    knobs = knobs if isinstance(knobs, dict) else {}
    return scene_logo_visible(
        scene.purpose,
        scene.id,
        knobs,
        scene_count=knobs.get("scene_count"),
        scene_flag=getattr(scene, "logo_visible", None),
    )


def _scene_stack(scene, purpose, brand, visual, knobs, assets=None):
    knobs = knobs if isinstance(knobs, dict) else {}
    extras = assets if isinstance(assets, dict) else {}
    stack = build_stack(
        {
            "id": scene.id,
            "purpose": purpose,
            "headline": scene.headline,
            "support": scene.support,
            "cta": scene.cta,
            "logo_visible": _logo_on(scene, knobs),
            "scene_count": knobs.get("scene_count"),
            "key_visual": visual,
        },
        brand=brand,
        assets={
            "scene_image": visual,
            "logo_url": brand.get("logo_url"),
            "cast_url": extras.get("cast_url"),
            "ground_url": extras.get("ground_url"),
            "field": extras.get("field"),
        },
    )
    stack["guidelines"] = check_stack(stack)
    return stack


def _payload_images(payload):
    urls = []
    for url in payload.get("images") or payload.get("references") or []:
        if url and url not in urls:
            urls.append(url)
    for item in payload.get("files") or []:
        url = item if isinstance(item, str) else (item or {}).get("url") or (item or {}).get("asset_url")
        if url and url not in urls:
            urls.append(url)
    return urls


def _mockup_payload(payload, spec, brand, campaign, knobs, images, bundle, steps, mockup, user_message):
    _mark(steps, "implement", "done", "mockup")
    _mark(steps, "validate", "done", "base")
    return {
        "id": str(payload.get("session_id") or new_session_id()),
        "intent": spec.intent,
        "format": spec.format,
        "variant": spec.variant,
        "adapter": spec.adapter,
        "platform_label": spec.platform_label,
        "brand_name": spec.brand_name,
        "brand": brand,
        "brand_dna": brand.get("brand_dna"),
        "campaign": {
            "slug": (campaign or {}).get("slug"),
            "title": (campaign or {}).get("title"),
            "objective": (campaign or {}).get("objective"),
        } if campaign else None,
        "spec": spec.model_dump(),
        "scenes": payload.get("scenes") or [],
        "storyboard": payload.get("storyboard") or [],
        "base_html": mockup.get("html"),
        "mockup": mockup,
        "renders": [{
            "scene_id": "base",
            "attempt": mockup.get("passes") or 1,
            "png_data_url": mockup.get("render_url"),
        }],
        "versions": mockup.get("versions") or [],
        "qa": {"passed": True, "notes": ["Mockup-base modelado."]},
        "status": "concept",
        "message": user_message,
        "skills": bundle["skills"],
        "trace": {
            "intent": bundle["intent"],
            "packs": bundle["packs"],
            "skills": bundle["skills"],
            "steps": steps,
        },
        "references": images,
        "knobs": knobs,
        "scene_count": knobs.get("scene_count") or len(spec.scenes),
        "duration": 15,
    }


def _scene_visual(campaign, scene_id, mapping=None, photos=None, index=0):
    pinned = mapping if isinstance(mapping, dict) else {}
    if pinned.get(scene_id):
        return pinned[scene_id]
    if isinstance(campaign, dict):
        for item in campaign.get("scenes") or []:
            if item.get("id") == scene_id and item.get("key_visual"):
                return item["key_visual"]
    photos = photos or []
    if index < len(photos):
        return photos[index]
    return ""


def _merge_versions(previous, incoming, scene_id=None):
    kept = []
    incoming = incoming or []
    target = str(scene_id or "").strip()
    for item in previous or []:
        if not isinstance(item, dict):
            continue
        if target and item.get("scene_id") == target:
            continue
        kept.append(item)
    kept.extend(item for item in incoming if isinstance(item, dict))
    return kept


def _scene_prompt(campaign, scene_id):
    if not isinstance(campaign, dict):
        return ""
    for item in campaign.get("scenes") or []:
        if item.get("id") == scene_id:
            return item.get("image_prompt") or ""
    return ""


def _mark(steps, skill_id, status, note=""):
    for item in steps:
        if item["id"] == skill_id:
            item["status"] = status
            if note:
                item["note"] = note
            return
