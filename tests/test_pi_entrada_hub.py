"""Enviar PI pelo hub de mídia: o que o cliente vê (e não vê), o fluxo de envio ao executivo e o isolamento entre contas. Sem banco."""

import io
import json
import os
from datetime import datetime, timezone

os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "1")

import pytest

from aicentralv2.area_cliente import emails, pi_envio
from aicentralv2.pi_entrada import cadastro, esquema, hub, repositorio, servico
from tests.shared_app import get_app
from tests.test_pi_entrada_leitura import CNPJ_AGENCIA, CNPJ_CLIENTE, resposta_modelo

HOST = "http://clientes.test"
UUID = "11111111-1111-1111-1111-111111111111"


def pi_completo():
    pi = esquema.normalizar_extracao(resposta_modelo(extenso="dez mil reais"))
    pi["pagamento"].update({"prazo": "60 dias após o envio da NF", "centro_custos": "ODE-26-001841", "help_desk": "2500",
                            "responsavel_cliente": "MARIANA COSTA", "emails_faturamento": ["faturamento@agencia.exemplo"],
                            "regras": ["Nota fiscal pelo valor líquido do PI."]})
    pi["cliente"].update({"endereco": "AV DO CONTORNO, 4265", "inscricao_estadual": "623221310098", "telefone": "3195-6342"})
    for i in range(2, 12):
        pi["linhas"].append({**pi["linhas"][0], "praca": f"Cidade {i}", "plataforma": "META ADS" if i % 2 else "LINKEDIN ADS"})
    return pi


# ---------- o que o cliente vê ----------

def test_resumo_do_cliente_nao_vaza_dados_da_visao_completa():
    resumo = hub.resumo_para_cliente(pi_completo())
    assert set(resumo) == hub.CAMPOS_PERMITIDOS                                  # só a lista permitida, nada a mais
    texto = json.dumps(resumo, ensure_ascii=False)
    for proibido in ("2000.00", "2.000,00", "8.000,00", "8000.00", CNPJ_CLIENTE, CNPJ_AGENCIA, "12.315.950", "CONTORNO", "623221310098",
                     "ODE-26-001841", "MARIANA", "faturamento@", "valor líquido", "comissao", "3195-6342", "2500"):
        assert proibido not in texto, proibido
    assert resumo["numero_pi"] == "86761" and resumo["total_bruto"] == "R$ 10.000,00" and resumo["n_linhas"] == 11


def test_resumo_limita_listas_e_nao_mostra_total_que_o_pdf_nao_traz():
    pi = pi_completo()
    pi["totais"]["bruto"] = ""
    resumo = hub.resumo_para_cliente(pi)
    assert resumo["total_bruto"] == ""
    assert len(resumo["pracas"]) == hub.MAX_PRACAS and resumo["pracas_mais"] == 5 and len(resumo["linhas"]) == hub.MAX_LINHAS and resumo["linhas_mais"] == 3
    assert set(resumo["plataformas"]) == {"Amazon Música", "META ADS", "LINKEDIN ADS"}
    assert hub.resumo_para_cliente({})["n_linhas"] == 0                          # PI vazio não quebra


def test_situacao_para_o_cliente():
    assert hub.situacao({"status": "recebido"}) == "lendo" and hub.situacao({"status": "lendo"}) == "lendo"
    assert hub.situacao({"status": "erro"}) == "erro" and hub.situacao({"status": "lido"}) == "pronto"
    assert hub.situacao({"status": "lido", "enviado_em": datetime.now(timezone.utc)}) == "enviado"


# ---------- rotas do hub ----------

class Memoria:
    def __init__(self):
        self.entradas = {}
        self.criadas, self.iniciadas, self.enviados, self.emails = [], [], [], []
        self.recentes = 0


@pytest.fixture()
def mem(monkeypatch):
    m = Memoria()
    pi = pi_completo()
    m.entradas[UUID] = {"id": 7, "uuid": UUID, "origem": "hub", "status": "lido", "id_cliente_envio": 900, "id_contato_envio": 501, "numero_pi": "86761",
                        "titulo": "Campanha", "json_revisado": pi, "enviado_em": None, "mensagem_cliente": None, "erro": None,
                        "criado_em": datetime.now(timezone.utc)}
    monkeypatch.setattr(repositorio, "obter_por_uuid", lambda u: m.entradas.get(u))
    monkeypatch.setattr(repositorio, "obter", lambda i: next((e for e in m.entradas.values() if e["id"] == i), None))
    monkeypatch.setattr(repositorio, "enviadas_pelo_cliente", lambda c, limite=10: [{**e, "nome_original": "pi.pdf"} for e in m.entradas.values() if e["id_cliente_envio"] == c])
    monkeypatch.setattr(repositorio, "contar_envios_recentes", lambda c, minutos=60: m.recentes)
    monkeypatch.setattr(repositorio, "entrada_por_sha", lambda sha: None)

    def criar(origem, **k):
        m.criadas.append((origem, k))
        novo = {"id": 8, "uuid": "22222222-2222-2222-2222-222222222222", "origem": origem, "status": "recebido", "id_cliente_envio": k["id_cliente_envio"],
                "enviado_em": None, "json_revisado": None, "erro": None, "criado_em": datetime.now(timezone.utc)}
        m.entradas[novo["uuid"]] = novo
        return 8
    monkeypatch.setattr(repositorio, "criar_entrada", criar)
    monkeypatch.setattr(repositorio, "registrar_arquivo", lambda *a, **k: None)

    def marcar(i, mensagem=None):
        entrada = next(e for e in m.entradas.values() if e["id"] == i)
        if entrada["status"] != "lido" or entrada["enviado_em"]:
            return False
        entrada["enviado_em"], entrada["mensagem_cliente"] = datetime.now(timezone.utc), mensagem
        m.enviados.append((i, mensagem))
        return True
    monkeypatch.setattr(repositorio, "marcar_enviado", marcar)
    monkeypatch.setattr(servico, "guardar_arquivo", lambda i, nome, c: {"sha256": "c" * 64, "caminho": "/tmp/y", "tamanho": len(c)})
    monkeypatch.setattr(servico, "iniciar_em_segundo_plano", lambda i: m.iniciadas.append(i))
    monkeypatch.setattr(cadastro, "executivo_da_conta", lambda c: 7)
    monkeypatch.setattr(emails, "pi_recebido", lambda *a, **k: m.emails.append(("recebido", a)) or True)
    monkeypatch.setattr(emails, "pi_enviado", lambda *a, **k: m.emails.append(("enviado", a)) or True)
    return m


def usuario(**extra):
    base = {"user_id": 501, "nome": "Ana Souza", "primeiro_nome": "Ana", "iniciais": "AS", "email": "ana@cliente.test", "foto_url": "", "cliente_id": 900,
            "cliente_nome": "Cliente Teste", "liberado": True,
            "executivo": {"nome": "João Lima", "email": "joao@centralcomm.media", "whatsapp": "https://wa.me/5531999990000", "foto_url": ""}}
    return {**base, **extra}


@pytest.fixture()
def hub_http(mem, monkeypatch):
    app = get_app()
    app.config["TESTING"] = True
    app.config["CLIENTES_URL"] = HOST
    from aicentralv2.area_cliente import acesso
    from aicentralv2.cadu_connect import reports_access
    monkeypatch.setattr(reports_access, "reports_only", lambda *a, **k: False)
    atual = {"u": usuario()}
    monkeypatch.setattr(acesso, "contexto_usuario", lambda user_id: atual["u"])
    cliente = app.test_client()
    with cliente.session_transaction(base_url=HOST) as sess:
        sess.update({"user_id": 501, "area_cliente_csrf": "tok"})
    cliente.usuario = atual
    return cliente


def pdf(nome="pi.pdf"):
    return (io.BytesIO(b"%PDF-1.4 conteudo"), nome)


def test_pagina_de_enviar_mostra_dropzone_executivo_e_o_botao_em_pis(hub_http, mem):
    html = hub_http.get("/pis/enviar", base_url=HOST).get_data(as_text=True)
    assert "Enviar um PI" in html and 'id="pe-drop"' in html and 'data-csrf="tok"' in html and "João" in html
    assert "Enviados por você" in html and "86761" in html


def test_upload_exige_csrf_valida_pdf_cria_entrada_do_hub_e_comeca_a_ler(hub_http, mem):
    sem = hub_http.post("/pis/enviar", base_url=HOST, data={"arquivos": pdf()}, content_type="multipart/form-data")
    assert sem.status_code == 400 and not mem.criadas
    ok = hub_http.post("/pis/enviar", base_url=HOST, data={"csrf": "tok", "arquivos": pdf()}, content_type="multipart/form-data")
    corpo = ok.get_json()
    assert ok.status_code == 200 and corpo["ok"] and corpo["entradas"][0]["url"].endswith("/pis/enviados/22222222-2222-2222-2222-222222222222")
    origem, dados = mem.criadas[0]
    assert origem == "hub" and dados["id_cliente_envio"] == 900 and dados["id_contato_envio"] == 501 and dados["id_executivo"] == 7 and mem.iniciadas == [8]
    ruim = hub_http.post("/pis/enviar", base_url=HOST, data={"csrf": "tok", "arquivos": (io.BytesIO(b"nao e pdf"), "x.pdf")}, content_type="multipart/form-data")
    assert ruim.get_json()["entradas"][0]["erro"] == "Envie o PI em PDF." and mem.iniciadas == [8]
    assert hub_http.post("/pis/enviar", base_url=HOST, data={"csrf": "tok"}, content_type="multipart/form-data").status_code == 400


def test_limite_por_hora_e_visao_como_cliente_bloqueiam_o_envio(hub_http, mem):
    mem.recentes = 10
    assert hub_http.post("/pis/enviar", base_url=HOST, data={"csrf": "tok", "arquivos": pdf()}, content_type="multipart/form-data").status_code == 429
    mem.recentes = 0
    hub_http.usuario["u"] = usuario(ver_como=True)
    bloqueado = hub_http.post("/pis/enviar", base_url=HOST, data={"csrf": "tok", "arquivos": pdf()}, content_type="multipart/form-data")
    assert bloqueado.status_code == 403 and not mem.criadas
    assert hub_http.post(f"/pis/enviados/{UUID}/enviar", base_url=HOST, data={"csrf": "tok"}).status_code == 403
    assert "desligado" in hub_http.get("/pis/enviar", base_url=HOST).get_data(as_text=True)


def test_pagina_do_pi_lido_mostra_resumo_sem_vazar_e_o_formulario_de_envio(hub_http, mem):
    html = hub_http.get(f"/pis/enviados/{UUID}", base_url=HOST).get_data(as_text=True)
    assert "O que entendi" in html and "86761" in html and "R$ 10.000,00" in html and "Enviar para João" in html
    assert "wa.me/5531999990000" in html and 'name="csrf" value="tok"' in html
    for proibido in ("8.000,00", "2.000,00", CNPJ_CLIENTE, CNPJ_AGENCIA, "ODE-26-001841", "MARIANA", "623221310098", "Nota fiscal pelo valor líquido"):
        assert proibido not in html, proibido


def test_estados_lendo_erro_e_isolamento_entre_contas(hub_http, mem):
    mem.entradas[UUID]["status"] = "lendo"
    html = hub_http.get(f"/pis/enviados/{UUID}", base_url=HOST).get_data(as_text=True)
    assert 'data-estado="lendo"' in html and "Lendo o seu PI" in html
    assert hub_http.get(f"/pis/enviados/{UUID}/status", base_url=HOST).get_json() == {"ok": True, "estado": "lendo", "pronto": False}
    mem.entradas[UUID].update(status="erro", erro="O PDF tem senha.")
    html = hub_http.get(f"/pis/enviados/{UUID}", base_url=HOST).get_data(as_text=True)
    assert "Não consegui ler este PI" in html and "O PDF tem senha." in html and "Enviar de novo" in html
    mem.entradas[UUID]["id_cliente_envio"] = 999                                    # entrada de outra conta
    assert hub_http.get(f"/pis/enviados/{UUID}", base_url=HOST).status_code == 404
    assert hub_http.get(f"/pis/enviados/{UUID}/status", base_url=HOST).status_code == 404
    assert hub_http.post(f"/pis/enviados/{UUID}/enviar", base_url=HOST, data={"csrf": "tok"}).status_code == 404
    mem.entradas[UUID].update(id_cliente_envio=900, origem="centralx")             # entrada da equipe nunca aparece no hub
    assert hub_http.get(f"/pis/enviados/{UUID}", base_url=HOST).status_code == 404
    assert hub_http.get("/pis/enviados/nao-existe", base_url=HOST).status_code == 404


def test_enviar_ao_executivo_marca_avisa_uma_vez_e_exige_csrf(hub_http, mem):
    url = f"/pis/enviados/{UUID}/enviar"
    assert hub_http.post(url, base_url=HOST, data={"mensagem": "urgente"}).status_code == 400            # sem token
    resposta = hub_http.post(url, base_url=HOST, data={"csrf": "tok", "mensagem": "Já tem cotação aprovada."})
    assert resposta.status_code == 303 and resposta.headers["Location"].endswith(f"/pis/enviados/{UUID}?enviado=1")
    assert mem.enviados == [(7, "Já tem cotação aprovada.")] and [e[0] for e in mem.emails] == ["recebido", "enviado"]
    interno = dict(mem.emails[0][1][1])
    assert "total_bruto" in interno and "comissao" not in json.dumps(interno)                              # o e-mail usa o mesmo resumo permitido
    de_novo = hub_http.post(url, base_url=HOST, data={"csrf": "tok"})
    assert de_novo.status_code == 303 and len(mem.enviados) == 1 and len(mem.emails) == 2                 # não avisa duas vezes
    html = hub_http.get(f"/pis/enviados/{UUID}?enviado=1", base_url=HOST).get_data(as_text=True)
    assert "seguiu para João" in html and "Já tem cotação aprovada." in html and "Enviar para João" not in html


def test_envio_nao_acontece_se_a_leitura_nao_terminou(hub_http, mem):
    mem.entradas[UUID]["status"] = "lendo"
    hub_http.post(f"/pis/enviados/{UUID}/enviar", base_url=HOST, data={"csrf": "tok"})
    assert mem.enviados == [] and mem.emails == []


def test_falha_de_email_nao_desfaz_o_envio(hub_http, mem, monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError("Brevo fora do ar")
    monkeypatch.setattr(emails, "pi_recebido", quebra)
    resposta = hub_http.post(f"/pis/enviados/{UUID}/enviar", base_url=HOST, data={"csrf": "tok"})
    assert resposta.status_code == 303 and len(mem.enviados) == 1                    # o envio valeu; só o aviso falhou


def test_pagina_de_pis_ganha_o_botao_enviar_um_pi(hub_http, monkeypatch):
    from aicentralv2.area_cliente import dados
    monkeypatch.setattr(dados, "listar_pis", lambda cliente_id: [])
    monkeypatch.setattr(dados, "campanhas_dos_pis", lambda ids: [])
    html = hub_http.get("/pis", base_url=HOST).get_data(as_text=True)
    assert "Enviar um PI" in html and "/pis/enviar" in html


# ---------- e-mails ----------

def test_emails_do_pi_enviado(app_emails, monkeypatch):
    enviados = []
    monkeypatch.setattr(emails, "_enviar", lambda modelo, para, nome, assunto, ctx, reply_to=None, remetente_nome=None: enviados.append((modelo, para, assunto, ctx, reply_to, remetente_nome)) or True)
    u = usuario()
    resumo = hub.resumo_para_cliente(pi_completo())
    with app_emails.test_request_context("/", base_url=HOST):
        emails.pi_enviado(u, resumo)
        emails.pi_recebido(u, resumo, 7, "Pode seguir?")
        html_cliente = emails.renderizar(enviados[0][0], **enviados[0][3])
        html_interno = emails.renderizar(enviados[1][0], **enviados[1][3])
    cliente, interno = enviados
    assert cliente[0] == "pi-enviado" and cliente[1] == "ana@cliente.test" and cliente[2] == "Ana, o PI 86761 seguiu para João" and cliente[5] == "João da Centralcomm"
    assert interno[0] == "pi-recebido" and interno[1] == "joao@centralcomm.media" and interno[2] == "PI 86761 enviado por Cliente Teste"
    assert interno[3]["link_entrada"].endswith("/pi-entrada/7") and interno[4] == {"name": "Ana Souza", "email": "ana@cliente.test"}
    assert "Pode seguir?" in html_interno and "Verificar no CentralX" in html_interno and "Área do Cliente" not in html_cliente + html_interno
    assert "O PI 86761 seguiu para João" in html_cliente and "8.000,00" not in html_cliente + html_interno


@pytest.fixture()
def app_emails():
    app = get_app()
    app.config["TESTING"] = True
    app.config["CLIENTES_URL"] = HOST
    return app
