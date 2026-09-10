"""API JSON do Agente CentralX."""

import base64
import binascii
import re
import uuid

from flask import current_app, jsonify, request, session

from .. import db
from ..crm_v3_repository import StoreUnavailable, get_store
from ..pi_operacao_repository import PiOperacaoRepository
from ..services.openrouter_service import DEFAULT_CHAT_MODEL
from . import bp, storage
from .context_records import (
    ContextRecordError,
    build_context_record,
    canonical_type,
    normalize_agent_context,
    search_operational_records,
)
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
CONTACT_EDITABLE_FIELDS = {
    "nome", "email", "telefone", "telefone_secundario",
}


def _context(raw=None):
    raw = raw or {}
    incoming = dict(raw)
    if not incoming.get("entity_label") and incoming.get("entity_name"):
        incoming["entity_label"] = incoming.get("entity_name")
    normalized = normalize_agent_context(incoming)
    clean = {}
    limits = {
        "module": 50, "screen": 80, "entity_type": 50,
        "entity_id": 80, "entity_label": 200, "entity_subtype": 40,
    }
    for key, limit in limits.items():
        value = str(normalized.get(key) or "").strip()[:limit]
        if key in {"module", "screen", "entity_type", "entity_subtype"}:
            value = re.sub(r"[^a-zA-Z0-9_.-]", "", value)
        elif key == "entity_id":
            value = re.sub(r"[^a-zA-Z0-9_-]", "", value)
        clean[key] = value
    return clean


def _suggestions(context):
    return suggestion_prompts(context)


def _current_user_payload():
    payload = {
        "id": session["user_id"],
        "name": session.get("user_name") or "Usuário",
        "photo_url": "",
    }
    try:
        user = db.obter_usuario_por_id(session["user_id"]) or {}
        payload["name"] = user.get("nome_completo") or payload["name"]
        payload["photo_url"] = user.get("foto_url") or ""
    except Exception:
        current_app.logger.debug(
            "Foto do usuário indisponível no bootstrap do agente.",
            exc_info=True,
        )
    return payload


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
            "entity_subtype": row.get("context_entity_subtype") or "",
        },
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _has_global_read():
    return "commercial.read.global" in public_capabilities()


def _requested_global_scope():
    if not _has_global_read():
        return False
    return str(request.args.get("scope") or "all").casefold() != "mine"


def _client_allowed(client):
    """Escrita: dono do registro ou admin."""
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


def _client_visible(client):
    return bool(
        client
        and (
            _has_global_read()
            or str(client.get("executivo_id") or "") == str(session["user_id"])
        )
    )


def _quote_visible(quote):
    return bool(
        quote
        and (
            _has_global_read()
            or str(quote.get("executivo_id") or "") == str(session["user_id"])
        )
    )


def _commercial_client_payload(store, client):
    client_id = str(client["id"])
    contacts = store.list_contatos(client_id) or []
    activities = store.list_atividades(client_id) or []
    quotes = store.list_cotacoes(client_id, include_vinculados=False) or []
    if not _has_global_read():
        quotes = [quote for quote in quotes if _quote_visible(quote)]
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
        "can_edit": _client_allowed(client),
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
        if not _client_visible(store.get_cliente(entity_id)):
            return {"entity": None, "alerts": [], "prompts": _suggestions({})}
    if entity_type in {"cotacao", "quote"} and entity_id:
        if not _quote_visible(store.get_cotacao(entity_id)):
            return {"entity": None, "alerts": [], "prompts": _suggestions({})}
    return build_insights(context)


def _safe_insights(context):
    try:
        return _authorized_insights(context)
    except Exception:
        storage.rollback_failed_transaction()
        current_app.logger.exception("Falha ao montar insights do agente")
        return {"entity": None, "alerts": [], "prompts": _suggestions(context)}


def _safe_search(label, fn, fallback=None):
    try:
        return fn()
    except Exception:
        storage.rollback_failed_transaction()
        current_app.logger.exception("Falha na busca %s do agente", label)
        return [] if fallback is None else fallback


@bp.get("/bootstrap")
@agent_internal_required_api
def bootstrap():
    context = _context(request.args)
    requested_id = request.args.get("conversation_id", type=int)
    active = None
    try:
        if requested_id:
            found = storage.get_conversation(requested_id, session["user_id"])
            if found:
                active = _conversation_payload(found["conversation"])
        if not active:
            conversations = storage.list_conversations(session["user_id"], limit=1)
            if conversations:
                active = _conversation_payload(conversations[0])
    except Exception:
        storage.rollback_failed_transaction()
        current_app.logger.exception("Histórico do agente indisponível no bootstrap")
        active = None
    return jsonify({
        "success": True,
        "data": {
            "user": _current_user_payload(),
            "capabilities": public_capabilities(),
            "model": DEFAULT_CHAT_MODEL,
            "csrf_token": get_or_create_csrf_token(),
            "context": context,
            "active_conversation": active,
            "suggestions": _suggestions(context),
            "insights": _safe_insights(context),
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


@bp.patch("/conversations/<int:conversation_id>/context")
@agent_internal_required_api
@agent_csrf_required
def conversations_update_context(conversation_id):
    payload = request.get_json(silent=True) or {}
    row = storage.update_conversation_context(
        conversation_id,
        session["user_id"],
        _context(payload.get("context")),
    )
    if not row:
        return jsonify({"success": False, "error": "Conversa não encontrada."}), 404
    return jsonify({"success": True, "data": _conversation_payload(row)})


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
        if not storage.update_conversation_context(
            conversation_id, session["user_id"], context
        ):
            return jsonify({"success": False, "error": "Conversa não encontrada."}), 404
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
                    "ui": result.get("ui") or {},
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
    return jsonify({"success": True, "data": _safe_insights(context)})


@bp.get("/commercial/search")
@agent_internal_required_api
def commercial_search():
    query = str(request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({
            "success": True,
            "data": {
                "clients": [], "quotes": [], "contacts": [],
                "pis": [], "campaigns": [], "channels": [], "audiences": [],
                "scope": "mine",
            },
        })
    kind = str(request.args.get("kind") or "all").casefold()
    if kind not in {"all", "clients", "contacts", "quotes", "pis", "campaigns", "channels", "audiences"}:
        return jsonify({"success": False, "error": "Tipo de busca inválido."}), 400
    limit = max(1, min(request.args.get("limit", 8, type=int) or 8, 20))
    global_scope = _requested_global_scope()
    executive_id = None if global_scope else session["user_id"]
    try:
        store = get_store()
    except StoreUnavailable:
        storage.rollback_failed_transaction()
        current_app.logger.warning("CRM indisponível na busca comercial do agente")
        store = None
    clients = []
    quotes = []
    contacts = []
    if store and kind in {"all", "clients"}:
        clients = _safe_search(
            "clientes",
            lambda: store.search_clientes(query, limit, executivo_id=executive_id),
        )
    if store and kind in {"all", "quotes"}:
        quotes = _safe_search(
            "cotacoes",
            lambda: store.search_cotacoes(query, limit, executivo_id=executive_id),
        )
    search_contacts = getattr(store, "search_contatos", None) if store else None
    if search_contacts and kind in {"all", "contacts"}:
        contacts = _safe_search(
            "contatos",
            lambda: search_contacts(query, limit, executivo_id=executive_id),
        )
    if not isinstance(contacts, list):
        contacts = []
    operational = {"pis": [], "campaigns": []}
    if kind in {"all", "pis", "campaigns"}:
        operational = _safe_search(
            "operacional",
            lambda: search_operational_records(query, limit=limit),
            {"pis": [], "campaigns": []},
        ) or {"pis": [], "campaigns": []}
    channels = []
    audiences = []
    if kind in {"all", "channels"}:
        channels = _safe_search(
            "canais",
            lambda: [
                {
                    "id": item.get("id"),
                    "nome": item.get("nome"),
                    "canais": item.get("canais") or "",
                    "total_audiencias": item.get("total_audiencias") or 0,
                }
                for item in (db.buscar_canais_plataformas(query, limit) or [])
            ],
        )
    if kind in {"all", "audiences"}:
        audiences = _safe_search(
            "audiencias",
            lambda: [
                {
                    "id": item.get("id"),
                    "nome": item.get("nome"),
                    "plataforma_nome": item.get("plataforma_nome") or item.get("fonte") or "",
                    "perfil": item.get("perfil_socioeconomico") or "",
                }
                for item in (db.buscar_audiencias(query, limit) or [])
            ],
        )
    return jsonify({
        "success": True,
        "data": {
            "clients": clients,
            "contacts": contacts,
            "quotes": quotes,
            "pis": operational["pis"] if kind in {"all", "pis"} else [],
            "campaigns": operational["campaigns"] if kind in {"all", "campaigns"} else [],
            "channels": channels,
            "audiences": audiences,
            "scope": "all" if global_scope else "mine",
        },
    })


@bp.get("/context/<entity_type>/<entity_id>")
@agent_internal_required_api
def context_record(entity_type, entity_id):
    try:
        data = build_context_record(
            entity_type,
            entity_id,
            get_store(),
            _client_visible,
            _quote_visible,
            PiOperacaoRepository(),
        )
    except ContextRecordError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "data": data})


@bp.get("/commercial/record/<entity_type>/<entity_id>")
@agent_internal_required_api
def commercial_record(entity_type, entity_id):
    if canonical_type(entity_type) not in {"cliente", "cotacao"}:
        return jsonify({"success": False, "error": "Tipo de registro inválido."}), 400
    return context_record(entity_type, entity_id)


@bp.post("/context/contact-changes")
@agent_internal_required_api
@agent_csrf_required
def apply_contact_change():
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict) or raw.get("confirmed") is not True:
        return jsonify({"success": False, "error": "Confirme a alteração antes de salvar."}), 400
    operation = str(raw.get("operation") or "").casefold()
    if operation not in {"create_contact", "update_contact"}:
        return jsonify({"success": False, "error": "Operação de contato inválida."}), 400
    changes = raw.get("changes")
    if not isinstance(changes, dict):
        return jsonify({"success": False, "error": "Dados do contato inválidos."}), 400
    changes = {
        key: str(value or "").strip()[:500]
        for key, value in changes.items()
        if key in CONTACT_EDITABLE_FIELDS
    }
    if not changes or not changes.get("nome"):
        return jsonify({"success": False, "error": "Informe o nome do contato."}), 400
    store = get_store()
    if operation == "create_contact":
        client_id = str(raw.get("cliente_id") or "")
        client = store.get_cliente(client_id)
        if not _client_allowed(client):
            return jsonify({"success": False, "error": "Cliente não encontrado."}), 404
        try:
            contact = store.create_contato(client_id, changes)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
    else:
        contact_id = str(raw.get("contato_id") or "")
        current = getattr(store, "get_contato", lambda _id: None)(contact_id)
        client = store.get_cliente(str((current or {}).get("cliente_id") or ""))
        if not current or not _client_allowed(client):
            return jsonify({"success": False, "error": "Contato não encontrado."}), 404
        merged = {
            key: changes.get(key, current.get(key, ""))
            for key in CONTACT_EDITABLE_FIELDS
        }
        try:
            contact, _client_id = store.update_contato(contact_id, merged)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
    if not contact:
        return jsonify({"success": False, "error": "Não foi possível salvar o contato."}), 400
    return jsonify({
        "success": True,
        "data": {
            "contact": contact,
            "context": {
                "module": "crm",
                "screen": "contato",
                "entity_type": "contato",
                "entity_id": str(contact["id"]),
                "entity_label": contact.get("nome") or "Contato",
            },
        },
    })


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


@bp.errorhandler(StoreUnavailable)
def crm_store_unavailable(exc):
    storage.rollback_failed_transaction()
    current_app.logger.warning("CRM indisponível no agente: %s", exc)
    return jsonify({
        "success": False,
        "error": "Os dados comerciais estão temporariamente indisponíveis.",
    }), 503
