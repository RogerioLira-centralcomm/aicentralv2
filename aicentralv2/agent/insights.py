"""Sugestões estáticas e insights de leitura para o Agente CentralX."""

from datetime import date, datetime

from ..crm_v3_repository import get_store

FINAL_QUOTE_STATUS = {
    "rejeitada",
    "cancelada",
    "perdida",
    "arquivada",
    "encerrada",
    "recusada",
}
DONE_ACTIVITY_STATUS = {"concluida", "concluída", "cancelada"}


def suggestion_prompts(context):
    entity_type = (context.get("entity_type") or "").casefold()
    screen = (context.get("screen") or "").casefold()
    if entity_type in {"cliente", "client"}:
        return [
            {"label": "Quais cotações estão abertas?", "prompt": "Liste as cotações abertas deste cliente.", "icon": "fa-magnifying-glass"},
            {"label": "Mostrar histórico de atividades", "prompt": "Liste as atividades deste cliente.", "icon": "fa-magnifying-glass"},
            {"label": "Listar PIs deste cliente", "prompt": "Liste as cotações e campanhas deste cliente.", "icon": "fa-magnifying-glass"},
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


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _quote_date(item):
    return _parse_date(item.get("periodo_inicio")) or _parse_date(item.get("data"))


def build_insights(context):
    prompts = suggestion_prompts(context)
    entity_type = (context.get("entity_type") or "").casefold()
    entity_id = str(context.get("entity_id") or "").strip()
    label = str(context.get("entity_label") or "").strip()
    empty = {"entity": None, "alerts": [], "prompts": prompts}

    if entity_type not in {"cliente", "client"} or not entity_id:
        return empty

    store = get_store()
    client = store.get_cliente(str(entity_id))
    if not client:
        return empty

    entity = {
        "id": str(client.get("id") or entity_id),
        "label": client.get("nome") or label or "Cliente",
        "type": "cliente",
        "url": f"/crm-v3/#cliente={entity_id}",
    }
    alerts = []
    today = date.today()

    activities = store.list_atividades(str(entity_id)) or []
    overdue = []
    for item in activities:
        status = str(item.get("status") or "").casefold()
        if status in DONE_ACTIVITY_STATUS:
            continue
        deadline = _parse_date(item.get("data_prazo")) or _parse_date(item.get("data"))
        if deadline and deadline < today:
            overdue.append(item)
    if overdue:
        count = len(overdue)
        noun = "atividade" if count == 1 else "atividades"
        alerts.append({
            "id": "overdue_activities",
            "tone": "danger",
            "icon": "fa-calendar-xmark",
            "title": f"{count} {noun} em atraso.",
            "body": f"Este cliente possui {count} {noun} sem atualização.",
            "prompt": "Liste as atividades em atraso deste cliente.",
        })

    quotes = store.list_cotacoes(str(entity_id)) or []
    last_quote = None
    for item in quotes:
        parsed = _quote_date(item)
        if parsed and (last_quote is None or parsed > last_quote):
            last_quote = parsed
    if not quotes:
        alerts.append({
            "id": "new_opportunity",
            "tone": "warn",
            "icon": "fa-chart-line",
            "title": "Nova oportunidade.",
            "body": "Ainda não há cotação neste cliente. Que tal criar uma?",
            "prompt": "Quero criar uma cotação para este cliente.",
        })
    elif last_quote:
        months = (today.year - last_quote.year) * 12 + (today.month - last_quote.month)
        if months >= 4:
            alerts.append({
                "id": "stale_quote",
                "tone": "warn",
                "icon": "fa-chart-line",
                "title": "Nova oportunidade.",
                "body": f"Há {months} meses sem nova cotação. Que tal criar uma?",
                "prompt": "Quero criar uma cotação para este cliente.",
            })

    open_quotes = [
        item for item in quotes
        if str(item.get("status") or "").casefold() not in FINAL_QUOTE_STATUS
        and "rejeit" not in str(item.get("status_label") or "").casefold()
    ]
    if open_quotes:
        count = len(open_quotes)
        noun = "campanha ativa" if count == 1 else "campanhas ativas"
        alerts.append({
            "id": "open_campaigns",
            "tone": "danger",
            "icon": "fa-bullhorn",
            "title": "Campanhas em andamento.",
            "body": f"{count} {noun} neste cliente.",
            "prompt": "Liste as cotações abertas deste cliente.",
        })

    return {"entity": entity, "alerts": alerts, "prompts": prompts}
