"""Render Chromium + QA visual. Devolve patch, não rewrite."""

from __future__ import annotations

import base64
import json
import os

from ..creative_html_compose import screenshot_html
from ..creative_modeling_generation import _json_content
from .html_builder import apply_patches
from .spec import parse_qa_report

QA_MODEL = os.getenv("CREATIVE_FORMAT_QA_MODEL", "openai/gpt-5.4")
MAX_RENDERS = 3


def clamp_renders(value):
    try:
        return max(1, min(MAX_RENDERS, int(value)))
    except (TypeError, ValueError):
        return 1


def render_png(html_text, width=1920, height=1080, screenshot=None):
    runner = screenshot or screenshot_html
    return runner(html_text, width, height)


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
    payload = json.dumps(
        {
            "format": spec.format,
            "variant": spec.variant,
            "adapter": spec.adapter,
            "attempt": attempt,
            "rules": [
                "Compare reference vs rendered result.",
                "Return patches, not a full rewrite.",
                "Preserve mechanic, QR position, CTA position, safe area.",
                "JSON: passed, score 0-1, defects[], notes[], patches[{layer_id,text,css}].",
            ],
        },
        ensure_ascii=False,
    )
    images = [render_url] + [url for url in (reference_urls or []) if url]
    content = [{"type": "text", "text": payload}]
    for url in images:
        content.append({"type": "image_url", "image_url": {"url": url}})
    response = text_callable(
        [
            {
                "role": "system",
                "content": (
                    "You are the Visual QA step of Creative Format Engineer. "
                    "Fidelity first. Return patches, never a new HTML document."
                ),
            },
            {"role": "user", "content": content},
        ],
        model=QA_MODEL,
        max_tokens=800,
        temperature=0.1,
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
        return parse_qa_report(raw, attempt=attempt)
    except Exception:
        return parse_qa_report(
            {"passed": False, "score": 0, "defects": ["QA inválido"], "patches": []},
            attempt=attempt,
        )


def run_qa_loop(
    *,
    spec,
    scenes,
    renders=1,
    reference_urls=None,
    text_callable=None,
    screenshot=None,
    scene_id=None,
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
