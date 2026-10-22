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
    from .services.cadu_email_sequence import apply_brevo_event
    for event in events:
        if not isinstance(event, dict):
            continue
        try:
            apply_brevo_event(event)
        except Exception:  # um evento ruim não derruba o lote; a Brevo reenviaria tudo
            logger.warning("Webhook Brevo: evento não aplicado ao registro de envios.", exc_info=True)
            _rollback()
        try:
            _aplicar_no_lead(event)
        except Exception:
            logger.warning("Webhook Brevo: evento não aplicado ao lead.", exc_info=True)
            _rollback()
    return jsonify({"success": True, "received": len(events)}), 200


def _rollback():
    try:
        from .db import get_db
        get_db().rollback()
    except Exception:
        pass


def _aplicar_no_lead(event):
    """E-mails do Leads v3 (enviados em nome do executivo): entrega, abertura, clique, bounce e descadastro."""
    from . import leads_v3_email
    from .db import get_db

    conn = get_db()
    with conn.cursor() as cursor:
        gravou = leads_v3_email.aplicar_evento_brevo(cursor, event)
    if gravou:
        conn.commit()
    else:
        conn.rollback()
