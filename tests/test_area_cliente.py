"""Área do Cliente: despacho por host, regra de acesso e liberação no CRM v3.

Roda sem banco (DB_HOST=127.0.0.1 DB_PORT=1): tudo que toca o banco é simulado.
"""
import os

os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "1")

import pytest

from tests.shared_app import get_app

HOST = "http://clientes.test"


def _usuario(liberado=True, cliente_id=900):
    return {
        "user_id": 501, "nome": "Ana Souza", "primeiro_nome": "Ana", "iniciais": "AS",
        "email": "ana@cliente.test", "foto_url": "", "cliente_id": cliente_id,
        "cliente_nome": "Cliente Teste", "liberado": liberado,
        "executivo": {"nome": "João Lima", "email": "joao@centralcomm.media",
                      "whatsapp": "https://wa.me/5531999990000", "foto_url": ""},
    }


def _payload():
    marcos = [
        {"id": "pi", "titulo": "PI aprovado", "previsto": "2026-10-01", "realizado": "2026-10-01", "responsavel": "cliente", "nota": ""},
        {"id": "dashboard", "titulo": "Dashboard publicado", "previsto": "2026-10-05", "realizado": "", "responsavel": "cc", "nota": ""},
        {"id": "prestacao", "titulo": "Prestação de contas", "previsto": "2026-12-10", "realizado": "", "responsavel": "cc", "nota": ""},
    ]
    resultado = {
        "id": 1, "nome": "Campanha Verão", "plataforma": "Meta Ads", "objetivo": "Alcance", "status": "Ativa",
        "periodo": {"inicio": "2026-10-01", "fim": "2026-12-01"}, "meta": 1000.0, "meta_label": "1.000",
        "atingido": 500.0, "atingido_label": "500", "pct": 50, "tempo_pct": 55, "dias_restantes": 26,
        "ritmo": "no_ritmo", "dash_embed": "", "dash_abrir": "https://lookerstudio.google.com/x", "atual": False,
    }
    return {
        "demo": False, "cliente": "Cliente Teste", "campanha": "PI Verão", "pi": "CC-123", "id_pi": 12, "grupo": False,
        "periodo": {"inicio": "2026-10-01", "fim": "2026-12-01"}, "atualizado_em": "2026-11-04",
        "marcos": marcos, "resultados": [resultado],
        "executivo": {"nome": "João Lima", "papel": "Executivo(a)", "email": "joao@centralcomm.media", "telefone": "", "whatsapp": "", "foto_url": ""},
        "operacao": None,
        "modulos": {
            "dashboard": {"aparece_apos": "dashboard"},
            "relatorios": {"aparece_apos": "prestacao", "itens": []},
            "combinados": {"aparece_apos": "pi", "pi": [{"rotulo": "Período", "valor": "01/10/2026 a 01/12/2026"}], "campanhas": []},
            "contatos": {"aparece_apos": "pi", "centralcomm": [], "cliente": [{"nome": "Ana", "papel": "Cliente", "email": "ana@cliente.test"}]},
            "documentos": {"aparece_apos": "pi", "itens": [{"titulo": "PI assinado", "url": "https://drive.google.com/x", "data": "2026-10-01"}]},
        },
    }


@pytest.fixture()
def app(monkeypatch):
    application = get_app()
    application.config["TESTING"] = True
    application.config["CLIENTES_URL"] = HOST
    from aicentralv2.cadu_connect import reports_access
    monkeypatch.setattr(reports_access, "reports_only", lambda *a, **k: False)
    return application


def _client(app, sessao=None):
    client = app.test_client()
    if sessao:
        with client.session_transaction(base_url=HOST) as sess:
            sess.update(sessao)
    return client


def _logado(monkeypatch, usuario):
    from aicentralv2.area_cliente import acesso
    monkeypatch.setattr(acesso, "contexto_usuario", lambda user_id: usuario)


def test_sem_sessao_vai_para_o_login_do_mesmo_host(app):
    resp = _client(app).get("/projetos?status=ativos", base_url=HOST)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login?next=%2Fprojetos%3Fstatus%3Dativos"


def test_contato_sem_liberacao_ve_aviso_com_executivo(app, monkeypatch):
    _logado(monkeypatch, _usuario(liberado=False))
    resp = _client(app, {"user_id": 501}).get("/", base_url=HOST)
    assert resp.status_code == 403
    html = resp.get_data(as_text=True)
    assert "Acesso ainda não liberado" in html
    assert "wa.me/5531999990000" in html


def test_inicio_liberado_sem_projetos_mostra_estado_vazio(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    monkeypatch.setattr(dados, "listar_projetos", lambda cliente_id, busca="": [])
    resp = _client(app, {"user_id": 501}).get("/", base_url=HOST)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Olá" not in html and "Cliente Teste" in html
    assert 'class="ac-nav ac-nav--cadu"' not in html and "Studio" in html  # Cadu só no menu do usuário
    assert "Nenhum PI ainda" in html and html.count("Enviar briefing") == 1
    assert 'href="/pis"' in html and 'href="/descobrir/canais"' in html
    nav = html.split('aria-label="Seções"', 1)[1].split("</nav>", 1)[0]
    ordem = [nav.index(t) for t in ("Início", "Briefing", "Campanhas", "Relatórios", "PIs", "Descobrir", "Canais", "Portais")]
    assert ordem == sorted(ordem) and "Projetos" not in nav and "Equipe" not in nav
    assert "ac-nav__sep" not in nav  # menu sem linhas
    assert nav.index("Planejar") < nav.index("Briefing") < nav.index("Acompanhar") < nav.index("Campanhas")
    assert "R$" not in html


def test_rotas_internas_nao_existem_no_host_de_clientes(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    client = _client(app, {"user_id": 501})
    for path in ("/cadu/creditos", "/crm-v3", "/clientes/novo", "/parametros/integracoes"):
        assert client.get(path, base_url=HOST).status_code == 404, path


def test_login_e_estaticos_continuam_no_host_de_clientes(app):
    from aicentralv2.area_cliente.routes import despachar
    for path in ("/login", "/logout", "/acesso-confirmado", "/static/css/area_cliente.css",
                 "/forgot-password", "/reset-password/abc", "/signup", "/auth/google"):
        with app.test_request_context(path, base_url=HOST):
            assert despachar() is None, path


def test_fora_do_host_de_clientes_nada_muda(app):
    from aicentralv2.area_cliente.routes import despachar
    with app.test_request_context("/clientes", base_url="http://localhost:5000"):
        assert despachar() is None
    with app.test_request_context("/", base_url="https://workspace.centralcomm.media"):
        assert despachar() is None


def test_projeto_de_outro_cliente_da_404(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    chamadas = []
    monkeypatch.setattr(dados, "projeto_do_cliente", lambda cliente_id, id_pi: chamadas.append((cliente_id, id_pi)))
    resp = _client(app, {"user_id": 501}).get("/projetos/77", base_url=HOST)
    assert resp.status_code == 404
    assert chamadas == [(900, 77)]  # sempre o cliente do cadastro, nunca da URL


def test_projeto_360_sem_custos(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    from aicentralv2.campanha_acompanhamento_publico import contexto_pagina
    payload = _payload()
    monkeypatch.setattr(dados, "projeto_do_cliente", lambda c, i: {"vazio": False, "payload": payload, "ctx": contexto_pagina(payload)})
    monkeypatch.setattr(dados, "resumo_projeto", lambda c, i: {
        "id": 12, "titulo": "PI Verão", "pi": "CC-123", "status": "Em andamento", "ativo": True,
        "periodo": payload["periodo"], "pct": 50, "n_campanhas": 1, "plataformas": ["Meta Ads"], "campanhas": [],
    })
    monkeypatch.setattr(dados, "campanhas_dos_pis", lambda ids: [
        {"nome": "Campanha Verão", "plataforma": "Meta Ads", "pct": 50, "no_ar": True}])
    resp = _client(app, {"user_id": 501}).get("/projetos/12", base_url=HOST)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    for trecho in ("PI Verão", "Visão 360°", "Campanha Verão", "1.000", "PI assinado", "Cronograma"):
        assert trecho in html
    assert "R$" not in html


def test_pagina_em_preparacao(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    client = _client(app, {"user_id": 501})
    resp = client.get("/equipe", base_url=HOST)
    assert resp.status_code == 200 and "Em preparação" in resp.get_data(as_text=True)
    antigo = client.get("/planejamento", base_url=HOST)
    assert antigo.status_code == 301 and antigo.headers["Location"] == "/descobrir/canais"


def test_sair_limpa_a_sessao(app):
    client = _client(app, {"user_id": 501})
    resp = client.get("/sair", base_url=HOST)
    assert resp.status_code == 302 and resp.headers["Location"].startswith("/login")
    with client.session_transaction(base_url=HOST) as sess:
        assert "user_id" not in sess


def test_area_url():
    from aicentralv2.area_cliente import area_url
    assert area_url("inicio") == "/"
    assert area_url("projeto", id_pi=12) == "/projetos/12"


def test_crm_libera_so_para_equipe_centralcomm(app, monkeypatch):
    from aicentralv2.area_cliente import acesso
    chamadas = []
    monkeypatch.setattr(acesso, "definir_acesso", lambda cid, ativo, autor: chamadas.append((cid, ativo, autor)) or {"id": cid, "cliente_id": "900", "ativo": ativo})
    monkeypatch.setattr(acesso, "ultima_liberacao", lambda cid: {"acao": "APPROVE", "autor": "Equipe", "em": "05/11/2026"})

    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess.update({"user_id": 501, "is_centralcomm": False})
    assert cliente.put("/crm-v3/api/contatos/42/area-cliente", json={"ativo": True}).status_code == 403

    equipe = app.test_client()
    with equipe.session_transaction() as sess:
        sess.update({"user_id": 7, "is_centralcomm": True})
    assert equipe.put("/crm-v3/api/contatos/42/area-cliente", json={"ativo": "sim"}).status_code == 400
    assert equipe.put("/crm-v3/api/contatos/abc/area-cliente", json={"ativo": True}).status_code == 404
    resp = equipe.put("/crm-v3/api/contatos/42/area-cliente", json={"ativo": True})
    assert resp.status_code == 200
    assert resp.get_json()["liberacao"]["autor"] == "Equipe"
    assert chamadas == [("42", True, 7)]


def _briefing_client(app, monkeypatch, enviados=None):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import briefing
    monkeypatch.setattr(briefing, "listar", lambda cliente_id: enviados or [])
    return _client(app, {"user_id": 501, "area_cliente_csrf": "tok"})


def test_briefing_mostra_formulario_e_nav_sem_integracoes(app, monkeypatch):
    client = _briefing_client(app, monkeypatch)
    resp = client.get("/briefing", base_url=HOST)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'name="csrf" value="tok"' in html
    assert "Enviar para a Centralcomm" in html
    assert "Integrações" not in html
    assert client.get("/integracoes", base_url=HOST).status_code == 404


def test_briefing_sem_token_e_recusado(app, monkeypatch):
    client = _briefing_client(app, monkeypatch)
    resp = client.post("/briefing", base_url=HOST, data={"titulo": "Verão", "objetivo": "Vender mais no verão"})
    assert resp.status_code == 400
    assert client.post("/briefing", base_url=HOST, data={"csrf": "ç"}).status_code == 400
    sem_token = _client(app, {"user_id": 501})
    assert sem_token.post("/briefing", base_url=HOST, data={"csrf": "-"}).status_code == 400


def test_briefing_invalido_volta_com_erros(app, monkeypatch):
    client = _briefing_client(app, monkeypatch)
    from aicentralv2.area_cliente import briefing
    monkeypatch.setattr(briefing, "enviar", lambda *a: pytest.fail("não deveria gravar"))
    resp = client.post("/briefing", base_url=HOST, data={
        "csrf": "tok", "titulo": "V", "objetivo": "curto", "inicio": "2026-12-10", "fim": "2026-12-01",
    })
    assert resp.status_code == 422
    html = resp.get_data(as_text=True)
    for msg in ("Dê um nome", "Conte em uma ou duas frases", "O fim precisa ser depois do início"):
        assert msg in html


def test_briefing_valido_grava_e_redireciona(app, monkeypatch):
    client = _briefing_client(app, monkeypatch)
    from aicentralv2.area_cliente import briefing
    gravados = []
    monkeypatch.setattr(briefing, "enviar", lambda usuario, d: gravados.append((usuario["cliente_id"], d)) or 77)
    resp = client.post("/briefing", base_url=HOST, data={
        "csrf": "tok", "titulo": "Coleção de verão", "objetivo": "Gerar visitas às lojas de BH",
        "canais": ["social", "inexistente"], "inicio": "2026-12-01", "fim": "2027-01-15", "verba": "até 50 mil",
    })
    assert resp.status_code == 303
    assert resp.headers["Location"] == "/briefing?enviado=77"
    cliente_id, d = gravados[0]
    assert cliente_id == 900 and d["canais"] == ["social"] and str(d["fim"]) == "2027-01-15"


def test_texto_do_briefing_reune_os_campos():
    from datetime import date
    from aicentralv2.area_cliente.briefing import _texto_briefing
    texto = _texto_briefing({
        "objetivo": "Vender", "publico": "BH", "inicio": date(2026, 12, 1), "fim": None,
        "canais": ["ooh"], "verba": "50 mil", "descricao": "Detalhes",
    })
    assert "Período desejado: 01/12/2026 a a definir" in texto
    assert "Canais de interesse: OOH e DOOH" in texto
    assert texto.endswith("Detalhes")


def _lista_fake(secao, busca="", categoria="", pagina=1):
    return {"cartoes": [{"id": 5, "nome": "Uber Ads", "descricao": "App de mobilidade", "imagem": "", "logo": "",
                         "meta": ["Mobilidade"]}],
            "total": 1, "pagina": 1, "paginas": 1, "categorias": ["Mobilidade"], "busca": busca, "categoria": categoria}


def test_descobrir_secao_lista_e_inclui_no_briefing(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import briefing, descobrir
    monkeypatch.setattr(descobrir, "listar", _lista_fake)
    monkeypatch.setattr(briefing, "listar", lambda cliente_id: [])
    client = _client(app, {"user_id": 501, "area_cliente_csrf": "tok"})
    html = client.get("/descobrir/canais", base_url=HOST).get_data(as_text=True)
    assert "Uber Ads" in html and "Incluir no briefing" in html and "Places" not in html and "Radar" not in html
    resp = client.post("/descobrir/selecao", base_url=HOST, data={
        "csrf": "tok", "secao": "canais", "id": "5", "nome": "Uber Ads", "voltar": "/descobrir/canais"})
    assert resp.status_code == 303 and resp.headers["Location"] == "/descobrir/canais"
    assert "No briefing" in client.get("/descobrir/canais", base_url=HOST).get_data(as_text=True)
    form = client.get("/briefing", base_url=HOST).get_data(as_text=True)
    assert "Uber Ads" in form and "Tirar Uber Ads do briefing" in form

    gravados = []
    monkeypatch.setattr(briefing, "enviar", lambda usuario, d: gravados.append(d) or 9)
    client.post("/briefing", base_url=HOST, data={"csrf": "tok", "titulo": "Verão", "objetivo": "Gerar visitas às lojas"})
    assert gravados[0]["descobrir"] == "Itens escolhidos no Descobrir:\n- Canal: Uber Ads"
    with client.session_transaction(base_url=HOST) as sess:
        assert "area_cliente_descobrir" not in sess


def test_descobrir_selecao_exige_token_e_voltar_local(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    client = _client(app, {"user_id": 501, "area_cliente_csrf": "tok"})
    assert client.post("/descobrir/selecao", base_url=HOST, data={"secao": "canais", "id": "5"}).status_code == 400
    resp = client.post("/descobrir/selecao", base_url=HOST, data={
        "csrf": "tok", "secao": "canais", "id": "5", "nome": "X", "voltar": "//evil.test/x"})
    assert resp.headers["Location"] == "/descobrir/canais"
    assert client.post("/descobrir/selecao", base_url=HOST, data={"csrf": "tok", "secao": "places", "id": "1"}).status_code == 404
    assert client.get("/descobrir/places", base_url=HOST).status_code == 404


def test_alternar_tira_e_respeita_limite():
    from aicentralv2.area_cliente import descobrir
    sess = {}
    assert descobrir.alternar(sess, "portais", 1, "G1") is True
    assert descobrir.alternar(sess, "portais", 1, "G1") is False
    assert descobrir.selecao(sess) == []
    for i in range(descobrir.LIMITE_SELECAO):
        descobrir.alternar(sess, "audiencias", i + 1, f"A{i}")
    assert descobrir.alternar(sess, "canais", 999, "Excedente") is False
    assert len(descobrir.selecao(sess)) == descobrir.LIMITE_SELECAO


def test_detalhe_de_audiencia_sem_custos(monkeypatch):
    from aicentralv2.cadu_planner import catalog
    from aicentralv2.area_cliente import descobrir
    monkeypatch.setattr(catalog, "audience_profile", lambda value: {
        "id": 3, "name": "Executivos", "description": "Líderes", "audience": "992K", "channel": "LinkedIn", "category": "B2B",
        "related": [{"id": 4, "name": "Diretores", "platform": "LinkedIn", "audience": "500K"}], "channel_ref": None, "channel_formats": [],
        "data_groups": [
            {"title": "Público, perfil e comportamento", "fields": [{"label": "Idade", "value": "30-50", "variable": "idade"}]},
            {"title": "Indicadores estimados", "fields": [
                {"label": "CPA mínimo", "value": "R$ 10", "variable": "cpa_estimado_min"},
                {"label": "Mercado", "value": "R$ 2 bi", "variable": "tamanho_mercado_brl"},
                {"label": "Alcance incremental", "value": "+12%", "variable": "alcance_incremental"}]},
        ]})
    monkeypatch.setattr(catalog, "detail", lambda kind, value: {
        "titulo_chamativo": "C-Level Digitais", "storytelling": "Entre reuniões estratégicas, este público vive no celular.",
        "is_premium": True, "perfil_socioeconomico": "A", "cpm_venda": "R$ 45", "ticket_medio_estimado": "15000.00",
        "perfil_consumo": {"horarios_pico": ["06h-08h"], "triggers_compra": ["ROI comprovado"], "ticket_medio_mensal": 15000,
                           "frequencia_compra": "trimestral"}})
    item = descobrir.detalhe("audiencias", 3)
    assert [s["id"] for s in item["sessoes"]] == ["perfil", "consumo"]
    consumo = item["sessoes"][1]["dados"]
    assert [l["titulo"] for l in consumo["listas"]] == ["Horários de pico", "Gatilhos de compra"]
    assert consumo["fatos"] == [{"rotulo": "Frequência de compra", "valor": "Trimestral"}]
    assert item["subtitulo"] == "C-Level Digitais" and item["selos"] == ["Premium", "LinkedIn"]
    assert item["destaques"][0]["titulo"] == "Retrato"
    assert {m["rotulo"] for m in item["metricas"]} == {"Público estimado", "Onde comprar", "Perfil socioeconômico", "Alcance incremental"}
    assert "15000" not in str(item) and "45" not in str(item)
    assert item["relacionados"]["itens"][0]["id"] == 4
    assert "R$" not in str(item) and "CPA" not in str(item)


def test_ficha_de_canal_na_organizacao_do_planner(monkeypatch):
    from aicentralv2.cadu_planner import catalog
    from aicentralv2.area_cliente import descobrir
    monkeypatch.setattr(catalog, "channel_profile", lambda value: {
        "id": 9, "name": "Spotify", "categoria": "Áudio", "tipo": "streaming", "logo_url": "/l.svg", "hero_image_url": "/capa.webp",
        "gallery": [{"url": "/g1.webp"}], "description": "Streaming de áudio", "alcance": "40M", "viewability": "92",
        "formats": [{"id": 7, "name": "Audio Ad", "dimensions": "640x640", "format_type": "audio"}],
        "audiences": [{"id": 11, "name": "Jovens", "category": "Lifestyle", "audience": "3M"}],
        "segmentacoes": [{"nome": "Capitais", "quando": "lançamento", "exemplo": "SP"}],
        "demografia": {"homens": 48, "mulheres": 52, "faixas": {"18_24": 30}},
        "related": [{"id": 10, "name": "Deezer", "alcance": "10M"}]})
    item = descobrir.detalhe("canais", 9)
    assert item["banner"] == "/capa.webp" and item["metricas"][0] == {"rotulo": "Alcance", "valor": "40M", "dica": "Declarado pelo canal"}
    assert {"rotulo": "Viewability", "valor": "92%"} in item["metricas"]
    ids = [s["id"] for s in item["sessoes"]]
    assert ids == ["ficha", "formatos", "audiencias", "publico", "estrategias", "fotos"]
    formatos = next(s for s in item["sessoes"] if s["id"] == "formatos")["dados"]
    assert formatos[0]["quadro"]["rotulo"] == "640×640"
    demografia = next(s for s in item["sessoes"] if s["id"] == "publico")["dados"]
    assert [g["titulo"] for g in demografia] == ["Gênero", "Faixas"]


def test_item_inexistente_da_404(monkeypatch):
    from werkzeug.exceptions import BadRequest, NotFound
    from aicentralv2.cadu_planner import catalog
    from aicentralv2.area_cliente import descobrir

    def falha(value):
        raise BadRequest()
    monkeypatch.setattr(catalog, "channel_profile", falha)
    import pytest
    with pytest.raises(NotFound):
        descobrir.detalhe("canais", 99)
    with pytest.raises(NotFound):
        descobrir.detalhe("canais", "abc")


def test_tirar_item_por_fetch_responde_json(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    client = _client(app, {"user_id": 501, "area_cliente_csrf": "tok",
                           "area_cliente_descobrir": [["canais", 5, "Uber Ads"]]})
    resp = client.post("/descobrir/selecao", base_url=HOST, headers={"X-Requested-With": "fetch"},
                       data={"csrf": "tok", "secao": "canais", "id": "5"})
    assert resp.status_code == 200 and resp.get_json() == {"incluido": False, "total": 0, "limite": 20}
    with client.session_transaction(base_url=HOST) as sess:
        assert sess["area_cliente_descobrir"] == []


def test_menu_lembra_sidebar_e_grupos_pelo_cookie(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    monkeypatch.setattr(dados, "listar_projetos", lambda cliente_id, busca="": [])
    client = _client(app, {"user_id": 501})
    html = client.get("/", base_url=HOST).get_data(as_text=True)
    assert '<html lang="pt-BR" class="ac-rail">' in html and 'id="ac-nav-descobrir"' in html
    client.set_cookie("ac_side", "aberta", domain=HOST.split("//")[1])
    client.set_cookie("ac_nav", "descobrir,acompanhar,xss", domain=HOST.split("//")[1])
    html = client.get("/", base_url=HOST).get_data(as_text=True)
    assert '<html lang="pt-BR">' in html
    assert 'class="ac-nav__group is-collapsed" id="ac-nav-descobrir"' in html
    assert 'class="ac-nav__group is-collapsed" id="ac-nav-acompanhar"' in html
    assert 'class="ac-nav__group" id="ac-nav-planejar"' in html


def test_selecao_cabe_no_cookie():
    from aicentralv2.area_cliente import descobrir
    sess = {}
    for i in range(descobrir.LIMITE_SELECAO):
        descobrir.alternar(sess, "audiencias", 10000 + i, "Audiência com um nome bem comprido " * 4)
    import json
    assert len(json.dumps(sess["area_cliente_descobrir"], ensure_ascii=False).encode()) < 2000


def test_campanhas_por_status_sem_custos(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    camp = {"id": 1, "nome": "Verão Meta", "plataforma": "Meta Ads", "objetivo": "Alcance", "status": "Aguardando",
            "periodo": {"inicio": "2026-12-01", "fim": "2027-01-01"}, "meta": 1000.0, "meta_label": "1.000",
            "atingido": 0.0, "atingido_label": "0", "pct": 0, "tempo_pct": None, "dias_restantes": None, "ritmo": "",
            "dash_embed": "", "dash_abrir": "", "atual": False, "id_pi": 12, "no_ar": False, "responsavel": "Ana Op"}
    monkeypatch.setattr(dados, "listar_projetos", lambda c, busca="", id_pi=None: [{"id": 12, "titulo": "PI Verão", "pi": "CC-123", "campanhas": [camp]}])
    client = _client(app, {"user_id": 501})
    html = client.get("/campanhas?status=aguardando", base_url=HOST).get_data(as_text=True)
    assert "Verão Meta" in html and "Ana Op" in html and "Aguardando criativos" in html
    for termo in ("Gasto", "Previsto", "Investimento", "Mídia e Veiculação", "Arquivos"):
        assert termo not in html
    assert client.get("/midia", base_url=HOST).headers["Location"] == "/campanhas"
    assert client.get("/arquivos", base_url=HOST).headers["Location"] == "/pis"


def test_pi_mostra_valores_de_venda_e_notas(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    pi = {"id": 12, "pi": "CC-123", "titulo": "PI Verão", "status": "Em faturamento", "status_id": 4,
          "periodo": {"inicio": "2026-10-01", "fim": "2026-11-01"}, "cliente": "Cliente", "agencia": "Agência X",
          "bruto": 10000.0, "comissao": 2000.0, "liquido": 8000.0, "n_notas": 1, "n_pagas": 0, "atualizado_em": "",
          "documentos": [], "faturado": 8000.0, "pago": None, "historico": [{"titulo": "Campanha no ar", "em": "2026-10-02"}],
          "etapas": [{"titulo": t, "estado": e} for t, e in zip(dados.ETAPAS_PI, ("done", "done", "done", "current", "todo"))],
          "notas": [{"numero": "123", "emissao": "2026-11-03", "valor": 8000.0, "liquido": 7500.0, "competencia": "11/2026",
                     "prevista": "2026-12-03", "pago_em": "", "status": "NF Emitida"}]}
    monkeypatch.setattr(dados, "pi_do_cliente", lambda c, i: pi if i == 12 else None)
    monkeypatch.setattr(dados, "campanhas_dos_pis", lambda ids: [])
    client = _client(app, {"user_id": 501})
    html = client.get("/pis/12", base_url=HOST).get_data(as_text=True)
    for trecho in ("R$ 10.000,00", "R$ 2.000,00", "R$ 8.000,00", "R$ 7.500,00", "NF 123", "Previsto 03/12", "Em faturamento"):
        assert trecho in html, trecho
    assert "lucratividade" not in html.lower() and "Gasto" not in html
    assert client.get("/pis/99", base_url=HOST).status_code == 404


OPCOES = [{"id": 80, "nome": "AGÊNCIA X", "tipo": "Agência", "n_pis": 12}]


def _admin_cc(monkeypatch):
    from aicentralv2.area_cliente import acesso, routes
    admin = dict(_usuario(cliente_id=174), cliente_nome="CENTRALCOMM", pode_ver_como=True, ver_como=False)
    monkeypatch.setattr(acesso, "contexto_usuario", lambda uid: dict(admin))
    monkeypatch.setattr(acesso, "clientes_para_ver_como", lambda ano: OPCOES)
    monkeypatch.setattr(routes, "_CACHE_VER_COMO", {"em": 0.0, "ano": None, "dados": []})

    def aplicar(usuario, cliente_id, ano, opcoes=None):
        if not usuario.get("pode_ver_como") or int(cliente_id) != 80:
            return None
        return {**usuario, "cliente_id": 80, "cliente_nome": "AGÊNCIA X", "executivo": None, "ver_como": True,
                "ver_como_tipo": "Agência", "cliente_real_id": 174, "cliente_real_nome": "CENTRALCOMM"}
    monkeypatch.setattr(acesso, "aplicar_ver_como", aplicar)
    from aicentralv2.area_cliente import dados
    monkeypatch.setattr(dados, "listar_projetos", lambda c, busca="", id_pi=None: [])
    return admin


def test_admin_cc_ve_seletor_e_troca_de_cliente(app, monkeypatch):
    _admin_cc(monkeypatch)
    import aicentralv2.audit as audit
    monkeypatch.setattr(audit, "registrar_acao_admin", lambda **k: None)
    client = _client(app, {"user_id": 501, "area_cliente_csrf": "tok"})
    html = client.get("/", base_url=HOST).get_data(as_text=True)
    assert "Ver como cliente" in html and "AGÊNCIA X · Agência · 12 PIs" in html
    assert client.post("/ver-como", base_url=HOST, data={"csrf": "tok", "cliente_id": "999"}).status_code == 403
    resp = client.post("/ver-como", base_url=HOST, data={"csrf": "tok", "cliente_id": "80"})
    assert resp.status_code == 303
    html = client.get("/", base_url=HOST).get_data(as_text=True)
    assert "Vendo como <b>AGÊNCIA X</b>" in html and "voltar para CENTRALCOMM" in html
    client.post("/ver-como/sair", base_url=HOST, data={"csrf": "tok"})
    with client.session_transaction(base_url=HOST) as sess:
        assert "area_cliente_ver_como" not in sess


def test_ver_como_nao_envia_briefing(app, monkeypatch):
    _admin_cc(monkeypatch)
    from aicentralv2.area_cliente import briefing
    monkeypatch.setattr(briefing, "listar", lambda c: [])
    monkeypatch.setattr(briefing, "enviar", lambda *a: pytest.fail("não pode gravar no modo ver como"))
    client = _client(app, {"user_id": 501, "area_cliente_csrf": "tok", "area_cliente_ver_como": 80})
    resp = client.post("/briefing", base_url=HOST, data={"csrf": "tok", "titulo": "Teste", "objetivo": "Objetivo de teste"})
    assert resp.status_code == 422
    assert "o envio fica desativado" in resp.get_data(as_text=True)


def test_quem_nao_e_admin_cc_nao_troca(app, monkeypatch):
    _logado(monkeypatch, dict(_usuario(), pode_ver_como=False))
    client = _client(app, {"user_id": 501, "area_cliente_csrf": "tok"})
    assert "Ver como cliente" not in client.get("/", base_url=HOST).get_data(as_text=True)
    from aicentralv2.area_cliente import acesso
    monkeypatch.setattr(acesso, "clientes_para_ver_como", lambda ano: OPCOES)
    assert client.post("/ver-como", base_url=HOST, data={"csrf": "tok", "cliente_id": "80"}).status_code == 403
    assert acesso.aplicar_ver_como(dict(_usuario(), pode_ver_como=True), "80abc", 2026, OPCOES) is None
    assert acesso.aplicar_ver_como(dict(_usuario(), pode_ver_como=True), 81, 2026, OPCOES) is None


def test_campanhas_grade_e_painel_lateral(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    camp = {"id": 1, "nome": "Verão </script> Meta", "plataforma": "Meta Ads", "objetivo": "Alcance", "status": "Ativa",
            "periodo": {"inicio": "2026-11-01", "fim": "2026-12-01"}, "meta": 1000.0, "meta_label": "1.000",
            "atingido": 500.0, "atingido_label": "500", "pct": 50, "tempo_pct": 40, "dias_restantes": 18, "ritmo": "no_ritmo",
            "dash_embed": "", "dash_abrir": "https://lookerstudio.google.com/x", "atual": False, "id_pi": 12, "no_ar": True,
            "responsavel": "Ana Op"}
    monkeypatch.setattr(dados, "listar_projetos", lambda c, busca="", id_pi=None: [{"id": 12, "titulo": "PI Verão", "pi": "CC-123", "campanhas": [camp]}])
    html = _client(app, {"user_id": 501}).get("/campanhas", base_url=HOST).get_data(as_text=True)
    assert 'id="camp-drawer"' in html and "18 d" in html and "Meta Ads" in html
    dados_json = html.split('id="camp-dados">', 1)[1].split("</script>", 1)[0]
    assert "</script>" not in dados_json and "\\u003c/script\\u003e" in dados_json  # nome escapado no JSON
    import json
    d = json.loads(dados_json)[0]
    assert d["tempo"] == "40% · 18 dias restantes" and d["pi_url"] == "/pis/12" and d["pi_360"] == "/projetos/12"


def test_logos_e_resumo_de_plataformas():
    from aicentralv2.area_cliente import plataformas
    assert plataformas.logo("Meta Ads").endswith("facebook.svg")
    assert plataformas.logo("Plataforma Nova") == "" and plataformas.iniciais("Plataforma Nova") == "PN"
    r = plataformas.resumo([
        {"plataforma": "DV360", "pct": 40, "no_ar": True}, {"plataforma": "DV360", "pct": 60, "no_ar": False},
        {"plataforma": "Spotify", "pct": None, "no_ar": True}])
    assert [(p["nome"], p["n"], p["no_ar"], p["pct"]) for p in r] == [("DV360", 2, 1, 50), ("Spotify", 1, 1, None)]


# ---------- E-mails e telas de acesso ----------

def test_todas_as_previas_de_email_renderizam(app, monkeypatch):
    from aicentralv2.area_cliente import emails
    with app.test_request_context("/", base_url=HOST):
        for modelo in emails.MODELOS:
            html = emails.previa(modelo)
            assert "Área do Cliente" in html and "Centralcomm" in html and "Cadu Workspace" not in html, modelo


def test_previa_de_email_so_para_admin_cc(app, monkeypatch):
    _admin_cc(monkeypatch)
    client = _client(app, {"user_id": 501})
    assert "Novo acesso à sua conta" in client.get("/emails/novo-acesso", base_url=HOST).get_data(as_text=True)
    _logado(monkeypatch, dict(_usuario(), pode_ver_como=False))
    assert client.get("/emails/novo-acesso", base_url=HOST).status_code == 404


def test_acesso_liberado_sem_senha_cria_link(app, monkeypatch):
    from aicentralv2 import db
    from aicentralv2.area_cliente import emails
    enviados, tokens = [], []
    monkeypatch.setattr(emails, "_executivo_do_cliente", lambda cid: {"cliente": "CLIENTE X", "nome": "João", "email": "joao@centralcomm.media", "whatsapp": ""})
    monkeypatch.setattr(emails, "_enviar", lambda modelo, para, nome, assunto, ctx, reply_to=None: enviados.append((modelo, para, ctx, reply_to)) or True)
    monkeypatch.setattr(db, "atualizar_reset_token", lambda email, token, exp: tokens.append(token) or True)
    with app.test_request_context("/", base_url=HOST):
        emails.acesso_liberado({"email": "ana@cliente.test", "nome_completo": "Ana Souza", "pk_id_tbl_cliente": 900, "tem_senha": False})
        emails.acesso_liberado({"email": "bia@cliente.test", "nome_completo": "Bia", "pk_id_tbl_cliente": 900, "tem_senha": True})
    (m1, para1, ctx1, reply1), (m2, _p, ctx2, _r) = enviados
    assert m1 == "acesso-liberado" and para1 == "ana@cliente.test" and ctx1["link_senha"].endswith(f"/reset-password/{tokens[0]}")
    assert reply1 == {"name": "João", "email": "joao@centralcomm.media"}
    assert ctx2["link_senha"] == "" and len(tokens) == 1


def test_sem_acesso_pede_ao_executivo_uma_vez(app, monkeypatch):
    _logado(monkeypatch, _usuario(liberado=False))
    from aicentralv2.area_cliente import emails
    pedidos = []
    monkeypatch.setattr(emails, "pedido_acesso", lambda usuario: pedidos.append(usuario["email"]) or True)
    client = _client(app, {"user_id": 501, "area_cliente_csrf": "tok"})
    assert "Solicitar acesso" in client.get("/", base_url=HOST).get_data(as_text=True)
    client.post("/solicitar-acesso", base_url=HOST, data={"csrf": "tok"})
    client.post("/solicitar-acesso", base_url=HOST, data={"csrf": "tok"})
    assert pedidos == ["ana@cliente.test"]
    assert "Pedido enviado para João Lima" in client.get("/", base_url=HOST).get_data(as_text=True)


def test_briefing_dispara_os_dois_emails(app, monkeypatch):
    client = _briefing_client(app, monkeypatch)
    from aicentralv2.area_cliente import briefing, emails
    monkeypatch.setattr(briefing, "enviar", lambda usuario, d: 41)
    chamados = []
    monkeypatch.setattr(emails, "briefing_novo", lambda u, v, i: chamados.append(("novo", i)))
    monkeypatch.setattr(emails, "briefing_recebido", lambda u, v: chamados.append(("recebido", v["titulo"])))
    client.post("/briefing", base_url=HOST, data={"csrf": "tok", "titulo": "Coleção", "objetivo": "Gerar visitas às lojas"})
    assert chamados == [("novo", 41), ("recebido", "Coleção")]


def test_login_no_host_de_clientes_usa_tela_centralcomm(app):
    html = app.test_client().get("/login?next=/", base_url=HOST).get_data(as_text=True)
    assert "Use o e-mail e a senha do Cadu" in html and "Área do Cliente" in html
    html = app.test_client().get("/forgot-password", base_url=HOST).get_data(as_text=True)
    assert "Criar nova senha" in html



def _camp(**extra):
    base = {"id": 1, "nome": "Verão Meta", "plataforma": "Meta Ads", "plataforma_logo": "", "plataforma_iniciais": "MA",
            "objetivo": "Alcance", "status": "Ativa", "periodo": {"inicio": "2026-11-01", "fim": "2026-12-01"},
            "meta": 1000.0, "meta_label": "1.000", "atingido": 500.0, "atingido_label": "500", "pct": 50, "tempo_pct": 40,
            "dias_restantes": 18, "ritmo": "adiantado", "dash_embed": "", "dash_abrir": "https://lookerstudio.google.com/x",
            "atual": False, "id_pi": 12, "no_ar": True, "responsavel": "Ana Op"}
    return {**base, **extra}


def test_relatorios_so_pis_abertos_com_link_publico(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    projetos = [
        {"id": 12, "titulo": "PI Verão", "pi": "CC-123", "status": "Em andamento", "status_id": 3, "ativo": True,
         "periodo": {"inicio": "2026-11-01", "fim": "2026-12-01"}, "campanhas": [_camp(), _camp(id=2, nome="Encerrada", no_ar=False)]},
        {"id": 13, "titulo": "PI Antigo", "pi": "CC-100", "status": "Finalizado", "status_id": 5, "ativo": False,
         "periodo": {"inicio": "2025-01-01", "fim": "2025-02-01"}, "campanhas": [_camp(id=3, nome="Velha")]},
    ]
    monkeypatch.setattr(dados, "listar_projetos", lambda c, busca="", id_pi=None: projetos)
    monkeypatch.setattr(dados, "_fetch", lambda sql, params: [
        {"id_pi": 12, "link_publico_token": "cliente-pi-abc123", "link_publico_ativo": True,
         "link_publico_expires_at": None, "googled_pi_financ": "https://drive.google.com/x"}])
    html = _client(app, {"user_id": 501}).get("/relatorios", base_url=HOST).get_data(as_text=True)
    assert "PI Verão" in html and "PI Antigo" not in html
    assert 'href="/campanha/p/cliente-pi-abc123"' in html and "Prestação de contas" in html
    assert "Verão Meta" in html and "Encerrada" not in html
    assert "ac-progress--adiantado" in html and "ac-progress--tempo" in html and "ac-progress__mark" not in html


def test_pis_abre_em_andamento(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    base = {"periodo": {"inicio": "", "fim": ""}, "bruto": 1.0, "liquido": 1.0, "comissao": None, "n_notas": 0, "n_pagas": 0,
            "agencia": "", "cliente": "", "atualizado_em": "", "documentos": []}
    monkeypatch.setattr(dados, "listar_pis", lambda c, id_pi=None: [
        {**base, "id": 1, "pi": "CC-1", "titulo": "Aberto", "status": "Em andamento", "status_id": 3},
        {**base, "id": 2, "pi": "CC-2", "titulo": "Fechado", "status": "Finalizado", "status_id": 5}])
    monkeypatch.setattr(dados, "campanhas_dos_pis", lambda ids: [])
    client = _client(app, {"user_id": 501})
    html = client.get("/pis", base_url=HOST).get_data(as_text=True)
    assert "Aberto" in html and "Fechado" not in html and "Em andamento<span>1</span>" in html
    assert "Fechado" in client.get("/pis?status=todos", base_url=HOST).get_data(as_text=True)


def test_selo_de_campanhas_e_brilho_do_briefing(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    monkeypatch.setattr(dados, "campanhas_em_andamento", lambda c: 7)
    monkeypatch.setattr(dados, "listar_projetos", lambda c, busca="", id_pi=None: [])
    html = _client(app, {"user_id": 501}).get("/", base_url=HOST).get_data(as_text=True)
    assert 'aria-label="7 campanhas em andamento">7<' in html and "ac-nav__link--shine" in html


def test_periodo_encerrado_nao_diz_termina_hoje(app):
    from aicentralv2.area_cliente import dados
    itens = dados.marcar_encerradas([{"periodo": {"fim": "2020-01-31"}, "dias_restantes": 0},
                                     {"periodo": {"fim": "2999-01-31"}, "dias_restantes": 5}])
    assert [i["dias_restantes"] for i in itens] == [-1, 5]
    with app.test_request_context("/"):
        from flask import render_template_string
        html = render_template_string("{% from 'area_cliente/_macros.html' import barra %}{{ barra(100, 'x', 100, '', -1) }}{{ barra(50, 'y', 90, '', 0) }}")
    assert "encerrada" in html and "termina hoje" in html


def test_grupo_da_pagina_atual_abre_mesmo_recolhido(app):
    from aicentralv2.area_cliente import routes
    with app.test_request_context("/pis", headers={"Cookie": "ac_nav=descobrir,acompanhar"}):
        estado = routes._estado_menu("pis")
    assert estado["recolhidos"] == {"descobrir"} and estado["grupo_atual"] == "acompanhar"
    assert estado["sidebar_aberta"] is False and estado["tem_cookie_sidebar"] is False


def test_portal_com_numeros_em_texto_nao_quebra(monkeypatch):
    from aicentralv2.cadu_planner import portals
    from aicentralv2.area_cliente import descobrir, ficha
    ficha._CACHE.clear()
    monkeypatch.setattr(portals, "detail", lambda value: {
        "id": 8, "name": "Portal X", "domain": "x.com.br", "featured_rank": "", "monthly_visits": "n/d",
        "avg_time_seconds": None, "traffic_tier": "medio", "uf": "MG", "site_sections": ["Política"],
        "formats": {"own": [{"id": 1, "nome": "Billboard", "dimensoes": "970x250"}], "observed": []}})
    item = descobrir.detalhe("portais", 8)
    rotulos = [m["rotulo"] for m in item["metricas"]]
    assert "Acessos por mês" not in rotulos and "Porte" in rotulos
    assert item["sessoes"][0]["dados"][0]["quadro"]["rotulo"] == "970×250"


def test_vitrine_de_formatos_agrupa_por_canal_e_por_tipo(monkeypatch):
    from aicentralv2.area_cliente import descobrir
    fake = [{"id": 1, "name": "Search", "platform": "Google Ads", "platform_logo": "/g.png", "family": "Performance", "family_order": 8, "purpose": "Conversão"},
            {"id": 2, "name": "Billboard", "platform": "Programática (IAB)", "platform_logo": "/static/images/canais/programatica.svg",
             "family": "Display", "family_order": 1, "dimensions": "970x250", "purpose": "Alcance"},
            {"id": 3, "name": "Half Page", "platform": "Programática (IAB)", "platform_logo": "/p.svg", "family": "Display", "family_order": 1, "dimensions": "300x600"}]

    class Repo:
        @staticmethod
        def catalog(secao, busca):
            return [r for r in fake if busca.lower() in r["name"].lower()]
    monkeypatch.setattr(descobrir, "_repo", lambda: Repo)
    v = descobrir.vitrine_formatos("formatos")
    assert [g["titulo"] for g in v["grupos"]] == ["Programática (IAB)", "Google Ads"] and v["total"] == 3
    assert v["grupos"][0]["cartoes"][0]["quadro"]["rotulo"] == "970×250"
    assert [c["valor"] for c in v["chips"]] == ["Programática (IAB)", "Google Ads"]
    v = descobrir.vitrine_formatos("formatos", visao="tipo")
    assert [g["titulo"] for g in v["grupos"]] == ["Display", "Performance"]
    v = descobrir.vitrine_formatos("formatos", canal="Google Ads")
    assert v["total"] == 1 and len(v["chips"]) == 2


def test_descobrir_sem_pagina_geral_abre_canais(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    from aicentralv2.area_cliente import dados
    monkeypatch.setattr(dados, "listar_projetos", lambda cliente_id, busca="": [])
    client = _client(app, {"user_id": 501})
    resp = client.get("/descobrir", base_url=HOST)
    assert resp.status_code == 302 and resp.headers["Location"] == "/descobrir/canais"
    assert "Ver tudo" not in client.get("/", base_url=HOST).get_data(as_text=True)


def test_quadro_ignora_medida_zero():
    from aicentralv2.area_cliente.ficha import _quadro
    assert _quadro("00x250") is None and _quadro("300x250")["rotulo"] == "300×250"


def test_demo_de_formato_so_aceita_http():
    from aicentralv2.area_cliente.ficha import _url_web
    assert _url_web("javascript:alert(1)") == "" and _url_web(" https://ads.centralcomm.media/x ") == "https://ads.centralcomm.media/x"
