"""Recibo de compra de tokens e aviso de plano ativado (Brevo sempre mockado)."""
import os
from contextlib import ExitStack
from unittest import mock

from flask import Flask, render_template

from aicentralv2.services import cadu_email_connector as conn
from aicentralv2.services import cadu_token_emails as te

BRAND = {"illustrations_url": "https://x/", "name": "Workspace", "deep": "#000", "signal": "#111",
         "accent": "#222", "icon_url": "https://x/i.png"}


def _app():
    return Flask(__name__, template_folder=os.path.join(os.path.dirname(te.__file__), "..", "templates"))


def _run(fn, svc, enabled=True, **kw):
    with _app().app_context(), ExitStack() as stack:
        stack.enter_context(mock.patch.object(te, "_enabled", return_value=enabled))
        stack.enter_context(mock.patch.object(conn, "get_brevo_product_service", return_value=svc))
        stack.enter_context(mock.patch.object(conn, "product_email_brand", return_value=BRAND))
        stack.enter_context(mock.patch("aicentralv2.email_service.record_workspace_email_event"))
        stack.enter_context(mock.patch("aicentralv2.product_domains.product_url", side_effect=lambda p, path="/": path))
        return fn(**kw)


def test_events_are_catalogued_as_active():
    for event in ("workspace.token_purchase_receipt", "workspace.plan_activated",
                  "studio.generation_failed", "connect.reports_alert"):
        assert conn.CADU_EMAIL_EVENTS[event]["status"] == "active"


def test_purchase_receipt_has_package_tokens_and_balance():
    svc = mock.MagicMock(); svc.enviar_email_com_template.return_value = {"success": True}
    result = _run(te.send_token_purchase_receipt_email, svc, user_email="a@x.com", user_name="Ana Lima",
                  package_name="Agência", tokens=500000, request_id=12, client_id=3, balance=650000)
    kw = svc.enviar_email_com_template.call_args.kwargs
    assert result["success"] and kw["template_name"] == "produto-atividade.html"
    assert "500.000 tokens" in kw["subject"]
    values = {row["label"]: row["value"] for row in kw["params"]["DETAILS"]}
    assert values["Pacote"] == "Agência" and values["Tokens adicionados"] == "500.000"
    assert values["Saldo disponível agora"] == "650.000 tokens" and values["Pedido"] == "nº 12"
    assert kw["params"]["CADU_EVENT"] == "workspace.token_purchase_receipt"


def test_purchase_receipt_reads_balance_when_missing_and_never_raises():
    svc = mock.MagicMock()
    with mock.patch("aicentralv2.cadu_skills.repository.credit_position", return_value={"available": 42}):
        _run(te.send_token_purchase_receipt_email, svc, user_email="a@x.com", user_name="A",
             package_name="P", tokens=10, client_id=3)
    assert any(r["value"] == "42 tokens" for r in svc.enviar_email_com_template.call_args.kwargs["params"]["DETAILS"])
    broken = mock.MagicMock(); broken.enviar_email_com_template.side_effect = RuntimeError("down")
    assert _run(te.send_token_purchase_receipt_email, broken, user_email="a@x.com", user_name="A",
                package_name="P", tokens=1, balance=1)["success"] is False
    off = mock.MagicMock()
    assert _run(te.send_token_purchase_receipt_email, off, enabled=False, user_email="a@x.com", user_name="A",
                package_name="P", tokens=1)["skipped"]
    off.enviar_email_com_template.assert_not_called()


def test_plan_activated_goes_to_each_admin_with_franchise():
    svc = mock.MagicMock(); svc.enviar_email_com_template.return_value = {"success": True}
    result = _run(te.send_plan_activated_email, svc, client_id=3, plan_name="Equipe", tokens_monthly=1000000,
                  changed=True, recipients=[{"email": "a@x.com", "name": "Ana"}, {"email": "b@x.com", "name": "Bia"}])
    assert result == {"success": True, "sent": 2}
    kw = svc.enviar_email_com_template.call_args.kwargs
    assert "foi alterado" in kw["subject"] and "1.000.000 tokens" in kw["params"]["DESCRIPTION"]


def test_plan_activated_without_franchise_or_recipients():
    svc = mock.MagicMock(); svc.enviar_email_com_template.return_value = {"success": True}
    _run(te.send_plan_activated_email, svc, client_id=3, plan_name="Beta", changed=False,
         recipients=[{"email": "a@x.com"}])
    kw = svc.enviar_email_com_template.call_args.kwargs
    assert "está ativo" in kw["subject"] and "franquia" not in kw["params"]["DESCRIPTION"].lower()
    assert _run(te.send_plan_activated_email, svc, client_id=3, plan_name="B", changed=False, recipients=[])["skipped"]


def test_plan_activated_never_raises():
    with mock.patch.object(te, "client_admin_recipients", side_effect=RuntimeError("db")):
        assert _run(te.send_plan_activated_email, mock.MagicMock(), client_id=3, plan_name="B",
                    changed=False)["success"] is False


def test_brand_template_renders_details_and_optional_cta():
    with _app().test_request_context():
        html = render_template("emails/externos/produto-atividade.html", brand=BRAND, title="T", description="D",
                               eyebrow="Recibo de compra", details=[{"label": "Pacote", "value": "Agência"}])
        legacy = render_template("emails/externos/produto-atividade.html", brand=BRAND, title="T", description="D",
                                 cta_url="/x", cta_label="Abrir")
    assert "Recibo de compra" in html and "Agência" in html and "href" not in html
    assert "Auditoria de marca" in legacy and 'href="/x"' in legacy


# ---- Studio: vídeo pronto e falha sem débito --------------------------------
from aicentralv2.services import cadu_product_emails as pe  # noqa: E402


def _run_pe(fn, svc, **kw):
    with _app().app_context(), ExitStack() as stack:
        stack.enter_context(mock.patch.object(pe, "_enabled", return_value=True))
        stack.enter_context(mock.patch.object(pe, "product_email_brand", return_value=BRAND))
        stack.enter_context(mock.patch.object(conn, "get_brevo_product_service", return_value=svc))
        stack.enter_context(mock.patch.object(conn, "product_email_brand", return_value=BRAND))
        stack.enter_context(mock.patch("aicentralv2.email_service.record_workspace_email_event"))
        return fn(**kw)


def test_generation_failed_states_balance_was_not_debited_or_refunded():
    svc = mock.MagicMock(); svc.enviar_email_com_template.return_value = {"success": True}
    _run_pe(pe.send_studio_generation_failed, svc, recipient_email="a@x.com", recipient_name="Ana",
            kind="video", reason="Provedor recusou", url="/studio")
    kw = svc.enviar_email_com_template.call_args.kwargs
    assert "NÃO foi debitado" in kw["params"]["DESCRIPTION"] and "Provedor recusou" in kw["params"]["DESCRIPTION"]
    assert kw["params"]["CADU_EVENT"] == "studio.generation_failed"
    _run_pe(pe.send_studio_generation_failed, svc, recipient_email="a@x.com", recipient_name="Ana",
            kind="image", refunded=True)
    assert "estornado" in svc.enviar_email_com_template.call_args.kwargs["params"]["DESCRIPTION"]
    broken = mock.MagicMock(); broken.enviar_email_com_template.side_effect = RuntimeError("down")
    assert _run_pe(pe.send_studio_generation_failed, broken, recipient_email="a@x.com",
                   recipient_name="A")["success"] is False


class _Repo:
    def __init__(self, before, after):
        self.rows = [before, after]

    def get_job(self, job_id):
        return self.rows.pop(0) if len(self.rows) > 1 else self.rows[0]


def _animate(before, after, outcome):
    from aicentralv2.creative_format_lab.animate import AnimateService
    service = AnimateService(store=mock.MagicMock(), repository=_Repo(before, after), spawn_job=lambda *a: None)
    worker = mock.MagicMock()
    if isinstance(outcome, Exception):
        worker.run.side_effect = outcome
    else:
        worker.run.return_value = outcome
    return service, worker


def _drive(service, worker):
    with _app().app_context(), \
         mock.patch.object(service, "_worker", return_value=worker), \
         mock.patch("aicentralv2.cadu_family.repository.actor", return_value={"email": "a@x.com", "name": "Ana"}), \
         mock.patch("aicentralv2.product_domains.product_url", side_effect=lambda p, path="/": path), \
         mock.patch.object(pe, "send_piece_ready") as ready, \
         mock.patch.object(pe, "send_studio_generation_failed") as failed:
        try:
            service._run("job1")
        except RuntimeError:
            pass
    return ready, failed


def test_video_ready_notifies_once_with_existing_piece_ready_event():
    ready_row = {"public_id": "job1", "status": "ready", "user_id": 7, "version_payload": {"name": "Clipe 8s"}}
    ready, failed = _drive(*_animate({"status": "queued"}, ready_row, ready_row))
    assert ready.call_args.kwargs["kind"] == "video" and ready.call_args.kwargs["title"] == "Clipe 8s"
    assert not failed.called
    ready, _ = _drive(*_animate(ready_row, ready_row, ready_row))  # job já pronto: não reenvia
    assert not ready.called


def test_video_failure_before_charge_warns_but_not_after_charge():
    failed_row = {"public_id": "job1", "status": "failed", "user_id": 7, "version_payload": None}
    _, failed = _drive(*_animate({"status": "queued"}, failed_row, RuntimeError("A geração falhou.")))
    assert failed.call_args.kwargs["kind"] == "video" and "falhou" in failed.call_args.kwargs["reason"]
    charged = {**failed_row, "version_payload": {"master_asset_id": "m1"}}
    _, failed = _drive(*_animate({"status": "queued"}, charged, RuntimeError("persist")))
    assert not failed.called
