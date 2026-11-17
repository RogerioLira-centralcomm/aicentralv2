"""Rascunho da entrada do PI: os dados verificados no formato que a tela atual (``/cadu_pi/novo``) já coleta.

As chaves são as de ``_coletar_dados_pi_form()`` em ``routes.py``. A tela atual **não muda**: este rascunho é o
que a próxima tela (e, no fim, um PI pré-preenchido na tela atual) vai consumir. O que o PDF não traz fica em
``pendencias`` para o executivo decidir (tipo de PI, plataforma do catálogo, contatos, margens).
"""

from __future__ import annotations

from decimal import Decimal

from . import normalizar as n


def _d(valor):
    try:
        return Decimal(str(valor)) if valor not in (None, "") else None
    except Exception:
        return None


def _texto_regras(pi: dict) -> str:
    pag = pi.get("pagamento") or {}
    partes = []
    for rotulo, campo in (("Prazo de pagamento", "prazo"), ("Centro de custos", "centro_custos"), ("Help desk", "help_desk"),
                          ("Responsável no cliente", "responsavel_cliente"), ("Retenções", "retencoes"),
                          ("Entrega da NF", "local_entrega_nf"), ("Cobrança", "local_cobranca")):
        if n.limpo(pag.get(campo)):
            partes.append(f"{rotulo}: {n.limpo(pag[campo])}")
    if pag.get("emails_faturamento"):
        partes.append("Faturamento: " + ", ".join(pag["emails_faturamento"]))
    if pag.get("documentos_exigidos"):
        partes.append("Documentos exigidos: " + "; ".join(pag["documentos_exigidos"]))
    regras = [f"- {r}" for r in (pag.get("regras") or [])]
    return "\n".join(partes + (["Regras de faturamento do PI:"] + regras if regras else []))


def _texto_operacao(pi: dict) -> str:
    cabecalho = [f"PI {pi.get('numero_pi')}" if pi.get("numero_pi") else ""]
    for rotulo, campo in (("Projeto", "projeto"), ("Plano", "plano"), ("Planilha", "planilha"), ("Produto", "produto")):
        if n.limpo(pi.get(campo)):
            cabecalho.append(f"{rotulo}: {pi[campo]}")
    linhas = []
    for i, l in enumerate(pi.get("linhas") or [], 1):
        partes = [l.get("plataforma") or l.get("meio"), l.get("formato"), l.get("praca"), l.get("target")]
        valor = n.formatar_brl(l.get("valor_bruto")) if l.get("valor_bruto") else ""
        modelo = f"{l.get('modelo_compra')} {n.formatar_brl(l.get('preco_unitario'))}" if l.get("modelo_compra") and l.get("preco_unitario") else ""
        entrega = f"{n.formatar_int(l.get('entrega'))} {l.get('unidade') or ''}".strip() if l.get("entrega") else ""
        linhas.append(f"{i}. " + " | ".join(p for p in [*partes, modelo, entrega, valor] if p))
    return "\n".join([" · ".join(c for c in cabecalho if c)] + linhas).strip()


def montar(pi: dict, *, cliente_id=None, agencia_id=None, executivo_id=None, cotacao: dict | None = None, entrada_id=None) -> dict:
    """PI revisado + cadastro + cotação escolhida -> rascunho no formato de ``_coletar_dados_pi_form``."""
    tot = pi.get("totais") or {}
    bruto, comissao, liquido = _d(tot.get("bruto")), _d(tot.get("comissao")), _d(tot.get("liquido"))
    perc = _d(tot.get("comissao_perc"))
    if perc is None and bruto and comissao is not None:
        perc = (comissao / bruto * 100).quantize(Decimal("0.01"))
    linhas = pi.get("linhas") or []
    precos = {l.get("preco_unitario") for l in linhas if l.get("preco_unitario")}
    modelos = {(l.get("modelo_compra") or "").upper() for l in linhas if l.get("modelo_compra")}
    entrega = sum((l.get("entrega") or 0) for l in linhas)
    cot = cotacao or {}
    titulo = n.limpo(cot.get("nome_campanha")) or n.limpo(pi.get("campanha")) or (n.limpo((linhas[0] if linhas else {}).get("campanha")))

    rascunho = {
        "id_cliente": cliente_id,
        "titulo_pi": titulo,
        "codigo_pi_cc": n.limpo(pi.get("numero_pi")) or None,
        "id_pi_tipo": None,
        "tem_agencia": bool(agencia_id),
        "id_agencia": agencia_id,
        "perc_comissao_agencia": str(perc) if perc is not None else None,
        "valor_bruto": str(bruto) if bruto is not None else None,
        "valor_liquido": str(liquido) if liquido is not None else None,
        "comissao_agencia": str(comissao) if comissao is not None else None,
        "plataforma_campanha": n.limpo(cot.get("plataforma_campanha")) or None,
        "custo_base_unitario": next(iter(precos)) if len(precos) == 1 else None,
        "objetivo_contratado_pi": str(entrega) if entrega else None,
        "meta_baseada_em_cpm": bool(modelos) and all(m.startswith("CPM") for m in modelos),
        "periodo_inicio": pi.get("periodo_inicio") or None,
        "periodo_fim": pi.get("periodo_fim") or None,
        "resp_comercial": executivo_id,
        "obs_financeiro": _texto_regras(pi) or None,
        "obs_operacao": _texto_operacao(pi) or None,
        "tipo_de_contrato": n.limpo(cot.get("tipo_de_contrato")) or None,
        "cotacao_id": cot.get("id"),
    }
    pendencias = []
    for chave, rotulo, motivo in (
        ("id_cliente", "Cliente", "não achei o CNPJ no cadastro"),
        ("id_pi_tipo", "Tipo de PI", "só o executivo define"),
        ("plataforma_campanha", "Plataforma da campanha", "vem do catálogo; escolha ao seguir"),
        ("resp_comercial", "Executivo de vendas", "o cliente não tem executivo cadastrado"),
        ("periodo_inicio", "Início do período", "o PI traz só o mês"),
        ("periodo_fim", "Fim do período", "o PI traz só o mês"),
        ("cotacao_id", "Cotação", "nenhuma cotação foi selecionada"),
    ):
        if rascunho.get(chave) in (None, ""):
            pendencias.append({"campo": chave, "rotulo": rotulo, "motivo": motivo})
    pendencias.append({"campo": "margens", "rotulo": "Margem, tech fee, impostos e comissão de vendas", "motivo": "não constam no PDF; vêm da cotação ou do executivo"})
    return {"campos": rascunho, "pendencias": pendencias, "origem": {"entrada_id": entrada_id, "numero_pi": pi.get("numero_pi")}}
