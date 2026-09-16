"""Endpoint público e autenticado para eventos transacionais da Brevo."""

from __future__ import annotations

import hmac
import logging

from flask import Blueprint, jsonify, request

from .services.integration_credentials import resolve_brevo_webhook_token


bp = Blueprint("brevo_webhook", __name__, url_prefix="/api/brevo")
logger = logging.getLogger(__name__)


def _provided_token() -> str:
    authorization = (request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return (
        request.headers.get("X-Webhook-Token")
        or request.headers.get("X-Webhook-Secret")
        or ""
    ).strip()


@bp.route("/webhook", methods=["POST"])
def receive_brevo_webhook():
    """Aceita eventos sem expor payload ou credenciais nos logs da aplicação."""
    expected = resolve_brevo_webhook_token()
    if not expected or not hmac.compare_digest(_provided_token(), expected):
        logger.warning("Webhook Brevo rejeitado: token ausente ou inválido.")
        return jsonify({"success": False, "error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form.to_dict(flat=True)
    events = payload if isinstance(payload, list) else [payload]
    event_types = sorted({
        str(event.get("event") or "unknown").strip().lower()
        for event in events if isinstance(event, dict)
    })
    logger.info(
        "Webhook Brevo recebido: %s evento(s), tipos=%s.",
        len(events), ",".join(event_types) or "unknown",
    )
    return jsonify({"success": True, "received": len(events)}), 200
