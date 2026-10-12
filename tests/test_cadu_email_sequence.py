from datetime import datetime, timezone
from unittest import mock

import pytest
from flask import Flask

from aicentralv2.services import cadu_email_sequence as seq

UTC = timezone.utc


def _app():
    import os
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(seq.__file__), "..", "templates"))
    app.secret_key = "test-secret"
    return app


def _row(**kw):
    base = {"id": 1, "contato_id": 7, "sequence_key": seq.SEQUENCE_KEY, "next_step": 1, "attempts": 0,
            "email": "ana@x.com", "nome_completo": "Ana Lima", "client_id": 3, "contact_active": True,
            "marketing_opt_out": False}
    return {**base, **kw}


# 14h em Brasília = 17h UTC: dentro da janela de envio
NOON = datetime(2026, 10, 13, 17, 0, tzinfo=UTC)


def test_sequencia_tem_sete_passos_e_todos_existem():
    from aicentralv2.services.cadu_growth_email_templates import GROWTH_EMAIL_MODELS
    assert len(seq.SEQUENCE_STEPS) == 7 and "planner-interativos" in seq.SEQUENCE_STEPS
    assert all(key in GROWTH_EMAIL_MODELS for key in seq.SEQUENCE_STEPS)


def test_janela_de_envio_empurra_madrugada_e_noite_para_as_9h_de_brasilia():
    assert seq.adjust_to_send_window(NOON) == NOON
    night = datetime(2026, 10, 14, 1, 0, tzinfo=UTC)  # 22h do dia 13 em Brasília
    assert seq.adjust_to_send_window(night) == datetime(2026, 10, 14, 12, 0, tzinfo=UTC)  # 9h do dia 14
    dawn = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)  # 5h em Brasília
    assert seq.adjust_to_send_window(dawn) == datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def test_decisao_respeita_descadastro_contato_inativo_fim_e_horario():
    assert seq.decide_due(_row(marketing_opt_out=True), NOON)["action"] == "cancel"
    assert seq.decide_due(_row(contact_active=False), NOON)["action"] == "pause"
    assert seq.decide_due(_row(email=""), NOON)["action"] == "pause"
    assert seq.decide_due(_row(next_step=8), NOON)["action"] == "complete"
    assert seq.decide_due(_row(), datetime(2026, 10, 14, 1, 0, tzinfo=UTC))["action"] == "defer"
    send = seq.decide_due(_row(next_step=3), NOON)
    assert send == {"action": "send", "step": 3, "model_key": "planner-radar"}


def test_depois_do_envio_agenda_dois_dias_e_conclui_no_ultimo():
    nxt = seq.after_success(1, NOON)
    assert nxt["status"] == "active" and nxt["next_step"] == 2
    assert (nxt["next_send_at"] - NOON).days == 2
    assert seq.after_success(7, NOON) == {"status": "completed", "next_step": 8, "next_send_at": None}


def test_falha_tenta_de_novo_e_pausa_na_terceira():
    assert seq.after_failure(1, NOON)["status"] == "active"
    assert seq.after_failure(3, NOON) == {"status": "paused", "paused_reason": "falha_envio", "next_send_at": None}


def test_token_de_descadastro_e_assinado():
    with _app().app_context():
        token = seq.make_unsubscribe_token(42)
        assert seq.read_unsubscribe_token(token) == 42
        assert seq.read_unsubscribe_token(token[:-2] + "xx") is None
        assert seq.read_unsubscribe_token("") is None


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((" ".join(sql.split()), params))

    def fetchall(self):
        return self.conn.rows

    def fetchone(self):
        return None


class FakeConn:
    def __init__(self, rows):
        self.rows, self.executed, self.commits = rows, [], 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def test_process_due_desligado_nao_toca_no_banco(monkeypatch):
    monkeypatch.delenv("CADU_EMAIL_SEQUENCE_ENABLED", raising=False)
    with mock.patch.object(seq, "_db") as db:
        assert seq.process_due()["disabled"] is True
    db.assert_not_called()


def test_process_due_reserva_envia_registra_e_avanca(monkeypatch):
    monkeypatch.setenv("CADU_EMAIL_SEQUENCE_ENABLED", "true")
    conn = FakeConn([_row(), _row(id=2, contato_id=8, marketing_opt_out=True)])
    logged = []
    with mock.patch.object(seq, "_db", return_value=conn), \
         mock.patch.object(seq, "last_usage", return_value={}), \
         mock.patch.object(seq, "datetime", wraps=datetime) as dt, \
         mock.patch.object(seq, "send_sequence_step", return_value={"success": True, "messageId": "m1"}) as send, \
         mock.patch.object(seq, "log_email", side_effect=lambda **kw: logged.append(kw)):
        dt.now.return_value = NOON
        result = seq.process_due()
    assert result["sent"] == 1 and result["cancelled"] == 1
    send.assert_called_once()
    assert send.call_args.args[1:] == ("dicas-de-uso", 1)
    assert "FOR UPDATE OF s SKIP LOCKED" in conn.executed[0][0]
    updates = [p for s, p in conn.executed if s.startswith("UPDATE cadu_email_sequence_state")]
    assert any("cancelled" in map(str, p) for p in updates)
    assert logged[0]["status"] == "sent" and logged[0]["message_id"] == "m1" and logged[0]["step"] == 1


def test_envio_que_falha_conta_tentativa(monkeypatch):
    monkeypatch.setenv("CADU_EMAIL_SEQUENCE_ENABLED", "true")
    conn = FakeConn([_row(attempts=2)])
    with mock.patch.object(seq, "_db", return_value=conn), \
         mock.patch.object(seq, "datetime", wraps=datetime) as dt, \
         mock.patch.object(seq, "send_sequence_step", side_effect=RuntimeError("down")), \
         mock.patch.object(seq, "log_email"):
        dt.now.return_value = NOON
        result = seq.process_due()
    assert result["failed"] == 1
    last = [p for s, p in conn.executed if s.startswith("UPDATE cadu_email_sequence_state")][-1]
    assert 3 in last and "paused" in last


def test_webhook_de_descadastro_cancela_a_sequencia():
    conn = FakeConn([{"contato_id": 7}])
    with mock.patch.object(seq, "_db", return_value=conn), mock.patch.object(seq, "set_opt_out") as opt:
        assert seq.apply_brevo_event({"event": "unsubscribed", "message-id": "<m1>"}) is True
    opt.assert_called_once_with(7, "brevo_webhook")
    assert seq.apply_brevo_event({"event": "request", "message-id": "x"}) is False


def test_pagina_de_descadastro_confirma_antes_e_aplica_no_post():
    from aicentralv2.cadu_email_public_routes import bp
    app = _app()
    app.register_blueprint(bp)
    client = app.test_client()
    with app.app_context():
        token = seq.make_unsubscribe_token(7)
    with mock.patch("aicentralv2.cadu_email_public_routes.set_opt_out") as opt:
        page = client.get(f"/workspace/email/descadastrar/{token}")
        assert page.status_code == 200 and "Parar de receber" in page.get_data(as_text=True)
        opt.assert_not_called()  # abrir o link nunca descadastra sozinho
        done = client.post(f"/workspace/email/descadastrar/{token}")
        assert done.status_code == 200 and "não vai mais receber" in done.get_data(as_text=True)
        opt.assert_called_once_with(7, "link")
        assert client.get("/workspace/email/descadastrar/falso").status_code == 404


def test_passo_enviado_tem_nome_link_e_cabecalho_de_descadastro():
    svc = mock.MagicMock(); svc.enviar_email.return_value = {"success": True}
    app = _app()
    app.config.update(WORKSPACE_URL="https://workspace.example")
    with app.test_request_context("/"), \
         mock.patch("aicentralv2.services.brevo_service.get_brevo_product_service", return_value=svc):
        seq.send_sequence_step(_row(), "planner-radar", 3)
    kw = svc.enviar_email.call_args.kwargs
    assert "Olá, Ana." in kw["html_content"] and "Não quero mais receber estas dicas" in kw["html_content"]
    assert kw["headers"]["List-Unsubscribe"].startswith("<https://workspace.example/workspace/email/descadastrar/")
    assert kw["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert kw["tags"] == ["seq:adocao_v1", "passo:3"]


def test_webhook_da_brevo_repassa_cada_evento_ao_registro():
    from aicentralv2 import brevo_webhook_routes as hook
    app = Flask(__name__)
    app.register_blueprint(hook.bp)
    with mock.patch.object(hook, "resolve_brevo_webhook_token", return_value="tok"), \
         mock.patch("aicentralv2.services.cadu_email_sequence.apply_brevo_event") as apply:
        response = app.test_client().post("/api/brevo/webhook", json=[{"event": "delivered", "message-id": "a"}, "lixo"],
                                          headers={"Authorization": "Bearer tok"})
    assert response.status_code == 200
    apply.assert_called_once_with({"event": "delivered", "message-id": "a"})


def test_passo_e_pulado_quando_a_pessoa_ja_usa_a_ferramenta(monkeypatch):
    monkeypatch.setenv("CADU_EMAIL_SEQUENCE_ENABLED", "true")
    conn = FakeConn([_row(next_step=3)])  # passo 3 = Radar
    logged = []
    with mock.patch.object(seq, "_db", return_value=conn), \
         mock.patch.object(seq, "last_usage", return_value={"planner-radar": NOON}), \
         mock.patch.object(seq, "datetime", wraps=datetime) as dt, \
         mock.patch.object(seq, "send_sequence_step") as send, \
         mock.patch.object(seq, "log_email", side_effect=lambda **kw: logged.append(kw)):
        dt.now.return_value = NOON
        result = seq.process_due()
    send.assert_not_called()
    assert result["skipped"] == 1 and logged[0]["status"] == "skipped" and logged[0]["step"] == 3
    last = [p for s, p in conn.executed if s.startswith("UPDATE cadu_email_sequence_state")][-1]
    assert 4 in last and "active" in last  # segue para o passo 4 sem esperar 2 dias


def test_reengajamento_lista_so_o_que_a_pessoa_nao_usou():
    body = seq.reengagement_body(["Radar de Oportunidades", "Studio para criar anúncios e imagens"])
    assert "**Radar de Oportunidades**" in body and "Studio" in body and "assistente" not in body
    assert "resumo do que já foi decidido" in seq.reengagement_body([])


def test_reengajamento_ignora_quem_usou_algo_na_semana_e_envia_uma_vez(monkeypatch):
    monkeypatch.setenv("CADU_EMAIL_SEQUENCE_ENABLED", "true")
    from datetime import timedelta
    conn = FakeConn([{"contato_id": 7, "email": "a@x.com", "nome_completo": "Ana", "client_id": 3},
                     {"contato_id": 8, "email": "b@x.com", "nome_completo": "Bia", "client_id": 3}])
    usage = {7: {"studio-criar": NOON - timedelta(days=1)}, 8: {"planner-radar": NOON - timedelta(days=30)}}
    svc = mock.MagicMock(); svc.enviar_email.return_value = {"success": True, "messageId": "r1"}
    logged = []
    app = _app()
    with app.test_request_context("/"), \
         mock.patch.object(seq, "_db", return_value=conn), \
         mock.patch.object(seq, "datetime", wraps=datetime) as dt, \
         mock.patch.object(seq, "last_usage", side_effect=lambda cid, keys=None: usage[cid]), \
         mock.patch.object(seq, "log_email", side_effect=lambda **kw: logged.append(kw)), \
         mock.patch("aicentralv2.services.brevo_service.get_brevo_product_service", return_value=svc):
        dt.now.return_value = NOON
        result = seq.process_reengagement()
    assert result == {"reengaged": 1, "active_users": 1}
    html = svc.enviar_email.call_args.kwargs["html_content"]
    assert "Olá, Bia." in html and "Studio para criar" in html and "assistente de IA" in html
    assert "<strong>Radar de Oportunidades</strong>" not in html  # já usou o Radar
    assert logged[0]["event_type"] == "reengajamento" and "NOT EXISTS" in conn.executed[0][0]
