from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

from aicentralv2 import admin_emails_routes as routes
from aicentralv2.services import cadu_email_admin as admin

ROOT = Path(__file__).resolve().parents[1]
BASE = "{% block content %}{% endblock %}{% block scripts %}{% endblock %}"
NOW = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)


def _app():
    app = Flask(__name__)
    app.secret_key = "t"
    app.jinja_loader = ChoiceLoader([DictLoader({"base_erp.html": BASE}),
                                     FileSystemLoader(str(ROOT / "aicentralv2" / "templates"))])
    app.register_blueprint(routes.bp)
    app.add_url_rule("/", "index", lambda: "home")  # destino do redirect de acesso negado
    return app


def _client(app, admin_ok=True):
    client = app.test_client()
    with client.session_transaction() as s:
        s.update(user_id=1, user_type="admin", is_centralcomm=admin_ok, admin_emails_csrf="tok")
    return client


READY = {"log": True, "seq": True, "legacy": True}


def test_somente_admin_interno_entra():
    app = _app()
    with mock.patch("aicentralv2.auth.is_internal_admin", return_value=False):
        assert _client(app, admin_ok=False).get("/admin/emails/").status_code == 302
        assert _client(app, admin_ok=False).post("/admin/emails/acao", json={}).status_code == 403


def test_tres_abas_renderizam():
    app = _app()
    ov = {"ready": READY, "days": 7, "by_status": {"sent": 8, "opened": 3, "failed": 1}, "total": 12,
          "funnel": [{"step": 1, "model": "dicas-de-uso", "waiting": 4}], "sequence": {"active": 4}, "opt_outs": 2,
          "failure_rate": 8.3}
    ev = {"ready": READY, "total": 1, "page": 1, "pages": 1, "rows": [
        {"sent_at": NOW, "contato_id": 7, "contact_ref": 7, "nome_completo": "Ana", "recipient_email": "a@x.com",
         "subject": "Dicas", "event_type": "seq.dicas-de-uso", "step": 1, "status": "bounced", "provider_error": "caixa cheia"}]}
    sq = {"ready": READY, "total": 1, "page": 1, "pages": 1, "rows": [
        {"contato_id": 7, "nome_completo": "Ana", "email": "a@x.com", "status": "paused", "opt_out": True,
         "paused_reason": "falha_envio", "next_step": 3, "next_send_at": None, "last_sent_at": NOW}]}
    with mock.patch("aicentralv2.auth.is_internal_admin", return_value=True), \
         mock.patch.object(admin, "overview", return_value=ov), \
         mock.patch.object(admin, "list_events", return_value=ev), \
         mock.patch.object(admin, "list_sequence", return_value=sq):
        client = _client(app)
        visao = client.get("/admin/emails/").get_data(as_text=True)
        eventos = client.get("/admin/emails/?tab=eventos&status=bounced").get_data(as_text=True)
        seq = client.get("/admin/emails/?tab=sequencia").get_data(as_text=True)
    assert "Taxa de falha de 8.3%" in visao and "dicas-de-uso" in visao and "desligada" in visao
    assert "caixa cheia" in eventos and "Devolvido" in eventos and "/admin/emails/usuario/7" in eventos
    assert "Descadastrado" in seq and "3 · planner-radar" in seq and "Aplicar a todos do filtro (1)" in seq


def test_acao_exige_csrf_faz_previa_e_audita():
    app = _app()
    with mock.patch("aicentralv2.auth.is_internal_admin", return_value=True), \
         mock.patch.object(admin, "apply_action", return_value=2) as apply, \
         mock.patch("aicentralv2.audit.registrar_acao_admin") as audit:
        client = _client(app)
        assert client.post("/admin/emails/acao", json={"action": "pause", "ids": [7]}).status_code == 403
        headers = {"X-CSRF-Token": "tok"}
        preview = client.post("/admin/emails/acao", json={"action": "pause", "ids": [7, "8", "x", 7], "dry_run": True}, headers=headers)
        assert preview.get_json() == {"ok": True, "count": 2, "label": "Pausar"}
        apply.assert_not_called()  # a prévia nunca altera nada
        done = client.post("/admin/emails/acao", json={"action": "pause", "ids": [7, 8]}, headers=headers).get_json()
        assert done == {"ok": True, "count": 2, "affected": 2}
        apply.assert_called_once_with("pause", [7, 8])
        audit.assert_called_once()
        assert client.post("/admin/emails/acao", json={"action": "apagar", "ids": [7]}, headers=headers).status_code == 400


def test_acao_por_filtro_resolve_os_contatos_do_filtro():
    app = _app()
    with mock.patch("aicentralv2.auth.is_internal_admin", return_value=True), \
         mock.patch.object(admin, "resolve_targets", return_value=[1, 2, 3]) as resolve:
        data = _client(app).post("/admin/emails/acao", headers={"X-CSRF-Token": "tok"},
                                 json={"action": "resume", "scope": "filter", "filters": {"status": "paused"}, "dry_run": True}).get_json()
    assert data["count"] == 3
    resolve.assert_called_once_with(contato_ids=[], filters={"status": "paused"})


class Cur:
    def __init__(self, conn): self.conn, self.rowcount = conn, conn.rowcount
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): self.conn.sql.append((" ".join(sql.split()), params))


class Conn:
    def __init__(self, rowcount=0): self.sql, self.rowcount, self.commits = [], rowcount, 0
    def cursor(self): return Cur(self)
    def commit(self): self.commits += 1


def test_acoes_de_estado_usam_guarda_e_descadastro_vai_para_preferencias():
    conn = Conn(rowcount=2)
    with mock.patch.object(admin, "_db", return_value=conn):
        assert admin.apply_action("pause", [7, 8]) == 2
    sql, params = conn.sql[0]
    assert "status = 'paused'" in sql and "AND status = 'active'" in sql and params[1] == [7, 8]
    with mock.patch.object(admin, "set_opt_out") as opt:
        assert admin.apply_action("unsubscribe", [7]) == 1
    opt.assert_called_once_with(7, "admin")
    assert admin.apply_action("pause", []) == 0


class OvCur:
    def __init__(self, rows): self.rows, self.calls = rows, 0
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, sql, params=None): self.calls += 1
    def fetchone(self): return {"log": True, "seq": False, "legacy": False, "n": 0}
    def fetchall(self): return self.rows


def test_visao_geral_nao_conta_ignorados_como_envio():
    cur = OvCur([{"status": "sent", "n": 8}, {"status": "failed", "n": 2}, {"status": "skipped", "n": 40}])
    conn = mock.MagicMock(); conn.cursor.return_value = cur
    with mock.patch.object(admin, "_db", return_value=conn):
        data = admin.overview(7)
    assert data["total"] == 10 and data["failure_rate"] == 20.0
