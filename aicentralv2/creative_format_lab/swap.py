"""Troca rápida: uma referência + GPT Image 2. Sem roteiro de 15s."""

from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path

from ..creative_modeling_fx import annotate_cost
from ..creative_modeling_generation import _json_content

SWAP_MODEL = "openai/gpt-image-2"
SWAP_READ_MODEL = os.getenv("CREATIVE_FORMAT_SWAP_READ_MODEL", "openai/gpt-4o-mini")
SWAP_READ_TEMPERATURE = float(os.getenv("CREATIVE_FORMAT_SWAP_READ_TEMPERATURE", "0") or 0)
SWAP_READ_MAX_TOKENS = int(os.getenv("CREATIVE_FORMAT_SWAP_READ_MAX_TOKENS", "1200") or 1200)
SWAP_ESTIMATE_USD = 0.22
SWAP_DRAFT_ESTIMATE_USD = 0.14
TYPE_ONLY = {"headline", "secondary", "cta", "price"}
TYPESET_SLOTS = {
    "1:1": {
        "headline": (0.04, 0.04, 0.50, 0.26),
        "secondary": (0.76, 0.27, 0.23, 0.14),
        "dates": (0.56, 0.06, 0.40, 0.28),
        "cta": (0.18, 0.84, 0.64, 0.10),
        "price": (0.18, 0.72, 0.40, 0.10),
    },
    "4:5": {
        "headline": (0.07, 0.58, 0.86, 0.14),
        "secondary": (0.07, 0.74, 0.86, 0.08),
        "cta": (0.12, 0.86, 0.76, 0.07),
        "price": (0.12, 0.52, 0.36, 0.08),
    },
    "9:16": {
        "headline": (0.05, 0.085, 0.70, 0.155),
        "secondary": (0.05, 0.27, 0.40, 0.14),
        "dates": (0.05, 0.27, 0.40, 0.14),
        "price": (0.04, 0.395, 0.40, 0.155),
        "cta": (0.58, 0.90, 0.28, 0.055),
    },
    "16:9": {
        "headline": (0.40, 0.14, 0.36, 0.34),
        "secondary": (0.40, 0.52, 0.34, 0.16),
        "cta": (0.76, 0.34, 0.20, 0.28),
        "price": (0.40, 0.70, 0.30, 0.10),
    },
}
TYPESET_SLOTS_TOP = {
    "9:16": {
        "headline": (0.05, 0.08, 0.90, 0.20),
        "secondary": (0.05, 0.28, 0.50, 0.16),
        "dates": (0.05, 0.28, 0.50, 0.16),
        "price": (0.05, 0.42, 0.48, 0.13),
        "cta": (0.06, 0.88, 0.88, 0.09),
    },
    "16:9": {
        "headline": (0.04, 0.10, 0.50, 0.28),
        "secondary": (0.04, 0.40, 0.22, 0.22),
        "dates": (0.50, 0.08, 0.28, 0.20),
        "price": (0.16, 0.40, 0.26, 0.20),
        "cta": (0.04, 0.78, 0.40, 0.14),
    },
    "1:1": TYPESET_SLOTS["1:1"],
    "4:5": TYPESET_SLOTS["4:5"],
}

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
Não invente oferta, preço, nome ou slogan. Copy em português do Brasil exatamente como aparece, com acento.
Cartela de evento: cada selo de nome é um element role=person. Datas vão em dates. Local vai em venue.
O grito da peça (É de graça, Entrada franca, etc.) vai em support ou cta — nunca some.
Bandeirola, fitas ou padrão repetido = graphic true.
style descreve o que se vê (cor do campo, luz, recorte). Nunca repita estas instruções.
Se um texto estiver ilegível, deixe vazio. Não corrija português. Retorne JSON puro:
{
  "headline": "",
  "support": "",
  "subtitle": "",
  "price": "",
  "cta": "",
  "disclaimer": "",
  "logo_text": "",
  "dates": "",
  "venue": "",
  "aspect_hint": "1:1",
  "style": "fundo azul, pessoa à direita, tipo à esquerda",
  "elements": [
    {"role": "person", "text": "nome no selo", "note": "onde está"}
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
analysis marca o que está visível. aspect_hint é 16:9, 9:16, 4:5 ou 1:1. Print de celular não muda o aspect da peça."""

READ_STRICT_SYSTEM = (
    READ_SYSTEM
    + "\nVALIDAÇÃO: transcreva glifo a glifo. Se o still escreveu Mumuzinho ou franceça, copie o erro."
    " Não normalize para o nome famoso nem corrija acento."
)


def quote_swap(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    if swap_mode(payload) == "typeset":
        return annotate_cost({
            "estimated_cost_usd": 0,
            "model": "typeset",
            "passes": 0,
            "quality": "typeset",
            "later": {"image": False, "video": False},
            "output_formats": list(OUTPUT_FORMATS),
        })
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
    return (
        match_aspect_ratio(
            payload.get("aspect_ratio") or payload.get("output") or payload.get("aspect_hint")
        )
        or "16:9"
    )


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
    recrop = swap_mode(payload) == "recrop"
    lines = [
        "Edit the attached advertising reference. Keep the same composition, crop, hierarchy and number of frames.",
        "All visible text must be Brazilian Portuguese.",
        "Spell every visible line exactly as written below. Do not scramble, hyphenate, invent or auto-correct Portuguese.",
        "Do not invent a new visual effect: no neon light trails, sci-fi streaks, extra glow, lens flares or futuristic overlays that are not in the reference.",
        "Keep the original lighting, color grade, materials and photography. Do not add a new light ribbon or energy streak.",
        "Do not add player chrome, app UI or extra frames that are not in the reference.",
    ]
    if recrop:
        lines = [
            "Recrop the attached advertising still to the output frame. Keep the same person, wardrobe, lighting and brand color field.",
            "Do not redesign the campaign. Do not invent a new effect, UI chrome or extra frame.",
            "A later typesetting pass will replace headline, price, quota and CTAs. Prefer a clean field behind the type.",
            "Do not invent a new offer, number or Portuguese line. If type must stay, clone it — do not add zeros to prices or quotas (199,90 not 1999,90; 1700 not 17000).",
        ]
    elif alter:
        lines.insert(
            1,
            "This is an item swap. Change only the listed items. Every other face, name pill, date, logo and graphic stays locked.",
        )
        lines.insert(2, "Do not redesign the layout.")
    else:
        lines.insert(1, "Swap only the advertised brand, product and copy. Do not redesign the layout.")
    if quality == "draft":
        lines.append("This is a draft preview. Prefer a clear, fast interpretation over extra micro-detail.")
    else:
        lines.append("This is a production render. Preserve brand fidelity, sharpness and exact copy.")
    aspect = resolve_aspect_ratio(payload)
    if aspect:
        lines.append(f"Output aspect ratio {aspect}. Recrop and rebalance composition for that frame.")
    if preserve:
        lines.append("Preserve exactly: " + ", ".join(PRESERVE_LABELS[item] for item in preserve) + ".")
    if "people" in preserve:
        lines.append(
            "Keep every face, pose, hair, garment and name-pill label exactly. Do not replace, add or drop a person."
        )
        lines.append(
            "Do not redraw name pills, dates, logos or the headline. Clone those text regions from the reference. "
            "Typeset only the lines listed under Change only."
        )
    if "graphic" in preserve:
        lines.append("Keep the repeating pennant/bunting and field pattern. Do not restyle the graphic devices.")
    if alter:
        lines.append("Change only: " + ", ".join(ALTER_LABELS[item] for item in alter) + ".")
    locks = _lock_list(payload)
    if locks:
        spelled = " | ".join(_spell_lock(item) for item in locks)
        lines.append("These strings must remain visible and correctly spelled: " + spelled + ".")
        lines.append(
            "Paint each locked string glyph by glyph. Do not double letters or add syllables "
            "(franca not franceça, Mumuzinho not Mumuzinho)."
        )
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
    if not recrop:
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
    risk = swap_risk(payload)
    mode = swap_mode(payload)
    if mode == "recrop":
        parts.append("O Image 2 só vira o formato. Preço, quota e headline entram na foto depois.")
    elif risk.get("level") == "high":
        if mode == "typeset":
            parts.append("Tipo composto na foto. Elenco e selos ficam iguais à referência.")
        else:
            parts.append(risk["reason"])
    return " ".join(parts)


def preview_swap_prompt(payload=None, brand=None):
    payload = prepare_swap(payload)
    prompt = build_optimized_prompt(payload, brand)
    mode = swap_mode(payload)
    return {
        "prompt": prompt,
        "preview": build_prompt_preview_pt(payload, brand),
        "quality": _quality(payload),
        "aspect_ratio": resolve_aspect_ratio(payload),
        "quote": quote_swap(payload),
        "risk": swap_risk(payload),
        "mode": mode,
        "locks": _lock_list(payload),
    }


def swap_risk(payload=None, read=None):
    """Cartela com muitos selos + troca de tipo = risco alto de português embaralhado."""
    payload = payload if isinstance(payload, dict) else {}
    read = read if isinstance(read, dict) else {}
    people = sum(
        1
        for item in (read.get("elements") or payload.get("elements") or [])
        if isinstance(item, dict) and item.get("role") == "person"
    )
    faces = 0
    try:
        faces = int(payload.get("faces") or 0)
    except (TypeError, ValueError):
        faces = 0
    alter = set(_token_list(payload.get("alter"), ALTER_LABELS))
    type_alter = bool(alter & {"headline", "secondary", "cta", "price"})
    if (people >= 4 or faces >= 4 or "people" in _token_list(payload.get("preserve"), PRESERVE_LABELS)) and type_alter:
        return {
            "level": "high",
            "reason": "Cartela com elenco. O Image 2 costuma embaralhar os selos. Clone o tipo da referência e só reescreva o item marcado — ou use decompose.",
        }
    return {"level": "ok", "reason": ""}


def needs_recrop(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    target = resolve_aspect_ratio(payload)
    hint = match_aspect_ratio(payload.get("aspect_hint"))
    return bool(hint and target and hint != target)


def swap_mode(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    patches = typeset_patches(payload)
    if needs_recrop(payload) and patches:
        return "recrop"
    if payload.get("force_image"):
        return "image"
    alter = set(_token_list(payload.get("alter"), ALTER_LABELS))
    if swap_risk(payload).get("level") == "high" and alter and alter <= TYPE_ONLY:
        return "typeset"
    return "image"


def prepare_swap(payload=None):
    data = dict(payload) if isinstance(payload, dict) else {}
    merged = []
    for item in locks_from_read(data) + _lock_list(data):
        if item not in merged:
            merged.append(item)
        if len(merged) >= 12:
            break
    data["locks"] = merged
    if not match_aspect_ratio(data.get("aspect_ratio") or data.get("output")):
        hint = match_aspect_ratio(data.get("aspect_hint"))
        if hint:
            data["aspect_ratio"] = hint
    if not data.get("subtitle") and data.get("dates"):
        data["subtitle"] = str(data.get("dates") or "").replace("\n", " ")[:80]
    return data


def locks_from_read(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    locks = []
    for item in payload.get("elements") or []:
        if not isinstance(item, dict):
            continue
        if item.get("role") == "person" and item.get("text"):
            locks.append(str(item["text"]).strip()[:80])
    for key in ("dates", "venue", "logo_text"):
        value = str(payload.get(key) or "").replace("\n", " ").strip()
        if value:
            locks.append(value[:80])
    return locks


def looks_scrambled(text):
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if re.search(r"(\S)\1{2,}", raw):
        return True
    folded = raw.casefold()
    tells = (
        "entradada",
        "franceça",
        "franceca",
        "graçça",
        "vaqueiroo",
        "famíliaía",
        "familiaia",
        "planoso",
        "contratator",
        "conferir plan",
    )
    return any(token in folded for token in tells)


def inflated_numbers(blob, locks=None):
    digits = re.sub(r"\D", "", str(blob or ""))
    found = []
    for lock in locks or []:
        seed = re.sub(r"\D", "", str(lock))
        if len(seed) < 3:
            continue
        if seed + "0" in digits:
            found.append(str(lock))
    return found


def read_swap_reference(payload=None, *, text_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    reference = _reference(payload)
    if not reference:
        raise ValueError("Envie uma imagem de referência.")
    empty = _empty_read()
    if text_callable is None:
        return empty
    system = READ_STRICT_SYSTEM if payload.get("strict") else READ_SYSTEM
    response = text_callable(
        [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Leia os elementos editáveis deste still."},
                    {"type": "image_url", "image_url": {"url": reference}},
                ],
            },
        ],
        model=SWAP_READ_MODEL,
        max_tokens=SWAP_READ_MAX_TOKENS,
        temperature=SWAP_READ_TEMPERATURE,
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
        if len(elements) >= 20:
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
        "dates": str(parsed.get("dates") or "").strip()[:80],
        "venue": str(parsed.get("venue") or "").strip()[:80],
        "aspect_hint": aspect_hint,
        "style": str(parsed.get("style") or "").strip()[:200],
        "elements": elements,
        "analysis": _analysis_from_read(parsed, elements),
    }


def swap_reference(payload=None, *, brand=None, image_callable=None):
    payload = prepare_swap(payload)
    refs = swap_input_references(payload, brand)
    if not refs:
        raise ValueError("Envie uma imagem de referência.")
    mode = swap_mode(payload)
    if mode == "typeset":
        return typeset_reference(payload, brand=brand)
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
    still = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    if mode == "recrop" and typeset_patches(payload):
        painted = typeset_reference(
            {
                **payload,
                "reference": still,
                "aspect_hint": aspect_ratio,
                "force_image": False,
                "typeset_all": True,
            },
            brand=brand,
        )
        painted["mode"] = "recrop"
        painted["passes"] = ["image", "typeset"]
        painted["model"] = SWAP_MODEL
        painted["quality"] = quality
        painted["prompt"] = prompt
        painted["preview"] = build_prompt_preview_pt(payload, brand)
        painted["logo_used"] = len(refs) > 1
        painted["quote"] = quote_swap(payload)
        return painted
    return {
        "prompt": prompt,
        "preview": build_prompt_preview_pt(payload, brand),
        "reference": refs[0][:80],
        "logo_used": len(refs) > 1,
        "aspect_ratio": aspect_ratio,
        "quality": quality,
        "model": SWAP_MODEL,
        "mode": "image",
        "risk": swap_risk(payload),
        "png_data_url": still,
        "quote": quote_swap({**payload, "force_image": True}),
    }


def typeset_reference(payload=None, brand=None):
    payload = prepare_swap(payload)
    reference = _reference(payload)
    raw = _png_bytes({"png_data_url": reference} if str(reference).startswith("data:image") else {})
    if not raw and str(reference).startswith("data:image") and "," in reference:
        raw = base64.b64decode(reference.split(",", 1)[-1])
    if not raw:
        raise ValueError("Envie uma imagem de referência.")
    patches = typeset_patches(payload)
    png = _paint_typeset(raw, patches, resolve_aspect_ratio(payload))
    return {
        "prompt": build_optimized_prompt(payload, brand),
        "preview": build_prompt_preview_pt(payload, brand),
        "reference": reference[:80],
        "logo_used": False,
        "aspect_ratio": resolve_aspect_ratio(payload),
        "quality": "typeset",
        "model": "typeset",
        "mode": "typeset",
        "risk": swap_risk(payload),
        "patches": patches,
        "png_data_url": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
        "quote": quote_swap(payload),
    }


def typeset_patches(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    alter = set(_token_list(payload.get("alter"), ALTER_LABELS))
    if payload.get("typeset_all") or needs_recrop(payload):
        alter = alter | {"headline", "secondary", "price"}
    rows = []
    if "headline" in alter and payload.get("headline"):
        rows.append({"slot": "headline", "text": str(payload["headline"]).strip()[:80]})
    if "secondary" in alter:
        if payload.get("support"):
            rows.append({"slot": "secondary", "text": str(payload["support"]).strip()[:80]})
        if payload.get("subtitle"):
            rows.append({"slot": "dates", "text": str(payload["subtitle"]).strip()[:80]})
    if "cta" in alter and payload.get("cta"):
        rows.append({"slot": "cta", "text": str(payload["cta"]).strip()[:40]})
    if "price" in alter and payload.get("price"):
        rows.append({"slot": "price", "text": str(payload["price"]).strip()[:40]})
    return rows


def _paint_typeset(png, patches, aspect="1:1"):
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise ValueError("Pillow é necessário para compor o tipo na foto.") from exc
    image = Image.open(io.BytesIO(png)).convert("RGB")
    slots = _slots_for(image, aspect)
    field = _canvas_field(image)
    for patch in patches:
        box = slots.get(patch["slot"])
        if not box:
            continue
        region = _locate_type(image, box, field)
        fill = (255, 255, 255) if patch["slot"] == "cta" else field
        _fill_slot(image, region["slot"], fill)
        ink = region["ink"]
        if patch["slot"] == "cta":
            ink = (17, 17, 17)
        elif patch["slot"] in {"headline", "price"} and _luma(field) < 90:
            ink = (255, 255, 255)
        elif patch["slot"] == "secondary" and _luma(field) < 90 and _luma(ink) > 180:
            ink = (227, 6, 19)
        _draw_copy(
            image,
            region["slot"],
            region["slot"],
            _stack_copy(patch["text"]),
            ink,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _slots_for(image, aspect="1:1"):
    base = TYPESET_SLOTS.get(aspect) or TYPESET_SLOTS["1:1"]
    top = TYPESET_SLOTS_TOP.get(aspect)
    if not top or aspect not in {"16:9"}:
        return base
    field = _canvas_field(image)
    upper = _ink_weight(image, (0.04, 0.04, 0.50, 0.40), field)
    lower = _ink_weight(image, (0.40, 0.55, 0.55, 0.28), field)
    return top if upper >= lower else base


def _ink_weight(image, box, field):
    width, height = image.size
    x, y, w, h = box
    left, top = max(0, int(width * x)), max(0, int(height * y))
    right = min(width, int(width * (x + w)))
    bottom = min(height, int(height * (y + h)))
    count = 0
    step = max(1, (right - left) // 48)
    for py in range(top, bottom, step):
        for px in range(left, right, step):
            pixel = image.getpixel((px, py))
            if _far_from_field(pixel, field) and _luma(pixel) > 210:
                count += 1
    return count


def _locate_type(image, slot, field):
    width, height = image.size
    x, y, w, h = slot
    left, top = max(0, int(width * x)), max(0, int(height * y))
    right = min(width, int(width * (x + w)))
    bottom = min(height, int(height * (y + h)))
    chromatic = []
    pale = []
    for py in range(top, bottom):
        for px in range(left, right):
            pixel = image.getpixel((px, py))
            if not _far_from_field(pixel, field):
                continue
            chroma = max(pixel[:3]) - min(pixel[:3])
            if chroma > 80:
                chromatic.append((px, py, pixel))
            elif _luma(pixel) > 205:
                pale.append((px, py, pixel))
    chosen = chromatic if len(chromatic) >= 40 else pale
    slot_box = (left, top, right, bottom)
    if len(chosen) < 40:
        return {
            "bbox": slot_box,
            "slot": slot_box,
            "ink": _contrast_ink(field),
            "cover": [],
        }
    xs = [item[0] for item in chosen]
    ys = [item[1] for item in chosen]
    pad = max(3, int(height * 0.006))
    return {
        "bbox": (
            max(left, min(xs) - pad),
            max(top, min(ys) - pad),
            min(right, max(xs) + pad + 1),
            min(bottom, max(ys) + pad + 1),
        ),
        "slot": slot_box,
        "ink": _ink_color([item[2] for item in chosen]),
        "cover": [(item[0], item[1]) for item in chosen],
    }


def _fill_slot(image, box, fill):
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    try:
        draw.rectangle(box, fill=fill)
    except Exception:
        pixels = image.load()
        left, top, right, bottom = box
        for py in range(top, bottom):
            for px in range(left, right):
                pixels[px, py] = fill


def _cover_type(image, points, field):
    if not points:
        return
    width, height = image.size
    pixels = image.load()
    radius = 3
    seen = set()
    for x, y in points:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                px, py = x + dx, y + dy
                if px < 0 or py < 0 or px >= width or py >= height:
                    continue
                if (px, py) in seen:
                    continue
                seen.add((px, py))
                pixels[px, py] = field


def _draw_copy(image, bbox, slot, text, ink):
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    left, right = slot[0], slot[2]
    top, bottom = bbox[1], bbox[3]
    max_width = max(12, right - left - 6)
    max_height = max(12, bottom - top + int((bottom - top) * 0.12))
    lines = max(1, text.count("\n") + 1)
    font = _fit_font(draw, text, max_width, max_height, int(max_height / lines * 0.96))
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=0, align="center")
    tw, th = box[2] - box[0], box[3] - box[1]
    tx = left + max(2, (right - left - tw) // 2)
    ty = top + max(0, (bottom - top - th) // 2)
    draw.multiline_text((tx, ty), text, font=font, fill=ink, spacing=0, align="center")


def _stack_copy(text):
    raw = str(text or "").strip()
    if not raw or "\n" in raw:
        return raw
    words = raw.split()
    if len(words) == 2:
        return "\n".join(words)
    if len(words) >= 6:
        mid = (len(words) + 1) // 2
        return " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
    return raw


def _far_from_field(pixel, field, threshold=140):
    return (
        abs(pixel[0] - field[0])
        + abs(pixel[1] - field[1])
        + abs(pixel[2] - field[2])
    ) > threshold


def _ink_color(colors):
    if not colors:
        return (255, 255, 255)
    ranked = sorted(colors, key=lambda item: max(item[:3]) - min(item[:3]), reverse=True)
    top = ranked[: max(1, len(ranked) // 5)]
    count = len(top)
    return (
        sum(item[0] for item in top) // count,
        sum(item[1] for item in top) // count,
        sum(item[2] for item in top) // count,
    )


def _contrast_ink(field):
    return (17, 17, 17) if _luma(field) > 140 else (255, 255, 255)


def _median_color(region):
    return _field_color(region)


def _canvas_field(image):
    from collections import Counter

    small = image.resize((48, 48))
    buckets = [
        ((pixel[0] // 16) * 16, (pixel[1] // 16) * 16, (pixel[2] // 16) * 16)
        for pixel in small.getdata()
    ]
    mid = [item for item in buckets if 40 < _luma(item) < 230]
    return Counter(mid or buckets).most_common(1)[0][0]


def _field_color(region):
    from collections import Counter

    small = region.resize((32, 32))
    width, height = small.size
    border = []
    for x in range(width):
        border.append(small.getpixel((x, 0)))
        border.append(small.getpixel((x, height - 1)))
    for y in range(height):
        border.append(small.getpixel((0, y)))
        border.append(small.getpixel((width - 1, y)))
    buckets = [((pixel[0] // 16) * 16, (pixel[1] // 16) * 16, (pixel[2] // 16) * 16) for pixel in border]
    return Counter(buckets).most_common(1)[0][0] if buckets else (255, 255, 255)


def _luma(color):
    red, green, blue = color[:3]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _fit_font(draw, text, max_width, max_height, start):
    size = max(14, int(start))
    font = _typeset_font(size)
    while size > 14:
        box = draw.multiline_textbbox((0, 0), text, font=font, spacing=0, align="center")
        if box[2] - box[0] <= max_width and box[3] - box[1] <= max_height:
            break
        size -= 2
        font = _typeset_font(size)
    return font


def _typeset_font(size):
    from PIL import ImageFont

    for path, index in (
        ("/System/Library/Fonts/Avenir Next Condensed.ttc", 8),
        ("/System/Library/Fonts/Avenir Next Condensed.ttc", 0),
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", None),
        ("/Library/Fonts/Arial Bold.ttf", None),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", None),
    ):
        if not Path(path).is_file():
            continue
        try:
            if index is None:
                return ImageFont.truetype(path, size)
            return ImageFont.truetype(path, size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def _empty_read():
    return {
        "headline": "",
        "support": "",
        "subtitle": "",
        "price": "",
        "cta": "",
        "disclaimer": "",
        "logo_text": "",
        "dates": "",
        "venue": "",
        "aspect_hint": "",
        "style": "",
        "elements": [],
        "analysis": {key: False for key in ANALYSIS_KEYS},
    }


def score_swap_copy(read, locks=None, forbidden=None):
    """Mede se as linhas travadas sobreviveram e se a troca apareceu."""
    read = read if isinstance(read, dict) else {}
    blob = " ".join(
        [
            str(read.get("headline") or ""),
            str(read.get("support") or ""),
            str(read.get("subtitle") or ""),
            str(read.get("cta") or ""),
            str(read.get("disclaimer") or ""),
            str(read.get("dates") or ""),
            str(read.get("venue") or ""),
            str(read.get("logo_text") or ""),
            " ".join(str(item.get("text") or "") for item in (read.get("elements") or []) if isinstance(item, dict)),
        ]
    )
    folded = blob.casefold()
    locks = [str(item).strip() for item in (locks or []) if str(item).strip()]
    forbidden = [str(item).strip() for item in (forbidden or []) if str(item).strip()]
    hits = [item for item in locks if item.casefold() in folded]
    leaks = [item for item in forbidden if item.casefold() in folded]
    inflated = inflated_numbers(blob, locks)
    total = len(locks) + len(forbidden)
    score = (len(hits) + (len(forbidden) - len(leaks))) / total if total else 0.0
    if inflated:
        score = max(0.0, score - 0.25 * len(inflated))
    return {
        "hits": hits,
        "misses": [item for item in locks if item not in hits],
        "leaks": leaks,
        "inflated": inflated,
        "accuracy": round(score, 3),
        "scrambled": looks_scrambled(blob) or bool(inflated),
        "blob": blob[:400],
    }


def _spell_lock(text):
    words = [part for part in str(text or "").split() if part]
    if not words:
        return str(text or "")
    counts = " + ".join(f"{word}={len(word)}" for word in words)
    return f"{text} ({counts})"


def _lock_list(payload):
    raw = payload.get("locks") if isinstance(payload, dict) else None
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split("|")]
    elif isinstance(raw, (list, tuple)):
        items = raw
    else:
        items = []
    seen = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.append(text[:80])
        if len(seen) >= 12:
            break
    return seen


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
    if parsed.get("price") or parsed.get("disclaimer") or parsed.get("dates"):
        present["supports"] = True
    result = {}
    for key in ANALYSIS_KEYS:
        flagged = raw.get(key)
        if present.get(key):
            result[key] = True
        elif flagged is True or flagged is False:
            result[key] = bool(flagged)
        else:
            result[key] = False
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
