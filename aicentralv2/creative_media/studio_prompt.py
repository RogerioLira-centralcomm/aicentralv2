"""Safe prompt optimization for Studio image creation and editing.

The original request is always stored separately.  This module may translate
operational instructions to English, but it must preserve every literal that
could be rendered in the creative exactly as the user supplied it.
"""
from __future__ import annotations

import json
import os
import re

from ..creative_modeling_generation import _json_content


MODEL = os.getenv("CREATIVE_STUDIO_PROMPT_MODEL", "openai/gpt-5-nano")
VERSION = "studio-prompt-v1"
_SYSTEM = """You are the prompt compiler for a professional image studio.
Convert the user's operational request into concise, unambiguous technical English for an image model.

Hard rules:
- Preserve the user's intent. Never add people, objects, brands, claims, prices, dates, times, places, colors, styles, copy or offers.
- Keep every protected literal byte-for-byte identical, including accents, capitalization and punctuation.
- Any copy that must appear inside the image remains in its original language and is quoted as literal visible text.
- Names and identities in reference images are immutable unless the user explicitly asks to replace them.
- For an edit, state what changes and explicitly preserve everything else.
- Do not turn an edit into a redesign. Do not improve facts or spelling inside protected literals.
- Return JSON only: {"optimized_prompt":"...","detected_language":"...","preserved_literals":["..."]}.
"""


def _content(response):
    raw = response.get("message", {}).get("content") if isinstance(response, dict) else response
    if isinstance(raw, dict):
        return raw
    try:
        return _json_content(raw)
    except Exception:
        return json.loads(str(raw or "{}"))


def protected_literals(text):
    """Return high-risk fragments that a translation must not rewrite."""
    source = str(text or "")
    patterns = (
        r'"[^"\n]+"|“[^”\n]+”|\'[^\'\n]+\'',
        r"R\$\s*\d[\d.,]*|\b\d{1,2}[:h]\d{0,2}\b|\b\d[\d.,:%xX/.-]*\b",
        r"\b[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ-]+(?:\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wÀ-ÿ-]+)+\b",
        r"\b[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{2,}(?:\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9]{2,})*\b",
    )
    values = []
    for pattern in patterns:
        for match in re.findall(pattern, source):
            value = str(match).strip()
            if value and value not in values:
                values.append(value)
    return values


def optimize_prompt(prompt, *, mode="create", context=None, text_callable=None):
    original = str(prompt or "").strip()[:12000]
    if not original:
        raise ValueError("Descreva o que deseja criar ou editar.")
    literals = protected_literals(original)
    fallback = {
        "original_prompt": original,
        "optimized_prompt": original,
        "detected_language": "pt-BR",
        "preserved_literals": literals,
        "optimized": False,
        "version": VERSION,
    }
    if not callable(text_callable):
        return fallback
    payload = {
        "mode": "edit" if str(mode).lower() == "edit" else "create",
        "source_request": original,
        "protected_literals": literals,
        "context": context if isinstance(context, dict) else {},
    }
    try:
        response = text_callable(
            [{"role": "system", "content": _SYSTEM},
             {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            model=MODEL, max_tokens=900, temperature=0,
            response_format={"type": "json_object"}, reasoning={"effort": "low"},
        )
        content = _content(response) or {}
        optimized = str(content.get("optimized_prompt") or "").strip()[:20000]
        language = str(content.get("detected_language") or "pt-BR").strip()[:16]
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return fallback
    if not optimized or any(literal not in optimized for literal in literals):
        return fallback
    return {
        **fallback,
        "optimized_prompt": optimized,
        "detected_language": language or "pt-BR",
        "preserved_literals": literals,
        "optimized": optimized != original,
    }
