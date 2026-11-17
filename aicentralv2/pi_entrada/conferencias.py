"""Conferências automáticas do PI lido (sem cotação): as contas que o próprio documento tem que fechar.

Cada conferência devolve ``{"id", "titulo", "status", "detalhe"}`` com status ``ok``, ``atencao``, ``erro`` ou ``info``.
Foram desenhadas a partir de PIs reais: soma das linhas = total, líquido = bruto − comissão,
entrega × preço = valor, e valor por extenso = valor numérico.
"""

from __future__ import annotations

from decimal import Decimal

from . import normalizar as n

CNPJ_CENTRALCOMM = "12315950000194"   # CENTRALCOMM-PUBLICIDADE ONLINE LTDA: o veículo dos PIs
TOLERANCIA_ABS = Decimal("0.05")      # arredondamentos de centavos
TOLERANCIA_REL = Decimal("0.005")     # 0,5% em entrega × preço (CPM e CPC arredondados)


def _d(valor):
    try:
        return Decimal(valor) if valor not in (None, "") else None
    except Exception:
        return None


def _brl(valor) -> str:
    return n.formatar_brl(valor)


def _item(id_, titulo, status, detalhe=""):
    return {"id": id_, "titulo": titulo, "status": status, "detalhe": detalhe}


def _perto(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= max(TOLERANCIA_ABS, abs(b) * TOLERANCIA_REL)


def valor_da_linha(linha: dict):
    """Valor esperado pela conta entrega × preço (CPM por mil, CPC por clique); None se não dá para calcular."""
    entrega, preco = _d(linha.get("entrega")), _d(linha.get("preco_unitario"))
    if entrega is None or preco is None:
        return None
    modelo = (linha.get("modelo_compra") or "").upper()
    if modelo.startswith("CPM"):
        return entrega * preco / 1000
    if modelo.startswith(("CPC", "CPV", "CPCV", "CPL", "CPA", "CPI")):
        return entrega * preco
    return None


def conferir(pi: dict, contexto: dict | None = None) -> list[dict]:
    """Conferências internas. ``contexto`` traz o que vem do cadastro: ``cliente_id``, ``agencia_id``,
    ``pi_existente`` ({"id_pi", "codigo"}) e ``texto_divergente`` (lista de campos fora do texto do PDF)."""
    contexto = contexto or {}
    saida: list[dict] = []
    tot = pi.get("totais") or {}
    bruto, comissao, liquido = _d(tot.get("bruto")), _d(tot.get("comissao")), _d(tot.get("liquido"))
    linhas = pi.get("linhas") or []

    # 1. campos essenciais
    faltam = [r for r, ok in (
        ("nº do PI", pi.get("numero_pi")), ("cliente", (pi.get("cliente") or {}).get("razao_social") or (pi.get("cliente") or {}).get("nome")),
        ("período", pi.get("periodo_texto") or pi.get("periodo_inicio")), ("total bruto", tot.get("bruto")),
    ) if not ok]
    saida.append(_item("essenciais", "Campos essenciais", "erro" if faltam else "ok",
                       ("Não encontrei: " + ", ".join(faltam)) if faltam else "Nº do PI, cliente, período e total bruto lidos."))

    # 2. soma das linhas = total bruto
    valores = [_d(l.get("valor_bruto")) for l in linhas]
    soma = sum((v for v in valores if v is not None), Decimal("0"))
    if bruto is None or not any(v is not None for v in valores):
        saida.append(_item("soma_linhas", "Soma das linhas = total bruto", "info", "Sem valores por linha para somar."))
    elif _perto(soma, bruto):
        saida.append(_item("soma_linhas", "Soma das linhas = total bruto", "ok", f"{len(linhas)} linhas somam {_brl(soma)}."))
    else:
        saida.append(_item("soma_linhas", "Soma das linhas = total bruto", "erro",
                           f"As linhas somam {_brl(soma)} e o total do PI é {_brl(bruto)} (diferença {_brl(bruto - soma)})."))

    # 3. líquido = bruto − comissão
    if None in (bruto, comissao, liquido):
        saida.append(_item("liquido", "Líquido = bruto − comissão", "info", "Comissão ou líquido não constam no PI."))
    elif _perto(bruto - comissao, liquido):
        perc = (comissao / bruto * 100).quantize(Decimal("0.1")) if bruto else Decimal("0")
        saida.append(_item("liquido", "Líquido = bruto − comissão", "ok", f"Comissão de {perc}% ({_brl(comissao)}); líquido {_brl(liquido)}."))
    else:
        saida.append(_item("liquido", "Líquido = bruto − comissão", "erro",
                           f"{_brl(bruto)} − {_brl(comissao)} dá {_brl(bruto - comissao)}, mas o líquido do PI é {_brl(liquido)}."))

    # 4. entrega × preço = valor
    fora, conferidas = [], 0
    for i, linha in enumerate(linhas, 1):
        esperado, valor = valor_da_linha(linha), _d(linha.get("valor_bruto"))
        if esperado is None or valor is None:
            continue
        conferidas += 1
        if not _perto(esperado, valor):
            fora.append(f"linha {i}: {n.formatar_int(linha.get('entrega'))} × {_brl(linha.get('preco_unitario'))} = {_brl(esperado)}, o PI diz {_brl(valor)}")
    if not conferidas:
        saida.append(_item("entrega_preco", "Entrega × preço = valor", "info", "Sem modelo de compra (CPM ou CPC) para conferir."))
    elif fora:
        saida.append(_item("entrega_preco", "Entrega × preço = valor", "atencao", "; ".join(fora[:3]) + ("…" if len(fora) > 3 else "")))
    else:
        saida.append(_item("entrega_preco", "Entrega × preço = valor", "ok", f"{conferidas} linha(s) conferem."))

    # 5. valor por extenso = valor numérico
    ext = _d(pi.get("valor_extenso_num"))
    if ext is None:
        saida.append(_item("extenso", "Valor por extenso = valor numérico", "info", "O PI não traz valor por extenso."))
    elif bruto is not None and _perto(ext, bruto):
        saida.append(_item("extenso", "Valor por extenso = valor numérico", "ok", f"Ambos dizem {_brl(bruto)}."))
    else:
        saida.append(_item("extenso", "Valor por extenso = valor numérico", "erro",
                           f"Por extenso: {_brl(ext)}; numérico: {_brl(bruto) if bruto is not None else 'não lido'}. O PI se contradiz."))

    # 6. período
    ini, fim = n.data_br(pi.get("periodo_inicio")), n.data_br(pi.get("periodo_fim"))
    emissao, mes = n.data_br(pi.get("data_emissao")), n.mes_ano(pi.get("mes_ref") or pi.get("periodo_texto"))
    problemas = []
    if ini and fim and fim < ini:
        problemas.append("o fim vem antes do início")
    if mes and ini and (ini.year, ini.month) != mes and (fim is None or (fim.year, fim.month) != mes):
        problemas.append(f"o mês de referência ({mes[1]:02d}/{mes[0]}) não bate com as datas das linhas")
    if emissao and ini and emissao > ini and (emissao - ini).days > 30:
        problemas.append("a emissão é mais de 30 dias depois do início")
    if not (ini and fim):
        saida.append(_item("periodo", "Período", "info", "Datas exatas não constam nas linhas; usei o mês de referência."))
    else:
        saida.append(_item("periodo", "Período", "atencao" if problemas else "ok",
                           ("; ".join(problemas)).capitalize() + "." if problemas else f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}."))

    # 7. CNPJ
    invalidos = [r for g, r in (("cliente", "cliente"), ("agencia", "agência"), ("veiculo", "veículo"))
                 if n.cnpj_digitos((pi.get(g) or {}).get("cnpj")) and not n.cnpj_valido((pi.get(g) or {}).get("cnpj"))]
    saida.append(_item("cnpj", "CNPJ válido", "atencao" if invalidos else "ok",
                       ("Dígito verificador inválido em: " + ", ".join(invalidos)) if invalidos else "Os CNPJs lidos são válidos."))

    # 8. veículo = Centralcomm
    cnpj_veiculo = n.cnpj_digitos((pi.get("veiculo") or {}).get("cnpj"))
    if not cnpj_veiculo:
        saida.append(_item("veiculo", "Veículo é a Centralcomm", "info", "CNPJ do veículo não lido."))
    elif cnpj_veiculo == CNPJ_CENTRALCOMM:
        saida.append(_item("veiculo", "Veículo é a Centralcomm", "ok", "CNPJ do veículo é o da Centralcomm."))
    else:
        saida.append(_item("veiculo", "Veículo é a Centralcomm", "erro", f"O veículo do PI tem CNPJ {n.cnpj_formatado(cnpj_veiculo)}, que não é o da Centralcomm."))

    # 9. cadastro: cliente, agência e número já usado
    if contexto.get("cliente_id"):
        saida.append(_item("cadastro_cliente", "Cliente no cadastro", "ok", "Cliente encontrado pelo CNPJ."))
    else:
        saida.append(_item("cadastro_cliente", "Cliente no cadastro", "atencao", "Não achei este CNPJ no cadastro de clientes."))
    if (pi.get("agencia") or {}).get("cnpj") or (pi.get("agencia") or {}).get("razao_social"):
        saida.append(_item("cadastro_agencia", "Agência no cadastro", "ok" if contexto.get("agencia_id") else "atencao",
                           "Agência encontrada pelo CNPJ." if contexto.get("agencia_id") else "Não achei esta agência no cadastro."))
    existente = contexto.get("pi_existente")
    if existente:
        saida.append(_item("duplicado", "Nº do PI já cadastrado", "atencao", f"Já existe o PI {existente.get('codigo')} (id {existente.get('id_pi')}) com este número."))
    elif pi.get("numero_pi"):
        saida.append(_item("duplicado", "Nº do PI já cadastrado", "ok", "Nenhum PI com este número."))

    # 10. texto do PDF
    divergentes = contexto.get("texto_divergente") or []
    if contexto.get("texto_conferido"):
        saida.append(_item("texto", "Campos conferem com o texto do PDF", "atencao" if divergentes else "ok",
                           ("Não achei no texto: " + ", ".join(d["rotulo"] for d in divergentes[:5])) if divergentes else "Todos os números e códigos lidos aparecem no texto do PDF."))
    return saida


def resumo(conferencias: list[dict]) -> dict:
    contagem = {"ok": 0, "atencao": 0, "erro": 0, "info": 0}
    for c in conferencias:
        contagem[c["status"]] = contagem.get(c["status"], 0) + 1
    return contagem
