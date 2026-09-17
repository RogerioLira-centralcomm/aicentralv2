"""Rotas públicas, sem shell ou navegação do CentralX."""

from flask import Blueprint, render_template, url_for


bp = Blueprint("cadu_presentation", __name__)


@bp.get("/cadu/apresentacao")
@bp.get("/cadu/apresentacao/")
def presentation():
    return render_template(
        "cadu_presentation/index.html",
        canonical=url_for("cadu_presentation.presentation", _external=True),
    )
