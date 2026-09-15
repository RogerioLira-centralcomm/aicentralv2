"""Regras pequenas e testáveis da gestão de créditos do Cadu."""

MOVEMENT_LABELS = {
    "addition": "Adição",
    "withdrawal": "Retirada",
    "bonus": "Bônus",
    "usage": "Uso",
    "refund": "Estorno",
    "purchase": "Compra",
}

ADJUSTMENT_SIGNS = {"addition": 1, "bonus": 1, "withdrawal": -1, "purchase": 1}
USAGE_DELTAS = {"usage": 1, "refund": -1}


def calculate_credit_position(monthly_limit, used, adjustments=0):
    allowance = max(int(monthly_limit or 0), 0)
    consumed = max(int(used or 0), 0)
    adjustment = int(adjustments or 0)
    available = allowance + adjustment - consumed
    effective_limit = max(allowance + adjustment, 0)
    usage_percentage = round((consumed / effective_limit) * 100, 1) if effective_limit else 0
    return {
        "allowance": allowance,
        "adjustments": adjustment,
        "used": consumed,
        "available": available,
        "effective_limit": effective_limit,
        "usage_percentage": usage_percentage,
    }


def movement_effect(movement_type, amount):
    if movement_type not in MOVEMENT_LABELS:
        raise ValueError("Tipo de movimentação inválido.")
    quantity = int(amount)
    if quantity <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")
    return {
        "adjustment_delta": ADJUSTMENT_SIGNS.get(movement_type, 0) * quantity,
        "usage_delta": USAGE_DELTAS.get(movement_type, 0) * quantity,
    }


def build_credit_recommendation(position, days_elapsed=1, days_in_month=30, plan_options=None):
    """Gera recomendação comercial determinística e mostra seus motivos."""
    used = position["used"]
    effective_limit = position["effective_limit"]
    available = position["available"]
    elapsed = max(int(days_elapsed or 1), 1)
    period_days = max(int(days_in_month or 30), elapsed)
    projected = round((used / elapsed) * period_days) if used else 0
    projected_percentage = round((projected / effective_limit) * 100, 1) if effective_limit else 0
    recommended_plan = None
    for option in sorted(plan_options or [], key=lambda item: int(item.get("limit") or 0)):
        if int(option.get("limit") or 0) >= projected * 1.15 and int(option.get("limit") or 0) > effective_limit:
            recommended_plan = option
            break

    if available <= 0:
        level, title = "critical", "Saldo esgotado"
        action = "Liberar um pacote agora e revisar o plano antes do próximo ciclo."
    elif projected_percentage >= 100:
        level, title = "attention", "Consumo acima do plano"
        action = "Oferecer pacote para este mês e um plano maior para a renovação."
    elif projected_percentage >= 80:
        level, title = "opportunity", "Oportunidade de expansão"
        action = "Conversar sobre pacote preventivo ou upgrade de plano."
    elif projected_percentage <= 30 and elapsed >= 10:
        level, title = "stable", "Uso abaixo da franquia"
        action = "Manter o plano e acompanhar a ativação do cliente."
    else:
        level, title = "stable", "Consumo dentro do esperado"
        action = "Manter o plano atual e acompanhar o ritmo até o fechamento do mês."
    return {
        "level": level,
        "title": title,
        "action": action,
        "projected": projected,
        "projected_percentage": projected_percentage,
        "recommended_plan": recommended_plan,
    }
