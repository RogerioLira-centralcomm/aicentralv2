"""Formatadores e resumos operacionais do Agente CentralX."""

from datetime import date, datetime
from decimal import Decimal
import re

from ..cotacao_tipos import rotulo_tipo_comercial

DEFAULT_OPERATION_YEAR = date.today().year

KPI_METRIC_KEYS = (
    ("cpm", "CPM"),
    ("cpc", "CPC"),
    ("cpa", "CPA"),
    ("cpv", "CPV"),
    ("cpl", "CPL"),
    ("cpe", "CPE"),
    ("ctr", "CTR"),
    ("vtr", "VTR"),
    ("custo_por_resultado", "Custo por resultado"),
    ("impressoes", "Impressões"),
    ("cliques", "Cliques"),
    ("visualizacoes", "Visualizações"),
    ("conversoes", "Conversões"),
    ("leads", "Leads"),
    ("alcance", "Alcance"),
    ("frequencia", "Frequência"),
    ("volume_contratado", "Volume contratado"),
)

PRICE_ROWS = (
    ("custo_midia", "Mídia orçada"),
    ("tech_fee", "Tech fee"),
    ("comissao", "Comissão comercial"),
    ("impostos", "Impostos"),
    ("incentivos", "Incentivos"),
)

DRIVE_FOLDERS = (
    ("principal", "Principal", "googled_pi_princ"),
    ("financeiro", "Financeiro", "googled_pi_financ"),
    ("pecas", "Peças", "googled_pi_pecas"),
    ("assinados", "Assinados", "googled_pi_arq_ass"),
)

COT_CODE_RE = re.compile(r"COT-\d{6}-[A-Z0-9]+", re.IGNORECASE)
PI_NUMBER_RE = re.compile(r"PI[_\s-]*0*(\d{4,})", re.IGNORECASE)
CNPJ_RE = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
NF_RE = re.compile(r"(?:NF[eE]?s?-?e?|nota\s+fiscal)[^\d]{0,8}(\d{3,})", re.IGNORECASE)


def parse_number(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return float(value)
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


def format_brl(value, hide_zero=True):
    number = parse_number(value)
    if number is None:
        return ""
    if hide_zero and number == 0:
        return ""
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def format_percent(value):
    number = parse_number(value)
    if number is None:
        return ""
    return f"{number:.2f}%".replace(".", ",")


def format_volume(value):
    number = parse_number(value)
    if number is None:
        return ""
    if number >= 1000 and number == int(number):
        return f"{int(number):,}".replace(",", ".")
    if number == int(number):
        return str(int(number))
    return f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_date_br(value, with_time=False):
    if value in (None, ""):
        return ""
    if hasattr(value, "strftime"):
        if with_time and getattr(value, "hour", None) is not None:
            if isinstance(value, datetime) and (value.hour or value.minute):
                return value.strftime("%d/%m/%Y às %H:%M")
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    if not text:
        return ""
    if re.match(r"\d{2}/\d{2}/\d{4}", text):
        if with_time and " " in text:
            date_part, time_part = text.split(" ", 1)
            hour = time_part[:5]
            return f"{date_part} às {hour}"
        return text[:10]
    match = re.match(
        r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?",
        text,
    )
    if not match:
        return text
    year, month, day, hour, minute = match.groups()
    if hour is not None and (with_time or hour != "00" or minute != "00"):
        return f"{day}/{month}/{year} às {hour}:{minute}"
    return f"{day}/{month}/{year}"


def format_period_br(start, end):
    left = format_date_br(start)
    right = format_date_br(end)
    if left and right:
        return f"{left} — {right}"
    return left or right


def quote_kind_label(quote):
    return quote.get("tipo_comercial_label") or rotulo_tipo_comercial(
        quote.get("tipo_comercial")
    )


def _money_fact(label, value):
    formatted = format_brl(value)
    if not formatted:
        return None
    return {"label": label, "value": formatted, "raw": parse_number(value)}


def _text_fact(label, value):
    text = str(value or "").strip()
    if not text:
        return None
    return {"label": label, "value": text}


def _kpi_metrics(row):
    metrics = []
    kpi = str(row.get("objetivo_kpi") or row.get("formato_compra") or "").strip()
    unit = format_brl(
        row.get("valor_unitario_negociado") or row.get("valor_unitario_tabela")
        or row.get("valor_unitario")
    )
    if kpi and unit:
        metrics.append({"label": kpi, "value": unit})
    volume = format_volume(row.get("volume_contratado") or row.get("impressoes_estimadas"))
    if volume:
        label = "Volume"
        kpi_lower = kpi.casefold()
        if "cpm" in kpi_lower:
            label = "Impressões"
        elif "cpc" in kpi_lower:
            label = "Cliques"
        elif "cpv" in kpi_lower:
            label = "Visualizações"
        elif any(token in kpi_lower for token in ("cpa", "cpl")):
            label = "Conversões"
        metrics.append({"label": label, "value": volume})
    aliases = {
        "impressoes": row.get("impressoes") or row.get("impressoes_estimadas"),
        "cliques": row.get("cliques"),
        "visualizacoes": row.get("visualizacoes"),
        "conversoes": row.get("conversoes"),
        "leads": row.get("leads"),
        "alcance": row.get("alcance"),
        "frequencia": row.get("frequencia"),
        "ctr": row.get("ctr"),
        "vtr": row.get("vtr"),
        "custo_por_resultado": row.get("custo_por_resultado"),
    }
    used = {item["label"].casefold() for item in metrics}
    for key, label in KPI_METRIC_KEYS:
        if label.casefold() in used:
            continue
        raw = aliases.get(key)
        if raw in (None, ""):
            continue
        if key in {"ctr", "vtr"}:
            value = format_percent(raw) if parse_number(raw) and parse_number(raw) <= 100 else format_volume(raw)
        elif key in {"cpm", "cpc", "cpa", "cpv", "cpl", "cpe", "custo_por_resultado"}:
            value = format_brl(raw)
        else:
            value = format_volume(raw) or format_brl(raw) or str(raw)
        if value:
            metrics.append({"label": label, "value": value})
            used.add(label.casefold())
    return metrics


def _quote_line_summary(row):
    if row.get("is_header") or row.get("is_subtotal"):
        return None
    title = row.get("plataforma") or row.get("titulo") or row.get("formato") or "Item"
    kind = row.get("formato") or row.get("tipo") or row.get("objetivo_kpi") or ""
    metrics = _kpi_metrics(row)
    facts = list(filter(None, [
        _text_fact("Objetivo", row.get("objetivo") or row.get("objetivo_kpi")),
        _text_fact("KPI", row.get("objetivo_kpi") or row.get("formato_compra")),
        _money_fact("Valor líquido", row.get("investimento_liquido")),
        _money_fact("Valor bruto", row.get("investimento_bruto")),
        _money_fact("Custo base", row.get("custo_midia")),
        _money_fact("Tech fee", row.get("val_tech_fee")),
        _money_fact("Comissão", row.get("val_com_vendas")),
    ]))
    return {
        "id": row.get("id"),
        "title": title,
        "subtitle": kind,
        "metrics": metrics,
        "facts": facts,
        "net": format_brl(row.get("investimento_liquido")),
        "gross": format_brl(row.get("investimento_bruto")),
    }


def _specific_item_summary(row):
    title = row.get("titulo") or "Entrega"
    facts = list(filter(None, [
        _text_fact("Descrição", row.get("descricao")),
        _text_fact("Quantidade", row.get("quantidade")),
        _money_fact("Valor unitário", row.get("valor_unitario")),
        _money_fact("Valor líquido", row.get("subtotal")),
    ]))
    return {
        "id": row.get("id"),
        "title": title,
        "subtitle": row.get("tipo_comercial") or "",
        "metrics": [],
        "facts": facts,
        "net": format_brl(row.get("subtotal") or row.get("valor_unitario")),
        "gross": "",
    }


def _sum_money(rows, key):
    total = 0.0
    found = False
    for row in rows:
        number = parse_number(row.get(key))
        if number is None:
            continue
        found = True
        total += number
    return total if found else None


def quote_price_breakdown(linhas, audiencias, totals):
    rows = [item for item in (linhas or []) if not item.get("is_header") and not item.get("is_subtotal")]
    rows.extend(audiencias or [])
    cost = _sum_money(rows, "custo_midia")
    if cost is None:
        cost = parse_number((totals or {}).get("total_custo_midia"))
    composition = []
    mapping = (
        (cost, "Mídia orçada"),
        (_sum_money(rows, "val_tech_fee"), "Tech fee"),
        (_sum_money(rows, "val_com_vendas"), "Comissão comercial"),
        (_sum_money(rows, "val_impostos"), "Impostos"),
        (_sum_money(rows, "val_pl_incentivos"), "Incentivos"),
    )
    for amount, label in mapping:
        formatted = format_brl(amount, hide_zero=(label != "Incentivos"))
        if not formatted:
            continue
        composition.append({"label": label, "value": formatted, "raw": amount})
    net = format_brl((totals or {}).get("valor_liquido"))
    gross = format_brl((totals or {}).get("valor_bruto"))
    if net:
        composition.append({"label": "Valor líquido", "value": net, "raw": parse_number((totals or {}).get("valor_liquido")), "emphasis": True})
    if gross:
        composition.append({"label": "Valor bruto", "value": gross, "raw": parse_number((totals or {}).get("valor_bruto")), "emphasis": True})
    return composition


def quote_margin(totals):
    net = parse_number((totals or {}).get("valor_liquido"))
    cost = parse_number((totals or {}).get("total_custo_midia"))
    if net in (None, 0) or cost is None:
        return ""
    return format_percent(((net - cost) / net) * 100)


def load_quote_details(quote):
    quote_id = quote.get("id")
    if not quote_id:
        return {"items": [], "platforms": quote.get("plataformas") or [], "totals": {}, "breakdown": []}
    from .. import db

    linhas = []
    audiencias = []
    extras = []
    try:
        linhas = db.obter_linhas_cotacao(quote_id) or []
    except Exception:
        linhas = []
    try:
        audiencias = db.obter_audiencias_cotacao(quote_id) or []
    except Exception:
        audiencias = []
    try:
        extras = db.listar_itens_especificos_cotacao(quote_id) or []
    except Exception:
        extras = []
    try:
        totals = db.calcular_totais_financeiros_cotacao(linhas, audiencias)
    except Exception:
        totals = {}
    items = [item for item in (_quote_line_summary(row) for row in linhas) if item]
    items.extend(_quote_line_summary(row) for row in audiencias if _quote_line_summary(row))
    items.extend(_specific_item_summary(row) for row in extras)
    platforms = []
    seen = set()
    for name in quote.get("plataformas") or []:
        label = str(name or "").strip()
        if label and label.casefold() not in seen:
            platforms.append(label)
            seen.add(label.casefold())
    for row in linhas + audiencias:
        label = str(row.get("plataforma") or "").strip()
        if label and label.casefold() not in seen:
            platforms.append(label)
            seen.add(label.casefold())
    return {
        "items": items,
        "platforms": platforms,
        "totals": totals,
        "breakdown": quote_price_breakdown(linhas, audiencias, totals),
        "margin": quote_margin(totals),
    }


def drive_folders(record):
    folders = []
    for key, label, field in DRIVE_FOLDERS:
        url = str((record or {}).get(field) or "").strip()
        if not url:
            continue
        folders.append({"key": key, "label": label, "url": url})
    return folders


def document_hints(text, attachments=None):
    blob = " ".join(filter(None, [
        str(text or ""),
        " ".join(str(item.get("name") or "") for item in (attachments or [])),
        " ".join(str(item.get("text") or "")[:4000] for item in (attachments or [])),
    ]))
    quotes = list(dict.fromkeys(match.group(0).upper() for match in COT_CODE_RE.finditer(blob)))
    pis = list(dict.fromkeys(match.group(1).lstrip("0") or "0" for match in PI_NUMBER_RE.finditer(blob)))
    invoices = list(dict.fromkeys(match.group(1) for match in NF_RE.finditer(blob)))
    cnpjs = list(dict.fromkeys(match.group(0) for match in CNPJ_RE.finditer(blob)))
    return {
        "quotes": quotes[:5],
        "pis": [item for item in pis if item != "0"][:5],
        "invoices": invoices[:5],
        "cnpjs": cnpjs[:5],
    }


AI_HISTORY_FUNCTIONS = {"gerar-roteiro", "melhorar-texto", "gerar-comunicacao"}


def activity_due_iso(item):
    return str(item.get("data_prazo") or item.get("data") or "").strip()[:10]


def activity_due_bucket(item, today=None):
    iso = activity_due_iso(item)
    if not iso:
        return ""
    try:
        due = datetime.strptime(iso, "%Y-%m-%d").date()
    except ValueError:
        return ""
    diff = (due - (today or date.today())).days
    if diff < 0:
        return "atrasadas"
    if diff == 0:
        return "hoje"
    if diff <= 7:
        return "semana"
    return ""


def activity_history_items(rows):
    items = []
    for row in rows or []:
        function = str(row.get("function") or "").strip()
        if function and function not in AI_HISTORY_FUNCTIONS:
            continue
        content = row.get("content") or {}
        subject = str(content.get("assunto") or content.get("titulo") or "").strip()
        body = str(content.get("mensagem") or content.get("texto") or "").strip()
        if subject and body.startswith(subject):
            body = body[len(subject):].strip()
        if not subject and not body:
            continue
        items.append({
            "id": row.get("id"),
            "function": function,
            "label": "Registro revisado" if function == "melhorar-texto" else "Geração",
            "subject": subject,
            "message": body,
            "created_at": format_date_br(row.get("created_at"), with_time=True)
            or format_date_br(row.get("created_at")),
        })
    return items
