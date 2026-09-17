"""AI directions and credit charging for the Studio creation desk."""
from __future__ import annotations

import json
import os
from uuid import uuid4

from ..creative_modeling_generation import _json_content

MODEL = os.getenv("CREATIVE_STUDIO_DIRECTION_MODEL", "openai/gpt-5-nano")


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
        ], model=MODEL, max_tokens=140 + count * 150, temperature=.45,
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
        "references": [text(item.get("url"), 500) for item in data.get("references", []) if isinstance(item, dict) and text(item.get("url"), 500)][:2],
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


def charge(provider_result, client_id, user_id, count, project_id, run_id=None):
    from ..cadu_tool_billing import ToolTokenLedger, charge_from_provider
    from ..creative_modeling_service import CreativeModelingService
    credit_client_id = CreativeModelingService()._credits_crm_id(client_id) or int(client_id)
    ledger = ToolTokenLedger()
    ledger.assert_available(credit_client_id, estimated_tokens(count))
    run_id = str(run_id or uuid4().hex)
    charged = charge_from_provider(ledger=ledger, idempotency_key=f"studio:directions:{run_id}", client_id=credit_client_id, user_id=int(user_id), tool="studio.direction", stage="creative_directions", provider_result=provider_result, model=MODEL, metadata={"project_id": str(project_id or ""), "directions": int(count), "run_id": run_id}, margin_multiplier=12) or {}
    return int(charged.get("tokens_cobrados") or 0), ledger.available(credit_client_id)


def integer(value, default=0):
    try: return int(value)
    except (TypeError, ValueError): return default


def text(value, limit):
    return " ".join(str(value or "").split())[:limit]
