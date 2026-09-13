"""Refino em 3 versões (rascunho → crítica → final) com early-exit."""

from __future__ import annotations

import json
import logging

from ..creative_modeling_generation import OpenRouterError, _json_content
from .lab_models import JSON_OBJECT

logger = logging.getLogger(__name__)

SCRIPT_MODEL = "openai/gpt-5-nano"
SCRIPT_V1_TEMPERATURE = 0.2
SCRIPT_V2_TEMPERATURE = 0.0
SCRIPT_V3_TEMPERATURE = 0.1
SCRIPT_V1_MAX_TOKENS = 1800
SCRIPT_V2_MAX_TOKENS = 1200
SCRIPT_V3_MAX_TOKENS = 1800
IMAGE_PROMPT_MAX_TOKENS = 500

SCRIPT_V1_SYSTEM = """Você escreve o storyboard de um anúncio em JSON.
Cenas é um array de 4 ou 6 objetos: id scene_01..scene_0N, purpose, headline, support, cta, set_note.
Copy em português do Brasil. Sem headline genérica (conheça, saiba mais, sua história).
CTA curto, verboso, da marca. Não invente preço nem oferta que não veio no input.
purpose da sequência 4: brand, product, lifestyle, cta.
purpose da sequência 6: brand, product, lifestyle, proof, experience, cta.
Responda só com JSON: {"storyboard":[]}."""

SCRIPT_V2_SYSTEM = """Você recebe um storyboard de anúncio em JSON. Aponte no máximo 3 problemas reais (não invente problema para preencher). Depois reescreva o storyboard[] inteiro corrigindo só esses problemas, mantendo purpose, cta e set_note estáveis quando já estiverem corretos. Checklist: clareza do CTA, redundância headline/support, aderência a target_audience/ad_segments, tom de voz. Responda só com JSON: {"problems":[],"storyboard":[]}. Sem texto fora do JSON."""

SCRIPT_V3_SYSTEM = """Você funde o rascunho e a crítica num storyboard final único.
Sem comentário de processo. Sem problems[]. Só o array pronto.
Mantenha purpose e o número de cenas. Copy em português do Brasil.
Responda só com JSON: {"storyboard":[]}."""

IMAGE_V1_SYSTEM = """Escreva um prompt em inglês para gerar UMA foto de publicidade sem texto.
Sem logo, sem tipografia, sem UI, sem neon inventado.
Inclua elenco (1/2/família/trabalho), faixa etária, pose e paleta hex da marca.
Responda só JSON: {"prompt":"..."}."""

IMAGE_V2_SYSTEM = """Você recebe um prompt de imagem. Aponte no máximo 3 riscos reais: pose ambígua, texto/logo no raster, paleta contraditória, enquadramento errado para o formato (feed/story/CTV). Reescreva o prompt corrigindo só isso. JSON: {"problems":[],"prompt":"..."}."""

IMAGE_V3_SYSTEM = """Prompt final em inglês. Sempre termine com: no text, no logo, no typography in the image. Brand palette: {ink}/{accent}. JSON: {"prompt":"..."}."""


def _chat(text_callable, system, user, *, temperature, max_tokens):
    if text_callable is None:
        return None
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": user if isinstance(user, str) else json.dumps(user, ensure_ascii=False),
        },
    ]
    kwargs = {
        "model": SCRIPT_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": JSON_OBJECT,
        "reasoning": {"effort": "low"},
    }
    try:
        response = text_callable(messages, **kwargs)
    except TypeError:
        kwargs.pop("reasoning", None)
        try:
            response = text_callable(messages, **kwargs)
        except TypeError:
            kwargs.pop("response_format", None)
            response = text_callable(messages, **kwargs)
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if isinstance(raw, dict):
        return raw
    try:
        return _json_content(raw)
    except Exception:
        try:
            parsed = json.loads(str(raw or ""))
        except Exception as exc:
            raise OpenRouterError("O provedor não devolveu JSON.") from exc
        if not isinstance(parsed, dict):
            raise OpenRouterError("O provedor não devolveu JSON.")
        return parsed


def _storyboard(data):
    rows = (data or {}).get("storyboard") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [item for item in rows if isinstance(item, dict)]


def _problems(data):
    rows = (data or {}).get("problems") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [str(item).strip() for item in rows if str(item).strip()][:3]


def refine_script(v1_storyboard, *, text_callable, brand=None, draft_payload=None):
    """v1 já veio; crítica v2; early-exit se não houver problemas; senão funde v3."""
    v1 = list(v1_storyboard or [])
    packed = {
        "v1": {"storyboard": v1},
        "v2": {"problems": [], "storyboard": v1},
        "v3": {"storyboard": v1},
        "selected": "v3",
        "early_exit": False,
    }
    if text_callable is None:
        return packed
    try:
        critique = _chat(
            text_callable,
            SCRIPT_V2_SYSTEM,
            {"storyboard": v1, "brand": brand or {}, "draft": draft_payload or {}},
            temperature=SCRIPT_V2_TEMPERATURE,
            max_tokens=SCRIPT_V2_MAX_TOKENS,
        )
    except OpenRouterError:
        logger.exception("Crítica do roteiro falhou; segue v1.")
        return packed
    problems = _problems(critique)
    rewritten = _storyboard(critique) or v1
    packed["v2"] = {"problems": problems, "storyboard": rewritten}
    if not problems:
        packed["v3"] = {"storyboard": rewritten}
        packed["early_exit"] = True
        return packed
    try:
        final = _chat(
            text_callable,
            SCRIPT_V3_SYSTEM,
            {"v1": v1, "v2_problems": problems, "v2_storyboard": rewritten, "brand": brand or {}},
            temperature=SCRIPT_V3_TEMPERATURE,
            max_tokens=SCRIPT_V3_MAX_TOKENS,
        )
        fused = _storyboard(final) or rewritten
    except OpenRouterError:
        logger.exception("Fusão do roteiro falhou; segue v2.")
        fused = rewritten
    packed["v3"] = {"storyboard": fused}
    return packed


def draft_script(*, text_callable, payload):
    if text_callable is None:
        return []
    raw = _chat(
        text_callable,
        SCRIPT_V1_SYSTEM,
        payload,
        temperature=SCRIPT_V1_TEMPERATURE,
        max_tokens=SCRIPT_V1_MAX_TOKENS,
    )
    return _storyboard(raw)


def refine_image_prompt(v1_prompt, *, text_callable, constraints=None):
    constraints = constraints if isinstance(constraints, dict) else {}
    ink = str(constraints.get("ink") or constraints.get("primary_color") or "").strip()
    accent = str(constraints.get("accent") or constraints.get("secondary_color") or "").strip()
    v1 = str(v1_prompt or "").strip()
    packed = {
        "v1": {"prompt": v1},
        "v2": {"problems": [], "prompt": v1},
        "v3": {"prompt": v1},
        "selected": "v3",
        "early_exit": False,
    }
    if text_callable is None or not v1:
        return packed
    try:
        critique = _chat(
            text_callable,
            IMAGE_V2_SYSTEM,
            {"prompt": v1, "constraints": constraints},
            temperature=SCRIPT_V2_TEMPERATURE,
            max_tokens=IMAGE_PROMPT_MAX_TOKENS,
        )
    except OpenRouterError:
        logger.exception("Crítica do prompt de imagem falhou; segue v1.")
        return packed
    problems = _problems(critique)
    rewritten = str((critique or {}).get("prompt") or v1).strip() or v1
    packed["v2"] = {"problems": problems, "prompt": rewritten}
    if not problems:
        packed["v3"] = {"prompt": rewritten}
        packed["early_exit"] = True
        return packed
    system = IMAGE_V3_SYSTEM.format(ink=ink or "brand ink", accent=accent or "brand accent")
    try:
        final = _chat(
            text_callable,
            system,
            {"v1": v1, "v2_problems": problems, "v2_prompt": rewritten, "constraints": constraints},
            temperature=SCRIPT_V3_TEMPERATURE,
            max_tokens=IMAGE_PROMPT_MAX_TOKENS,
        )
        fused = str((final or {}).get("prompt") or rewritten).strip() or rewritten
    except OpenRouterError:
        logger.exception("Fusão do prompt de imagem falhou; segue v2.")
        fused = rewritten
    if "no text" not in fused.lower():
        fused = f"{fused} no text, no logo, no typography in the image. Brand palette: {ink}/{accent}."
    packed["v3"] = {"prompt": fused}
    return packed


def draft_image_prompt(*, text_callable, knobs):
    if text_callable is None:
        return _fallback_image_prompt(knobs)
    raw = _chat(
        text_callable,
        IMAGE_V1_SYSTEM,
        knobs,
        temperature=SCRIPT_V1_TEMPERATURE,
        max_tokens=IMAGE_PROMPT_MAX_TOKENS,
    )
    prompt = str((raw or {}).get("prompt") or "").strip()
    return prompt or _fallback_image_prompt(knobs)


def _fallback_image_prompt(knobs):
    knobs = knobs if isinstance(knobs, dict) else {}
    kind = knobs.get("kind") or "cast"
    cast = knobs.get("elenco") or "1 pessoa"
    age = knobs.get("idade") or "25-34"
    palette = knobs.get("palette") or []
    hexes = ", ".join(str(item) for item in palette[:4] if item)
    if kind == "ground":
        return (
            f"Empty advertising background, brand color field {hexes}, soft wash, "
            "no people, no text, no logo, no typography in the image."
        )
    return (
        f"Photoreal advertising portrait, {cast}, age {age}, natural light, "
        f"wardrobe in {hexes or 'brand colors'}, 16:9, no text, no logo, "
        "no typography in the image."
    )
