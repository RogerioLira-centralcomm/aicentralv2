"""Cena-base: mockup HTML preto + marca, 1–3 passes baratos (GPT-4o-mini)."""

from __future__ import annotations

import json

from ..creative_modeling_generation import OpenRouterError, _json_content
from ..creative_skills.visual import load_visual_brief
from .catalog import is_end_card, logo_visible_for
from .engineer import _resolve_offer
from .lab_models import JSON_OBJECT, MOCKUP_MODEL, MOCKUP_TEMPERATURE, lab_chat_model
from .html_builder import (
    apply_cta_visibility,
    apply_logo_visibility,
    apply_patches,
    build_scene_html,
    ensure_system_layers,
)
from .layer_export import snapshot_layers
from .spec import QaPatch
from .visual_qa import clamp_renders, lock_copy_patches, png_data_url, render_png, still_is_usable

MOCKUP_PASSES = 3
MOCKUP_ESTIMATE_USD = 0.005
MOCKUP_LAYER_IDS = (
    "layer-brand",
    "layer-headline",
    "layer-support",
    "layer-cta",
    "layer-key-visual",
)


def build_base_mockup(
    spec,
    *,
    brand=None,
    campaign=None,
    knobs=None,
    images=None,
    assets=None,
    brand_prototypes=None,
    text_callable=None,
    screenshot=None,
    passes=None,
):
    brand = brand if isinstance(brand, dict) else {}
    campaign = campaign if isinstance(campaign, dict) else {}
    knobs = knobs if isinstance(knobs, dict) else {}
    images = [
        url for url in (images or [])
        if isinstance(url, str) and url.startswith("https://")
    ][:4]
    attempts = clamp_renders(passes or knobs.get("mockup_passes") or MOCKUP_PASSES)
    scene = spec.scenes[0]
    html_text = build_scene_html(
        spec,
        scene,
        dna=brand.get("brand_dna"),
        assets=assets,
        brand_prototypes=brand_prototypes,
        render=True,
        logo_visible=True,
        mockup=True,
    )
    html_text = ensure_system_layers(html_text)
    versions = []
    reports = []
    current = html_text
    best = {"score": 0.55, "html": current, "attempt": 1}
    provider = "plate"
    model = lab_chat_model("mockup")
    previous_render = ""
    for attempt in range(1, attempts + 1):
        if text_callable is not None:
            try:
                current = _refine_mockup(
                    current,
                    spec=spec,
                    brand=brand,
                    campaign=campaign,
                    knobs=knobs,
                    images=images,
                    attempt=attempt,
                    plate_render=previous_render,
                    text_callable=text_callable,
                )
                provider = "llm"
            except (OpenRouterError, ValueError, TypeError, KeyError):
                pass
        current = ensure_system_layers(current)
        current = apply_logo_visibility(current, True)
        png = render_png(current, spec.canvas.width, spec.canvas.height, screenshot)
        url = png_data_url(png)
        previous_render = url
        score = min(0.95, 0.55 + (0.15 * attempt))
        versions.append({
            "scene_id": "base",
            "attempt": attempt,
            "html": current,
            "png_data_url": url,
            "score": score,
            "passed": attempt == attempts,
            "discarded": True,
            "model": model if provider == "llm" else "plate",
        })
        reports.append({
            "attempt": attempt,
            "model": model if provider == "llm" else "plate",
            "score": score,
        })
        if score >= best["score"]:
            best = {"score": score, "html": current, "attempt": attempt}
    for item in versions:
        item["discarded"] = item["attempt"] != best["attempt"]
        item["chosen"] = item["attempt"] == best["attempt"]
    plan = layer_plan(spec, knobs)
    return {
        "id": "base",
        "html": best["html"],
        "render_url": next(
            (item["png_data_url"] for item in versions if item.get("chosen")),
            versions[-1]["png_data_url"] if versions else "",
        ),
        "versions": versions,
        "attempts": reports,
        "passes": len(versions),
        "model": MOCKUP_MODEL,
        "provider": provider,
        "layer_plan": plan,
        "status": "ready",
    }


def layer_plan(spec, knobs=None):
    knobs = knobs if isinstance(knobs, dict) else {}
    scenes = []
    count = len(getattr(spec, "scenes", []) or [])
    for scene in getattr(spec, "scenes", []) or []:
        purpose = scene.purpose
        show_logo = scene_logo_visible(
            purpose,
            scene.id,
            knobs,
            scene_count=count,
            scene_flag=getattr(scene, "logo_visible", None),
        )
        scenes.append({
            "id": scene.id,
            "purpose": purpose,
            "logo_visible": show_logo,
            "cta_visible": is_end_card(purpose, scene.id, count),
        })
    return {
        "logo_on": [item["id"] for item in scenes if item["logo_visible"]],
        "cta_on": [item["id"] for item in scenes if item["cta_visible"]],
        "scenes": scenes,
    }


def scene_logo_visible(purpose, scene_id=None, knobs=None, scene_count=None, scene_flag=None):
    knobs = knobs if isinstance(knobs, dict) else {}
    if scene_count is None:
        scene_count = knobs.get("scene_count")
    if is_end_card(purpose, scene_id, scene_count):
        return True
    for item in knobs.get("storyboard") or []:
        if isinstance(item, dict) and item.get("id") == scene_id and "logo_visible" in item:
            return bool(item.get("logo_visible"))
    if scene_flag is not None:
        return bool(scene_flag)
    return logo_visible_for(purpose, scene_id, scene_count)


def _refine_mockup(
    html_text,
    *,
    spec,
    brand,
    campaign,
    knobs,
    images,
    attempt,
    text_callable,
    plate_render="",
):
    layers = snapshot_layers(html_text, MOCKUP_LAYER_IDS)
    payload = {
        "task": f"Pass {attempt}/{MOCKUP_PASSES}: patch this black 16:9 plate. Use the current layers"
        + (" and the previous still." if still_is_usable(plate_render) else "."),
        "rules": [
            "Return JSON only: {passed, score, defects[], patches[{layer_id,text,css}], css_vars{}}.",
            "No markdown fences. css is a string, not an object.",
            "Do not return a new HTML document.",
            "Keep layer IDs. Keep 1920x1080. Keep the black velvet plate.",
            "Use brand ink/accent/logo. Do not invent a layout.",
            "Pick one plate: split (product floats right), hero (photo full-bleed), or center (end card).",
            "Do not draw Netflix/YouTube chrome. Channel dress comes later.",
            "Key visual has no frame. Product sits on black, like a beauty still.",
            "No uppercase headlines. No pill buttons. No player chrome.",
            "Logo in the base is a system mark, not a lock for every later scene.",
            "No website menu, no extra scenes, no grey landscape drawing.",
            "Patch from the current layer texts. Do not invent missing copy.",
            "Do not rewrite headline, support or CTA. CSS and key-visual only.",
            "The base plate has no end-card CTA. Leave layer-cta empty.",
        ],
        "selected_skills": knobs.get("selected_skills") or [],
        "visual_skill": load_visual_brief(knobs.get("selected_skills"), stage="html"),
        "attempt": attempt,
        "format": spec.format,
        "brand": {
            "name": brand.get("name"),
            "palette": brand.get("palette"),
            "tone": brand.get("tone_of_voice"),
            "forbidden": brand.get("forbidden_elements"),
            "mandatory": brand.get("mandatory_elements"),
            "guidelines": brand.get("creative_guidelines"),
            "logo_url": brand.get("logo_url"),
        },
        "campaign": {
            "title": campaign.get("title"),
            "offer": knobs.get("offer") or _resolve_offer(knobs, campaign),
            "objective": knobs.get("objective") or campaign.get("objective"),
        },
        "layer_ids": list(MOCKUP_LAYER_IDS),
        "layers": layers,
        "locked": {
            "headline": spec.scenes[0].headline,
            "support": spec.scenes[0].support,
            "cta": spec.scenes[0].cta or "",
        },
        "has_previous_still": still_is_usable(plate_render),
    }
    content = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]
    for url in images:
        if isinstance(url, str) and url.startswith("https://"):
            content.append({"type": "image_url", "image_url": {"url": url}})
    if still_is_usable(plate_render):
        content.append({"type": "image_url", "image_url": {"url": plate_render}})
    response = text_callable(
        [
            {
                "role": "system",
                "content": _mockup_system(knobs),
            },
            {"role": "user", "content": content},
        ],
        model=lab_chat_model("mockup"),
        max_tokens=900,
        temperature=MOCKUP_TEMPERATURE,
        response_format=JSON_OBJECT,
    )
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if not isinstance(raw, dict):
        try:
            raw = _json_content(raw)
        except Exception:
            try:
                raw = json.loads(str(raw))
            except Exception:
                return html_text
    patches = []
    for item in raw.get("patches") or []:
        try:
            patches.append(QaPatch.model_validate(item).model_dump())
        except Exception:
            continue
    first = spec.scenes[0]
    patches = lock_copy_patches(
        patches,
        {"headline": first.headline, "support": first.support, "cta": first.cta or ""},
    )
    updated = apply_patches(html_text, patches)
    css_vars = raw.get("css_vars") if isinstance(raw.get("css_vars"), dict) else {}
    if css_vars:
        updated = _apply_css_vars(updated, css_vars)
    show_cta = bool(first.cta) or is_end_card(first.purpose, first.id, len(spec.scenes))
    return apply_cta_visibility(updated, show_cta)


def _apply_css_vars(html_text, css_vars):
    declarations = []
    allowed = {
        "--brand-ink",
        "--brand-accent",
        "--brand-muted",
        "--brand-paper",
        "--logo",
    }
    for key, value in css_vars.items():
        name = str(key)
        if not name.startswith("--"):
            name = f"--{name}"
        if name not in allowed or not value:
            continue
        declarations.append(f"{name}:{value}")
    if not declarations:
        return html_text
    block = ":root{" + ";".join(declarations) + "}"
    if "</style>" in html_text:
        return html_text.replace("</style>", f"{block}\n</style>", 1)
    return html_text


def _mockup_system(knobs=None):
    brief = load_visual_brief((knobs or {}).get("selected_skills"), stage="html")
    base = (
        "You model advertising format HTML. "
        "Black 16:9 mockup first. Patches only. GPT-4o-mini fidelity pass. "
        "Reply with one JSON object only. No markdown fences."
    )
    if not brief:
        return base
    return f"{base}\n\nSelected visual skill for this still:\n{brief}"
