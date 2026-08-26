"""Protótipo visual CRM — dados fictícios, sem acesso ao banco."""

from flask import Blueprint, render_template

bp = Blueprint("crm_test", __name__, url_prefix="/teste-crm")


@bp.route("/")
def teste_crm_mock():
    return render_template("teste_crm_mock.html")
