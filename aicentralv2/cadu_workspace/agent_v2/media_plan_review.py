"""Deterministic arithmetic checks for a saved media plan.

These checks cover only fields present in the canonical Planner record. They
do not judge channel suitability, inventory, quoted prices, or likely results.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .investment_scenarios import _amount


def _decimal(value) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def review_media_plan(plan: dict) -> dict:
    """Return explicit findings without changing the plan or inventing totals."""
    items = plan.get("items") if isinstance(plan.get("items"), list) else []
    allocations = plan.get("allocations") if isinstance(plan.get("allocations"), list) else []
    selected_channels = {str(item.get("resource_id")) for item in items
                         if isinstance(item, dict) and item.get("kind") == "canais" and item.get("resource_id") is not None}
    findings = []

    def issue(code: str, severity: str, evidence: str, correction: str) -> None:
        findings.append({"code": code, "severity": severity, "evidence": evidence,
                         "correction": correction})

    weights, investments = [], []
    seen_resources = set()
    if allocations and not selected_channels:
        issue("no_selected_channels", "blocking", "Há distribuição, mas nenhum canal selecionado no plano.",
              "Selecione os canais correspondentes às alocações.")
    for index, row in enumerate(allocations, 1):
        if not isinstance(row, dict):
            issue("invalid_allocation", "blocking", f"Alocação {index} ilegível.",
                  "Revise a linha de distribuição no Planner.")
            continue
        resource_id = str(row.get("resource_id") or "")
        if resource_id in seen_resources:
            issue("duplicate_channel", "blocking", f"Canal {resource_id} aparece em mais de uma alocação.",
                  "Consolide as linhas repetidas antes de comparar valores.")
        seen_resources.add(resource_id)
        weight = _decimal(row.get("weight"))
        investment = _decimal(row.get("investment"))
        if weight is None or investment is None or weight < 0 or investment < 0:
            issue("invalid_allocation", "blocking", f"Alocação {index} tem peso ou investimento inválido.",
                  "Corrija os valores dessa linha no Planner.")
            continue
        weights.append(weight)
        investments.append(investment)
        if selected_channels and resource_id not in selected_channels:
            issue("unselected_channel", "blocking", f"Alocação {index} usa canal {resource_id} fora dos canais selecionados.",
                  "Selecione o canal ou remova sua alocação.")

    total_weight = sum(weights, Decimal("0"))
    total_investment = sum(investments, Decimal("0"))
    if allocations and len(weights) == len(allocations) and total_weight != Decimal("100"):
        issue("weight_total", "blocking", f"Os pesos somam {total_weight}%.",
              "Ajuste os pesos para somar 100%.")

    briefing = plan.get("briefing") if isinstance(plan.get("briefing"), dict) else {}
    budget_text = str(briefing.get("budget") or "")
    budget = _amount(budget_text)
    if budget is not None and allocations and len(investments) == len(allocations) and total_investment != budget:
        issue("budget_total", "blocking", f"Investimento alocado: R$ {total_investment}; verba no briefing: R$ {budget}.",
              "Ajuste a distribuição ou atualize a verba do briefing.")
    if (allocations and len(weights) == len(allocations) and total_weight == Decimal("100")
            and total_investment > 0):
        for index, (weight, investment) in enumerate(zip(weights, investments), 1):
            expected = total_investment * weight / Decimal("100")
            if abs(investment - expected) > Decimal("0.01"):
                issue("allocation_mismatch", "warning",
                      f"Alocação {index}: {weight}% e R$ {investment}; proporcional ao total seria R$ {expected.quantize(Decimal('0.01'))}.",
                      "Confira se percentual e valor representam a mesma distribuição.")

    if not allocations:
        issue("no_allocations", "missing", "O plano não contém distribuição de investimento.",
              "Defina canais e distribuição antes de auditar as contas.")
    return {
        "status": "issues" if any(item["severity"] in {"blocking", "warning"} for item in findings)
                  else "insufficient_data" if not allocations else "clear_within_checked_fields",
        "checked_fields": ["selected_channels", "allocation_weights", "allocation_investments", "briefing_budget"],
        "budget_brl": str(budget) if budget is not None else None,
        "total_weight_percent": str(total_weight) if allocations else None,
        "total_investment_brl": str(total_investment) if allocations else None,
        "findings": findings,
        "scope_note": "Revisão aritmética dos dados do Planner; não avalia adequação estratégica, cotação ou desempenho previsto.",
    }
