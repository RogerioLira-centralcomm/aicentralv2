"""API JSON do Agente CentralX."""

import base64
import binascii
import re
import uuid

from flask import current_app, jsonify, request, session

from ..crm_v3_repository import get_store
from ..services.openrouter_service import DEFAULT_CHAT_MODEL
from . import bp, storage
from .insights import build_insights, suggestion_prompts
from .permissions import (
    agent_csrf_required,
    agent_internal_required_api,
    get_or_create_csrf_token,
    has_global_commercial_access,
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
CLIENT_EDITABLE_FIELDS = {
    "nome",
    "nome_fantasia",
    "razao_social",
    "cnpj",
    "classificacao_cliente",
    "site_url",
    "nota_executivo",
    "observacoes_comerciais_adicionais",
    "opera_midia",
    "demanda_dados",
    "demanda_programatica_canais",
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
    return suggestion_prompts(context)


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


def _requested_global_scope():
    return (
        str(request.args.get("scope") or "").casefold() == "all"
        and has_global_commercial_access()
    )


def _client_allowed(client):
    return bool(
        client
        and (
            has_global_commercial_access()
            or str(client.get("executivo_id") or "") == str(session["user_id"])
        )
    )


def _quote_allowed(quote):
    return bool(
        quote
        and (
            has_global_commercial_access()
            or str(quote.get("executivo_id") or "") == str(session["user_id"])
        )
    )


def _commercial_client_payload(store, client):
    client_id = str(client["id"])
    contacts = store.list_contatos(client_id) or []
    activities = store.list_atividades(client_id) or []
    quotes = store.list_cotacoes(client_id, include_vinculados=False) or []
    if not has_global_commercial_access():
        quotes = [quote for quote in quotes if _quote_allowed(quote)]
    context = {
        "module": "crm",
        "screen": "cliente_detalhe",
        "entity_type": "cliente",
        "entity_id": client_id,
        "entity_label": client.get("nome") or "Cliente",
    }
    return {
        "type": "cliente",
        "record": client,
        "contacts": contacts[:5],
        "activities": activities[:5],
        "quotes": quotes[:8],
        "insights": build_insights(context),
        "can_edit": True,
        "url": f"/crm-v3/#cliente={client_id}",
    }


def _commercial_quote_payload(store, quote):
    client_id = str(quote.get("cliente_id") or "")
    client = store.get_cliente(client_id) if client_id else None
    context = {
        "module": "comercial",
        "screen": "cotacao",
        "entity_type": "cotacao",
        "entity_id": str(quote["id"]),
        "entity_label": quote.get("titulo") or quote.get("numero_cotacao") or "Cotação",
    }
    return {
        "type": "cotacao",
        "record": quote,
        "client": client,
        "insights": build_insights(context),
        "can_edit": False,
        "url": f"/cotacoes/{quote['id']}/detalhes",
    }


def _authorized_insights(context):
    entity_type = str(context.get("entity_type") or "").casefold()
    entity_id = str(context.get("entity_id") or "")
    if not entity_id or entity_type not in {"cliente", "client", "cotacao", "quote"}:
        return build_insights(context)
    store = get_store()
    if entity_type in {"cliente", "client"} and entity_id:
        if not _client_allowed(store.get_cliente(entity_id)):
            return {"entity": None, "alerts": [], "prompts": _suggestions({})}
    if entity_type in {"cotacao", "quote"} and entity_id:
        if not _quote_allowed(store.get_cotacao(entity_id)):
            return {"entity": None, "alerts": [], "prompts": _suggestions({})}
    return build_insights(context)


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
            "insights": _authorized_insights(context),
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


@bp.get("/insights")
@agent_internal_required_api
def insights():
    context = _context(request.args)
    try:
        data = _authorized_insights(context)
    except Exception:
        current_app.logger.exception("Falha ao montar insights do agente")
        data = {"entity": None, "alerts": [], "prompts": _suggestions(context)}
    return jsonify({"success": True, "data": data})


@bp.get("/commercial/search")
@agent_internal_required_api
def commercial_search():
    query = str(request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({
            "success": True,
            "data": {"clients": [], "quotes": [], "scope": "mine"},
        })
    kind = str(request.args.get("kind") or "all").casefold()
    if kind not in {"all", "clients", "quotes"}:
        return jsonify({"success": False, "error": "Tipo de busca inválido."}), 400
    limit = max(1, min(request.args.get("limit", 8, type=int) or 8, 20))
    global_scope = _requested_global_scope()
    executive_id = None if global_scope else session["user_id"]
    store = get_store()
    clients = (
        store.search_clientes(query, limit, executivo_id=executive_id)
        if kind in {"all", "clients"}
        else []
    )
    quotes = (
        store.search_cotacoes(query, limit, executivo_id=executive_id)
        if kind in {"all", "quotes"}
        else []
    )
    return jsonify({
        "success": True,
        "data": {
            "clients": clients,
            "quotes": quotes,
            "scope": "all" if global_scope else "mine",
        },
    })


@bp.get("/commercial/record/<entity_type>/<entity_id>")
@agent_internal_required_api
def commercial_record(entity_type, entity_id):
    store = get_store()
    entity_type = str(entity_type).casefold()
    if entity_type in {"cliente", "client"}:
        client = store.get_cliente(str(entity_id))
        if not _client_allowed(client):
            return jsonify({"success": False, "error": "Cliente não encontrado."}), 404
        return jsonify({
            "success": True,
            "data": _commercial_client_payload(store, client),
        })
    if entity_type in {"cotacao", "quote"}:
        quote = store.get_cotacao(str(entity_id))
        if not _quote_allowed(quote):
            return jsonify({"success": False, "error": "Cotação não encontrada."}), 404
        return jsonify({
            "success": True,
            "data": _commercial_quote_payload(store, quote),
        })
    return jsonify({"success": False, "error": "Tipo de registro inválido."}), 400


@bp.patch("/commercial/clients/<cliente_id>")
@agent_internal_required_api
@agent_csrf_required
def commercial_update_client(cliente_id):
    store = get_store()
    client = store.get_cliente(str(cliente_id))
    if not _client_allowed(client):
        return jsonify({"success": False, "error": "Cliente não encontrado."}), 404
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return jsonify({"success": False, "error": "Corpo JSON inválido."}), 400
    payload = {
        key: value for key, value in raw.items()
        if key in CLIENT_EDITABLE_FIELDS
    }
    if not payload:
        return jsonify({"success": False, "error": "Nenhum campo editável informado."}), 400
    try:
        updated = store.update_cliente(str(cliente_id), payload)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    if not updated:
        return jsonify({"success": False, "error": "Cliente não encontrado."}), 404
    return jsonify({
        "success": True,
        "data": _commercial_client_payload(store, updated),
    })


@bp.errorhandler(storage.AgentStorageUnavailable)
def storage_unavailable(exc):
    current_app.logger.warning("Agente CentralX sem migration: %s", exc)
    return jsonify({
        "success": False,
        "error": "O Agente CentralX ainda não foi ativado no banco. Execute a migration pendente.",
    }), 503
