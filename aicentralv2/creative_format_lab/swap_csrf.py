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
        # Pages rendered before the token fix carry the Studio token. It is
        # still session-bound and random, so accept it during the transition
        # rather than forcing an authenticated editor to reload or log in.
        legacy_studio_token = session.get("studio_csrf_token") or ""
        valid_tokens = (expected, legacy_studio_token)
        if not received or not any(token and hmac.compare_digest(token, received) for token in valid_tokens):
            return jsonify({"success": False, "error": "Token de segurança inválido."}), 403
        return view(*args, **kwargs)

    return wrapped
