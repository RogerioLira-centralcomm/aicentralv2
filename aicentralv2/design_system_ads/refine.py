"""Loop de fidelidade: até 4 passes, patches de token, gpt-4o-mini."""

from __future__ import annotations

import json
import os

from ..creative_modeling_generation import _json_content
from ..services.openrouter_service import resolve_chat_model
from .schema import (
    MAX_PASSES,
    MIN_CONTRAST,
    DesignSystemAds,
    DesignSystemPass,
    contrast_ratio,
    dump_system,
    normalize_hex,
    parse_system,
)

REFINE_MODEL = os.getenv("DESIGN_SYSTEM_ADS_MODEL", "openai/gpt-4o-mini")


def clamp_passes(value):
    try:
        return max(1, min(MAX_PASSES, int(value)))
    except (TypeError, ValueError):
        return 1


def apply_token_patches(system, patches):
    parsed = parse_system(system)
    tokens = dict(parsed.tokens)
    applied = []
    for item in patches or []:
        if not isinstance(item, dict):
            continue
        token_id = str(item.get("token_id") or item.get("id") or "").strip()
        css = item.get("css") if item.get("css") is not None else item.get("value")
        if not token_id or css is None or token_id not in tokens:
            continue
        if token_id in {"paper", "ink", "accent", "muted", "cta_ink", "highlight"}:
            color = normalize_hex(css)
            if not color:
                continue
            tokens[token_id] = color
        else:
            tokens[token_id] = str(css).strip()[:120]
        applied.append(
            {
                "token_id": token_id,
                "css": tokens[token_id],
                "reason": str(item.get("reason") or "")[:240],
            }
        )
    data = dump_system(parsed)
    data["tokens"] = tokens
    data["passes"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in parsed.passes]
    return DesignSystemAds.model_validate(data), applied


def heal_contrast(system):
    parsed = parse_system(system)
    tokens = dict(parsed.tokens)
    paper = normalize_hex(tokens.get("paper"), "#FFFFFF")
    ink = normalize_hex(tokens.get("ink"), "#1E4D4F")
    accent = normalize_hex(tokens.get("accent"), ink)
    cta_ink = normalize_hex(tokens.get("cta_ink"), "#FFFFFF")
    patches = []
    if contrast_ratio(ink, paper) < MIN_CONTRAST:
        tokens["ink"] = "#1E4D4F" if paper.upper() in {"#FFFFFF", "#F8F9FA", "#FFF"} else "#FFFFFF"
        patches.append({"token_id": "ink", "css": tokens["ink"], "reason": "Contraste ink/paper abaixo de 4.5."})
    if contrast_ratio(cta_ink, accent) < MIN_CONTRAST:
        tokens["accent"] = tokens.get("ink") or "#1E4D4F"
        tokens["cta_ink"] = "#FFFFFF"
        patches.append({"token_id": "accent", "css": tokens["accent"], "reason": "CTA sem contraste. Fill da tinta da marca."})
        patches.append({"token_id": "cta_ink", "css": "#FFFFFF", "reason": "Texto do CTA em branco."})
    data = dump_system(parsed)
    data["tokens"] = tokens
    healed = DesignSystemAds.model_validate(data)
    return healed, patches


def refine_design_system(
    system,
    *,
    attempts=4,
    text_callable=None,
    reference_urls=None,
):
    current = parse_system(system)
    current, heal_patches = heal_contrast(current)
    limit = clamp_passes(attempts)
    already = len(current.passes)
    remaining = max(0, MAX_PASSES - already)
    budget = min(limit, remaining) if remaining else 0
    reports = []

    if already == 0:
        first = DesignSystemPass(
            attempt=1,
            passed=bool(current.contrast.get("passed")),
            score=1.0 if current.contrast.get("passed") else 0.6,
            defects=[] if current.contrast.get("passed") else ["Contraste ajustado na materialização."],
            notes=["Passo local: tokens da marca e tema Tailwind."],
            patches=heal_patches,
        )
        current = _append_pass(current, first)
        reports.append(first)
        if first.passed and not text_callable:
            return current, reports
        budget = max(0, budget - 1)

    if text_callable is None or budget <= 0:
        return current, reports

    last_score = reports[-1].score if reports else 0.0
    for step in range(budget):
        attempt = len(current.passes) + 1
        review = _review_tokens(
            current,
            attempt=attempt,
            text_callable=text_callable,
            reference_urls=reference_urls,
        )
        if review.patches:
            current, applied = apply_token_patches(current, review.patches)
            review.patches = applied
            current, _ = heal_contrast(current)
        current = _append_pass(current, review)
        reports.append(review)
        if review.passed:
            break
        if review.score and last_score and review.score < last_score:
            break
        last_score = review.score
    return current, reports


def _append_pass(system, report):
    data = dump_system(system)
    passes = list(data.get("passes") or [])
    passes.append(report.model_dump() if isinstance(report, DesignSystemPass) else report)
    data["passes"] = passes[:MAX_PASSES]
    data["version"] = max(1, int(data.get("version") or 1))
    return DesignSystemAds.model_validate(data)


def _review_tokens(system, *, attempt, text_callable, reference_urls=None):
    parsed = parse_system(system)
    payload = json.dumps(
        {
            "framework": "design-system-ads",
            "attempt": attempt,
            "tokens": parsed.tokens,
            "contrast": parsed.contrast,
            "copy": parsed.ad_copy,
            "rules": [
                "Fidelity first. Return token patches, never a new system.",
                "Keep Tailwind class names (bg-dsa-paper, text-dsa-ink, bg-dsa-accent).",
                "Do not invent a cream, terracotta, or acid-green palette.",
                "JSON: passed, score 0-1, defects[], notes[], patches[{token_id,css,reason}].",
            ],
        },
        ensure_ascii=False,
    )
    images = [url for url in (reference_urls or []) if url]
    content = [{"type": "text", "text": payload}]
    for url in images[:4]:
        content.append({"type": "image_url", "image_url": {"url": url}})
    try:
        response = text_callable(
            [
                {
                    "role": "system",
                    "content": (
                        "You refine Design System Ads tokens. "
                        "Fonts, contrast and CSS only. Patches, never rewrite."
                    ),
                },
                {"role": "user", "content": content},
            ],
            model=resolve_chat_model(REFINE_MODEL),
            max_tokens=700,
            temperature=0.1,
        )
    except Exception:
        return DesignSystemPass(
            attempt=attempt,
            passed=bool(parsed.contrast.get("passed")),
            score=0.5,
            defects=["O refino não concluiu."],
            patches=[],
        )
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if not isinstance(raw, dict):
        try:
            raw = _json_content(raw)
        except Exception:
            try:
                raw = json.loads(str(raw))
            except Exception:
                raw = {"passed": False, "defects": ["O refino não devolveu JSON."]}
    try:
        score = float(raw.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    return DesignSystemPass(
        attempt=attempt,
        passed=bool(raw.get("passed")),
        score=max(0.0, min(1.0, score)),
        defects=[str(item)[:200] for item in (raw.get("defects") or [])][:8],
        notes=[str(item)[:200] for item in (raw.get("notes") or [])][:8],
        patches=[item for item in (raw.get("patches") or []) if isinstance(item, dict)][:12],
    )
