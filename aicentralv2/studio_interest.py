"""'Quero ser avisado' dos produtos do Studio ainda não lançados, sobre a tbl_interesse_produto (a mesma lista do ERP)."""
import logging

from flask import jsonify, request, session

from . import db
from .creative_format_lab.swap_csrf import trocr_csrf_required
from .creative_modeling_routes import studio_or_admin_required_api

logger = logging.getLogger(__name__)

# slug in the URL -> (tipo_produto stored, expected launch). Anything else is refused, so the table only gets known products.
PRODUCTS = {
    "audio": ("cadu_studio_audio", "2026-12"),
}


def _contact_id():
    try:
        return int(session.get("user_id") or 0) or None
    except (TypeError, ValueError):
        return None


def _client_ip():
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return (forwarded or request.remote_addr or "")[:45] or None


def _unavailable():
    return jsonify(success=False, error="Não foi possível registrar agora. Tente de novo em instantes."), 503


@studio_or_admin_required_api
def interest_status(product):
    if product not in PRODUCTS:
        return jsonify(success=False, error="Produto desconhecido."), 404
    contact = _contact_id()
    if not contact:
        return jsonify(success=True, data={"registered": False})
    try:
        rows = db.obter_interesses_produto(contato_id=contact, tipo_produto=PRODUCTS[product][0])
    except Exception:
        logger.warning("Falha ao consultar o interesse em %s", product, exc_info=True)
        return jsonify(success=True, data={"registered": False, "unknown": True})
    return jsonify(success=True, data={"registered": bool(rows), "launch": PRODUCTS[product][1]})


@studio_or_admin_required_api
@trocr_csrf_required
def interest_create(product):
    if product not in PRODUCTS:
        return jsonify(success=False, error="Produto desconhecido."), 404
    contact = _contact_id()
    if not contact:
        return jsonify(success=False, error="Entre na sua conta para ser avisado."), 401
    tipo, launch = PRODUCTS[product]
    try:
        # None means this contact is already on the list: same answer, nothing duplicated.
        db.criar_interesse_produto(
            contact, tipo, ip_registro=_client_ip(), user_agent=(request.headers.get("User-Agent") or "")[:500],
            dados_adicionais={"origem": "studio-modal-em-breve", "lancamento": launch},
        )
    except Exception:
        logger.error("Falha ao registrar interesse em %s", product, exc_info=True)
        return _unavailable()
    return jsonify(success=True, data={"registered": True, "launch": launch})


def register_api_routes(blueprint):
    blueprint.add_url_rule("/api/interesse/<product>", endpoint="studio_interest_status", view_func=interest_status, methods=["GET"])
    blueprint.add_url_rule("/api/interesse/<product>", endpoint="studio_interest_create", view_func=interest_create, methods=["POST"])
