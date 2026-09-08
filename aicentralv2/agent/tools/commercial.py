"""Seis consultas comerciais read-only com saída mínima e estruturada."""

from ...crm_v3_repository import get_store

MAX_RESULTS = 20


def _ok(data, title, items=None, links=None):
    items = items if items is not None else (data if isinstance(data, list) else [data])
    return {
        "success": True,
        "data": data,
        "display": {"title": title, "type": "result_list", "items": items[:MAX_RESULTS]},
        "links": links or [],
        "metadata": {"count": len(items)},
        "error": None,
    }


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


def buscar_cliente(query, limit=10, **_):
    clients = get_store().search_clientes(query, min(limit, MAX_RESULTS))
    items = [_client_item(item) for item in clients]
    return _ok(items, f"{len(items)} cliente(s) encontrado(s)", items)


def consultar_cliente(cliente_id, **_):
    client = get_store().get_cliente(str(cliente_id))
    if not client:
        return _error("Cliente não encontrado ou indisponível.")
    item = _client_item(client)
    item.update({
        "classification": client.get("classificacao"),
        "agency": client.get("agencia_nome") or None,
    })
    return _ok(item, item["title"], [item], [{"label": "Abrir cliente", "url": item["url"]}])


def listar_contatos(cliente_id, limit=20, **_):
    contacts = get_store().list_contatos(str(cliente_id))
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


def listar_atividades(cliente_id, limit=20, status=None, **_):
    activities = get_store().list_atividades(str(cliente_id))
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


def listar_cotacoes(cliente_id, limit=20, status=None, **_):
    quotes = get_store().list_cotacoes(str(cliente_id))
    if quotes is None:
        return _error("Cliente não encontrado ou indisponível.")
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


def consultar_cotacao(cotacao_id, **_):
    quote = get_store().get_cotacao(str(cotacao_id))
    if not quote:
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
    return _ok(item, item["title"], [item], [{"label": "Abrir cotação", "url": item["url"]}])
