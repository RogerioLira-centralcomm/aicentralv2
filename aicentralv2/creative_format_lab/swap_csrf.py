"""CSRF só das rotas POST do Trocr. GET de histórico e still usa cookie."""

from __future__ import annotations

import hmac
import secrets
from functools import wraps

from flask import jsonify, request, session

HEADER = "X-Trocr-CSRF-Token"
SESSION_KEY = "trocr_csrf_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_or_create_token():
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token


def trocr_csrf_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method in SAFE_METHODS:
            return view(*args, **kwargs)
        expected = session.get(SESSION_KEY) or ""
        received = request.headers.get(HEADER, "")
        if not expected or not received or not hmac.compare_digest(expected, received):
            return jsonify({"success": False, "error": "Token de segurança inválido."}), 403
        return view(*args, **kwargs)

    return wrapped
