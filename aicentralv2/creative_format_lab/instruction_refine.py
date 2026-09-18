"""Conservative instruction cleanup for Studio image edits.

The user's original request always remains the source of truth. The model may
only organize it; it is never allowed to introduce creative content.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata

from ..creative_modeling_generation import _json_content


INSTRUCTION_MODEL = os.getenv("CREATIVE_FORMAT_INSTRUCTION_MODEL", "openai/gpt-5-nano")
_SYSTEM = """Você organiza instruções de edição de imagem em português do Brasil.
Não crie, sugira ou complete marcas, objetos, pessoas, textos, números, preços,
cores, estilos, formatos ou ofertas que não estejam no pedido. Não corrija nomes
próprios. Preserve literalmente todo texto entre aspas, marcas, números, moedas,
percentuais e medidas. Apenas melhore pontuação e ordem; remova ambiguidades sem
adivinhar. Se faltar informação, mantenha a lacuna. Responda somente JSON:
{"instruction":"..."}."""


def _content(response):
    raw = response.get("message", {}).get("content") if isinstance(response, dict) else response
    if isinstance(raw, dict):
        return raw
    try:
        return _json_content(raw)
    except Exception:
        return json.loads(str(raw or "{}"))


def _protected_literals(text):
    return set(re.findall(r'"[^"]+"|“[^”]+”|R\$\s*\d[\d.,]*|\b\d[\d.,:%xX/-]*\b', text or ""))


_HARMLESS_LINK_WORDS = {
    "a", "as", "com", "da", "das", "de", "do", "dos", "e", "em",
    "na", "nas", "no", "nos", "o", "os", "para", "por", "que", "sem",
    "um", "uma",
}


def _words(text):
    normalized = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return set(re.findall(r"[a-z0-9]+", normalized.lower()))


def refine_edit_instruction(instruction, *, text_callable=None):
    original = str(instruction or "").strip()
    if not original or not callable(text_callable):
        return {"original_instruction": original, "refined_instruction": original, "refined": False}
    try:
        response = text_callable(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": original}],
            model=INSTRUCTION_MODEL,
            max_tokens=320,
            temperature=0,
            response_format={"type": "json_object"},
            reasoning={"effort": "low"},
        )
        refined = str((_content(response) or {}).get("instruction") or "").strip()
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        refined = ""
    # A missing literal is evidence that the cleanup changed the request.
    original_words = _words(original)
    refined_words = _words(refined)
    if (
        not refined
        or not _protected_literals(original).issubset(_protected_literals(refined))
        or not original_words.issubset(refined_words)
        or not (refined_words - original_words).issubset(_HARMLESS_LINK_WORDS)
    ):
        refined = original
    return {
        "original_instruction": original,
        "refined_instruction": refined,
        "refined": refined != original,
    }
