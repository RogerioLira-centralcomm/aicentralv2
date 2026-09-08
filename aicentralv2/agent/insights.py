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
            {"label": "Listar PIs deste cliente", "prompt": "Liste os PIs deste cliente.", "icon": "fa-receipt"},
        ]
    if entity_type == "pi":
        return [
            {"label": "Resumir este PI", "prompt": "Consulte este PI e resuma status, valor, período e responsável.", "icon": "fa-receipt"},
            {"label": "Listar campanhas", "prompt": "Liste as campanhas deste PI com objetivo, entrega, gasto e orçamento.", "icon": "fa-bullhorn"},
            {"label": "Analisar operação", "prompt": "Analise a situação operacional deste PI e destaque riscos nos números das campanhas.", "icon": "fa-chart-line"},
        ]
    if entity_type in {"campanha", "campaign"}:
        return [
            {"label": "Consultar campanha", "prompt": "Consulte esta campanha e resuma seus indicadores operacionais.", "icon": "fa-bullhorn"},
            {"label": "Analisar entrega", "prompt": "Compare objetivo, entrega, gasto e orçamento desta campanha.", "icon": "fa-chart-line"},
            {"label": "Consultar o PI", "prompt": "Consulte o PI relacionado a esta campanha.", "icon": "fa-receipt"},
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
        {"label": "Resumo da operação", "prompt": "Mostre os números consolidados atuais de PIs e campanhas.", "icon": "fa-chart-line"},
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

    if not entity_id:
        return empty

    store = get_store()
    if entity_type in {"cotacao", "quote"}:
        quote = store.get_cotacao(entity_id)
        if not quote:
            return empty
        status = str(
            quote.get("status_label") or quote.get("status") or ""
        ).casefold()
        entity = {
            "id": str(quote.get("id") or entity_id),
            "label": quote.get("titulo") or quote.get("numero_cotacao") or label or "Cotação",
            "type": "cotacao",
            "url": f"/cotacoes/{entity_id}/detalhes",
        }
        alerts = []
        if "rascunho" in status or not status:
            alerts.append({
                "id": "complete_quote",
                "tone": "warn",
                "icon": "fa-pen-ruler",
                "title": "Concluir proposta.",
                "body": "Revise briefing, formatos e valores antes do envio.",
                "prompt": "Analise esta cotação e liste o que falta para concluir a proposta.",
            })
        elif "enviad" in status or "análise" in status or "analise" in status:
            alerts.append({
                "id": "quote_follow_up",
                "tone": "warn",
                "icon": "fa-phone",
                "title": "Planejar follow-up.",
                "body": "A proposta foi enviada e precisa de uma próxima ação comercial.",
                "prompt": "Sugira um follow-up objetivo para esta cotação.",
            })
        elif "aprovad" in status:
            alerts.append({
                "id": "quote_approved",
                "tone": "info",
                "icon": "fa-circle-check",
                "title": "Preparar operação.",
                "body": "Confirme materiais, responsáveis e próximos marcos da campanha.",
                "prompt": "Liste os próximos passos operacionais desta cotação aprovada.",
            })
        elif any(term in status for term in ("rejeit", "perdid", "cancel")):
            alerts.append({
                "id": "quote_lost",
                "tone": "info",
                "icon": "fa-rotate",
                "title": "Registrar aprendizado.",
                "body": "Documente o motivo e identifique uma oportunidade futura.",
                "prompt": "Ajude a registrar o aprendizado e uma próxima oportunidade para esta cotação.",
            })
        if not quote.get("objetivo"):
            alerts.append({
                "id": "missing_objective",
                "tone": "warn",
                "icon": "fa-bullseye",
                "title": "Objetivo não informado.",
                "body": "Defina o resultado esperado para orientar proposta e mensuração.",
                "prompt": "Sugira perguntas para definir o objetivo desta cotação.",
            })
        return {"entity": entity, "alerts": alerts, "prompts": prompts}

    if entity_type not in {"cliente", "client"}:
        return empty

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
    if not activities:
        alerts.append({
            "id": "first_contact",
            "tone": "warn",
            "icon": "fa-calendar-plus",
            "title": "Planejar primeiro contato.",
            "body": "O cliente ainda não possui atividade comercial registrada.",
            "prompt": "Sugira uma primeira abordagem e uma atividade para este cliente.",
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
