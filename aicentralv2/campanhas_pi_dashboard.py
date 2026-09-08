"""Projeções puras do painel operacional de campanhas."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import re
import unicodedata


ACTIVE_STATUS_NAMES = frozenset({"ativa", "ativo", "em andamento"})
DEFAULT_STALE_DAYS = 3


def normalize_text(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def parse_number(value):
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    raw = re.sub(r"[^\d,.\-]", "", str(value).strip())
    if not raw:
        return 0.0
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    try:
        return float(Decimal(raw))
    except (InvalidOperation, ValueError):
        return 0.0


def as_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (TypeError, ValueError):
        return None


def month_reference(day):
    day = as_date(day) or date.today()
    return f"{day.month}/{day.strftime('%y')}"


def previous_month_reference(day):
    if isinstance(day, str) and re.fullmatch(r"\d{1,2}/\d{2,4}", day.strip()):
        month_raw, year_raw = day.strip().split("/")
        year = int(year_raw)
        if year < 100:
            year += 2000
        try:
            day = date(year, int(month_raw), 1)
        except ValueError:
            day = date.today()
    else:
        day = as_date(day) or date.today()
    previous = day.replace(day=1) - timedelta(days=1)
    return month_reference(previous)


def percentage_delta(current, previous):
    current = parse_number(current)
    previous = parse_number(previous)
    if previous == 0:
        return None if current else 0.0
    return round(((current - previous) / previous) * 100, 1)


def _clamp(value, lower=0.0, upper=100.0):
    return round(max(lower, min(upper, value)), 1)


def _campaign_progress(row, today):
    start = as_date(row.get("periodo_inicio"))
    finish = as_date(row.get("periodo_fim"))
    if not start or not finish:
        return 0.0, None
    total_days = max((finish - start).days, 1)
    elapsed_days = (today - start).days
    return _clamp((elapsed_days / total_days) * 100), (finish - today).days


def project_campaign_health(
    campaign,
    today=None,
    tolerance=5.0,
    stale_days=DEFAULT_STALE_DAYS,
):
    """Acrescenta ritmo, risco e recomendação sem alterar a linha original."""
    today = as_date(today) or date.today()
    row = dict(campaign)
    period_pct, days_left = _campaign_progress(row, today)
    objective = parse_number(row.get("obj_contratados"))
    delivered = parse_number(row.get("totalizador_atingido"))
    planned = parse_number(row.get("custo_midia_previsto")) or parse_number(
        row.get("valor_plataforma")
    )
    spent = parse_number(row.get("totalizador_gasto"))
    delivery_pct = _clamp((delivered / objective) * 100, upper=999.0) if objective else 0.0
    investment_pct = _clamp((spent / planned) * 100, upper=999.0) if planned else 0.0
    latest_diary = as_date(row.get("ultimo_diario_data"))
    diary_age = (today - latest_diary).days if latest_diary else None
    delivery_gap = round(period_pct - delivery_pct, 1)
    investment_gap = round(investment_pct - period_pct, 1)

    issues = []
    score = 0
    if not row.get("id_responsavel_operacao") and not row.get("responsavel_operacao_nome"):
        issues.append(("Sem responsável operacional", 32, "owner"))
    if not as_date(row.get("periodo_inicio")) or not as_date(row.get("periodo_fim")):
        issues.append(("Completar período da campanha", 28, "data"))
    if objective <= 0:
        issues.append(("Informar objetivo contratado", 24, "data"))
    if latest_diary is None:
        issues.append(("Adicionar primeiro diário", 30, "update"))
    elif diary_age > stale_days:
        issues.append((f"Atualizar diário · {diary_age} dias sem registro", min(35, 18 + diary_age), "update"))
    if delivery_gap > tolerance:
        issues.append((f"Entrega {delivery_gap:.0f} p.p. abaixo do ritmo", min(50, 20 + delivery_gap), "delivery"))
    if investment_pct > 100:
        issues.append(("Investimento acima do previsto", 50, "budget"))
    elif investment_gap > tolerance:
        issues.append((f"Investimento {investment_gap:.0f} p.p. adiantado", min(42, 18 + investment_gap), "budget"))
    if days_left is not None and days_left < 0:
        issues.append((f"Prazo vencido há {abs(days_left)} dias", 55, "deadline"))
    elif days_left is not None and days_left <= 7 and delivery_pct < 90:
        issues.append((f"Encerra em {days_left} dias com {delivery_pct:.0f}% entregue", 45, "deadline"))

    if issues:
        issues.sort(key=lambda issue: issue[1], reverse=True)
        score = int(sum(issue[1] for issue in issues))
        recommendation, _, primary_issue = issues[0]
    else:
        recommendation = "Ritmo dentro do esperado"
        primary_issue = "ok"

    severity = "critical" if score >= 75 else "attention" if score >= 30 else "healthy"
    row.update(
        {
            "periodo_pct_elapsed": period_pct,
            "periodo_dias_restantes": days_left,
            "pct_objetivo": delivery_pct,
            "pct_custo_midia": investment_pct,
            "custo_midia_previsto": planned,
            "totalizador_gasto_num": spent,
            "desvio_entrega": delivery_gap,
            "desvio_investimento": investment_gap,
            "dias_sem_diario": diary_age,
            "health_score": score,
            "health_severity": severity,
            "health_issue": primary_issue,
            "health_recommendation": recommendation,
            "health_issue_count": len(issues),
        }
    )
    return row


def prioritize_active_campaigns(campaigns, **kwargs):
    projected = [project_campaign_health(row, **kwargs) for row in campaigns or []]
    return sorted(
        projected,
        key=lambda row: (
            -row["health_score"],
            row["periodo_dias_restantes"] if row["periodo_dias_restantes"] is not None else 10**6,
            normalize_text(row.get("cliente_nome")),
            normalize_text(row.get("nome_campanha")),
        ),
    )


def build_month_comparison(current=None, previous=None):
    current = dict(current or {})
    previous = dict(previous or {})
    fields = ("campanhas", "campanhas_ativas", "campanhas_atencao", "previsto", "gasto")
    return {
        field: {
            "atual": parse_number(current.get(field)),
            "anterior": parse_number(previous.get(field)),
            "delta": percentage_delta(current.get(field), previous.get(field)),
        }
        for field in fields
    }


def summarize_campaigns(campaigns):
    rows = list(campaigns or [])
    projected = [
        row if "health_score" in row else project_campaign_health(row)
        for row in rows
    ]
    active_rows = [
        row
        for row in projected
        if normalize_text(row.get("status_nome")) in ACTIVE_STATUS_NAMES
    ]
    return {
        "campanhas": len(projected),
        "campanhas_ativas": len(active_rows),
        "campanhas_atencao": sum(
            1 for row in active_rows if row.get("health_severity") != "healthy"
        ),
        "encerram_sete_dias": sum(
            1
            for row in active_rows
            if row.get("periodo_dias_restantes") is not None
            and 0 <= row["periodo_dias_restantes"] <= 7
        ),
        "previsto": round(
            sum(parse_number(row.get("custo_midia_previsto")) or parse_number(row.get("valor_plataforma")) for row in projected),
            2,
        ),
        "gasto": round(
            sum(parse_number(row.get("totalizador_gasto_num", row.get("totalizador_gasto"))) for row in projected),
            2,
        ),
    }


def build_platform_series(current_rows=None, previous_rows=None):
    current = {str(row.get("plataforma_nome") or "Sem plataforma"): parse_number(row.get("gasto")) for row in current_rows or []}
    previous = {str(row.get("plataforma_nome") or "Sem plataforma"): parse_number(row.get("gasto")) for row in previous_rows or []}
    labels = sorted(set(current) | set(previous), key=normalize_text)
    return {
        "labels": labels,
        "atual": [round(current.get(label, 0.0), 2) for label in labels],
        "anterior": [round(previous.get(label, 0.0), 2) for label in labels],
    }
