from unittest import mock

from flask import Flask

from aicentralv2.services import cadu_token_emails as te

BRAND = {"illustrations_url": "https://x/", "name": "Workspace"}


def _app():
    import os
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(te.__file__), "..", "templates"))
    app.config["WORKSPACE_URL"] = "https://ws.example"
    return app


def _patches(svc, allowance=False):
    return [mock.patch.object(te, "_enabled", return_value=True),
            mock.patch("aicentralv2.services.brevo_service.get_brevo_product_service", return_value=svc),
            mock.patch("aicentralv2.services.brevo_service.product_email_brand", return_value=BRAND),
            mock.patch("aicentralv2.product_domains.product_url", side_effect=lambda p, path="/": path),
            mock.patch("aicentralv2.cadu_plan_allowance.allowance_enabled", return_value=allowance)]


def _run(fn, svc, allowance=False, **kw):
    ps = _patches(svc, allowance)
    with _app().app_context():
        for p in ps: p.start()
        try:
            return fn(**kw)
        finally:
            for p in ps: p.stop()


def test_welcome_announces_tokens_and_plan_when_allowance_on(monkeypatch):
    monkeypatch.delenv("CADU_WELCOME_TOKENS", raising=False)
    svc = mock.MagicMock()
    _run(te.send_public_welcome_tokens_email, svc, allowance=True, user_email="a@x.com", user_name="Ana Lima", client_id=1)
    kw = svc.enviar_email_com_template.call_args.kwargs
    assert kw["template_name"] == "bonus-creditos.html" and "50.000 tokens" in kw["subject"]
    assert kw["params"]["WELCOME_TOKENS"] == "50.000" and kw["params"]["PLAN_TOKENS"] == "100.000"
    assert kw["params"]["CREDITS_URL"] == "/workspace/app/creditos"


def test_welcome_hides_plan_franchise_when_flag_off(monkeypatch):
    monkeypatch.delenv("CADU_WELCOME_TOKENS", raising=False)
    svc = mock.MagicMock()
    _run(te.send_public_welcome_tokens_email, svc, user_email="a@x.com", user_name="Ana", client_id=1)
    assert svc.enviar_email_com_template.call_args.kwargs["params"]["PLAN_TOKENS"] == ""


def test_welcome_never_raises_and_respects_switches(monkeypatch):
    svc = mock.MagicMock(); svc.enviar_email_com_template.side_effect = RuntimeError("down")
    assert _run(te.send_public_welcome_tokens_email, svc, user_email="a@x.com", user_name="A")["success"] is False
    monkeypatch.setenv("CADU_WELCOME_TOKENS", "0")
    svc2 = mock.MagicMock()
    assert _run(te.send_public_welcome_tokens_email, svc2, user_email="a@x.com", user_name="A")["skipped"]
    svc2.enviar_email_com_template.assert_not_called()
    with _app().app_context(), mock.patch.object(te, "_enabled", return_value=False):
        assert te.send_public_welcome_tokens_email(user_email="a@x.com", user_name="A")["skipped"]


def test_plan_request_confirmation_does_not_promise_automatic_charge():
    svc = mock.MagicMock()
    _run(te.send_plan_request_received_email, svc, user_email="a@x.com", user_name="Ana", plan_name="Equipe", request_id=9)
    p = svc.enviar_email_com_template.call_args.kwargs["params"]
    assert "financeiro entra em contato" in p["DESCRIPTION"] and "Nada é cobrado automaticamente" in p["DESCRIPTION"]
    assert p["CTA_URL"] == "/workspace/app/planos"


def test_bonus_template_renders_both_variants():
    from flask import render_template
    app = _app()
    with app.test_request_context():
        welcome = render_template("emails/externos/bonus-creditos.html", welcome_tokens="50.000", plan_name="Free",
                                  plan_tokens="100.000", primeiro_nome="Ana", credits_url="/c", brand=BRAND)
        launch = render_template("emails/externos/bonus-creditos.html", expires_at="01/12/2026", empresa="ACME",
                                 primeiro_nome="Ana", credits_url="/c", brand=BRAND)
    assert "50.000 tokens de boas-vindas" in welcome and "100.000 tokens por mês" in welcome and "crédito" not in welcome
    assert "100.000 tokens de bônus" in launch and "01/12/2026" in launch
