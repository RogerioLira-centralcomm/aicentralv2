"""API JSON do Agente CentralX."""

import base64
import binascii
import re
import uuid

from flask import current_app, jsonify, request, session

from ..services.openrouter_service import DEFAULT_CHAT_MODEL
from . import bp, storage
from .permissions import (
    agent_csrf_required,
    agent_internal_required_api,
    get_or_create_csrf_token,
    public_capabilities,
)
from .services.orchestrator import AgentOrchestratorError, run

MAX_PROMPT_LENGTH = 12000
RATE_LIMIT_MESSAGES = 30
MAX_ATTACHMENTS = 4
MAX_ATTACHMENTS_BYTES = 20 * 1024 * 1024
ATTACHMENT_LIMITS = {
    "image/png": 8 * 1024 * 1024,
    "image/jpeg": 8 * 1024 * 1024,
    "image/webp": 8 * 1024 * 1024,
    "application/pdf": 12 * 1024 * 1024,
    "text/plain": 1024 * 1024,
    "text/csv": 1024 * 1024,
    "application/json": 1024 * 1024,
}


def _context(raw=None):
    raw = raw or {}
    clean = {}
    limits = {"module": 50, "screen": 80, "entity_type": 50, "entity_id": 80, "entity_label": 200}
    for key, limit in limits.items():
        value = str(raw.get(key) or "").strip()[:limit]
        if key in {"module", "screen", "entity_type"}:
            value = re.sub(r"[^a-zA-Z0-9_.-]", "", value)
        elif key == "entity_id":
            value = re.sub(r"[^a-zA-Z0-9_-]", "", value)
        clean[key] = value
    return clean


def _suggestions(context):
    entity_type = (context.get("entity_type") or "").casefold()
    screen = (context.get("screen") or "").casefold()
    if entity_type in {"cliente", "client"}:
        return [
            {"label": "Ver contatos deste cliente", "prompt": "Liste os contatos deste cliente.", "icon": "fa-address-book"},
            {"label": "Ver atividades recentes", "prompt": "Liste as atividades deste cliente.", "icon": "fa-calendar-check"},
            {"label": "Ver cotações", "prompt": "Liste as cotações deste cliente.", "icon": "fa-file-invoice-dollar"},
            {"label": "Preparar follow-up", "prompt": "Com base no contexto que eu fornecer, redija uma mensagem de follow-up profissional.", "icon": "fa-pen"},
        ]
    if entity_type in {"cotacao", "quote"} or screen == "pipeline":
        return [
            {"label": "Consultar esta cotação", "prompt": "Consulte os detalhes desta cotação.", "icon": "fa-file-invoice"},
            {"label": "Buscar um cliente", "prompt": "Quero buscar um cliente.", "icon": "fa-magnifying-glass"},
            {"label": "Ver cotações de um cliente", "prompt": "Liste as cotações de um cliente.", "icon": "fa-chart-column"},
            {"label": "Analisar proposta", "prompt": "Vou anexar uma proposta. Resuma escopo, valores, riscos e próximos passos.", "icon": "fa-file-lines"},
        ]
    return [
        {"label": "Buscar um cliente", "prompt": "Busque um cliente pelo nome.", "icon": "fa-magnifying-glass"},
        {"label": "Consultar contatos", "prompt": "Quero listar os contatos de um cliente.", "icon": "fa-address-book"},
        {"label": "Consultar cotações", "prompt": "Quero listar as cotações de um cliente.", "icon": "fa-file-invoice-dollar"},
        {"label": "Analisar documento", "prompt": "Vou anexar um documento. Faça uma análise estruturada dos pontos principais.", "icon": "fa-file-lines"},
    ]


def _valid_signature(mime, raw):
    if mime == "application/pdf":
        return raw.startswith(b"%PDF-")
    if mime == "image/png":
        return raw.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return raw.startswith(b"\xff\xd8\xff")
    if mime == "image/webp":
        return len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
    if mime.startswith("text/") or mime == "application/json":
        try:
            raw.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    return False


def _validated_attachments(raw_items):
    if raw_items in (None, []):
        return []
    if not isinstance(raw_items, list) or len(raw_items) > MAX_ATTACHMENTS:
        raise ValueError("Envie no máximo 4 anexos por mensagem.")
    clean = []
    total = 0
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Anexo inválido.")
        mime = str(item.get("mime") or "").lower()
        if mime not in ATTACHMENT_LIMITS:
            raise ValueError("Formato de anexo não permitido.")
        name = re.sub(r"[^a-zA-Z0-9À-ÿ._() -]", "_", str(item.get("name") or "anexo"))[:180]
        data_url = str(item.get("data") or "")
        prefix = f"data:{mime};base64,"
        if not data_url.startswith(prefix):
            raise ValueError(f"Conteúdo inválido em {name}.")
        encoded = data_url[len(prefix):]
        if len(encoded) > (ATTACHMENT_LIMITS[mime] * 4 // 3) + 8:
            raise ValueError(f"{name} excede o limite permitido.")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError(f"Conteúdo inválido em {name}.")
        if not raw or len(raw) > ATTACHMENT_LIMITS[mime] or not _valid_signature(mime, raw):
            raise ValueError(f"Arquivo inválido ou muito grande: {name}.")
        total += len(raw)
        if total > MAX_ATTACHMENTS_BYTES:
            raise ValueError("Os anexos somados devem ter no máximo 20 MB.")
        clean.append({
            "name": name,
            "mime": mime,
            "size": len(raw),
            "data": data_url,
            "text": raw.decode("utf-8") if mime.startswith("text/") or mime == "application/json" else None,
        })
    return clean


def _conversation_payload(row):
    return {
        "id": str(row.get("id")),
        "title": row.get("title") or "Nova conversa",
        "context": {
            "module": row.get("context_module") or "",
            "screen": row.get("context_screen") or "",
            "entity_type": row.get("context_entity_type") or "",
            "entity_id": row.get("context_entity_id") or "",
            "entity_label": row.get("context_entity_label") or "",
        },
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@bp.get("/bootstrap")
@agent_internal_required_api
def bootstrap():
    context = _context(request.args)
    requested_id = request.args.get("conversation_id", type=int)
    active = None
    if requested_id:
        found = storage.get_conversation(requested_id, session["user_id"])
        if found:
            active = _conversation_payload(found["conversation"])
    if not active:
        conversations = storage.list_conversations(session["user_id"], limit=1)
        if conversations:
            active = _conversation_payload(conversations[0])
    return jsonify({
        "success": True,
        "data": {
            "user": {"id": session["user_id"], "name": session.get("user_name") or "Usuário"},
            "capabilities": public_capabilities(),
            "model": DEFAULT_CHAT_MODEL,
            "csrf_token": get_or_create_csrf_token(),
            "context": context,
            "active_conversation": active,
            "suggestions": _suggestions(context),
        },
    })


@bp.get("/conversations")
@agent_internal_required_api
def conversations_index():
    page = max(1, request.args.get("page", 1, type=int))
    rows = storage.list_conversations(session["user_id"], limit=30, page=page)
    return jsonify({"success": True, "data": [_conversation_payload(row) for row in rows], "page": page})


@bp.post("/conversations")
@agent_internal_required_api
@agent_csrf_required
def conversations_create():
    payload = request.get_json(silent=True) or {}
    row = storage.create_conversation(
        session["user_id"], _context(payload.get("context")), payload.get("title")
    )
    return jsonify({"success": True, "data": _conversation_payload(row)}), 201


@bp.get("/conversations/<int:conversation_id>")
@agent_internal_required_api
def conversations_show(conversation_id):
    found = storage.get_conversation(conversation_id, session["user_id"])
    if not found:
        return jsonify({"success": False, "error": "Conversa não encontrada."}), 404
    messages = [{
        "id": str(item.get("id")),
        "role": item.get("role"),
        "content": item.get("content") or "",
        "display": item.get("display_payload") or {},
        "created_at": item.get("created_at"),
    } for item in found["messages"] if item.get("role") != "system"]
    return jsonify({
        "success": True,
        "data": {"conversation": _conversation_payload(found["conversation"]), "messages": messages},
    })


@bp.post("/conversations/<int:conversation_id>/messages")
@agent_internal_required_api
@agent_csrf_required
def messages_create(conversation_id):
    payload = request.get_json(silent=True) or {}
    content = str(payload.get("message") or "").strip()
    if not content or len(content) > MAX_PROMPT_LENGTH:
        return jsonify({"success": False, "error": "Mensagem deve ter entre 1 e 12.000 caracteres."}), 400
    try:
        attachments = _validated_attachments(payload.get("attachments"))
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    request_id = uuid.uuid4().hex
    stage = "rate_limit"
    try:
        if storage.count_recent_user_messages(session["user_id"], minutes=5) >= RATE_LIMIT_MESSAGES:
            return jsonify({"success": False, "error": "Muitas consultas. Aguarde alguns minutos."}), 429
        context = _context(payload.get("context"))
        attachment_display = {
            "attachments": [
                {"name": item["name"], "mime": item["mime"], "size": item["size"]}
                for item in attachments
            ]
        } if attachments else None
        stage = "persist_user_message"
        user_message = storage.add_message(
            conversation_id, session["user_id"], "user", content, attachment_display
        )
        if not user_message:
            return jsonify({"success": False, "error": "Conversa não encontrada."}), 404
        stage = "orchestrator"
        result = run(
            conversation_id, session["user_id"], user_message["id"], context,
            set(public_capabilities()), request_id, attachments=attachments,
        )
        stage = "persist_assistant_message"
        assistant = storage.add_message(
            conversation_id, session["user_id"], "assistant", result["content"],
            result.get("display"), result.get("model"), result.get("usage"),
        )
        return jsonify({
            "success": True,
            "data": {
                "message": {
                    "id": str(assistant["id"]),
                    "role": "assistant",
                    "content": assistant["content"],
                    "display": assistant.get("display_payload") or result.get("display") or {},
                },
                "request_id": request_id,
            },
        })
    except storage.AgentStorageUnavailable as exc:
        current_app.logger.error(
            "Schema do Agente CentralX incompatível stage=%s request_id=%s: %s",
            stage, request_id, exc,
        )
        return jsonify({
            "success": False,
            "error": "O banco do agente precisa ser atualizado. Execute a migration pendente.",
            "request_id": request_id,
        }), 503
    except AgentOrchestratorError as exc:
        current_app.logger.warning("Agente CentralX indisponível request_id=%s: %s", request_id, exc)
        error_text = "Não consegui concluir a consulta agora. Tente novamente em instantes."
        try:
            storage.rollback_failed_transaction()
            storage.add_message(conversation_id, session["user_id"], "assistant", error_text)
        except Exception:
            current_app.logger.warning(
                "Não foi possível persistir erro do agente request_id=%s", request_id
            )
        return jsonify({"success": False, "error": error_text, "request_id": request_id}), 503
    except Exception:
        storage.rollback_failed_transaction()
        current_app.logger.exception(
            "Falha no Agente CentralX stage=%s request_id=%s", stage, request_id
        )
        storage_failure = stage in {
            "rate_limit", "persist_user_message", "persist_assistant_message"
        }
        return jsonify({
            "success": False,
            "error": (
                "Não foi possível acessar o histórico do agente. Tente novamente."
                if storage_failure
                else "Ocorreu uma falha ao consultar os dados. Tente novamente."
            ),
            "request_id": request_id,
        }), 503 if storage_failure else 500


@bp.get("/history")
@agent_internal_required_api
def history():
    return conversations_index()


@bp.get("/suggestions")
@agent_internal_required_api
def suggestions():
    context = _context(request.args)
    return jsonify({"success": True, "data": _suggestions(context)})


@bp.errorhandler(storage.AgentStorageUnavailable)
def storage_unavailable(exc):
    current_app.logger.warning("Agente CentralX sem migration: %s", exc)
    return jsonify({
        "success": False,
        "error": "O Agente CentralX ainda não foi ativado no banco. Execute a migration pendente.",
    }), 503
