import os
from unittest import mock

from flask import Flask

from aicentralv2.services import cadu_signup_emails as se
from aicentralv2.services import cadu_token_emails as te

BRAND = {"illustrations_url": "https://x/", "name": "Workspace"}


def _app():
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(se.__file__), "..", "templates"))
    return app


def _ctx(svc, enabled=True):
    return [mock.patch.object(se, "_enabled", return_value=enabled),
            mock.patch.object(te, "_enabled", return_value=enabled),
            mock.patch("aicentralv2.services.brevo_service.get_brevo_product_service", return_value=svc),
            mock.patch("aicentralv2.services.brevo_service.product_email_brand", return_value=BRAND),
            mock.patch("aicentralv2.product_domains.product_url", side_effect=lambda p, path="/": path),
            mock.patch("aicentralv2.email_service.record_workspace_email_event")]


def _run(svc, **kw):
    ps = _ctx(svc, kw.pop("enabled", True))
    with _app().app_context():
        started = [p.start() for p in ps]
        try:
            return se.send_signup_email_series(**kw), started[-1]
        finally:
            for p in ps: p.stop()


def test_series_sends_three_emails_in_order_and_records_each():
    svc = mock.MagicMock(); svc.enviar_email_com_template.return_value = {"success": True}
    with mock.patch("aicentralv2.cadu_plan_allowance.allowance_enabled", return_value=False):
        results, record = _run(svc, user_email="a@x.com", user_name="Ana Lima", client_id=7)
    templates = [c.kwargs["template_name"] for c in svc.enviar_email_com_template.call_args_list]
    assert templates == ["boas-vindas-cadastro.html", "configurar-marca-projeto.html", "bonus-creditos.html"]
    assert [r["event"] for r in results] == list(se.SIGNUP_EVENTS)
    assert [c.kwargs["event_type"] for c in record.call_args_list] == list(se.SIGNUP_EVENTS)
    params = svc.enviar_email_com_template.call_args_list[1].kwargs["params"]
    assert params["ONBOARDING_URL"] == "/workspace/onboarding" and params["PRIMEIRO_NOME"] == "Ana"


def test_one_failure_does_not_block_the_next_emails():
    svc = mock.MagicMock()
    svc.enviar_email_com_template.side_effect = [RuntimeError("down"), {"success": True}, {"success": True}]
    with mock.patch("aicentralv2.cadu_plan_allowance.allowance_enabled", return_value=False):
        results, _ = _run(svc, user_email="a@x.com", user_name="Ana", client_id=1)
    assert [r.get("success") for r in results] == [False, True, True]


def test_welcome_series_ignores_the_product_emails_switch_but_tokens_email_respects_it():
    svc = mock.MagicMock(); svc.enviar_email_com_template.return_value = {"success": True}
    results, _ = _run(svc, enabled=False, user_email="a@x.com", user_name="Ana", client_id=1)
    templates = [c.kwargs["template_name"] for c in svc.enviar_email_com_template.call_args_list]
    assert templates == ["boas-vindas-cadastro.html", "configurar-marca-projeto.html"]
    assert results[2].get("skipped") is True


def test_templates_render_with_family_colors_and_illustration():
    from flask import render_template
    with _app().test_request_context():
        one = render_template("emails/externos/boas-vindas-cadastro.html", primeiro_nome="Ana", link_login="/w",
                              brand=BRAND, illustration_url="https://x/signup-welcome.png")
        two = render_template("emails/externos/configurar-marca-projeto.html", primeiro_nome="Ana",
                              onboarding_url="/workspace/onboarding", brand=BRAND,
                              illustration_url="https://x/signup-brand-project.png")
    for color in ("#007D6D", "#087D4D", "#6344CF", "#1363C5"):
        assert color in one
    assert "Planner" in one and "signup-welcome.png" in one
    assert "/workspace/onboarding" in two and "consome tokens" in two
