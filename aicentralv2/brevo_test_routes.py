"""Formulário de teste de envio de e-mail via Brevo (sem Make)."""

from __future__ import annotations

import re

from flask import Blueprint, flash, render_template, request

from aicentralv2.services.brevo_test_templates import (
    DEFAULT_BREVO_TEST_TEMPLATE,
    list_brevo_test_template_choices,
    run_brevo_email_test,
)

bp = Blueprint("brevo_test", __name__, url_prefix="/teste-brevo")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.route("/", methods=["GET", "POST"])
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
