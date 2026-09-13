"""Studio: roteiro → referências → cenas HTML → animação. Sem Trocr."""

from __future__ import annotations

import base64
import logging

from ..creative_modeling_fx import annotate_cost
from .brand_context import build_brand_context
from .catalog import (
    clamp_scene_count,
    composition_purposes,
    format_entry,
    is_ctv_format,
    toggles_for_purpose,
)
from .html_builder import build_scene_html
from .refine import draft_image_prompt, draft_script, refine_image_prompt, refine_script
from .spec import parse_format_spec
from .stack import build_stack

logger = logging.getLogger(__name__)

CAST_MODEL = "google/gemini-3-pro-image"
SEEDANCE_MODEL = "bytedance/seedance-2.0-mini"
SEEDANCE_PROMPT = (
    "Animate this advertising sequence. Keep the same people, wardrobe, lighting and brand colors. "
    "Gentle camera and product motion only. Do not add new text, logo, UI chrome, neon or extra people. "
    "Hold the last frame as an end card. No voiceover."
)
SCRIPT_ESTIMATE_USD = 0.03
IMAGE_PROMPT_ESTIMATE_USD = 0.005
CAST_ESTIMATE_USD = 0.13
GROUND_ESTIMATE_USD = 0.13
SEEDANCE_720_USD = 0.38
SEEDANCE_480_USD = 0.17

AGES = ("18-24", "25-34", "35-44", "45-54", "55+")
CAST_KINDS = ("1 pessoa", "2", "família", "trabalho")


def quote_prototype(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    recipe = payload.get("recipe") if isinstance(payload.get("recipe"), dict) else {}
    need_cast = bool(payload.get("need_cast", True) or recipe.get("pessoa"))
    ground = str(payload.get("fundo") or "lavagem").strip().lower()
    need_ground = ground in {"imagem", "image"}
    video = bool(payload.get("video"))
    resolution = str(payload.get("video_resolution") or "720p")
    usd = SCRIPT_ESTIMATE_USD + IMAGE_PROMPT_ESTIMATE_USD
    if need_cast:
        usd += CAST_ESTIMATE_USD + IMAGE_PROMPT_ESTIMATE_USD
    if need_ground:
        usd += GROUND_ESTIMATE_USD + IMAGE_PROMPT_ESTIMATE_USD
    if video:
        usd += SEEDANCE_480_USD if resolution == "480p" else SEEDANCE_720_USD
    return annotate_cost({
        "estimated_cost_usd": round(usd, 3),
        "model": CAST_MODEL,
        "passes": 0,
        "quality": "studio",
        "later": {"image": need_cast or need_ground, "video": video},
        "line": {
            "script": SCRIPT_ESTIMATE_USD,
            "cast": CAST_ESTIMATE_USD if need_cast else 0,
            "ground": GROUND_ESTIMATE_USD if need_ground else 0,
            "video": (SEEDANCE_480_USD if resolution == "480p" else SEEDANCE_720_USD) if video else 0,
            "display_css": 0,
        },
    })


def infer_persona(brand=None):
    brand = brand if isinstance(brand, dict) else {}
    audience = " ".join([
        str(brand.get("target_audience") or ""),
        " ".join(str(item) for item in (brand.get("ad_segments") or [])),
        str(brand.get("sector") or ""),
    ]).casefold()
    age = "25-34"
    if any(token in audience for token in ("55", "60", "senior", "aposent")):
        age = "55+"
    elif any(token in audience for token in ("45", "50", "maduro")):
        age = "45-54"
    elif any(token in audience for token in ("18", "jovem", "gen z", "universit")):
        age = "18-24"
    elif any(token in audience for token in ("35", "40", "família", "familia", "pais")):
        age = "35-44"
    elenco = "1 pessoa"
    if any(token in audience for token in ("família", "familia", "casal", "pais")):
        elenco = "família"
    elif any(token in audience for token in ("trabalho", "escritório", "escritorio", "b2b", "corporativ")):
        elenco = "trabalho"
    elif any(token in audience for token in ("casal", "dois", "2 pessoas")):
        elenco = "2"
    return {"elenco": elenco, "idade": age, "fundo": "lavagem"}


def build_script(payload=None, *, brand=None, text_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    brand = brand if isinstance(brand, dict) else build_brand_context(payload.get("client"))
    format_key = payload.get("format_key") or payload.get("format") or "video-linear-15"
    scene_count = clamp_scene_count(payload.get("scene_count") or 4)
    variant = str(payload.get("variant") or "C").upper()
    purposes = composition_purposes(variant, scene_count)
    draft_payload = {
        "format": format_key,
        "scene_count": scene_count,
        "objective": payload.get("objective") or "Reconhecimento",
        "variant": variant,
        "purposes": purposes,
        "brand": {
            "name": brand.get("name") or "",
            "tone": brand.get("tone_of_voice") or "",
            "target_audience": brand.get("target_audience") or "",
            "ad_segments": brand.get("ad_segments") or [],
            "forbidden": brand.get("forbidden_elements") or [],
        },
        "offer": payload.get("offer") or "",
        "cta": payload.get("cta") or "",
    }
    v1 = draft_script(text_callable=text_callable, payload=draft_payload)
    if not v1:
        v1 = _fallback_storyboard(purposes, brand, payload)
    packed = refine_script(v1, text_callable=text_callable, brand=draft_payload["brand"], draft_payload=draft_payload)
    selected = packed["v3"]["storyboard"] or packed["v1"]["storyboard"]
    return {
        **packed,
        "storyboard": selected,
        "format_key": format_key,
        "scene_count": scene_count,
        "variant": variant,
        "purposes": purposes,
        "persona": infer_persona(brand),
    }


def build_refs(payload=None, *, brand=None, text_callable=None, image_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    brand = brand if isinstance(brand, dict) else {}
    persona = infer_persona(brand)
    persona.update({
        key: payload[key]
        for key in ("elenco", "idade", "fundo")
        if payload.get(key)
    })
    format_key = payload.get("format_key") or "video-linear-15"
    entry = format_entry(format_key) or {}
    aspect = entry.get("aspect_ratio") or "16:9"
    palette = list(brand.get("palette") or [])
    ink = brand.get("primary_color") or (palette[0] if palette else "")
    accent = brand.get("secondary_color") or (palette[1] if len(palette) > 1 else "")
    refs = {"cast": None, "ground": None, "persona": persona, "prompts": {}}
    need_cast = persona.get("elenco") != "nenhum" and payload.get("need_cast", True)
    if need_cast:
        refs["prompts"]["cast"] = _image_versions(
            text_callable,
            {
                "kind": "cast",
                "elenco": persona.get("elenco"),
                "idade": persona.get("idade"),
                "palette": palette,
                "ink": ink,
                "accent": accent,
                "format": format_key,
            },
        )
        refs["cast"] = _generate_still(
            image_callable,
            refs["prompts"]["cast"]["v3"]["prompt"],
            aspect_ratio=aspect,
        )
    if str(persona.get("fundo") or "").lower() in {"imagem", "image"}:
        refs["prompts"]["ground"] = _image_versions(
            text_callable,
            {
                "kind": "ground",
                "palette": palette,
                "ink": ink,
                "accent": accent,
                "format": format_key,
            },
        )
        refs["ground"] = _generate_still(
            image_callable,
            refs["prompts"]["ground"]["v3"]["prompt"],
            aspect_ratio=aspect,
        )
    return refs


def compose_scenes(payload=None, *, brand=None):
    payload = payload if isinstance(payload, dict) else {}
    brand = brand if isinstance(brand, dict) else {}
    format_key = payload.get("format_key") or "video-linear-15"
    entry = format_entry(format_key) or format_entry("video-linear-15")
    storyboard = list(payload.get("storyboard") or [])
    scene_count = clamp_scene_count(payload.get("scene_count") or len(storyboard) or 4)
    variant = str(payload.get("variant") or "C").upper()
    purposes = composition_purposes(variant, scene_count)
    overrides = payload.get("recipes") if isinstance(payload.get("recipes"), dict) else {}
    refs = payload.get("refs") if isinstance(payload.get("refs"), dict) else {}
    cast_url = (refs.get("cast") or {}).get("url") if isinstance(refs.get("cast"), dict) else ""
    ground_url = (refs.get("ground") or {}).get("url") if isinstance(refs.get("ground"), dict) else ""
    scenes = []
    spec_scenes = []
    for index, purpose in enumerate(purposes):
        scene_id = f"scene_0{index + 1}"
        card = next((item for item in storyboard if item.get("id") == scene_id), None) or {}
        if index < len(storyboard) and not card.get("headline"):
            card = storyboard[index]
        recipe = dict(toggles_for_purpose(purpose, format_key=format_key))
        recipe.update(overrides.get(scene_id) or {})
        scene = {
            "id": scene_id,
            "purpose": purpose,
            "headline": card.get("headline") or "",
            "support": card.get("support") or "",
            "cta": card.get("cta") or "",
            "set_note": card.get("set_note") or "",
            "logo_visible": bool(recipe.get("logo")),
            "recipe": recipe,
        }
        if not recipe.get("titulo"):
            scene["headline"] = ""
        if not recipe.get("texto_curto"):
            scene["support"] = ""
        if not recipe.get("cta"):
            scene["cta"] = ""
        scene["cta_kind"] = recipe.get("cta_kind") or ""
        assets = {
            "logo_url": brand.get("logo_url") or "",
            "cast_url": cast_url if recipe.get("pessoa") else "",
            "ground_url": ground_url if ground_url else "",
            "scene_image": ground_url or cast_url,
        }
        spec_scenes.append({
            "id": scene_id,
            "duration": 15 / max(scene_count, 1),
            "purpose": purpose,
            "headline": scene["headline"],
            "support": scene["support"],
            "cta": scene["cta"],
            "set_note": scene["set_note"],
            "logo_visible": scene["logo_visible"],
        })
        scenes.append(scene)
        scene["_assets"] = assets
    spec = parse_format_spec({
        "intent": "create",
        "format": entry["key"],
        "variant": variant,
        "adapter": entry.get("adapter") or "generic_ctv",
        "platform_label": entry.get("platform_label") or "16:9",
        "brand_name": brand.get("name") or "",
        "scenes": spec_scenes,
    })
    built = []
    for scene in scenes:
        assets = scene.pop("_assets")
        html = build_scene_html(
            spec,
            next(item for item in spec.scenes if item.id == scene["id"]),
            dna=brand.get("brand_dna"),
            assets={
                "logo_url": assets.get("logo_url") or "",
                "cast_url": assets.get("cast_url") or "",
                "ground_url": assets.get("ground_url") or "",
                "scene_image": assets.get("scene_image") or "",
            },
            logo_visible=scene["logo_visible"],
        )
        html = apply_studio_assets(html, assets, scene["recipe"], format_key)
        stack = build_stack(scene, brand=brand, assets=assets)
        built.append({
            **scene,
            "html": html,
            "stack": stack,
            "cta_kind": scene["recipe"].get("cta_kind") or "",
        })
    return {
        "format_key": entry["key"],
        "kind": entry.get("kind") or "video",
        "canvas": entry.get("canvas") or {"width": 1920, "height": 1080},
        "scene_count": scene_count,
        "scenes": built,
        "safe_area": 0.9,
    }


def animate_spec(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    format_key = payload.get("format_key") or "video-linear-15"
    seconds = int(payload.get("seconds") or (5 if is_ctv_format(format_key) else 10))
    if seconds not in {5, 10}:
        seconds = 5
    scenes = list(payload.get("scenes") or [])
    count = max(len(scenes), 1)
    step = seconds / count
    timeline = []
    for index, scene in enumerate(scenes):
        timeline.append({
            "scene_id": scene.get("id") or f"scene_0{index + 1}",
            "start": round(index * step, 2),
            "end": round((index + 1) * step, 2),
            "motion": "fade" if index == 0 else "kenburns",
        })
    return {
        "mode": "css",
        "seconds": seconds,
        "presets": ["fade", "kenburns", "rise", "overlay"],
        "timeline": timeline,
        "cost_usd": 0,
    }


def video_payload(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    scenes = [item for item in (payload.get("scenes") or []) if isinstance(item, dict)]
    first = scenes[0] if scenes else {}
    last = scenes[-1] if scenes else {}
    format_key = payload.get("format_key") or "video-linear-15"
    entry = format_entry(format_key) or {}
    resolution = str(payload.get("resolution") or "720p")
    if resolution not in {"480p", "720p"}:
        resolution = "720p"
    frames = []
    for item, frame_type in ((first, "first_frame"), (last, "last_frame")):
        url = item.get("render_url") or item.get("image_url") or ""
        if url:
            frames.append({
                "type": "image_url",
                "image_url": {"url": url},
                "frame_type": frame_type,
            })
    return {
        "model": SEEDANCE_MODEL,
        "prompt": SEEDANCE_PROMPT,
        "duration": 5,
        "resolution": resolution,
        "aspect_ratio": entry.get("aspect_ratio") or "16:9",
        "generate_audio": False,
        "frame_images": frames,
        "quote": annotate_cost({
            "estimated_cost_usd": SEEDANCE_480_USD if resolution == "480p" else SEEDANCE_720_USD,
            "model": SEEDANCE_MODEL,
            "passes": 1,
            "quality": resolution,
            "later": {"image": False, "video": True},
        }),
    }


def _image_versions(text_callable, knobs):
    v1 = draft_image_prompt(text_callable=text_callable, knobs=knobs)
    return refine_image_prompt(v1, text_callable=text_callable, constraints=knobs)


def _generate_still(image_callable, prompt, *, aspect_ratio="16:9"):
    if not callable(image_callable) or not prompt:
        return None
    result = image_callable(
        prompt,
        aspect_ratio=aspect_ratio,
        resolution="1K",
        model=CAST_MODEL,
    )
    raw = result.get("b64_json") if isinstance(result, dict) else None
    if not raw:
        return {"url": "", "model": CAST_MODEL, "prompt": prompt}
    return {
        "url": "data:image/png;base64," + raw if not str(raw).startswith("data:") else raw,
        "model": result.get("model") or CAST_MODEL,
        "prompt": prompt,
        "usage": result.get("usage") or {},
    }


def _fallback_storyboard(purposes, brand, payload):
    name = brand.get("name") or "Marca"
    cta = payload.get("cta") or "Procure na loja"
    offer = payload.get("offer") or name
    rows = []
    for index, purpose in enumerate(purposes):
        scene_id = f"scene_0{index + 1}"
        rows.append({
            "id": scene_id,
            "purpose": purpose,
            "headline": offer if purpose != "cta" else cta,
            "support": brand.get("brand_summary") or "",
            "cta": cta if purpose == "cta" else "",
            "set_note": f"Cena {purpose} da marca {name}.",
        })
    return rows


def apply_studio_assets(html_text, assets, recipe, format_key):
    from .html_builder import _append_style, apply_cta_visibility

    text = str(html_text or "")
    cast = assets.get("cast_url") or ""
    ground = assets.get("ground_url") or ""
    rules = []
    if ground:
        rules.append(
            f"body.render .stage,.stage{{background-image:url('{ground}');"
            "background-size:cover;background-position:center}"
            if ground else ""
        )
    if cast and recipe.get("pessoa"):
        rules.append(
            f"#layer-key-visual,.key-visual{{background-image:url('{cast}');"
            "background-size:contain;background-repeat:no-repeat;"
            "background-position:center right}"
        )
    if recipe.get("cta_kind") == "instruction" or (
        is_ctv_format(format_key) and recipe.get("cta")
    ):
        rules.append(
            "#layer-cta,.cta{background:transparent;border:0;border-radius:0;"
            "box-shadow:none;padding:0;font-size:clamp(28px,3.2vw,42px);"
            "letter-spacing:.02em;text-transform:none}"
        )
    if not recipe.get("cta"):
        text = apply_cta_visibility(text, False)
    if recipe.get("grafico") and recipe.get("texto_curto"):
        rules.append("#layer-support::after{content:'';display:block;height:6px;"
                     "margin-top:12px;width:40%;background:currentColor;opacity:.35}")
    joined = "".join(item for item in rules if item)
    if joined:
        text = _append_style(text, "studio-assets", joined)
    return text


def encode_png(raw):
    if not raw:
        return ""
    if isinstance(raw, str) and raw.startswith("data:image/"):
        return raw
    if isinstance(raw, str):
        return "data:image/png;base64," + raw
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
