"""Modo demonstração da conta 174: PIs e campanhas fictícios e envios simulados, sem tocar no banco nem mandar e-mail."""

import io

import pytest

from aicentralv2.area_cliente import briefing, cotacao, dados, demo, emails
from tests.shared_app import get_app
from tests.test_pi_entrada_hub import HOST, usuario


def pytest_nada_no_banco(*a, **k):
    pytest.fail("o modo demonstração não pode consultar nem gravar no banco")


@pytest.fixture()
def conta174(monkeypatch):
    app = get_app()
    app.config.update(TESTING=True, CLIENTES_URL=HOST)
    app.config.pop("HUB_DEMO_CLIENTE_ID", None)
    from aicentralv2.area_cliente import acesso
    from aicentralv2.cadu_connect import reports_access
    from aicentralv2.pi_entrada import repositorio
    monkeypatch.setattr(reports_access, "reports_only", lambda *a, **k: False)
    atual = {"u": usuario(cliente_id=174, cliente_nome="CENTRALCOMM")}
    monkeypatch.setattr(acesso, "contexto_usuario", lambda uid: atual["u"])
    # o que o banco responderia para ids que não existem: nada. Se algo consultar por conta própria, o teste enxerga.
    consultas = []
    monkeypatch.setattr(dados, "_fetch", lambda sql, params: consultas.append(params) or [])
    for nome in ("criar_entrada", "registrar_arquivo", "marcar_enviado", "obter_por_uuid", "enviadas_pelo_cliente", "contar_envios_recentes"):
        monkeypatch.setattr(repositorio, nome, pytest_nada_no_banco)
    monkeypatch.setattr(briefing, "enviar", pytest_nada_no_banco)
    for nome in ("criar_rascunho", "definir_arquivos", "reservar", "marcar_enviado"):
        monkeypatch.setattr(cotacao, nome, pytest_nada_no_banco)
    for nome in ("briefing_novo", "briefing_recebido", "pi_recebido", "pi_enviado"):
        monkeypatch.setattr(emails, nome, pytest_nada_no_banco)
    monkeypatch.setattr(demo, "ESPERA_LEITURA", 0)
    c = app.test_client()
    with c.session_transaction(base_url=HOST) as s:
        s.update({"user_id": 501, "area_cliente_csrf": "tok"})
    c.consultas, c.usuario, c.app = consultas, atual, app
    return c


def pagina(c, url):
    r = c.get(url, base_url=HOST)
    assert r.status_code == 200, (url, r.status_code)
    return r.get_data(as_text=True)


def test_dados_de_demonstracao_so_para_a_conta_certa(monkeypatch):
    app = get_app()
    with app.test_request_context("/", base_url=HOST):
        projetos = dados.listar_projetos(174)
        assert len(projetos) == 5 and {p["status"] for p in projetos} == {"Em andamento", "Finalizado"}
        assert sum(1 for p in projetos if p["ativo"]) == 2 and all(demo.eh_pi_demo(p["id"]) for p in projetos)
        assert sum(1 for p in projetos for c in p["campanhas"] if c["no_ar"]) == 5
        assert len(dados.campanhas_dos_pis([p["id"] for p in projetos])) == sum(p["n_campanhas"] for p in projetos)
        assert not demo.ativo(80) and not demo.ativo(None)
        app.config["HUB_DEMO_CLIENTE_ID"] = 0
        assert not demo.ativo(174)
        app.config.pop("HUB_DEMO_CLIENTE_ID")
        # outro cliente continua indo ao banco
        monkeypatch.setattr(dados, "_fetch", lambda sql, params: [])
        assert dados.listar_projetos(80) == []


def test_telas_da_conta_174_mostram_os_cinco_pis_e_campanhas(conta174):
    inicio = pagina(conta174, "/")
    assert "ac-modo-demo" in inicio and "Lançamento Coleção Verão" in inicio and "Ao vivo" in inicio and ">Plataformas<" in inicio
    pis = pagina(conta174, "/pis")
    assert pis.count("DEMO-00") >= 2 and "Black Friday Varejo" in pis
    assert "Dia das Mães" in pagina(conta174, "/pis?status=finalizados") and "Dia das Mães" not in pis
    camp = pagina(conta174, "/campanhas")
    assert "Alcance · Redes sociais" in camp and "Meta Ads" in camp
    rel = pagina(conta174, "/relatorios")
    assert "Lançamento Coleção Verão" in rel
    pi = pagina(conta174, f"/pis/{demo.BASE_ID + 3}")
    assert "Dia das Mães" in pi and "Pagamento" in pi
    assert pagina(conta174, f"/pis/{demo.BASE_ID + 1}")
    assert "Coleção de verão 2027" in pagina(conta174, "/briefing/todos")
    # tudo o que foi ao "banco" foi consulta de leitura por ids de demonstração (ou nada)
    assert all(not isinstance(p, tuple) or all(not isinstance(x, list) or all(demo.eh_pi_demo(i) for i in x) for x in p) for p in conta174.consultas)


def test_pi_enviado_na_demonstracao_le_mostra_e_envia_sem_gravar(conta174):
    r = conta174.post("/pis/enviar", base_url=HOST, data={"csrf": "tok", "arquivos": (io.BytesIO(b"%PDF-1.4 x"), "PI cliente.pdf")}, content_type="multipart/form-data")
    url = r.get_json()["entradas"][0]["url"]
    assert url.startswith("/pis/enviados/demo-")
    assert conta174.get(url + "/status", base_url=HOST).get_json()["estado"] == "pronto"
    html = pagina(conta174, url)
    assert "O que entendi" in html and "DEMO-0451" in html and "Enviar para João" in html
    assert "Comissão" not in html and "CNPJ" not in html
    assert conta174.post(url + "/enviar", base_url=HOST, data={"csrf": "tok", "mensagem": "Teste"}).status_code == 303
    assert "seguiu para João" in pagina(conta174, url + "?enviado=1")
    assert "PI cliente.pdf" in pagina(conta174, "/pis/enviar")
    ruim = conta174.post("/pis/enviar", base_url=HOST, data={"csrf": "tok", "arquivos": (io.BytesIO(b"x"), "a.exe")}, content_type="multipart/form-data")
    assert "PDF" in ruim.get_json()["entradas"][0]["erro"]


def test_cotacao_e_planejamento_na_demonstracao(conta174):
    r = conta174.post("/briefing/cotacao", base_url=HOST, data={"csrf": "tok", "arquivos": (io.BytesIO(b"a;b"), "plano.csv")}, content_type="multipart/form-data")
    url = r.get_json()["entradas"][0]["url"]
    html = pagina(conta174, url)
    assert "Li os seus arquivos" in html and "Campanha de verão 2027" in html and "Não achei nos arquivos" in html
    corpo = {"csrf": "tok", "titulo": "Campanha de verão 2027", "objetivo": "Vender a nova coleção de verão"}
    assert conta174.post(url + "/enviar", base_url=HOST, data=corpo).status_code == 303
    assert "seguiu para João" in pagina(conta174, url + "?enviado=1")
    # planejamento com anexo
    a = conta174.post("/briefing/anexo", base_url=HOST, data={"csrf": "tok", "arquivos": (io.BytesIO(b"%PDF-1.4"), "b.pdf")}, content_type="multipart/form-data").get_json()
    assert a["uuid"].startswith("demo-") and conta174.get(a["dados_url"], base_url=HOST).get_json()["leitura"]["pracas"]
    env = conta174.post("/briefing/planejamento", base_url=HOST, data={**corpo, "titulo": "Do planejamento", "anexo": a["uuid"]})
    assert env.status_code == 303 and env.headers["Location"].startswith("/briefing?enviado=")
    todos = pagina(conta174, "/briefing/todos")
    assert "Do planejamento" in todos and "Campanha de verão 2027" in todos


def test_conta_demo_desligada_volta_ao_banco(conta174, monkeypatch):
    conta174.app.config["HUB_DEMO_CLIENTE_ID"] = 0
    try:
        monkeypatch.setattr(dados, "listar_projetos", lambda c, busca="", id_pi=None: [])
        assert "ac-modo-demo" not in pagina(conta174, "/")
    finally:
        conta174.app.config.pop("HUB_DEMO_CLIENTE_ID", None)
