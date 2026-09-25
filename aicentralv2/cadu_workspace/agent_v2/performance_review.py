"""Deterministic normalization of campaign metrics pasted into the chat."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .campaign_metrics import supplied_metrics


_ALIASES = {
    "clique": "cliques", "cliques": "cliques", "impressões": "impressões", "impressoes": "impressões",
    "conversão": "conversões", "conversões": "conversões", "conversao": "conversões", "conversoes": "conversões",
    "venda": "vendas", "vendas": "vendas", "lead": "leads", "leads": "leads",
    "orcamento": "orçamento", "orçamento": "orçamento",
}


def _number(raw: str) -> Decimal | None:
    value = str(raw or "").replace(" ", "")
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif value.count(".") and len(value.rsplit(".", 1)[-1]) == 3:
        value = value.replace(".", "")
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


def review_supplied_metrics(message: str) -> dict:
    """Calculate ratios only for unique metric labels; never infer periods."""
    entries = []
    by_name: dict[str, list[Decimal]] = {}
    for item in supplied_metrics(message):
        name = _ALIASES.get(item["name"], item["name"])
        value = _number(item["value"])
        if value is None:
            continue
        entries.append({"name": name, "value": str(value), "unit": item["unit"], "source": "user_message"})
        by_name.setdefault(name, []).append(value)
    unique = {name: values[0] for name, values in by_name.items() if len(values) == 1}
    repeated = sorted(name for name, values in by_name.items() if len(values) > 1)
    derived = []

    def ratio(name: str, numerator: str, denominator: str, factor: str, unit: str) -> None:
        top, bottom = unique.get(numerator), unique.get(denominator)
        if top is None or bottom is None or bottom == 0:
            return
        value = (top / bottom * Decimal(factor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        derived.append({"name": name, "value": str(value), "unit": unit,
                        "formula": f"{numerator} / {denominator} × {factor}",
                        "input_metrics": [numerator, denominator],
                        "condition": "Válido somente se as métricas pertencem ao mesmo período e escopo."})

    ratio("CTR calculado", "cliques", "impressões", "100", "%")
    ratio("CPC calculado", "investimento", "cliques", "1", "BRL")
    ratio("CPM calculado", "investimento", "impressões", "1000", "BRL")
    ratio("ROAS calculado", "receita", "investimento", "1", "x")
    return {
        "status": "ambiguous" if repeated else "partial" if entries else "missing_metrics",
        "metrics": entries,
        "derived_metrics": derived,
        "repeated_metrics": repeated,
        "period_verified": False,
        "scope_note": "Valores transcritos da mensagem do usuário. Período, canal, atribuição e unidade não foram verificados; cálculos condicionais não são dados da plataforma nem comparação temporal.",
    }
