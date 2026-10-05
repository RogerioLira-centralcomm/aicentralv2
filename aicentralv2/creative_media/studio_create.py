"""AI directions and credit charging for the Studio creation desk."""
from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import os
import re
import time
from decimal import Decimal
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from ..creative_modeling_generation import OpenRouterError, _json_content
from . import studio_playbook, studio_review

logger = logging.getLogger(__name__)

MODEL = os.getenv("CREATIVE_STUDIO_DIRECTION_MODEL", "openai/gpt-5-nano")
# Haiku 4.5 (OpenRouter) writes the direction; GPT-5 nano on OpenAI and gpt-4o-mini on OpenRouter are the fallbacks.
DIRECTOR_MODEL = os.getenv("CREATIVE_STUDIO_DIRECTOR_MODEL", "anthropic/claude-haiku-4.5")
DIRECTOR_FALLBACK_MODEL = os.getenv("CREATIVE_STUDIO_DIRECTOR_FALLBACK_MODEL", MODEL.removeprefix("openai/"))
DIRECTION_PROMPT_CHARS = 1600
DIRECTION_TOKEN_BASE = 4000
DIRECTION_TOKENS_PER_ITEM = 1200
REDUNDANCY_MODEL = os.getenv("CREATIVE_STUDIO_DIRECTION_FALLBACK_MODEL", "openai/gpt-4o-mini")
IMAGE_MODEL = os.getenv("CREATIVE_STUDIO_IMAGE_MODEL", "openai/gpt-image-2")
MAX_IMAGE_REFERENCES = 3
MIN_SIDE_PX = 16
REFERENCE_DIRECTION_TOKENS = 180
REFERENCE_IMAGE_COST_FACTOR = Decimal("0.12")
IMAGE_ROLES = {
    "primary": "the primary/base image whose unrequested content must be preserved",
    "insert": "an element source to integrate naturally into the primary image",
    "replace": "the visual source for the selected replacement region",
    "style": "a style-only reference; do not copy its subject or text",
    "composition": "a composition-only reference; do not copy its subject or text",
    "reference": "a general user-supplied visual reference; use it to inform the image without treating it as a base image",
    "identity": "an identity reference whose product, person or package details must remain faithful",
}
_REQUEST_ID = re.compile(r"^[a-zA-Z0-9_-]{8,160}$")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def estimated_tokens(count, reference_count=0):
    # Reserve the complete, bounded prompt and completion budget before making
    # a billable provider call. Visual inputs make the director's multimodal
    # inspection more expensive, so the estimate must rise before the call;
    # actual provider usage remains the source of truth at charge time.
    directions = max(1, min(int(count or 1), 5))
    references = max(0, min(int(reference_count or 0), MAX_IMAGE_REFERENCES))
    return 1300 + directions * 320 + references * REFERENCE_DIRECTION_TOKENS


def suggestions(document):
    data = document if isinstance(document, dict) else {}
    subject = text(data.get("objective") or data.get("brief") or data.get("name"), 110) or "a campanha"
    audience = text(data.get("audience") or data.get("publico"), 70)
    return [
        text(f"Campanha institucional de {subject} para {audience or 'o público prioritário'}", 140),
        text(f"Display IAB para {subject}: cena brasileira, mensagem curta e marca reconhecível", 140),
        text(f"Filme CTV para {subject}: momento humano, direção de arte e assinatura de marca", 140),
    ]


def create(payload, text_callable):
    data = payload if isinstance(payload, dict) else {}
    count = max(1, min(integer(data.get("count"), 1), 5))
    request = clean_prompt(data.get("prompt"), 1200)
    if not request:
        raise ValueError("Descreva a direção que deseja criar.")
    context = clean_context(data.get("context"), count)
    budget = studio_playbook.copy_budget(context.get("width"), context.get("height"))
    context["orcamento_de_texto"] = budget
    messages = [
        {"role": "system", "content": system_prompt(count) + "\n\n" + studio_playbook.budget_instruction(
            budget, context.get("width"), context.get("height"),
            typeset=display_typeset(context.get("width"), context.get("height"), bool(context.get("typeset_social")) or SOCIAL_TYPESET))},
        {"role": "user", "content": direction_user_content(request, context)},
    ]
    response = None
    raw = None
    provider_used = model_used = ""
    errors = []
    # The first call is direct OpenAI. OpenRouter is a true redundancy path,
    # not a synthetic direction: both providers must satisfy the same JSON
    # contract before the request can continue to generation.
    for provider, model in director_routes():
        try:
            response = text_callable(
                messages,
                model=model,
                provider=provider,
                # GPT-5 reasoning consumes this same budget; a tight cap returns an empty answer.
                max_tokens=DIRECTION_TOKEN_BASE + count * DIRECTION_TOKENS_PER_ITEM,
                temperature=.45,
                **({"reasoning": {"effort": "low"}} if "gpt-5" in model else {}),
                response_format={"type": "json_object"},
            )
            content = response.get("message", {}).get("content") if isinstance(response, dict) else response
            raw = content if isinstance(content, dict) else _json_content(content)
            if not isinstance(raw, dict) or not isinstance(raw.get("directions"), list):
                raise OpenRouterError("O provedor não devolveu o contrato de direções.")
            provider_used, model_used = provider, model
            break
        except (OpenRouterError, ValueError, KeyError, TypeError, AttributeError) as error:
            errors.append(f"{provider}: {error}")
            response = None
            raw = None
    if response is None or not isinstance(raw, dict):
        # Keep provider/model diagnostics out of the user-facing API error,
        # but retain a structured trace for the operational investigation.
        # Do not include the briefing or reference URLs here: both can carry
        # customer material and are not needed to identify the failed route.
        logger.warning(
            "Studio direction failed routes=%s reference_count=%s format=%s",
            " | ".join(errors)[:900],
            len(context.get("references") or []),
            context.get("format") or "",
        )
        raise OpenRouterError("Não foi possível preparar a direção criativa. Tente novamente em alguns instantes.")
    items = []
    for item in raw.get("directions", []) if isinstance(raw, dict) else []:
        if not isinstance(item, dict):
            continue
        title, prompt = text(item.get("title"), 90), whole_words(item.get("prompt"), DIRECTION_PROMPT_CHARS)
        if title and prompt:
            reference_plan = []
            for reference in item.get("reference_plan", []) if isinstance(item.get("reference_plan"), list) else []:
                if not isinstance(reference, dict):
                    continue
                source = str(reference.get("source") or "user")
                if source not in {"global", "user", "project"}:
                    source = "user"
                use = text(reference.get("use"), 260)
                label = text(reference.get("label"), 140)
                if label and use:
                    entry = {"label": label, "source": source, "use": use}
                    layout = reference.get("layout") if isinstance(reference.get("layout"), dict) else {}
                    layout_contract = {key: text(layout.get(key), 180) for key in ("subject_zone", "headline_zone", "support_zone", "safe_margin", "layer_order", "alignment") if text(layout.get(key), 180)}
                    if layout_contract:
                        entry["layout"] = layout_contract
                    reference_plan.append(entry)
            edited = studio_playbook.edited_copy(item.get("copy"), request, budget)
            if not studio_playbook.fits(edited, budget, request) and studio_playbook._briefing_headline(request):
                edited = fit_copy(request, budget, context, text_callable) or edited
            items.append({"title": title, "summary": text(item.get("summary") or item.get("rationale"), 220) or "Direção baseada no briefing do projeto.", "prompt": prompt, "reference_plan": reference_plan[:4],
                          **({"copy": edited} if edited else {})})
        if len(items) == count:
            break
    if not items:
        raise ValueError("O agente não devolveu direções utilizáveis. Tente novamente.")
    return {"directions": items, "count": len(items), "model": str(response.get("model") or model_used), "provider": provider_used}, response


def fit_copy(request, budget, context, text_callable, attempts=2):
    """The director's copy review: cut the briefing's copy to the size's budget (only when the direction did not)."""
    best, previous = None, None
    for _ in range(attempts):
        for provider, model in director_routes()[:2]:
            try:
                response = text_callable(
                    studio_playbook.copy_fit_messages(request, budget, context.get("width"), context.get("height"), previous),
                    model=model, provider=provider, max_tokens=600, temperature=.2,
                    **({"reasoning": {"effort": "low"}} if "gpt-5" in model else {}),
                    response_format={"type": "json_object"},
                )
                content = response.get("message", {}).get("content") if isinstance(response, dict) else response
                raw = content if isinstance(content, dict) else _json_content(content)
                break
            except (OpenRouterError, ValueError, KeyError, TypeError, AttributeError):
                raw = None
        candidate = studio_playbook.edited_copy(raw, request, budget)
        if studio_playbook.fits(candidate, budget, request):
            return candidate
        if candidate and (not best or len(candidate["headline"].split()) < len(best["headline"].split())):
            best = candidate
        previous = candidate or (raw if isinstance(raw, dict) else None)
    return best


def director_routes():
    """(provider, model) in order: OpenRouter for ``vendor/model`` ids, OpenAI direct for bare GPT ids."""
    routes = []
    for model in (DIRECTOR_MODEL, DIRECTOR_FALLBACK_MODEL, REDUNDANCY_MODEL):
        route = ("openrouter" if "/" in model else "openai", model)
        if model and route not in routes:
            routes.append(route)
    return routes


def clean_context(raw, count):
    data = raw if isinstance(raw, dict) else {}
    references = [clean_direction_reference(item, index) for index, item in enumerate(data.get("references", [])[:MAX_IMAGE_REFERENCES]) if isinstance(item, dict)]
    creation_intent = str(data.get("creation_intent") or "branded_creative").strip().lower()
    if creation_intent not in {"branded_creative", "neutral_asset"}:
        creation_intent = "branded_creative"
    raw_brand = data.get("brand_context") if isinstance(data.get("brand_context"), dict) else {}
    brand_assets = raw_brand.get("assets") if isinstance(raw_brand.get("assets"), dict) else {}
    brand_context = {
        "name": text(raw_brand.get("name"), 120),
        "logo_url": text(raw_brand.get("logo_url"), 500),
        "palette": [text(item, 16) for item in raw_brand.get("palette", [])[:8]],
        "fonts": [
            {
                "family": text(item.get("family"), 80),
                "classification": text(item.get("classification"), 80),
                "role": text(item.get("role"), 24) or ("display" if index == 0 else "body"),
                "weight": text(item.get("weight"), 24),
                "style": text(item.get("style"), 24),
            }
            if isinstance(item, dict) else {"family": text(item, 80), "role": "display" if index == 0 else "body"}
            for index, item in enumerate(raw_brand.get("fonts", [])[:4])
            if text(item.get("family") if isinstance(item, dict) else item, 80) or (isinstance(item, dict) and text(item.get("classification"), 80))
        ],
        "brand_summary": text(raw_brand.get("brand_summary"), 500),
        "products_services": [text(item, 120) for item in raw_brand.get("products_services", [])[:8]],
        "mandatory_elements": [text(item, 160) for item in raw_brand.get("mandatory_elements", [])[:8]],
        "forbidden_elements": [text(item, 160) for item in raw_brand.get("forbidden_elements", [])[:8]],
        "creative_guidelines": text(raw_brand.get("creative_guidelines"), 700),
        "assets": {
            "logo": [text(item, 500) for item in brand_assets.get("logo", [])[:3]],
            "references": [text(item, 500) for item in brand_assets.get("references", [])[:8]],
        },
    }
    brand_context["readiness"] = brand_identity_readiness(brand_context)
    if mask_logo_policy(references) == "none":
        brand_context = brand_without_logo(brand_context)
    if creation_intent == "branded_creative":
        references = references_with_brand_logo(references, brand_context)
    return {key: text(data.get(key), limit) for key, limit in (("project_name", 120), ("brand", 120), ("brief", 1800), ("objective", 300), ("audience", 300), ("purpose", 24), ("format", 24))} | {
        "channels": [text(item, 24) for item in data.get("channels", []) if text(item, 24)][:5],
        "iab_formats": [text(item, 32) for item in data.get("formats", []) if text(item, 32)][:6],
        "direction_intensity": max(0, min(integer(data.get("direction_intensity"), 70), 100)),
        "format_key": text(data.get("format_key"), 80),
        "typeset_social": data.get("typeset_social") is True,
        "width": integer(data.get("width"), 0),
        "height": integer(data.get("height"), 0),
        "requested_directions": count,
        "auto_generate_next": data.get("auto_generate_next") is True,
        "generation_round": max(0, integer(data.get("generation_round"), 0)),
        "requested_palette": clean_palette(data.get("requested_palette")),
        "creation_intent": creation_intent,
        "references": references,
        "reference_mode": reference_mode(references),
        # When set, the Studio itself applies the official logo after generation, in this corner.
        "logo_corner": logo_position(references) if creation_intent == "branded_creative" and load_brand_logo(brand_context) is not None else "",
        "brand_context": brand_context if brand_context.get("name") and creation_intent == "branded_creative" else {},
    }


def clean_palette(raw):
    values = raw if isinstance(raw, list) else []
    colors = []
    for value in values[:6]:
        color = str(value or "").strip().upper()
        if _HEX_COLOR.fullmatch(color) and color not in colors:
            colors.append(color)
    return colors


def reference_mode(references):
    """Describe whether the user supplied a visual source for a fast remix.

    A Studio composition mask and a user image are complementary: the first
    controls the ad's spatial architecture, while the second supplies the
    visual language.  This must be explicit so a missing project logo or
    palette does not incorrectly turn a reference-led edit into a blank,
    neutral brand exercise.
    """
    items = references if isinstance(references, list) else []
    has_user_visual = any(
        item.get("source") == "user" and item.get("role") == "reference"
        for item in items if isinstance(item, dict)
    )
    has_global_mask = any(item.get("source") == "global" for item in items if isinstance(item, dict))
    if has_user_visual and has_global_mask:
        return "visual_remix"
    if has_user_visual:
        return "user_visual_reference"
    return "visual_references_selected" if items else "briefing_only"


def uses_user_visual_reference(references):
    return reference_mode(references) in {"visual_remix", "user_visual_reference"}


def brand_identity_readiness(brand_context):
    """Return a server-derived guard against invented visual identities."""
    brand = brand_context if isinstance(brand_context, dict) else {}
    assets = brand.get("assets") if isinstance(brand.get("assets"), dict) else {}
    has_logo = bool(text(brand.get("logo_url"), 500) or any(assets.get("logo") or []))
    has_palette = bool([item for item in brand.get("palette", []) if text(item, 16)])
    missing = []
    if not has_logo:
        missing.append("logo")
    if not has_palette:
        missing.append("cores")
    return {
        "status": "ready" if not missing else "partial" if len(missing) == 1 else "missing",
        "has_logo": has_logo,
        "has_palette": has_palette,
        "missing": missing,
    }


def brand_identity_guard(raw_brand, visual_reference=False, creation_intent="branded_creative", editing=False, logo_corner="", logo_free=False):
    brand = raw_brand if isinstance(raw_brand, dict) else {}
    if editing:
        # A masked edit changes one region; it must not stamp a new logo onto the piece.
        return (
            "BRAND IDENTITY (edit): preserve any logo, colors and typography already present outside the selected region. "
            "Do not add or move a logo unless the edit instruction explicitly asks for it."
        )
    if creation_intent == "neutral_asset":
        return (
            "NEUTRAL ASSET MODE: This request is a page, background, texture, scene or other reusable visual asset, not a branded advertisement. "
            "Do not apply, infer, reserve space for, or describe the project's logo, palette, font system, product, claim or campaign. "
            "Follow only the user's requested visual material and any selected reference contract."
        )
    if visual_reference:
        logo = official_logo_reference(brand)
        return (
            "VISUAL REFERENCE MODE: A user-supplied image is the visual source for this request. "
            "Use its observable palette, materials, lighting and subject treatment together with any global composition mask. "
            "Those visual cues are not official brand identity: do not invent or claim a logo, wordmark or color system for the project."
            + (
                " An approved logo was supplied separately. Preserve that exact logo, make it fully visible within the safe margin, and do not redraw or crop it."
                if logo else ""
            )
        )
    name = text(brand.get("name"), 120) or "the brand"
    logo = official_logo_reference(brand)
    palette = [text(item, 16) for item in brand.get("palette", []) if text(item, 16)]
    fonts = [
        text(item.get("family") or item.get("classification"), 80) if isinstance(item, dict) else text(item, 80)
        for item in brand.get("fonts", [])
    ]
    fonts = [item for item in fonts if item]
    lines = ["BRAND IDENTITY (mandatory for this branded piece):"]
    if logo_free:
        lines.append(
            "- LOGO: this composition carries no logo. Do not draw any logo, wordmark, monogram, initials or brand name anywhere in the image."
        )
    elif logo and logo_corner:
        lines.append(
            f"- LOGO: the Studio applies the official {name} logo after generation in the {logo_corner.replace('-', ' ')} corner. "
            f"Keep that corner clean and calm (plain background, no text, no objects, no faces), leaving about 24% of the width and 14% of the height free there, "
            "and do NOT draw any logo, wordmark, monogram, brand name or lookalike anywhere in the image."
        )
    elif logo:
        lines.append(
            f"- LOGO: the image labelled as the official logo of {name} must appear exactly once, reproduced faithfully "
            "(same shapes, letters and colors; no redraw, recolor, outline, 3D or distortion), fully inside the safe margin, "
            "on a calm area with enough contrast, at a clearly legible size (about 10-16% of the canvas width). "
            "POSITION: the logo's bottom edge must sit at least 10% of the canvas height above the bottom edge and its side edge at least 8% of the canvas width from the side edge; never touching, clipped by or hugging any edge. "
            "Do not invent any other logo, monogram or wordmark for the brand."
        )
    else:
        lines.append(
            f"- LOGO: no official logo of {name} was supplied. Do not invent, infer or stylize a logo, monogram, initials or wordmark; "
            "keep a clean intentional area where it will be applied later."
        )
    if palette:
        lines.append(
            f"- OFFICIAL COLORS: {', '.join(palette)}. They must be clearly visible in the piece (backgrounds, shapes, typography or CTA), "
            "not only in the logo. A campaign or briefing palette may lead the mood, but the official colors must remain recognizable."
        )
    elif logo:
        lines.append(
            "- COLORS: no official palette was registered. Take accent colors from the supplied logo's own visible colors so the piece "
            "feels like the brand; do not present unrelated colors as official."
        )
    else:
        lines.append("- COLORS: no official palette was registered; never present arbitrary colors as official brand colors.")
    if fonts:
        lines.append(f"- TYPOGRAPHY: follow this direction for visible copy: {', '.join(fonts[:3])}.")
    return " ".join(lines)


def official_logo_reference(raw_brand):
    """Return the first provider-safe official logo, never a generated proxy."""
    brand = raw_brand if isinstance(raw_brand, dict) else {}
    assets = brand.get("assets") if isinstance(brand.get("assets"), dict) else {}
    candidates = [brand.get("logo_url"), *(assets.get("logo") or [])]
    for candidate in candidates:
        url = text(candidate, 500)
        if url.startswith(("https://", "http://", "/static/")) and not url.lower().split("?")[0].endswith(".svg"):
            return {
                "id": "brand:official-logo",
                "url": url,
                "role": "identity",
                "source": "project",
                "label": f"{text(brand.get('name'), 120) or 'Marca'} · logo oficial",
                "instruction": "the OFFICIAL BRAND LOGO: place it once, exactly as supplied, fully visible and legible inside the safe margin",
            }
    return None


def references_with_brand_logo(raw_references, raw_brand):
    """Append an approved logo without displacing the selected visual sources.

    Studio V2 intentionally sends up to three high-fidelity image inputs:
    global composition, user or project source, and approved identity. This
    gives complex creatives their full visual contract instead of silently
    choosing between layout, subject and brand.
    """
    references = [dict(item) for item in raw_references if isinstance(item, dict)][:MAX_IMAGE_REFERENCES]
    global_references = [
        item for item in references
        if item.get("source") == "global" or str(item.get("url") or "").startswith("/static/images/cadu/studio/references/")
    ]
    if len(global_references) > 1:
        raise ValueError("Escolha somente uma referência global de composição por criação.")
    logo = official_logo_reference(raw_brand)
    if not logo or any(str(item.get("url") or "") == logo["url"] for item in references):
        return references
    if len(references) >= MAX_IMAGE_REFERENCES:
        raise ValueError("Remova uma referência para incluir o logo oficial: a criação aceita até três imagens visuais.")
    return [*references, logo]


def _director_image_url(raw):
    """Public URL for the director; local development hosts get the pixels embedded instead."""
    from ..creative_modeling_storage import public_studio_asset_url
    public = public_studio_asset_url(raw)
    try:
        return _provider_reference_value(raw if str(raw).startswith("/static/") else public)
    except ValueError:
        return public


def direction_user_content(request, context):
    """Send stored references as URLs so the director can inspect their pixels."""
    from ..creative_modeling_storage import public_studio_asset_url

    provider_context = dict(context)
    provider_context["references"] = [
        {**reference, "url": public_studio_asset_url(reference.get("url"))}
        for reference in context.get("references", [])
        if isinstance(reference, dict) and str(reference.get("url") or "") not in {"", "inline upload"}
    ]
    brand = context.get("brand_context") if isinstance(context.get("brand_context"), dict) else {}
    if brand:
        provider_brand = dict(brand)
        if provider_brand.get("logo_url"):
            provider_brand["logo_url"] = public_studio_asset_url(provider_brand["logo_url"])
        assets = provider_brand.get("assets") if isinstance(provider_brand.get("assets"), dict) else {}
        if assets:
            provider_assets = dict(assets)
            provider_assets["logo"] = [
                public_studio_asset_url(url) for url in assets.get("logo", []) if isinstance(url, str)
            ]
            provider_assets["logos"] = [
                {**logo, "url": public_studio_asset_url(logo.get("url"))}
                for logo in assets.get("logos", []) if isinstance(logo, dict) and logo.get("url")
            ]
            provider_brand["assets"] = provider_assets
        provider_context["brand_context"] = provider_brand
    blocks = [{"type": "text", "text": json.dumps({"pedido": request, "contexto": provider_context}, ensure_ascii=False)}]
    for index, reference in enumerate(context.get("references", []), start=1):
        url = str(reference.get("url") or "")
        if not url or url == "inline upload":
            continue
        blocks.append({"type": "text", "text": (
            f"Referência visual {index}: {reference.get('label', 'sem nome')}; "
            f"source={reference.get('source', 'user')}; role={reference.get('role', 'reference')}. "
            "Inspecione os pixels e aplique o contrato descrito no contexto."
        )})
        from . import ad_masks
        spec = ad_masks.spec_from_url(url)
        if spec:
            # The director misreads wireframes when left to guess; hand it the exact zones it must describe.
            blocks.append({"type": "text", "text": (
                f"CONTRATO DE LAYOUT OBRIGATÓRIO da referência {index} (o gerador recebe o mesmo contrato): "
                "descreva a composição exatamente com estas zonas, nas mesmas posições, sem inventar outra divisão "
                "da tela, sem mover título, CTA ou logo e sem acrescentar elementos que o contrato não prevê.\n"
                + ad_masks.layout_contract(spec, index)
            )})
        blocks.append({"type": "image_url", "image_url": {"url": _director_image_url(url)}})
    logo = official_logo_reference(context.get("brand_context"))
    if logo and not any(
        str(reference.get("url") or "") == logo["url"]
        for reference in context.get("references", []) if isinstance(reference, dict)
    ):
        blocks.append({"type": "text", "text": (
            f"Logo oficial da marca {context.get('brand_context', {}).get('name') or 'do projeto'}: "
            "inspecione os pixels, preserve o desenho e use-o apenas como identidade da peça. "
            "Não redesenhe, simplifique ou substitua esta marca."
        )})
        blocks.append({"type": "image_url", "image_url": {"url": _director_image_url(logo["url"])}})
    return blocks


def clean_direction_reference(item, index):
    raw_url = str(item.get("url") or "")
    source = "global" if raw_url.startswith("/static/images/cadu/studio/references/") else str(item.get("source") or "user")
    role = str(item.get("role") or ("primary" if index == 0 else "insert"))
    # The Studio UI uses the neutral label "reference" for a selected
    # composition reference. Only protected global masks become composition;
    # a user upload remains a visual source for a fast remix.
    if role == "reference" and source == "global":
        role = "composition"
    if role not in IMAGE_ROLES:
        role = "insert"
    if source not in {"global", "user", "project"}:
        source = "user"
    return {
        "label": text(item.get("name") or item.get("label") or f"Imagem {index + 1}", 140),
        "role": role,
        "source": source,
        "instruction": text(item.get("instruction"), 500) or IMAGE_ROLES[role],
        "url": text(raw_url, 500) if raw_url.startswith(("https://", "http://", "/static/")) else "inline upload",
    }


def system_prompt(count):
    return f"""Você é diretor criativo de mídia no Cadu Studio. Crie exatamente {count} direções distintas para uma peça publicitária a partir do projeto fornecido.

Responda somente JSON no formato {{\"directions\":[{{\"title\":\"...\",\"summary\":\"...\",\"prompt\":\"...\",\"reference_plan\":[]}}]}}. Use português do Brasil. O conteúdo de reference_plan está definido ao final destas instruções.

REVISÃO DO BRIEFING: antes de escrever cada prompt, harmonize o pedido do usuário com o contexto do Studio. Preserve a intenção, anunciante, produto, público, cenário, ação, texto literal, preço, volume, logo solicitado e restrições explícitas. Corrija apenas ambiguidades, contradições, ordem e instruções técnicas; não troque o produto, não remova requisitos concretos e não invente benefícios, ofertas ou identidade visual. Se o usuário informar explicitamente uma marca, preço, volume, slogan ou pedido de logo, isso é requisito obrigatório e deve aparecer no prompt final exatamente como informado.
ORDEM OBRIGATÓRIA DO PROMPT FINAL: escreva um único parágrafo corrido, em linguagem natural, com no máximo 130 palavras, cobrindo nesta ordem: objetivo da peça; assunto principal visível; pessoas e ação; cenário, praça ou contexto cultural brasileiro e atmosfera; composição e posição de cada zona; uso das referências; luz, materiais e paleta; texto literal e onde fica. Não numere nem rotule as partes, não repita o formato e não escreva instruções técnicas: o Studio já envia formato, margens e regras de marca. MENOS É MAIS: uma ideia visual forte e um único foco por peça. TEXTO VISÍVEL: na arte entram somente os textos literais que o usuário escreveu (por exemplo, título e botão) e o logo oficial. Não acrescente subtítulos, listas, ícones com frases, números, porcentagens, gráficos com rótulos, selos, datas ou microtextos que o usuário não pediu. Se o usuário não informou texto algum, peça só uma área livre para a assinatura.
FORMATO É CONTROLADO PELO STUDIO: o campo contexto.format, contexto.format_key, contexto.width e contexto.height é a fonte de verdade do output selecionado na interface. Se o texto do pedido mencionar outra dimensão ou proporção, trate isso apenas como descrição do pedido e ignore a dimensão conflitante. Nunca escreva 300x300, 1080x1080 ou outra medida no prompt final quando o formato selecionado for diferente. Não repita o formato nem as dimensões no prompt final: o Studio já os envia ao gerador.
MARCA E PROJETO: contexto.creation_intent define o escopo. Em "branded_creative", quando contexto.brand_context existir, use-o como fonte de verdade para nome, logo, paleta, tipografia, ativos, elementos obrigatórios e elementos proibidos; aplique os ativos aprovados na peça. Tipografia pode trazer família aprovada ou somente uma classificação observada; não invente o nome de uma fonte proprietária quando houver apenas classificação. Em "neutral_asset", ignore integralmente a identidade do projeto: a solicitação é um fundo, página, textura, cena ou elemento reutilizável, não uma peça de marca. Referências de composição continuam sendo apenas guias de posição e hierarquia. Se contexto.requested_palette tiver cores, aplique-as apenas nesta peça como escolha explícita do briefing: elas não sobrescrevem nem passam a ser apresentadas como cores oficiais da marca. Avalie logo e cores separadamente em contexto.brand_context.readiness. LOGO: quando houver logo oficial (has_logo=true, ele chega como imagem anexada com o rótulo \"logo oficial\"), o prompt final DEVE dizer explicitamente onde o logo oficial entra (canto, assinatura ou lockup), em tamanho legível, uma única vez, reproduzido exatamente como fornecido, nunca encostado na borda: com a base do logo a pelo menos 10% da altura acima da borda inferior e o lado a pelo menos 8% da largura da borda lateral. EXCEÇÃO: quando contexto.logo_corner estiver preenchido (bottom-right ou top-left), o próprio Studio aplica o logo oficial depois da geração nesse canto; então NÃO peça para desenhar o logo no prompt final, e sim para manter esse canto limpo e calmo, sem texto, objetos ou rostos, e para não criar nenhum logo, marca ou nome de marca na imagem; nunca peça para reservar área vazia no lugar dele. Sem logo oficial, nunca invente logotipo, monograma, inicial, símbolo ou wordmark: reserve uma área limpa para aplicação posterior. CORES: quando houver paleta oficial, cite os hexadecimais no prompt final e diga onde aparecem (fundo, formas, tipografia, CTA); uma paleta temática do briefing (por exemplo, rosa de Outubro Rosa) pode conduzir o clima, mas as cores oficiais precisam continuar reconhecíveis. Sem paleta oficial mas com logo, use as cores visíveis do próprio logo como acentos, sem chamá-las de paleta oficial. Sem logo e sem cores, não invente identidade. TIPOGRAFIA: quando brand_context.fonts existir, indique a direção tipográfica para os textos visíveis. O título de cada direção deve citar a marca. EXCEÇÃO DE REMIX: quando contexto.reference_mode for "visual_remix" ou "user_visual_reference", a imagem anexada pelo usuário é a evidência visual prioritária. Extraia dela apenas características observáveis — paleta, materiais, luz, tratamento do assunto e linguagem da peça — sem dizer que são cores ou logo oficiais do projeto e sem exigir identidade ausente.

REFERÊNCIAS — você receberá as imagens selecionadas como blocos visuais no mesmo turno. Inspecione seus pixels antes de escrever cada direção; não deduza a composição apenas pelo nome ou URL. Trate cada item do contexto como contrato, nunca como decoração. Itens com source="global" são máscaras protegidas de composição do Studio: diagramas anotados em que só o retângulo interno, dentro da guia SAFE MARGIN, é a peça; título, legenda e coluna de camadas ao redor são documentação. Use-as como planta estrutural, extraindo ordem de camadas, zona do produto/assunto, faixa de headline, área de preço ou CTA, margens seguras, alinhamento, respiro e relação entre foreground e background. Reproduza essa arquitetura espacial na peça final com o conteúdo do briefing, sem copiar o template, sem usar o objeto fictício da máscara como produto, sem alterar o arquivo e sem colocá-lo na biblioteca do usuário. Quando houver máscara global, o prompt final deve REPRODUZIR a máscara fielmente, sem reinterpretar: se o assunto principal está centralizado na máscara, ele fica centralizado; se o título está centralizado no alto, ele fica centralizado no alto; só mude a posição de uma zona se o briefing exigir. Descreva em texto a posição de cada zona (por exemplo, "metade esquerda: cena da TV; metade direita: título e texto; canto inferior direito: CTA") e, se a máscara tiver zona LOGO, posicionar o logo oficial nela. Respeite a guia SAFE MARGIN da máscara: título, textos, logo e botão ficam dentro dela, com respiro das bordas; só o fundo vai até a borda. Para cada global, devolva no reference_plan um layout com subject_zone, headline_zone, support_zone, safe_margin, layer_order e alignment, descrevendo posições relativas observadas na imagem. Itens com source="user" ou source="project" são referências de produção: aplique na imagem criada o conteúdo visual útil, como produto, pessoa, embalagem, identidade, textura, cenário ou objeto, preservando os detalhes relevantes quando a intenção indicar. Quando reference_mode="visual_remix", una a imagem do usuário e a máscara global: a imagem do usuário define a linguagem visual e a máscara global define a estrutura, zonas e respiro. Gere uma nova peça coerente, não uma cópia literal, e não transforme cores vistas no anexo em identidade oficial. Não confunda uma referência global de composição com uma imagem-base do usuário. Quando reference_mode="briefing_only", não mencione referências visuais, não invente uma reference_plan e crie uma direção original baseada somente no briefing, canal e formato. O prompt final deve mencionar como cada referência será usada somente quando houver referência selecionada e respeitar o role declarado.

Para Display, trate o formato IAB informado como uma unidade publicitária final — não o transforme em pôster ou interface. Para CTV, trate como still cinematográfico 16:9. Para social, preserve área segura e leitura no feed. Escreva uma cena específica, não adjetivos vagos como “moderno”, “bonito” ou “impactante”. Prefira detalhes observáveis: lugar, hora, enquadramento, distância de câmera, gesto, textura e espaço para copy.

Use a marca, briefing, referências e ativos do contexto como fonte de verdade. Cada substantivo concreto do briefing é obrigatório: anunciante, produto, embalagem, pessoas, cenário, ação, mensagem, preço, volume e formato não podem ser omitidos ou substituídos por uma cena genérica. Se o briefing pede produto visível, descreva-o como assunto principal em primeiro plano, com escala, luz e enquadramento suficientes para ser reconhecível. Mantenha todo logo, texto, embalagem e elemento de marca inteiro dentro da margem segura do formato; nunca corte, encoste ou esconda esses elementos na borda. Se o usuário pediu um logo mas nenhum ativo oficial está disponível, mantenha no prompt a instrução de reservar uma área limpa e identifique a marca que deverá ser aplicada posteriormente. Não invente dados comerciais além dos que o usuário informou. Se não houver texto literal aprovado, peça espaço reservado para a assinatura, sem fabricar tipografia. Todo texto publicitário visível deve ser português do Brasil; se a renderização textual não for confiável, instrua a manter a área livre para composição posterior. Não inclua marca d'água, interface de plataforma, mockup de dashboard ou logos de terceiros. Não use pessoas identificáveis sem necessidade. Preserve briefing, marca, canal e formato.
 Antes de devolver cada direção, faça uma revisão final como diretor: confirme que o prompt está fiel ao pedido, respeita todas as exclusões explícitas, usa cada referência conforme seu source e role, não inventa informações e está pronto para ser enviado ao gerador de imagem. O campo "prompt" deve ser a instrução final revisada para o processador de imagem, sem comentários sobre esta revisão. Inclua também "reference_plan" como uma lista curta de objetos {{"label":"...","source":"global|user|project","use":"...","layout":{{"subject_zone":"...","headline_zone":"...","support_zone":"...","safe_margin":"...","layer_order":"...","alignment":"..."}}}} para tornar a decisão de cada referência auditável. O campo layout é obrigatório para source="global" e opcional para os demais.

TEXTO DA PEÇA (você edita, pensando na peça e não só no pedido): contexto.orcamento_de_texto diz quanto texto cabe neste tamanho. Devolva em cada direção o campo "copy": {{"headline":"...","support":["..."],"cta":"..."}} com o texto final que vai na arte. Use somente palavras do pedido, na mesma ordem e grafia (acentos, números, %, cupom): você pode cortar palavras, trechos e linhas inteiras para caber no orçamento, mas nunca reescrever, traduzir, abreviar nem inventar. Ordem de corte (corte primeiro o que vem antes): palavras de ligação > nome da marca (o logo já a identifica) > detalhes e prazos > benefício. Número, %, preço, cupom e o nome da oferta nunca saem do título. Se o pedido já cabe, repita-o como está. Sem título no pedido, devolva "copy": null. Apoio além de apoio_max_linhas e CTA quando cta_max_palavras for 0 ficam de fora. O prompt da direção descreve apenas este texto editado, nunca o excedente."""


def credit_context(modeling, client_id, user_id):
    from ..cadu_credit_connector import CaduCreditConnector, CreditActor
    payer = modeling._credits_crm_id(client_id) or int(client_id)
    credits = getattr(modeling, "credit_connector", None) or CaduCreditConnector(modeling.credit_ledger)
    return credits, CreditActor.from_values(payer, user_id)


def assert_available(client_id, user_id, count, reference_count=0):
    from ..creative_modeling_service import CreativeModelingService
    modeling = CreativeModelingService()
    credits, actor = credit_context(modeling, client_id, user_id)
    credits.authorize(actor, estimated_tokens(count, reference_count))
    return actor.client_id


def charge(provider_result, client_id, user_id, count, project_id, run_id=None,
           reference_count=0,
           studio_session_id="", studio_root_session_id=""):
    from ..creative_modeling_service import CreativeModelingService
    modeling = CreativeModelingService()
    credits, actor = credit_context(modeling, client_id, user_id)
    credits.authorize(actor, estimated_tokens(count, reference_count))
    run_id = str(run_id or uuid4().hex)
    charged = credits.charge_provider(
        actor=actor, idempotency_key=f"studio:directions:{run_id}",
        app="Cadu Studio", stage="creative_directions", provider_result=provider_result,
        model=str(provider_result.get("model") or MODEL) if isinstance(provider_result, dict) else MODEL,
        metadata={
            "project_id": str(project_id or ""), "directions": int(count), "run_id": run_id,
            "reference_count": max(0, min(int(reference_count or 0), MAX_IMAGE_REFERENCES)),
            "studio_session_id": str(studio_session_id or ""),
            "studio_root_session_id": str(studio_root_session_id or studio_session_id or ""),
            # Direction drafting and the final prompt review happen inside the
            # same metered provider call. Its complete usage is charged once.
            "prompt_review_included": True,
            "prompt_review_mode": "same_provider_call",
        },
        margin_multiplier=1,
    ) or {}
    return int(charged.get("tokens_cobrados") or 0), credits.balance(actor.client_id)


def create_image(payload, modeling, client_id, user_id):
    """Generate one Studio still with explicit reference roles and mask-safe composition."""
    data = payload if isinstance(payload, dict) else {}
    prompt = clean_prompt(data.get("prompt"), 4000)
    if not prompt:
        raise ValueError("Descreva a imagem que deseja gerar.")
    aspect_ratio = str(data.get("aspect_ratio") or "1:1")
    if aspect_ratio not in {"1:1", "4:5", "9:16", "16:9"}:
        try:
            ratio_width, ratio_height = (float(part) for part in aspect_ratio.split(":", 1))
            if ratio_width <= 0 or ratio_height <= 0:
                raise ValueError
        except (TypeError, ValueError, ZeroDivisionError):
            raise ValueError("Formato de imagem inválido.")
    raw_references = data.get("references") if isinstance(data.get("references"), list) else []
    creation_intent = str(data.get("creation_intent") or "branded_creative").strip().lower()
    if creation_intent not in {"branded_creative", "neutral_asset"}:
        creation_intent = "branded_creative"
    typeset_social = getattr(modeling, "typeset_social", None)
    typeset_social = SOCIAL_TYPESET if typeset_social is None else bool(typeset_social)
    # Lab v5: a layout by position (elements and relations) replaces the box mask; its sketch is the reference image.
    from . import position_layouts
    position_id = str(data.get("position_layout") or "")
    position_spec = position_layouts.spec(position_id) if position_id else None
    if position_spec and data.get("position_sketch", True) is not False and \
            len([item for item in raw_references if isinstance(item, dict)]) < MAX_IMAGE_REFERENCES:
        raw_references = [*raw_references, {"id": f"position-{position_id}", "url": position_layouts.sketch_data_url(position_id),
                                            "role": "composition", "source": "global", "label": f"Posições · {position_spec['family_label']}"}]
    auto_mask = None if position_spec else display_mask_reference(
        data, raw_references, integer(data.get("width"), 0), integer(data.get("height"), 0), creation_intent, social=typeset_social)
    if auto_mask:
        raw_references = [*raw_references, auto_mask]

    def layout_specs():
        return [position_spec] if position_spec else mask_specs(raw_references)
    visual_reference = uses_user_visual_reference([
        clean_direction_reference(item, index)
        for index, item in enumerate(raw_references[:MAX_IMAGE_REFERENCES]) if isinstance(item, dict)
    ])
    # No logo: a mask drawn without one, a layout by position without one, or a piece the request signs elsewhere
    # (institutional teaser, campaign without signature).
    logo_free = (mask_logo_policy(raw_references) == "none" or bool(position_spec and position_spec["logo"] == "none")
                 or bool(data.get("logo_free")))
    if logo_free:
        data["brand_context"] = brand_without_logo(data.get("brand_context"))
    # The model redraws logos and tends to hug the edge. When the official logo file
    # is readable, the Studio applies it after generation instead of sending it as a reference.
    brand_logo = load_brand_logos(data.get("brand_context")) if creation_intent == "branded_creative" and not data.get("mask") else None
    brand_logo = brand_logo or None
    logo_corner = (position_spec["logo"] if position_spec else logo_position(raw_references)) if brand_logo else ""
    try:
        provider_source_references = (
            references_with_brand_logo(raw_references, data.get("brand_context"))
            if creation_intent == "branded_creative" and not data.get("mask") and not brand_logo else raw_references
        )
        references = normalize_image_references(provider_source_references, modeling.storage)
    except Exception as error:
        setattr(error, "studio_phase", "image_reference")
        raise
    mask = str(data.get("mask") or "")
    mask_node_id = text(data.get("mask_node_id"), 160)
    primary = next((item for item in references if item["role"] == "primary"), None)
    if mask and not primary:
        raise ValueError("A seleção precisa estar ligada a uma imagem principal.")
    if mask and mask_node_id and primary.get("id") != mask_node_id:
        raise ValueError("A área marcada não pertence à imagem principal deste pedido.")
    request_id = image_request_id(data)

    # Fail before a paid provider call whenever the request cannot be billed or
    # composed.  Masked edits need a local source because the original pixels
    # are used as the preservation layer after generation.
    requested_quality = str(data.get("quality") or "Padrão").strip().lower()
    quality_map = {
        "econômica": ("low", "1K", "draft"), "economica": ("low", "1K", "draft"),
        "padrão": ("medium", "1K", "draft"), "padrao": ("medium", "1K", "draft"),
        "alta": ("high", "2K", "publish"),
    }
    provider_quality, provider_resolution, billing_fidelity = quality_map.get(
        requested_quality, ("medium", "1K", "draft"),
    )
    from .size_plan import plan as early_size_plan
    from .studio_costs import image_estimate_usd
    early_width, early_height = integer(data.get("width"), 0), integer(data.get("height"), 0)
    early_sizing = early_size_plan(early_width, early_height, provider_quality) if early_width and early_height else None
    estimate = image_estimate_usd(provider_quality, early_sizing["generation"] if early_sizing else provider_canvas(aspect_ratio), len(references))
    from ..cadu_tool_billing import cost_token_equivalent
    credits, actor = credit_context(modeling, client_id, user_id)
    try:
        credits.authorize(actor, cost_token_equivalent(estimate, margin_multiplier=1))
    except Exception as error:
        setattr(error, "studio_phase", "image_credit")
        raise
    if mask and primary:
        primary["data"] = materialize_reference(primary["data"], modeling.storage)
        validate_mask(primary["data"], mask)

    role_lines = [
        f"IMAGE {index}: source={item['source']}; {item.get('instruction') or IMAGE_ROLES[item['role']]} ({item['label']})."
        for index, item in enumerate(references, start=1)
    ]
    reference_plan = data.get("reference_plan") if isinstance(data.get("reference_plan"), list) else []
    plan_lines = []
    for item in reference_plan[:4]:
        if not isinstance(item, dict) or not text(item.get('use'), 260):
            continue
        line = f"{text(item.get('label'), 120)} [{text(item.get('source'), 16)}]: {text(item.get('use'), 260)}"
        layout = item.get("layout") if isinstance(item.get("layout"), dict) else {}
        if layout:
            line += " | layout: " + "; ".join(
                f"{key}={text(value, 180)}" for key, value in layout.items() if text(value, 180)
            )
        plan_lines.append(line)
    if mask and len(references) == 1:
        edit_guard = (
            "IMAGE 2 is a black-and-white selection mask for IMAGE 1. Change only the white region, "
            "blend its boundary naturally and preserve the black region."
        )
    elif mask:
        edit_guard = (
            "The translucent mint overlay on IMAGE 1 marks the only region that may change. "
            "Use IMAGE 2 according to its declared role and blend the edited boundary naturally."
        )
    else:
        edit_guard = "Respect the declared role of every image. Never silently swap the base image and a supporting reference."
    edit_guard += (
        " Apart from the supplied official brand logo, never add third-party logos, prices or offers that the user did not request."
    )
    channel = str(data.get("channel") or "").strip()[:32]
    try:
        direction_intensity = max(0, min(int(data.get("direction_intensity") or 70), 100))
    except (TypeError, ValueError):
        direction_intensity = 70
    width = integer(data.get("width"), 0)
    height = integer(data.get("height"), 0)
    if bool(width) != bool(height):
        raise ValueError("Informe largura e altura do formato.")
    if width and height:
        assert_masks_fit_format(raw_references, width, height)
    # Every ad size is accepted, down to the 88x31 micro bar and the 320x50 / 300x50 mobile banners.
    if (width and not MIN_SIDE_PX <= width <= 7680) or (height and not MIN_SIDE_PX <= height <= 7680):
        raise ValueError(f"Dimensões do formato fora do limite permitido ({MIN_SIDE_PX} a 7680 px por lado).")
    supplied_logo = official_logo_reference(data.get("brand_context")) if creation_intent == "branded_creative" else None
    identity_safe_area = (
        "NEUTRAL ASSET CHECK: Do not reserve space for a logo, headline, price, product packshot or brand lockup unless the user explicitly asks for that element."
        if creation_intent == "neutral_asset" else
        "VISUAL REMIX IDENTITY CHECK: Use the supplied approved logo exactly as provided, fully inside the safe margin, without redrawing or cropping it."
        if visual_reference and supplied_logo else
        "VISUAL REMIX IDENTITY CHECK: The user reference is sufficient visual evidence for this remix. "
        "Do not reserve a project-logo area or invent a project logo unless the briefing explicitly requests one."
        if visual_reference else
        "LOGO CHECK: Before finishing, verify the supplied official logo is present once, unaltered, legible and fully inside the frame with breathing room. "
        "Keep headline text, product and packaging fully inside the selected format as well."
        if supplied_logo and not mask else
        ""
    )
    if logo_corner:
        identity_safe_area = (
            f"LOGO ZONE: leave the {logo_corner.replace('-', ' ')} corner clean for the official logo that is applied afterwards; "
            "do not draw any logo or brand name in the image, and keep headline text and the button out of that corner."
        )
    if logo_corner:
        prompt = strip_logo_clauses(prompt)
    requested_palette = clean_palette(data.get("requested_palette"))
    from .size_plan import plan as size_plan
    sizing = size_plan(width, height, provider_quality) if width and height else None
    provider_size = sizing["generation"] if sizing else provider_canvas(aspect_ratio)
    # Banners beyond 3:1 get the visual from the model and the typography from the Studio.
    from .banner_compose import extract_copy
    copy_headline, copy_cta = extract_copy(data.get("original_prompt") or prompt)
    briefing = data.get("original_prompt") or ""
    budget = studio_playbook.copy_budget(width, height)
    director_copy = studio_playbook.edited_copy(data.get("copy"), briefing, budget) if briefing else None
    if director_copy:
        # The director already fitted the briefing's copy to this size (cuts only, checked against the briefing).
        copy_headline, copy_cta = director_copy["headline"], director_copy["cta"]
    composed = bool(sizing and (position_spec or sizing["strategy"] == "composed" or display_typeset(width, height, typeset_social))
                    and not mask and layout_specs() and "headline" in layout_specs()[0]["zones"]
                    and copy_headline)
    if director_copy:
        support_copy = director_copy["support"]
    else:
        # No director copy: same rules by code — support to the budget, the offer line kept in the headline.
        copy_headline, support_copy = studio_playbook.protect(copy_headline, studio_playbook.support_copy(briefing),
                                                              briefing, budget["apoio_max_linhas"]) if copy_headline else (
            copy_headline, studio_playbook.support_copy(briefing)[:budget["apoio_max_linhas"]])
    layout_lines = (position_layouts.words(position_id, text_free=composed,
                                           palette=clean_palette(data.get("requested_palette"))
                                           or list((data.get("brand_context") or {}).get("palette") or []))
                    if position_spec
                    else composition_layout_lines(references, mask, provider_size, composed))
    product_visibility_line = (
        "PRODUCT VISIBILITY CHECK: If the briefing requests a product, make it a deliberate, recognizable foreground subject with enough scale and light to be clearly visible. Do not hide it behind hands, bodies, crops or depth-of-field blur. If bottles or packages are requested, show the requested quantity visibly and keep their labels facing the camera when the briefing asks for labels."
        if re.search(r"produto|product|embalag|garraf|frasco|bottle|package|pote\b|caixa", prompt, re.IGNORECASE) else ""
    )
    global_composition_line = (
        "GLOBAL COMPOSITION CHECK: When a global composition mask is supplied, treat its spatial architecture as binding: preserve the indicated subject/product zone, background field, headline band, support/price/CTA band, layer order, alignment and safe margins. Replace only the mask's placeholder subject with the product and facts from the briefing. Do not center or resize the product arbitrarily if that changes the reference hierarchy."
        if any(isinstance(item, dict) and item.get("source") == "global" for item in references) and not layout_lines else ""
    )
    visual_remix_line = (
        "VISUAL REMIX CHECK: When a user-supplied visual reference is present, make its observable visual language materially visible in the new piece. Combine it with the global mask's layout rather than choosing one reference and ignoring the other. Do not call the reference palette official brand colors or fabricate a brand mark from it."
        if visual_reference else ""
    )
    # One call: the binding layout (when a mask is used), then the scene, then short rules (the Lab showed long rule
    # blocks make the model add extras). A piece
    # whose copy the Studio typesets gets no copy rules at all: they only tempt the model to write.
    scene = studio_playbook.scene_only(prompt, [copy_headline, *support_copy, copy_cta]) if composed else prompt
    if position_spec:
        # The layout by position owns placement: the director's own placement sentences would contradict it.
        scene = studio_playbook.without_placement(scene)
    technical_prompt = "\n".join(line for line in [
        *(["TEXT-FREE IMAGE (overrides every other instruction about copy): this image must contain no words, letters, numbers, buttons or logos. Ignore any request below to render a headline, CTA or brand name: the Studio typesets them afterwards."] if composed else []),
        *layout_lines,
        scene,
        studio_playbook.ad_craft_line(text_free=composed),
        crop_safe_zone_line(aspect_ratio, width, height, provider_size),
        "BRIEF FIDELITY: keep every concrete element of the brief (product, packaging, people, setting, action); a composition reference only guides placement and never replaces the requested subject.",
        *([] if composed else ["VISIBLE TEXT: only the literal copy below and the official logo; no subheadlines, lists, statistics, badges, dates or small print the brief did not write."]),
        brand_identity_guard(data.get("brand_context"), visual_reference=visual_reference, creation_intent=creation_intent, editing=bool(mask), logo_corner=logo_corner, logo_free=logo_free),
        f"REQUESTED CREATIVE PALETTE: {', '.join(requested_palette)}. Use these colors for this piece's campaign mood only; they are not a claim about official brand identity and must not erase the official brand colors or logo." if requested_palette else "",
        *studio_playbook.prompt_lines([copy_headline, *support_copy, copy_cta], text_free=composed),
        "\nREFERENCE CONTRACT:",
        *(role_lines or ["No image reference was supplied; create an original image."]),
        *(["DIRECTOR REFERENCE PLAN:", *plan_lines] if plan_lines else []),
        edit_guard,
        product_visibility_line,
        identity_safe_area,
        global_composition_line,
        visual_remix_line,
        (f"FORMAT: {width}x{height}px ({aspect_ratio}){', channel ' + channel if channel else ''}; this format overrides any size written in the brief."
         if width and height else f"FORMAT: aspect ratio {aspect_ratio}{', channel ' + channel if channel else ''}; this format overrides any size written in the brief."),
        *([f"FINAL LOGO CHECK: the image must contain no logo, wordmark, monogram or brand name of any company; the {logo_corner.replace('-', ' ')} corner stays plain background."] if logo_corner else []),
        *(["FINAL LOGO CHECK: this composition has no logo; the image must contain no logo, wordmark, monogram or brand name."] if logo_free else []),
        *([final_layout_check(references, provider_size, composed)] if layout_lines else []),
    ] if line)
    provider_references = provider_image_references(references_with_provider_masks(references, provider_size), mask)
    def render(prompt_text, references=None, quality=None):
        try:
            result = modeling.generator.generate_image(
                prompt_text,
                provider_references if references is None else references,
                aspect_ratio=aspect_ratio,
                quality=quality or provider_quality,
                resolution=provider_resolution,
                model=IMAGE_MODEL,
                max_input_references=MAX_IMAGE_REFERENCES,
                size=f"{provider_size[0]}x{provider_size[1]}" if sizing else None,
            )
        except Exception as error:
            setattr(error, "studio_phase", "image_provider")
            raise
        image = result.get("b64_json")
        if not image:
            raise ValueError("O gerador não devolveu uma imagem.")
        fmt = result.get("output_format") or "png"
        if mask and primary:
            try:
                image, fmt = compose_inside_mask(image, primary["data"], mask), "png"
            except Exception as error:
                setattr(error, "studio_phase", "image_storage")
                raise
        return result, image, fmt

    def fit_to(raw, fmt, target_w, target_h):
        """One generation serves every delivery size (1x and 2x)."""
        if mask or not (target_w and target_h):
            return raw
        try:
            # A composition mask is drawn on the provider canvas with the final frame marked, so trim exactly to it.
            return fit_generated_output(raw, target_w, target_h, fmt, max_trim=0.5 if mask_specs(raw_references) else None)
        except Exception as error:
            setattr(error, "studio_phase", "image_storage")
            raise

    chosen_layout = {"spec": None}

    def finish(fitted, fmt):
        """Logo and code-set typography on top of a fitted image; returns (piece, base, layers)."""
        piece_layers = None
        layout = None
        if composed:
            from . import banner_compose
            # The copy goes where this picture is calm (or on the painted band), not where the model was told to leave room.
            # A layout by position is the design itself: only mirrored when the model put the subject on the copy side.
            picture = banner_compose.decode(fitted).convert("RGB")
            layout = (banner_compose.place_position(picture, position_spec) if position_spec
                      else banner_compose.choose_layout(picture, mask_specs(raw_references)[0]))
            chosen_layout["spec"] = layout

        def with_logo(encoded_image, encoded_format):
            if not (brand_logo and not mask):
                return encoded_image
            specs = [layout] if layout else layout_specs()
            rect = next((spec["zones"]["logo"] for spec in specs if "logo" in spec["zones"]), None)
            return apply_brand_logo(encoded_image, encoded_format, brand_logo, logo_corner, rect=rect)

        base = with_logo(fitted, fmt)
        piece = base
        if composed:
            palette = clean_palette(data.get("requested_palette")) or list((data.get("brand_context") or {}).get("palette") or [])
            image, piece_layers = banner_compose.render_text_layers(
                banner_compose.decode(fitted), layout, copy_headline, copy_cta,
                data.get("brand_context") or {}, palette, support=support_copy,
            )
            # The logo goes last: the composer paints the text panel, which would otherwise cover it.
            piece = with_logo(banner_compose.encode(image, "png"), "png")
        return piece, base, piece_layers

    review_enabled = not mask and studio_review.enabled(modeling)
    if review_enabled:
        # A composed piece carries the support line only where the layout has room for it (not in wide strips).
        from . import banner_compose as _compose
        support = support_copy if not composed or _compose.renders_support(layout_specs()[0]) else []
        required_text = [item for item in (copy_headline, *support, copy_cta) if item]
        review_args = dict(
            # The piece is judged against what it is meant to carry: the director's scene and the copy fitted to this
            # size, not the raw briefing (whose excess the director cut on purpose for small formats).
            prompt="\n".join(line for line in [
                scene,
                ("Texto final da peça: " + " / ".join(item for item in (copy_headline, *support_copy, copy_cta) if item))
                if copy_headline else "",
                f"Formato: {width}x{height}px." if width and height else "",
            ] if line) or data.get("original_prompt") or prompt,
            allowed_text=" ".join(item for item in (data.get("original_prompt") or "", prompt) if item),
            required_text=required_text,
            palette=clean_palette(data.get("requested_palette")) or list((data.get("brand_context") or {}).get("palette") or []),
            brand_name=str((data.get("brand_context") or {}).get("name") or ""),
            forbidden=list((data.get("brand_context") or {}).get("forbidden_elements") or []),
            # The official logo is either set by the Studio after generation, drawn by the model from the reference, or absent.
            logo_mode="none" if logo_free or creation_intent != "branded_creative" else "composed" if brand_logo
            else "in_image" if any(item.get("role") == "identity" or "logo" in str(item.get("label") or "").lower()
                                   for item in raw_references if isinstance(item, dict)) else "none",
            has_cta=bool(copy_cta),
            refine=bool(getattr(modeling, "refine_target", None)),
            text_free=composed,
        )

        def reviewed(candidate_encoded, candidate_format, structure=False):
            try:
                piece_b64, _base, piece_layers = finish(candidate_encoded, candidate_format)
                args = dict(review_args)
                if structure:
                    # The draft has no copy yet (unless the Studio typesets it): judge only its structure.
                    args["required_text"] = []
                if piece_layers is not None:
                    # Typeset copy: require exactly what the composer drew (a support line may not fit the zone).
                    # Whole phrases as drawn (kicker in caps, hero, support, button): found whether the eyes transcribe
                    # a wrapped title as one line or several (measured: word-per-line strings scored text 0.04).
                    args["required_text"] = [line for layer in piece_layers
                                             for line in (layer.get("phrases") or layer.get("lines")
                                                          or str(layer.get("text") or "").split("\n")) if line]
                return studio_review.review(image_b64=piece_b64, **args)
            except Exception:
                logger.warning("Studio review failed request=%s", request_id, exc_info=True)
                return {"reviewed": False, "approved": True, "score": None, "reason": "", "reason_text": ""}

    # Two image calls instead of one: a cheap low-quality draft of the structure only (short prompt), our partial
    # review of it, then the finishing edit at the requested quality that completes the piece with the review's fixes.
    # A further variation skips the draft and edits a finished piece of the same request.
    base_palette = clean_palette(data.get("requested_palette")) or list((data.get("brand_context") or {}).get("palette") or [])
    draft_prompt = "\n".join(line for line in [
        studio_review.DRAFT_HEADER,
        *layout_lines,
        crop_safe_zone_line(aspect_ratio, width, height, provider_size),
        prompt,
        f"BASE PALETTE: {', '.join(base_palette)}." if base_palette else "",
        "\nREFERENCE CONTRACT:",
        *(role_lines or ["No image reference was supplied; create an original image."]),
        product_visibility_line,
        global_composition_line,
        f"Output aspect ratio: {aspect_ratio}.",
        *([final_layout_check(references, provider_size, composed)] if layout_lines else []),
    ] if line)
    variation_base = variation_reference(data, modeling)
    passes = []
    if variation_base and not mask:
        provider, raw, output_format = render(studio_review.variation_prompt(aspect_ratio) + "\n\n" + technical_prompt,
                                              [compact_provider_reference(variation_base), *provider_references[:MAX_IMAGE_REFERENCES - 1]])
        passes = ["variation"]
    elif (TWO_PASS if getattr(modeling, "two_pass", None) is None else modeling.two_pass) and not mask:
        _draft_provider, draft_raw, draft_format = render(draft_prompt, quality=DRAFT_QUALITY)
        partial = reviewed(fit_to(draft_raw, draft_format, width, height), draft_format, structure=True) if review_enabled else None
        logger.info("Studio draft request=%s reviewed=%s reason=%s", request_id, bool(partial and partial.get("reviewed")),
                    (partial or {}).get("reason") or "-")
        draft_base = compact_provider_reference(f"data:image/{draft_format or 'png'};base64,{draft_raw}")
        provider, raw, output_format = render(studio_review.finish_prompt(partial, aspect_ratio) + "\n\n" + technical_prompt,
                                              [draft_base, *provider_references[:MAX_IMAGE_REFERENCES - 1]])
        passes = ["draft", "finish"]
    else:
        provider, raw, output_format = render(technical_prompt)
    encoded = fit_to(raw, output_format, width, height)
    if sizing and not mask and MARGIN_QA_ENABLED:
        # Elements the model drew outside the safe frame get one corrected attempt (charged once).
        safe = safe_frame(raw_references, int(width), int(height))
        edges = margin_violations(encoded, safe, getattr(modeling.generator, "text_callable", None))
        logger.info("Studio margin check request=%s edges=%s", request_id, ",".join(edges) or "none")
        if edges:
            logger.info("Studio margin check failed edges=%s; regenerating once", ",".join(edges))
            provider, raw, output_format = render(technical_prompt + "\n" + margin_correction(edges, safe))
            encoded = fit_to(raw, output_format, width, height)
    review_info = None
    if review_enabled:
        # Version 1 comes from the Studio prompt; every further version is an edit of the best one so far that
        # fixes what the reviewer found (and, when refining, what it would improve). Only the delivered version is billed.
        attempts = studio_review.max_attempts(modeling)
        best = {"provider": provider, "raw": raw, "format": output_format, "encoded": encoded, "verdict": reviewed(encoded, output_format), "version": 1}
        first_verdict = best["verdict"]
        log = [studio_review.attempt_entry(1, first_verdict, "studio_prompt")]
        logger.info("Studio auto review request=%s version=1 approved=%s reason=%s score=%s",
                    request_id, best["verdict"]["approved"], best["verdict"].get("reason") or "-", best["verdict"].get("score"))
        version, latest = 1, best
        while version < attempts and studio_review.wants_another(latest["verdict"], modeling):
            version += 1
            try:
                # Each edit starts from the latest version (the chain keeps what was already fixed); the best is delivered.
                # A broken safe margin is a layout problem that prompt edits do not move: shrink the picture by code
                # and let the model only outpaint the border.
                # Once per chain: shrinking again compounds and softens the copy.
                factor = (studio_review.reframe_factor(latest["verdict"].get("observation") or {})
                          if latest["verdict"].get("reason") == "margin" and not any(item.get("source") == "reframe" for item in log) else None)
                if factor:
                    base = compact_provider_reference(shrink_into_border(latest["raw"], factor))
                    provider_n, raw_n, format_n = render(studio_review.reframe_prompt(aspect_ratio), [base])
                else:
                    base = compact_provider_reference(f"data:image/{latest['format'] or 'png'};base64,{latest['raw']}")
                    provider_n, raw_n, format_n = render(studio_review.edit_prompt(latest["verdict"], aspect_ratio),
                                                         [base, *provider_references[:MAX_IMAGE_REFERENCES - 1]])
                encoded_n = fit_to(raw_n, format_n, width, height)
                verdict_n = reviewed(encoded_n, format_n)
            except Exception:
                logger.warning("Studio version %s failed request=%s; keeping version %s", version, request_id, best["version"], exc_info=True)
                log.append({"version": version, "failed": True})
                break
            latest = {"provider": provider_n, "raw": raw_n, "format": format_n, "encoded": encoded_n, "verdict": verdict_n, "version": version}
            better = studio_review.prefer_second(best["verdict"], verdict_n)
            log.append({**studio_review.attempt_entry(version, verdict_n, "reframe" if factor else "edit"), "best": better})
            logger.info("Studio auto review request=%s version=%s approved=%s reason=%s score=%s best=%s",
                        request_id, version, verdict_n["approved"], verdict_n.get("reason") or "-", verdict_n.get("score"), better)
            if better:
                best = latest
        provider, raw, output_format, encoded = best["provider"], best["raw"], best["format"], best["encoded"]
        final = best["verdict"]
        # ``reason`` explains why version 1 was not delivered as is; the delivered version's state is in the rest.
        review_info = {"reviewed": final["reviewed"], "approved": final["approved"], "retried": version > 1,
                       "score": final.get("score"), "reason": first_verdict.get("reason"), "reason_text": first_verdict.get("reason_text"),
                       "final_reason": final.get("reason") or "",
                       "delivered": "first" if best["version"] == 1 else "second" if best["version"] == 2 else f"v{best['version']}",
                       "delivered_version": best["version"], "attempts": log, **({"fix": "edit"} if version > 1 else {})}
        if len(log) > 1 and log[1].get("score") is not None:
            review_info["second_score"] = log[1]["score"]
        if any(item.get("failed") for item in log):
            review_info["retry_failed"] = True
    image_url_2x, file_kb, file_kb_2x, variation_base_url = None, None, None, None
    try:
        from .export import save_sibling, smallest_encoding
        budget = sizing["weight_budget_kb"] if sizing else None
        piece, base_encoded, layers = finish(encoded, output_format)
        # Masked edits stay lossless PNG: the same file is edited again and again.
        piece, delivered_format, file_kb = (piece, output_format, None) if mask else smallest_encoding(piece, budget)
        image_url = modeling.storage.save_generated_base64(piece, delivered_format)
        if sizing and sizing.get("delivery_2x") and not mask:
            # Display units ship a 2x for high-density screens, cut from the same generation.
            piece_2x, _, _ = finish(fit_to(raw, output_format, *sizing["delivery_2x"]), output_format)
            piece_2x, format_2x, file_kb_2x = smallest_encoding(piece_2x, budget)
            image_url_2x = save_sibling(image_url, "@2x", piece_2x, format_2x)
        if layers is not None:
            from . import banner_compose
            banner_compose.save_layers(image_url, base_encoded, layers, chosen_layout["spec"] or layout_specs()[0])
        # The finished picture (provider canvas, before logo and code typography): the base of further variations.
        try:
            variation_base_url = None if mask else save_sibling(image_url, "@base", raw, output_format)
        except Exception:
            # Only a convenience for further variations: never blocks the delivery.
            logger.warning("Studio variation base not saved request=%s", request_id, exc_info=True)
    except Exception as error:
        setattr(error, "studio_phase", "image_storage")
        raise
    try:
        charged = modeling._charge_studio_call(
            client_id=client_id,
            user_id=user_id,
            idempotency_key=f"studio:create-image:{request_id}",
            stage="image_generation",
            provider_result=provider,
            fallback_cost=estimate,
            media=True,
            metadata={
                "project_id": str(data.get("project_id") or ""),
                "aspect_ratio": aspect_ratio,
                "reference_roles": [item["role"] for item in references],
                "reference_count": len(references),
                "estimate_includes_references": True,
                "masked": bool(mask),
                "studio_session_id": text(data.get("studio_session_id"), 80),
                "studio_root_session_id": text(
                    data.get("studio_root_session_id") or data.get("studio_session_id"), 80,
                ),
            },
        ) or {}
    except Exception as error:
        setattr(error, "studio_phase", "image_billing")
        raise
    try:
        remaining = credits.balance(actor.client_id)
    except Exception:
        remaining = None
    return {
        "image_url": image_url,
        "model": provider.get("model") or IMAGE_MODEL,
        "charged_credits": int(charged.get("tokens_cobrados") or 0),
        "remaining_credits": remaining,
        "masked": bool(mask),
        **({"review": review_info} if review_info else {}),
        **({"layers": layers, "composed": True} if layers is not None else {}),
        **({"image_url_2x": image_url_2x} if image_url_2x else {}),
        **({"variation_base": variation_base_url} if variation_base_url else {}),
        "passes": passes,
        "file_kb": file_kb,
        **({"file_kb_2x": file_kb_2x} if file_kb_2x else {}),
    }


def normalize_image_references(raw, storage):
    references = raw if isinstance(raw, list) else []
    if len(references) > MAX_IMAGE_REFERENCES:
        raise ValueError(f"Use no máximo {MAX_IMAGE_REFERENCES} imagens neste pedido.")
    cleaned = []
    for index, item in enumerate(references):
        if not isinstance(item, dict):
            continue
        value = str(item.get("url") or "")
        source = "global" if value.startswith("/static/images/cadu/studio/references/") else str(item.get("source") or "user")
        role = str(item.get("role") or ("primary" if index == 0 else "insert"))
        if role == "reference" and source == "global":
            role = "composition"
        if role not in IMAGE_ROLES:
            raise ValueError("A função de uma das imagens é inválida.")
        value = str(item.get("url") or "")
        if value.startswith("data:image/"):
            image_data = value
        elif value.startswith("/static/uploads/creative_generated/"):
            image_data = value
        elif value.startswith("/static/uploads/creative_references/"):
            image_data = value
        elif value.startswith("/static/images/cadu/studio/references/"):
            from flask import current_app
            from pathlib import Path
            relative = value.removeprefix("/static/")
            path = (Path(current_app.static_folder) / relative).resolve()
            static_root = Path(current_app.static_folder).resolve()
            try:
                path.relative_to(static_root)
            except ValueError:
                raise ValueError("Imagem de referência não encontrada.")
            if not path.is_file():
                raise ValueError("Imagem de referência não encontrada.")
            image_data = value
        elif value.startswith("/static/") and ".." not in value:
            # Official brand logos and other Studio-owned assets live under
            # other /static/ folders; the provider can only fetch them by
            # their public URL, resolved in provider_image_references.
            image_data = value
        elif value.startswith(("https://", "http://")):
            from ..creative_modeling_storage import _validated_public_asset_url, studio_owned_static_path
            # A just-uploaded piece is already a canonical Studio URL. Keep it
            # URL-first without DNS validation or an accidental conversion to
            # base64; only third-party URLs take the public-host validation path.
            image_data = value if studio_owned_static_path(value) else _validated_public_asset_url(value)
        else:
            raise ValueError("Uma das imagens relacionadas não está disponível.")
        cleaned.append({
            "id": text(item.get("id"), 160),
            "role": role,
            "source": "global" if value.startswith("/static/images/cadu/studio/references/") else str(item.get("source") or "user") if str(item.get("source") or "user") in {"user", "project"} else "user",
            "label": text(item.get("label") or f"Imagem {index + 1}", 120),
            "instruction": text(item.get("instruction"), 300),
            "data": image_data,
        })
    if sum(1 for item in cleaned if item["role"] == "primary") > 1:
        raise ValueError("Escolha somente uma imagem principal.")
    return sorted(cleaned, key=lambda item: item["role"] != "primary")


def materialize_reference(value, storage):
    """Load pixels only for local operations such as masks.

    Normal generation keeps references URL-first so the Studio does not build
    multi-megabyte base64 strings merely to pass an already public asset on.
    """
    raw = str(value or "")
    # Uploaded pieces travel through Studio as public URLs after persistence.
    # A mask still needs pixels locally, so map only our own canonical URL back
    # to its trusted static path; arbitrary remote URLs remain remote.
    from ..creative_modeling_storage import studio_owned_static_path
    raw = studio_owned_static_path(raw) or raw
    if raw.startswith("data:image/"):
        return raw
    if raw.startswith("/static/uploads/creative_generated/"):
        return storage.generated_as_data_url(raw)
    if raw.startswith("/static/uploads/creative_references/"):
        return storage.reference_as_data_url(raw, image_mime(raw))
    if raw.startswith("/static/images/cadu/studio/references/"):
        from flask import current_app
        from pathlib import Path
        path = (Path(current_app.static_folder) / raw.removeprefix("/static/")).resolve()
        static_root = Path(current_app.static_folder).resolve()
        try:
            path.relative_to(static_root)
        except ValueError as exc:
            raise ValueError("Imagem de referência não encontrada.") from exc
        if not path.is_file():
            raise ValueError("Imagem de referência não encontrada.")
        mime = image_mime(path)
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    raise ValueError("A imagem principal precisa estar disponível no Studio para usar máscara.")


def image_request_id(payload):
    data = payload if isinstance(payload, dict) else {}
    request_id = str(data.get("request_id") or uuid4().hex)
    if not _REQUEST_ID.fullmatch(request_id):
        raise ValueError("Identificador do pedido inválido.")
    return request_id


def validate_mask(source_data_url, mask_data_url):
    source = _data_image(source_data_url)
    mask = _data_image(mask_data_url).convert("L")
    if mask.size != source.size:
        raise ValueError("A seleção não corresponde ao tamanho da imagem principal.")
    if not mask.getbbox():
        raise ValueError("Marque uma área antes de gerar.")


def _provider_reference_value(value):
    """Give the provider a fetchable image: public URL, or pixels when the host is not public."""
    raw = str(value or "")
    if not raw.startswith("/static/"):
        return raw
    from urllib.parse import urlparse
    from flask import current_app
    from pathlib import Path
    from ..creative_modeling_storage import public_studio_asset_url
    try:
        url = public_studio_asset_url(raw)
        host = (urlparse(url).hostname or "").lower()
        if host not in {"localhost", "127.0.0.1", "::1"} and not host.endswith((".localhost", ".test")):
            return url
    except ValueError:
        pass
    # Local development: the provider cannot reach this host, so embed the file.
    static_root = Path(current_app.static_folder).resolve()
    path = (static_root / raw.removeprefix("/static/")).resolve()
    try:
        path.relative_to(static_root)
    except ValueError:
        raise ValueError("Imagem de referência não encontrada.")
    if not path.is_file():
        raise ValueError("Imagem de referência não encontrada.")
    return f"data:{image_mime(path)};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def provider_image_references(references, mask):
    """Prepare up to three high-fidelity provider inputs for Studio V2."""
    values = [_provider_reference_value(item["data"]) for item in references[:MAX_IMAGE_REFERENCES]]
    if not mask or not references:
        return [compact_provider_reference(value) for value in values]
    primary = references[0]["data"]
    if len(values) == 1:
        # The selection mask must remain lossless and pixel-aligned. Only the
        # visual source is compacted for transport.
        return [compact_provider_reference(primary), mask]
    return [
        compact_provider_reference(marked_reference(primary, mask)),
        *[compact_provider_reference(value) for value in values[1:]],
    ]


def compact_provider_reference(value, max_side=1536, max_bytes=900_000):
    """Bound provider payloads without modifying the stored reference asset."""
    raw = str(value or "")
    if not raw.startswith("data:image/") or "," not in raw:
        return raw
    try:
        encoded = raw.split(",", 1)[1]
        content = base64.b64decode(encoded, validate=True)
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(content)))
        image.load()
    except (binascii.Error, OSError, ValueError) as exc:
        raise ValueError("Uma das referências de imagem é inválida.") from exc
    if len(content) <= max_bytes and max(image.size) <= max_side:
        return raw
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")
    output = io.BytesIO()
    try:
        image.save(output, "WEBP", quality=82, method=4)
        mime = "image/webp"
    except (OSError, ValueError):
        output = io.BytesIO()
        image.save(output, "PNG", optimize=True)
        mime = "image/png"
    compacted = output.getvalue()
    if len(compacted) >= len(content):
        return raw
    return f"data:{mime};base64,{base64.b64encode(compacted).decode('ascii')}"


def image_mime(value):
    suffix = str(value or "").lower().rsplit(".", 1)[-1]
    if suffix in {"jpg", "jpeg"}:
        return "image/jpeg"
    if suffix == "webp":
        return "image/webp"
    return "image/png"


def composition_layout_lines(references, mask="", provider_size=None, text_free=False):
    """Lead the prompt with the selected wireframe so it is not lost at the end."""
    if mask:
        return []
    indexes = [index for index, item in enumerate(references, start=1) if item.get("source") == "global"]
    if not indexes:
        return []
    index = indexes[0]
    from . import ad_masks
    spec = ad_masks.spec_from_url(references[index - 1].get("data"))
    if spec:
        return [ad_masks.layout_contract(spec, index, provider_size, text_free)]
    return [
        f"LAYOUT (binding, highest priority after the briefing): IMAGE {index} is an annotated layout wireframe, not artwork. "
        "Only the large inner rectangle inside its SAFE MARGIN guide is the ad canvas; the title, legend, layer-order column and notes around it are documentation and must not appear. "
        "Rebuild that inner rectangle's zone geometry in the final ad: the same split between image area and text area, the same position and relative size of the main subject, "
        "headline block, support text and CTA, and the same margins. Fill each zone with the briefing's content. "
        "Keep headline, text, logo, CTA and the main subject inside that same dashed guide; only background and full-bleed imagery may reach the edge. "
        "If the wireframe marks a LOGO zone, the official logo goes there. "
        "FULL BLEED: the artwork must fill the whole canvas edge to edge as ONE continuous picture. Do not draw full-width solid-colour bands, bars or panels along any edge to hold text or to complete the layout (this does NOT apply to the CTA button: keep it a solid, fully opaque, high-contrast pill with a clearly readable label in a brand accent color); "
        "the text zone is part of the photograph (calm area of the scene), never a separate flat strip. "
        "Never render the wireframe's grey placeholders, numbers, labels, sample words such as HEADLINE, LOGO or CTA, guide lines or its placeholder product (bottle, jar or box).",
    ]


LOGO_WIDTH_RATIO = 0.16
LOGO_HEIGHT_RATIO = 0.07
# The official logo honours the 8% safe margin on each axis (8% of the width at the sides, of the height top/bottom).
LOGO_MARGIN_RATIO = 0.08
LOGO_CORNER_EDGE_LIMIT = 9.0
LOGO_MIN_CONTRAST = 0.3


# Aspect ratio (width / height) of each shared composition-mask family.
GLOBAL_MASK_RATIOS = {
    "/static/images/cadu/studio/references/feed/": 1080 / 1350,
    "/static/images/cadu/studio/references/square-300x300/": 1.0,
    "/static/images/cadu/studio/references/iab-300x250/": 300 / 250,
}


def assert_masks_fit_format(references, width, height):
    """A composition mask only guides the format it was drawn for.

    Sending a 4:5 feed wireframe for a 1:1 or 16:9 piece makes the model force the wrong
    layout, so refuse it with a clear message instead of generating (and charging) a bad piece.
    """
    try:
        output_ratio = float(width) / float(height)
    except (TypeError, ValueError, ZeroDivisionError):
        return
    for item in references or []:
        url = str(item.get("url") or item.get("data") or "") if isinstance(item, dict) else ""
        from . import ad_masks
        spec = ad_masks.spec_from_url(url)
        if spec:
            if abs(spec["width"] / spec["height"] - output_ratio) > 0.02:
                raise ValueError(
                    "A composição escolhida é de outro formato. Escolha uma composição deste formato ou remova a seleção."
                )
            continue
        for prefix, ratio in GLOBAL_MASK_RATIOS.items():
            if url.startswith(prefix) and abs(ratio - output_ratio) > 0.02:
                raise ValueError(
                    "A composição escolhida é de outro formato. Escolha uma composição deste formato ou remova a seleção."
                )


def final_layout_check(references, provider_size=None, text_free=False):
    from . import ad_masks
    for item in references:
        spec = ad_masks.spec_from_url(item.get("data") or item.get("url")) if item.get("source") == "global" else None
        if spec:
            return ad_masks.final_check(spec, provider_size, text_free)
    return "FINAL LAYOUT CHECK: the composition must match the wireframe zones described at the top; if it does not, recompose before finishing."


# The image is made in two calls: a low-quality structure draft (always low, whatever the requested quality) and the
# finishing edit at the requested quality. CREATIVE_STUDIO_TWO_PASS=0 goes back to a single call.
# Off in the Studio until the Lab's A/B shows the gain; the Lab turns it on per run (LabModeling.two_pass).
TWO_PASS = os.getenv("CREATIVE_STUDIO_TWO_PASS", "0") == "1"
DRAFT_QUALITY = "low"


def variation_reference(data, modeling):
    """A finished piece of this request to vary from (only the Studio's own generated files), as a data URL."""
    url = str(data.get("variation_base") or "").split("?", 1)[0]
    if not url.startswith("/static/uploads/creative_generated/") or ".." in url:
        return None
    try:
        return modeling.storage.generated_as_data_url(url)
    except Exception:
        logger.warning("Studio variation base unavailable url=%s", url, exc_info=True)
        return None


# Display units get their headline, support line and CTA typeset by code (exact text, brand font, safe margin).
DISPLAY_TYPESET = os.getenv("CREATIVE_STUDIO_DISPLAY_TYPESET", "1") == "1"
# Layout used when the person did not pick a composition: a calm band carries the copy over the picture.
DISPLAY_FAMILIES = ("faixa-inferior", "foto-texto-base", "split", "texto-central")


# Feeds, stories and LinkedIn with the copy typeset by code too: off in the Studio until the Lab's A/B shows the gain.
SOCIAL_TYPESET = os.getenv("CREATIVE_STUDIO_SOCIAL_TYPESET", "0") == "1"
SOCIAL_TYPESET_FORMATS = {"feed-4x5", "feed-1x1", "story-9x16", "linkedin-1200x627"}


def display_format(width, height, social=False):
    from . import ad_masks
    size = (int(width or 0), int(height or 0))
    return next((key for key, value in ad_masks.FORMATS.items() if (value[1], value[2]) == size
                 and (value[3] == "iab" or (social and key in SOCIAL_TYPESET_FORMATS))), None)


def display_typeset(width, height, social=False):
    return DISPLAY_TYPESET and display_format(width, height, social) is not None


def display_mask_reference(data, raw_references, width, height, creation_intent, social=False):
    """The default composition mask for a display unit with copy, when none was picked (None otherwise)."""
    from . import ad_masks
    from .banner_compose import extract_copy
    if not display_typeset(width, height, social) or data.get("mask") or mask_specs(raw_references) or data.get("auto_mask") is False:
        return None
    if len([item for item in raw_references if isinstance(item, dict)]) >= MAX_IMAGE_REFERENCES:
        return None
    headline, cta = extract_copy(data.get("original_prompt") or data.get("prompt") or "")
    if not headline:
        return None
    brand = data.get("brand_context") if isinstance(data.get("brand_context"), dict) else {}
    has_logo = creation_intent == "branded_creative" and bool(brand.get("logo_url") or (brand.get("assets") or {}).get("logo"))
    options = [spec for spec in ad_masks.served_specs() if spec["format"] == display_format(width, height, social)]
    # The bottom band works whatever the model does with the picture (tested: a side panel covered the subject
    # the model put there, and copy over the photo fought it), so it leads; a support line goes in only if legible.
    def rank(spec):
        family = DISPLAY_FAMILIES.index(spec["family"]) if spec["family"] in DISPLAY_FAMILIES else len(DISPLAY_FAMILIES)
        return (spec["cta"] != bool(cta), (spec["logo"] != "none") != has_logo, family)
    if not options:
        return None
    spec = min(options, key=rank)
    return {"id": f"auto-mask-{spec['id']}", "url": ad_masks.MASK_URL_PREFIX + ad_masks.mask_filename(spec),
            "role": "composition", "source": "global", "label": f"Composição · {spec['family_label']}"}


def mask_specs(references):
    from . import ad_masks
    urls = [str(item.get("url") or item.get("data") or "") for item in references or [] if isinstance(item, dict)]
    return [spec for spec in (ad_masks.spec_from_url(url) for url in urls) if spec]


def mask_logo_policy(references):
    """'none' when a selected composition mask is drawn without logo space."""
    return "none" if any(spec["logo"] == "none" for spec in mask_specs(references)) else ""


def brand_without_logo(raw_brand):
    brand = dict(raw_brand) if isinstance(raw_brand, dict) else {}
    brand.pop("logo_url", None)
    assets = dict(brand.get("assets")) if isinstance(brand.get("assets"), dict) else {}
    assets["logo"], assets["logos"] = [], []
    brand["assets"] = assets
    return brand


def logo_position(references):
    """Square display masks put the brand mark top-left; everything else bottom-right."""
    for spec in mask_specs(references):
        if spec["logo"] != "none":
            return spec["logo"]
    urls = [str(item.get("url") or item.get("data") or "") for item in references or [] if isinstance(item, dict)]
    return "top-left" if any("square-mask" in url for url in urls) else "bottom-right"


def _open_trimmed_logo(url, palette=None):
    from pathlib import Path
    from flask import current_app, has_app_context
    from ..creative_modeling_storage import studio_owned_static_path
    if str(url).startswith("data:image/"):
        # An embedded logo (the Lab's LOGO reference when the brand record has no logo URL).
        try:
            content = base64.b64decode(str(url).split(",", 1)[1])
            image = _rasterize_svg(content) if _is_svg(content) else Image.open(io.BytesIO(content))
            image.load()
        except (ValueError, OSError, IndexError, RuntimeError):
            return None
    else:
        path_value = studio_owned_static_path(url)
        if not path_value or not has_app_context():
            return None
        static_root = Path(current_app.static_folder).resolve()
        path = (static_root / path_value.removeprefix("/static/")).resolve()
        try:
            path.relative_to(static_root)
            content = path.read_bytes() if str(path).lower().endswith(".svg") else b""
            image = _rasterize_svg(content) if content else Image.open(path)
            image.load()
        except (ValueError, OSError, RuntimeError):
            return None
    image = _without_flat_background(image.convert("RGBA"), palette=palette)
    # Logo files often carry transparent padding; trim it so margins are measured from the artwork.
    box = image.getchannel("A").point(lambda value: 255 if value > 8 else 0).getbbox()
    return image.crop(box) if box else image


def _is_svg(content):
    from . import svg_raster
    return svg_raster.is_svg(content)


def _rasterize_svg(content, width=1200):
    """An SVG logo as a transparent PNG (the Studio composes logos from pixels); see ``svg_raster`` for the guards."""
    from . import svg_raster
    return Image.open(io.BytesIO(svg_raster.rasterize(content, width)))


def _without_flat_background(image, tolerance=40, palette=None):
    """An opaque logo on a flat color (a JPEG/WebP export with a stray square behind the wordmark) loses that color where
    it touches the edges, so it is set as artwork, not as a colored square. Logos with real transparency stay as they
    are, and so does a badge in one of the brand's own colors (a red square with the name inside is the logo)."""
    if image.getchannel("A").getextrema()[0] < 250:
        return image
    rgb = image.convert("RGB")
    width, height = rgb.size
    step_x, step_y = max(1, width // 40), max(1, height // 40)
    border = [rgb.getpixel((x, y)) for x in range(0, width, step_x) for y in (0, height - 1)]
    border += [rgb.getpixel((x, y)) for y in range(0, height, step_y) for x in (0, width - 1)]
    ground = tuple(sorted(channel)[len(channel) // 2] for channel in zip(*border))
    near = [sum(abs(a - b) for a, b in zip(pixel, ground)) <= tolerance for pixel in border]
    if sum(near) < 0.9 * len(near):
        return image  # a photo or a busy edge: not a flat background
    from .banner_compose import _hex
    brand = [rgb for rgb in (_hex(item.get("hex") if isinstance(item, dict) else item) for item in palette or []) if rgb]
    neutral = max(ground) - min(ground) < 18  # white, grey or black: an export background, never a badge
    if not neutral and any(sum(abs(a - b) for a, b in zip(ground, color)) <= 60 for color in brand):
        return image
    distance = Image.new("L", rgb.size)
    distance.putdata([255 if sum(abs(a - b) for a, b in zip(pixel, ground)) <= tolerance else 0 for pixel in rgb.getdata()])
    for seed in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        if distance.getpixel(seed) == 255:
            ImageDraw.floodfill(distance, seed, 128)
    alpha = distance.point(lambda value: 0 if value == 128 else 255)
    if alpha.getextrema() == (0, 0):
        return image
    keyed = image.copy()
    keyed.putalpha(alpha)
    return keyed


def shrink_into_border(encoded, factor):
    """The picture scaled by ``factor`` and centred on its own canvas, the border painted with the median edge color
    (a neutral start for the model to outpaint). Returns a PNG data URL."""
    image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")
    width, height = image.size
    edge = [image.getpixel((x, y)) for x in range(0, width, max(1, width // 40)) for y in (0, height - 1)]
    edge += [image.getpixel((x, y)) for y in range(0, height, max(1, height // 40)) for x in (0, width - 1)]
    fill = tuple(sorted(channel)[len(channel) // 2] for channel in zip(*edge))
    canvas = Image.new("RGB", (width, height), fill)
    small = image.resize((max(1, round(width * factor)), max(1, round(height * factor))), Image.Resampling.LANCZOS)
    canvas.paste(small, ((width - small.width) // 2, (height - small.height) // 2))
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")


_EXTERNAL_LOGOS: dict[str, str] = {}


def _external_logo_data_url(url):
    """The logo of an external address as a PNG data URL (an SVG is rasterized there); "" when it cannot be had.

    Only successes are remembered, so a failed download is tried again on the next piece."""
    if url in _EXTERNAL_LOGOS:
        return _EXTERNAL_LOGOS[url]
    try:
        from ..services.openrouter_service import _download_reference_bytes
        content, _mime = _download_reference_bytes(url, max_bytes=8 * 1024 * 1024)
    except Exception:  # the piece goes without a logo rather than failing
        return ""
    if len(_EXTERNAL_LOGOS) >= 64:
        _EXTERNAL_LOGOS.clear()
    _EXTERNAL_LOGOS[url] = "data:image/png;base64," + base64.b64encode(content).decode("ascii")
    return _EXTERNAL_LOGOS[url]


def load_brand_logos(raw_brand):
    """Open every readable official logo variant from the Studio's own static files (first = primary)."""
    brand = raw_brand if isinstance(raw_brand, dict) else {}
    assets = brand.get("assets") if isinstance(brand.get("assets"), dict) else {}
    urls = []
    for candidate in [brand.get("logo_url"), *(assets.get("logo") or [])]:
        raw_value = str(candidate or "")
        url = raw_value if raw_value.startswith("data:image/") else text(candidate, 500)
        # The Lab and some briefs carry the Studio's own absolute URL; its /static/ path is the same file.
        if url.startswith(("https://", "http://")) and "/static/" in url:
            url = "/static/" + url.split("/static/", 1)[1].split("?", 1)[0]
        elif url.startswith(("https://", "http://")):
            # A brand whose official logo lives on its own site (often SVG): fetched once by the safe downloader.
            url = _external_logo_data_url(url)
        if (url.startswith("/static/") or url.startswith("data:image/")) and url not in urls:
            urls.append(url)
    palette = brand.get("palette") if isinstance(brand.get("palette"), list) else []
    images = [image for image in (_open_trimmed_logo(url, palette) for url in urls) if image is not None]
    return images


def load_brand_logo(raw_brand):
    """The primary official logo, or None when it cannot be read."""
    logos = load_brand_logos(raw_brand)
    return logos[0] if logos else None


def _mean_luminance(image, mask=None):
    gray = image.convert("L")
    if mask is None:
        histogram = gray.histogram()
        total = sum(histogram) or 1
        return sum(index * count for index, count in enumerate(histogram)) / total / 255
    pixels, weights = gray.tobytes(), mask.tobytes()
    weight = sum(1 for value in weights if value > 128) or 1
    return sum(luma for luma, alpha in zip(pixels, weights) if alpha > 128) / weight / 255


_LOGO_WORD = re.compile(r"\blogo(?:tipo|marca|type)?s?\b|\bwordmark\b|\bmarca d['’]água\b", re.IGNORECASE)


def strip_logo_clauses(prompt):
    """Drop short clauses that ask the model to draw a logo; the Studio applies it afterwards.

    The approved direction is written as ';'-separated clauses or sentences. A clause that
    mentions the logo and nothing long besides it is removed so the model is not told to draw one.
    """
    pieces = re.split(r"(?<=[;.])\s+", str(prompt or ""))
    kept = [piece for piece in pieces if not (_LOGO_WORD.search(piece) and len(piece) <= 220)]
    return " ".join(kept).strip() or str(prompt or "")


def clean_logo_corner(canvas, position, rect=None):
    """Blur the logo's corner when the model drew something there anyway.

    The corner was asked to stay plain. If its edge density is high, lettering or a lookalike
    mark is likely there (models like to hug the edge, so the zone reaches the border); a
    feathered heavy blur makes it unreadable before the real logo goes on.
    Returns True when the area had to be cleaned.
    """
    width, height = canvas.size
    zone_w, zone_h = round(width * 0.32), round(height * 0.20)
    at_left, at_top = position.endswith("left"), position.startswith("top")
    left = 0 if at_left else width - zone_w
    top = 0 if at_top else height - zone_h
    if rect:  # the slot sits inside the safe frame, not on the border: look around it
        zone_w, zone_h = round(rect[2] * width * 1.5), round(rect[3] * height * 2.2)
        left = max(0, min(width - zone_w, round((rect[0] + rect[2] / 2) * width - zone_w / 2)))
        top = max(0, min(height - zone_h, round((rect[1] + rect[3] / 2) * height - zone_h / 2)))
    box = (left, top, left + zone_w, top + zone_h)
    region = canvas.crop(box).convert("RGB")
    edges = region.convert("L").filter(ImageFilter.FIND_EDGES)
    density = sum(edges.tobytes()) / max(1, edges.width * edges.height)
    if density < LOGO_CORNER_EDGE_LIMIT:
        return False
    softened = region.filter(ImageFilter.GaussianBlur(radius=max(8, zone_h // 4))).convert("RGBA")
    # Feather only the sides that face the picture; the sides on the border stay fully covered.
    soft = 14
    feather = Image.new("L", region.size, 0)
    x0, x1 = (0, region.width - soft) if at_left else (soft, region.width)
    y0, y1 = (0, region.height - soft) if at_top else (soft, region.height)
    if rect:
        x0, x1, y0, y1 = soft, region.width - soft, soft, region.height - soft
    feather.paste(255, (x0, y0, x1, y1))
    canvas.paste(softened, box[:2], feather.filter(ImageFilter.GaussianBlur(radius=soft / 2)))
    return True


def _mono_logo(logo, color):
    """Same artwork, flat single color, original transparency."""
    flat = Image.new("RGBA", logo.size, (*color, 255))
    flat.putalpha(logo.getchannel("A"))
    return flat


def apply_brand_logo(encoded, output_format, logo, position="bottom-right", rect=None):
    """Place the official logo whole, away from the edges.

    `logo` may be a list of variants: the one with the best contrast against the spot wins, and a
    plate is only a last resort when no variant reads on the picture.
    """
    variants = list(logo) if isinstance(logo, (list, tuple)) else [logo]
    logo = variants[0]
    try:
        content = base64.b64decode(str(encoded or ""), validate=True)
        canvas = Image.open(io.BytesIO(content))
        canvas.load()
    except (binascii.Error, OSError, ValueError, TypeError) as exc:
        raise ValueError("A imagem retornada não pôde receber o logo.") from exc
    canvas = canvas.convert("RGBA")
    width, height = canvas.size
    if clean_logo_corner(canvas, position, rect):
        logger.info("Studio logo corner had model-drawn content and was softened before the official logo")
    margin_x, margin_y = round(width * LOGO_MARGIN_RATIO), round(height * LOGO_MARGIN_RATIO)
    slot_w, slot_h = (rect[2] * width, rect[3] * height) if rect else (width * LOGO_WIDTH_RATIO, height * LOGO_HEIGHT_RATIO)

    def placed(candidate):
        scale = min(slot_w / candidate.width, slot_h / candidate.height)
        mark = candidate.resize((max(1, round(candidate.width * scale)), max(1, round(candidate.height * scale))), Image.Resampling.LANCZOS)
        if rect:  # flush to the corner of the slot, which is the corner of the safe frame
            left = (round(rect[0] * width) if position.endswith("left") else
                    round((rect[0] + rect[2] / 2) * width - mark.width / 2) if position.endswith("center") else
                    round((rect[0] + rect[2]) * width) - mark.width)
            top = round(rect[1] * height) if position.startswith("top") else round((rect[1] + rect[3]) * height) - mark.height
        else:
            left = margin_x if position.endswith("left") else width - margin_x - mark.width
            top = margin_y if position.startswith("top") else height - margin_y - mark.height
        region = canvas.crop((left, top, left + mark.width, top + mark.height)).convert("RGB")
        luma = _mean_luminance(mark.convert("RGB"), mark.getchannel("A"))
        return mark, left, top, luma, abs(_mean_luminance(region) - luma)

    # Official variants win whenever one reads; otherwise fall back to a flat white or dark version
    # of the same artwork (the usual negative/positive logo), never a box or haze behind it.
    alpha = variants[0].getchannel("A").tobytes()
    transparent = sum(1 for value in alpha if value < 250) / max(1, len(alpha))
    # A flat recolor only makes sense when the artwork has real transparency; an opaque
    # rectangle would just become a solid block.
    mono = [_mono_logo(variants[0], (255, 255, 255)), _mono_logo(variants[0], (11, 18, 25))] if transparent > 0.05 else []
    best = max((placed(item) for item in variants), key=lambda item: item[4])
    if best[4] < LOGO_MIN_CONTRAST:
        best = max([best, *(placed(item) for item in mono)], key=lambda item: item[4])
    mark, left, top = best[0], best[1], best[2]
    canvas.alpha_composite(mark, (left, top))
    normalized = str(output_format or "png").lower()
    output = io.BytesIO()
    if normalized in {"jpg", "jpeg"}:
        canvas.convert("RGB").save(output, "JPEG", quality=92)
    elif normalized == "webp":
        canvas.save(output, "WEBP", quality=92)
    else:
        canvas.save(output, "PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def reserved_band_line():
    """The model tends to hug the bottom edge with the logo; reserve that band explicitly."""
    return (
        "RESERVED EDGE BANDS: keep the outer 8% of the canvas on every side free of logo, text, buttons and faces; "
        "only background, light and texture may live there."
    )


# Off by default: a vision check plus a possible second image costs more than it saves. Opt in with =1.
MARGIN_QA_ENABLED = os.getenv("CREATIVE_STUDIO_MARGIN_QA", "0") == "1"
LAYOUT_QA_MODEL = os.getenv("CREATIVE_STUDIO_LAYOUT_QA_MODEL", "gpt-5-mini")
MARGIN_QA_SLACK = 0.02


def safe_frame(references, width, height):
    """Safe area of the delivered piece as (left, top, right, bottom) fractions."""
    from . import ad_masks
    for spec in mask_specs(references):
        x, y, w, h = spec["safe"]
        return (x, y, x + w, y + h)
    return ad_masks._safe_rect(width, height)


def _margin_strips(image, safe, slack=MARGIN_QA_SLACK):
    """Thin strips along each edge, outside the safe frame minus a small tolerance."""
    width, height = image.size
    left, top, right, bottom = safe
    boxes = {
        "left": (0, 0, round(width * (left - slack)), height),
        "right": (round(width * (right + slack)), 0, width, height),
        "top": (0, 0, width, round(height * (top - slack))),
        "bottom": (0, round(height * (bottom + slack)), width, height),
    }
    return {name: image.crop(box) for name, box in boxes.items() if box[2] - box[0] >= 4 and box[3] - box[1] >= 4}


def margin_violations(encoded, safe, text_callable, model=LAYOUT_QA_MODEL):
    """Edges whose margin strip contains rendered text or a button. Fails open: [] when the check is unavailable.

    Asking a vision model for coordinates is off by 2-3 points, which is useless for an 8% margin; asking
    whether a cropped edge strip contains letters is reliable (validated on Studio pieces, 2026-10-02).
    """
    if not text_callable:
        return []
    try:
        image = Image.open(io.BytesIO(base64.b64decode(str(encoded), validate=True))).convert("RGB")
        strips = _margin_strips(image, safe)
        if not strips:
            return []
        content = [{"type": "text", "text": (
            "Each image below is a thin strip cut from the EDGE of an advertisement. For each strip answer true only if it "
            "contains rendered typography (letters, words or parts of letters) or part of a call-to-action button, meaning a "
            "pill or rounded rectangle with a text label. Answer false for everything else: photographic content, people, "
            "furniture, lights, decorative shapes, waves, lines, gradients or solid color areas. Reply JSON with one boolean per strip name."
        )}]
        for name, strip in strips.items():
            buffer = io.BytesIO()
            strip.save(buffer, "JPEG", quality=88)
            content += [
                {"type": "text", "text": f"Strip: {name}"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")}},
            ]
        response = text_callable(
            [{"role": "user", "content": content}], model=model, provider="openai", max_tokens=2000,
            temperature=0, reasoning={"effort": "low"}, response_format={"type": "json_object"},
        )
        raw = response.get("message", {}).get("content") if isinstance(response, dict) else response
        answer = raw if isinstance(raw, dict) else _json_content(raw)
        return [name for name in strips if answer.get(name) is True]
    except Exception:
        logger.warning("Studio margin check unavailable", exc_info=True)
        return []


def margin_correction(edges, safe):
    left, top, right, bottom = safe
    return (
        f"CORRECTION: a previous attempt placed text or the button too close to the {', '.join(edges)} edge. "
        f"Every letter, the button and any mark must sit inside x {round(left * 100)}–{round(right * 100)}% and "
        f"y {round(top * 100)}–{round(bottom * 100)}% of the canvas, with visible breathing room; only the scene may reach the edges."
    )


def provider_canvas(aspect_ratio):
    """Pixel shape the OpenAI image route returns for a ratio, or None when unknown."""
    from ..creative_modeling_generation import normalize_image_aspect_ratio
    return {"1:1": (1024, 1024), "4:3": (1536, 1024), "16:9": (1536, 1024), "3:4": (1024, 1536), "9:16": (1024, 1536)}.get(
        normalize_image_aspect_ratio(aspect_ratio)
    )


def references_with_provider_masks(references, provider_size):
    """Draw each served composition mask on the provider canvas, so zones survive the final trim."""
    import base64 as _b64
    from . import ad_masks
    result = []
    for item in references:
        spec = ad_masks.spec_from_url(item.get("data")) if item.get("source") == "global" else None
        if spec and provider_size:
            png = ad_masks.render_mask(spec, longest_side=1536, provider_size=provider_size)
            item = {**item, "data": "data:image/png;base64," + _b64.b64encode(png).decode("ascii")}
        result.append(item)
    return result


def crop_safe_zone_line(aspect_ratio, width, height, provider_size=None):
    """Tell the model which bands are trimmed when the provider ratio differs from the delivery size."""
    from ..creative_modeling_generation import normalize_image_aspect_ratio
    if not (width and height):
        return "SAFE MARGIN: keep all text, logos, CTA and key subjects at least 8% away from every edge; only background may reach the edge."
    provider_ratio = normalize_image_aspect_ratio(aspect_ratio)
    # Pixel sizes the OpenAI image route actually returns for each ratio.
    provider_pixels = {"1:1": (1, 1), "4:3": (3, 2), "16:9": (3, 2), "3:4": (2, 3), "9:16": (2, 3)}
    try:
        ratio_width, ratio_height = provider_size or provider_pixels.get(provider_ratio) or (float(part) for part in provider_ratio.split(":", 1))
        generated, target = ratio_width / ratio_height, width / height
    except (TypeError, ValueError, ZeroDivisionError):
        return "SAFE MARGIN: keep all text, logos, CTA and key subjects at least 8% away from every edge; only background may reach the edge."
    if abs(generated - target) < 0.01:
        return "SAFE MARGIN: keep all text, logos, CTA and key subjects at least 8% away from every edge; only background may reach the edge, nothing else may touch or cross the frame."
    if generated < target:
        trimmed = min(MAX_TRIM_PER_SIDE, (1 - generated / target) / 2)
        bands = "top and bottom"
    else:
        trimmed = min(MAX_TRIM_PER_SIDE, (1 - target / generated) / 2)
        bands = "left and right"
    margin = round(trimmed * 100 + 8)
    return (
        f"SAFE MARGIN: the image is trimmed to {width}x{height}, removing about {round(trimmed * 100, 1)}% at the {bands}. "
        f"Keep every headline, text line, logo, CTA and key subject at least {margin}% away from the {bands} edges and 8% from the other edges; only background may reach the edge, nothing else may touch or cross the frame."
    )


MAX_TRIM_PER_SIDE = 0.11


def _fit_without_losing_content(image, width, height, max_trim=None):
    """Fit the provider output to the delivery size without cutting copy or logos.

    Providers return a few fixed sizes (e.g. 1024x1536 for portrait), so a 4:5
    delivery used to lose ~8% at the top and bottom. Trim at most 4% per side;
    any remaining difference is filled with a blurred extension of the image.
    """
    from PIL import ImageFilter
    max_trim = MAX_TRIM_PER_SIDE if max_trim is None else max_trim
    image = image.convert("RGB") if image.mode not in {"RGB", "RGBA"} else image
    source_ratio, target_ratio = image.width / image.height, width / height
    if abs(source_ratio - target_ratio) < 0.005:
        return image.resize((width, height), Image.Resampling.LANCZOS)
    if source_ratio < target_ratio:
        # Taller than the target: trim top/bottom up to the limit.
        keep = max(image.width / target_ratio, image.height * (1 - 2 * max_trim))
        top = (image.height - keep) / 2
        trimmed = image.crop((0, round(top), image.width, round(top + keep)))
    else:
        keep = max(image.height * target_ratio, image.width * (1 - 2 * max_trim))
        left = (image.width - keep) / 2
        trimmed = image.crop((round(left), 0, round(left + keep), image.height))
    background = ImageOps.fit(trimmed, (width, height), method=Image.Resampling.LANCZOS)
    background = background.filter(ImageFilter.GaussianBlur(radius=max(width, height) / 40))
    contained = ImageOps.contain(trimmed, (width, height), method=Image.Resampling.LANCZOS)
    background.paste(contained, ((width - contained.width) // 2, (height - contained.height) // 2))
    return background


def fit_generated_output(encoded, width, height, output_format="png", max_trim=None):
    try:
        content = base64.b64decode(str(encoded or ""), validate=True)
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(content)))
        image.load()
        fitted = _fit_without_losing_content(image, int(width), int(height), max_trim)
        normalized = str(output_format or "png").lower()
        if normalized in {"jpg", "jpeg"}:
            fitted = fitted.convert("RGB")
            pil_format = "JPEG"
        elif normalized == "webp":
            pil_format = "WEBP"
        else:
            pil_format = "PNG"
        output = io.BytesIO()
        save_options = {"quality": 92} if pil_format != "PNG" else {}
        fitted.save(output, pil_format, **save_options)
        return base64.b64encode(output.getvalue()).decode("ascii")
    except (binascii.Error, OSError, ValueError, TypeError) as exc:
        raise ValueError("A imagem retornada não pôde ser ajustada ao formato.") from exc


def marked_reference(source_data_url, mask_data_url):
    source = _data_image(source_data_url).convert("RGBA")
    mask = _data_image(mask_data_url).convert("L")
    if mask.size != source.size:
        raise ValueError("A seleção não corresponde ao tamanho da imagem principal.")
    overlay = Image.new("RGBA", source.size, (130, 223, 200, 150))
    marked = Image.composite(overlay, source, mask)
    output = io.BytesIO()
    marked.save(output, "PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def compose_inside_mask(generated_b64, source_data_url, mask_data_url):
    generated = _data_image(generated_b64, encoded_only=True).convert("RGBA")
    source = _data_image(source_data_url).convert("RGBA")
    mask = _data_image(mask_data_url).convert("L")
    validate_mask(source_data_url, mask_data_url)
    if generated.size != source.size:
        generated = generated.resize(source.size, Image.Resampling.LANCZOS)
    if min(mask.size) >= 64:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(1, min(mask.size) * .003)))
    composed = Image.composite(generated, source, mask)
    output = io.BytesIO()
    composed.save(output, "PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _data_image(value, encoded_only=False):
    raw = str(value or "")
    if not encoded_only:
        if not raw.startswith("data:image/") or "," not in raw:
            raise ValueError("A composição mascarada exige uma imagem principal local.")
        raw = raw.split(",", 1)[1]
    try:
        content = base64.b64decode(raw, validate=True)
        image = Image.open(io.BytesIO(content))
        image.load()
        return image
    except (binascii.Error, OSError, ValueError) as exc:
        raise ValueError("A imagem usada na seleção é inválida.") from exc


def integer(value, default=0):
    try: return int(value)
    except (TypeError, ValueError): return default


def text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def whole_words(value, limit):
    """Like ``text`` but never cuts a word: ends at the last full sentence, else the last full word."""
    clean = " ".join(str(value or "").split())
    if len(clean) <= limit:
        return clean
    cut = clean[:limit]
    sentence = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:sentence + 1] if sentence >= limit * 0.6 else cut[:cut.rfind(" ")].rstrip(",;:")


def clean_prompt(value, limit):
    """Keep only readable prompt text before an agent or image model sees it."""
    raw = str(value or "")
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    raw = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", raw)
    raw = re.sub(r"```[a-zA-Z0-9_-]*", " ", raw)
    raw = raw.replace("`", "")
    raw = re.sub(r"(^|\s)#{1,6}\s*", r"\1", raw)
    raw = re.sub(r"(^|\s)>\s*", r"\1", raw)
    raw = re.sub(r"(^|\s)(?:[-*+]\s+|\d+[.)]\s+)", r"\1", raw)
    raw = re.sub(r"(\*\*|__|~~)", "", raw)
    raw = re.sub(r"(?<!\w)[*_](?!\w)", "", raw)
    raw = re.sub(r"[^\w\sÀ-ÖØ-öø-ÿ.,;:!?()/%+&'\"-]", " ", raw, flags=re.UNICODE)
    return text(raw, limit)
