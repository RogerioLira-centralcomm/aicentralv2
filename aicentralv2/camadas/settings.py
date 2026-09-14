"""Modelo e resolução da geração — só via env/config, sem slug no serviço."""

from __future__ import annotations

import os


def image_model():
    return _config("CAMADAS_V2_IMAGE_MODEL", "")


def image_resolution():
    return _config("CAMADAS_V2_IMAGE_RESOLUTION", "1K") or "1K"


def image_configured():
    return bool(image_model())


def _config(name, default=""):
    try:
        from flask import current_app

        value = current_app.config.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    except RuntimeError:
        pass
    return str(os.getenv(name, default) or default).strip()
