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

READ_SYSTEM = """Você lê um still de anúncio. Extraia só o que está visível.
Não invente oferta, preço ou slogan. Copy em português do Brasil exatamente como aparece.
Se um texto estiver ilegível, deixe vazio. Retorne JSON puro:
{
  "headline": "",
  "support": "",
  "cta": "",
  "logo_text": "",
  "aspect_hint": "16:9",
  "style": "iluminação, fundo e materiais — sem sugerir efeito novo",
  "elements": [
    {"role": "logo", "text": "", "note": "onde está e o que o humano pode editar"}
  ]
}
roles válidos: logo, headline, support, cta, product, price, person, background.
aspect_hint é 16:9, 9:16, 4:5 ou 1:1."""


def quote_swap():
    return annotate_cost({
        "estimated_cost_usd": SWAP_ESTIMATE_USD,
        "model": SWAP_MODEL,
        "passes": 1,
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
    logo = swap_logo_url(payload, brand)
    if logo and logo not in refs:
        refs.append(logo)
    return refs[:2]


def build_swap_prompt(payload=None, brand=None):
    payload = payload if isinstance(payload, dict) else {}
    brand = brand if isinstance(brand, dict) else {}
    name = str(payload.get("brand_name") or brand.get("name") or "").strip()
    headline = str(payload.get("headline") or "").strip()
    support = str(payload.get("support") or "").strip()
    cta = str(payload.get("cta") or "").strip()
    note = str(payload.get("note") or payload.get("message") or "").strip()
    color = str(
        payload.get("color")
        or brand.get("primary_color")
        or ""
    ).strip()
    has_logo = bool(swap_logo_url(payload, brand))
    lines = [
        "Edit the attached advertising reference. Keep the same composition, crop, hierarchy and number of frames.",
        "Swap only the advertised brand, product and copy. Do not redesign the layout.",
        "All visible text must be Brazilian Portuguese.",
        "Spell every visible line exactly as written below. Do not scramble, hyphenate, invent or auto-correct Portuguese.",
        "Do not invent a new visual effect: no neon light trails, sci-fi streaks, extra glow, lens flares or futuristic overlays that are not in the reference.",
        "Keep the original lighting, color grade, materials and photography. Do not add a new light ribbon or energy streak.",
        "Do not add player chrome, app UI or extra frames that are not in the reference.",
    ]
    if name:
        lines.append(f"New brand: {name}.")
    if color:
        lines.append(f"Brand color: {color}.")
    if has_logo:
        lines.append(
            "Image 2 is the official brand logo lockup. Place that exact mark where the old logo sat."
        )
        lines.append(
            "Do not typeset the legal company name as a substitute for the official logo."
        )
    elif name:
        lines.append(
            f"Use the official {name} logo mark, not the spelled-out legal company name."
        )
    instruction = str((brand.get("creative_line") or {}).get("gpt_image_instruction") or "").strip()
    if instruction:
        lines.append(instruction[:280])
    for item in (brand.get("forbidden_elements") or [])[:4]:
        text = str(item).strip()
        if text:
            lines.append(f"Do not add: {text}.")
    if headline:
        lines.append(f"Headline exactly: {headline}")
    if support:
        lines.append(f"Support exactly: {support}")
    if cta:
        lines.append(f"CTA exactly: {cta}")
    if not (headline or support or cta):
        lines.append("Keep the original copy unless the note asks to change a brand name.")
    if note:
        lines.append(note)
    return " ".join(lines)


def read_swap_reference(payload=None, *, text_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    reference = _reference(payload)
    if not reference:
        raise ValueError("Envie uma imagem de referência.")
    empty = {
        "headline": "",
        "support": "",
        "cta": "",
        "logo_text": "",
        "aspect_hint": "",
        "style": "",
        "elements": [],
    }
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
        max_tokens=500,
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
        if len(elements) >= 8:
            break
    aspect_hint = match_aspect_ratio(parsed.get("aspect_hint"))
    return {
        "headline": str(parsed.get("headline") or "").strip()[:80],
        "support": str(parsed.get("support") or "").strip()[:160],
        "cta": str(parsed.get("cta") or "").strip()[:40],
        "logo_text": str(parsed.get("logo_text") or "").strip()[:40],
        "aspect_hint": aspect_hint,
        "style": str(parsed.get("style") or "").strip()[:200],
        "elements": elements,
    }


def swap_reference(payload=None, *, brand=None, image_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    refs = swap_input_references(payload, brand)
    if not refs:
        raise ValueError("Envie uma imagem de referência.")
    if image_callable is None:
        raise ValueError("Gerador de imagem indisponível.")
    prompt = build_swap_prompt(payload, brand)
    aspect_ratio = resolve_aspect_ratio(payload)
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
        "reference": refs[0][:80],
        "logo_used": len(refs) > 1,
        "aspect_ratio": aspect_ratio,
        "model": SWAP_MODEL,
        "png_data_url": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
        "quote": quote_swap(),
    }


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
