"""Authenticated entry surface for Cadu Connect."""

from flask import Blueprint, render_template, session

from ..auth import login_required


bp = Blueprint("cadu_connect", __name__, url_prefix="/connect")


@bp.get("")
@bp.get("/")
@login_required
def index():
    return render_template(
        "cadu_portals/connect.html",
        account_name=session.get("user_name") or "Minha conta",
    )
