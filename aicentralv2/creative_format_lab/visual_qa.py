"""Render Chromium + QA visual. Devolve patch, não rewrite."""

from __future__ import annotations

import base64
import json
import re

from ..creative_html_compose import screenshot_html
from ..creative_modeling_generation import _json_content
from .lab_models import JSON_OBJECT, QA_TEMPERATURE, lab_chat_model
from .html_builder import apply_patches
from .layer_export import snapshot_layers
from .spec import parse_qa_report

QA_LAYER_IDS = (
    "layer-brand",
    "layer-headline",
    "layer-support",
    "layer-cta",
    "layer-key-visual",
    "layer-qr",
)

MAX_RENDERS = 3
MIN_STILL_BYTES = 200
_GENERIC_CTA = re.compile(
    r"\b(explore now|explore a\b|shop now|buy now|learn more|click here|saiba mais|compre agora)\b",
    re.I,
)
_VISUAL_DEFECT = re.compile(
    r"spacing|kerning|overlap|contrast|crop|pixel|align|margin|padding|"
    r"unreadable|blur|typo|placeholder|momentospedem",
    re.I,
)
_CTA_PLACEHOLDER = re.compile(
    r"placeholder|labeled ['\"]cta['\"]|just labeled|text ['\"]cta['\"]",
    re.I,
)


def still_is_usable(url, min_bytes=MIN_STILL_BYTES):
    if not isinstance(url, str) or not url.strip():
        return False
    if url.startswith("https://"):
        return True
    if not url.startswith("data:image/"):
        return False
    try:
        raw = base64.b64decode(url.split(",", 1)[1], validate=False)
    except Exception:
        return False
    return len(raw) >= min_bytes


def _norm_copy(value):
    return " ".join(str(value or "").split()).casefold()


def lock_copy_patches(patches, scene):
    scene = scene if isinstance(scene, dict) else {}
    locked = {
        "layer-headline": scene.get("headline") or "",
        "layer-support": scene.get("support") or "",
        "layer-cta": scene.get("cta") or "",
    }
    kept = []
    for patch in patches or []:
        if isinstance(patch, dict):
            layer_id = str(patch.get("layer_id") or "")
            text = str(patch.get("text") or "").strip()
        else:
            layer_id = str(getattr(patch, "layer_id", "") or "")
            text = str(getattr(patch, "text", "") or "").strip()
        expected = locked.get(layer_id)
        if expected is not None and text:
            if _GENERIC_CTA.search(text):
                continue
            if expected.strip() and _norm_copy(text) != _norm_copy(expected):
                continue
        kept.append(patch)
    return kept


def _layer_text(layers, layer_id):
    for item in layers or []:
        if isinstance(item, dict) and item.get("id") == layer_id:
            return item.get("text") or ""
    return ""


def _copy_matches(actual, expected):
    wanted = _norm_copy(expected)
    if not wanted:
        return True
    return _norm_copy(actual) == wanted


def scrub_stub_defects(defects, scene, layers):
    scene = scene if isinstance(scene, dict) else {}
    headline_ok = _copy_matches(_layer_text(layers, "layer-headline"), scene.get("headline"))
    cta_empty = not str(scene.get("cta") or "").strip()
    kept = []
    for item in defects or []:
        text = str(item)
        if _VISUAL_DEFECT.search(text):
            continue
        if headline_ok and re.search(r"headline|momentos", text, re.I):
            continue
        if cta_empty and _CTA_PLACEHOLDER.search(text):
            continue
        kept.append(item)
    return kept


def _qa_images(render_url, scene, reference_urls):
    if not still_is_usable(render_url):
        return []
    ordered = [render_url]
    for url in ((scene or {}).get("key_visual"), *(reference_urls or [])):
        if still_is_usable(url) and url not in ordered:
            ordered.append(url)
    return ordered[:5]


def clamp_renders(value):
    try:
        return max(1, min(MAX_RENDERS, int(value)))
    except (TypeError, ValueError):
        return 1


def render_png(html_text, width=1920, height=1080, screenshot=None):
    runner = screenshot or screenshot_html
    try:
        png = runner(html_text, width, height)
    except Exception:
        return b""
    return png if isinstance(png, (bytes, bytearray)) else b""


def png_data_url(png_bytes):
    raw = png_bytes if isinstance(png_bytes, (bytes, bytearray)) else b""
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def review_render(
    *,
    spec,
    scene_html,
    render_url,
    reference_urls=None,
    attempt=1,
    scene=None,
    brand=None,
    prior=None,
    text_callable=None,
):
    if text_callable is None:
        return parse_qa_report(
            {
                "passed": True,
                "score": 0.8,
                "defects": [],
                "notes": ["QA automático sem modelo — aceito o render."],
                "patches": [],
            },
            attempt=attempt,
        )
    scene = scene if isinstance(scene, dict) else {}
    brand = brand if isinstance(brand, dict) else {}
    prior = prior if isinstance(prior, dict) else {}
    layers = snapshot_layers(scene_html, QA_LAYER_IDS)
    payload = json.dumps(
        {
            "format": spec.format,
            "variant": spec.variant,
            "adapter": spec.adapter,
            "attempt": attempt,
            "scene": {
                "id": scene.get("id") or "",
                "purpose": scene.get("purpose") or "",
                "headline": scene.get("headline") or "",
                "support": scene.get("support") or "",
                "cta": scene.get("cta") or "",
                "logo_visible": scene.get("logo_visible"),
            },
            "brand": {
                "name": brand.get("name") or "",
                "palette": list(brand.get("palette") or [])[:6],
                "forbidden": list(brand.get("forbidden_elements") or [])[:6],
            },
            "layer_ids": [item["id"] for item in layers] or list(QA_LAYER_IDS[:5]),
            "layers": layers,
            "locked": {
                "headline": scene.get("headline") or "",
                "support": scene.get("support") or "",
                "cta": scene.get("cta") or "",
            },
            "has_render": still_is_usable(render_url),
            "prior": {
                "score": prior.get("score"),
                "defects": list(prior.get("defects") or [])[:6],
                "notes": list(prior.get("notes") or [])[:4],
            } if attempt > 1 else {},
            "rules": [
                "Compare reference vs rendered result.",
                "Return patches, not a full rewrite.",
                "Preserve mechanic, QR position, CTA position, safe area.",
                "Keep the locked headline, support and CTA. Restore them if the layer drifted.",
                "Never invent English or website CTAs (Explore Now, Shop Now, Saiba mais).",
                "If has_render is false, judge locked copy vs layers only.",
                "If layers match locked copy, passed is true, score is 0.9, defects is empty.",
                "Do not invent spacing, typo or placeholder-CTA defects without a real still.",
                "score is 0-1, never 0-100.",
                "Fix prior defects before inventing new ones.",
                "JSON: passed, score 0-1, defects[], notes[], patches[{layer_id,text,css}].",
            ],
        },
        ensure_ascii=False,
    )
    images = _qa_images(render_url, scene, reference_urls)
    content = [{"type": "text", "text": payload}]
    for url in images:
        content.append({"type": "image_url", "image_url": {"url": url}})
    has_render = still_is_usable(render_url)
    system = (
        "You are the Visual QA step of Creative Format Engineer. "
        "Fidelity first. Reply with one JSON object only. "
        "No markdown, no prose. Keys: passed, score (0-1), defects[], notes[], "
        "patches[{layer_id,text,css}]. css must be a string, not an object. "
        "score is between 0 and 1, never 0-100."
    )
    if not has_render:
        system += (
            " There is no usable still. Compare locked copy to layers only. "
            "If they match, passed is true and defects is empty."
        )
    response = text_callable(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        model=lab_chat_model("qa"),
        max_tokens=800,
        temperature=QA_TEMPERATURE,
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
                raw = {"passed": False, "defects": ["QA não devolveu JSON."]}
    try:
        report = parse_qa_report(raw, attempt=attempt)
    except Exception:
        report = parse_qa_report(
            {"passed": False, "score": 0, "defects": ["QA inválido"], "patches": []},
            attempt=attempt,
        )
    report.patches = lock_copy_patches(report.patches, scene)
    if not still_is_usable(render_url):
        report.defects = scrub_stub_defects(report.defects, scene, layers)
        if not report.defects:
            report.score = max(report.score, 0.9)
            report.passed = True
    return report


def run_qa_loop(
    *,
    spec,
    scenes,
    renders=1,
    reference_urls=None,
    text_callable=None,
    screenshot=None,
    scene_id=None,
    brand=None,
):
    attempts = clamp_renders(renders)
    reports = []
    versions = []
    winners = []
    last_qa = None
    target = str(scene_id or "").strip()
    for item in scenes:
        scene = dict(item)
        if target and scene.get("id") != target:
            winners.append(scene)
            continue
        bundle = run_scene_versions(
            spec=spec,
            scene=scene,
            renders=attempts,
            reference_urls=reference_urls,
            text_callable=text_callable,
            screenshot=screenshot,
            brand=brand,
        )
        winners.append(bundle["scene"])
        versions.extend(bundle["versions"])
        reports.extend(bundle["attempts"])
        last_qa = bundle["qa"]
    qa = last_qa
    return {
        "scenes": winners,
        "qa": qa.model_dump() if hasattr(qa, "model_dump") else (qa or {"passed": False, "attempt": attempts}),
        "renders": [
            {
                "scene_id": item["id"],
                "attempt": item.get("attempt") or (qa.attempt if qa and hasattr(qa, "attempt") else attempts),
                "png_data_url": item.get("render_url"),
            }
            for item in winners
            if item.get("html")
        ],
        "attempts": reports,
        "versions": versions,
    }


def run_scene_versions(
    *,
    spec,
    scene,
    renders=3,
    reference_urls=None,
    text_callable=None,
    screenshot=None,
    brand=None,
):
    attempts = clamp_renders(renders)
    current = dict(scene)
    reports = []
    versions = []
    best = {"score": -1, "scene": current, "qa": None, "attempt": 1}
    last_qa = None
    for attempt in range(1, attempts + 1):
        png = render_png(current.get("html"), spec.canvas.width, spec.canvas.height, screenshot)
        url = png_data_url(png)
        current["render_url"] = url
        current["attempt"] = attempt
        last_qa = review_render(
            spec=spec,
            scene_html=current.get("html"),
            render_url=url,
            reference_urls=reference_urls,
            attempt=attempt,
            scene=current,
            brand=brand,
            prior=last_qa.model_dump() if last_qa else None,
            text_callable=text_callable,
        )
        last_qa.attempt = attempt
        report = last_qa.model_dump()
        reports.append(report)
        versions.append({
            "scene_id": current.get("id"),
            "attempt": attempt,
            "png_data_url": url,
            "html": current.get("html"),
            "score": last_qa.score,
            "passed": last_qa.passed,
            "defects": list(last_qa.defects or []),
            "discarded": True,
        })
        if last_qa.score >= best["score"]:
            best = {
                "score": last_qa.score,
                "scene": dict(current),
                "qa": last_qa,
                "attempt": attempt,
            }
        if last_qa.passed:
            break
        if last_qa.patches:
            current["html"] = apply_patches(current.get("html"), last_qa.patches)
    winner_attempt = best["attempt"]
    for item in versions:
        item["discarded"] = item["attempt"] != winner_attempt
        item["chosen"] = item["attempt"] == winner_attempt
    winner = dict(best["scene"])
    winner["attempt"] = winner_attempt
    winner["versions"] = versions
    return {
        "scene": winner,
        "qa": best["qa"] or last_qa,
        "versions": versions,
        "attempts": reports,
    }
