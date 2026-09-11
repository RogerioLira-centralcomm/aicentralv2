"""Troca rápida: uma referência + GPT Image 2. Sem roteiro de 15s."""

from __future__ import annotations

import base64
import json
import os

from ..creative_modeling_fx import annotate_cost
from ..creative_modeling_generation import _json_content

SWAP_MODEL = "openai/gpt-image-2"
SWAP_READ_MODEL = os.getenv("CREATIVE_FORMAT_SWAP_READ_MODEL", "openai/gpt-4o-mini")
SWAP_ESTIMATE_USD = 0.22
SWAP_DRAFT_ESTIMATE_USD = 0.14

OUTPUT_FORMATS = (
    {
        "key": "ctv",
        "label": "CTV / TV",
        "aspect_ratio": "16:9",
        "hint": "YouTube e TV horizontal",
    },
    {
        "key": "mobile",
        "label": "Stories / Reels",
        "aspect_ratio": "9:16",
        "hint": "Vertical no celular",
    },
    {
        "key": "feed",
        "label": "Feed",
        "aspect_ratio": "4:5",
        "hint": "Instagram e Facebook",
    },
    {
        "key": "square",
        "label": "Quadrado",
        "aspect_ratio": "1:1",
        "hint": "Feed 1:1",
    },
)

ANALYSIS_KEYS = (
    "background",
    "images",
    "graphic",
    "logo",
    "headline",
    "secondary",
    "cta",
    "supports",
)

PRESERVE_LABELS = {
    "layout": "layout",
    "background": "background",
    "people": "people",
    "product": "product",
    "logo": "logo",
    "text_position": "text placement",
    "colors": "colors",
    "graphic": "graphic devices",
    "style": "visual style",
}

ALTER_LABELS = {
    "price": "price",
    "cta": "CTA",
    "headline": "headline",
    "secondary": "secondary text",
    "people": "people",
    "product": "product",
    "background": "background",
    "colors": "colors",
    "graphic": "graphic devices",
}

_ROLE_TO_ANALYSIS = {
    "background": "background",
    "person": "images",
    "product": "images",
    "logo": "logo",
    "headline": "headline",
    "support": "secondary",
    "cta": "cta",
    "price": "supports",
    "graphic": "graphic",
}

READ_SYSTEM = """Você lê um still de anúncio. Extraia só o que está visível.
Não invente oferta, preço ou slogan. Copy em português do Brasil exatamente como aparece.
Se um texto estiver ilegível, deixe vazio. Retorne JSON puro:
{
  "headline": "",
  "support": "",
  "subtitle": "",
  "price": "",
  "cta": "",
  "disclaimer": "",
  "logo_text": "",
  "aspect_hint": "16:9",
  "style": "iluminação, fundo e materiais — sem sugerir efeito novo",
  "elements": [
    {"role": "logo", "text": "", "note": "onde está e o que o humano pode editar"}
  ],
  "analysis": {
    "background": true,
    "images": true,
    "graphic": false,
    "logo": true,
    "headline": true,
    "secondary": true,
    "cta": true,
    "supports": false
  }
}
roles válidos: logo, headline, support, cta, product, price, person, background, graphic.
analysis marca o que está visível. aspect_hint é 16:9, 9:16, 4:5 ou 1:1."""


def quote_swap(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    quality = _quality(payload)
    estimate = SWAP_DRAFT_ESTIMATE_USD if quality == "draft" else SWAP_ESTIMATE_USD
    return annotate_cost({
        "estimated_cost_usd": estimate,
        "model": SWAP_MODEL,
        "passes": 1,
        "quality": quality,
        "later": {"image": True, "video": False},
        "output_formats": list(OUTPUT_FORMATS),
    })


def match_aspect_ratio(value):
    raw = str(value or "").strip()
    for item in OUTPUT_FORMATS:
        if raw in {item["key"], item["aspect_ratio"]}:
            return item["aspect_ratio"]
    return ""


def resolve_aspect_ratio(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    return match_aspect_ratio(payload.get("aspect_ratio") or payload.get("output")) or "16:9"


def swap_logo_url(payload=None, brand=None):
    payload = payload if isinstance(payload, dict) else {}
    brand = brand if isinstance(brand, dict) else {}
    for value in (payload.get("logo_url"), brand.get("logo_url")):
        if isinstance(value, str) and value.startswith(("https://", "http://", "data:image/")):
            return value
    return ""


def swap_input_references(payload=None, brand=None):
    refs = []
    reference = _reference(payload)
    if reference:
        refs.append(reference)
    if _quality(payload) == "production" or payload.get("use_brand_context") is not False:
        logo = swap_logo_url(payload, brand)
        if logo and logo not in refs:
            refs.append(logo)
    return refs[:2]


def build_optimized_prompt(payload=None, brand=None):
    payload = payload if isinstance(payload, dict) else {}
    brand = brand if isinstance(brand, dict) else {}
    override = str(payload.get("prompt_override") or "").strip()
    if override:
        return override[:4000]
    name = str(payload.get("brand_name") or brand.get("name") or "").strip()
    headline = str(payload.get("headline") or "").strip()
    support = str(payload.get("support") or "").strip()
    subtitle = str(payload.get("subtitle") or "").strip()
    price = str(payload.get("price") or "").strip()
    cta = str(payload.get("cta") or "").strip()
    note = str(payload.get("note") or payload.get("message") or payload.get("instruction") or "").strip()
    color = str(
        payload.get("color")
        or brand.get("primary_color")
        or ""
    ).strip()
    has_logo = bool(swap_logo_url(payload, brand))
    quality = _quality(payload)
    use_brand = payload.get("use_brand_context") is not False
    preserve = _token_list(payload.get("preserve"), PRESERVE_LABELS)
    alter = _token_list(payload.get("alter"), ALTER_LABELS)
    lines = [
        "Edit the attached advertising reference. Keep the same composition, crop, hierarchy and number of frames.",
        "Swap only the advertised brand, product and copy. Do not redesign the layout.",
        "All visible text must be Brazilian Portuguese.",
        "Spell every visible line exactly as written below. Do not scramble, hyphenate, invent or auto-correct Portuguese.",
        "Do not invent a new visual effect: no neon light trails, sci-fi streaks, extra glow, lens flares or futuristic overlays that are not in the reference.",
        "Keep the original lighting, color grade, materials and photography. Do not add a new light ribbon or energy streak.",
        "Do not add player chrome, app UI or extra frames that are not in the reference.",
    ]
    if quality == "draft":
        lines.append("This is a draft preview. Prefer a clear, fast interpretation over extra micro-detail.")
    else:
        lines.append("This is a production render. Preserve brand fidelity, sharpness and exact copy.")
    aspect = resolve_aspect_ratio(payload)
    if aspect:
        lines.append(f"Output aspect ratio {aspect}. Recrop and rebalance composition for that frame.")
    if preserve:
        lines.append("Preserve exactly: " + ", ".join(PRESERVE_LABELS[item] for item in preserve) + ".")
    if alter:
        lines.append("Change only: " + ", ".join(ALTER_LABELS[item] for item in alter) + ".")
    if use_brand and name:
        lines.append(f"New brand: {name}.")
    if use_brand and color:
        lines.append(f"Brand color: {color}.")
    if use_brand and has_logo:
        lines.append(
            "Image 2 is the official brand logo lockup. Place that exact mark where the old logo sat."
        )
        lines.append(
            "Do not typeset the legal company name as a substitute for the official logo."
        )
    elif use_brand and name:
        lines.append(
            f"Use the official {name} logo mark, not the spelled-out legal company name."
        )
    if use_brand:
        instruction = str((brand.get("creative_line") or {}).get("gpt_image_instruction") or "").strip()
        if instruction:
            lines.append(instruction[:280])
        tone = str(brand.get("tone_of_voice") or "").strip()
        if tone:
            lines.append(f"Brand tone: {tone[:160]}.")
        for item in (brand.get("forbidden_elements") or [])[:4]:
            text = str(item).strip()
            if text:
                lines.append(f"Do not add: {text}.")
    if headline:
        lines.append(f"Headline exactly: {headline}")
    if support:
        lines.append(f"Support exactly: {support}")
    if subtitle:
        lines.append(f"Subtitle exactly: {subtitle}")
    if price:
        lines.append(f"Price exactly: {price}")
    if cta:
        lines.append(f"CTA exactly: {cta}")
    if not (headline or support or cta or price):
        lines.append("Keep the original copy unless the note asks to change a brand name.")
    if note:
        lines.append(note)
    return " ".join(lines)


def build_swap_prompt(payload=None, brand=None):
    return build_optimized_prompt(payload, brand)


def build_prompt_preview_pt(payload=None, brand=None):
    payload = payload if isinstance(payload, dict) else {}
    brand = brand if isinstance(brand, dict) else {}
    name = str(payload.get("brand_name") or brand.get("name") or "").strip()
    headline = str(payload.get("headline") or "").strip()
    support = str(payload.get("support") or "").strip()
    price = str(payload.get("price") or "").strip()
    cta = str(payload.get("cta") or "").strip()
    note = str(payload.get("note") or payload.get("instruction") or "").strip()
    preserve = _token_list(payload.get("preserve"), PRESERVE_LABELS)
    alter = _token_list(payload.get("alter"), ALTER_LABELS)
    quality = _quality(payload)
    aspect = resolve_aspect_ratio(payload)
    parts = []
    if name:
        parts.append(f"Edite o criativo preservando a identidade visual da marca {name}.")
    else:
        parts.append("Edite o criativo preservando a identidade visual, a oferta e a composição geral.")
    if preserve:
        labels = {
            "layout": "layout",
            "background": "fundo",
            "people": "pessoas",
            "product": "produto",
            "logo": "logo",
            "text_position": "posicionamento dos textos",
            "colors": "cores",
            "graphic": "grafismo",
            "style": "estilo visual",
        }
        parts.append("Preserve " + ", ".join(labels[item] for item in preserve) + ".")
    if alter:
        labels = {
            "price": "preço",
            "cta": "CTA",
            "headline": "headline",
            "secondary": "texto secundário",
            "people": "pessoas",
            "product": "produto",
            "background": "fundo",
            "colors": "cores",
            "graphic": "grafismo",
        }
        parts.append("Altere " + ", ".join(labels[item] for item in alter) + ".")
    if headline:
        parts.append(f"Headline: '{headline}'.")
    if support:
        parts.append(f"Apoio: '{support}'.")
    if price:
        parts.append(f"Destaque o bloco de preço '{price}'.")
    if cta:
        parts.append(f"CTA: '{cta}'.")
    if note:
        parts.append(note)
    parts.append(f"Formato de saída {aspect}.")
    parts.append("Rascunho de validação." if quality == "draft" else "Versão de produção, alta fidelidade.")
    return " ".join(parts)


def preview_swap_prompt(payload=None, brand=None):
    prompt = build_optimized_prompt(payload, brand)
    return {
        "prompt": prompt,
        "preview": build_prompt_preview_pt(payload, brand),
        "quality": _quality(payload),
        "aspect_ratio": resolve_aspect_ratio(payload),
        "quote": quote_swap(payload),
    }


def read_swap_reference(payload=None, *, text_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    reference = _reference(payload)
    if not reference:
        raise ValueError("Envie uma imagem de referência.")
    empty = _empty_read()
    if text_callable is None:
        return empty
    response = text_callable(
        [
            {"role": "system", "content": READ_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Leia os elementos editáveis deste still."},
                    {"type": "image_url", "image_url": {"url": reference}},
                ],
            },
        ],
        model=SWAP_READ_MODEL,
        max_tokens=700,
        temperature=0.1,
    )
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = _json_content(raw)
        except Exception:
            try:
                parsed = json.loads(str(raw))
            except Exception:
                return empty
    if not isinstance(parsed, dict):
        return empty
    elements = []
    for item in parsed.get("elements") or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if not role:
            continue
        elements.append({
            "role": role[:24],
            "text": str(item.get("text") or "").strip()[:120],
            "note": str(item.get("note") or "").strip()[:160],
        })
        if len(elements) >= 12:
            break
    aspect_hint = match_aspect_ratio(parsed.get("aspect_hint"))
    return {
        "headline": str(parsed.get("headline") or "").strip()[:80],
        "support": str(parsed.get("support") or "").strip()[:160],
        "subtitle": str(parsed.get("subtitle") or "").strip()[:80],
        "price": str(parsed.get("price") or "").strip()[:40],
        "cta": str(parsed.get("cta") or "").strip()[:40],
        "disclaimer": str(parsed.get("disclaimer") or "").strip()[:160],
        "logo_text": str(parsed.get("logo_text") or "").strip()[:40],
        "aspect_hint": aspect_hint,
        "style": str(parsed.get("style") or "").strip()[:200],
        "elements": elements,
        "analysis": _analysis_from_read(parsed, elements),
    }


def swap_reference(payload=None, *, brand=None, image_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    refs = swap_input_references(payload, brand)
    if not refs:
        raise ValueError("Envie uma imagem de referência.")
    if image_callable is None:
        raise ValueError("Gerador de imagem indisponível.")
    prompt = build_optimized_prompt(payload, brand)
    aspect_ratio = resolve_aspect_ratio(payload)
    quality = _quality(payload)
    result = image_callable(
        prompt,
        input_references=refs,
        aspect_ratio=aspect_ratio,
        background="opaque",
    )
    png = _png_bytes(result)
    if not png:
        raise ValueError("O GPT Image 2 não devolveu o still.")
    return {
        "prompt": prompt,
        "preview": build_prompt_preview_pt(payload, brand),
        "reference": refs[0][:80],
        "logo_used": len(refs) > 1,
        "aspect_ratio": aspect_ratio,
        "quality": quality,
        "model": SWAP_MODEL,
        "png_data_url": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
        "quote": quote_swap(payload),
    }


def _empty_read():
    return {
        "headline": "",
        "support": "",
        "subtitle": "",
        "price": "",
        "cta": "",
        "disclaimer": "",
        "logo_text": "",
        "aspect_hint": "",
        "style": "",
        "elements": [],
        "analysis": {key: False for key in ANALYSIS_KEYS},
    }


def _analysis_from_read(parsed, elements):
    raw = parsed.get("analysis") if isinstance(parsed.get("analysis"), dict) else {}
    present = {}
    for item in elements:
        mapped = _ROLE_TO_ANALYSIS.get(item.get("role"))
        if mapped:
            present[mapped] = True
    if parsed.get("headline"):
        present["headline"] = True
    if parsed.get("support") or parsed.get("subtitle"):
        present["secondary"] = True
    if parsed.get("cta"):
        present["cta"] = True
    if parsed.get("price") or parsed.get("disclaimer"):
        present["supports"] = True
    result = {}
    for key in ANALYSIS_KEYS:
        flagged = raw.get(key)
        if flagged is True or flagged is False:
            result[key] = bool(flagged)
        else:
            result[key] = bool(present.get(key))
    return result


def _quality(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    raw = str(payload.get("quality") or "production").strip().lower()
    if raw in {"draft", "rascunho"}:
        return "draft"
    return "production"


def _token_list(value, allowed):
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple)):
        items = value
    else:
        items = []
    seen = []
    for item in items:
        key = str(item or "").strip().lower()
        if key in allowed and key not in seen:
            seen.append(key)
    return seen


def _reference(payload):
    payload = payload if isinstance(payload, dict) else {}
    for key in ("reference", "image", "reference_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith(("https://", "http://", "data:image/")):
            return value
    return ""


def _png_bytes(result):
    if isinstance(result, (bytes, bytearray)):
        return bytes(result)
    if not isinstance(result, dict):
        return b""
    raw = result.get("b64_json") or ""
    if raw:
        return base64.b64decode(raw)
    url = result.get("png_data_url") or ""
    if url.startswith("data:image") and "," in url:
        return base64.b64decode(url.split(",", 1)[-1])
    return b""
