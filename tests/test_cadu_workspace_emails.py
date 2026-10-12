from datetime import datetime, timedelta, timezone
from unittest import mock

from flask import Flask

from aicentralv2.services import cadu_workspace_emails as we

UTC = timezone.utc


def _app():
    app = Flask(__name__)
    app.config.update(WORKSPACE_URL="https://ws.example")
    return app


class Cur:
    def __init__(self, conn): self.conn = conn
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): self.conn.sql.append(" ".join(sql.split()))
    def fetchall(self): return self.conn.team
    def fetchone(self): return self.conn.project


class Conn:
    def __init__(self, team=(), project=None): self.team, self.project, self.sql = list(team), project, []
    def cursor(self): return Cur(self)
    def rollback(self): pass


CONTACTS = {1: {"nome_completo": "Ana Lima", "email": "ana@x.com"}, 2: {"nome_completo": "Bruno Reis", "email": "bruno@x.com"}}


def _patch(conn, sent):
    return [mock.patch.object(we, "_db", return_value=conn),
            mock.patch.object(we, "_contact", side_effect=lambda cid: dict(CONTACTS.get(int(cid or 0), {}))),
            mock.patch.object(we, "_send", side_effect=lambda event, **kw: sent.append((event, kw)) or {"success": True})]


def _run(fn, conn, **kw):
    sent = []
    with _app().app_context():
        ps = _patch(conn, sent)
        for p in ps: p.start()
        try:
            return fn(**kw), sent
        finally:
            for p in ps: p.stop()


def test_projeto_criado_avisa_o_time_menos_quem_criou_e_ignora_conta_de_uma_pessoa():
    count, sent = _run(we.notify_project_created, Conn(team=[{"email": "bruno@x.com", "nome_completo": "Bruno"}]),
                       client_id=3, creator_id=1, project_id="p1", name="Lançamento")
    assert count == 1 and sent[0][0] == "workspace.project_created"
    assert sent[0][1]["subject"] == "Ana criou o projeto Lançamento" and sent[0][1]["cta_url"].endswith("/projetos/p1")
    count, sent = _run(we.notify_project_created, Conn(team=[]), client_id=3, creator_id=1, project_id="p1", name="X")
    assert count == 0 and sent == []


def test_fonte_recebida_so_avisa_o_dono_quando_foi_um_colega():
    project = {"id": "p1", "nome": "Lançamento", "criado_por": 1}
    ok, sent = _run(we.notify_source_received, Conn(project=project), client_id=3, project_id="p1", actor_id=2,
                    source_names=["briefing.pdf", "ata.docx", "planilha.xlsx", "extra.pdf"])
    assert ok and sent[0][1]["recipient"]["email"] == "ana@x.com"
    assert "Bruno adicionou 4 fontes em Lançamento" == sent[0][1]["title"] and "e mais 1" in sent[0][1]["description"]
    ok, sent = _run(we.notify_source_received, Conn(project=project), client_id=3, project_id="p1", actor_id=1,
                    source_names=["meu.pdf"])
    assert ok is False and sent == []  # o próprio dono adicionou


def test_link_lido_e_revisao_so_avisam_quando_demoraram():
    now = datetime.now(UTC)
    ok, sent = _run(we.notify_source_indexed, Conn(), client_id=3, project_id="p1", user_id=1, source_name="site",
                    started_at=now - timedelta(seconds=30))
    assert ok is False and sent == []
    ok, sent = _run(we.notify_source_indexed, Conn(), client_id=3, project_id="p1", user_id=1, source_name="site",
                    started_at=now - timedelta(minutes=5))
    assert sent and sent[0][0] == "workspace.source_indexed"
    _, sent = _run(we.notify_document_reviewed, Conn(), client_id=3, user_id=1, document_id="d1", title="Plano", elapsed_seconds=10)
    assert sent == []
    _, sent = _run(we.notify_document_reviewed, Conn(), client_id=3, user_id=1, document_id="d1", title="Plano", elapsed_seconds=90)
    assert sent[0][0] == "workspace.document_reviewed" and sent[0][1]["cta_url"].endswith("/docs/d1")


def test_trabalho_longo_concluido_leva_ao_projeto_ou_ao_chat():
    _, sent = _run(we.notify_conversation_important, Conn(), client_id=3, user_id=1, title="Pesquisa", project_ref="ci:p9")
    assert sent[0][0] == "workspace.conversation_important" and sent[0][1]["cta_url"].endswith("/projetos/p9")
    _, sent = _run(we.notify_conversation_important, Conn(), client_id=3, user_id=1, title="Pesquisa", project_ref=None)
    assert sent[0][1]["cta_url"].endswith("/chat")


def test_intervalo_minimo_e_falha_de_leitura_nao_reenviam():
    with _app().app_context(), mock.patch("aicentralv2.services.cadu_product_emails._enabled", return_value=True), \
         mock.patch("aicentralv2.services.cadu_email_connector.send_cadu_event") as send, \
         mock.patch("aicentralv2.services.brevo_service.product_email_brand", return_value={}):
        with mock.patch.object(we, "_recently_sent", return_value=True):
            assert we._send("workspace.project_created", recipient={"email": "a@x.com"}, subject="s", title="t",
                            description="d", cta_label="c", cta_url="u")["reason"] == "throttled"
        broken = mock.MagicMock(); broken.cursor.side_effect = RuntimeError("db")
        with mock.patch.object(we, "_db", return_value=broken):
            assert we._recently_sent("a@x.com", "workspace.project_created") is True  # na dúvida, não envia
    send.assert_not_called()


def test_todos_os_eventos_do_workspace_estao_ativos():
    from aicentralv2.services.cadu_email_connector import CADU_EMAIL_EVENTS
    planned = [k for k, v in CADU_EMAIL_EVENTS.items() if v["status"] != "active"]
    assert planned == []
