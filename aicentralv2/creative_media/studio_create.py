"""AI directions and credit charging for the Studio creation desk."""
from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import os
import re
from decimal import Decimal
from uuid import uuid4

from PIL import Image, ImageFilter, ImageOps

from ..creative_modeling_generation import OpenRouterError, _json_content

logger = logging.getLogger(__name__)

MODEL = os.getenv("CREATIVE_STUDIO_DIRECTION_MODEL", "openai/gpt-5-nano")
DIRECTOR_MODEL = os.getenv("CREATIVE_STUDIO_DIRECTOR_MODEL", MODEL.removeprefix("openai/"))
REDUNDANCY_MODEL = os.getenv("CREATIVE_STUDIO_DIRECTION_FALLBACK_MODEL", "openai/gpt-4o-mini")
IMAGE_MODEL = os.getenv("CREATIVE_STUDIO_IMAGE_MODEL", "openai/gpt-image-2")
MAX_IMAGE_REFERENCES = 3
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
    messages = [
        {"role": "system", "content": system_prompt(count)},
        {"role": "user", "content": direction_user_content(request, context)},
    ]
    response = None
    raw = None
    provider_used = ""
    errors = []
    # The first call is direct OpenAI. OpenRouter is a true redundancy path,
    # not a synthetic direction: both providers must satisfy the same JSON
    # contract before the request can continue to generation.
    for provider, model in (("openai", DIRECTOR_MODEL), ("openrouter", REDUNDANCY_MODEL)):
        try:
            response = text_callable(
                messages,
                model=model,
                provider=provider,
                max_tokens=900 + count * 320,
                temperature=.45,
                response_format={"type": "json_object"},
            )
            content = response.get("message", {}).get("content") if isinstance(response, dict) else response
            raw = content if isinstance(content, dict) else _json_content(content)
            if not isinstance(raw, dict) or not isinstance(raw.get("directions"), list):
                raise OpenRouterError("O provedor não devolveu o contrato de direções.")
            provider_used = provider
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
        title, prompt = text(item.get("title"), 90), text(item.get("prompt"), 900)
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
            items.append({"title": title, "summary": text(item.get("summary") or item.get("rationale"), 220) or "Direção baseada no briefing do projeto.", "prompt": prompt, "reference_plan": reference_plan[:4]})
        if len(items) == count:
            break
    if not items:
        raise ValueError("O agente não devolveu direções utilizáveis. Tente novamente.")
    return {"directions": items, "count": len(items), "model": str(response.get("model") or (DIRECTOR_MODEL if provider_used == "openai" else REDUNDANCY_MODEL)), "provider": provider_used}, response


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
    if creation_intent == "branded_creative":
        references = references_with_brand_logo(references, brand_context)
    return {key: text(data.get(key), limit) for key, limit in (("project_name", 120), ("brand", 120), ("brief", 1800), ("objective", 300), ("audience", 300), ("purpose", 24), ("format", 24))} | {
        "channels": [text(item, 24) for item in data.get("channels", []) if text(item, 24)][:5],
        "iab_formats": [text(item, 32) for item in data.get("formats", []) if text(item, 32)][:6],
        "direction_intensity": max(0, min(integer(data.get("direction_intensity"), 70), 100)),
        "format_key": text(data.get("format_key"), 80),
        "width": integer(data.get("width"), 0),
        "height": integer(data.get("height"), 0),
        "requested_directions": count,
        "auto_generate_next": data.get("auto_generate_next") is True,
        "generation_round": max(0, integer(data.get("generation_round"), 0)),
        "requested_palette": clean_palette(data.get("requested_palette")),
        "creation_intent": creation_intent,
        "references": references,
        "reference_mode": reference_mode(references),
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


def brand_identity_guard(raw_brand, visual_reference=False, creation_intent="branded_creative"):
    brand = raw_brand if isinstance(raw_brand, dict) else {}
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
    readiness = brand_identity_readiness(brand)
    if readiness["status"] == "ready":
        palette = ", ".join(text(item, 16) for item in brand.get("palette", []) if text(item, 16))
        return (
            "BRAND IDENTITY GUARD: Official logo and palette are available. "
            "Use only supplied identity assets; do not alter or reinterpret them. "
            f"Official color tokens: {palette}."
        )
    missing = ", ".join(readiness["missing"])
    return (
        f"BRAND IDENTITY GUARD: This project is missing official {missing}. "
        "Do not invent, infer or stylize a logo, monogram, lettermark, initials, wordmark, icon or color system from the brand name. "
        "Keep a clean neutral safe area for identity to be applied later, and never present arbitrary colors as official brand colors."
    )


def official_logo_reference(raw_brand):
    """Return the first provider-safe official logo, never a generated proxy."""
    brand = raw_brand if isinstance(raw_brand, dict) else {}
    assets = brand.get("assets") if isinstance(brand.get("assets"), dict) else {}
    candidates = [brand.get("logo_url"), *(assets.get("logo") or [])]
    for candidate in candidates:
        url = text(candidate, 500)
        if url.startswith(("https://", "http://", "/static/")):
            return {
                "id": "brand:official-logo",
                "url": url,
                "role": "identity",
                "source": "project",
                "label": f"{text(brand.get('name'), 120) or 'Marca'} · logo oficial",
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
        blocks.append({"type": "image_url", "image_url": {"url": public_studio_asset_url(url)}})
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
        blocks.append({"type": "image_url", "image_url": {"url": public_studio_asset_url(logo["url"])}})
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

Responda somente JSON no formato {{\"directions\":[{{\"title\":\"...\",\"summary\":\"...\",\"prompt\":\"...\"}}]}}. Use português do Brasil.

REVISÃO DO BRIEFING: antes de escrever cada prompt, harmonize o pedido do usuário com o contexto do Studio. Preserve a intenção, anunciante, produto, público, cenário, ação, texto literal, preço, volume, logo solicitado e restrições explícitas. Corrija apenas ambiguidades, contradições, ordem e instruções técnicas; não troque o produto, não remova requisitos concretos e não invente benefícios, ofertas ou identidade visual. Se o usuário informar explicitamente uma marca, preço, volume, slogan ou pedido de logo, isso é requisito obrigatório e deve aparecer no prompt final exatamente como informado.
ORDEM OBRIGATÓRIA DO PROMPT FINAL: escreva um único prompt contínuo, nesta sequência: (1) objetivo e tipo de peça; (2) produto/assunto principal e o que precisa estar visível; (3) público, pessoas e ação; (4) cenário, praça ou contexto cultural brasileiro, momento e atmosfera; (5) composição, enquadramento, hierarquia, posição dos elementos e área segura; (6) como cada referência selecionada deve orientar a peça; (7) iluminação, materiais e paleta; (8) canal e formato controlados pelo Studio; (9) texto literal solicitado e posição reservada; (10) restrições e checagens finais. Não comece pelo formato nem pelas referências: eles orientam a execução, mas não substituem a ideia do usuário.
FORMATO É CONTROLADO PELO STUDIO: o campo contexto.format, contexto.format_key, contexto.width e contexto.height é a fonte de verdade do output selecionado na interface. Se o texto do pedido mencionar outra dimensão ou proporção, trate isso apenas como descrição do pedido e ignore a dimensão conflitante. Nunca escreva 300x300, 1080x1080 ou outra medida no prompt final quando o formato selecionado for diferente. Sempre repita o formato controlado pelo contexto no prompt final.
MARCA E PROJETO: contexto.creation_intent define o escopo. Em "branded_creative", quando contexto.brand_context existir, use-o como fonte de verdade para nome, logo, paleta, tipografia, ativos, elementos obrigatórios e elementos proibidos; aplique os ativos aprovados na peça. Tipografia pode trazer família aprovada ou somente uma classificação observada; não invente o nome de uma fonte proprietária quando houver apenas classificação. Em "neutral_asset", ignore integralmente a identidade do projeto: a solicitação é um fundo, página, textura, cena ou elemento reutilizável, não uma peça de marca. Referências de composição continuam sendo apenas guias de posição e hierarquia. Se contexto.requested_palette tiver cores, aplique-as apenas nesta peça como escolha explícita do briefing: elas não sobrescrevem nem passam a ser apresentadas como cores oficiais da marca. Se contexto.brand_context.readiness indicar ausência de logo ou cores, trate o nome apenas como contexto verbal: nunca invente logotipo, monograma, inicial, símbolo, wordmark ou paleta de marca. Reserve uma área neutra e segura para a identidade ser aplicada posteriormente. EXCEÇÃO DE REMIX: quando contexto.reference_mode for "visual_remix" ou "user_visual_reference", a imagem anexada pelo usuário é a evidência visual prioritária. Extraia dela apenas características observáveis — paleta, materiais, luz, tratamento do assunto e linguagem da peça — sem dizer que são cores ou logo oficiais do projeto e sem exigir identidade ausente.

REFERÊNCIAS — você receberá as imagens selecionadas como blocos visuais no mesmo turno. Inspecione seus pixels antes de escrever cada direção; não deduza a composição apenas pelo nome ou URL. Trate cada item do contexto como contrato, nunca como decoração. Itens com source="global" são máscaras protegidas de composição do Studio: use-as como planta estrutural, extraindo ordem de camadas, zona do produto/assunto, faixa de headline, área de preço ou CTA, margens seguras, alinhamento, respiro e relação entre foreground e background. Reproduza essa arquitetura espacial na peça final com o conteúdo do briefing, sem copiar o template, sem usar o objeto fictício da máscara como produto, sem alterar o arquivo e sem colocá-lo na biblioteca do usuário. Para cada global, devolva no reference_plan um layout com subject_zone, headline_zone, support_zone, safe_margin, layer_order e alignment, descrevendo posições relativas observadas na imagem. Itens com source="user" ou source="project" são referências de produção: aplique na imagem criada o conteúdo visual útil, como produto, pessoa, embalagem, identidade, textura, cenário ou objeto, preservando os detalhes relevantes quando a intenção indicar. Quando reference_mode="visual_remix", una a imagem do usuário e a máscara global: a imagem do usuário define a linguagem visual e a máscara global define a estrutura, zonas e respiro. Gere uma nova peça coerente, não uma cópia literal, e não transforme cores vistas no anexo em identidade oficial. Não confunda uma referência global de composição com uma imagem-base do usuário. Quando reference_mode="briefing_only", não mencione referências visuais, não invente uma reference_plan e crie uma direção original baseada somente no briefing, canal e formato. O prompt final deve mencionar como cada referência será usada somente quando houver referência selecionada e respeitar o role declarado.

Para Display, trate o formato IAB informado como uma unidade publicitária final — não o transforme em pôster ou interface. Para CTV, trate como still cinematográfico 16:9. Para social, preserve área segura e leitura no feed. Escreva uma cena específica, não adjetivos vagos como “moderno”, “bonito” ou “impactante”. Prefira detalhes observáveis: lugar, hora, enquadramento, distância de câmera, gesto, textura e espaço para copy.

Use a marca, briefing, referências e ativos do contexto como fonte de verdade. Cada substantivo concreto do briefing é obrigatório: anunciante, produto, embalagem, pessoas, cenário, ação, mensagem, preço, volume e formato não podem ser omitidos ou substituídos por uma cena genérica. Se o briefing pede produto visível, descreva-o como assunto principal em primeiro plano, com escala, luz e enquadramento suficientes para ser reconhecível. Mantenha todo logo, texto, embalagem e elemento de marca inteiro dentro da margem segura do formato; nunca corte, encoste ou esconda esses elementos na borda. Se o usuário pediu um logo mas nenhum ativo oficial está disponível, mantenha no prompt a instrução de reservar uma área limpa e identifique a marca que deverá ser aplicada posteriormente. Não invente dados comerciais além dos que o usuário informou. Se não houver texto literal aprovado, peça espaço reservado para a assinatura, sem fabricar tipografia. Todo texto publicitário visível deve ser português do Brasil; se a renderização textual não for confiável, instrua a manter a área livre para composição posterior. Não inclua marca d'água, interface de plataforma, mockup de dashboard ou logos de terceiros. Não use pessoas identificáveis sem necessidade. Preserve briefing, marca, canal e formato.
 Antes de devolver cada direção, faça uma revisão final como agente GPT-5 nano: confirme que o prompt está fiel ao pedido, respeita todas as exclusões explícitas, usa cada referência conforme seu source e role, não inventa informações e está pronto para ser enviado ao GPT Image 2. O campo "prompt" deve ser a instrução final revisada para o processador de imagem, sem comentários sobre esta revisão. Inclua também "reference_plan" como uma lista curta de objetos {{"label":"...","source":"global|user|project","use":"...","layout":{{"subject_zone":"...","headline_zone":"...","support_zone":"...","safe_margin":"...","layer_order":"...","alignment":"..."}}}} para tornar a decisão de cada referência auditável. O campo layout é obrigatório para source="global" e opcional para os demais."""


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
    visual_reference = uses_user_visual_reference([
        clean_direction_reference(item, index)
        for index, item in enumerate(raw_references[:MAX_IMAGE_REFERENCES]) if isinstance(item, dict)
    ])
    try:
        provider_source_references = (
            references_with_brand_logo(raw_references, data.get("brand_context"))
            if creation_intent == "branded_creative" else raw_references
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
    estimate = Decimal(str(modeling._estimate("image", billing_fidelity, IMAGE_MODEL)))
    estimate *= Decimal("1") + REFERENCE_IMAGE_COST_FACTOR * len(references)
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
    edit_guard += " Never add text, logos, prices or offers that the user did not request."
    channel = str(data.get("channel") or "").strip()[:32]
    try:
        direction_intensity = max(0, min(int(data.get("direction_intensity") or 70), 100))
    except (TypeError, ValueError):
        direction_intensity = 70
    width = integer(data.get("width"), 0)
    height = integer(data.get("height"), 0)
    if bool(width) != bool(height):
        raise ValueError("Informe largura e altura do formato.")
    if (width and not 120 <= width <= 7680) or (height and not 80 <= height <= 7680):
        raise ValueError("Dimensões do formato fora do limite permitido.")
    supplied_logo = official_logo_reference(data.get("brand_context")) if creation_intent == "branded_creative" else None
    identity_safe_area = (
        "NEUTRAL ASSET CHECK: Do not reserve space for a logo, headline, price, product packshot or brand lockup unless the user explicitly asks for that element."
        if creation_intent == "neutral_asset" else
        "VISUAL REMIX IDENTITY CHECK: Use the supplied approved logo exactly as provided, fully inside the safe margin, without redrawing or cropping it."
        if visual_reference and supplied_logo else
        "VISUAL REMIX IDENTITY CHECK: The user reference is sufficient visual evidence for this remix. "
        "Do not reserve a project-logo area or invent a project logo unless the briefing explicitly requests one."
        if visual_reference else
        "SAFE AREA CHECK: Keep all requested logos, brand marks, headline text and product packaging fully inside the selected format with visible breathing room on every side. Never place a logo partially outside the frame or crop it at the top, bottom or side. If no official logo asset is supplied, leave a clean intentional logo-safe area instead of generating a guessed mark."
    )
    requested_palette = clean_palette(data.get("requested_palette"))
    technical_prompt = "\n".join([
        "MANDATORY BRIEFING FIDELITY: Preserve every concrete requirement in the user briefing, especially named products, packaging, people, setting, action, copy and requested format. A composition reference is only a layout guide; it must never replace the requested subject or product.",
        "MANDATORY COMMERCIAL FACTS: Any advertiser name, brand name, product name, price, currency, package volume, slogan or logo request explicitly present in the user briefing must remain in the creative instruction exactly as provided. Do not silently drop Reserva, R$ 599, 50 ml, 1 Million or any other named fact.",
        brand_identity_guard(data.get("brand_context"), visual_reference=visual_reference, creation_intent=creation_intent),
        f"REQUESTED CREATIVE PALETTE: {', '.join(requested_palette)}. Use these colors for this piece only; they are not a claim about official brand identity." if requested_palette else "REQUESTED CREATIVE PALETTE: none.",
        prompt,
        "\nREFERENCE CONTRACT:",
        *(role_lines or ["No image reference was supplied; create an original image."]),
        "DIRECTOR REFERENCE PLAN:",
        *(plan_lines or ["Apply the reference contract directly and preserve the declared source boundaries."]),
        edit_guard,
        "PRODUCT VISIBILITY CHECK: If the briefing requests a product, make it a deliberate, recognizable foreground subject with enough scale and light to be clearly visible. Do not hide it behind hands, bodies, crops or depth-of-field blur. If bottles or packages are requested, show the requested quantity visibly and keep their labels facing the camera when the briefing asks for labels.",
        identity_safe_area,
        "GLOBAL COMPOSITION CHECK: When a global composition mask is supplied, treat its spatial architecture as binding: preserve the indicated subject/product zone, background field, headline band, support/price/CTA band, layer order, alignment and safe margins. Replace only the mask's placeholder subject with the product and facts from the briefing. Do not center or resize the product arbitrarily if that changes the reference hierarchy.",
        "VISUAL REMIX CHECK: When a user-supplied visual reference is present, make its observable visual language materially visible in the new piece. Combine it with the global mask's layout rather than choosing one reference and ignoring the other. Do not call the reference palette official brand colors or fabricate a brand mark from it.",
        "FORMAT AUTHORITY: The selected Studio format below overrides any conflicting dimension written in the user briefing. Compose and deliver only in this selected format.",
        f"Output channel: {channel or 'unspecified'}.",
        f"Requested output dimensions: {width}x{height}px." if width and height else "Requested output dimensions: use the selected aspect ratio.",
        f"Creative direction exploration intensity: {direction_intensity}/100.",
        f"Output aspect ratio: {aspect_ratio}.",
    ])
    provider_references = provider_image_references(references, mask)
    try:
        provider = modeling.generator.generate_image(
            technical_prompt,
            provider_references,
            aspect_ratio=aspect_ratio,
            quality=provider_quality,
            resolution=provider_resolution,
            model=IMAGE_MODEL,
            max_input_references=MAX_IMAGE_REFERENCES,
        )
    except Exception as error:
        setattr(error, "studio_phase", "image_provider")
        raise
    encoded = provider.get("b64_json")
    if not encoded:
        raise ValueError("O gerador não devolveu uma imagem.")
    output_format = provider.get("output_format") or "png"
    try:
        if mask and primary:
            encoded = compose_inside_mask(encoded, primary["data"], mask)
            output_format = "png"
        elif width and height:
            encoded = fit_generated_output(encoded, width, height, output_format)
        image_url = modeling.storage.save_generated_base64(
            encoded, output_format
        )
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


def provider_image_references(references, mask):
    """Prepare up to three high-fidelity provider inputs for Studio V2."""
    values = [item["data"] for item in references[:MAX_IMAGE_REFERENCES]]
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


def fit_generated_output(encoded, width, height, output_format="png"):
    try:
        content = base64.b64decode(str(encoded or ""), validate=True)
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(content)))
        image.load()
        fitted = ImageOps.fit(
            image, (int(width), int(height)), method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
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
