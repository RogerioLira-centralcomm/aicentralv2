"""Organizador de praças do briefing: base do IBGE, apelidos, recortes, repetidas e o que não é praça (sem travar)."""

from werkzeug.datastructures import MultiDict

from aicentralv2.area_cliente import briefing
from aicentralv2.area_cliente import pracas as P


def test_base_do_ibge_tem_todos_os_municipios():
    por_nome, por_nome_uf = P._base()
    assert len(por_nome_uf) == 5571 and "cristalia|MG" in por_nome_uf and "tres ranchos|GO" in por_nome_uf


def test_nomes_viram_um_formato_so():
    casos = {
        "Belo Horizonte": "Belo Horizonte - MG", "juiz de fora": "Juiz de Fora - MG", "sao jose dos campos/sp": "São José dos Campos - SP",
        "Itajubá MG": "Itajubá - MG", "MG": "Minas Gerais (estado)", "estado de São Paulo": "São Paulo (estado)", "Nordeste": "Região Nordeste",
        "bh e região": "RM de Belo Horizonte - MG", "Grande SP": "RM de São Paulo - SP", "Campinas e região": "RM de Campinas - SP",
        "interior de SP": "São Paulo (estado) exceto São Paulo - SP", "capitais do Sul": "Capitais da Região Sul", "Brasil": "Brasil (nacional)",
    }
    for entrada, saida in casos.items():
        assert P.normalizar(entrada)["nome"] == saida, entrada


def test_excecao_escrita_de_dois_jeitos_vira_uma_praca_so():
    org = P.organizar(["Belo Horizonte", "MG - Exceto BH", "MG (Excluindo BH)", "Belo Horizonte - MG"])
    assert [p["nome"] for p in org] == ["Belo Horizonte - MG", "Minas Gerais (estado) exceto Belo Horizonte - MG"]
    assert org[1]["tipo"] == "recorte" and all(p["ok"] for p in org)


def test_texto_livre_e_separado_e_o_que_nao_e_praca_fica_para_conferir():
    org = P.organizar(["Salvador e SP; Lojas do shopping", "Bom Jesus"])
    assert [p["nome"] for p in org] == ["Salvador - BA", "São Paulo (estado)", "Lojas do shopping", "Bom Jesus"]
    assert [p["ok"] for p in org] == [True, True, False, False] and "mais de um estado" in org[3]["obs"]


def test_envio_organiza_e_avisa_o_executivo_sem_travar():
    v, erros = briefing.validar(MultiDict([("anunciante", "Marca"), ("titulo", "Verão"), ("objetivo", "Vender mais no verão"),
                                           ("pracas", "BH"), ("pracas", "MG - Exceto BH"), ("pracas", "Lojas do shopping")]))
    assert not erros and v["pracas"] == ["Belo Horizonte - MG", "Minas Gerais (estado) exceto Belo Horizonte - MG", "Lojas do shopping"]
    assert "A conferir com o cliente: Lojas do shopping" in dict(briefing.resumo(v))["Praças"]


def test_recorte_ja_organizado_nao_se_parte_ao_organizar_de_novo():
    uma = P.organizar(["MG - Exceto BH"])[0]["nome"]
    assert P.organizar([uma]) == P.organizar(["MG - Exceto BH"]) and P.organizar(["MG, exceto BH e Contagem"])[0]["nome"] == \
        "Minas Gerais (estado) exceto Belo Horizonte - MG e Contagem - MG"


def test_todo_municipio_do_ibge_volta_igual_ao_organizar_de_novo():
    import json
    nomes = json.loads((P.Path(P.__file__).resolve().parent.parent / "static" / "data" / "municipios_br.json").read_text(encoding="utf-8"))
    assert [n for n in nomes if P.normalizar(n)["nome"] != n] == []          # "Juiz de Fora - MG" não vira "exceto"


def test_brasil_todo_nao_manda_pracas_a_conferir():
    v, _ = briefing.validar(MultiDict([("anunciante", "M"), ("titulo", "Verão"), ("objetivo", "Vender mais no verão"),
                                       ("abrangencia", "nacional"), ("pracas", "praça da estação")]))
    assert v["pracas"] == [] and v["pracas_conferir"] == [] and "A conferir" not in dict(briefing.resumo(v)).get("Praças", "")
