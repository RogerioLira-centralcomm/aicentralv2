"""Provider-neutral conversation context assembly.

The persisted transcript is canonical. Memory state, recovered references and
selected context are bounded projections assembled here for every runtime.
"""

import json
import re
from dataclasses import dataclass, replace

from ..conversations.guardrails import history_context, normalize_colloquial, temporal_context
from ..conversations import conversation_memory
from ..intent_engine import interpret


_TURN_URL = re.compile(r"https?://[^\s<>\]\[\"']+", re.IGNORECASE)
_LINK_REFERENCE = re.compile(
    r"\b(?:esse|este|aquele|o)\s+(?:link|site|endere[cç]o|url)|"
    r"\b(?:link|site|url)\s+que\s+(?:eu\s+)?(?:enviei|mandei|passei|adicionei)|"
    r"\bcom\s+base\s+(?:nele|nisso|no\s+link)\b", re.IGNORECASE,
)
_SHORT_CONFIRMATION = re.compile(
    r"^\s*(?:sim|pode|pode\s+(?:criar|fazer|gerar|seguir)|fa[cç]a|crie|gere|continue|prossiga|ok)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_FORMAT_CONTINUATION = re.compile(
    r"\b(?:pode\s+ser|fa[cç]a|quero)\s+(?:um|uma|em\s+formato\s+de)?\s*"
    r"(plano|relat[oó]rio|apresenta[cç][aã]o|briefing|documento|texto)\b", re.IGNORECASE,
)
_GENERIC_REFERENCE = re.compile(
    r"\b(?:isso|isto|aquilo|nele|nela|deles|delas|esse|essa|este|esta|aquele|aquela)\b|"
    r"\b(?:o|a|esse|essa|aquele|aquela)\s+(?:arquivo|anexo|documento|texto|resposta|imagem|"
    r"plano|relat[oó]rio|apresenta[cç][aã]o|briefing|projeto|marca|campanha|conte[uú]do)\b|"
    r"\b(?:continue|continue\s+da[ií]|prossiga|retome|revise|ajuste|altere|melhore|resuma|"
    r"transforme|reescreva|complete|finalize)\b", re.IGNORECASE,
)


def selected_context(value):
    if not isinstance(value, dict):
        return None
    kind = str(value.get("type") or "selection")[:40]
    raw = str(value.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in raw.split("\n")).strip() if kind == "assistant_response" else " ".join(raw.split())
    limit = 40000 if kind == "assistant_response" else 12000
    if not 3 <= len(text) <= limit:
        return None
    result = {"type": kind, "label": str(value.get("label") or "Contexto selecionado")[:80], "text": text}
    source_message_id = str(value.get("source_message_id") or "")[:80]
    if source_message_id:
        result["source_message_id"] = source_message_id
    return result


def _metadata_response(message):
    metadata = message.get("metadata") if isinstance(message, dict) else None
    response = metadata.get("response") if isinstance(metadata, dict) else None
    return response if isinstance(response, dict) else {}


def previous_assistant_context(message, messages):
    explicit_reference = re.search(
        r"\b(?:[uú]ltima resposta|resposta anterior|texto anterior|conte[uú]do anterior|"
        r"esse texto|este texto|essa resposta|esta resposta|esse resumo|este resumo|"
        r"esse conte[uú]do|este conte[uú]do|esse material|este material|essa pesquisa|esta pesquisa|"
        r"o que voc[eê] (?:escreveu|gerou|respondeu))\b",
        str(message or ""), re.IGNORECASE,
    )
    natural_intent = interpret(str(message or ""), has_project=True)
    actionable_reference = (
        natural_intent.intent in {"create_artifact", "persist_content"}
        and natural_intent.source == "referenced_content"
    )
    if not explicit_reference and not actionable_reference:
        return None
    previous = next((item for item in reversed(messages or []) if item.get("role") == "assistant" and str(item.get("content") or "").strip()), None)
    return selected_context({
        "type": "assistant_response",
        "label": "Última resposta do assistente",
        "text": previous.get("content"),
        "source_message_id": previous.get("id"),
    }) if previous else None


def turn_context(message, messages):
    recent = [item for item in (messages or []) if item.get("role") in {"user", "assistant"}][-12:]
    if not recent:
        return None
    latest_url = ""
    latest_url_message = None
    pending = None
    files = []
    artifact = None
    latest_user_request = ""
    latest_assistant_answer = ""
    inspected_latest_assistant = False
    for item in reversed(recent):
        role = item.get("role")
        content = str(item.get("content") or "")
        if not latest_url and (match := _TURN_URL.search(content)):
            latest_url = match.group(0).rstrip(".,;:!?)")
            latest_url_message = item
        if role == "user" and not latest_user_request and content.strip():
            latest_user_request = " ".join(content.split())[:1200]
        if role == "assistant" and not latest_assistant_answer and content.strip():
            latest_assistant_answer = " ".join(content.split())[:1600]
        for file in item.get("files") or []:
            if not isinstance(file, dict):
                continue
            identity = str(file.get("id") or file.get("url") or file.get("name") or "")
            if identity and all(existing.get("identity") != identity for existing in files):
                files.append({"identity": identity, "name": str(file.get("name") or "Arquivo")[:180], "url": str(file.get("url") or "")[:2000]})
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        if artifact is None and metadata.get("artifact_id"):
            artifact = {"id": str(metadata["artifact_id"]), "title": str(metadata.get("artifact_title") or "Artefato")[:180]}
        if role == "assistant" and not inspected_latest_assistant:
            inspected_latest_assistant = True
            for block in reversed(_metadata_response(item).get("blocks") or []):
                if not isinstance(block, dict):
                    continue
                for option in reversed(block.get("items") or []):
                    if isinstance(option, dict) and option.get("auto_submit") and option.get("prompt"):
                        pending = {"title": str(option.get("title") or "Continuar"), "prompt": str(option["prompt"])}
                        break
                if pending:
                    break
    normalized = normalize_colloquial(message)
    format_match = _FORMAT_CONTINUATION.search(normalized)
    routing_message = f"Abra o link e crie um resumo editável estruturado como {format_match.group(1)}: {latest_url}" if format_match and latest_url else ""
    resolved = "format_refinement" if routing_message else "latest_url" if _LINK_REFERENCE.search(normalized) and latest_url else "pending_action" if _SHORT_CONFIRMATION.match(normalized) and pending else "recent_turn" if _GENERIC_REFERENCE.search(normalized) else "none"
    entities = {}
    if latest_url:
        entities["url"] = latest_url
    if files:
        entities["files"] = files[:5]
    if artifact:
        entities["artifact"] = artifact
    transcript = [{"role": item.get("role"), "content": " ".join(str(item.get("content") or "").split())[:1000]} for item in recent[-6:] if str(item.get("content") or "").strip()]
    return {"type": "conversation_turn", "active_entities": entities, "resolved_reference": resolved,
            "requires_selected_context": resolved != "none", "pending_action": pending,
            "routing_message": routing_message, "source_message_id": str((latest_url_message or {}).get("id") or ""),
            "latest_user_request": latest_user_request, "latest_assistant_answer": latest_assistant_answer,
            "recent_turns": transcript}


def turn_selected_context(turn):
    if not turn or not turn.get("requires_selected_context"):
        return None
    return selected_context({"type": "conversation_turn", "label": "Continuidade da conversa", "text": json.dumps(turn, ensure_ascii=False, separators=(",", ":"))})


@dataclass(frozen=True)
class BuiltContext:
    request_context: object
    history: str
    state: dict
    turn: dict | None
    routing_message: str
    diagnostics: dict


class ConversationContextBuilder:
    def build(self, *, message, messages, request_context, conversation_id, memory_enabled=True):
        turn = turn_context(message, messages)
        current = request_context
        if not current.selected_context:
            selected = previous_assistant_context(message, messages) or turn_selected_context(turn)
            if selected:
                current = replace(current, selected_context=selected)
        state = {}
        memory_packet = {}
        if memory_enabled:
            memory_packet = conversation_memory.packet(
                conversation_id=conversation_id if messages is not None else None,
                organization_id=current.organization_id, client_id=current.client_id,
                user_id=current.user_id, query=message,
            )
            state = memory_packet
        if turn:
            state = {**state, "turn_context": turn}
        timing = temporal_context(message)
        if timing.get("matched"):
            state = {**state, "temporal_context": timing}
        routing = turn.get("routing_message") if turn else ""
        if not routing and turn and turn.get("resolved_reference") == "pending_action":
            routing = (turn.get("pending_action") or {}).get("prompt") or ""
        transcript = history_context(messages or [])
        recent = (messages or [])[-12:]
        sequences = [int(item.get("conversation_sequence") or item.get("message_sequence") or 0)
                     for item in recent if item.get("conversation_sequence") or item.get("message_sequence")]
        diagnostics = {
            "history_message_count": len(messages or []),
            "recent_message_count": len(recent),
            "recent_sequence_start": min(sequences) if sequences else None,
            "recent_sequence_end": max(sequences) if sequences else None,
            "history_chars": len(transcript),
            "memory_present": bool(
                memory_packet.get("estado")
                or memory_packet.get("mensagens_originais_recuperadas")
                or memory_packet.get("cobre_ate_mensagem")
            ),
            "memory_version": memory_packet.get("versao"),
            "memory_covers_through": int(memory_packet.get("cobre_ate_mensagem") or 0),
            "retrieved_message_count": len(memory_packet.get("mensagens_originais_recuperadas") or []),
            "resolved_reference": (turn or {}).get("resolved_reference", "none"),
        }
        return BuiltContext(current, transcript, state, turn, routing or message, diagnostics)
