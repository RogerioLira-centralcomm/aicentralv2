"""Contratos de leitura para a parede contextual do Agente CentralX."""

from decimal import Decimal
from urllib.parse import urlsplit

from ..pi_operacao_repository import PiNaoEncontradoError, PiOperacaoRepository
from .presenters import (
    drive_folders,
    format_brl,
    format_date_br,
    format_period_br,
    load_quote_details,
    quote_kind_label,
)


class ContextRecordError(LookupError):
    pass


ALIASES = {
    "client": "cliente",
    "agency": "cliente",
    "agencia": "cliente",
    "quote": "cotacao",
    "contact": "contato",
    "campaign": "campanha",
}

CLIENT_ENTITY_TYPES = {"cliente", "client", "agencia", "agency"}
SUBTYPE_ALIASES = {
    "agency": "agencia",
    "agencia": "agencia",
    "cliente_final": "cliente_final",
    "clientefinal": "cliente_final",
}


def canonical_type(entity_type):
    value = str(entity_type or "").strip().casefold()
    return ALIASES.get(value, value)


def client_subtype(record=None, raw_type="", explicit=""):
    explicit = str(explicit or "").casefold().replace("-", "_").replace(" ", "_")
    if explicit in SUBTYPE_ALIASES:
        return SUBTYPE_ALIASES[explicit]
    raw = str(raw_type or "").casefold()
    if raw in {"agencia", "agency"}:
        return "agencia"
    if record is not None:
        return "agencia" if record.get("is_agencia") else "cliente_final"
    return ""


def type_label_for(entity_type, subtype=""):
    entity_type = canonical_type(entity_type)
    if entity_type == "cliente":
        return "Agência" if subtype == "agencia" else "Cliente final"
    return {
        "contato": "Contato",
        "cotacao": "Cotação",
        "pi": "PI",
        "campanha": "Campanha",
    }.get(entity_type, "Registro")


def normalize_agent_context(raw=None):
    raw = raw or {}
    entity_type = str(raw.get("entity_type") or "").strip()
    subtype = client_subtype(
        raw_type=entity_type,
        explicit=raw.get("entity_subtype") or raw.get("subtype") or "",
    )
    canonical = canonical_type(entity_type)
    label = str(raw.get("entity_label") or raw.get("entity_name") or "").strip()
    return {
        "module": str(raw.get("module") or "").strip(),
        "screen": str(raw.get("screen") or "").strip(),
        "entity_type": canonical,
        "entity_id": str(raw.get("entity_id") or "").strip(),
        "entity_label": label,
        "entity_subtype": subtype if canonical == "cliente" else str(raw.get("entity_subtype") or "").strip(),
    }


def safe_context_url(value, allow_external=False):
    value = str(value or "").strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    if not allow_external:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.username or parsed.password:
        return ""
    return value


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


def _period_fact(start, end):
    return _fact("Período", format_period_br(start, end))


def _money_fact(label, value):
    return _fact(label, format_brl(value))


def _secondary_actions(*actions):
    return [item for item in actions if item]


def _drive_action(folders, label="Pasta do Drive"):
    if not folders:
        return None
    return {"kind": "drive", "label": label, "folders": folders}


def _dashboard_action(url, label="Dashboard"):
    href = safe_context_url(url, allow_external=True)
    if not href:
        return None
    return {"kind": "dashboard", "label": label, "url": href}


def _facts(*items):
    return [item for item in items if item]


def _percentage(value, total):
    try:
        if value in (None, "") or total in (None, "") or float(total) == 0:
            return ""
        return f"{(float(value) / float(total)) * 100:.1f}%"
    except (TypeError, ValueError):
        return ""


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


def _base(entity_type, record, context, title, subtitle, url, facts, relations=None, actions=None, type_label=""):
    subtype = str((context or {}).get("entity_subtype") or "")
    return {
        "type": entity_type,
        "record": record,
        "context": context,
        "identity": {
            "title": title,
            "subtitle": subtitle or "",
            "photo_url": (
                record.get("foto_url")
                or record.get("responsavel_comercial_foto_url")
                or record.get("responsavel_operacao_foto_url")
                or ""
            ),
            "type_label": type_label or type_label_for(entity_type, subtype),
            "responsible": record.get("responsavel") or record.get("vendedor_nome")
            or record.get("responsavel_comercial_nome") or record.get("responsavel_operacao_nome") or "",
            "location": " · ".join(filter(None, [record.get("cidade"), record.get("uf")])),
            "entity_subtype": subtype,
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
    subtype = client_subtype(client)
    type_label = type_label_for("cliente", subtype)
    contacts = store.list_contatos(client_id) or []
    quotes = [item for item in (store.list_cotacoes(client_id, include_vinculados=False) or [])]
    activities = store.list_atividades(client_id) or []
    if not isinstance(activities, list):
        activities = []
    done_status = {"concluida", "concluída", "cancelada"}
    open_activities = [
        item for item in activities
        if str(item.get("status") or "").casefold() not in done_status
    ]
    finais = client.get("clientes_finais") or []
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
        "entity_label": client.get("nome") or type_label,
        "entity_subtype": subtype,
    }
    relations = []
    if subtype == "agencia":
        relations.append({
            "key": "clients",
            "title": "Clientes finais",
            "count": int(client.get("clientes_finais_count") or len(finais)),
            "items": [
                _entity(
                    "cliente", item["id"], item.get("nome") or "Cliente final",
                    "Cliente final", url,
                    entity_subtype="cliente_final",
                )
                for item in finais[:8]
            ],
        })
    relations.extend([
        {
            "key": "contacts",
            "title": "Contatos",
            "count": len(contacts),
            "items": [
                _entity(
                    "contato", item["id"], item.get("nome") or "Contato",
                    item.get("cargo") or "",
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
                    value=item.get("valor") if item.get("valor_total") else "",
                    updated=item.get("data") or "",
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
        {
            "key": "activities",
            "title": "Atividades abertas",
            "count": len(open_activities),
            "items": [
                _entity(
                    "atividade", item.get("id") or index,
                    item.get("titulo") or item.get("tipo") or "Atividade",
                    " · ".join(filter(None, [format_date_br(item.get("data")), item.get("status")])),
                    url,
                )
                for index, item in enumerate(open_activities[:8])
            ],
        },
    ])
    payload = _base(
        "cliente",
        client,
        context,
        client.get("nome") or type_label,
        " · ".join(filter(None, [client.get("cidade"), client.get("uf")])),
        url,
        _facts(
            _fact("Etapa", stage),
            _fact("Responsável", client.get("responsavel")),
            _fact("Classificação", client.get("classificacao")),
            _fact("CNPJ", client.get("cnpj"), True),
            _fact("Site", client.get("site_url"), True),
        ),
        relations,
        [
            {"kind": "open", "label": "Abrir registro", "url": url},
            {"kind": "copy", "label": "Copiar link", "value": url},
            {
                "kind": "prompt",
                "label": "Resumir pendências",
                "prompt": "Resuma as pendências e próximos passos deste registro.",
            },
        ],
        type_label,
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
        "entity_subtype": "",
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
            "items": [_entity(
                "cliente", client_id, client.get("nome") or "Cliente",
                type_label_for("cliente", client_subtype(client)), url,
                entity_subtype=client_subtype(client),
            )],
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
    agency_id = str(quote.get("agencia_id") or "")
    client = store.get_cliente(client_id) if client_id else None
    agency = store.get_cliente(agency_id) if agency_id and agency_id != client_id else None
    details = load_quote_details(quote)
    totals = details.get("totals") or {}
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
    code = quote.get("numero_cotacao") or ""
    status = quote.get("status_label") or quote.get("status") or ""
    kind = quote_kind_label(quote)
    context = {
        "module": "comercial",
        "screen": "cotacao",
        "entity_type": "cotacao",
        "entity_id": quote_id,
        "entity_label": title,
        "entity_subtype": "",
    }
    relations = []
    if client:
        relations.append({
            "key": "client", "title": "Cliente", "count": 1,
            "items": [_entity(
                "cliente", client_id, client.get("nome") or "Cliente",
                type_label_for("cliente", client_subtype(client)),
                f"/crm-v3/#cliente={client_id}",
                entity_subtype=client_subtype(client),
            )],
        })
    if agency:
        relations.append({
            "key": "agency", "title": "Agência", "count": 1,
            "items": [_entity(
                "cliente", agency_id, agency.get("nome") or "Agência",
                type_label_for("cliente", "agencia"),
                f"/crm-v3/#cliente={agency_id}",
                entity_subtype="agencia",
            )],
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
    primary = [
        {"kind": "open", "label": "Abrir cotação", "url": url},
        {"kind": "prompt", "label": "Preparar follow-up", "prompt": f"Prepare um follow-up para a cotação {title}."},
    ]
    secondary = _secondary_actions(
        {"kind": "copy", "label": "Copiar link", "value": url},
        {"kind": "prompt", "label": "Ver histórico", "prompt": "Mostre o histórico desta cotação."},
        {"kind": "use_context", "label": "Ver cliente", "entity_type": "cliente", "entity_id": client_id,
         "entity_label": (client or {}).get("nome") or "Cliente",
         "entity_subtype": client_subtype(client)} if client else None,
        {"kind": "use_context", "label": "Ver PI relacionado", "entity_type": "pi",
         "entity_id": str(pis[0]["id_pi"]),
         "entity_label": pis[0].get("titulo_pi") or f"PI {pis[0]['id_pi']}"} if pis else None,
    )
    payload = _base(
        "cotacao", quote, context, title, code, url,
        _facts(
            _money_fact("Valor bruto", totals.get("valor_bruto") or quote.get("valor_total")),
            _money_fact("Valor líquido", totals.get("valor_liquido")),
            _money_fact("Custo de mídia", totals.get("total_custo_midia")),
            _fact("Margem", details.get("margin")),
            _period_fact(quote.get("periodo_inicio"), quote.get("periodo_fim")),
            _fact("Objetivo", quote.get("objetivo")),
            _fact("KPI", quote.get("kpi") or quote.get("kpi_principal")),
            _fact("Meta", quote.get("meta_entrega") or quote.get("objetivo_contratado")),
        ),
        relations,
        primary,
        "Cotação",
    )
    payload["identity"]["meta"] = " · ".join(filter(None, [status, kind]))
    payload["identity"]["code"] = code
    payload["identity"]["status"] = status
    payload["identity"]["kind"] = kind
    payload.update({
        "client": client,
        "agency": agency,
        "pis": pis,
        "can_edit": False,
        "platforms": details.get("platforms") or [],
        "quote_items": details.get("items") or [],
        "price_breakdown": details.get("breakdown") or [],
        "sections": [
            {"key": "items", "title": "Itens da proposta", "count": len(details.get("items") or []), "collapsed": True},
            {"key": "pricing", "title": "Composição de preço", "count": len(details.get("breakdown") or []), "collapsed": True},
        ],
        "actions_secondary": secondary,
    })
    return payload


def _campaign_row(item):
    return _entity(
        "campanha", item["id_campanha"],
        item.get("nome_campanha") or f"Campanha {item['id_campanha']}",
        " · ".join(filter(None, [
            item.get("status_descricao"),
            format_period_br(item.get("periodo_inicio"), item.get("periodo_fim")),
        ])),
        f"/campanhas-pi/{item['id_campanha']}",
        status=item.get("status_descricao") or "",
        platform=item.get("plataforma_nome") or "",
        period=format_period_br(item.get("periodo_inicio"), item.get("periodo_fim")),
        dashboard=item.get("link_dash") or "",
    )


def _pi_context(store, pi_repo, pi):
    pi_id = str(pi["id_pi"])
    client_id = str(pi.get("id_cliente") or "")
    agency_id = str(pi.get("id_agencia") or "")
    client = store.get_cliente(client_id) if client_id else None
    agency = store.get_cliente(agency_id) if agency_id and agency_id != client_id else None
    campaigns = pi_repo.listar_campanhas(pi_id)
    folders = drive_folders(pi)
    url = f"/cadu_pi/editar/{pi_id}"
    title = pi.get("titulo_pi") or pi.get("codigo_pi_cc") or f"PI {pi_id}"
    code = pi.get("codigo_pi_cc") or pi.get("codigo_pi_ag") or f"PI {pi_id}"
    status = pi.get("sub_status_descricao") or ""
    context = {
        "module": "operacao",
        "screen": "pi",
        "entity_type": "pi",
        "entity_id": pi_id,
        "entity_label": title,
        "entity_subtype": "",
    }
    relations = []
    if client:
        relations.append({
            "key": "client", "title": "Cliente", "count": 1,
            "items": [_entity(
                "cliente", client_id, client.get("nome") or "Cliente",
                type_label_for("cliente", client_subtype(client)),
                f"/crm-v3/#cliente={client_id}",
                entity_subtype=client_subtype(client),
            )],
        })
    if agency:
        relations.append({
            "key": "agency", "title": "Agência", "count": 1,
            "items": [_entity(
                "cliente", agency_id, agency.get("nome") or "Agência",
                type_label_for("cliente", "agencia"),
                f"/crm-v3/#cliente={agency_id}",
                entity_subtype="agencia",
            )],
        })
    relations.append({
        "key": "campaigns", "title": "Campanhas", "count": len(campaigns),
        "items": [_campaign_row(item) for item in campaigns[:10]],
    })
    dashboards = [
        {"label": item.get("nome_campanha") or "Dashboard", "url": safe_context_url(item.get("link_dash"), allow_external=True)}
        for item in campaigns if safe_context_url(item.get("link_dash"), allow_external=True)
    ]
    primary = [
        {"kind": "open", "label": "Abrir PI", "url": url},
        {"kind": "prompt", "label": "Ver campanhas", "prompt": "Liste as campanhas deste PI."},
    ]
    drive = _drive_action(folders)
    if drive:
        primary.append(drive)
    if len(dashboards) == 1:
        dash = _dashboard_action(dashboards[0]["url"], "Dashboard")
        if dash:
            primary.append(dash)
    elif dashboards:
        primary.append({"kind": "dashboard", "label": "Dashboards", "items": dashboards})
    secondary = _secondary_actions(
        {"kind": "copy", "label": "Copiar link", "value": url},
        {"kind": "prompt", "label": "Ver faturamento", "prompt": "Mostre o faturamento deste PI."},
        {"kind": "prompt", "label": "Ver histórico", "prompt": "Mostre o histórico operacional deste PI."},
    )
    payload = _base(
        "pi", pi, context, title, code, url,
        _facts(
            _fact("Status", status),
            _money_fact("Valor líquido", pi.get("vr_liquido_pi") or pi.get("valor_liquido")),
            _money_fact("Valor bruto", pi.get("vr_bruto_pi")),
            _fact("Início", format_date_br(pi.get("periodo_inicio"))),
            _fact("Término previsto", format_date_br(pi.get("periodo_fim"))),
            _fact("Código CentralComm", pi.get("codigo_pi_cc"), True),
            _fact("Código agência", pi.get("codigo_pi_ag"), True),
        ),
        relations,
        primary,
        "PI",
    )
    payload["identity"]["meta"] = status
    payload["identity"]["code"] = code
    payload["identity"]["status"] = status
    payload["identity"]["role"] = pi.get("responsavel_comercial_cargo") or ""
    payload["identity"]["responsible_photo"] = pi.get("responsavel_comercial_foto_url") or ""
    payload["identity"]["photo_url"] = ""
    payload.update({
        "client": client,
        "agency": agency,
        "campaigns": [_campaign_row(item) for item in campaigns],
        "drive_folders": folders,
        "dashboards": dashboards,
        "actions_secondary": secondary,
        "sections": [
            {"key": "campaigns", "title": "Campanhas", "count": len(campaigns), "collapsed": True},
        ],
    })
    return payload


def _campaign_context(store, pi_repo, campaign):
    campaign_id = str(campaign["id_campanha"])
    pi_id = str(campaign.get("id_pi") or "")
    pi = pi_repo.obter_pi(pi_id) if pi_id else None
    client_id = str(campaign.get("id_cliente") or (pi or {}).get("id_cliente") or "")
    client = store.get_cliente(client_id) if client_id else None
    folders = drive_folders(pi or {})
    url = f"/campanhas-pi/{campaign_id}"
    title = campaign.get("nome_campanha") or f"Campanha {campaign_id}"
    status = campaign.get("status_descricao") or ""
    context = {
        "module": "operacao",
        "screen": "campanha",
        "entity_type": "campanha",
        "entity_id": campaign_id,
        "entity_label": title,
        "entity_subtype": "",
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
            "items": [_entity(
                "cliente", client_id, client.get("nome") or "Cliente",
                type_label_for("cliente", client_subtype(client)),
                f"/crm-v3/#cliente={client_id}",
                entity_subtype=client_subtype(client),
            )],
        })
    quote_id = str((pi or {}).get("cotacao_id") or "")
    if quote_id:
        relations.append({
            "key": "quote", "title": "Cotação", "count": 1,
            "items": [_entity("cotacao", quote_id, f"Cotação {quote_id}", "", f"/cotacoes/{quote_id}/detalhes")],
        })
    delivery = _percentage(campaign.get("totalizador_atingido"), campaign.get("obj_contratados"))
    primary = [
        {"kind": "open", "label": "Abrir campanha", "url": url},
        {"kind": "prompt", "label": "Ver PI", "prompt": "Abra o PI desta campanha."} if pi else None,
        {"kind": "prompt", "label": "Ver entrega", "prompt": "Mostre a entrega desta campanha."},
    ]
    drive = _drive_action(folders)
    if drive:
        primary.append(drive)
    dash = _dashboard_action(campaign.get("link_dash"))
    if dash:
        primary.append(dash)
    secondary = _secondary_actions(
        {"kind": "copy", "label": "Copiar link", "value": url},
        {"kind": "copy", "label": "Copiar dashboard", "value": dash["url"]} if dash else None,
        {"kind": "prompt", "label": "Ver faturamento", "prompt": "Mostre o faturamento desta campanha."},
    )
    payload = _base(
        "campanha", campaign, context, title, campaign.get("plataforma_nome") or "", url,
        _facts(
            _fact("Status", status),
            _period_fact(campaign.get("periodo_inicio"), campaign.get("periodo_fim")),
            _money_fact("Budget", campaign.get("custo_midia_orcado")),
            _fact("Contratado", campaign.get("obj_contratados")),
            _fact("Realizado", campaign.get("totalizador_atingido")),
            _fact("Entrega", delivery),
            _money_fact("Valor contratado", campaign.get("valor_plataforma")),
            _money_fact("Valor realizado", campaign.get("totalizador_gasto")),
            _fact("Plataforma", campaign.get("plataforma_nome")),
            _fact("PI", (pi or {}).get("codigo_pi_cc") or (pi or {}).get("id_pi")),
        ),
        relations,
        [item for item in primary if item],
        "Campanha",
    )
    payload["identity"]["meta"] = " · ".join(filter(None, [status, campaign.get("plataforma_nome")]))
    payload["identity"]["status"] = status
    payload["identity"]["role"] = campaign.get("responsavel_operacao_cargo") or ""
    payload["identity"]["responsible_photo"] = campaign.get("responsavel_operacao_foto_url") or ""
    payload["identity"]["photo_url"] = ""
    payload["drive_folders"] = folders
    payload["dashboards"] = [{"label": "Dashboard", "url": dash["url"]}] if dash else []
    payload["actions_secondary"] = secondary
    return payload


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
