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
from .lab_models import JSON_OBJECT

SWAP_MODEL = "openai/gpt-image-2"
# Keep OCR on the Studio's GPT-5 family.  The old 4o-mini default often failed
# structured creative reads and made the UI fall back to manual entry.
SWAP_READ_MODEL = os.getenv("CREATIVE_FORMAT_SWAP_READ_MODEL", "openai/gpt-5-nano")
# O Studio usa a conta central do OpenRouter como rota preferencial. Quando a
# operação direta estiver configurada, OpenAI é a única rota alternativa
# permitida para OCR — nunca há leitor local, mock ou outro provedor oculto.
SWAP_READ_OPENAI_MODEL = os.getenv("CREATIVE_FORMAT_SWAP_READ_OPENAI_MODEL", "gpt-4o-mini")
SWAP_READ_TEMPERATURE = float(os.getenv("CREATIVE_FORMAT_SWAP_READ_TEMPERATURE", "0") or 0)
SWAP_READ_MAX_TOKENS = int(os.getenv("CREATIVE_FORMAT_SWAP_READ_MAX_TOKENS", "4000") or 4000)
OCR_MAX_SIDE = 1280
OCR_MAX_BYTES = 400_000
OCR_JPEG_QUALITY = 82
SWAP_ESTIMATE_USD = 0.22
SWAP_DRAFT_ESTIMATE_USD = 0.14
TYPE_ONLY = {"headline", "secondary", "cta", "price"}
SCENE_VARIANT_NOTES = {
    2: (
        "Segunda tomada da mesma campanha. Mesmo produto e mesmos textos. "
        "Mude só o ambiente e o ângulo. Serve de cena 2 para animar."
    ),
    3: (
        "Terceira tomada da mesma campanha. Mesmo produto e mesmos textos. "
        "Outro ambiente, distinto do still original. Serve de cena 3 para animar."
    ),
}
SCENE_VARIANT_PROMPT = {
    2: (
        "This is a second shot of the same campaign for later animation. "
        "Keep the exact product, logo, typography and offer. "
        "Change only the scene: new camera angle, new setting, new lighting. "
        "Do not invent a new product or rewrite the copy."
    ),
    3: (
        "This is a third shot of the same campaign for later animation. "
        "Keep the exact product, logo, typography and offer. "
        "Use a different scene from the original still. New angle, setting and light. "
        "Do not invent a new product or rewrite the copy."
    ),
}
TYPESET_MAX_PIXELS = 20_000_000
TYPESET_MAX_BYTES = 12_000_000
PATCH_ROLES = {
    "headline": "headline",
    "secondary": "support",
    "dates": "support",
    "cta": "cta",
    "price": "price",
}
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
        "headline": (0.04, 0.055, 0.92, 0.145),
        "secondary": (0.08, 0.22, 0.84, 0.10),
        "dates": (0.08, 0.22, 0.84, 0.10),
        "price": (0.08, 0.33, 0.52, 0.11),
        "cta": (0.10, 0.875, 0.80, 0.075),
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
        "headline": (0.04, 0.05, 0.92, 0.16),
        "secondary": (0.07, 0.22, 0.86, 0.11),
        "dates": (0.07, 0.22, 0.86, 0.11),
        "price": (0.07, 0.34, 0.55, 0.12),
        "cta": (0.08, 0.875, 0.84, 0.08),
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
    "logo": "brand logo",
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

READ_SYSTEM = """Você lê um still de anúncio. Leia os elementos editáveis deste still.
Extraia só o que está visível.
Não invente oferta, preço, CTA, logo, nome ou slogan. Copy em português do Brasil exatamente como aparece, com acento.
price, cta e logo_text são opcionais. A maioria das peças não tem os três. Se não aparecer, deixe vazio e marque false no analysis.
price só se houver valor em reais visível (R$ 99,90, 12x de 99,90). Sem R$, price fica vazio. Não escreva R$ 0,00.
% off, liquidação e desconto percentual vão em headline ou support — nunca em price.
Não invente Saiba mais, Compre agora, Encontre a loja nem outro CTA se não houver botão ou pill no still.
logo_text só se o wordmark estiver escrito na peça. Marca, Logo ou o nome da campanha no briefing não valem.
Além do OCR textual, faça leitura visual dos sinais de marca. Registre em visual_marks cada símbolo, ícone ou marca gráfica visível, mesmo sem texto. Para cada um informe type (icon, wordmark, logo, symbol ou graphic), description, orientation (left, right, up, down, rotated ou unknown), text (se houver), confidence de 0 a 1 e matches_reference (true, false ou null quando houver referência).
Peça de conteúdo (depoimento, B2B): nome, cargo, gráfico e a palavra custo na headline não são price.
Cartela de evento: cada selo de nome é um element role=person. Datas vão em dates. Local vai em venue.
O grito da peça (É de graça, Entrada franca, etc.) vai em support ou cta — nunca some.
Bandeirola, fitas ou padrão repetido = graphic true.
style descreve o que se vê (cor do campo, luz, recorte). Nunca repita estas instruções.
Se um texto estiver ilegível, deixe vazio. Não corrija português. Retorne JSON puro:
{
  "headline": "Frete barato nem sempre é o menor custo.",
  "support": "Atraso, retrabalho e baixa previsibilidade também pesam.",
  "subtitle": "",
  "price": "",
  "cta": "",
  "disclaimer": "",
  "logo_text": "",
  "visual_marks": [
    {"type": "icon", "description": "dois chevrons apontando para a direita", "orientation": "right", "text": "", "confidence": 0.94, "matches_reference": null}
  ],
  "dates": "",
  "venue": "",
  "aspect_hint": "9:16",
  "style": "pessoa à frente, caminhão ao fundo, tipo grande embaixo",
  "elements": [
    {"role": "person", "text": "Luciana Menezes", "note": "selo de nome"}
  ],
  "analysis": {
    "background": true,
    "images": true,
    "graphic": false,
    "logo": false,
    "headline": true,
    "secondary": true,
    "cta": false,
    "supports": false
  }
}
roles válidos: logo, headline, support, cta, product, price, person, background, graphic.
analysis marca só o que está visível. Sem preço, CTA ou logo: false. aspect_hint é 16:9, 9:16, 4:5 ou 1:1. Print de celular não muda o aspect da peça."""

READ_STRICT_SYSTEM = (
    READ_SYSTEM
    + "\nVALIDAÇÃO: transcreva glifo a glifo. Se o still escreveu Mumuzinho ou franceça, copie o erro."
    " Não normalize para o nome famoso nem corrija acento."
)


def quote_swap(payload=None):
    from ..cadu_tool_billing import estimated_credit_tokens

    payload = payload if isinstance(payload, dict) else {}
    variation_count = 2 if str(payload.get("variation_count") or "1") == "2" else 1
    if swap_mode(payload) == "typeset":
        quote = annotate_cost({
            "estimated_cost_usd": 0,
            "model": "typeset",
            "passes": 0,
            "image_credits": 0,
            "agent_tokens_estimate": 0,
            "quality": "typeset",
            "later": {"image": False, "video": False},
            "output_formats": list(OUTPUT_FORMATS),
        })
        quote["estimated_tokens"] = 0
        quote.pop("spent_brl", None)
        return quote
    quality = _quality(payload)
    estimate = (SWAP_DRAFT_ESTIMATE_USD if quality == "draft" else SWAP_ESTIMATE_USD) * variation_count
    quote = annotate_cost({
        "estimated_cost_usd": estimate,
        "model": SWAP_MODEL,
        "passes": variation_count,
        "image_credits": variation_count,
        "agent_tokens_estimate": 900,
        "quality": quality,
        "later": {"image": True, "video": False},
        "output_formats": list(OUTPUT_FORMATS),
    })
    quote["estimated_tokens"] = estimated_credit_tokens(cost_usd=estimate)
    quote.pop("spent_brl", None)
    return quote


def match_aspect_ratio(value):
    raw = str(value or "").strip()
    for item in OUTPUT_FORMATS:
        if raw in {item["key"], item["aspect_ratio"]}:
            return item["aspect_ratio"]
    return ""


def resolve_aspect_ratio(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    chosen = match_aspect_ratio(payload.get("aspect_ratio") or payload.get("output"))
    if chosen:
        return chosen
    from_px = ratio_from_size(payload.get("ref_width"), payload.get("ref_height"))
    if from_px:
        return from_px
    return match_aspect_ratio(payload.get("aspect_hint")) or "16:9"


def ratio_from_size(width, height):
    try:
        wide, tall = int(width), int(height)
    except (TypeError, ValueError):
        return ""
    if wide < 8 or tall < 8:
        return ""
    ratio = wide / tall
    if abs(ratio - 1) < 0.08:
        return "1:1"
    if ratio <= 0.75:
        return "9:16"
    if ratio < 0.92:
        return "4:5"
    return "16:9"


def swap_logo_url(payload=None, brand=None):
    payload = payload if isinstance(payload, dict) else {}
    brand = brand if isinstance(brand, dict) else {}
    for value in (payload.get("logo_url"), brand.get("logo_url")):
        if isinstance(value, str) and value.startswith(("https://", "http://", "data:image/")):
            return value
    return ""


def explicit_brand_change(payload=None):
    """Brand context is styling context, never permission to replace identity."""
    payload = payload if isinstance(payload, dict) else {}
    alter = set(_token_list(payload.get("alter"), ALTER_LABELS))
    return payload.get("explicit_brand_change") is True and "logo" in alter


def swap_input_references(payload=None, brand=None):
    refs = []
    reference = _reference(payload)
    if reference:
        refs.append(reference)
    # Extra stills are intentional agent references (product, packshot, or
    # visual direction), never a replacement for the active creative.
    for value in (payload or {}).get("reference_images") or []:
        image = str(value or "").strip()
        if image.startswith(("https://", "http://", "data:image/")) and image not in refs:
            refs.append(image)
        if len(refs) >= 2:
            break
    initial_reference = str((payload or {}).get("initial_reference") or "").strip()
    if initial_reference and initial_reference not in refs and len(refs) < 2:
        refs.append(initial_reference)
    if len(refs) >= 2 or not explicit_brand_change(payload):
        return refs[:2]
    logo = swap_logo_url(payload, brand)
    if logo and logo not in refs:
        refs.append(logo)
    return refs[:2]


def build_optimized_prompt(payload=None, brand=None, operations=None):
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
    brand_change = explicit_brand_change(payload)
    has_logo = brand_change and bool(swap_logo_url(payload, brand)) and not bool(payload.get("initial_reference"))
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
        "Use only the supplied brand reference for logos and symbols. Never redraw, rotate, mirror or invent a brand icon; preserve its exact geometry and orientation unless that icon is explicitly the selected item to change.",
        "The brand identity visible in the FIRST image is locked. Never replace its logo, wordmark, bank, institution or advertiser from context, memory or an unrelated reference.",
    ]
    variation = str(payload.get("variation_index") or "").strip().upper()
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
        lines.insert(1, "Change only what the user explicitly requested. Do not redesign the layout or replace the advertiser.")
    if payload.get("initial_reference"):
        lines.insert(
            1,
            "The first attachment is the latest approved working version. The second is the original continuity anchor. "
            "Preserve the same people, identity, products, logos and recurring graphic elements across both; do not drift or replace them.",
        )
    elif len(swap_input_references(payload, brand)) > 1 and not brand_change:
        lines.insert(
            1,
            "The FIRST attachment is the source creative. The SECOND attachment may guide only the explicitly selected item. "
            "It is not permission to replace the source advertiser, logo, wordmark, copy, people or layout.",
        )
    if variation in {"A", "B"}:
        lines.append(
            f"Create controlled test variation {variation}. Keep the same campaign, message and locked elements; vary only composition emphasis and visual treatment enough for an A/B comparison."
        )
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
    selected = payload.get("selected_element") if isinstance(payload.get("selected_element"), dict) else {}
    selected_role = str(selected.get("role") or "").strip()
    selected_box = selected.get("bbox_px")
    if selected_role:
        lines.append(f"The user selected the {selected_role} element for this request.")
        if isinstance(selected_box, (list, tuple)) and len(selected_box) == 4:
            coords = ", ".join(str(int(value)) for value in selected_box)
            lines.append(f"Apply the requested edit inside the selected crop bounds [{coords}] and protect the surrounding composition.")
    locks = _lock_list(payload)
    if locks:
        spelled = " | ".join(_spell_lock(item) for item in locks)
        lines.append("These strings must remain visible and correctly spelled: " + spelled + ".")
        lines.append(
            "Paint each locked string glyph by glyph. Do not double letters or add syllables "
            "(franca not franceça, Mumuzinho not Mumuzinho)."
        )
    if brand_change and use_brand and name:
        lines.append(f"New brand: {name}.")
    if brand_change and use_brand and color:
        lines.append(f"Brand color: {color}.")
    if use_brand and has_logo:
        lines.append(
            "Image 2 is the official brand logo lockup. Place that exact mark where the old logo sat."
        )
        lines.append(
            "Do not typeset the legal company name as a substitute for the official logo."
        )
    elif brand_change and use_brand and name:
        lines.append(
            f"Use the official {name} logo mark, not the spelled-out legal company name."
        )
    if use_brand:
        instruction = str((brand.get("creative_line") or {}).get("gpt_image_instruction") or "").strip()
        if instruction and (brand_change or not name):
            lines.append(instruction[:280])
        tone = str(brand.get("tone_of_voice") or "").strip()
        if tone:
            lines.append(f"Brand tone: {tone[:160]}.")
        for item in (brand.get("forbidden_elements") or [])[:4]:
            text = str(item).strip()
            if text:
                lines.append(f"Do not add: {text}.")
    variant = scene_variant(payload)
    if variant:
        lines.append(SCENE_VARIANT_PROMPT[variant])
    if not recrop:
        changed = _copy_from_operations(operations)
        if changed:
            for item in changed:
                lines.append(f"{item['label']} exactly: {item['to']}")
                if item["from"] and item["from"] != item["to"]:
                    lines.append(f"Replace only the line {item['from']!r}. Leave every other line untouched.")
        else:
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


def _copy_from_operations(operations):
    labels = {
        "headline": "Headline",
        "support": "Support",
        "price": "Price",
        "cta": "CTA",
    }
    rows = []
    for item in operations or []:
        if not isinstance(item, dict):
            continue
        current = str(item.get("to") or "").strip()
        if not current:
            continue
        original = str(item.get("from") or "").strip()
        if original == current:
            continue
        field = item.get("field") or ""
        rows.append({
            "field": field,
            "label": labels.get(field, field or "Line"),
            "from": original,
            "to": current,
        })
    return rows


def build_prompt_preview_pt(payload=None, brand=None, operations=None, mode=None):
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
    changed = _copy_from_operations(operations)
    if changed:
        for item in changed:
            if item["from"]:
                parts.append(f"{item['label']}: '{item['from']}' → '{item['to']}'.")
            else:
                parts.append(f"{item['label']}: '{item['to']}'.")
    else:
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
    variant = scene_variant(payload)
    if variant:
        parts.append(SCENE_VARIANT_NOTES[variant])
    parts.append(f"Formato de saída {aspect}.")
    parts.append("Rascunho de validação." if quality == "draft" else "Versão de produção, alta fidelidade.")
    risk = swap_risk(payload)
    mode = mode or swap_mode(payload)
    if mode == "recrop":
        parts.append("O Image 2 só vira o formato. Preço, quota e headline entram na foto depois.")
    elif risk.get("level") == "high":
        if mode == "typeset":
            parts.append("Tipo composto na foto. Elenco e selos ficam iguais à referência.")
        else:
            parts.append(risk["reason"])
    return " ".join(parts)


def preview_swap_prompt(payload=None, brand=None):
    from .swap_plan import build_swap_plan

    plan = build_swap_plan(payload, brand)
    data = plan["payload"]
    return {
        "prompt": "" if plan["noop"] else build_optimized_prompt(data, brand, operations=plan["operations"]),
        "preview": (
            "Nada para trocar. O Trocr não gera versão nem cobra Image 2."
            if plan["noop"]
            else build_prompt_preview_pt(data, brand, operations=plan["operations"], mode=plan["mode"])
        ),
        "quality": plan["quality"],
        "aspect_ratio": plan["aspect_ratio"],
        "quote": plan["quote"],
        "risk": plan["risk"],
        "mode": plan["mode"],
        "locks": plan["locks"],
        "plan_id": plan["plan_id"],
        "plan_hash": plan["plan_hash"],
        "planner_version": plan["planner_version"],
        "operations": plan["operations"],
        "conflicts": plan["conflicts"],
        "noop": plan["noop"],
        "blocked": plan["blocked"],
        "qa_criteria": plan["qa_criteria"],
        "protected": plan["protected"],
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
    alter = set(_token_list(payload.get("alter"), ALTER_LABELS))
    has_marked_type_region = any(item.get("bbox_px") for item in patches)
    if (
        alter
        and alter <= TYPE_ONLY
        and not scene_variant(payload)
        and (not payload.get("force_image") or has_marked_type_region)
    ):
        return "typeset"
    if payload.get("force_image"):
        return "image"
    return "image"


def prepare_swap(payload=None):
    from pydantic import ValidationError

    from .swap_schema import apply_swap_schema

    try:
        data = apply_swap_schema(payload, strict_limits=True)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        detail = str(first.get("msg") or "").strip() or "O pedido de troca é inválido."
        raise ValueError(detail) from exc
    data = apply_scene_variant(data)
    # Every edit inherits a hard brand lock. Only an explicit logo operation
    # can remove it; merely selecting a client/brand is never authorization.
    preserve = set(data.get("preserve") or [])
    alter = set(data.get("alter") or [])
    if explicit_brand_change(data):
        preserve.discard("logo")
    else:
        preserve.add("logo")
    from .swap_schema import ALTER_TOKENS, PRESERVE_TOKENS
    data["preserve"] = [key for key in PRESERVE_TOKENS if key in preserve]
    data["alter"] = [key for key in ALTER_TOKENS if key in alter]
    if not match_aspect_ratio(data.get("aspect_ratio") or data.get("output")):
        hint = match_aspect_ratio(data.get("aspect_hint"))
        if hint:
            data["aspect_ratio"] = hint
    return data


def scene_variant(payload=None):
    raw = payload.get("scene_variant") if isinstance(payload, dict) else None
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return 0
    return number if number in {2, 3} else 0


def apply_scene_variant(data):
    """Mesmos elementos, outra cena. Cena 2 ou 3 para animar depois."""
    payload = dict(data) if isinstance(data, dict) else {}
    variant = scene_variant(payload)
    if not variant:
        payload.pop("scene_variant", None)
        return payload
    from .swap_schema import ALTER_TOKENS, PRESERVE_TOKENS

    payload["scene_variant"] = variant
    payload["force_image"] = True
    preserve = set(payload.get("preserve") or [])
    preserve.update({"layout", "product", "logo", "colors", "style", "text_position"})
    preserve.discard("background")
    alter = set(payload.get("alter") or [])
    alter.add("background")
    alter.discard("product")
    payload["preserve"] = [key for key in PRESERVE_TOKENS if key in preserve]
    payload["alter"] = [key for key in ALTER_TOKENS if key in alter]
    payload["scene_index"] = variant
    if not str(payload.get("note") or "").strip():
        payload["note"] = SCENE_VARIANT_NOTES[variant]
    return payload


def locks_from_read(payload=None):
    from .swap_schema import apply_swap_schema

    try:
        return list(apply_swap_schema(payload, strict_limits=False).get("locks") or [])
    except (ValueError, TypeError):
        return []


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


def _ocr_message_content(response):
    if isinstance(response, dict):
        message = response.get("message")
        if isinstance(message, dict):
            for key in ("content", "parsed", "output_text"):
                value = message.get(key)
                if value not in (None, "", []):
                    return value
            details = message.get("reasoning_details")
            if isinstance(details, list):
                chunks = []
                for item in details:
                    if isinstance(item, str) and item.strip():
                        chunks.append(item)
                        continue
                    if not isinstance(item, dict):
                        continue
                    for key in ("text", "summary", "content", "reasoning"):
                        value = item.get(key)
                        if isinstance(value, str) and value.strip():
                            chunks.append(value)
                            break
                blob = "\n".join(chunks)
                if "{" in blob:
                    return blob
            reasoning = message.get("reasoning")
            if isinstance(reasoning, str) and "{" in reasoning:
                return reasoning
            return message.get("content")
        return response.get("content", response)
    return response


def _ocr_kwargs(extra=None):
    extra = extra if isinstance(extra, dict) else {}
    model = extra.get("model") or SWAP_READ_MODEL
    kwargs = {
        "model": model,
        "max_tokens": SWAP_READ_MAX_TOKENS,
        "temperature": SWAP_READ_TEMPERATURE,
        "response_format": JSON_OBJECT,
    }
    from ..services.openrouter_service import model_omits_sampling

    if model_omits_sampling(model) and "reasoning" not in extra:
        kwargs["reasoning"] = {"effort": "low"}
    for key, value in extra.items():
        if value is None:
            kwargs.pop(key, None)
        else:
            kwargs[key] = value
    return kwargs


def _invoke_ocr(text_callable, messages, extra=None):
    kwargs = _ocr_kwargs(extra)
    try:
        return text_callable(messages, **kwargs)
    except TypeError:
        kwargs.pop("reasoning", None)
        try:
            return text_callable(messages, **kwargs)
        except TypeError:
            kwargs.pop("response_format", None)
            try:
                return text_callable(messages, **kwargs)
            except TypeError:
                kwargs.pop("provider", None)
                return text_callable(messages, **kwargs)


def _ocr_runners(text_callable):
    from ..services.openrouter_service import chat_completion, resolve_api_key, resolve_openai_api_key

    if text_callable is None:
        return []
    if text_callable is not chat_completion:
        return [(text_callable, {}), (text_callable, {"reasoning": None})]
    runners = []
    # Prefer the configured OpenRouter account so Studio consumption uses its
    # credit balance. The only permitted alternative is the direct OpenAI
    # integration. With neither credential configured, do not call any service.
    has_openrouter = bool(resolve_api_key())
    if has_openrouter:
        runners.append((
            text_callable,
            {"model": SWAP_READ_MODEL, "provider": "openrouter", "reasoning": None},
        ))
    if resolve_openai_api_key():
        runners.append((
            text_callable,
            {"model": SWAP_READ_OPENAI_MODEL, "provider": "openai", "reasoning": None},
        ))
    return runners


def prepare_ocr_reference(reference):
    """JPEG compacto para o modelo. Still grande estoura o nano e devolve JSON inválido."""
    text = str(reference or "").strip()
    if not text.startswith("data:image/") or "," not in text:
        return text
    _header, encoded = text.split(",", 1)
    try:
        raw = base64.b64decode(encoded)
    except Exception:
        return text
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:
        return text
    width, height = image.size
    if max(width, height) <= OCR_MAX_SIDE and len(raw) <= OCR_MAX_BYTES:
        return text
    rgb = image.convert("RGB")
    if max(width, height) > OCR_MAX_SIDE:
        scale = OCR_MAX_SIDE / max(width, height)
        rgb = rgb.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
    out = io.BytesIO()
    rgb.save(out, format="JPEG", quality=OCR_JPEG_QUALITY, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")


def _parse_ocr_dict(response):
    raw = _ocr_message_content(response)
    if isinstance(raw, dict):
        return raw
    try:
        parsed = _json_content(raw)
    except Exception:
        try:
            parsed = json.loads(str(raw))
        except Exception:
            return None
    return parsed if isinstance(parsed, dict) else None


def _visual_marks(value):
    if not isinstance(value, list):
        return []
    marks = []
    for item in value[:20]:
        if not isinstance(item, dict):
            continue
        marks.append({
            "type": str(item.get("type") or "graphic").strip()[:24],
            "description": str(item.get("description") or "").strip()[:180],
            "orientation": str(item.get("orientation") or "unknown").strip()[:16],
            "text": str(item.get("text") or "").strip()[:80],
            "confidence": item.get("confidence"),
            "matches_reference": item.get("matches_reference"),
        })
    return marks


def _finish_ocr_read(parsed):
    from .swap_schema import normalize_read

    aspect_hint = match_aspect_ratio(parsed.get("aspect_hint"))
    normalized = normalize_read({**parsed, "aspect_hint": aspect_hint})
    elements = normalized.get("elements") or []
    return {
        "headline": normalized.get("headline") or "",
        "support": normalized.get("support") or "",
        "subtitle": normalized.get("subtitle") or "",
        "price": normalized.get("price") or "",
        "cta": normalized.get("cta") or "",
        "disclaimer": normalized.get("disclaimer") or "",
        "logo_text": normalized.get("logo_text") or "",
        "visual_marks": _visual_marks(parsed.get("visual_marks")),
        "dates": normalized.get("dates") or "",
        "venue": normalized.get("venue") or "",
        "aspect_hint": aspect_hint,
        "style": normalized.get("style") or "",
        "elements": elements,
        "faces": normalized.get("faces") or 0,
        "locks": normalized.get("locks") or [],
        "locks_overflow": bool(normalized.get("locks_overflow")),
        "elements_overflow": bool(normalized.get("elements_overflow")),
        "overflow": normalized.get("overflow") or [],
        "analysis": _analysis_from_read({**parsed, **normalized}, elements),
        "status": _read_status(normalized),
        "error": "",
    }


def read_swap_reference(payload=None, *, text_callable=None):
    payload = payload if isinstance(payload, dict) else {}
    reference = prepare_ocr_reference(_reference(payload))
    if not reference:
        raise ValueError("Envie uma imagem de referência.")
    empty = _empty_read()
    if text_callable is None:
        return {**empty, "status": "unavailable", "error": "OCR indisponível. Escreva os textos na mão."}
    system = READ_STRICT_SYSTEM if payload.get("strict") else READ_SYSTEM
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Faça OCR multimodal do still: leia todo texto visível e também inspecione símbolos, ícones, wordmarks e marcas gráficas. Retorne visual_marks mesmo quando não houver texto. Para ícones, descreva a geometria e a orientação; não transforme um símbolo em logo_text. Preço, CTA e logo são opcionais: se não aparecer, deixe vazio. Não invente R$, Saiba mais nem marca."},
                {"type": "image_url", "image_url": {"url": reference}},
            ],
        },
    ]
    last_status = "invalid"
    last_error = "A leitura veio inválida. Escreva os textos na mão."
    for runner, extra in _ocr_runners(text_callable):
        try:
            response = _invoke_ocr(runner, messages, extra)
        except Exception:
            last_status = "provider_error"
            last_error = "O provedor de OCR falhou. Escreva na mão ou tente de novo."
            # O primeiro adaptador injetado já chega sem parâmetros extras.
            # Reexecutá-lo depois de uma falha operacional duplica consumo
            # sem aumentar a chance de recuperação. As tentativas seguintes
            # permanecem para respostas JSON inválidas e para a rota direta
            # OpenAI, a única alternativa autorizada do chat_completion real.
            if not extra:
                break
            continue
        parsed = _parse_ocr_dict(response)
        if not isinstance(parsed, dict):
            last_status = "invalid"
            last_error = "A leitura veio inválida. Escreva os textos na mão."
            continue
        result = _finish_ocr_read(parsed)
        if result.get("status") != "unreadable":
            return result
        last_status = "unreadable"
        last_error = "A leitura veio vazia. Escreva os textos na mão."
    return {**empty, "status": last_status, "error": last_error}


def swap_reference(payload=None, *, brand=None, image_callable=None):
    from .swap_plan import assert_swap_plan

    plan = assert_swap_plan(payload, brand)
    payload = plan["payload"]
    if not _reference(payload):
        raise ValueError("Envie uma imagem de referência.")
    if plan["noop"]:
        return {
            "prompt": "",
            "preview": "Nada para trocar. O Trocr não gera versão nem cobra Image 2.",
            "reference": (_reference(payload) or "")[:80],
            "logo_used": False,
            "aspect_ratio": plan["aspect_ratio"],
            "quality": plan["quality"],
            "model": "noop",
            "mode": "noop",
            "noop": True,
            "risk": plan["risk"],
            "png_data_url": "",
            "quote": plan["quote"],
            "plan_id": plan["plan_id"],
            "plan_hash": plan["plan_hash"],
            "conflicts": plan["conflicts"],
            "operations": plan["operations"],
        }
    refs = swap_input_references(payload, brand)
    if not refs:
        raise ValueError("Envie uma imagem de referência.")
    mode = swap_mode(payload)
    if mode == "typeset":
        return _with_plan(typeset_reference(payload, brand=brand, operations=plan.get("operations")), plan)
    if image_callable is None:
        raise ValueError("Gerador de imagem indisponível.")
    prompt = build_optimized_prompt(payload, brand, operations=plan.get("operations"))
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
            },
            brand=brand,
            operations=plan.get("operations"),
        )
        painted["mode"] = "recrop"
        painted["passes"] = ["image", "typeset"]
        painted["model"] = SWAP_MODEL
        painted["quality"] = quality
        painted["prompt"] = prompt
        painted["preview"] = build_prompt_preview_pt(
            payload, brand, operations=plan.get("operations"), mode="recrop"
        )
        painted["logo_used"] = bool(swap_logo_url(payload, brand) in refs)
        painted["quote"] = quote_swap(payload)
        return _with_plan(painted, plan)
    return _with_plan({
        "prompt": prompt,
        "preview": build_prompt_preview_pt(
            payload, brand, operations=plan.get("operations"), mode="image"
        ),
        "reference": refs[0][:80],
        "logo_used": bool(swap_logo_url(payload, brand) in refs),
        "aspect_ratio": aspect_ratio,
        "quality": quality,
        "model": SWAP_MODEL,
        "mode": "image",
        "risk": swap_risk(payload),
        "png_data_url": still,
        "quote": quote_swap({**payload, "force_image": True}),
    }, plan)


def _with_plan(result, plan):
    data = dict(result or {})
    data["plan_id"] = plan.get("plan_id") or ""
    data["plan_hash"] = plan.get("plan_hash") or ""
    data["conflicts"] = list(plan.get("conflicts") or [])
    data["operations"] = list(plan.get("operations") or [])
    data["noop"] = bool(plan.get("noop"))
    data["blocked"] = bool(plan.get("blocked"))
    return data


def typeset_reference(payload=None, brand=None, operations=None):
    payload = prepare_swap(payload)
    reference = _reference(payload)
    raw = _load_typeset_png(reference)
    before = _open_typeset_image(raw)
    payload = attach_inferred_cta_regions(payload, before)
    after = before.copy()
    patches = typeset_patches(payload)
    _apply_typeset(after, patches, resolve_aspect_ratio(payload), payload)
    boxes = [tuple(item["bbox_px"]) for item in patches if item.get("masked") and item.get("bbox_px")]
    qa = score_typeset_qa(before, after, boxes)
    if qa.get("status") == "fail":
        raise ValueError("O typeset pintou fora da região. Selecione de novo.")
    buffer = io.BytesIO()
    after.save(buffer, format="PNG")
    return {
        "prompt": build_optimized_prompt(payload, brand, operations=operations),
        "preview": build_prompt_preview_pt(payload, brand, operations=operations, mode="typeset"),
        "reference": reference[:80],
        "logo_used": False,
        "aspect_ratio": resolve_aspect_ratio(payload),
        "quality": "typeset",
        "model": "typeset",
        "mode": "typeset",
        "risk": swap_risk(payload),
        "patches": patches,
        "qa": qa,
        "png_data_url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
        "quote": quote_swap(payload),
    }


def typeset_patches(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    alter = set(_token_list(payload.get("alter"), ALTER_LABELS))
    if payload.get("typeset_all"):
        alter = alter | {"headline", "secondary", "price"}
    rows = []
    if "headline" in alter and payload.get("headline"):
        rows.append(_patch_row(payload, "headline", payload["headline"]))
    if "secondary" in alter:
        if payload.get("support"):
            rows.append(_patch_row(payload, "secondary", payload["support"]))
        if payload.get("dates"):
            rows.append(_patch_row(payload, "dates", payload["dates"]))
    ctas = [
        item
        for item in (payload.get("elements") or [])
        if isinstance(item, dict) and item.get("role") == "cta" and str(item.get("text") or "").strip()
    ]
    if "cta" in alter and len(ctas) > 1:
        for item in ctas:
            box = item.get("bbox_px")
            rows.append({
                "slot": "cta",
                "text": str(item.get("text") or "").strip(),
                "bbox_px": [int(part) for part in box] if isinstance(box, (list, tuple)) and len(box) == 4 else None,
                "element_id": item.get("id") or "",
            })
    elif "cta" in alter and payload.get("cta"):
        rows.append(_patch_row(payload, "cta", payload["cta"]))
    if "price" in alter and payload.get("price"):
        rows.append(_patch_row(payload, "price", payload["price"]))
    return rows


def _patch_row(payload, slot, text):
    return {
        "slot": slot,
        "text": str(text).strip(),
        "bbox_px": _region_for_slot(payload, slot),
    }


def _region_for_slot(payload, slot):
    payload = payload if isinstance(payload, dict) else {}
    regions = payload.get("regions") if isinstance(payload.get("regions"), dict) else {}
    role = PATCH_ROLES.get(slot) or slot
    raw = regions.get(slot) or regions.get(role)
    if not raw:
        for item in payload.get("elements") or []:
            if isinstance(item, dict) and item.get("role") == role and item.get("bbox_px"):
                raw = item.get("bbox_px")
                break
    if isinstance(raw, dict):
        raw = [raw.get("x0"), raw.get("y0"), raw.get("x1"), raw.get("y1")]
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        return [int(part) for part in raw]
    except (TypeError, ValueError):
        return None


def _paint_typeset(png, patches, aspect="1:1"):
    image = _open_typeset_image(png)
    _apply_typeset(image, patches, aspect, {})
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _apply_typeset(image, patches, aspect="1:1", payload=None):
    slots = _slots_for(image, aspect)
    field = _canvas_field(image)
    ref = (
        int(payload.get("ref_width") or 0),
        int(payload.get("ref_height") or 0),
    ) if isinstance(payload, dict) else (0, 0)
    for patch in patches:
        user_box = _valid_user_box(patch.get("bbox_px"), image.size, ref)
        if user_box:
            crop = image.crop(user_box)
            patch["masked"] = True
            _paint_patch(crop, patch, field, (0.0, 0.0, 1.0, 1.0))
            image.paste(crop, (user_box[0], user_box[1]))
            patch["bbox_px"] = list(user_box)
            continue
        box = slots.get(patch["slot"])
        if not box:
            continue
        patch["masked"] = False
        _paint_patch(image, patch, field, box)


def _paint_patch(image, patch, field, slot):
    region = _locate_type(image, slot, field)
    fill = field
    if region.get("cover"):
        _cover_type(image, region["cover"], fill)
        target = region["bbox"]
    elif patch.get("masked"):
        _fill_slot(image, region["bbox"], fill)
        target = region["bbox"]
    else:
        target = region["bbox"]
    _draw_copy(
        image,
        target,
        target,
        _stack_copy(patch["text"]),
        _patch_ink(patch["slot"], region, field),
        align=_copy_align(patch["slot"], target),
    )


def _patch_ink(slot, region, field):
    ink = region.get("ink") or _contrast_ink(field)
    if slot in {"headline", "price"} and _luma(field) < 90:
        return (255, 255, 255)
    if slot == "secondary" and _luma(field) < 90 and _luma(ink) > 180:
        return (227, 6, 19)
    if slot == "cta":
        return ink if region.get("cover") else _contrast_ink(field)
    return ink


def _copy_align(slot, bbox):
    width = max(1, bbox[2] - bbox[0])
    height = max(1, bbox[3] - bbox[1])
    if slot == "headline" and 2.4 <= width / height < 4.5:
        return "left"
    return "center"


def _valid_user_box(raw, size, ref=None):
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    width, height = size
    ref_width, ref_height = ref if isinstance(ref, (list, tuple)) and len(ref) == 2 else (0, 0)
    if ref_width and ref_height and (ref_width != width or ref_height != height):
        return None
    try:
        x0, y0, x1, y1 = [int(part) for part in raw]
    except (TypeError, ValueError):
        return None
    x0, x1 = sorted((max(0, x0), max(0, x1)))
    y0, y1 = sorted((max(0, y0), max(0, y1)))
    x1, y1 = min(width, x1), min(height, y1)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return (x0, y0, x1, y1)


def score_typeset_qa(before, after, boxes):
    boxes = [tuple(item) for item in boxes or [] if item]
    if before.size != after.size:
        return {
            "status": "fail",
            "same_size": False,
            "pixels_outside_mask": -1,
            "masks": boxes,
        }
    if not boxes:
        return {
            "status": "unchecked",
            "same_size": True,
            "pixels_outside_mask": None,
            "masks": [],
        }
    from PIL import Image, ImageChops, ImageDraw

    changed = ImageChops.difference(before, after).convert("L").point(lambda pixel: 255 if pixel else 0)
    keep = Image.new("L", before.size, 255)
    draw = ImageDraw.Draw(keep)
    for box in boxes:
        draw.rectangle((box[0], box[1], max(box[0], box[2] - 1), max(box[1], box[3] - 1)), fill=0)
    leaked = ImageChops.multiply(changed, keep)
    leaked_n = sum(leaked.histogram()[1:])
    return {
        "status": "pass" if leaked_n == 0 else "fail",
        "same_size": True,
        "pixels_outside_mask": leaked_n,
        "masks": boxes,
    }


def _load_typeset_png(reference):
    text = str(reference or "")
    if text.startswith(("https://", "http://")):
        raise ValueError("O typeset não busca URL remota. Use a imagem da mesa.")
    if not text.startswith("data:image/") or "," not in text:
        raise ValueError("Envie uma imagem de referência.")
    encoded = text.split(",", 1)[-1]
    if len(encoded) > TYPESET_MAX_BYTES * 2:
        raise ValueError("A referência passa do limite do typeset.")
    try:
        raw = base64.b64decode(encoded)
    except Exception as exc:
        raise ValueError("A referência não é uma imagem válida.") from exc
    if len(raw) > TYPESET_MAX_BYTES:
        raise ValueError("A referência passa do limite do typeset.")
    return raw


def _open_typeset_image(png):
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Pillow é necessário para compor o tipo na foto.") from exc
    image = Image.open(io.BytesIO(png)).convert("RGB")
    if image.size[0] * image.size[1] > TYPESET_MAX_PIXELS:
        raise ValueError("A referência tem pixels demais para o typeset.")
    if image.size[0] < 8 or image.size[1] < 8:
        raise ValueError("A referência é pequena demais.")
    return image


def _slots_for(image, aspect="1:1"):
    base = TYPESET_SLOTS.get(aspect) or TYPESET_SLOTS["1:1"]
    top = TYPESET_SLOTS_TOP.get(aspect)
    if not top or aspect not in {"16:9", "9:16"}:
        return base
    field = _canvas_field(image)
    if aspect == "9:16":
        upper = _ink_weight(image, (0.04, 0.04, 0.92, 0.28), field)
        lower = _ink_weight(image, (0.08, 0.55, 0.84, 0.28), field)
    else:
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
    slot_box = (left, top, right, bottom)
    area = max(1, (right - left) * (bottom - top))
    if chromatic and len(chromatic) / area > 0.25:
        chromatic = []
    chosen = pale if pale else chromatic
    if not chosen:
        return {
            "bbox": slot_box,
            "slot": slot_box,
            "ink": _contrast_ink(field),
            "cover": [],
        }
    xs = [item[0] for item in chosen]
    ys = [item[1] for item in chosen]
    pad = max(2, int(height * (0.003 if height > width else 0.006)))
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
    radius = 6
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


def _draw_copy(image, bbox, slot, text, ink, align="center"):
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    left, right = slot[0], slot[2]
    top, bottom = bbox[1], bbox[3]
    max_width = max(12, right - left - 6)
    max_height = max(12, bottom - top + int((bottom - top) * 0.12))
    lines = max(1, text.count("\n") + 1)
    font = _fit_font(draw, text, max_width, max_height, int(max_height / lines * 0.96))
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=0, align=align)
    tw, th = box[2] - box[0], box[3] - box[1]
    if align == "left":
        tx = left + 4
    else:
        tx = left + max(2, (right - left - tw) // 2)
    ty = top + max(0, (bottom - top - th) // 2)
    draw.multiline_text((tx, ty), text, font=font, fill=ink, spacing=0, align=align)


def _stack_copy(text):
    raw = str(text or "").strip()
    if not raw or "\n" in raw:
        return raw
    words = raw.split()
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
    wash = [item for item in buckets if _luma(item) < 232]
    return Counter(wash or buckets).most_common(1)[0][0]


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
        "visual_marks": [],
        "dates": "",
        "venue": "",
        "aspect_hint": "",
        "style": "",
        "elements": [],
        "faces": 0,
        "locks": [],
        "locks_overflow": False,
        "elements_overflow": False,
        "overflow": [],
        "analysis": {key: False for key in ANALYSIS_KEYS},
        "status": "",
        "error": "",
    }


def _read_status(read):
    read = read if isinstance(read, dict) else {}
    if read.get("overflow") or read.get("elements_overflow") or read.get("locks_overflow"):
        return "partial"
    filled = bool(read.get("visual_marks")) or any(
        str(read.get(key) or "").strip()
        for key in ("headline", "support", "price", "cta", "dates", "logo_text", "disclaimer")
    )
    if not filled:
        filled = any(
            str(item.get("text") or "").strip()
            for item in (read.get("elements") or [])
            if isinstance(item, dict)
        )
    return "completed" if filled else "unreadable"


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
            seen.append(text)
    return seen


def _analysis_from_read(parsed, elements):
    raw = parsed.get("analysis") if isinstance(parsed.get("analysis"), dict) else {}
    present = {}
    for item in elements:
        role = item.get("role") if isinstance(item, dict) else getattr(item, "role", "")
        mapped = _ROLE_TO_ANALYSIS.get(role)
        if mapped:
            present[mapped] = True
    if parsed.get("headline"):
        present["headline"] = True
    if parsed.get("support") or parsed.get("subtitle"):
        present["secondary"] = True
    if parsed.get("cta"):
        present["cta"] = True
    if parsed.get("logo_text"):
        present["logo"] = True
    if parsed.get("price") or parsed.get("disclaimer") or parsed.get("dates"):
        present["supports"] = True
    result = {}
    for key in ANALYSIS_KEYS:
        flagged = raw.get(key)
        if present.get(key):
            result[key] = True
        elif key in {"cta", "logo", "supports"}:
            result[key] = False
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


def image_quality(payload=None):
    """Qualidade HTTP do Image 2 só no Trocr. Mesa/Camadas não passam este campo."""
    return "medium" if _quality(payload) == "draft" else "high"


def may_infer_cta_pills(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    if "cta" not in set(payload.get("alter") or []):
        return False
    ctas = [
        item
        for item in (payload.get("elements") or [])
        if isinstance(item, dict) and item.get("role") == "cta" and str(item.get("text") or "").strip()
    ]
    if ctas:
        return not all(item.get("bbox_px") for item in ctas)
    if not str(payload.get("cta") or "").strip():
        return False
    regions = payload.get("regions") if isinstance(payload.get("regions"), dict) else {}
    return not bool(regions.get("cta"))


def attach_inferred_cta_regions(payload, image):
    data = dict(payload or {})
    if "cta" not in set(data.get("alter") or []):
        return data
    elements = [dict(item) if isinstance(item, dict) else item for item in (data.get("elements") or [])]
    ctas = [
        item
        for item in elements
        if isinstance(item, dict) and item.get("role") == "cta" and str(item.get("text") or "").strip()
    ]
    wanted = len(ctas) if ctas else (1 if str(data.get("cta") or "").strip() else 0)
    if wanted == 0:
        return data
    if wanted >= 2 and all(item.get("bbox_px") for item in ctas):
        return data
    if wanted == 1:
        has_box = bool(ctas and ctas[0].get("bbox_px"))
        regions = data.get("regions") if isinstance(data.get("regions"), dict) else {}
        if has_box or regions.get("cta"):
            return data
    boxes = locate_cta_pills(image, max(wanted, 2))
    if wanted >= 2:
        if len(boxes) < wanted:
            raise ValueError("Não achei as duas pills de CTA. Selecione a região de cada botão.")
        for item, box in zip(ctas, boxes):
            if not item.get("bbox_px"):
                item["bbox_px"] = box
        data["elements"] = elements
        return data
    if not boxes:
        raise ValueError("Não achei a pill de CTA. Selecione a região do botão.")
    first = boxes[0]
    if ctas:
        if not ctas[0].get("bbox_px"):
            ctas[0]["bbox_px"] = first
        data["elements"] = elements
        return data
    regions = dict(data.get("regions") or {}) if isinstance(data.get("regions"), dict) else {}
    regions["cta"] = first
    data["regions"] = regions
    return data


def locate_cta_pills(image, count=2):
    count = max(1, int(count or 1))
    width, height = image.size
    work = image
    scale = 1.0
    if width > 480:
        scale = width / 480.0
        work = image.resize((480, max(1, int(round(height / scale)))))
    field = _canvas_field(work)
    work_w, work_h = work.size
    chromatic = []
    for py in range(work_h):
        for px in range(work_w):
            pixel = work.getpixel((px, py))
            if not _far_from_field(pixel, field):
                continue
            if max(pixel[:3]) - min(pixel[:3]) > 80:
                chromatic.append((px, py))
    if not chromatic:
        return []
    clusters = _split_x_clusters(chromatic, min_gap=max(12, work_w // 20))
    valid = [
        cluster
        for cluster in clusters
        if _pill_score(cluster, (work_w, work_h)) > 0
    ]
    valid.sort(key=lambda cluster: min(point[0] for point in cluster))
    chosen = valid[:count]
    if not chosen:
        return []
    pad = max(3, int(work_h * 0.02))
    boxes = []
    for cluster in chosen:
        xs = [point[0] for point in cluster]
        ys = [point[1] for point in cluster]
        box = [
            max(0, min(xs) - pad),
            max(0, min(ys) - pad),
            min(work_w, max(xs) + pad + 1),
            min(work_h, max(ys) + pad + 1),
        ]
        if scale != 1.0:
            box = [
                max(0, int(box[0] * scale)),
                max(0, int(box[1] * scale)),
                min(width, int(box[2] * scale)),
                min(height, int(box[3] * scale)),
            ]
        if box[2] - box[0] < 8 or box[3] - box[1] < 8:
            return []
        boxes.append(box)
    return boxes


def _split_x_clusters(points, min_gap=16):
    if not points:
        return []
    ordered = sorted(points, key=lambda item: (item[0], item[1]))
    clusters = [[ordered[0]]]
    for item in ordered[1:]:
        if item[0] - clusters[-1][-1][0] >= min_gap:
            clusters.append([item])
        else:
            clusters[-1].append(item)
    return clusters


def _pill_score(cluster, size):
    if len(cluster) < 12:
        return -1
    xs = [point[0] for point in cluster]
    ys = [point[1] for point in cluster]
    width = max(xs) - min(xs) + 1
    height = max(ys) - min(ys) + 1
    if height < 6 or width < 12:
        return -1
    area = width * height
    img_area = max(1, size[0] * size[1])
    if area / img_area > 0.35:
        return -1
    aspect = width / max(1, height)
    if aspect < 1.2:
        return -1
    return len(cluster) * min(aspect, 4.0)


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
