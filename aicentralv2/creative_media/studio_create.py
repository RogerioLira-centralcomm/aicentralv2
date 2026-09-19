"""AI directions and credit charging for the Studio creation desk."""
from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import os
import re
from uuid import uuid4

from PIL import Image, ImageFilter, ImageOps

from ..creative_modeling_generation import OpenRouterError, _json_content

logger = logging.getLogger(__name__)

MODEL = os.getenv("CREATIVE_STUDIO_DIRECTION_MODEL", "openai/gpt-5-nano")
DIRECTOR_MODEL = os.getenv("CREATIVE_STUDIO_DIRECTOR_MODEL", MODEL.removeprefix("openai/"))
REDUNDANCY_MODEL = os.getenv("CREATIVE_STUDIO_DIRECTION_FALLBACK_MODEL", "openai/gpt-4o-mini")
IMAGE_MODEL = os.getenv("CREATIVE_STUDIO_IMAGE_MODEL", "openai/gpt-image-2")
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


def estimated_tokens(count):
    # Reserve the complete, bounded prompt and completion budget before making
    # a billable provider call. The actual usage is charged afterwards.
    return 1300 + max(1, min(int(count or 1), 5)) * 320


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
    references = [clean_direction_reference(item, index) for index, item in enumerate(data.get("references", [])[:2]) if isinstance(item, dict)]
    raw_brand = data.get("brand_context") if isinstance(data.get("brand_context"), dict) else {}
    brand_context = {
        "name": text(raw_brand.get("name"), 120),
        "logo_url": text(raw_brand.get("logo_url"), 500),
        "palette": [text(item, 16) for item in raw_brand.get("palette", [])[:8]],
        "fonts": [text(item.get("family") if isinstance(item, dict) else item, 80) for item in raw_brand.get("fonts", [])[:4]],
        "brand_summary": text(raw_brand.get("brand_summary"), 500),
        "products_services": [text(item, 120) for item in raw_brand.get("products_services", [])[:8]],
        "mandatory_elements": [text(item, 160) for item in raw_brand.get("mandatory_elements", [])[:8]],
        "forbidden_elements": [text(item, 160) for item in raw_brand.get("forbidden_elements", [])[:8]],
        "creative_guidelines": text(raw_brand.get("creative_guidelines"), 700),
        "assets": {
            "logo": [text(item, 500) for item in (raw_brand.get("assets") or {}).get("logo", [])[:3]],
            "references": [text(item, 500) for item in (raw_brand.get("assets") or {}).get("references", [])[:8]],
        },
    }
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
        "references": references,
        "reference_mode": "visual_references_selected" if references else "briefing_only",
        "brand_context": brand_context if brand_context.get("name") else {},
    }


def direction_user_content(request, context):
    """Send stored references as URLs so the director can inspect their pixels."""
    blocks = [{"type": "text", "text": json.dumps({"pedido": request, "contexto": context}, ensure_ascii=False)}]
    for index, reference in enumerate(context.get("references", []), start=1):
        url = str(reference.get("url") or "")
        if not url or url == "inline upload":
            continue
        blocks.append({"type": "text", "text": (
            f"Referência visual {index}: {reference.get('label', 'sem nome')}; "
            f"source={reference.get('source', 'user')}; role={reference.get('role', 'reference')}. "
            "Inspecione os pixels e aplique o contrato descrito no contexto."
        )})
        blocks.append({"type": "image_url", "image_url": {"url": url}})
    return blocks


def clean_direction_reference(item, index):
    role = str(item.get("role") or ("primary" if index == 0 else "insert"))
    # The Studio UI uses the neutral label "reference" for a selected
    # composition reference. The image contract needs a concrete role.
    if role == "reference":
        role = "composition"
    if role not in IMAGE_ROLES:
        role = "insert"
    raw_url = str(item.get("url") or "")
    source = "global" if raw_url.startswith("/static/images/cadu/studio/references/") else str(item.get("source") or "user")
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
MARCA E PROJETO: quando contexto.brand_context existir, use-o como fonte de verdade para nome, logo, paleta, tipografia, ativos, elementos obrigatórios e elementos proibidos. Ativos de marca podem ser aplicados na peça; referências de composição continuam sendo apenas guias de posição e hierarquia.

REFERÊNCIAS — você receberá as imagens selecionadas como blocos visuais no mesmo turno. Inspecione seus pixels antes de escrever cada direção; não deduza a composição apenas pelo nome ou URL. Trate cada item do contexto como contrato, nunca como decoração. Itens com source="global" são máscaras protegidas de composição do Studio: use-as como planta estrutural, extraindo ordem de camadas, zona do produto/assunto, faixa de headline, área de preço ou CTA, margens seguras, alinhamento, respiro e relação entre foreground e background. Reproduza essa arquitetura espacial na peça final com o conteúdo do briefing, sem copiar o template, sem usar o objeto fictício da máscara como produto, sem alterar o arquivo e sem colocá-lo na biblioteca do usuário. Para cada global, devolva no reference_plan um layout com subject_zone, headline_zone, support_zone, safe_margin, layer_order e alignment, descrevendo posições relativas observadas na imagem. Itens com source="user" ou source="project" são referências de produção: aplique na imagem criada o conteúdo visual útil, como produto, pessoa, embalagem, identidade, textura, cenário ou objeto, preservando os detalhes relevantes quando a intenção indicar. Não confunda uma referência global de composição com uma imagem-base do usuário. Quando reference_mode="briefing_only", não mencione referências visuais, não invente uma reference_plan e crie uma direção original baseada somente no briefing, canal e formato. O prompt final deve mencionar como cada referência será usada somente quando houver referência selecionada e respeitar o role declarado.

Para Display, trate o formato IAB informado como uma unidade publicitária final — não o transforme em pôster ou interface. Para CTV, trate como still cinematográfico 16:9. Para social, preserve área segura e leitura no feed. Escreva uma cena específica, não adjetivos vagos como “moderno”, “bonito” ou “impactante”. Prefira detalhes observáveis: lugar, hora, enquadramento, distância de câmera, gesto, textura e espaço para copy.

Use a marca, briefing, referências e ativos do contexto como fonte de verdade. Cada substantivo concreto do briefing é obrigatório: anunciante, produto, embalagem, pessoas, cenário, ação, mensagem, preço, volume e formato não podem ser omitidos ou substituídos por uma cena genérica. Se o briefing pede produto visível, descreva-o como assunto principal em primeiro plano, com escala, luz e enquadramento suficientes para ser reconhecível. Mantenha todo logo, texto, embalagem e elemento de marca inteiro dentro da margem segura do formato; nunca corte, encoste ou esconda esses elementos na borda. Se o usuário pediu um logo mas nenhum ativo oficial está disponível, mantenha no prompt a instrução de reservar uma área limpa e identifique a marca que deverá ser aplicada posteriormente. Não invente dados comerciais além dos que o usuário informou. Se não houver texto literal aprovado, peça espaço reservado para a assinatura, sem fabricar tipografia. Todo texto publicitário visível deve ser português do Brasil; se a renderização textual não for confiável, instrua a manter a área livre para composição posterior. Não inclua marca d'água, interface de plataforma, mockup de dashboard ou logos de terceiros. Não use pessoas identificáveis sem necessidade. Preserve briefing, marca, canal e formato.
 Antes de devolver cada direção, faça uma revisão final como agente GPT-5 nano: confirme que o prompt está fiel ao pedido, respeita todas as exclusões explícitas, usa cada referência conforme seu source e role, não inventa informações e está pronto para ser enviado ao GPT Image 2. O campo "prompt" deve ser a instrução final revisada para o processador de imagem, sem comentários sobre esta revisão. Inclua também "reference_plan" como uma lista curta de objetos {{"label":"...","source":"global|user|project","use":"...","layout":{{"subject_zone":"...","headline_zone":"...","support_zone":"...","safe_margin":"...","layer_order":"...","alignment":"..."}}}} para tornar a decisão de cada referência auditável. O campo layout é obrigatório para source="global" e opcional para os demais."""


def credit_context(modeling, client_id, user_id):
    from ..cadu_credit_connector import CaduCreditConnector, CreditActor
    payer = modeling._credits_crm_id(client_id) or int(client_id)
    credits = getattr(modeling, "credit_connector", None) or CaduCreditConnector(modeling.credit_ledger)
    return credits, CreditActor.from_values(payer, user_id)


def assert_available(client_id, user_id, count):
    from ..creative_modeling_service import CreativeModelingService
    modeling = CreativeModelingService()
    credits, actor = credit_context(modeling, client_id, user_id)
    credits.authorize(actor, estimated_tokens(count))
    return actor.client_id


def charge(provider_result, client_id, user_id, count, project_id, run_id=None,
           studio_session_id="", studio_root_session_id=""):
    from ..creative_modeling_service import CreativeModelingService
    modeling = CreativeModelingService()
    credits, actor = credit_context(modeling, client_id, user_id)
    credits.authorize(actor, estimated_tokens(count))
    run_id = str(run_id or uuid4().hex)
    charged = credits.charge_provider(
        actor=actor, idempotency_key=f"studio:directions:{run_id}",
        app="Cadu Studio", stage="creative_directions", provider_result=provider_result,
        model=str(provider_result.get("model") or MODEL) if isinstance(provider_result, dict) else MODEL,
        metadata={
            "project_id": str(project_id or ""), "directions": int(count), "run_id": run_id,
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
    try:
        references = normalize_image_references(data.get("references"), modeling.storage)
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
    estimate = modeling._estimate("image", "draft", IMAGE_MODEL)
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
    technical_prompt = "\n".join([
        "MANDATORY BRIEFING FIDELITY: Preserve every concrete requirement in the user briefing, especially named products, packaging, people, setting, action, copy and requested format. A composition reference is only a layout guide; it must never replace the requested subject or product.",
        "MANDATORY COMMERCIAL FACTS: Any advertiser name, brand name, product name, price, currency, package volume, slogan or logo request explicitly present in the user briefing must remain in the creative instruction exactly as provided. Do not silently drop Reserva, R$ 599, 50 ml, 1 Million or any other named fact.",
        prompt,
        "\nREFERENCE CONTRACT:",
        *(role_lines or ["No image reference was supplied; create an original image."]),
        "DIRECTOR REFERENCE PLAN:",
        *(plan_lines or ["Apply the reference contract directly and preserve the declared source boundaries."]),
        edit_guard,
        "PRODUCT VISIBILITY CHECK: If the briefing requests a product, make it a deliberate, recognizable foreground subject with enough scale and light to be clearly visible. Do not hide it behind hands, bodies, crops or depth-of-field blur. If bottles or packages are requested, show the requested quantity visibly and keep their labels facing the camera when the briefing asks for labels.",
        "SAFE AREA CHECK: Keep all requested logos, brand marks, headline text and product packaging fully inside the selected format with visible breathing room on every side. Never place a logo partially outside the frame or crop it at the top, bottom or side. If no official logo asset is supplied, leave a clean intentional logo-safe area instead of generating a guessed mark.",
        "GLOBAL COMPOSITION CHECK: When a global composition mask is supplied, treat its spatial architecture as binding: preserve the indicated subject/product zone, background field, headline band, support/price/CTA band, layer order, alignment and safe margins. Replace only the mask's placeholder subject with the product and facts from the briefing. Do not center or resize the product arbitrarily if that changes the reference hierarchy.",
        "FORMAT AUTHORITY: The selected Studio format below overrides any conflicting dimension written in the user briefing. Compose and deliver only in this selected format.",
        f"Output channel: {channel or 'unspecified'}.",
        f"Requested output dimensions: {width}x{height}px." if width and height else "Requested output dimensions: use the selected aspect ratio.",
        f"Creative direction exploration intensity: {direction_intensity}/100.",
        f"Output aspect ratio: {aspect_ratio}.",
    ])
    provider_references = provider_image_references(references, mask)
    requested_quality = str(data.get("quality") or "Padrão").strip().lower()
    quality_map = {"econômica": ("low", "1K"), "economica": ("low", "1K"), "padrão": ("medium", "1K"), "padrao": ("medium", "1K"), "alta": ("high", "2K")}
    provider_quality, provider_resolution = quality_map.get(requested_quality, ("medium", "1K"))
    try:
        provider = modeling.generator.generate_image(
            technical_prompt,
            provider_references,
            aspect_ratio=aspect_ratio,
            quality=provider_quality,
            resolution=provider_resolution,
            model=IMAGE_MODEL,
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
    if len(references) > 2:
        raise ValueError("Use no máximo duas imagens neste pedido.")
    cleaned = []
    for index, item in enumerate(references):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or ("primary" if index == 0 else "insert"))
        if role == "reference":
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
            from ..creative_modeling_storage import _validated_public_asset_url
            image_data = _validated_public_asset_url(value)
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
    """Represent the selection inside the provider's two-reference limit."""
    values = [item["data"] for item in references[:2]]
    if not mask or not references:
        return [compact_provider_reference(value) for value in values]
    primary = references[0]["data"]
    if len(values) == 1:
        # The selection mask must remain lossless and pixel-aligned. Only the
        # visual source is compacted for transport.
        return [compact_provider_reference(primary), mask]
    return [
        compact_provider_reference(marked_reference(primary, mask)),
        compact_provider_reference(values[1]),
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
