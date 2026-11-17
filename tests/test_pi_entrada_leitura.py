"""Entrada de PI: normalizadores, esquema, leitor de PDF e conferências.

Os números espelham PIs reais (CPM, CPC, comissão de 20%, valor por extenso divergente), mas nomes e CNPJs
são inventados: PDFs de clientes não entram no repositório.
"""

from decimal import Decimal

import pytest

from aicentralv2.pi_entrada import conferencias, esquema, leitor
from aicentralv2.pi_entrada import normalizar as n

CNPJ_CLIENTE = "11.222.333/0001-81"      # CNPJ de teste com dígito verificador válido
CNPJ_AGENCIA = "11.444.777/0001-61"
CNPJ_CENTRALCOMM = "12.315.950/0001-94"


def folha(valor, conf=0.95, pagina=1):
    return {"valor": valor, "confianca": conf, "pagina": pagina}


def resposta_modelo(*, bruto="R$ 10.000,00", comissao="R$ 2.000,00", liquido="R$ 8.000,00", extenso=None,
                    valor_linha="R$ 10.000,00", entrega="163.399", preco="R$ 61,20", modelo="CPM"):
    """O que o modelo devolveria para um PI de uma linha (áudio programático em CPM)."""
    return {
        "documento": {"numero_pi": folha("86761"), "data_emissao": folha("28/10/2026"), "periodo": folha("NOVEMBRO/2026"),
                      "campanha": folha("INSTITUCIONAL SEGUNDO SEMESTRE"), "valor_extenso": folha(extenso)},
        "agencia": {"nome": folha("AGENCIA EXEMPLO"), "razao_social": folha("AGENCIA EXEMPLO LTDA"), "cnpj": folha(CNPJ_AGENCIA)},
        "cliente": {"nome": folha("CLIENTE EXEMPLO"), "razao_social": folha("CLIENTE EXEMPLO S.A."), "cnpj": folha(CNPJ_CLIENTE)},
        "veiculo": {"nome": folha("CENTRALCOMM"), "razao_social": folha("CENTRALCOMM-PUBLICIDADE ONLINE LTDA"), "cnpj": folha(CNPJ_CENTRALCOMM)},
        "linhas": [{"campanha": "Institucional", "meio": "Programática áudio", "plataforma": "Amazon Música", "formato": "Jingle",
                    "modelo_compra": modelo, "praca": "MG, PA, Salvador e SP", "target": "18+ alta renda",
                    "preco_unitario": preco, "entrega": entrega, "unidade": "impressões", "valor_bruto": valor_linha,
                    "periodo": "01/11 a 30/11", "pagina": 1}],
        "totais": {"bruto": folha(bruto), "comissao": folha(comissao), "liquido": folha(liquido)},
        "pagamento": {"prazo": folha(None), "regras": ["Nota fiscal pelo valor líquido."], "emails_faturamento": []},
        "observacoes": "",
    }


# ---------- normalizadores ----------

def test_dinheiro_e_numeros_no_formato_brasileiro():
    assert n.dinheiro("R$ 10.000,00") == Decimal("10000.00")
    assert n.dinheiro("59.393,20") == Decimal("59393.20")
    assert n.decimal_br("8,16") == Decimal("8.16")
    assert n.decimal_br("1.250") == Decimal("1250")             # ponto de milhar, não decimal
    assert n.inteiro_br("1.566.580 impressões") == 1566580
    assert n.decimal_br("sem número") is None and n.decimal_br(None) is None
    assert n.formatar_brl("42000") == "R$ 42.000,00" and n.formatar_int(1566580) == "1.566.580"


def test_datas_periodos_e_meses():
    assert str(n.data_br("28/10/2026")) == "2026-10-28" and n.data_br("32/13/2026") is None
    assert n.mes_ano("NOVEMBRO/2026") == (2026, 11) and n.mes_ano("Agosto/2026") == (2026, 8)
    assert [str(d) for d in n.periodo_do_texto("26/10 A 26/11/2026")] == ["2026-10-26", "2026-11-26"]
    assert [str(d) for d in n.periodo_do_texto("PERÍODO: 01/11 a 30/11", 2026)] == ["2026-11-01", "2026-11-30"]
    assert n.periodo_do_texto("sem datas") == (None, None)


def test_cnpj_e_numero_de_pi():
    assert n.cnpj_valido(CNPJ_CLIENTE) and n.cnpj_valido(CNPJ_CENTRALCOMM) and not n.cnpj_valido("11.222.333/0001-82")
    assert n.cnpj_formatado("11222333000181") == CNPJ_CLIENTE
    assert n.chave_numero_pi("036826") == n.chave_numero_pi("36826") == "36826"


def test_valor_por_extenso():
    assert n.extenso_para_decimal("quarenta e dois mil reais") == Decimal("42000")
    assert n.extenso_para_decimal("cento e vinte e três mil e quatrocentos reais e cinquenta centavos") == Decimal("123400.50")
    assert n.extenso_para_decimal("um milhão duzentos mil") == Decimal("1200000")
    assert n.extenso_para_decimal("texto qualquer") is None
    assert n.extenso_no_texto("R$59.393,20 [quarenta e dois mil reais] - bruto: mídia") == Decimal("42000")


# ---------- esquema ----------

def test_normalizar_extracao_tipa_valores_e_guarda_confianca():
    pi = esquema.normalizar_extracao(resposta_modelo(extenso="dez mil reais"))
    assert pi["numero_pi"] == "86761" and pi["data_emissao"] == "2026-10-28" and pi["mes_ref"] == "2026-11"
    assert pi["totais"] == {"bruto": "10000.00", "comissao": "2000.00", "comissao_perc": "", "liquido": "8000.00"}
    assert pi["cliente"]["cnpj"] == CNPJ_CLIENTE and pi["valor_extenso_num"] == "10000"
    linha = pi["linhas"][0]
    assert linha["entrega"] == 163399 and linha["preco_unitario"] == "61.20" and linha["modelo_compra"] == "CPM"
    assert (pi["periodo_inicio"], pi["periodo_fim"]) == ("2026-11-01", "2026-11-30")
    assert pi["confianca"]["numero_pi"] == 0.95 and pi["paginas"]["numero_pi"] == 1 and 0 < pi["confianca_geral"] <= 1


def test_extrair_json_tolera_cerca_de_codigo_e_texto_em_volta():
    assert esquema.extrair_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert esquema.extrair_json('Aqui está: {"a": {"b": 2}} fim') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        esquema.extrair_json("sem json")


# ---------- conferências ----------

def status_de(conferencias_, id_):
    return next(c["status"] for c in conferencias_ if c["id"] == id_)


def test_pi_que_fecha_as_contas_passa_nas_conferencias():
    pi = esquema.normalizar_extracao(resposta_modelo(extenso="dez mil reais"))
    itens = conferencias.conferir(pi, {"cliente_id": 9, "agencia_id": 80})
    assert [c["status"] for c in itens if c["id"] in ("essenciais", "soma_linhas", "liquido", "entrega_preco", "extenso", "veiculo")] == ["ok"] * 6
    assert conferencias.resumo(itens)["erro"] == 0


def test_valor_por_extenso_que_contradiz_o_total_e_erro():
    """O caso real: R$ 59.393,20 ao lado de "quarenta e dois mil reais"."""
    pi = esquema.normalizar_extracao(resposta_modelo(
        bruto="R$ 59.393,20", comissao="R$ 11.878,64", liquido="R$ 47.514,56", valor_linha="R$ 59.393,20",
        entrega="148.483", preco="R$ 0,40", modelo="CPC", extenso="quarenta e dois mil reais"))
    itens = conferencias.conferir(pi)
    assert status_de(itens, "extenso") == "erro" and "42.000,00" in next(c for c in itens if c["id"] == "extenso")["detalhe"]
    assert status_de(itens, "entrega_preco") == "ok"          # 148.483 cliques × R$ 0,40 = R$ 59.393,20
    assert status_de(itens, "liquido") == "ok"


def test_soma_das_linhas_liquido_e_veiculo_errados_sao_apontados():
    pi = esquema.normalizar_extracao(resposta_modelo(valor_linha="R$ 9.000,00", liquido="R$ 7.000,00"))
    pi["veiculo"]["cnpj"] = CNPJ_CLIENTE
    itens = conferencias.conferir(pi)
    assert status_de(itens, "soma_linhas") == "erro" and status_de(itens, "liquido") == "erro" and status_de(itens, "veiculo") == "erro"


def test_cadastro_e_numero_duplicado():
    pi = esquema.normalizar_extracao(resposta_modelo())
    sem = conferencias.conferir(pi, {})
    com = conferencias.conferir(pi, {"cliente_id": 9, "agencia_id": 80, "pi_existente": {"id_pi": 180, "codigo": "86761"}})
    assert status_de(sem, "cadastro_cliente") == "atencao" and status_de(com, "cadastro_cliente") == "ok"
    assert status_de(com, "duplicado") == "atencao" and "180" in next(c for c in com if c["id"] == "duplicado")["detalhe"]


# ---------- leitor ----------

def pdf_de_teste(paginas: list[str]) -> bytes:
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    for texto in paginas:
        pagina = doc.new_page()
        pagina.insert_textbox(fitz.Rect(30, 30, 560, 800), texto, fontsize=9)
    return doc.tobytes()


CABECALHO = "PEDIDO DE INSERCAO AGENCIA EXEMPLO LTDA CNPJ 11.444.777/0001-61 PI 86761 CLIENTE EXEMPLO"


def test_limpar_paginas_tira_cabecalho_repetido_e_calendario():
    paginas = [f"{CABECALHO}\nD\nS\n01\nLinha da campanha A", f"{CABECALHO}\nT\n02\nContinuação da campanha"]
    limpas = leitor.limpar_paginas(paginas)
    assert CABECALHO in limpas[0] and CABECALHO not in limpas[1]
    assert "Linha da campanha A" in limpas[0] and "Continuação da campanha" in limpas[1]
    assert "\nD\n" not in "\n" + limpas[0] + "\n" and "01" not in limpas[0].split()


def test_leitor_usa_so_o_texto_quando_o_pdf_tem_camada_de_texto():
    chamadas = []

    def modelo_falso(mensagens, **kw):
        chamadas.append((mensagens, kw))
        import json
        return {"message": {"content": json.dumps(resposta_modelo(extenso="dez mil reais"))}, "model": "modelo-teste",
                "usage": {"prompt_tokens": 1200, "completion_tokens": 300}}

    texto = CABECALHO + "\n" + ("Campanha institucional programática áudio CPM R$ 61,20 impressões 163.399 valor bruto R$ 10.000,00 " * 6)
    leitura = leitor.ler(pdf_de_teste([texto, texto]), "pi.pdf", chamar=modelo_falso)
    assert leitura.metodo == "texto" and leitura.paginas == 2 and leitura.modelo == "modelo-teste"
    assert (leitura.tokens_entrada, leitura.tokens_saida) == (1200, 300)
    mensagens, kw = chamadas[0]
    assert kw["plugins"] is None and kw["temperature"] == 0 and kw["response_format"] == {"type": "json_object"}
    assert all(p["type"] == "text" for p in mensagens[1]["content"])          # nenhum arquivo foi enviado
    assert leitura.pi["numero_pi"] == "86761" and leitura.pi["totais"]["bruto"] == "10000.00"


def test_leitor_cai_no_ocr_quando_o_pdf_e_so_imagem():
    chamadas = []

    def modelo_falso(mensagens, **kw):
        import json
        chamadas.append((mensagens, kw))
        return {"message": {"content": json.dumps(resposta_modelo())}, "model": "m", "usage": {}}

    leitura = leitor.ler(pdf_de_teste([""]), "escaneado.pdf", chamar=modelo_falso)
    mensagens, kw = chamadas[0]
    assert leitura.metodo == "ocr" and kw["plugins"] == [{"id": "file-parser", "pdf": {"engine": "mistral-ocr"}}]
    assert any(p["type"] == "file" and p["file"]["file_data"].startswith("data:application/pdf;base64,") for p in mensagens[1]["content"])
    assert any("OCR" in a for a in leitura.avisos)


def test_leitor_tenta_de_novo_com_json_invalido_e_falha_com_mensagem_clara():
    respostas = iter(["isso não é json", '{"documento": {"numero_pi": "7"}, "linhas": [{"praca": "BH", "valor_bruto": "R$ 1,00"}]}'])

    def modelo_falso(mensagens, **kw):
        return {"message": {"content": next(respostas)}, "model": "m", "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    texto = "x" * 400
    leitura = leitor.ler(pdf_de_teste([texto]), chamar=modelo_falso)
    assert leitura.pi["numero_pi"] == "7" and leitura.tokens_entrada == 20

    with pytest.raises(leitor.LeituraErro):
        leitor.ler(b"nao e pdf")
    with pytest.raises(leitor.LeituraErro):
        leitor.ler(pdf_de_teste([texto]), chamar=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fora do ar")))
    with pytest.raises(leitor.LeituraErro):                                     # modelo devolveu algo sem PI
        leitor.ler(pdf_de_teste([texto]), chamar=lambda *a, **k: {"message": {"content": "{}"}, "model": "m"})


def test_conferir_contra_texto_acha_o_que_o_modelo_inventou():
    texto = "PI 86761 CNPJ 11.222.333/0001-81 TOTAL BRUTO R$ 10.000,00 COMISSÃO R$ 2.000,00 LIQUIDO R$ 8.000,00"
    pi = esquema.normalizar_extracao(resposta_modelo(valor_linha="R$ 10.000,00", entrega="163.399", preco="R$ 61,20"))
    campos = {d["campo"] for d in leitor.conferir_contra_texto(pi, texto)}
    assert "linhas.1.entrega" in campos and "linhas.1.preco_unitario" in campos      # não estão neste texto curto
    assert "totais.bruto" not in campos and "numero_pi" not in campos and "cliente.cnpj" not in campos
    assert leitor.conferir_contra_texto(pi, "") == []                                  # sem texto, não confere


# ---------- oportunidades de cadastro ----------

from aicentralv2.pi_entrada import oportunidades as oport                       # noqa: E402


def pi_com_cadastro():
    pi = esquema.normalizar_extracao(resposta_modelo())
    pi["cliente"].update({"endereco": "AV DO CONTORNO, 4265 - SAO LUCAS", "cep": "30110-021", "municipio": "BELO HORIZONTE", "uf": "MG",
                          "inscricao_estadual": "ISENTA", "inscricao_municipal": "0397.846/001-9", "email": "fin@cliente.exemplo"})
    pi["pagamento"]["emails_faturamento"] = ["faturamento@agencia.exemplo"]
    pi["pagamento"]["prazo"] = "60 dias após o envio da nota fiscal"
    return pi


def test_cliente_que_nao_esta_no_cadastro_vira_oportunidade_de_cadastrar():
    itens = oport.oportunidades(pi_com_cadastro(), None, {"id_cliente": 80, "razao_social": "AGENCIA EXEMPLO LTDA"})
    novo = next(i for i in itens if i["tipo"] == "novo")
    assert novo["entidade"] == "cliente" and any(d["campo"] == "cnpj" for d in novo["dados"]) and "CLIENTE EXEMPLO" in novo["sugestao"]
    assert oport.resumo(itens)["novo"] == 1


def test_campo_vazio_e_campo_diferente_no_cadastro():
    cadastro = {"id_cliente": 9, "razao_social": "CLIENTE EXEMPLO", "endereco": "", "logradouro": "RUA OUTRA", "numero": "10", "bairro": "CENTRO",
                "cep": "30110021", "cidade": "Belo Horizonte", "estado": "MG", "inscricao_estadual": "", "inscricao_municipal": "0397846/001-9"}
    itens = oport.oportunidades(pi_com_cadastro(), cadastro, {"id_cliente": 80, "razao_social": "AGENCIA EXEMPLO LTDA"},
                                {"cliente": {"fin@cliente.exemplo"}}, {"cliente": ""})
    por_campo = {(i["entidade"], i["campo"]): i for i in itens}
    assert por_campo[("cliente", "inscricao_estadual")]["tipo"] == "preencher"          # vazio no cadastro, ISENTA no PI
    assert por_campo[("cliente", "endereco")]["tipo"] == "revisar"                      # endereço bem diferente
    assert ("cliente", "cep") not in por_campo and ("cliente", "municipio") not in por_campo      # iguais, sem barulho
    assert por_campo[("cliente", "email")]["tipo"] == "preencher" or ("cliente", "email") not in por_campo
    assert por_campo[("cliente", "contato")]["valor_pi"] == "faturamento@agencia.exemplo"
    assert por_campo[("cliente", "regras")]["tipo"] == "regras"


def test_razao_social_truncada_no_pi_nao_gera_ruido():
    pi = pi_com_cadastro()
    pi["cliente"]["razao_social"] = "SICOOB CREDICOM - COOPERATIVA DE ECONOMIA E CREDIT"
    cadastro = {"id_cliente": 9, "razao_social": "SICOOB CREDICOM - COOPERATIVA DE ECONOMIA E CREDITO"}
    itens = oport.oportunidades(pi, cadastro, None)
    assert not [i for i in itens if i["campo"] == "razao_social"]


# ---------- comparação com a cotação e rascunho ----------

from aicentralv2.pi_entrada import cotacao as cmp, rascunho                          # noqa: E402


def status_de_linha(linhas, chave):
    return next(l["status"] for l in linhas if l["chave"] == chave)


def cotacao_de(nome, bruto, liquido, volume, preco, kpi, plataforma="Amazon Música"):
    return {"id": 228, "nome_campanha": nome, "periodo_inicio": "2026-11-01", "periodo_fim": "2026-11-30", "status": "Aprovada",
            "valor_total_proposta": bruto, "plataforma_campanha": None, "tipo_de_contrato": "operacao_propria",
            "linhas": [{"plataforma": plataforma, "formatos": "Jingle", "objetivo_kpi": kpi, "praca": "MG, PA, Salvador e SP", "volume_contratado": volume,
                        "valor_unitario_negociado": preco, "investimento_bruto": bruto, "investimento_liquido": liquido}]}


def test_pi_quase_igual_a_cotacao_fica_dentro_da_tolerancia():
    """Caso real: o PI diz 163.399 impressões a R$ 61,20 e a cotação 163.425 a R$ 61,1875 (mesmos R$ 10.000)."""
    pi = esquema.normalizar_extracao(resposta_modelo())
    linhas = cmp.comparar(pi, cotacao_de("INSTITUCIONAL SEGUNDO SEMESTRE", 10000, 8000, 163425, 61.1875, "CPM"))
    assert status_de_linha(linhas, "bruto") == "igual" and status_de_linha(linhas, "liquido") == "igual"
    assert status_de_linha(linhas, "entrega") == "proximo" and status_de_linha(linhas, "preco") == "proximo"
    assert status_de_linha(linhas, "praca") == "igual" and status_de_linha(linhas, "modelo_compra") == "igual"
    resumo = cmp.resumo(linhas)
    assert resumo["diferente"] == 0 and resumo["conferem"] == resumo["comparaveis"]


def test_pi_com_valor_maior_que_a_cotacao_e_marcado_como_diferente():
    """Caso real: PI de R$ 59.393,20 (148.483 cliques a R$ 0,40) contra cotação aprovada de R$ 42.000 (105.822 cliques a R$ 0,3969)."""
    pi = esquema.normalizar_extracao(resposta_modelo(bruto="R$ 59.393,20", comissao="R$ 11.878,64", liquido="R$ 47.514,56",
                                                     valor_linha="R$ 59.393,20", entrega="148.483", preco="R$ 0,40", modelo="CPC"))
    linhas = cmp.comparar(pi, cotacao_de("INSTITUCIONAL SEGUNDO SEMESTRE", 42000, 33600, 105822, 0.3969, "CPC"))
    assert status_de_linha(linhas, "bruto") == "diferente" and status_de_linha(linhas, "liquido") == "diferente"
    assert status_de_linha(linhas, "entrega") == "diferente" and status_de_linha(linhas, "preco") == "proximo"
    assert cmp.resumo(linhas)["diferente"] >= 3


def test_sem_cotacao_so_mostra_o_pi_e_sugere_a_melhor():
    pi = esquema.normalizar_extracao(resposta_modelo())
    linhas = cmp.comparar(pi, None)
    assert {l["status"] for l in linhas} == {"sem_cotacao"} and cmp.resumo(linhas)["comparaveis"] == 0
    certa = cotacao_de("INSTITUCIONAL SEGUNDO SEMESTRE", 10000, 8000, 163425, 61.1875, "CPM")
    outra = {**cotacao_de("Outra campanha", 55000, 40000, 1, 1, "CPC"), "id": 5, "periodo_inicio": "2026-03-01", "periodo_fim": "2026-03-31"}
    ranking = cmp.sugerir(pi, [outra, certa])
    assert ranking[0]["id"] == 228 and ranking[0]["pontuacao"] > 0.9 and ranking[1]["pontuacao"] < 0.5


def test_rascunho_segue_as_chaves_da_tela_atual():
    pi = esquema.normalizar_extracao(resposta_modelo(extenso="dez mil reais"))
    pi["pagamento"].update({"prazo": "60 dias", "centro_custos": "CC-1", "regras": ["NF pelo valor líquido"]})
    r = rascunho.montar(pi, cliente_id=9, agencia_id=80, executivo_id=7, cotacao=cotacao_de("Campanha da cotação", 10000, 8000, 163425, 61.1875, "CPM"), entrada_id=1)
    c = r["campos"]
    assert c["codigo_pi_cc"] == "86761" and c["id_cliente"] == 9 and c["id_agencia"] == 80 and c["tem_agencia"] is True and c["resp_comercial"] == 7
    assert c["valor_bruto"] == "10000.00" and c["valor_liquido"] == "8000.00" and c["comissao_agencia"] == "2000.00" and c["perc_comissao_agencia"] == "20.00"
    assert c["titulo_pi"] == "Campanha da cotação" and c["cotacao_id"] == 228 and c["meta_baseada_em_cpm"] is True
    assert c["periodo_inicio"] == "2026-11-01" and c["periodo_fim"] == "2026-11-30" and c["objetivo_contratado_pi"] == "163399"
    assert "Prazo de pagamento: 60 dias" in c["obs_financeiro"] and "NF pelo valor líquido" in c["obs_financeiro"]
    assert "Amazon Música" in c["obs_operacao"] and "MG, PA, Salvador e SP" in c["obs_operacao"]
    pendentes = {p["campo"] for p in r["pendencias"]}
    assert "id_pi_tipo" in pendentes and "plataforma_campanha" in pendentes and "margens" in pendentes and "id_cliente" not in pendentes
    sem = rascunho.montar(pi, cliente_id=None, agencia_id=None, executivo_id=None)
    assert {"id_cliente", "resp_comercial", "cotacao_id"} <= {p["campo"] for p in sem["pendencias"]}


# ---------- correções da revisão ----------

def test_limpar_paginas_nao_apaga_linhas_do_corpo_que_se_repetem():
    """PI de 3 páginas só de segmentações: depois do calendário, 'TARGET', 'CPM' e os asteriscos se repetem em todas e ficam."""
    calendario = "COLOCAÇÃO\nNOVEMBRO/2026\nP\nE\nÇ\nA\n01\nD\n02\nS\nTOT\nINS\nCUSTO\nUNITARIO\n%\nDESCONTO\nCUSTO\n(TOTAL R$)"
    corpo = "TARGET: AB AS 30+\nCPM CONTRATADO: R$ 8,16\n********************"
    paginas = [f"{CABECALHO}\n{calendario}\n{corpo}\nBotumirim", f"{CABECALHO}\n{calendario}\n{corpo}\nCristália", f"{CABECALHO}\n{calendario}\n{corpo}\nBetim"]
    limpas = leitor.limpar_paginas(paginas)
    assert all(corpo in p for p in limpas)                                     # nenhuma linha real foi perdida
    assert CABECALHO in limpas[0] and not any(CABECALHO in p for p in limpas[1:])
    assert "COLOCAÇÃO" not in limpas[1] and "(TOTAL R$)" not in limpas[2]      # calendário e colunas saem
    assert "Cristália" in limpas[1] and "Betim" in limpas[2]


def test_soma_e_liquido_fecham_em_centavos_nao_em_meio_por_cento():
    pi = esquema.normalizar_extracao(resposta_modelo(bruto="R$ 19.000,00", comissao="R$ 3.800,00", liquido="R$ 15.290,00", valor_linha="R$ 18.910,00"))
    itens = conferencias.conferir(pi)
    assert status_de(itens, "soma_linhas") == "erro" and status_de(itens, "liquido") == "erro"       # R$ 90 de diferença não passa mais


def test_confianca_geral_ignora_campos_vazios():
    bruto = resposta_modelo()
    bruto["documento"]["projeto"] = {"valor": None, "confianca": 0, "pagina": None}
    pi = esquema.normalizar_extracao(bruto)
    assert "projeto" not in pi["confianca"] and pi["confianca_geral"] > 0.9
