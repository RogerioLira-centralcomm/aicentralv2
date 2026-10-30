"""Breakdown financeiro da cotação em representação comercial."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .domain import IMPOSTO_COMISSAO_REP


def _fee_parceiro_fracao(cotacao: Dict[str, Any]) -> float:
    raw = cotacao.get("fee_pr") or cotacao.get("parceiro_percentual") or 0
    try:
        val = float(str(raw).replace(",", ".").replace("%", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0
    if val <= 0:
        return 0.0
    if val <= 1:
        return val
    return val / 100.0


def calcular_breakdown_representacao_linha(
    cotacao: Dict[str, Any],
    data: Dict[str, Any],
    *,
    parse_valor: Callable[[Any], float],
    derivar_investimento_de_liquido_informado: Callable,
    derivar_investimento_de_preco: Callable,
    derivar_investimento_liquido_de_bruto: Callable,
    obter_com_vendas_fracao: Callable[[Any], Optional[float]],
) -> Dict[str, Any]:
    plataforma = (data.get("plataforma") or "").strip()
    objetivo_kpi = (data.get("objetivo_kpi") or "").strip()
    valor_tabela = parse_valor(data.get("valor_unitario_tabela"))
    investimento_bruto_in = parse_valor(data.get("investimento_bruto"))
    investimento_liquido_in = parse_valor(
        data.get("investimento_liquido") or data.get("investimento_sugerido")
    )
    volume_in = parse_valor(data.get("volume_contratado"))
    if volume_in <= 0:
        volume_in = parse_valor(data.get("impressoes_estimadas"))
    fator_desconto = parse_valor(data.get("fator_desconto")) if data.get("fator_desconto") not in (None, "") else 1.0
    if fator_desconto <= 0:
        fator_desconto = 1.0

    if not plataforma:
        raise ValueError("Informe a plataforma para calcular.")
    if not objetivo_kpi:
        raise ValueError("Informe o KPI (Tipo de Compra) para calcular.")
    if valor_tabela <= 0:
        raise ValueError("Valor unitário tabela inválido.")
    if investimento_bruto_in <= 0 and investimento_liquido_in <= 0 and volume_in <= 0:
        raise ValueError("Preencha Valor Líq. ou Vol. Contratado.")

    preco_unit = round(valor_tabela * fator_desconto, 6)
    is_cpm = objetivo_kpi == "CPM"
    fee_ag_pct = parse_valor(cotacao.get("fee_ag") or cotacao.get("agencia_percentual"))
    fee_pr_pct = parse_valor(cotacao.get("fee_pr") or cotacao.get("parceiro_percentual"))
    fee_ag_frac = fee_ag_pct / 100.0 if fee_ag_pct > 1 else (fee_ag_pct if fee_ag_pct > 0 else 0.0)
    fee_pr_frac = _fee_parceiro_fracao(cotacao)

    if investimento_liquido_in > 0:
        cms = derivar_investimento_de_liquido_informado(investimento_liquido_in, fee_ag_frac)
        investimento_liquido = cms["investimento_liquido"]
        investimento_bruto = cms["investimento_bruto"]
        comissao_agencia = cms["comissao_agencia"]
        if volume_in > 0:
            volume_contratado = volume_in
            volume_efetivo = (volume_contratado / 1000.0) if is_cpm else float(volume_contratado)
        else:
            volume_efetivo = investimento_bruto / preco_unit if preco_unit else 0
            volume_contratado = round(volume_efetivo * 1000.0) if is_cpm else round(volume_efetivo)
            volume_efetivo = (volume_contratado / 1000.0) if is_cpm else float(volume_contratado)
    elif volume_in > 0:
        volume_contratado = volume_in
        volume_efetivo = (volume_contratado / 1000.0) if is_cpm else float(volume_contratado)
        cms = derivar_investimento_de_preco(volume_efetivo, preco_unit, fee_ag_frac, fee_pr_frac)
        investimento_liquido = cms["investimento_liquido"]
        investimento_bruto = cms["investimento_bruto"]
        comissao_agencia = cms["comissao_agencia"]
    else:
        investimento_bruto = investimento_bruto_in
        investimento_liquido = derivar_investimento_liquido_de_bruto(investimento_bruto, cotacao)
        comissao_agencia = round(investimento_bruto - investimento_liquido, 2)
        volume_efetivo = investimento_bruto / preco_unit if preco_unit else 0
        volume_contratado = round(volume_efetivo * 1000.0) if is_cpm else round(volume_efetivo)
        volume_efetivo = (volume_contratado / 1000.0) if is_cpm else float(volume_contratado)

    comissao_cc_base = round(investimento_bruto * fee_pr_frac, 2) if fee_pr_frac > 0 else 0.0
    com_frac = obter_com_vendas_fracao(cotacao.get("responsavel_comercial")) or 0.0
    val_impostos = round(comissao_cc_base * IMPOSTO_COMISSAO_REP, 2)
    val_com_vendas = round(comissao_cc_base * com_frac, 2)
    comissao_parceiro = comissao_cc_base
    custo_midia = round(valor_tabela * fator_desconto * volume_efetivo, 2)

    return {
        "perc_tech_fee": 0.0,
        "perc_margem_cc": 0.0,
        "perc_com_vendas": com_frac,
        "perc_pl_incentivos": 0.0,
        "perc_impostos": IMPOSTO_COMISSAO_REP,
        "val_tech_fee": 0.0,
        "val_margem_cc": 0.0,
        "val_com_vendas": val_com_vendas,
        "val_pl_incentivos": 0.0,
        "val_impostos": val_impostos,
        "valor_unitario_negociado": preco_unit,
        "valor_unitario": preco_unit,
        "volume_contratado": int(volume_contratado),
        "investimento_bruto": round(investimento_bruto, 2),
        "investimento_liquido": round(investimento_liquido, 2),
        "perc_comissao_agencia": fee_ag_pct,
        "perc_comissao_parceiro": fee_pr_pct,
        "fee_ag": fee_ag_pct,
        "fee_pr": fee_pr_frac,
        "comissao_agencia": round(comissao_agencia, 2),
        "comissao_parceiro": round(comissao_parceiro, 2),
        "custo_midia": custo_midia,
        "valor_total": round(investimento_bruto, 2),
        "fator_desconto": fator_desconto,
        "parc": fee_pr_frac,
        "perc_fee_pr": fee_pr_frac,
        "val_fee_pr": round(comissao_parceiro, 2),
        "val_comissao_parceiro": round(comissao_parceiro, 2),
        "comissao_cc_base": comissao_cc_base,
        "representacao_comercial": True,
        "opex_unit": preco_unit,
        "preco_unit": preco_unit,
        "warnings": [],
    }
