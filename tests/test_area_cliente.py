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
    assert "Olá, Ana" in html
    assert "Nenhum projeto ainda" in html
    assert 'href="/projetos"' in html
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
    resp = _client(app, {"user_id": 501}).get("/projetos/12", base_url=HOST)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    for trecho in ("PI Verão", "Visão 360°", "Campanha Verão", "1.000", "PI assinado", "Cronograma"):
        assert trecho in html
    assert "R$" not in html


def test_pagina_em_preparacao(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    client = _client(app, {"user_id": 501})
    resp = client.get("/relatorios", base_url=HOST)
    assert resp.status_code == 200 and "Em preparação" in resp.get_data(as_text=True)
    antigo = client.get("/planejamento", base_url=HOST)
    assert antigo.status_code == 301 and antigo.headers["Location"] == "/descobrir"


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
    assert resp.headers["Location"] == "/descobrir"
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
    monkeypatch.setattr(catalog, "client_detail", lambda kind, value: {
        "name": "Executivos", "description": "Líderes", "audience": "992K", "channel": "LinkedIn", "category": "B2B",
        "data_groups": [
            {"title": "Público, perfil e comportamento", "fields": [{"label": "Idade", "value": "30-50", "variable": "idade"}]},
            {"title": "Indicadores estimados", "fields": [{"label": "CPA mínimo", "value": "R$ 10", "variable": "cpa_estimado_min"}]},
        ]})
    item = descobrir.detalhe("audiencias", 3)
    assert [g["titulo"] for g in item["grupos"]] == ["Público, perfil e comportamento"]
    assert "R$" not in str(item)


def test_tirar_item_por_fetch_responde_204(app, monkeypatch):
    _logado(monkeypatch, _usuario())
    client = _client(app, {"user_id": 501, "area_cliente_csrf": "tok",
                           "area_cliente_descobrir": [["canais", 5, "Uber Ads"]]})
    resp = client.post("/descobrir/selecao", base_url=HOST, headers={"X-Requested-With": "fetch"},
                       data={"csrf": "tok", "secao": "canais", "id": "5"})
    assert resp.status_code == 204
    with client.session_transaction(base_url=HOST) as sess:
        assert sess["area_cliente_descobrir"] == []


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
    for trecho in ("R$ 10.000,00", "R$ 2.000,00", "R$ 8.000,00", "R$ 7.500,00", "NF Emitida", "Previsto 03/12/2026", "Em faturamento"):
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
    assert "Você está vendo a Área do Cliente como <b>AGÊNCIA X</b>" in html and "Voltar para CENTRALCOMM" in html
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
