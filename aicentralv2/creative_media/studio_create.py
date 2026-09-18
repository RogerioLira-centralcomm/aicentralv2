"""AI directions and credit charging for the Studio creation desk."""
from __future__ import annotations

import base64
import binascii
import io
import json
import os
import re
from uuid import uuid4

from PIL import Image, ImageFilter

from ..creative_modeling_generation import _json_content

MODEL = os.getenv("CREATIVE_STUDIO_DIRECTION_MODEL", "openai/gpt-5-nano")
IMAGE_MODEL = os.getenv("CREATIVE_STUDIO_IMAGE_MODEL", "openai/gpt-image-2")
IMAGE_ROLES = {
    "primary": "the primary/base image whose unrequested content must be preserved",
    "insert": "an element source to integrate naturally into the primary image",
    "replace": "the visual source for the selected replacement region",
    "style": "a style-only reference; do not copy its subject or text",
    "composition": "a composition-only reference; do not copy its subject or text",
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
    request = text(data.get("prompt"), 1200)
    if not request:
        raise ValueError("Descreva a direção que deseja criar.")
    context = clean_context(data.get("context"), count)
    response = text_callable(
        [
            {"role": "system", "content": system_prompt(count)},
            {"role": "user", "content": json.dumps({"pedido": request, "contexto": context}, ensure_ascii=False)},
        # Each direction contains scene, composition, restrictions, and safe
        # copy. The former 440-token budget for two directions could truncate
        # the JSON object before its closing delimiter.
        ], model=MODEL, max_tokens=900 + count * 320, temperature=.45,
        response_format={"type": "json_object"},
    )
    content = response.get("message", {}).get("content") if isinstance(response, dict) else response
    raw = content if isinstance(content, dict) else _json_content(content)
    items = []
    for item in raw.get("directions", []) if isinstance(raw, dict) else []:
        if not isinstance(item, dict):
            continue
        title, prompt = text(item.get("title"), 90), text(item.get("prompt"), 900)
        if title and prompt:
            items.append({"title": title, "summary": text(item.get("summary") or item.get("rationale"), 220) or "Direção baseada no briefing do projeto.", "prompt": prompt})
        if len(items) == count:
            break
    if not items:
        raise ValueError("O agente não devolveu direções utilizáveis. Tente novamente.")
    return {"directions": items, "count": len(items), "model": str(response.get("model") or MODEL)}, response


def clean_context(raw, count):
    data = raw if isinstance(raw, dict) else {}
    return {key: text(data.get(key), limit) for key, limit in (("project_name", 120), ("brand", 120), ("brief", 1800), ("objective", 300), ("audience", 300), ("purpose", 24), ("format", 24))} | {
        "channels": [text(item, 24) for item in data.get("channels", []) if text(item, 24)][:5],
        "iab_formats": [text(item, 32) for item in data.get("formats", []) if text(item, 32)][:6],
        "direction_intensity": max(0, min(integer(data.get("direction_intensity"), 70), 100)),
        "requested_directions": count,
        "references": [clean_direction_reference(item, index) for index, item in enumerate(data.get("references", [])[:2]) if isinstance(item, dict)],
    }


def clean_direction_reference(item, index):
    role = str(item.get("role") or ("primary" if index == 0 else "insert"))
    if role not in IMAGE_ROLES:
        role = "insert"
    raw_url = str(item.get("url") or "")
    return {
        "label": text(item.get("name") or item.get("label") or f"Imagem {index + 1}", 140),
        "role": role,
        "instruction": IMAGE_ROLES[role],
        "url": text(raw_url, 500) if raw_url.startswith(("https://", "http://", "/static/")) else "inline upload",
    }


def system_prompt(count):
    return f"""Você é diretor criativo de mídia no Cadu Studio. Crie exatamente {count} direções distintas para uma peça publicitária a partir do projeto fornecido.

Responda somente JSON no formato {{\"directions\":[{{\"title\":\"...\",\"summary\":\"...\",\"prompt\":\"...\"}}]}}. Use português do Brasil.

Cada prompt deve ser executável por um gerador de imagem e conter, nesta ordem quando houver contexto: objetivo de comunicação; tipo de peça (institucional, lançamento ou produto); praça ou contexto cultural brasileiro; público e momento humano; assunto principal; cenário; composição e área de respiro; linguagem visual, iluminação e materiais; paleta e ativos de marca; formato/canal exato; texto de campanha literal apenas quando fornecido; e restrições.

Para Display, trate o formato IAB informado como uma unidade publicitária final — não o transforme em pôster ou interface. Para CTV, trate como still cinematográfico 16:9. Para social, preserve área segura e leitura no feed. Escreva uma cena específica, não adjetivos vagos como “moderno”, “bonito” ou “impactante”. Prefira detalhes observáveis: lugar, hora, enquadramento, distância de câmera, gesto, textura e espaço para copy.

Use a marca, briefing, referências e ativos do contexto como fonte de verdade. Não invente preço, promoção, produto, dado, prazo, benefício, CTA, logotipo ou slogan. Se não houver texto literal aprovado, peça espaço reservado para a assinatura, sem fabricar tipografia. Todo texto publicitário visível deve ser português do Brasil; se a renderização textual não for confiável, instrua a manter a área livre para composição posterior. Não inclua marca d'água, interface de plataforma, mockup de dashboard ou logos de terceiros. Não use pessoas identificáveis sem necessidade. Preserve briefing, marca, canal e formato."""


def assert_available(client_id, count):
    from ..cadu_tool_billing import ToolTokenLedger
    from ..creative_modeling_service import CreativeModelingService
    credit_client_id = CreativeModelingService()._credits_crm_id(client_id) or int(client_id)
    ToolTokenLedger().assert_available(credit_client_id, estimated_tokens(count))
    return credit_client_id


def charge(provider_result, client_id, user_id, count, project_id, run_id=None,
           studio_session_id="", studio_root_session_id=""):
    from ..cadu_tool_billing import ToolTokenLedger, charge_from_provider
    from ..creative_modeling_service import CreativeModelingService
    credit_client_id = CreativeModelingService()._credits_crm_id(client_id) or int(client_id)
    ledger = ToolTokenLedger()
    ledger.assert_available(credit_client_id, estimated_tokens(count))
    run_id = str(run_id or uuid4().hex)
    charged = charge_from_provider(
        ledger=ledger, idempotency_key=f"studio:directions:{run_id}",
        client_id=credit_client_id, user_id=int(user_id), tool="studio.direction",
        stage="creative_directions", provider_result=provider_result, model=MODEL,
        metadata={
            "project_id": str(project_id or ""), "directions": int(count), "run_id": run_id,
            "studio_session_id": str(studio_session_id or ""),
            "studio_root_session_id": str(studio_root_session_id or studio_session_id or ""),
        },
        margin_multiplier=12,
    ) or {}
    return int(charged.get("tokens_cobrados") or 0), ledger.available(credit_client_id)


def create_image(payload, modeling, client_id, user_id):
    """Generate one Studio still with explicit reference roles and mask-safe composition."""
    data = payload if isinstance(payload, dict) else {}
    prompt = text(data.get("prompt"), 4000)
    if not prompt:
        raise ValueError("Descreva a imagem que deseja gerar.")
    aspect_ratio = str(data.get("aspect_ratio") or "1:1")
    if aspect_ratio not in {"1:1", "4:5", "9:16", "16:9"}:
        raise ValueError("Formato de imagem inválido.")
    references = normalize_image_references(data.get("references"), modeling.storage)
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
    credit_client_id = modeling._credits_crm_id(client_id) or int(client_id)
    modeling.credit_ledger.assert_available(
        credit_client_id, cost_token_equivalent(estimate, margin_multiplier=8)
    )
    if mask and primary:
        validate_mask(primary["data"], mask)

    role_lines = [
        f"IMAGE {index}: {IMAGE_ROLES[item['role']]} ({item['label']})."
        for index, item in enumerate(references, start=1)
    ]
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
    technical_prompt = "\n".join([
        prompt,
        "\nREFERENCE CONTRACT:",
        *(role_lines or ["No image reference was supplied; create an original image."]),
        edit_guard,
        f"Output aspect ratio: {aspect_ratio}.",
    ])
    provider_references = provider_image_references(references, mask)
    requested_quality = str(data.get("quality") or "Padrão").strip().lower()
    quality_map = {"econômica": ("low", "1K"), "economica": ("low", "1K"), "padrão": ("medium", "1K"), "padrao": ("medium", "1K"), "alta": ("high", "2K")}
    provider_quality, provider_resolution = quality_map.get(requested_quality, ("medium", "1K"))
    provider = modeling.generator.generate_image(
        technical_prompt,
        provider_references,
        aspect_ratio=aspect_ratio,
        quality=provider_quality,
        resolution=provider_resolution,
        model=IMAGE_MODEL,
    )
    encoded = provider.get("b64_json")
    if not encoded:
        raise ValueError("O gerador não devolveu uma imagem.")
    if mask and primary:
        encoded = compose_inside_mask(encoded, primary["data"], mask)
    image_url = modeling.storage.save_generated_base64(
        encoded, provider.get("output_format") or "png"
    )
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
    try:
        remaining = modeling.credit_ledger.available(
            modeling._credits_crm_id(client_id) or int(client_id)
        )
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
        if role not in IMAGE_ROLES:
            raise ValueError("A função de uma das imagens é inválida.")
        value = str(item.get("url") or "")
        if value.startswith("data:image/"):
            image_data = value
        elif value.startswith("/static/uploads/creative_generated/"):
            image_data = storage.generated_as_data_url(value)
        elif value.startswith("/static/uploads/creative_references/"):
            image_data = storage.reference_as_data_url(value, "image/png")
        elif value.startswith(("https://", "http://")):
            image_data = value
        else:
            raise ValueError("Uma das imagens relacionadas não está disponível.")
        cleaned.append({
            "id": text(item.get("id"), 160),
            "role": role,
            "label": text(item.get("label") or f"Imagem {index + 1}", 120),
            "data": image_data,
        })
    if sum(1 for item in cleaned if item["role"] == "primary") > 1:
        raise ValueError("Escolha somente uma imagem principal.")
    return sorted(cleaned, key=lambda item: item["role"] != "primary")


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
        return values
    primary = references[0]["data"]
    if len(values) == 1:
        return [primary, mask]
    return [marked_reference(primary, mask), values[1]]


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
