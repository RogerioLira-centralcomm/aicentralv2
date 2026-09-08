"""Consultas contextuais e propostas confirmáveis do Agente CentralX."""

from ... import db
from ...crm_v3_repository import get_store
from ...pi_operacao_repository import PiNaoEncontradoError, PiOperacaoRepository
from ...pi_operacao_service import PiOperacaoService

MAX_RESULTS = 20


def _number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentage(value, total):
    value = _number(value)
    total = _number(total)
    if value is None or not total:
        return None
    return round((value / total) * 100, 2)


def _serializable(value):
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    number = _number(value)
    if value is not None and not isinstance(value, (str, bool)) and number is not None:
        return number
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


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
        "type": "cliente",
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
        "type": "contato",
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
        "type": "contato",
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
        "type": "contato",
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
        "type": "cotacao",
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
        "type": "cotacao",
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


def listar_canais_plataformas(query=None, limit=20, **_):
    rows = db.buscar_canais_plataformas(query, min(limit, MAX_RESULTS))
    items = [{
        "title": item.get("nome") or "Plataforma",
        "subtitle": " · ".join(filter(None, [
            item.get("canais"),
            f"{item.get('total_audiencias') or 0} audiência(s)",
        ])),
        "platform_id": item.get("id"),
        "channels": item.get("canais") or "",
        "audiences": item.get("total_audiencias") or 0,
    } for item in rows]
    return _ok(items, f"{len(items)} plataforma(s) e canal(is)", items)


def buscar_audiencias(query, plataforma_id=None, limit=20, **_):
    rows = db.buscar_audiencias(query, min(limit, MAX_RESULTS))
    if plataforma_id not in (None, ""):
        rows = [
            item for item in rows
            if str(item.get("plataforma_id") or "") == str(plataforma_id)
        ]
    items = [{
        "title": item.get("nome") or "Audiência",
        "subtitle": " · ".join(filter(None, [
            item.get("plataforma_nome") or item.get("fonte"),
            item.get("perfil_socioeconomico"),
        ])),
        "platform": item.get("plataforma_nome") or item.get("fonte") or "",
        "cpm_sale": _number(item.get("cpm_venda")),
        "cpm_cost": _number(item.get("cpm_custo")),
    } for item in rows[:min(limit, MAX_RESULTS)]]
    return _ok(items, f"{len(items)} audiência(s) do CADU", items)


def listar_formatos(query=None, limit=20, **_):
    rows = db.buscar_formatos_comerciais(query, min(limit, MAX_RESULTS))
    items = [{
        "title": item.get("nome") or "Formato",
        "subtitle": " · ".join(filter(None, [
            item.get("tipo"),
            f"{item.get('total_usos') or 0} uso(s)",
        ])),
        "format_type": item.get("tipo") or "",
        "usage_count": item.get("total_usos") or 0,
    } for item in rows]
    return _ok(items, f"{len(items)} formato(s) comercial(is)", items)


def _pi_item(item):
    return {
        "type": "pi",
        "id": item.get("id_pi"),
        "title": item.get("titulo_pi") or item.get("codigo_pi_cc") or f"PI {item.get('id_pi')}",
        "subtitle": " · ".join(filter(None, [item.get("cliente_nome"), item.get("sub_status_descricao")])),
        "code": item.get("codigo_pi_cc") or item.get("codigo_pi_ag") or "",
        "client": item.get("cliente_nome") or "",
        "status": item.get("sub_status_descricao") or "",
        "value": _number(item.get("vr_bruto_pi")),
        "responsible": item.get("responsavel_comercial_nome") or "",
        "responsible_photo": item.get("responsavel_comercial_foto_url") or "",
        "period": " a ".join(filter(None, [
            str(item.get("periodo_inicio") or ""),
            str(item.get("periodo_fim") or ""),
        ])),
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
    })
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir PI", "url": item["url"]}],
        _focus("pi", item["id"], item["title"], "operacao", "pi"),
    )


def listar_pis_cliente(
    cliente_id, limit=10, _viewer_user_id=None, _allow_global=False, **_
):
    store = get_store()
    client = store.get_cliente(str(cliente_id))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente não encontrado ou indisponível.")
    rows = PiOperacaoRepository().listar_pis_cliente(
        str(cliente_id), min(limit, MAX_RESULTS)
    )
    items = []
    for row in rows:
        enriched = dict(row)
        enriched.setdefault("cliente_nome", client.get("nome") or "")
        items.append(_pi_item(enriched))
    return _ok(items, f"{len(items)} PI(s) deste cliente", items)


def _campaign_item(item):
    contracted = _number(item.get("obj_contratados"))
    achieved = _number(item.get("totalizador_atingido"))
    return {
        "type": "campanha",
        "id": item.get("id_campanha"),
        "title": item.get("nome_campanha") or f"Campanha {item.get('id_campanha')}",
        "subtitle": " · ".join(filter(None, [item.get("cliente_nome"), item.get("status_descricao"), item.get("plataforma_nome")])),
        "pi_id": item.get("id_pi") or "",
        "client": item.get("cliente_nome") or "",
        "status": item.get("status_descricao") or "",
        "platform": item.get("plataforma_nome") or "",
        "responsible": item.get("responsavel_operacao_nome") or "",
        "responsible_photo": item.get("responsavel_operacao_foto_url") or "",
        "contracted": contracted,
        "achieved": achieved,
        "delivery_percent": _percentage(achieved, contracted),
        "spent": _number(item.get("totalizador_gasto")),
        "budget": _number(item.get("custo_midia_orcado")),
        "value": _number(item.get("valor_plataforma")),
        "period": " a ".join(filter(None, [
            str(item.get("periodo_inicio") or ""),
            str(item.get("periodo_fim") or ""),
        ])),
        "dashboard": item.get("link_dash") or "",
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
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir campanha", "url": item["url"]}],
        _focus("campanha", item["id"], item["title"], "operacao", "campanha"),
    )


def listar_campanhas_pi(pi_id, limit=20, **_):
    repository = PiOperacaoRepository()
    try:
        pi = repository.obter_pi(str(pi_id))
    except PiNaoEncontradoError:
        return _error("PI não encontrado ou indisponível.")
    rows = repository.listar_campanhas(str(pi_id))
    items = []
    for row in rows[:min(limit, MAX_RESULTS)]:
        enriched = dict(row)
        enriched.setdefault("cliente_nome", pi.get("cliente_nome") or "")
        items.append(_campaign_item(enriched))
    return _ok(items, f"{len(items)} campanha(s) deste PI", items)


def consultar_operacao_pi(pi_id, **_):
    try:
        state = PiOperacaoService().estado_completo(str(pi_id))
    except PiNaoEncontradoError:
        return _error("PI não encontrado ou indisponível.")
    pi = _pi_item(state.get("pi") or {})
    data = {
        "pi": pi,
        "summary": _serializable(state.get("resumo") or {}),
        "sla": _serializable(state.get("sla") or {}),
        "health": _serializable(state.get("saude") or {}),
        "timeline": _serializable(state.get("timeline") or []),
        "operational_checklist": _serializable(
            state.get("checklist_operacional") or {}
        ),
        "recommendations": _serializable(state.get("recomendacoes") or []),
    }
    return _ok(
        data,
        f"Operação do {pi['title']}",
        [pi],
        [{"label": "Abrir PI", "url": pi["url"]}],
        _focus("pi", pi["id"], pi["title"], "operacao", "pi"),
    )


def resumir_operacao(**_):
    raw = PiOperacaoRepository().resumo_operacao()
    pis_por_status = [{
        "status": item.get("status_descricao") or "Sem status",
        "count": int(item.get("total_pis") or 0),
        "gross_value": _number(item.get("valor_bruto")) or 0,
    } for item in raw.get("pis_por_status", [])]
    campanhas_por_status = [{
        "status": item.get("status_descricao") or "Sem status",
        "count": int(item.get("total_campanhas") or 0),
        "contracted": _number(item.get("objetivo_contratado")) or 0,
        "achieved": _number(item.get("objetivo_atingido")) or 0,
        "spent": _number(item.get("total_gasto")) or 0,
        "budget": _number(item.get("custo_orcado")) or 0,
        "delivery_percent": _percentage(
            item.get("objetivo_atingido"),
            item.get("objetivo_contratado"),
        ),
    } for item in raw.get("campanhas_por_status", [])]
    plataformas = [{
        "platform": item.get("plataforma") or "Sem plataforma",
        "count": int(item.get("total_campanhas") or 0),
    } for item in raw.get("campanhas_por_plataforma", [])]
    data = {
        "total_pis": sum(item["count"] for item in pis_por_status),
        "gross_value": round(sum(item["gross_value"] for item in pis_por_status), 2),
        "total_campaigns": sum(item["count"] for item in campanhas_por_status),
        "pis_by_status": pis_por_status,
        "campaigns_by_status": campanhas_por_status,
        "campaigns_by_platform": plataformas,
    }
    display = [
        {
            "title": item["status"],
            "subtitle": f'{item["count"]} PI(s)',
            "value": item["gross_value"],
        }
        for item in pis_por_status
    ] + [
        {
            "title": item["status"],
            "subtitle": f'{item["count"]} campanha(s)',
            "delivery_percent": item["delivery_percent"],
        }
        for item in campanhas_por_status
    ]
    return _ok(data, "Resumo da operação", display)


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
