"""Camadas V2 — decomposição persistente de criativos."""

from flask import current_app


def v2_enabled():
    try:
        return bool(current_app.config.get("CAMADAS_V2_ENABLED"))
    except RuntimeError:
        return False
