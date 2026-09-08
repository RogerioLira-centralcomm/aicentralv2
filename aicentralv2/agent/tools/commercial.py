"""Consultas contextuais e propostas confirmáveis do Agente CentralX."""

from ...crm_v3_repository import get_store
from ...pi_operacao_repository import PiNaoEncontradoError, PiOperacaoRepository

MAX_RESULTS = 20


def _ok(data, title, items=None, links=None, focus=None, confirmation=None):
    items = items if items is not None else (data if isinstance(data, list) else [data])
    result = {
        "success": True,
        "data": data,
        "display": {
            "title": title,
            "type": "result_list",
            "items": items[:MAX_RESULTS],
            "links": links or [],
        },
        "links": links or [],
        "metadata": {"count": len(items)},
        "error": None,
    }
    if focus:
        result["context_focus"] = focus
    if confirmation:
        result["confirmation"] = confirmation
    return result


def _error(message, code="not_found"):
    return {
        "success": False, "data": None, "display": None, "links": [],
        "metadata": {}, "error": {"code": code, "message": message},
    }


def _client_item(item):
    return {
        "id": item.get("id"),
        "title": item.get("nome") or "Cliente sem nome",
        "subtitle": " · ".join(filter(None, [
            item.get("tipo_label"), " / ".join(filter(None, [item.get("cidade"), item.get("uf")])),
        ])),
        "responsible": item.get("responsavel") or "Não informado",
        "url": f"/crm-v3/#cliente={item.get('id')}",
    }


def _focus(entity_type, entity_id, label, module, screen):
    return {
        "module": module,
        "screen": screen,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "entity_label": label,
    }


def _normalized(value):
    return " ".join(str(value or "").casefold().split())


def _unique_exact_focus(query, items, entity_type, module, screen):
    if len(items) != 1:
        return None
    item = items[0]
    candidates = [item.get("title"), item.get("code"), item.get("id"), item.get("email")]
    if _normalized(query) not in {_normalized(value) for value in candidates if value}:
        return None
    return _focus(entity_type, item["id"], item.get("title") or entity_type.title(), module, screen)


def _client_allowed(client, viewer_user_id=None, allow_global=False):
    if allow_global or viewer_user_id is None:
        return True
    return str(client.get("executivo_id") or "") == str(viewer_user_id)


def _quote_allowed(quote, viewer_user_id=None, allow_global=False):
    if allow_global or viewer_user_id is None:
        return True
    return str(quote.get("executivo_id") or "") == str(viewer_user_id)


def buscar_cliente(
    query, limit=10, _viewer_user_id=None, _allow_global=False, **_
):
    clients = get_store().search_clientes(
        query,
        min(limit, MAX_RESULTS),
        executivo_id=None if _allow_global else _viewer_user_id,
    )
    items = [_client_item(item) for item in clients]
    return _ok(
        items,
        f"{len(items)} cliente(s) encontrado(s)",
        items,
        focus=_unique_exact_focus(query, items, "cliente", "crm", "cliente_detalhe"),
    )


def consultar_cliente(
    cliente_id, _viewer_user_id=None, _allow_global=False, **_
):
    client = get_store().get_cliente(str(cliente_id))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente não encontrado ou indisponível.")
    item = _client_item(client)
    item.update({
        "classification": client.get("classificacao"),
        "agency": client.get("agencia_nome") or None,
    })
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir cliente", "url": item["url"]}],
        _focus("cliente", item["id"], item["title"], "crm", "cliente_detalhe"),
    )


def listar_contatos(
    cliente_id, limit=20, _viewer_user_id=None, _allow_global=False, **_
):
    store = get_store()
    client = store.get_cliente(str(cliente_id))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente não encontrado ou indisponível.")
    contacts = store.list_contatos(str(cliente_id))
    if contacts is None:
        return _error("Cliente não encontrado ou indisponível.")
    items = [{
        "id": item.get("id"),
        "title": item.get("nome") or "Contato sem nome",
        "subtitle": item.get("cargo") or item.get("email") or "",
        "email": item.get("email") or "",
        "phone": item.get("telefone") or "",
        "url": f"/crm-v3/#cliente={cliente_id}",
    } for item in contacts[:min(limit, MAX_RESULTS)]]
    return _ok(items, f"{len(items)} contato(s)", items)


def buscar_contato(
    query, limit=10, _viewer_user_id=None, _allow_global=False, **_
):
    store = get_store()
    search = getattr(store, "search_contatos", None)
    contacts = search(
        query,
        min(limit, MAX_RESULTS),
        executivo_id=None if _allow_global else _viewer_user_id,
    ) if search else []
    items = [{
        "id": item.get("id"),
        "title": item.get("nome") or "Contato sem nome",
        "subtitle": " · ".join(filter(None, [item.get("cargo"), item.get("setor"), item.get("cliente_nome")])),
        "email": item.get("email") or "",
        "phone": item.get("telefone") or "",
        "url": f"/crm-v3/#cliente={item.get('cliente_id')}",
    } for item in contacts]
    return _ok(
        items,
        f"{len(items)} contato(s) encontrado(s)",
        items,
        focus=_unique_exact_focus(query, items, "contato", "crm", "contato"),
    )


def consultar_contato(
    contato_id, _viewer_user_id=None, _allow_global=False, **_
):
    store = get_store()
    contact = getattr(store, "get_contato", lambda _id: None)(str(contato_id))
    client = store.get_cliente(str((contact or {}).get("cliente_id") or "")) if contact else None
    if not contact or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Contato não encontrado ou indisponível.")
    item = {
        "id": contact.get("id"),
        "title": contact.get("nome") or "Contato",
        "subtitle": " · ".join(filter(None, [contact.get("cargo"), contact.get("setor")])),
        "email": contact.get("email") or "",
        "phone": contact.get("telefone") or "",
        "secondary_phone": contact.get("telefone_secundario") or "",
        "client_id": contact.get("cliente_id") or "",
        "client": client.get("nome") or "",
        "url": f"/crm-v3/#cliente={contact.get('cliente_id')}",
    }
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir cliente", "url": item["url"]}],
        _focus("contato", item["id"], item["title"], "crm", "contato"),
    )


def listar_atividades(
    cliente_id, limit=20, status=None,
    _viewer_user_id=None, _allow_global=False, **_
):
    store = get_store()
    client = store.get_cliente(str(cliente_id))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente não encontrado ou indisponível.")
    activities = store.list_atividades(str(cliente_id))
    if activities is None:
        return _error("Cliente não encontrado ou indisponível.")
    if status:
        activities = [a for a in activities if str(a.get("status") or "").casefold() == status.casefold()]
    items = [{
        "id": item.get("id"),
        "title": item.get("titulo") or item.get("tipo") or "Atividade",
        "subtitle": " · ".join(filter(None, [item.get("data"), item.get("status")])),
        "url": f"/crm-v3/#cliente={cliente_id}",
    } for item in activities[:min(limit, MAX_RESULTS)]]
    return _ok(items, f"{len(items)} atividade(s)", items)


def listar_cotacoes(
    cliente_id, limit=20, status=None,
    _viewer_user_id=None, _allow_global=False, **_
):
    store = get_store()
    client = store.get_cliente(str(cliente_id))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente não encontrado ou indisponível.")
    quotes = store.list_cotacoes(str(cliente_id))
    if quotes is None:
        return _error("Cliente não encontrado ou indisponível.")
    if not _allow_global and _viewer_user_id is not None:
        quotes = [
            quote for quote in quotes
            if _quote_allowed(quote, _viewer_user_id, False)
        ]
    if status:
        wanted = status.casefold()
        quotes = [q for q in quotes if wanted in str(q.get("status_label") or q.get("status") or "").casefold()]
    items = [{
        "id": item.get("id"),
        "title": item.get("titulo") or item.get("numero_cotacao") or "Cotação",
        "subtitle": " · ".join(filter(None, [item.get("status_label"), item.get("valor")])),
        "responsible": item.get("vendedor_nome") or "Não informado",
        "url": f"/cotacoes/{item.get('id')}/detalhes",
    } for item in quotes[:min(limit, MAX_RESULTS)]]
    return _ok(items, f"{len(items)} cotação(ões)", items)


def consultar_cotacao(
    cotacao_id, _viewer_user_id=None, _allow_global=False, **_
):
    quote = get_store().get_cotacao(str(cotacao_id))
    if not quote or not _quote_allowed(quote, _viewer_user_id, _allow_global):
        return _error("Cotação não encontrada ou indisponível.")
    item = {
        "id": quote.get("id"),
        "title": quote.get("titulo") or quote.get("numero_cotacao") or "Cotação",
        "subtitle": " · ".join(filter(None, [quote.get("status_label"), quote.get("valor")])),
        "responsible": quote.get("vendedor_nome") or "Não informado",
        "client_id": quote.get("cliente_id") or "",
        "client": quote.get("cliente_nome") or "",
        "period": " a ".join(filter(None, [quote.get("periodo_inicio"), quote.get("periodo_fim")])),
        "url": f"/cotacoes/{quote.get('id')}/detalhes",
    }
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir cotação", "url": item["url"]}],
        _focus("cotacao", item["id"], item["title"], "comercial", "cotacao"),
    )


def _pi_item(item):
    return {
        "id": item.get("id_pi"),
        "title": item.get("titulo_pi") or item.get("codigo_pi_cc") or f"PI {item.get('id_pi')}",
        "subtitle": " · ".join(filter(None, [item.get("cliente_nome"), item.get("sub_status_descricao")])),
        "code": item.get("codigo_pi_cc") or item.get("codigo_pi_ag") or "",
        "url": f"/cadu_pi/editar/{item.get('id_pi')}",
    }


def buscar_pi(query, limit=10, **_):
    items = [_pi_item(item) for item in PiOperacaoRepository().buscar_pis(query, min(limit, MAX_RESULTS))]
    return _ok(
        items,
        f"{len(items)} PI(s) encontrado(s)",
        items,
        focus=_unique_exact_focus(query, items, "pi", "operacao", "pi"),
    )


def consultar_pi(pi_id, **_):
    try:
        raw = PiOperacaoRepository().obter_pi(str(pi_id))
    except PiNaoEncontradoError:
        return _error("PI não encontrado ou indisponível.")
    item = _pi_item(raw)
    item.update({
        "client_id": raw.get("id_cliente") or "",
        "value": raw.get("vr_bruto_pi"),
        "period": " a ".join(filter(None, [str(raw.get("periodo_inicio") or ""), str(raw.get("periodo_fim") or "")])),
    })
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir PI", "url": item["url"]}],
        _focus("pi", item["id"], item["title"], "operacao", "pi"),
    )


def _campaign_item(item):
    return {
        "id": item.get("id_campanha"),
        "title": item.get("nome_campanha") or f"Campanha {item.get('id_campanha')}",
        "subtitle": " · ".join(filter(None, [item.get("cliente_nome"), item.get("status_descricao"), item.get("plataforma_nome")])),
        "url": f"/campanhas-pi/{item.get('id_campanha')}",
    }


def buscar_campanha(query, limit=10, **_):
    items = [
        _campaign_item(item)
        for item in PiOperacaoRepository().buscar_campanhas(query, min(limit, MAX_RESULTS))
    ]
    return _ok(
        items,
        f"{len(items)} campanha(s) encontrada(s)",
        items,
        focus=_unique_exact_focus(query, items, "campanha", "operacao", "campanha"),
    )


def consultar_campanha(campanha_id, **_):
    try:
        raw = PiOperacaoRepository().obter_campanha(str(campanha_id))
    except LookupError:
        return _error("Campanha não encontrada ou indisponível.")
    item = _campaign_item(raw)
    item.update({
        "pi_id": raw.get("id_pi") or "",
        "platform": raw.get("plataforma_nome") or "",
        "dashboard": raw.get("link_dash") or "",
    })
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir campanha", "url": item["url"]}],
        _focus("campanha", item["id"], item["title"], "operacao", "campanha"),
    )


def preparar_alteracao_contato(
    operation, nome, cliente_id=None, contato_id=None, email=None,
    telefone=None, telefone_secundario=None,
    _viewer_user_id=None, _allow_global=False, **_
):
    operation = str(operation or "").casefold()
    if operation not in {"create_contact", "update_contact"}:
        return _error("Operação de contato inválida.", "invalid_contact_change")
    store = get_store()
    before = {}
    if operation == "update_contact":
        before = getattr(store, "get_contato", lambda _id: None)(str(contato_id or "")) or {}
        cliente_id = before.get("cliente_id")
    client = store.get_cliente(str(cliente_id or ""))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente ou contato não encontrado.", "not_found")
    changes = {
        key: value for key, value in {
            "nome": nome,
            "email": email,
            "telefone": telefone,
            "telefone_secundario": telefone_secundario,
        }.items() if value is not None
    }
    if operation == "create_contact" and not changes.get("email"):
        return _error("Informe o e-mail para criar um novo contato.", "email_required")
    confirmation = {
        "operation": operation,
        "cliente_id": str(cliente_id),
        "contato_id": str(contato_id or ""),
        "client_label": client.get("nome") or "Cliente",
        "before": {key: before.get(key) or "" for key in changes},
        "changes": changes,
        "title": "Criar contato" if operation == "create_contact" else "Atualizar contato",
    }
    preview = {
        "id": str(contato_id or ""),
        "title": changes.get("nome") or before.get("nome") or "Contato",
        "subtitle": client.get("nome") or "",
        "email": changes.get("email") or before.get("email") or "",
        "phone": changes.get("telefone") or before.get("telefone") or "",
    }
    return _ok(preview, confirmation["title"], [preview], confirmation=confirmation)
