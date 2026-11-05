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
    resp = _client(app, {"user_id": 501}).get("/planejamento", base_url=HOST)
    assert resp.status_code == 200
    assert "Cadu Planner" in resp.get_data(as_text=True)


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
