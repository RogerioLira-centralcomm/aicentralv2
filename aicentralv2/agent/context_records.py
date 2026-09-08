"""Contratos de leitura para a parede contextual do Agente CentralX."""

from decimal import Decimal

from ..pi_operacao_repository import PiNaoEncontradoError, PiOperacaoRepository


class ContextRecordError(LookupError):
    pass


ALIASES = {
    "client": "cliente",
    "quote": "cotacao",
    "contact": "contato",
    "campaign": "campanha",
}


def canonical_type(entity_type):
    value = str(entity_type or "").strip().casefold()
    return ALIASES.get(value, value)


def _value(value):
    if value is None or value == "":
        return ""
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _fact(label, value, copy=False):
    value = _value(value)
    if value in (None, ""):
        return None
    return {"label": label, "value": value, "copy": bool(copy)}


def _facts(*items):
    return [item for item in items if item]


def _entity(entity_type, entity_id, title, subtitle="", url="", **extra):
    item = {
        "type": entity_type,
        "id": str(entity_id),
        "title": title or entity_type.title(),
        "subtitle": subtitle or "",
        "url": url or "",
    }
    item.update({key: _value(value) for key, value in extra.items() if value not in (None, "")})
    return item


def _base(entity_type, record, context, title, subtitle, url, facts, relations=None, actions=None):
    return {
        "type": entity_type,
        "record": record,
        "context": context,
        "identity": {
            "title": title,
            "subtitle": subtitle or "",
            "type_label": {
                "cliente": "Cliente",
                "contato": "Contato",
                "cotacao": "Cotação",
                "pi": "PI",
                "campanha": "Campanha",
            }.get(entity_type, "Registro"),
        },
        "facts": facts,
        "relations": relations or [],
        "actions": actions or [],
        "url": url,
    }


def _client_context(store, pi_repo, client, client_allowed):
    if not client or not client_allowed(client):
        raise ContextRecordError("Cliente não encontrado.")
    client_id = str(client["id"])
    contacts = store.list_contatos(client_id) or []
    quotes = [item for item in (store.list_cotacoes(client_id, include_vinculados=False) or [])]
    try:
        pis = pi_repo.listar_pis_cliente(client_id, 8)
    except Exception:
        pis = []
    campaigns = []
    for pi in pis[:5]:
        try:
            campaigns.extend(pi_repo.listar_campanhas(pi["id_pi"])[:4])
        except Exception:
            continue
    stage = "Sem proposta"
    if quotes:
        stage = "Com cotação"
    if pis:
        stage = "Com PI"
    if campaigns:
        stage = "Em operação"
    url = f"/crm-v3/#cliente={client_id}"
    context = {
        "module": "crm",
        "screen": "cliente_detalhe",
        "entity_type": "cliente",
        "entity_id": client_id,
        "entity_label": client.get("nome") or "Cliente",
    }
    payload = _base(
        "cliente",
        client,
        context,
        client.get("nome") or "Cliente",
        " · ".join(filter(None, [client.get("tipo_label"), client.get("cidade"), client.get("uf")])),
        url,
        _facts(
            _fact("Etapa", stage),
            _fact("Responsável", client.get("responsavel")),
            _fact("Classificação", client.get("classificacao")),
            _fact("CNPJ", client.get("cnpj"), True),
            _fact("Site", client.get("site_url"), True),
        ),
        [
            {
                "key": "contacts",
                "title": "Contatos",
                "count": len(contacts),
                "items": [
                    _entity(
                        "contato", item["id"], item.get("nome") or "Contato",
                        " · ".join(filter(None, [item.get("cargo"), item.get("setor")])),
                        url, email=item.get("email"), phone=item.get("telefone"),
                    )
                    for item in contacts[:8]
                ],
            },
            {
                "key": "quotes",
                "title": "Cotações",
                "count": len(quotes),
                "items": [
                    _entity(
                        "cotacao", item["id"],
                        item.get("titulo") or item.get("numero_cotacao") or "Cotação",
                        item.get("status_label") or item.get("status") or "",
                        f"/cotacoes/{item['id']}/detalhes",
                        value=item.get("valor"),
                    )
                    for item in quotes[:8]
                ],
            },
            {
                "key": "pis",
                "title": "PIs",
                "count": len(pis),
                "items": [
                    _entity(
                        "pi", item["id_pi"],
                        item.get("titulo_pi") or item.get("codigo_pi_cc") or f"PI {item['id_pi']}",
                        item.get("sub_status_descricao") or "",
                        f"/cadu_pi/editar/{item['id_pi']}",
                        code=item.get("codigo_pi_cc") or item.get("codigo_pi_ag"),
                    )
                    for item in pis
                ],
            },
            {
                "key": "campaigns",
                "title": "Campanhas",
                "count": len(campaigns),
                "items": [
                    _entity(
                        "campanha", item["id_campanha"],
                        item.get("nome_campanha") or f"Campanha {item['id_campanha']}",
                        item.get("status_descricao") or item.get("plataforma_nome") or "",
                        f"/campanhas-pi/{item['id_campanha']}",
                    )
                    for item in campaigns[:8]
                ],
            },
        ],
        [
            {"kind": "open", "label": "Abrir no CentralX", "url": url},
            {"kind": "copy", "label": "Copiar link", "value": url},
            {
                "kind": "prompt",
                "label": "Resumir pendências",
                "prompt": f"Resuma as pendências e próximos passos do cliente {client.get('nome') or client_id}.",
            },
        ],
    )
    payload.update({
        "contacts": contacts[:8],
        "quotes": quotes[:8],
        "pis": pis[:8],
        "campaigns": campaigns[:8],
        "can_edit": False,
    })
    return payload


def _contact_context(store, contact, client_allowed):
    if not contact:
        raise ContextRecordError("Contato não encontrado.")
    client_id = str(contact.get("cliente_id") or "")
    client = store.get_cliente(client_id) if client_id else None
    if not client or not client_allowed(client):
        raise ContextRecordError("Contato não encontrado.")
    contact_id = str(contact["id"])
    url = f"/crm-v3/#cliente={client_id}"
    context = {
        "module": "crm",
        "screen": "contato",
        "entity_type": "contato",
        "entity_id": contact_id,
        "entity_label": contact.get("nome") or "Contato",
    }
    return _base(
        "contato",
        contact,
        context,
        contact.get("nome") or "Contato",
        " · ".join(filter(None, [contact.get("cargo"), contact.get("setor")])),
        url,
        _facts(
            _fact("Cliente", client.get("nome")),
            _fact("Cargo", contact.get("cargo")),
            _fact("Setor", contact.get("setor")),
            _fact("Telefone", contact.get("telefone"), True),
            _fact("Telefone secundário", contact.get("telefone_secundario"), True),
            _fact("E-mail", contact.get("email"), True),
        ),
        [{
            "key": "client",
            "title": "Cliente",
            "count": 1,
            "items": [_entity("cliente", client_id, client.get("nome") or "Cliente", "", url)],
        }],
        [
            {"kind": "open", "label": "Abrir cliente", "url": url},
            {"kind": "copy", "label": "Copiar link", "value": url},
            *(
                [{"kind": "copy", "label": "Copiar telefone", "value": contact["telefone"]}]
                if contact.get("telefone") else []
            ),
            *(
                [{"kind": "copy", "label": "Copiar e-mail", "value": contact["email"]}]
                if contact.get("email") else []
            ),
        ],
    )


def _quote_context(store, pi_repo, quote, quote_allowed):
    if not quote or not quote_allowed(quote):
        raise ContextRecordError("Cotação não encontrada.")
    quote_id = str(quote["id"])
    client_id = str(quote.get("cliente_id") or "")
    client = store.get_cliente(client_id) if client_id else None
    pis = []
    if client_id:
        try:
            pis = [
                item for item in pi_repo.listar_pis_cliente(client_id, 20)
                if str(item.get("cotacao_id") or "") == quote_id
            ]
        except Exception:
            pis = []
    url = f"/cotacoes/{quote_id}/detalhes"
    title = quote.get("titulo") or quote.get("numero_cotacao") or "Cotação"
    context = {
        "module": "comercial",
        "screen": "cotacao",
        "entity_type": "cotacao",
        "entity_id": quote_id,
        "entity_label": title,
    }
    relations = []
    if client:
        relations.append({
            "key": "client", "title": "Cliente", "count": 1,
            "items": [_entity("cliente", client_id, client.get("nome") or "Cliente", "", f"/crm-v3/#cliente={client_id}")],
        })
    if pis:
        relations.append({
            "key": "pis", "title": "PIs", "count": len(pis),
            "items": [
                _entity("pi", item["id_pi"], item.get("titulo_pi") or item.get("codigo_pi_cc") or f"PI {item['id_pi']}",
                        item.get("sub_status_descricao") or "", f"/cadu_pi/editar/{item['id_pi']}")
                for item in pis
            ],
        })
    payload = _base(
        "cotacao", quote, context, title, quote.get("numero_cotacao") or "", url,
        _facts(
            _fact("Status", quote.get("status_label") or quote.get("status")),
            _fact("Valor", quote.get("valor")),
            _fact("Responsável", quote.get("vendedor_nome")),
            _fact("Período", " a ".join(filter(None, [str(quote.get("periodo_inicio") or ""), str(quote.get("periodo_fim") or "")]))),
            _fact("Objetivo", quote.get("objetivo")),
        ),
        relations,
        [
            {"kind": "open", "label": "Abrir cotação", "url": url},
            {"kind": "copy", "label": "Copiar link", "value": url},
            {"kind": "prompt", "label": "Preparar follow-up", "prompt": f"Prepare um follow-up para a cotação {title}."},
        ],
    )
    payload.update({"client": client, "pis": pis, "can_edit": False})
    return payload


def _pi_context(store, pi_repo, pi):
    pi_id = str(pi["id_pi"])
    client_id = str(pi.get("id_cliente") or "")
    client = store.get_cliente(client_id) if client_id else None
    campaigns = pi_repo.listar_campanhas(pi_id)
    url = f"/cadu_pi/editar/{pi_id}"
    title = pi.get("titulo_pi") or pi.get("codigo_pi_cc") or f"PI {pi_id}"
    context = {
        "module": "operacao",
        "screen": "pi",
        "entity_type": "pi",
        "entity_id": pi_id,
        "entity_label": title,
    }
    relations = []
    if client:
        relations.append({
            "key": "client", "title": "Cliente", "count": 1,
            "items": [_entity("cliente", client_id, client.get("nome") or "Cliente", "", f"/crm-v3/#cliente={client_id}")],
        })
    relations.append({
        "key": "campaigns", "title": "Campanhas", "count": len(campaigns),
        "items": [
            _entity("campanha", item["id_campanha"], item.get("nome_campanha") or f"Campanha {item['id_campanha']}",
                    item.get("status_descricao") or item.get("plataforma_nome") or "",
                    f"/campanhas-pi/{item['id_campanha']}")
            for item in campaigns[:10]
        ],
    })
    return _base(
        "pi", pi, context, title, pi.get("codigo_pi_cc") or pi.get("codigo_pi_ag") or "", url,
        _facts(
            _fact("Código CentralComm", pi.get("codigo_pi_cc"), True),
            _fact("Código agência", pi.get("codigo_pi_ag"), True),
            _fact("Status", pi.get("sub_status_descricao")),
            _fact("Valor bruto", pi.get("vr_bruto_pi")),
            _fact("Responsável", pi.get("responsavel_comercial_nome")),
            _fact("Período", " a ".join(filter(None, [str(pi.get("periodo_inicio") or ""), str(pi.get("periodo_fim") or "")]))),
        ),
        relations,
        [
            {"kind": "open", "label": "Abrir PI", "url": url},
            {"kind": "copy", "label": "Copiar link", "value": url},
            {"kind": "prompt", "label": "Resumir operação", "prompt": f"Resuma a situação operacional do PI {title}."},
        ],
    )


def _campaign_context(store, pi_repo, campaign):
    campaign_id = str(campaign["id_campanha"])
    pi_id = str(campaign.get("id_pi") or "")
    pi = pi_repo.obter_pi(pi_id) if pi_id else None
    client_id = str(campaign.get("id_cliente") or (pi or {}).get("id_cliente") or "")
    client = store.get_cliente(client_id) if client_id else None
    url = f"/campanhas-pi/{campaign_id}"
    title = campaign.get("nome_campanha") or f"Campanha {campaign_id}"
    context = {
        "module": "operacao",
        "screen": "campanha",
        "entity_type": "campanha",
        "entity_id": campaign_id,
        "entity_label": title,
    }
    relations = []
    if pi:
        relations.append({
            "key": "pi", "title": "PI", "count": 1,
            "items": [_entity("pi", pi_id, pi.get("titulo_pi") or pi.get("codigo_pi_cc") or f"PI {pi_id}",
                              pi.get("sub_status_descricao") or "", f"/cadu_pi/editar/{pi_id}")],
        })
    if client:
        relations.append({
            "key": "client", "title": "Cliente", "count": 1,
            "items": [_entity("cliente", client_id, client.get("nome") or "Cliente", "", f"/crm-v3/#cliente={client_id}")],
        })
    actions = [
        {"kind": "open", "label": "Abrir campanha", "url": url},
        {"kind": "copy", "label": "Copiar link", "value": url},
    ]
    if campaign.get("link_dash"):
        actions.append({"kind": "open", "label": "Abrir dashboard", "url": campaign["link_dash"], "external": True})
        actions.append({"kind": "copy", "label": "Copiar dashboard", "value": campaign["link_dash"]})
    return _base(
        "campanha", campaign, context, title, campaign.get("plataforma_nome") or "", url,
        _facts(
            _fact("Status", campaign.get("status_descricao")),
            _fact("Plataforma", campaign.get("plataforma_nome")),
            _fact("Responsável", campaign.get("responsavel_operacao_nome")),
            _fact("Valor", campaign.get("valor_plataforma")),
            _fact("Custo orçado", campaign.get("custo_midia_orcado")),
            _fact("Período", " a ".join(filter(None, [str(campaign.get("periodo_inicio") or ""), str(campaign.get("periodo_fim") or "")]))),
        ),
        relations,
        actions,
    )


def build_context_record(
    entity_type, entity_id, store, client_allowed, quote_allowed, pi_repo=None
):
    entity_type = canonical_type(entity_type)
    pi_repo = pi_repo or PiOperacaoRepository()
    try:
        if entity_type == "cliente":
            return _client_context(store, pi_repo, store.get_cliente(str(entity_id)), client_allowed)
        if entity_type == "contato":
            return _contact_context(store, store.get_contato(str(entity_id)), client_allowed)
        if entity_type == "cotacao":
            return _quote_context(store, pi_repo, store.get_cotacao(str(entity_id)), quote_allowed)
        if entity_type == "pi":
            return _pi_context(store, pi_repo, pi_repo.obter_pi(str(entity_id)))
        if entity_type == "campanha":
            return _campaign_context(store, pi_repo, pi_repo.obter_campanha(str(entity_id)))
    except (PiNaoEncontradoError, LookupError) as exc:
        raise ContextRecordError(str(exc)) from exc
    raise ValueError("Tipo de contexto inválido.")


def search_operational_records(query, limit=8, pi_repo=None):
    pi_repo = pi_repo or PiOperacaoRepository()
    pis = pi_repo.buscar_pis(query, limit)
    campaigns = pi_repo.buscar_campanhas(query, limit)
    return {
        "pis": [
            _entity(
                "pi", item["id_pi"],
                item.get("titulo_pi") or item.get("codigo_pi_cc") or f"PI {item['id_pi']}",
                " · ".join(filter(None, [item.get("cliente_nome"), item.get("sub_status_descricao")])),
                f"/cadu_pi/editar/{item['id_pi']}",
            )
            for item in pis
        ],
        "campaigns": [
            _entity(
                "campanha", item["id_campanha"],
                item.get("nome_campanha") or f"Campanha {item['id_campanha']}",
                " · ".join(filter(None, [item.get("cliente_nome"), item.get("status_descricao")])),
                f"/campanhas-pi/{item['id_campanha']}",
            )
            for item in campaigns
        ],
    }
