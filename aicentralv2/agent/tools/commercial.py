"""Consultas contextuais e propostas confirmáveis do Agente CentralX."""

import re
import unicodedata

from ... import db
from ...crm_v3_repository import get_store
from ...pi_operacao_repository import PiNaoEncontradoError, PiOperacaoRepository
from ...pi_operacao_service import PiOperacaoService
from .. import storage
from ..context_records import client_subtype, type_label_for
from ..presenters import (
    COT_CODE_RE,
    DEFAULT_OPERATION_YEAR,
    drive_folders,
    format_brl,
    format_date_br,
    format_period_br,
    load_quote_details,
    quote_kind_label,
)

MAX_RESULTS = 20


def _resolve_year(ano):
    if ano in (None, ""):
        return DEFAULT_OPERATION_YEAR
    try:
        year = int(ano)
    except (TypeError, ValueError):
        return DEFAULT_OPERATION_YEAR
    if year < 2000 or year > 2100:
        return DEFAULT_OPERATION_YEAR
    return year


def _period_meta(year):
    return {"label": "Período", "value": str(year), "change_prompt": "Alterar período"}


def _number(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^\d,.-]", "", str(value).strip())
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
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


FINAL_QUOTE_STATUS = {
    "rejeitada", "cancelada", "perdida", "arquivada", "encerrada", "recusada",
}
OPEN_QUOTE_HINTS = ("abert", "andamento", "enviad", "aprovad")
DRAFT_QUOTE_HINTS = ("rascunho",)
DONE_ACTIVITY_STATUS = {"concluida", "concluída", "cancelada"}


def _ok(
    data, title, items=None, links=None, focus=None, confirmation=None,
    display_type="result_list", summary=None, actions=None, empty=None,
    ambiguous=False, period=None,
):
    items = items if items is not None else (data if isinstance(data, list) else [data])
    display = {
        "title": title,
        "type": display_type,
        "summary": summary or "",
        "items": items[:MAX_RESULTS],
        "links": links or [],
        "actions": actions or [],
        "ambiguous": bool(ambiguous),
    }
    if empty:
        display["empty"] = empty
        display["type"] = display.get("type") or "empty"
    if period:
        display["period"] = period
    result = {
        "success": True,
        "data": data,
        "display": display,
        "links": links or [],
        "metadata": {"count": len(items), "ambiguous": bool(ambiguous)},
        "error": None,
        "ambiguous": bool(ambiguous),
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


def _query_or_fail(fn):
    try:
        return fn(), None
    except Exception:
        storage.rollback_failed_transaction()
        return None, _error(
            "A consulta aos dados falhou. Informe que a busca não pôde ser "
            "concluída; não invente registros nem IDs.",
            "query_failed",
        )


def _client_item(item):
    subtype = client_subtype(item)
    type_label = item.get("tipo_label") or type_label_for("cliente", subtype)
    return {
        "type": "cliente",
        "id": item.get("id"),
        "title": item.get("nome") or "Cliente sem nome",
        "type_label": type_label,
        "entity_subtype": subtype,
        "subtitle": type_label,
        "location": " / ".join(filter(None, [item.get("cidade"), item.get("uf")])),
        "is_agency": bool(item.get("is_agencia")),
        "responsible": item.get("responsavel") or "Não informado",
        "url": f"/crm-v3/#cliente={item.get('id')}",
        "primary_action": "use_context",
    }


def _focus(entity_type, entity_id, label, module, screen, subtype=""):
    return {
        "module": module,
        "screen": screen,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "entity_label": label,
        "entity_subtype": subtype or client_subtype(raw_type=entity_type),
    }


def _normalized(value):
    text = " ".join(str(value or "").casefold().split())
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _unique_exact_focus(query, items, entity_type, module, screen):
    if len(items) != 1:
        return None
    item = items[0]
    candidates = [item.get("title"), item.get("code"), item.get("id"), item.get("email")]
    if _normalized(query) not in {_normalized(value) for value in candidates if value}:
        return None
    return _focus(
        entity_type, item["id"], item.get("title") or entity_type.title(),
        module, screen, item.get("entity_subtype") or "",
    )


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
    clients, failed = _query_or_fail(lambda: get_store().search_clientes(
        query,
        min(limit, MAX_RESULTS),
        executivo_id=None if _allow_global else _viewer_user_id,
    ))
    if failed:
        return failed
    items = [_client_item(item) for item in clients]
    ambiguous = len(items) > 1
    if not items:
        return _ok(
            items, "Nenhum resultado", items,
            display_type="empty",
            summary=f'Nenhum registro encontrado para “{query}”.',
            empty={
                "title": "Nenhum registro encontrado",
                "body": f'Não encontramos cliente ou agência para “{query}”.',
                "actions": [
                    {"kind": "prompt", "label": "Buscar cotação", "prompt": f"Busque a cotação {query}."},
                    {"kind": "prompt", "label": "Buscar PI", "prompt": f"Busque o PI {query}."},
                ],
            },
        )
    if ambiguous:
        summary = (
            f'Encontrei {len(items)} registros com nomes semelhantes. '
            "Qual você quer consultar?"
        )
    else:
        summary = f'Encontrei {len(items)} resultado{"s" if len(items) != 1 else ""} para “{query}”.'
    return _ok(
        items,
        f"{len(items)} resultado{'s' if len(items) != 1 else ''}",
        items,
        summary=summary,
        display_type="entity_list",
        ambiguous=ambiguous,
        actions=[{"kind": "use_context", "label": "Usar como contexto"}] if items else [],
        focus=None if ambiguous else _unique_exact_focus(
            query, items, "cliente", "crm", "cliente_detalhe"
        ),
    )


def consultar_cliente(
    cliente_id, _viewer_user_id=None, _allow_global=False, **_
):
    client = get_store().get_cliente(str(cliente_id))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente não encontrado ou indisponível.")
    item = _client_item(client)
    item.update({
        "classification": client.get("classificacao") or client.get("classificacao_cliente"),
        "abc": client.get("categoria_abc") or client.get("categoria"),
        "cnpj": client.get("cnpj") or "",
        "agency": client.get("agencia_nome") or None,
        "note": client.get("nota_executivo") or "",
        "email": client.get("email") or "",
        "phone": client.get("telefone") or "",
        "bv_percent": client.get("bv_percentual"),
        "margin": client.get("margem_cc"),
        "profile": client.get("perfil") or "",
    })
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir cliente", "url": item["url"]}],
        _focus(
            "cliente", item["id"], item["title"], "crm", "cliente_detalhe",
            item.get("entity_subtype") or "",
        ),
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
        "subtitle": item.get("cargo") or "",
        "email": item.get("email") or "",
        "phone": item.get("telefone") or "",
        "url": f"/crm-v3/#cliente={cliente_id}",
    } for item in contacts[:min(limit, MAX_RESULTS)]]
    if not items:
        return _ok(
            items, "Nenhum contato", items,
            display_type="empty",
            summary="Nenhum contato encontrado.",
            empty={
                "title": "Nenhum contato",
                "body": f"Não encontramos contatos para:\n{client.get('nome') or 'este registro'}",
                "actions": [
                    {"kind": "prompt", "label": "Ver cotações", "prompt": "Liste as cotações deste cliente."},
                ],
            },
        )
    return _ok(
        items, f"{len(items)} contato{'s' if len(items) != 1 else ''}", items,
        display_type="contact_list",
        summary=f"{len(items)} contato{'s' if len(items) != 1 else ''}.",
    )


def buscar_contato(
    query, limit=10, _viewer_user_id=None, _allow_global=False, **_
):
    def _run():
        store = get_store()
        search = getattr(store, "search_contatos", None)
        if not search:
            return []
        return search(
            query,
            min(limit, MAX_RESULTS),
            executivo_id=None if _allow_global else _viewer_user_id,
        )

    contacts, failed = _query_or_fail(_run)
    if failed:
        return failed
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


def _quote_list_item(item):
    valor_num = _number(item.get("valor_total"))
    status = item.get("status_label") or item.get("status") or ""
    kind = item.get("tipo_comercial_label") or quote_kind_label(item)
    return {
        "type": "cotacao",
        "id": item.get("id"),
        "title": item.get("titulo") or item.get("numero_cotacao") or "Cotação",
        "subtitle": " · ".join(filter(None, [status, kind])),
        "status": status,
        "kind": kind,
        "code": item.get("numero_cotacao") or "",
        "value": item.get("valor") if valor_num else "",
        "value_number": valor_num,
        "updated": item.get("data") or "",
        "period": format_period_br(item.get("periodo_inicio"), item.get("periodo_fim")),
        "responsible": item.get("vendedor_nome") or "",
        "url": f"/cotacoes/{item.get('id')}/detalhes",
        "primary_action": "use_context",
    }


def _quote_status_text(item):
    return str(item.get("status_label") or item.get("status") or "").casefold()


def _is_open_quote(item):
    status = _quote_status_text(item)
    if any(term in status for term in FINAL_QUOTE_STATUS):
        return False
    return any(hint in status for hint in OPEN_QUOTE_HINTS) or not status


def _is_draft_quote(item):
    status = _quote_status_text(item)
    return any(hint in status for hint in DRAFT_QUOTE_HINTS)


def _similar_counterpart(store, client, viewer_user_id=None, allow_global=False):
    query = str(client.get("nome") or "").strip()
    if len(query) < 3:
        return None
    try:
        others = store.search_clientes(
            query, 8, executivo_id=None if allow_global else viewer_user_id,
        ) or []
    except Exception:
        storage.rollback_failed_transaction()
        return None
    want_agency = not bool(client.get("is_agencia"))
    for item in others:
        if str(item.get("id") or "") == str(client.get("id") or ""):
            continue
        if bool(item.get("is_agencia")) == want_agency:
            return _client_item(item)
    return None


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
        wanted = status.casefold()
        if wanted in {"aberta", "aberto", "pendente", "pendentes"}:
            activities = [
                a for a in activities
                if str(a.get("status") or "").casefold() not in DONE_ACTIVITY_STATUS
            ]
        else:
            activities = [a for a in activities if str(a.get("status") or "").casefold() == wanted]
    items = [{
        "id": item.get("id"),
        "type": "atividade",
        "title": item.get("titulo") or item.get("tipo") or "Atividade",
        "subtitle": " · ".join(filter(None, [item.get("data"), item.get("status")])),
        "url": f"/crm-v3/#cliente={cliente_id}",
    } for item in activities[:min(limit, MAX_RESULTS)]]
    if not items:
        return _ok(
            items, "Nenhuma atividade", items,
            display_type="empty",
            summary="Nenhuma atividade encontrada.",
            empty={
                "title": "Nenhuma atividade aberta" if status else "Nenhuma atividade",
                "body": f"Não encontramos atividades para:\n{client.get('nome') or 'este registro'}",
                "actions": [
                    {"kind": "prompt", "label": "Ver cotações", "prompt": "Liste as cotações deste registro."},
                ],
            },
        )
    return _ok(
        items, f"{len(items)} atividade{'s' if len(items) != 1 else ''}", items,
        display_type="status_list",
        summary=f"{len(items)} atividade{'s' if len(items) != 1 else ''}.",
    )


def listar_cotacoes(
    cliente_id, limit=20, status=None,
    _viewer_user_id=None, _allow_global=False, **_
):
    store = get_store()
    client = store.get_cliente(str(cliente_id))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente não encontrado ou indisponível.")
    quotes = store.list_cotacoes(str(cliente_id), include_vinculados=False)
    if quotes is None:
        return _error("Cliente não encontrado ou indisponível.")
    if not _allow_global and _viewer_user_id is not None:
        quotes = [
            quote for quote in quotes
            if _quote_allowed(quote, _viewer_user_id, False)
        ]
    all_quotes = list(quotes)
    wanted = str(status or "").casefold()
    open_filter = wanted and any(hint in wanted for hint in ("abert", "andamento"))
    if status:
        if open_filter:
            quotes = [q for q in quotes if _is_open_quote(q)]
        else:
            quotes = [q for q in quotes if wanted in _quote_status_text(q)]
    items = [_quote_list_item(item) for item in quotes[:min(limit, MAX_RESULTS)]]
    type_label = type_label_for("cliente", client_subtype(client))
    name = client.get("nome") or type_label
    if not items:
        drafts = [q for q in all_quotes if _is_draft_quote(q)]
        counterpart = _similar_counterpart(store, client, _viewer_user_id, _allow_global)
        actions = [{"kind": "prompt", "label": "Ver todas as cotações", "prompt": "Liste todas as cotações deste registro."}]
        if drafts:
            actions.insert(0, {
                "kind": "prompt",
                "label": "Ver rascunhos",
                "prompt": "Liste as cotações em rascunho deste registro.",
            })
        related = []
        if counterpart:
            related.append(counterpart)
            actions.append({
                "kind": "use_context",
                "label": f"Consultar {counterpart.get('type_label')}",
                "entity_type": "cliente",
                "entity_id": counterpart.get("id"),
                "entity_label": counterpart.get("title"),
                "entity_subtype": counterpart.get("entity_subtype"),
            })
        empty = {
            "title": "Nenhuma cotação aberta" if open_filter else "Nenhuma cotação encontrada",
            "body": f"Não encontramos cotações{' abertas' if open_filter else ''} para:\n{name}",
            "record_name": name,
            "record_type": type_label,
            "actions": actions,
            "related_candidates": related,
        }
        if counterpart:
            empty["hint"] = (
                f"Nenhuma cotação encontrada para esta {type_label.lower()}. "
                f"Existe um registro com nome semelhante: {counterpart.get('title')}."
            )
        summary = empty["title"]
        if drafts:
            summary = f"{empty['title']}. Este registro possui {len(drafts)} cotação(ões) em rascunho."
        return _ok(
            items, empty["title"], items,
            display_type="empty",
            summary=summary,
            empty=empty,
            actions=actions,
        )
    return _ok(
        items,
        f"{len(items)} cotação{'ões' if len(items) != 1 else ''}",
        items,
        display_type="quote_list",
        summary=f"{len(items)} cotação{'ões' if len(items) != 1 else ''} encontrada{'s' if len(items) != 1 else ''}.",
    )


def buscar_cotacao(
    query, limit=10, _viewer_user_id=None, _allow_global=False, **_
):
    term = str(query or "").strip()
    code_match = COT_CODE_RE.search(term)
    if code_match:
        term = code_match.group(0).upper()
    quotes, failed = _query_or_fail(lambda: get_store().search_cotacoes(
        term,
        min(limit, MAX_RESULTS),
        executivo_id=None if _allow_global else _viewer_user_id,
    ))
    if failed:
        return failed
    if code_match:
        exact = [
            item for item in quotes
            if str(item.get("numero_cotacao") or "").upper() == term
        ]
        if exact:
            quotes = exact
    items = [_quote_list_item(item) for item in quotes]
    ambiguous = len(items) > 1
    return _ok(
        items,
        f"{len(items)} cotação{'ões' if len(items) != 1 else ''} encontrada{'s' if len(items) != 1 else ''}",
        items,
        display_type="quote_list",
        summary=(
            f'Encontrei {len(items)} cotações. Qual você quer consultar?'
            if ambiguous else ("Encontrei a cotação." if items else f'Nenhuma cotação encontrada para “{query}”.')
        ) if items else f'Nenhuma cotação encontrada para “{query}”.',
        ambiguous=ambiguous,
        focus=None if ambiguous else _unique_exact_focus(query, items, "cotacao", "comercial", "cotacao"),
    )


def consultar_cotacao(
    cotacao_id, _viewer_user_id=None, _allow_global=False, **_
):
    quote = get_store().get_cotacao(str(cotacao_id))
    if not quote or not _quote_allowed(quote, _viewer_user_id, _allow_global):
        return _error("Cotação não encontrada ou indisponível.")
    details = load_quote_details(quote)
    totals = details.get("totals") or {}
    item = {
        "type": "cotacao",
        "id": quote.get("id"),
        "title": quote.get("titulo") or quote.get("numero_cotacao") or "Cotação",
        "subtitle": " · ".join(filter(None, [
            quote.get("status_label") or quote.get("status"),
            quote_kind_label(quote),
        ])),
        "code": quote.get("numero_cotacao") or "",
        "status": quote.get("status_label") or quote.get("status") or "",
        "kind": quote_kind_label(quote),
        "gross": format_brl(totals.get("valor_bruto") or quote.get("valor_total")),
        "net": format_brl(totals.get("valor_liquido")),
        "cost": format_brl(totals.get("total_custo_midia")),
        "margin": details.get("margin") or "",
        "responsible": quote.get("vendedor_nome") or "Não informado",
        "client_id": quote.get("cliente_id") or "",
        "client": quote.get("cliente_nome") or "",
        "period": format_period_br(quote.get("periodo_inicio"), quote.get("periodo_fim")),
        "objective": quote.get("objetivo") or "",
        "platforms": details.get("platforms") or [],
        "items": details.get("items") or [],
        "price_breakdown": details.get("breakdown") or [],
        "url": f"/cotacoes/{quote.get('id')}/detalhes",
    }
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir cotação", "url": item["url"]}],
        _focus("cotacao", item["id"], item["title"], "comercial", "cotacao"),
        display_type="quote_summary",
        summary="Encontrei a cotação.",
    )


def listar_canais_plataformas(query=None, limit=20, **_):
    rows, failed = _query_or_fail(
        lambda: db.buscar_canais_plataformas(query, min(limit, MAX_RESULTS))
    )
    if failed:
        return failed
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
    rows, failed = _query_or_fail(lambda: db.buscar_audiencias(query, min(limit, MAX_RESULTS)))
    if failed:
        return failed
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
    code = item.get("codigo_pi_cc") or item.get("codigo_pi_ag") or ""
    return {
        "type": "pi",
        "id": item.get("id_pi"),
        "title": item.get("titulo_pi") or item.get("codigo_pi_cc") or f"PI {item.get('id_pi')}",
        "subtitle": " · ".join(filter(None, [
            item.get("sub_status_descricao"),
            item.get("cliente_nome"),
        ])),
        "code": code,
        "client": item.get("cliente_nome") or "",
        "agency": item.get("agencia_nome") or "",
        "status": item.get("sub_status_descricao") or "",
        "value": _number(item.get("vr_bruto_pi")),
        "net": format_brl(item.get("vr_liquido_pi") or item.get("valor_liquido")),
        "gross": format_brl(item.get("vr_bruto_pi")),
        "responsible": item.get("responsavel_comercial_nome") or "",
        "responsible_photo": item.get("responsavel_comercial_foto_url") or "",
        "role": item.get("responsavel_comercial_cargo") or "",
        "start": format_date_br(item.get("periodo_inicio")),
        "end": format_date_br(item.get("periodo_fim")),
        "period": format_period_br(item.get("periodo_inicio"), item.get("periodo_fim")),
        "url": f"/cadu_pi/editar/{item.get('id_pi')}",
        "drive_folders": drive_folders(item),
    }


def buscar_pi(query, limit=10, status=None, ano=None, **_):
    repo = PiOperacaoRepository()
    exact = repo.obter_pi_por_numero(query)
    if exact:
        item = _pi_item(exact)
        return _ok(
            [item],
            item["title"],
            [item],
            display_type="pi_summary",
            summary="Encontrei o PI.",
            focus=_focus("pi", item["id"], item["title"], "operacao", "pi"),
        )
    year = _resolve_year(ano)
    if status:
        rows, failed = _query_or_fail(
            lambda: repo.listar_pis(
                min(limit, MAX_RESULTS), year, status, None
            )
        )
        if failed:
            return failed
        items = [_pi_item(item) for item in rows]
        return _ok(
            items,
            f"PIs {status} em {year}",
            items,
            display_type="entity_list",
            summary=f"{len(items)} PI(s) {status} em {year}.",
            period=_period_meta(year),
        )
    rows, failed = _query_or_fail(
        lambda: repo.buscar_pis(query, min(limit, MAX_RESULTS))
    )
    if failed:
        return failed
    items = [_pi_item(item) for item in rows]
    ambiguous = len(items) > 1
    return _ok(
        items,
        f"{len(items)} PI(s) encontrado(s)",
        items,
        display_type="entity_list",
        summary=(
            f"Encontrei {len(items)} PIs. Qual você quer consultar?"
            if ambiguous else (f"{len(items)} PI encontrado." if items else f'Nenhum PI encontrado para “{query}”.')
        ),
        ambiguous=ambiguous,
        focus=None if ambiguous else _unique_exact_focus(query, items, "pi", "operacao", "pi"),
    )


def consultar_pi(pi_id, **_):
    try:
        raw = PiOperacaoRepository().obter_pi(str(pi_id))
    except PiNaoEncontradoError:
        return _error("PI não encontrado ou indisponível.")
    campaigns = PiOperacaoRepository().listar_campanhas(str(pi_id))
    item = _pi_item(raw)
    item.update({
        "client_id": raw.get("id_cliente") or "",
        "campaigns": [{
            "id": row.get("id_campanha"),
            "title": row.get("nome_campanha") or f"Campanha {row.get('id_campanha')}",
            "status": row.get("status_descricao") or "",
            "period": format_period_br(row.get("periodo_inicio"), row.get("periodo_fim")),
            "dashboard": row.get("link_dash") or "",
        } for row in campaigns],
        "campaign_count": len(campaigns),
    })
    return _ok(
        item,
        item["title"],
        [item],
        [{"label": "Abrir PI", "url": item["url"]}],
        _focus("pi", item["id"], item["title"], "operacao", "pi"),
        display_type="pi_summary",
        summary="Encontrei o PI.",
    )


def listar_pis_cliente(
    cliente_id, limit=20, status=None, ano=None,
    _viewer_user_id=None, _allow_global=False, **_
):
    store = get_store()
    client = store.get_cliente(str(cliente_id))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente não encontrado ou indisponível.")
    year = _resolve_year(ano)
    if not status:
        raw = PiOperacaoRepository().resumo_operacao(year, cliente_id)
        return _status_summary(
            "pis", year, raw.get("pis_por_status") or [],
            count_key="total_pis", prompt_prefix="Liste os PIs",
        )
    if "finaliz" in str(status).casefold() and int(limit or 20) > 8:
        limit = 8
    rows = PiOperacaoRepository().listar_pis_cliente(
        str(cliente_id), min(limit, MAX_RESULTS), year, status
    )
    items = []
    for row in rows:
        enriched = dict(row)
        enriched.setdefault("cliente_nome", client.get("nome") or "")
        items.append(_pi_item(enriched))
    return _ok(
        items, f"{len(items)} PI(s) deste cliente", items,
        display_type="entity_list",
        summary=f"{len(items)} PI(s) {status} em {year}.",
        period=_period_meta(year),
    )


def _campaign_item(item):
    contracted = _number(item.get("obj_contratados"))
    achieved = _number(item.get("totalizador_atingido"))
    return {
        "type": "campanha",
        "id": item.get("id_campanha"),
        "title": item.get("nome_campanha") or f"Campanha {item.get('id_campanha')}",
        "subtitle": " · ".join(filter(None, [item.get("status_descricao"), item.get("plataforma_nome")])),
        "pi_id": item.get("id_pi") or "",
        "pi_code": item.get("codigo_pi_cc") or item.get("codigo_pi_ag") or "",
        "client": item.get("cliente_nome") or "",
        "status": item.get("status_descricao") or "",
        "platform": item.get("plataforma_nome") or "",
        "responsible": item.get("responsavel_operacao_nome") or "",
        "responsible_photo": item.get("responsavel_operacao_foto_url") or "",
        "role": item.get("responsavel_operacao_cargo") or "",
        "contracted": contracted,
        "achieved": achieved,
        "delivery_percent": _percentage(achieved, contracted),
        "spent": _number(item.get("totalizador_gasto")),
        "budget": _number(item.get("custo_midia_orcado")),
        "value": _number(item.get("valor_plataforma")),
        "period": format_period_br(item.get("periodo_inicio"), item.get("periodo_fim")),
        "dashboard": item.get("link_dash") or "",
        "url": f"/campanhas-pi/{item.get('id_campanha')}",
    }


def buscar_campanha(query, limit=10, status=None, ano=None, risco=False, **_):
    year = _resolve_year(ano)
    if status or risco:
        items = [
            _campaign_item(item)
            for item in PiOperacaoRepository().listar_campanhas_filtradas(
                min(limit, MAX_RESULTS), year, status, None, bool(risco)
            )
        ]
        label = "com risco" if risco else status
        return _ok(
            items,
            f"Campanhas {label} em {year}",
            items,
            display_type="entity_list",
            summary=f"{len(items)} campanha(s) {label} em {year}.",
            period=_period_meta(year),
        )
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
        display_type="campaign_summary",
        summary="Encontrei a campanha.",
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


def _status_summary(kind, year, rows, count_key="total_pis", prompt_prefix="Liste os PIs"):
    counts = [{
        "status": item.get("status_descricao") or item.get("status") or "Sem status",
        "count": int(item.get(count_key) or item.get("count") or 0),
        "label": item.get("status_descricao") or item.get("status") or "Sem status",
    } for item in rows]
    display_items = [{
        "title": item["status"],
        "subtitle": f'{item["count"]}',
        "count": item["count"],
        "group": kind,
    } for item in counts]
    title = f"{'PIs' if kind == 'pis' else 'Campanhas'} em {year}"
    actions = []
    for item in counts:
        status = item["status"]
        lowered = status.casefold()
        if "finaliz" in lowered and item["count"] > 8:
            continue
        if item["count"] <= 0:
            continue
        if kind == "pis":
            actions.append({
                "kind": "prompt",
                "label": status,
                "prompt": f"{prompt_prefix} {status.casefold()}.",
            })
        else:
            actions.append({
                "kind": "prompt",
                "label": f"Ver {status.casefold()}",
                "prompt": f"Liste as campanhas {status.casefold()}.",
            })
    result = _ok(
        {"year": year, "counts": counts, "total": sum(item["count"] for item in counts)},
        title,
        display_items,
        display_type="status_summary",
        summary=title,
        actions=actions[:6],
        period=_period_meta(year),
    )
    result["display"]["groups"] = [{
        "title": title,
        "items": [{"label": item["status"], "count": item["count"]} for item in counts],
    }]
    result["display"]["metrics"] = [
        {"label": "Período", "value": year},
        {"label": "Total", "value": sum(item["count"] for item in counts)},
    ]
    return result


def resumir_operacao(ano=None, cliente_id=None, escopo=None, **_):
    year = _resolve_year(ano)
    raw = PiOperacaoRepository().resumo_operacao(year, cliente_id)
    escopo = str(escopo or "operacao").casefold()
    if escopo in {"pis", "pi"}:
        return _status_summary("pis", year, raw.get("pis_por_status") or [], "total_pis")
    if escopo in {"campanhas", "campanha"}:
        campaign_rows = raw.get("campanhas_por_status") or []
        summary = _status_summary(
            "campanhas", year, campaign_rows, "total_campanhas", "Liste as campanhas"
        )
        actions = list(summary["display"]["actions"])
        actions.append({
            "kind": "prompt", "label": "Ver com risco",
            "prompt": "Liste as campanhas com risco.",
        })
        summary["display"]["actions"] = actions
        return summary
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
        "year": year,
        "total_pis": sum(item["count"] for item in pis_por_status),
        "gross_value": round(sum(item["gross_value"] for item in pis_por_status), 2),
        "total_campaigns": sum(item["count"] for item in campanhas_por_status),
        "pis_by_status": pis_por_status,
        "campaigns_by_status": campanhas_por_status,
        "campaigns_by_platform": plataformas,
    }
    display_items = [
        {
            "title": item["status"],
            "subtitle": f'{item["count"]} PI(s)',
            "count": item["count"],
            "value": item["gross_value"],
            "group": "pi",
        }
        for item in pis_por_status
    ] + [
        {
            "title": item["status"],
            "subtitle": f'{item["count"]} campanha(s)',
            "count": item["count"],
            "delivery_percent": item["delivery_percent"],
            "group": "campaign",
        }
        for item in campanhas_por_status
    ]
    actions = []
    for item in pis_por_status:
        if item["count"] and "finaliz" not in item["status"].casefold():
            actions.append({
                "kind": "prompt",
                "label": item["status"],
                "prompt": f"Liste os PIs {item['status'].casefold()}.",
            })
    for item in campanhas_por_status:
        lowered = item["status"].casefold()
        if item["count"] and "finaliz" not in lowered:
            actions.append({
                "kind": "prompt",
                "label": f"Ver {item['status'].casefold()}",
                "prompt": f"Liste as campanhas {item['status'].casefold()}.",
            })
    result = _ok(
        data,
        f"Operação em {year}",
        display_items,
        display_type="operation_summary",
        summary=f"Operação em {year}",
        actions=actions[:8],
        period=_period_meta(year),
    )
    result["display"]["metrics"] = [
        {"label": "Período", "value": year},
        {"label": "PIs", "value": data["total_pis"]},
        {"label": "Campanhas", "value": data["total_campaigns"]},
        {"label": "Valor bruto", "value": data["gross_value"], "kind": "currency"},
    ]
    result["display"]["groups"] = [
        {"title": "PIs", "items": [{"label": item["status"], "count": item["count"]} for item in pis_por_status]},
        {"title": "Campanhas", "count": data["total_campaigns"], "items": [
            {"label": item["status"], "count": item["count"]} for item in campanhas_por_status
        ]},
    ]
    return result


def listar_objetivos(
    cliente_id, limit=20, _viewer_user_id=None, _allow_global=False, **_
):
    store = get_store()
    client = store.get_cliente(str(cliente_id))
    if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
        return _error("Cliente não encontrado ou indisponível.")
    goals = store.list_objetivos(str(cliente_id))
    if goals is None:
        return _error("Cliente não encontrado ou indisponível.")
    items = [{
        "id": item.get("id"),
        "title": item.get("texto") or "Objetivo",
        "subtitle": " · ".join(filter(None, [
            "Conquistado" if item.get("concluido") or item.get("conquistado") else "Aberto",
            item.get("prazo") or item.get("data_prazo") or "",
        ])),
        "done": bool(item.get("concluido") or item.get("conquistado")),
        "deadline": item.get("prazo") or item.get("data_prazo") or "",
        "url": f"/crm-v3/#cliente={cliente_id}",
    } for item in goals[:min(limit, MAX_RESULTS)]]
    return _ok(items, f"{len(items)} objetivo(s)", items)


def listar_notas_fiscais(
    pi_id=None, cliente_id=None, limit=10,
    _viewer_user_id=None, _allow_global=False, **_
):
    if cliente_id:
        client = get_store().get_cliente(str(cliente_id))
        if not client or not _client_allowed(client, _viewer_user_id, _allow_global):
            return _error("Cliente não encontrado ou indisponível.")
    rows, failed = _query_or_fail(lambda: PiOperacaoRepository().listar_notas_fiscais(
        pi_id=pi_id, cliente_id=cliente_id, limite=min(limit, MAX_RESULTS)
    ))
    if failed:
        return failed
    items = [{
        "type": "nota_fiscal",
        "id": item.get("id"),
        "title": item.get("numero_nota") or f"NF {item.get('id')}",
        "subtitle": " · ".join(filter(None, [
            item.get("cliente_nome"),
            item.get("codigo_pi_cc"),
            item.get("status_descricao"),
        ])),
        "amount": _number(item.get("valor")),
        "net": _number(item.get("valor_liquido")),
        "status": item.get("status_descricao") or "",
        "issued_at": format_date_br(item.get("data_emissao")),
        "paid_at": format_date_br(item.get("data_pag_realizado")),
        "due": format_date_br(item.get("data_pag_prevista")),
        "pi_id": item.get("id_pi"),
        "url": f"/cadu_pi/editar/{item.get('id_pi')}" if item.get("id_pi") else "/financeiro/",
    } for item in rows]
    return _ok(items, f"{len(items)} nota(s) fiscal(is)", items)


def listar_reembolsos(limit=10, status=None, _viewer_user_id=None, _allow_global=False, **_):
    from ...financeiro.db_finance import list_expenses_for_user
    from ...financeiro.permissions import is_finance_admin

    filtros = {"status": status} if status else {}
    if _allow_global and is_finance_admin():
        rows, failed = _query_or_fail(lambda: _list_all_expenses(filtros, min(limit, MAX_RESULTS)))
    else:
        rows, failed = _query_or_fail(lambda: list_expenses_for_user(
            _viewer_user_id, filtros
        )[:min(limit, MAX_RESULTS)])
    if failed:
        return failed
    items = [{
        "type": "reembolso",
        "id": item.get("id"),
        "title": item.get("merchant_name") or item.get("notes") or "Despesa",
        "subtitle": " · ".join(filter(None, [
            item.get("category_label"),
            item.get("status"),
            str(item.get("expense_date") or ""),
        ])),
        "amount": _number(item.get("total_amount")),
        "status": item.get("status") or "",
        "client_id": item.get("client_id") or "",
        "url": "/financeiro/meus-reembolsos",
    } for item in rows[:min(limit, MAX_RESULTS)]]
    return _ok(items, f"{len(items)} reembolso(s)", items)


def _list_all_expenses(filtros, limit):
    conn = db.get_db()
    clauses = ["TRUE"]
    params = []
    if filtros.get("status"):
        clauses.append("e.status = %s")
        params.append(filtros["status"])
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT e.id, e.user_id, e.status, e.merchant_name, e.expense_date,
                   e.total_amount, e.client_id, e.notes,
                   cat.label AS category_label
              FROM finance_expenses e
              LEFT JOIN finance_expense_categories cat ON cat.id = e.category_id
             WHERE {' AND '.join(clauses)}
             ORDER BY e.created_at DESC
             LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def resumir_financeiro(_viewer_user_id=None, _allow_global=False, **_):
    from ...financeiro.db_finance import list_expenses_for_user, list_summaries_for_user
    from ...financeiro.permissions import is_finance_admin

    def _run():
        expenses = list_expenses_for_user(_viewer_user_id, {})
        summaries = list_summaries_for_user(_viewer_user_id)
        invoices = PiOperacaoRepository().resumo_notas_fiscais()
        return expenses, summaries, invoices

    packed, failed = _query_or_fail(_run)
    if failed:
        return failed
    expenses, summaries, invoices = packed
    mine_total = round(sum(_number(item.get("total_amount")) or 0 for item in expenses), 2)
    by_status = {}
    for item in expenses:
        key = item.get("status") or "sem_status"
        by_status[key] = by_status.get(key, 0) + 1
    data = {
        "my_expenses": len(expenses),
        "my_expense_total": mine_total,
        "my_expenses_by_status": by_status,
        "my_summaries": len(summaries or []),
        "invoices_by_status": [{
            "status": item.get("status_descricao"),
            "count": int(item.get("total") or 0),
        } for item in invoices],
        "scope": "all" if _allow_global and is_finance_admin() else "mine",
    }
    display = [{
        "title": "Meus reembolsos",
        "subtitle": f'{data["my_expenses"]} lançamento(s)',
        "value": mine_total,
    }] + [{
        "title": item["status"],
        "subtitle": f'{item["count"]} NF(s)',
    } for item in data["invoices_by_status"]]
    return _ok(data, "Resumo financeiro", display)


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


def lookup_document_refs(hints):
    """Tenta relacionar identificadores extraídos de um anexo com registros reais."""
    hits = []
    unmatched = []
    repo = PiOperacaoRepository()
    store = get_store()
    for number in hints.get("pis") or []:
        raw = repo.obter_pi_por_numero(number)
        if raw:
            item = _pi_item(raw)
            item["origin"] = "centralx"
            hits.append(item)
        else:
            unmatched.append({"kind": "pi", "value": number})
    for code in hints.get("quotes") or []:
        quotes = store.search_cotacoes(code, 3) or []
        exact = [
            item for item in quotes
            if str(item.get("numero_cotacao") or "").upper() == str(code).upper()
        ]
        if exact:
            item = _quote_list_item(exact[0])
            item["origin"] = "centralx"
            hits.append(item)
        else:
            unmatched.append({"kind": "cotacao", "value": code})
    if not hits:
        return _ok(
            {"source": "document", "matches": [], "unmatched": unmatched},
            "Documento identificado",
            [],
            display_type="document_summary",
            summary="Não encontrei um registro correspondente no CentralX.",
            empty={
                "title": "Não encontrei um registro correspondente no CentralX.",
                "body": "O documento foi lido, mas não deu para relacionar com um PI, cotação ou NF com segurança.",
                "actions": [
                    {"kind": "prompt", "label": "Buscar cliente", "prompt": "Busque o cliente mencionado neste documento."},
                    {"kind": "prompt", "label": "Buscar PI", "prompt": "Busque o PI mencionado neste documento."},
                    {"kind": "prompt", "label": "Buscar cotação", "prompt": "Busque a cotação mencionada neste documento."},
                ],
            },
        )
    item = hits[0]
    display_type = "pi_summary" if item.get("type") == "pi" else "quote_summary"
    return _ok(
        {"source": "centralx", "document": hints, "matches": hits, "unmatched": unmatched},
        item.get("title") or "Documento identificado",
        hits,
        display_type=display_type,
        summary="Documento identificado. Dados encontrados no CentralX.",
        focus=_focus(item.get("type"), item.get("id"), item.get("title"), "operacao" if item.get("type") == "pi" else "comercial", item.get("type")),
    )
