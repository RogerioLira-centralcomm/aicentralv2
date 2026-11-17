"""Entrada de PI: rotas, permissões, página de verificação e travas de justificativa. Sem banco (tudo simulado)."""

import io
import json
import os

os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "1")

import pytest

from aicentralv2.pi_entrada import cadastro, esquema, repositorio, routes, servico
from tests.shared_app import get_app
from tests.test_pi_entrada_leitura import resposta_modelo

EXECUTIVO = {"user_id": 7, "cliente_id": 1, "user_type": "admin", "is_centralcomm": True, "user_name": "Executivo"}
CLIENTE_EXTERNO = {"user_id": 501, "cliente_id": 900, "user_type": "admin", "is_centralcomm": False, "user_name": "Ana"}


class Banco:
    """Repositório e cadastro em memória."""

    def __init__(self):
        self.entradas, self.ajustes, self.arquivos, self.iniciadas = {}, {}, {}, []
        pi = esquema.normalizar_extracao(resposta_modelo(extenso="dez mil reais"))
        self.entradas[1] = {"id": 1, "status": "lido", "numero_pi": "86761", "titulo": "Campanha", "origem": "centralx", "metodo_leitura": "texto",
                            "confianca": 0.95, "cotacao_id": None, "id_executivo": 7, "json_extraido": {"pi": pi, "bruto": {"texto_divergente": [], "texto_conferido": True}},
                            "json_revisado": pi, "conferencias": {"erro": 0, "oportunidades": 1}, "erro": None, "rascunho": None}
        self.cotacao = {"id": 228, "numero_cotacao": "COT-1", "nome_campanha": "INSTITUCIONAL SEGUNDO SEMESTRE", "periodo_inicio": "2026-11-01", "periodo_fim": "2026-11-30",
                        "status": "Aprovada", "valor_total_proposta": 10000, "plataforma_campanha": "Programática", "tipo_de_contrato": "operacao_propria",
                        "linhas": [{"plataforma": "Amazon Música", "formatos": "Jingle", "objetivo_kpi": "CPM", "praca": "MG, PA, Salvador e SP", "volume_contratado": 163425,
                                    "valor_unitario_negociado": 61.1875, "investimento_bruto": 10000, "investimento_liquido": 8000}]}


@pytest.fixture()
def banco(monkeypatch):
    b = Banco()
    # A barra do ERP consulta o banco (conta "só Reports", saldo de créditos): simula como nos testes de papéis.
    from aicentralv2 import db
    from aicentralv2.cadu_connect import reports_access
    from aicentralv2.cadu_skills import repository as skills_repo
    monkeypatch.setattr(db, "obter_contato_por_id", lambda uid: {"id_contato_cliente": uid, "pk_id_tbl_cliente": 1})
    monkeypatch.setattr(db, "obter_cliente_por_id", lambda cid: {"id_cliente": cid, "nome_fantasia": "CENTRALCOMM", "status": True})
    monkeypatch.setattr(reports_access, "reports_only", lambda *a, **k: False)
    monkeypatch.setattr(skills_repo, "_credit_position", lambda *a, **k: {"granted": 0, "used": 0, "available": 0})
    monkeypatch.setattr(repositorio, "obter", lambda i: b.entradas.get(i))
    monkeypatch.setattr(repositorio, "listar", lambda *a, **k: [{**e, "cliente_nome": "CLIENTE EXEMPLO", "nome_original": "pi.pdf", "executivo_nome": "Executivo",
                                                               "criado_em": None, "resumo": e["conferencias"]} for e in b.entradas.values()])
    monkeypatch.setattr(repositorio, "ajustes", lambda i: list(b.ajustes.get(i, {}).values()))
    monkeypatch.setattr(repositorio, "registrar_ajuste", lambda i, **k: b.ajustes.setdefault(i, {}).__setitem__(k["campo"], k))
    monkeypatch.setattr(repositorio, "salvar_revisado", lambda i, pi: b.entradas[i].__setitem__("json_revisado", pi))
    monkeypatch.setattr(repositorio, "definir_cotacao", lambda i, c: b.entradas[i].__setitem__("cotacao_id", c))
    monkeypatch.setattr(repositorio, "aprovar", lambda i, u, r: b.entradas[i].update(status="rascunho", rascunho=r))
    monkeypatch.setattr(repositorio, "entrada_por_sha", lambda sha: None)
    monkeypatch.setattr(repositorio, "criar_entrada", lambda *a, **k: 2)
    monkeypatch.setattr(repositorio, "registrar_arquivo", lambda *a, **k: None)
    monkeypatch.setattr(repositorio, "arquivo_da_entrada", lambda i: None)
    monkeypatch.setattr(servico, "guardar_arquivo", lambda i, nome, c: {"sha256": "b" * 64, "caminho": "/tmp/x", "tamanho": len(c)})
    monkeypatch.setattr(servico, "iniciar_em_segundo_plano", lambda i: b.iniciadas.append(i))
    monkeypatch.setattr(cadastro, "contexto", lambda pi: {"cliente": {"id_cliente": 9, "razao_social": "CLIENTE EXEMPLO S.A.", "cep": "", "cidade": ""},
                                                          "agencia": {"id_cliente": 80, "razao_social": "AGENCIA EXEMPLO LTDA"}, "cliente_id": 9, "agencia_id": 80,
                                                          "executivo_id": 7, "pi_existente": None, "emails": {"cliente": set(), "agencia": set()}, "observacoes": {"cliente": ""}})
    monkeypatch.setattr(cadastro, "cotacoes_do_cliente", lambda *a, **k: [{k_: v for k_, v in b.cotacao.items() if k_ != "linhas"}])
    monkeypatch.setattr(cadastro, "cotacao_completa", lambda i: b.cotacao if i == 228 else None)
    return b


@pytest.fixture()
def http(banco):
    app = get_app()
    app.config["TESTING"] = True
    cliente = app.test_client()
    with cliente.session_transaction() as sess:
        sess.update(EXECUTIVO)
    return cliente


def test_so_a_equipe_centralcomm_acessa(banco):
    app = get_app()
    externo = app.test_client()
    with externo.session_transaction() as sess:
        sess.update(CLIENTE_EXTERNO)
    for caminho in ("/pi-entrada/", "/pi-entrada/1", "/pi-entrada/1/rascunho"):
        assert externo.get(caminho).status_code == 302
    assert externo.post("/pi-entrada/upload").status_code == 403
    assert externo.post("/pi-entrada/1/ajustes", json={"itens": []}).status_code == 403
    assert app.test_client().get("/pi-entrada/").status_code == 302                    # sem login


def test_fila_lista_as_entradas(http):
    html = http.get("/pi-entrada/").get_data(as_text=True)
    assert "Entrada de PI automática" in html and "86761" in html and "CLIENTE EXEMPLO" in html and "1 p/ cadastro" in html
    assert 'id="pie-drop"' in html


def test_upload_aceita_pdf_rejeita_outros_e_dispara_a_leitura(http, banco):
    ok = http.post("/pi-entrada/upload", data={"arquivos": (io.BytesIO(b"%PDF-1.4 conteudo"), "pi.pdf")}, content_type="multipart/form-data")
    assert ok.status_code == 200 and ok.get_json()["entradas"][0]["id"] == 2 and banco.iniciadas == [2]
    ruim = http.post("/pi-entrada/upload", data={"arquivos": (io.BytesIO(b"nao e pdf"), "pi.pdf")}, content_type="multipart/form-data")
    assert ruim.get_json()["entradas"][0]["erro"] == "Só aceito arquivos PDF." and banco.iniciadas == [2]
    assert http.post("/pi-entrada/upload").get_json()["erro"] == "Escolha ao menos um PDF."
    muitos = http.post("/pi-entrada/upload", data={"arquivos": [(io.BytesIO(b"%PDF-1"), f"{i}.pdf") for i in range(11)]}, content_type="multipart/form-data")
    assert muitos.status_code == 400


def test_pagina_de_verificacao_compara_pi_e_cotacao(http, banco):
    banco.entradas[1]["cotacao_id"] = 228
    html = http.get("/pi-entrada/1").get_data(as_text=True)
    assert "PI lido × cotação" in html and "Valor bruto" in html and "R$ 10.000,00" in html
    assert "Conferências do documento" in html and "Soma das linhas = total bruto" in html
    assert "Cadastro: oportunidades" in html and "Preparar entrada do PI" in html
    assert 'data-caminho="totais.bruto"' in html and 'data-caminho="linhas.1.valor_bruto"' in html          # campos editáveis
    assert "disabled" not in html.split('id="pie-aprovar"')[1].split(">")[0]                                  # nada pendente: pode preparar


def test_cotacao_sugerida_e_aplicada_na_tela_sem_gravar(http, banco):
    assert banco.entradas[1]["cotacao_id"] is None
    html = http.get("/pi-entrada/1").get_data(as_text=True)
    assert "Confirmar esta cotação" in html and "Sugerida pelo valor" in html and banco.entradas[1]["cotacao_id"] is None


def test_divergencia_exige_justificativa_antes_de_preparar(http, banco):
    pi = banco.entradas[1]["json_revisado"]
    pi["valor_extenso_num"] = "42000"                      # o PI se contradiz: por extenso 42.000, numérico 10.000
    html = http.get("/pi-entrada/1").get_data(as_text=True)
    assert "Precisa de justificativa (1)" in html and "Valor por extenso" in html
    assert "disabled" in html.split('id="pie-aprovar"')[1].split(">")[0]
    bloqueado = http.post("/pi-entrada/1/aprovar")
    assert bloqueado.status_code == 302 and banco.entradas[1]["status"] == "lido"

    sem_motivo = http.post("/pi-entrada/1/ajustes", json={"itens": [{"campo": "conf:extenso", "tipo": "aceite", "motivo": "", "justificativa": "ok ok ok"}]})
    assert sem_motivo.status_code == 422 and "motivo" in sem_motivo.get_json()["erro"]
    curta = http.post("/pi-entrada/1/ajustes", json={"itens": [{"campo": "conf:extenso", "tipo": "aceite", "motivo": "erro_do_pi", "justificativa": "x"}]})
    assert curta.status_code == 422
    feito = http.post("/pi-entrada/1/ajustes", json={"itens": [{"campo": "conf:extenso", "tipo": "aceite", "motivo": "erro_do_pi", "justificativa": "O extenso está errado no PDF da agência."}]})
    assert feito.get_json() == {"ok": True, "salvos": 1}

    html = http.get("/pi-entrada/1").get_data(as_text=True)
    assert "Divergências justificadas" in html and "O extenso está errado" in html
    pronto = http.post("/pi-entrada/1/aprovar")
    assert pronto.status_code == 302 and pronto.headers["Location"].endswith("/pi-entrada/1/rascunho")
    rascunho = banco.entradas[1]["rascunho"]["campos"]
    assert banco.entradas[1]["status"] == "rascunho" and rascunho["codigo_pi_cc"] == "86761" and rascunho["valor_bruto"] == "10000.00"
    assert rascunho["id_cliente"] == 9 and rascunho["id_agencia"] == 80 and rascunho["resp_comercial"] == 7
    assert "86761" in http.get("/pi-entrada/1/rascunho").get_data(as_text=True)


def test_editar_campo_valida_o_valor_e_registra_o_ajuste(http, banco):
    item = {"campo": "totais.bruto", "tipo": "ajuste", "valor": "R$ 9.500,00", "motivo": "combinado_com_cliente", "justificativa": "Desconto combinado por telefone."}
    assert http.post("/pi-entrada/1/ajustes", json={"itens": [item]}).get_json()["ok"]
    assert banco.entradas[1]["json_revisado"]["totais"]["bruto"] == "9500.00"
    registro = banco.ajustes[1]["totais.bruto"]
    assert (registro["valor_lido"], registro["valor_final"], registro["motivo"]) == ("10000.00", "9500.00", "combinado_com_cliente")
    assert http.post("/pi-entrada/1/ajustes", json={"itens": [{**item, "valor": "abc"}]}).status_code == 422
    assert http.post("/pi-entrada/1/ajustes", json={"itens": [{**item, "campo": "status"}]}).status_code == 422          # campo não editável
    assert http.post("/pi-entrada/1/ajustes", json={"itens": [{**item, "campo": "linhas.99.valor_bruto"}]}).status_code == 422


def test_entrada_lendo_mostra_carregamento_e_erro_mostra_mensagem(http, banco):
    banco.entradas[3] = {**banco.entradas[1], "id": 3, "status": "lendo", "json_revisado": None, "json_extraido": None}
    assert 'data-carregando="1"' in http.get("/pi-entrada/3").get_data(as_text=True)
    banco.entradas[4] = {**banco.entradas[1], "id": 4, "status": "erro", "json_revisado": None, "erro": "O PDF tem senha."}
    html = http.get("/pi-entrada/4").get_data(as_text=True)
    assert "Não consegui ler este PI" in html and "O PDF tem senha." in html and "Ler de novo" in html
    assert http.get("/pi-entrada/3/status").get_json() == {"ok": True, "status": "lendo", "erro": None, "pronto": False}
    assert http.get("/pi-entrada/999").status_code == 404
