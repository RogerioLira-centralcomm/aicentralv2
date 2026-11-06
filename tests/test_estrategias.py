"""Estratégias de mídia: divisão de verba por faixa, validação e catálogo-semente (sem banco)."""

import pytest

from aicentralv2.estrategias import catalogo, repositorio, semente

SLUGS = set(catalogo.CANAIS_EXTRAS) | {
    "youtube", "tiktok", "linkedin", "kwai", "twitch", "spotify", "deezer", "amazon-music", "podcast-ads", "netflix",
    "globoplay", "prime-video", "disney-plus", "hbo-max", "paramount-plus", "samsung-tv-plus", "eletromidia", "uber",
    "99", "ifood", "g1-globo", "uol", "r7", "cnn-brasil", "sbt", "infomoney", "ge-globo-esporte", "tudogostoso",
    "techtudo", "experian-portal", "google-dv360", "logan", "experian-dmp", "amazon-ads", "interativos",
}


def test_divisao_soma_a_verba_e_tira_canal_abaixo_do_minimo():
    canais = [{"slug": "google-search", "peso": 40, "essencial": True}, {"slug": "meta-ads", "peso": 35, "essencial": True},
              {"slug": "youtube", "peso": 15}, {"slug": "google-demand-gen", "peso": 10}, {"slug": "site", "peso": 0}]
    d = catalogo.divisao(canais, 10_000)
    assert sum(l["valor"] for l in d["linhas"]) == 10_000
    assert {l["slug"] for l in d["linhas"]} == {"google-search", "meta-ads"}
    assert d["fora"] == ["youtube", "google-demand-gen"]
    grande = catalogo.divisao(canais, 150_000)
    assert len(grande["linhas"]) == 4 and sum(l["valor"] for l in grande["linhas"]) == 150_000
    assert all(l["valor"] % catalogo.ARREDONDA == 0 for l in grande["linhas"][1:])


def test_essencial_fica_mesmo_abaixo_do_minimo():
    canais = [{"slug": "netflix", "peso": 50, "essencial": True}, {"slug": "google-search", "peso": 50, "essencial": True}]
    assert len(catalogo.divisao(canais, 10_000)["linhas"]) == 2


def test_entra_a_partir_e_faixa_inicial():
    canais = [{"slug": "google-search", "peso": 50, "essencial": True}, {"slug": "meta-ads", "peso": 40, "essencial": True},
              {"slug": "spotify", "peso": 10}]
    assert catalogo.faixa_inicial(25_000) == 30_000
    assert catalogo.entra_a_partir(canais, 10_000) == {"google-search": 10_000, "meta-ads": 10_000, "spotify": 100_000}


def test_semente_tem_25_ou_mais_estrategias_validas():
    slugs = [e["slug"] for e in semente.ESTRATEGIAS]
    assert len(slugs) >= 25 and len(slugs) == len(set(slugs))
    for e in semente.lista():
        n = repositorio.normalizar(e, SLUGS)
        pagos = catalogo.divisao(n["canais"], catalogo.faixa_inicial(n["verba_minima"]))["linhas"]
        assert len(pagos) >= 2, e["slug"]
        nos_fluxo = {s for et in n["fluxo"] for s in et["nos"]}
        assert {c["slug"] for c in n["canais"]} <= nos_fluxo, e["slug"]
        assert any(k["principal"] for k in n["kpis"]), e["slug"]
        assert n["criativos"], e["slug"]


def test_semente_cobre_remarketing_lista_e_portais():
    todas = semente.ESTRATEGIAS
    assert sum(e["remarketing"]["usa"] for e in todas) >= 20
    assert sum(e["lista_clientes"]["usa"] for e in todas) >= 12
    portais = {"g1-globo", "uol", "r7", "cnn-brasil", "sbt", "infomoney", "ge-globo-esporte", "tudogostoso", "techtudo"}
    assert sum(any(c["slug"] in portais for c in e["canais"]) for e in todas) >= 8
    assert {e["conversao"]["precisa_link"] for e in todas} == {True, False}


@pytest.mark.parametrize("mexe, erro", [
    (lambda e: e.update(slug="Com Espaço"), "slug"),
    (lambda e: e.update(canais=e["canais"][:1]), "2 canais"),
    (lambda e: e["canais"].append(dict(e["canais"][0])), "repetido"),
    (lambda e: e["canais"].append({"slug": "inexistente", "papel": "Alcance", "peso": 10}), "desconhecido"),
    (lambda e: e.update(kpis=[]), "indicador"),
    (lambda e: e.update(fluxo=e["fluxo"][:1]), "2 etapas"),
    (lambda e: e.update(verba_minima=5_000), "Verba mínima"),
])
def test_normalizar_recusa_estrategia_invalida(mexe, erro):
    e = semente.lista()[0]
    mexe(e)
    with pytest.raises(repositorio.EstrategiaInvalida, match=erro):
        repositorio.normalizar(e, SLUGS)


def test_brl():
    assert catalogo.brl(12_500) == "R$ 12.500"
    assert catalogo.brl_curto(10_000) == "R$ 10 mil"
    assert catalogo.brl_curto(75_000) == "R$ 75 mil"


def test_semente_tem_o_que_esperar_em_tres_fases():
    for e in semente.lista():
        assert len(e["efeitos"]) == 3 and all(f["fase"] and f["texto"] for f in e["efeitos"]), e["slug"]
        assert repositorio.normalizar(e, SLUGS)["efeitos"] == e["efeitos"]


def test_pracas_ibge_brasil_estado_engole_cidades_e_capitais():
    from aicentralv2.estrategias import pracas
    b = pracas.base()
    assert b["brasil"] == 203_080_756
    capitais = [i for i in b["itens"].values() if i["tipo"] == "capital"]
    assert len(capitais) == 27
    assert pracas.resolver([])["nacional"] and pracas.resolver(["BR", "3550308"])["ids"] == ["BR"]
    sp = pracas.resolver(["UF-SP", "3550308", "3509502"])
    assert sp["ids"] == ["UF-SP"] and sp["pop"] == b["itens"]["UF-SP"]["pop"]
    duas = pracas.resolver(["3550308", "3509502", "xx"])
    assert duas["capitais"] == 1 and duas["interior"] == 1 and 1.0 < duas["fator_custo"] < 1.15
    assert pracas.pessoas(1_800_000) == "1,8 milhão" and pracas.pessoas(11_451_999) == "11,5 milhões"


def test_estimativa_em_faixa_e_praca_pequena_vira_frequencia():
    from aicentralv2.estrategias import estimativa
    e = next(x for x in semente.lista() if x["slug"] == "leads-b2c-formulario-nativo")
    par = estimativa.padroes()
    nac = estimativa.simular(e, 20_000, [], par)
    n = nac["_numeros"]
    assert all(n[k][0] < n[k][1] for k in ("imp", "cli", "res"))
    assert n["res"][1] / n["res"][0] < 3  # faixa útil, não de 1 a 10
    assert nac["resultado_nome"] == "leads" and not nac["avisos"][1:]
    pequena = estimativa.simular(e, 150_000, ["3509502"], par)  # Campinas
    assert pequena["saturado"] and "frequência" in pequena["avisos"][0]
    assert pequena["_numeros"]["alc"][1] <= 1_139_047 * estimativa.ALCANCAVEL * estimativa.TETO_COBERTURA + 1
    capital = estimativa.simular(e, 50_000, ["3550308"], par)["_numeros"]["imp"][1]
    interior = estimativa.simular(e, 50_000, ["3509502", "3518800"], par)["_numeros"]["imp"][1]
    assert interior > capital  # interior tem CPM menor


def test_validar_parametros_recusa_valor_fora():
    from aicentralv2.estrategias import estimativa
    ok = estimativa.validar_parametros(estimativa.padroes())
    assert ok["benchmarks"]["meta-ads"][0] == "cpm"
    for ruim in ({"benchmarks": {"meta-ads": ["cpm", 30, 10, 0.01, 0.02]}},
                 {"benchmarks": {"meta-ads": ["cpv", 1, 2, 0.01, 0.02]}},
                 {"conversao": {"landing": ["leads", 0.5, 2]}},
                 {"benchmarks": {"inventado": ["cpm", 1, 2, 0, 0]}}):
        with pytest.raises(ValueError):
            estimativa.validar_parametros(ruim)
