"""Agente CentralX — camada conversacional controlada do ERP."""

from flask import Blueprint

bp = Blueprint("agent", __name__, url_prefix="/api/agent")

from . import routes  # noqa: E402,F401
