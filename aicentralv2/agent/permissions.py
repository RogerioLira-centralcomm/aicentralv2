"""Autorização e proteção de requisições do Agente CentralX."""

import hmac
import secrets
from functools import wraps

from flask import jsonify, request, session


CAPABILITIES = {
    "commercial.read.global",
}


def agent_internal_required_api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "error": "Sessão expirada."}), 401
        if not session.get("is_centralcomm"):
            return jsonify({"success": False, "error": "Acesso restrito à equipe CentralComm."}), 403
        return view(*args, **kwargs)
    return wrapped


def get_or_create_csrf_token():
    token = session.get("agent_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["agent_csrf_token"] = token
    return token


def agent_csrf_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = session.get("agent_csrf_token") or ""
        received = request.headers.get("X-Agent-CSRF-Token", "")
        if not expected or not received or not hmac.compare_digest(expected, received):
            return jsonify({"success": False, "error": "Token de segurança inválido."}), 403
        return view(*args, **kwargs)
    return wrapped


def public_capabilities():
    return sorted(CAPABILITIES)
