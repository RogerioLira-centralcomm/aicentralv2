"""Briefing para cotação (hub, F6): prazo de 24 h, validação de arquivos, leitura pelo modelo e as telas."""

import io
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from aicentralv2.area_cliente import briefing, cotacao, emails
from tests.shared_app import get_app
from tests.test_pi_entrada_hub import HOST, usuario

FUSO = ZoneInfo("America/Sao_Paulo")


def local(*a):
    return datetime(*a, tzinfo=FUSO)


# ---------- prazo ----------

@pytest.mark.parametrize("envio,esperado", [
    (local(2026, 11, 17, 10, 0), local(2026, 11, 18, 10, 0)),      # terça 10h -> quarta 10h
    (local(2026, 11, 17, 18, 30), local(2026, 11, 19, 9, 0)),     # fim cai às 18h30 (depois do expediente) -> quinta 9h
    (local(2026, 11, 19, 10, 0), local(2026, 11, 20, 10, 0)),      # quinta 10h -> sexta 10h
    (local(2026, 11, 20, 11, 0), local(2026, 11, 23, 9, 0)),       # sexta 11h -> sábado 11h -> segunda 9h
    (local(2026, 11, 21, 15, 0), local(2026, 11, 23, 9, 0)),       # sábado -> domingo -> segunda 9h
    (local(2026, 11, 17, 6, 0), local(2026, 11, 18, 9, 0)),        # terça 6h -> quarta 6h, antes de abrir -> quarta 9h
])
def test_prazo_de_24h_cai_sempre_em_horario_util(envio, esperado):
    assert cotacao.prazo_resposta(envio).astimezone(FUSO) == esperado


def test_prazo_texto():
    assert cotacao.prazo_texto(local(2026, 11, 23, 9, 0)) == "23/11 às 09:00"
    assert cotacao.prazo_texto(None) == ""


# ---------- arquivos ----------

def test_validar_arquivo():
    assert cotacao.validar_arquivo("a.pdf", b"%PDF-1.4 x") == "pdf"
    assert cotacao.validar_arquivo("a.PNG", b"\x89PNG....") == "imagem"
    assert cotacao.validar_arquivo("a.csv", b"a;b") == "planilha"
    for nome, conteudo in (("a.exe", b"MZ"), ("a.pdf", b"nao e pdf"), ("a.pdf", b""), ("a.xlsx", b"texto")):
        with pytest.raises(cotacao.CotacaoErro):
            cotacao.validar_arquivo(nome, conteudo)
    with pytest.raises(cotacao.CotacaoErro):
        cotacao.validar_arquivo("a.pdf", b"%PDF-" + b"0" * (cotacao.MAX_BYTES + 1))


# ---------- leitura ----------

def resposta(bruto):
    return {"message": {"content": json.dumps(bruto)}, "usage": {"prompt_tokens": 100, "completion_tokens": 50}, "model": "teste/modelo"}


def arquivo_csv(tmp_path, texto="praça;verba\nBH;50 mil"):
    caminho = tmp_path / "plano.csv"
    caminho.write_text(texto, encoding="utf-8")
    return [{"nome": "plano.csv", "caminho": str(caminho), "tipo": "planilha", "sha256": "x", "tamanho": 10}]


def test_leitura_normaliza_e_descarta_o_que_nao_cabe_no_formulario(tmp_path):
    visto = {}

    def chamar(mensagens, **kw):
        visto["texto"] = json.dumps(mensagens)
        return resposta({"titulo": "Verão", "objetivo": "Vender mais", "pracas": ["BH", "bh", "Contagem"], "inicio": "2026-12-01", "fim": "data errada",
                         "verba": "até R$ 50 mil", "canais": ["social", "inventado"], "formatos": ["Story"], "faltou": ["público"], "preco_secreto": "R$ 1"})

    r = cotacao.ler(arquivo_csv(tmp_path), chamar=chamar)
    leitura = r["leitura"]
    assert "praça | verba" in visto["texto"] or "praça;verba" in visto["texto"] or "BH" in visto["texto"]
    assert leitura["pracas"] == ["BH", "Contagem"] and leitura["inicio"] == "2026-12-01" and leitura["fim"] == ""
    assert leitura["canais"] == ["social"] and "preco_secreto" not in leitura
    assert r["tokens_entrada"] == 100 and r["modelo"] == "teste/modelo"


def test_leitura_com_resposta_invalida_levanta_erro_claro(tmp_path):
    with pytest.raises(cotacao.CotacaoErro):
        cotacao.ler(arquivo_csv(tmp_path), chamar=lambda m, **k: {"message": {"content": "sem json"}})
    def cai(m, **k):
        raise RuntimeError("fora do ar")
    with pytest.raises(cotacao.CotacaoErro):
        cotacao.ler(arquivo_csv(tmp_path), chamar=cai)


def test_situacao():
    agora = datetime.now(timezone.utc)
    assert cotacao.situacao({"status": "lendo", "atualizado_em": agora}) == "lendo"
    assert cotacao.situacao({"status": "lendo", "atualizado_em": datetime(2020, 1, 1, tzinfo=timezone.utc)}) == "erro"
    assert cotacao.situacao({"status": "lido"}) == "pronto" and cotacao.situacao({"status": "enviado"}) == "enviado"


# ---------- telas ----------

class Mem:
    def __init__(self):
        self.rascunhos, self.briefings, self.emails, self.iniciadas = {}, [], [], []


@pytest.fixture()
def hub(monkeypatch, tmp_path):
    m = Mem()
    app = get_app()
    app.config.update(TESTING=True, CLIENTES_URL=HOST, HUB_BRIEFING_DIR=str(tmp_path / "arq"))
    from aicentralv2.area_cliente import acesso
    from aicentralv2.cadu_connect import reports_access
    monkeypatch.setattr(reports_access, "reports_only", lambda *a, **k: False)
    atual = {"u": usuario()}
    monkeypatch.setattr(acesso, "contexto_usuario", lambda uid: atual["u"])

    def criar(id_cliente, id_contato):
        i = len(m.rascunhos) + 1
        m.rascunhos[f"u{i}"] = {"id": i, "uuid": f"u{i}", "id_cliente": id_cliente, "status": "recebido", "arquivos": [], "leitura": None, "erro": None,
                                "atualizado_em": datetime.now(timezone.utc), "prazo_resposta_em": None}
        return {"id": i, "uuid": f"u{i}"}
    monkeypatch.setattr(cotacao, "criar_rascunho", criar)
    monkeypatch.setattr(cotacao, "definir_arquivos", lambda i, a: next(r for r in m.rascunhos.values() if r["id"] == i).update(arquivos=a))
    monkeypatch.setattr(cotacao, "obter", lambda u: m.rascunhos.get(u))
    monkeypatch.setattr(cotacao, "contar_recentes", lambda c, minutos=60: 0)
    monkeypatch.setattr(cotacao, "iniciar_em_segundo_plano", lambda i, u: m.iniciadas.append(u))

    def reservar(i):
        r = next(r for r in m.rascunhos.values() if r["id"] == i)
        if r["status"] not in ("lido", "erro"):
            return None
        anterior, r["status"] = r["status"], "enviando"
        return anterior

    def enviado(i, bid, prazo):
        r = next(r for r in m.rascunhos.values() if r["id"] == i)
        r.update(status="enviado", prazo_resposta_em=prazo)
        return True
    monkeypatch.setattr(cotacao, "reservar", reservar)
    monkeypatch.setattr(cotacao, "mudar_status", lambda i, st, erro=None: next(r for r in m.rascunhos.values() if r["id"] == i).update(status=st))
    monkeypatch.setattr(cotacao, "marcar_enviado", enviado)
    monkeypatch.setattr(briefing, "enviar", lambda u, d, extra=None: m.briefings.append((d, extra)) or 55)
    monkeypatch.setattr(emails, "briefing_novo", lambda u, v, i: m.emails.append(("novo", v)) or True)
    monkeypatch.setattr(emails, "briefing_recebido", lambda u, v: m.emails.append(("recebido", v)) or True)
    c = app.test_client()
    with c.session_transaction(base_url=HOST) as s:
        s.update({"user_id": 501, "area_cliente_csrf": "tok"})
    c.mem, c.usuario = m, atual
    return c


def sobe(c, arquivos, csrf="tok"):
    return c.post("/briefing/cotacao", base_url=HOST, data={"csrf": csrf, "arquivos": arquivos}, content_type="multipart/form-data")


def test_pagina_de_anexar_e_cartao_na_escolha(hub):
    html = hub.get("/briefing/cotacao", base_url=HOST).get_data(as_text=True)
    assert "Tenho arquivos para cotar" in html and "pe-drop" in html and "24 horas" in html
    assert 'href="/briefing/cotacao"' in hub.get("/briefing", base_url=HOST).get_data(as_text=True)


def test_upload_valida_guarda_e_comeca_a_ler(hub):
    assert sobe(hub, [(io.BytesIO(b"%PDF-1.4 x"), "briefing.pdf")], csrf="errado").status_code == 400
    ruim = sobe(hub, [(io.BytesIO(b"MZ"), "virus.exe")])
    assert ruim.status_code == 400 and "PDF" in ruim.get_json()["erro"]
    ok = sobe(hub, [(io.BytesIO(b"%PDF-1.4 x"), "briefing.pdf"), (io.BytesIO(b"a;b"), "plano.csv")])
    corpo = ok.get_json()
    assert ok.status_code == 200 and corpo["entradas"][0]["url"] == "/briefing/cotacao/u1" and hub.mem.iniciadas == ["u1"]
    assert [a["nome"] for a in hub.mem.rascunhos["u1"]["arquivos"]] == ["briefing.pdf", "plano.csv"]


def test_limites_e_ver_como(hub):
    assert sobe(hub, [(io.BytesIO(b"%PDF-1"), f"{i}.pdf") for i in range(cotacao.MAX_ARQUIVOS + 1)]).status_code == 400
    hub.usuario["u"] = usuario(ver_como=True)
    assert sobe(hub, [(io.BytesIO(b"%PDF-1"), "a.pdf")]).status_code == 200      # ver como: o envio funciona


def pronto(hub, **extra):
    sobe(hub, [(io.BytesIO(b"%PDF-1.4 x"), "briefing.pdf")])
    hub.mem.rascunhos["u1"].update(status="lido", leitura={"titulo": "Verão 2027", "objetivo": "Vender a coleção de verão", "pracas": ["BH", "Contagem"],
                                                            "inicio": "2026-12-01", "fim": "2027-01-15", "verba": "até R$ 50 mil", "canais": ["social"],
                                                            "resumo": "Cliente quer vender a coleção.", "faltou": ["público"]}, **extra)


def test_tela_lida_vem_preenchida_e_mostra_o_que_faltou(hub):
    pronto(hub)
    html = hub.get("/briefing/cotacao/u1", base_url=HOST).get_data(as_text=True)
    assert 'value="Verão 2027"' in html and "BH, Contagem" in html and 'value="2027-01-15"' in html
    assert "Não achei nos arquivos: público" in html and "briefing.pdf" in html and "Enviar para João" in html


def test_estados_lendo_erro_e_isolamento(hub):
    sobe(hub, [(io.BytesIO(b"%PDF-1.4 x"), "a.pdf")])
    assert "Lendo os seus arquivos" in hub.get("/briefing/cotacao/u1", base_url=HOST).get_data(as_text=True)
    assert hub.get("/briefing/cotacao/u1/status", base_url=HOST).get_json()["pronto"] is False
    hub.mem.rascunhos["u1"].update(status="erro", erro="O modelo de leitura não respondeu agora.")
    html = hub.get("/briefing/cotacao/u1", base_url=HOST).get_data(as_text=True)
    assert "Não consegui ler os arquivos" in html and "Enviar para João" in html          # ainda dá para enviar
    hub.mem.rascunhos["u1"]["id_cliente"] = 999
    assert hub.get("/briefing/cotacao/u1", base_url=HOST).status_code == 404
    assert hub.get("/briefing/cotacao/nao-existe", base_url=HOST).status_code == 404


def form(**extra):
    return {"csrf": "tok", "titulo": "Verão 2027", "objetivo": "Vender a coleção de verão", "pracas": "BH, Contagem", "inicio": "2026-12-01",
            "fim": "2027-01-15", "verba": "até R$ 50 mil", "canais": ["social"], **extra}


def test_enviar_cria_briefing_de_cotacao_com_prazo_arquivos_e_emails(hub):
    pronto(hub)
    assert hub.post("/briefing/cotacao/u1/enviar", base_url=HOST, data=form(csrf="x")).status_code == 400
    r = hub.post("/briefing/cotacao/u1/enviar", base_url=HOST, data=form(descricao="Urgente"))
    assert r.status_code == 303 and r.headers["Location"].endswith("/briefing/cotacao/u1?enviado=1")
    (dados, extra), = hub.mem.briefings
    assert extra["modo"] == "cotacao" and extra["prazo_resposta_em"] > datetime.now(timezone.utc)
    assert extra["arquivos"][0]["nome"] == "briefing.pdf" and extra["leitura_ia"]["resumo"]
    assert "Urgente" in dados["descricao"] and "briefing.pdf" in dados["descricao"] and "Não achei nos arquivos: público" in dados["descricao"]
    assert [e[0] for e in hub.mem.emails] == ["novo", "recebido"] and hub.mem.emails[1][1]["prazo_texto"] and hub.mem.emails[1][1]["anexos"] == ["briefing.pdf"]
    html = hub.get("/briefing/cotacao/u1?enviado=1", base_url=HOST).get_data(as_text=True)
    assert "seguiu para João" in html and "A cotação volta até" in html


def test_enviar_invalido_volta_com_erros_sem_gravar_e_nao_envia_se_ainda_le(hub):
    pronto(hub)
    r = hub.post("/briefing/cotacao/u1/enviar", base_url=HOST, data=form(titulo="", objetivo="curto"))
    assert r.status_code == 422 and not hub.mem.briefings
    assert "Dê um nome" in r.get_data(as_text=True) and 'value="BH, Contagem"' in r.get_data(as_text=True)
    hub.mem.rascunhos["u1"]["status"] = "lendo"
    r = hub.post("/briefing/cotacao/u1/enviar", base_url=HOST, data=form())
    assert r.status_code == 303 and not hub.mem.briefings


def test_ver_como_envia(hub):
    pronto(hub)
    hub.usuario["u"] = usuario(ver_como=True)
    assert hub.post("/briefing/cotacao/u1/enviar", base_url=HOST, data=form()).status_code == 303 and len(hub.mem.briefings) == 1


# ---------- banco de verdade (descartável) ----------

import os                                                                            # noqa: E402
from pathlib import Path                                                             # noqa: E402

DSN = os.getenv("PI_ENTRADA_TEST_DSN")
from psycopg import connect as conectar_de_verdade                                  # noqa: E402  (o conftest troca psycopg.connect por uma recusa em cada teste)
from psycopg.rows import dict_row                                                  # noqa: E402


@pytest.mark.skipif(not DSN, reason="defina PI_ENTRADA_TEST_DSN para rodar contra um Postgres descartável")
def test_rascunho_e_envio_contra_postgres(monkeypatch):
    from tests.test_pi_entrada_banco import TABELAS_ANTIGAS
    raiz = Path(__file__).resolve().parent.parent
    conn = conectar_de_verdade(DSN, row_factory=dict_row, autocommit=False)
    with conn.cursor() as c:
        c.execute("DROP TABLE IF EXISTS hub_briefing_cotacao, cadu_briefings CASCADE")
        c.execute(TABELAS_ANTIGAS)
        c.execute("""CREATE TABLE cadu_briefings (id SERIAL PRIMARY KEY, uuid TEXT, id_cliente INTEGER, id_contato_cliente INTEGER, cliente TEXT,
            titulo TEXT, status TEXT, progresso INTEGER, briefing_original TEXT, objetivo TEXT, budget TEXT, prazo DATE, canais JSONB, responsavel TEXT,
            responsavel_centralcomm TEXT, id_responsavel_vendas INTEGER, email_destinatario TEXT, enviado_para_centralcomm BOOLEAN, data_envio TIMESTAMPTZ,
            created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ, deleted_at TIMESTAMPTZ)""")
        sql = (raiz / "migrations" / "add_briefing_cotacao.sql").read_text(encoding="utf-8")
        c.execute(sql)
        c.execute(sql)                                                               # idempotente
        c.execute("INSERT INTO tbl_cliente (nome_fantasia) VALUES ('Cliente Teste')")
    conn.commit()

    class FalsoDb:
        @staticmethod
        def get_db():
            return conn
    monkeypatch.setattr(cotacao, "_db", lambda: FalsoDb)
    monkeypatch.setattr(briefing, "_db", lambda: FalsoDb)

    r = cotacao.criar_rascunho(1, 501)
    cotacao.definir_arquivos(r["id"], [{"nome": "a.pdf", "sha256": "x", "tamanho": 1, "caminho": "/x", "tipo": "pdf"}])
    cotacao.mudar_status(r["id"], "lendo")
    cotacao.salvar_leitura(r["id"], {"leitura": {"titulo": "Verão"}, "avisos": [], "modelo": "m", "tokens_entrada": 3, "tokens_saida": 2})
    lido = cotacao.obter(r["uuid"])
    assert lido["status"] == "lido" and lido["leitura"]["titulo"] == "Verão" and lido["arquivos"][0]["nome"] == "a.pdf"
    assert cotacao.contar_recentes(1) == 1 and cotacao.contar_recentes(2) == 0

    valores, erros = briefing.validar(__import__("werkzeug.datastructures", fromlist=["MultiDict"]).MultiDict(
        {"titulo": "Verão 2027", "objetivo": "Vender a coleção de verão", "canais": "social"}))
    assert not erros
    prazo = cotacao.prazo_resposta()
    novo = briefing.enviar({"cliente_id": 1, "user_id": 501, "nome": "Ana"}, valores,
                           {"modo": "cotacao", "prazo_resposta_em": prazo, "arquivos": lido["arquivos"], "leitura_ia": lido["leitura"]})
    assert cotacao.marcar_enviado(r["id"], novo, prazo) is False                       # sem reservar antes, não marca
    assert cotacao.reservar(r["id"]) == "lido" and cotacao.reservar(r["id"]) is None   # a trava vale para um envio só
    assert cotacao.marcar_enviado(r["id"], novo, prazo) is True
    assert cotacao.marcar_enviado(r["id"], novo, prazo) is False
    with conn.cursor() as c:
        c.execute("SELECT modo, prazo_resposta_em, arquivos, leitura_ia, respondido_em FROM cadu_briefings WHERE id = %s", (novo,))
        b = c.fetchone()
        c.execute("SELECT modo FROM cadu_briefings WHERE id <> %s", (novo,))
    assert b["modo"] == "cotacao" and b["prazo_resposta_em"] and b["arquivos"][0]["nome"] == "a.pdf" and b["leitura_ia"]["titulo"] == "Verão" and b["respondido_em"] is None
    # briefing comum (sem extra) continua gravando com o modo padrão
    outro = briefing.enviar({"cliente_id": 1, "user_id": 501, "nome": "Ana"}, valores)
    with conn.cursor() as c:
        c.execute("SELECT modo, prazo_resposta_em FROM cadu_briefings WHERE id = %s", (outro,))
        assert c.fetchone() == {"modo": "planejamento", "prazo_resposta_em": None}
    conn.close()


# ---------- lembretes do prazo ----------

from datetime import timedelta                                                       # noqa: E402
from aicentralv2.area_cliente import lembretes_cotacao as lembretes                  # noqa: E402


def test_decidir_lembretes_um_por_vez_e_sem_repetir():
    prazo = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    antes = lambda h: prazo - timedelta(hours=h)                                      # noqa: E731
    assert lembretes.decidir(prazo, antes(20), {}) == []
    assert lembretes.decidir(prazo, antes(11), {}) == ["12h"]
    assert lembretes.decidir(prazo, antes(11), {"12h": "x"}) == []
    assert lembretes.decidir(prazo, antes(3), {"12h": "x"}) == ["4h"]
    assert lembretes.decidir(prazo, antes(3), {}) == ["4h"]                           # perdeu o de 12h: manda o mais urgente
    assert lembretes.decidir(prazo, prazo + timedelta(minutes=1), {"12h": "x", "4h": "y"}) == ["atraso"]
    assert lembretes.decidir(prazo, prazo + timedelta(hours=9), {}) == ["atraso"]     # vencido sem avisos: só o de atraso
    assert lembretes.decidir(prazo, prazo + timedelta(hours=9), {"atraso": "z"}) == []


def test_processar_avisa_uma_vez_e_marca_respondidos(monkeypatch):
    agora = datetime(2026, 11, 18, 2, 0, tzinfo=timezone.utc)
    base = {"titulo": "Verão", "cliente": "Cliente", "email_destinatario": "exec@centralcomm.test", "lembretes": None, "status": "pendente"}
    linhas = [{**base, "id": 1, "prazo_resposta_em": agora + timedelta(hours=10)},                 # 12h
              {**base, "id": 2, "prazo_resposta_em": agora + timedelta(hours=20)},                 # cedo demais
              {**base, "id": 3, "prazo_resposta_em": agora + timedelta(hours=3), "status": "aceito"}]   # a equipe já respondeu
    gravados, enviados = [], []
    monkeypatch.setattr(lembretes, "pendentes", lambda: linhas)
    monkeypatch.setattr(lembretes, "_gravar", lambda i, lembretes=None, respondido=False: gravados.append((i, lembretes, respondido)))
    r = lembretes.processar(agora, enviar=lambda b, chave, dest: enviados.append((b["id"], chave, dest)) or True)
    assert r == {"avisos": 1, "respondidos": 1}
    assert enviados == [(1, "12h", ["exec@centralcomm.test"])]
    assert (3, None, True) in gravados and gravados[0][0] == 1 and "12h" in gravados[0][1]


def test_gestor_so_recebe_com_a_variavel_configurada(monkeypatch):
    b = {"email_destinatario": "exec@centralcomm.test"}
    monkeypatch.delenv("HUB_GESTOR_EMAIL", raising=False)
    assert lembretes._destinatarios(b, "gestor") == [] and lembretes._destinatarios(b, "executivo") == ["exec@centralcomm.test"]
    monkeypatch.setenv("HUB_GESTOR_EMAIL", "g1@centralcomm.test, g2@centralcomm.test")
    assert lembretes._destinatarios(b, "gestor") == ["g1@centralcomm.test", "g2@centralcomm.test"]
    assert lembretes._destinatarios(b, "executivo", atraso=True)[0] == "exec@centralcomm.test" and len(lembretes._destinatarios(b, "executivo", atraso=True)) == 3


def test_email_de_prazo_renderiza():
    app = get_app()
    with app.test_request_context("/", base_url=HOST):
        html = emails.renderizar("briefing-prazo", titulo="Verão", cliente="Cliente Teste", prazo="18/11 às 12:00", situacao="faltam 12 horas",
                                 atraso=False, link_briefings="https://x/briefings", executivo=None, primeiro_nome="equipe")
    assert "Cliente Teste" in html and "18/11 às 12:00" in html and "vence em breve" in html


def test_envio_duplicado_cria_um_so_briefing_e_falha_libera_o_rascunho(hub, monkeypatch):
    pronto(hub)
    assert hub.post("/briefing/cotacao/u1/enviar", base_url=HOST, data=form()).status_code == 303
    assert hub.post("/briefing/cotacao/u1/enviar", base_url=HOST, data=form()).status_code == 303
    assert len(hub.mem.briefings) == 1 and len(hub.mem.emails) == 2
    # falha ao gravar o briefing: o rascunho volta a "lido" e dá para tentar de novo
    hub.mem.rascunhos["u1"]["status"] = "lido"
    def quebra(*a, **k):
        raise RuntimeError("banco fora")
    monkeypatch.setattr(briefing, "enviar", quebra)
    assert hub.post("/briefing/cotacao/u1/enviar", base_url=HOST, data=form()).status_code >= 500
    assert hub.mem.rascunhos["u1"]["status"] == "lido"


def test_pdf_com_senha_mostra_a_mensagem_do_leitor(tmp_path, monkeypatch):
    from aicentralv2.pi_entrada import leitor
    estados = []
    monkeypatch.setattr(cotacao, "obter", lambda u: {"arquivos": []})
    monkeypatch.setattr(cotacao, "mudar_status", lambda i, st, erro=None: estados.append((st, erro)))
    monkeypatch.setattr(cotacao, "ler", lambda a, chamar=None: (_ for _ in ()).throw(leitor.LeituraErro("O PDF tem senha.")))
    cotacao.processar(1, "u")
    assert estados[-1] == ("erro", "O PDF tem senha.")


# ---------- anexo opcional do planejamento ----------

def planejamento(**extra):
    return {"csrf": "tok", "titulo": "Verão 2027", "objetivo": "Vender a coleção de verão", **extra}


def test_planejamento_nao_reaproveita_pi_e_mostra_apoio_e_ajuda(hub, monkeypatch):
    monkeypatch.setattr(briefing, "historico", lambda c, limite=8: pytest.fail("planejamento não consulta o histórico de PIs"))
    monkeypatch.setattr(briefing, "listar", lambda c: [])
    html = hub.get("/briefing/planejamento", base_url=HOST).get_data(as_text=True)
    assert "Quer aproveitar algo que já fizemos juntos" not in html and "Públicos que você já usou" not in html
    assert "Itens do Descobrir" in html and "Anexo" in html and 'id="bw-anexo-btn"' in html and 'name="anexo"' in html
    assert "Sobre a campanha" in html and "Quando e quanto" in html and html.count('class="bw-ajuda"') >= 8
    assert "Tenho arquivos para cotar" in html                              # o anexo só ajuda; para cotar, outro caminho


def test_anexo_do_planejamento_le_devolve_os_dados_e_vai_com_o_briefing(hub):
    r = hub.post("/briefing/anexo", base_url=HOST, data={"csrf": "x", "arquivos": [(io.BytesIO(b"%PDF-1.4 x"), "briefing.pdf")]}, content_type="multipart/form-data")
    assert r.status_code == 400                                              # sem csrf
    r = sobe_anexo(hub)
    corpo = r.get_json()
    assert r.status_code == 200 and corpo["uuid"] == "u1" and corpo["dados_url"] == "/briefing/anexo/u1" and corpo["nomes"] == ["briefing.pdf"]
    assert hub.get("/briefing/anexo/u1", base_url=HOST).get_json()["estado"] == "lendo"
    hub.mem.rascunhos["u1"].update(status="lido", leitura={"titulo": "Verão", "pracas": ["BH"], "faltou": ["verba"]})
    dados = hub.get("/briefing/anexo/u1", base_url=HOST).get_json()
    assert dados["estado"] == "pronto" and dados["leitura"]["pracas"] == ["BH"] and dados["nomes"] == ["briefing.pdf"]
    env = hub.post("/briefing/planejamento", base_url=HOST, data=planejamento(anexo="u1", descricao="Urgente"))
    assert env.status_code == 303
    (d, extra), = hub.mem.briefings
    assert extra["modo"] == "planejamento" and extra["prazo_resposta_em"] is None and extra["arquivos"][0]["nome"] == "briefing.pdf"
    assert "Urgente" in d["descricao"] and "Arquivos anexados: briefing.pdf" in d["descricao"] and "Não achei nos arquivos: verba" in d["descricao"]
    assert hub.mem.rascunhos["u1"]["status"] == "enviado"
    # o mesmo anexo não vale duas vezes
    hub.post("/briefing/planejamento", base_url=HOST, data=planejamento(anexo="u1"))
    assert hub.mem.briefings[1][1] is None


def test_anexo_de_outro_cliente_ou_inexistente_e_ignorado(hub):
    sobe_anexo(hub)
    hub.mem.rascunhos["u1"].update(status="lido", id_cliente=999)
    assert hub.get("/briefing/anexo/u1", base_url=HOST).status_code == 404
    hub.post("/briefing/planejamento", base_url=HOST, data=planejamento(anexo="u1"))
    hub.post("/briefing/planejamento", base_url=HOST, data=planejamento(anexo="nao-existe"))
    assert [b[1] for b in hub.mem.briefings] == [None, None]
    assert hub.post("/briefing/anexo", base_url=HOST, data={"csrf": "tok", "arquivos": [(io.BytesIO(b"MZ"), "x.exe")]}, content_type="multipart/form-data").status_code == 400


def sobe_anexo(c):
    return c.post("/briefing/anexo", base_url=HOST, data={"csrf": "tok", "arquivos": [(io.BytesIO(b"%PDF-1.4 x"), "briefing.pdf")]}, content_type="multipart/form-data")
