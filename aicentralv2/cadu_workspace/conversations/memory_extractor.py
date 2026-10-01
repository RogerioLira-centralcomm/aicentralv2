"""Extract project decisions, constraints and risks from new chat messages with a model.

Runs in the memory worker, never in the HTTP turn. Only statements made by the
people in the conversation can become memory; assistant text is context.
"""
from __future__ import annotations

import json
import os
import re
from uuid import UUID, uuid4

import requests
from flask import current_app

from ...cadu_family import repository
from . import working_memory

EXTRACTOR_VERSION = "llm-memory-v1"
URL = "https://api.openai.com/v1/chat/completions"
MODEL = os.getenv("CADU_MEMORY_EXTRACTION_MODEL", "gpt-4.1-mini")
TIMEOUT = float(os.getenv("CADU_MEMORY_EXTRACTION_TIMEOUT", "30"))
MAX_NEW_MESSAGES = 30
CONTEXT_MESSAGES = 4
MESSAGE_CHARS = 1500
MAX_ITEMS = 6
AUTO_CONFIRM_MIN = 0.85
AUTO_CONFIRM_KINDS = {"decision", "constraint"}

SYSTEM = """Você registra a memória de trabalho de um projeto de marketing e mídia a partir de uma conversa.
Extraia somente o que as PESSOAS (mensagens "usuario") afirmaram de forma explícita e que continuará valendo depois da conversa:
- decision: algo decidido ou aprovado ("vamos com Google Ads", "verba fechada em R$ 50 mil", "lançamento dia 15/10").
- constraint: restrição ou regra ("não usar humor", "aprovação do jurídico antes de publicar", "teto de CPL R$ 40").
- risk: risco ou dependência apontado ("depende da liberação do estoque").
- next_step: compromisso de próximo passo com responsável ou prazo.
- brand_context: fato duradouro sobre a marca ou o cliente.
Regras:
- Mensagens "assistente" são contexto, nunca fonte. Se o usuário aceitar uma proposta do assistente ("pode ser", "fechado"), registre a decisão citando a mensagem do usuário e use confidence até 0.8.
- Não registre perguntas, hipóteses, brainstorming, opiniões em dúvida, conselhos genéricos nem o que já é óbvio da conversa.
- Mantenha números, nomes, datas e canais exatamente como ditos. Cada item é uma frase autônoma, compreensível sem a conversa, com até 300 caracteres.
- confidence: 0.9 a 1.0 para afirmação clara e definitiva do usuário; 0.6 a 0.8 para o que é provável ou depende de interpretação.
- source_message_id deve ser um id presente na lista, de uma mensagem "usuario".
- Se não houver nada, retorne {"items": []}. No máximo 6 itens.
Responda somente JSON: {"items":[{"kind":"decision","summary":"...","confidence":0.95,"source_message_id":"..."}]}"""


def enabled() -> bool:
    return os.getenv("CADU_MEMORY_EXTRACTION", "1") != "0" and working_memory.available() \
        and repository.family_table_available("cadu_working_memory_extraction")


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", str(value or "").lower()).split())


def _similar(a: str, b: str) -> bool:
    left, right = set(_normalize(a).split()), set(_normalize(b).split())
    if not left or not right:
        return False
    return len(left & right) / len(left | right) >= 0.75


def parse_items(raw: str, allowed: dict[str, str]) -> list[dict]:
    """Validate model output; ``allowed`` maps message id to role."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    items, seen = [], []
    for item in (data.get("items") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        summary = " ".join(str(item.get("summary") or "").split())[:300]
        source = str(item.get("source_message_id") or "")
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence"))))
        except (TypeError, ValueError):
            continue
        if kind not in working_memory.KINDS or len(summary) < 12 or allowed.get(source) != "user":
            continue
        if any(_similar(summary, other) for other in seen):
            continue
        seen.append(summary)
        items.append({"kind": kind, "summary": summary, "confidence": round(confidence, 3),
                      "source_message_id": source})
    return items[:MAX_ITEMS]


def should_auto_confirm(item: dict) -> bool:
    return item["kind"] in AUTO_CONFIRM_KINDS and item["confidence"] >= AUTO_CONFIRM_MIN


def _call_model(messages: list[dict]) -> str:
    from ...services.openrouter_service import resolve_openai_api_key

    key = resolve_openai_api_key()
    if not key:
        raise RuntimeError("OpenAI não configurada para extração de memória.")
    lines = [f'[{item["id"]}] {"usuario" if item["role"] == "user" else "assistente"}'
             f'{" (" + item["author"] + ")" if item["role"] == "user" and item.get("author") else ""}: '
             f'{" ".join(str(item["content"] or "").split())[:MESSAGE_CHARS]}' for item in messages]
    response = requests.post(
        URL, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": 0, "max_tokens": 900,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": "Conversa:\n" + "\n".join(lines)}]},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def extract_conversation(conversation_id: str) -> int:
    """Read messages added since the last pass; returns how many memories were stored."""
    if not enabled():
        return 0
    binding = repository.rows(
        """SELECT binding.client_id, binding.project_ref, conversation.id_contato_cliente AS author_id,
                  author.nome_completo AS author_name
             FROM cadu_family_conversation_context binding
             JOIN cadu_conversations conversation ON conversation.id=binding.conversation_id
        LEFT JOIN tbl_contato_cliente author ON author.id_contato_cliente=conversation.id_contato_cliente
            WHERE binding.conversation_id=%s AND binding.project_ref IS NOT NULL""", (conversation_id,))
    if not binding:
        return 0
    client_id, project_ref = int(binding[0]["client_id"]), str(binding[0]["project_ref"])
    author = str(binding[0].get("author_name") or "").split(" ")[0]
    mark = repository.rows("SELECT last_sequence FROM cadu_working_memory_extraction WHERE conversation_id=%s",
                           (conversation_id,))
    last = int(mark[0]["last_sequence"]) if mark else 0
    fresh = repository.rows(
        """SELECT id, role, content, conversation_sequence FROM cadu_conversation_messages
            WHERE conversation_id=%s AND role IN ('user','assistant') AND conversation_sequence > %s
            ORDER BY conversation_sequence LIMIT %s""", (conversation_id, last, MAX_NEW_MESSAGES))
    if not any(item["role"] == "user" for item in fresh):
        return 0
    context = repository.rows(
        """SELECT id, role, content, conversation_sequence FROM (
              SELECT id, role, content, conversation_sequence FROM cadu_conversation_messages
               WHERE conversation_id=%s AND role IN ('user','assistant') AND conversation_sequence <= %s
               ORDER BY conversation_sequence DESC LIMIT %s) previous
            ORDER BY conversation_sequence""", (conversation_id, last, CONTEXT_MESSAGES)) if last else []
    window = [{**dict(item), "author": author} for item in [*context, *fresh]]
    allowed = {str(item["id"]): item["role"] for item in window}
    items = parse_items(_call_model(window), allowed)
    stored = _store(client_id, project_ref, conversation_id, int(binding[0]["author_id"]), items)
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO cadu_working_memory_extraction
                (conversation_id, last_sequence, extractor_version, updated_at) VALUES (%s,%s,%s,NOW())
                ON CONFLICT (conversation_id) DO UPDATE SET last_sequence=EXCLUDED.last_sequence,
                    extractor_version=EXCLUDED.extractor_version, updated_at=NOW()""",
                        (conversation_id, int(fresh[-1]["conversation_sequence"]), EXTRACTOR_VERSION))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return stored


def _store(client_id, project_ref, conversation_id, author_id, items) -> int:
    if not items:
        return 0
    existing = [row["summary"] for row in repository.rows(
        """SELECT summary FROM cadu_working_memories
            WHERE client_id=%s AND (project_ref=%s OR (scope='client' AND project_ref IS NULL))""",
        (client_id, project_ref))]
    conn = repository.get_db()
    stored = 0
    try:
        with conn.cursor() as cur:
            for item in items:
                if any(_similar(item["summary"], known) for known in existing):
                    continue
                confirmed = should_auto_confirm(item)
                memory_id = str(uuid4())
                cur.execute(
                    """INSERT INTO cadu_working_memories
                        (id, organization_id, client_id, project_ref, scope, kind, summary, confidence, status,
                         source_conversation_id, source_message_id, source_author_id, reviewed_at)
                        VALUES (%s,%s,%s,%s,'project',%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s THEN NOW() END)""",
                    (memory_id, client_id, client_id, project_ref, item["kind"], item["summary"],
                     item["confidence"], "confirmed" if confirmed else "proposed", conversation_id,
                     str(UUID(item["source_message_id"])), author_id, confirmed))
                cur.execute(
                    """INSERT INTO cadu_working_memory_events (memory_id, actor_id, event, detail)
                       VALUES (%s,NULL,%s,%s::jsonb)""",
                    (memory_id, "confirmed" if confirmed else "proposed",
                     json.dumps({"source": "llm_extractor", "version": EXTRACTOR_VERSION,
                                 "auto_confirmed": confirmed, "confidence": item["confidence"]})))
                existing.append(item["summary"])
                stored += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return stored


def safe_extract(conversation_id: str) -> int:
    """Extraction is additive; a model failure is retried on the next turn."""
    try:
        return extract_conversation(conversation_id)
    except Exception as exc:
        repository.get_db().rollback()
        current_app.logger.warning("Extração de memória falhou; conversa=%s erro=%s",
                                   conversation_id, type(exc).__name__)
        return 0
