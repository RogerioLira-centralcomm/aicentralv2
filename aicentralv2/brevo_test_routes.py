"""Formulário de teste de envio de e-mail via Brevo (sem Make)."""

from __future__ import annotations

import re

from flask import Blueprint, flash, render_template, request

from aicentralv2.auth import admin_required
from aicentralv2.services.cadu_growth_email_templates import (
    BREVO_GROWTH_TEST_RECIPIENT,
    list_growth_email_model_choices,
    run_growth_email_test_suite,
)

from aicentralv2.services.brevo_test_templates import (
    DEFAULT_BREVO_TEST_TEMPLATE,
    list_brevo_test_template_choices,
    run_brevo_email_test,
)

bp = Blueprint("brevo_test", __name__, url_prefix="/teste-brevo")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.route("/", methods=["GET", "POST"])
@admin_required
def formulario_teste_brevo():
    template_choices = list_brevo_test_template_choices()
    result = None
    form = {
        "to_email": "",
        "to_name": "Teste Brevo",
        "template": DEFAULT_BREVO_TEST_TEMPLATE,
        "dry_run": False,
    }

    if request.method == "POST":
        form["to_email"] = (request.form.get("to_email") or "").strip()
        form["to_name"] = (request.form.get("to_name") or "Teste Brevo").strip()
        form["template"] = (request.form.get("template") or DEFAULT_BREVO_TEST_TEMPLATE).strip()
        form["dry_run"] = request.form.get("dry_run") == "on"

        if not form["to_email"]:
            flash("Informe o e-mail destinatário.", "error")
        elif not _EMAIL_RE.match(form["to_email"]):
            flash("E-mail destinatário inválido.", "error")
        else:
            result = run_brevo_email_test(
                template_key=form["template"],
                to_email=form["to_email"],
                to_name=form["to_name"],
                dry_run=form["dry_run"],
            )
            if result.get("success"):
                if result.get("dry_run"):
                    flash("Pré-visualização gerada com sucesso. Nenhum e-mail foi enviado.", "success")
                else:
                    flash(
                        f"E-mail enviado! messageId: {result.get('messageId', '—')}",
                        "success",
                    )
            else:
                msg = result.get("user_message") or result.get("error") or "Falha no envio."
                if result.get("status_code") == 401 and "IP" in str(result.get("error", "")):
                    msg += (
                        " Libere o IP do servidor em "
                        "https://app.brevo.com/security/authorised_ips"
                    )
                flash(msg, "error")

    return render_template(
        "teste_brevo_email.html",
        template_choices=template_choices,
        default_template=DEFAULT_BREVO_TEST_TEMPLATE,
        form=form,
        result=result,
    )


@bp.route("/cadu-growth", methods=["GET", "POST"])
@admin_required
def teste_cadu_growth_emails():
    """Suíte de homologação dos modelos de adoção, exclusiva do administrador."""
    result = None
    model_choices = list_growth_email_model_choices()
    selected_models = [key for key, _label in model_choices]
    if request.method == "POST":
        selected_models = request.form.getlist("models")
        preview_only = request.form.get("mode") == "preview"
        try:
            result = run_growth_email_test_suite(
                dry_run=preview_only,
                model_keys=selected_models,
            )
            result["notice"] = (
                f"Prévia de {len(result['results'])} modelo(s) gerada. Nenhum e-mail foi enviado."
                if preview_only
                else f"{result['sent']} teste(s) enviado(s) para Apolo; {result['failed']} falha(s)."
            )
        except ValueError as exc:
            result = {
                "success": False,
                "dry_run": preview_only,
                "sent": 0,
                "failed": 0,
                "results": [],
                "notice": str(exc),
            }
    return render_template(
        "teste_cadu_growth_emails.html",
        recipient=BREVO_GROWTH_TEST_RECIPIENT,
        result=result,
        model_choices=model_choices,
        selected_models=selected_models,
    )
