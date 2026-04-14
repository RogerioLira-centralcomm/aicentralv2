"""
API JSON interna para Display & Video 360 (OAuth + v4).
Requer sessão autenticada (login_required_api — 401 JSON, sem redirect HTML).

Página de diagnóstico (HTML, mesma sessão): GET /dv360/diagnostico
"""
from __future__ import annotations

import json
import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, render_template, request

from aicentralv2.auth import login_required, login_required_api
from aicentralv2.services.dv360_client import DV360_ENDPOINTS, DV360API, get_dv360_client

logger = logging.getLogger(__name__)

bp = Blueprint("dv360", __name__, url_prefix="/api/dv360")
pages_bp = Blueprint("dv360_pages", __name__, url_prefix="/dv360")


def _json_preview(obj: Any, max_len: int = 80000) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        s = repr(obj)
    if len(s) > max_len:
        return s[:max_len] + "\n\n... (saída truncada)"
    return s


def _query_params() -> dict:
    """Mapeia query string para parâmetros da API Google (pageSize, pageToken, filter, orderBy)."""
    out: dict = {}
    if request.args.get("page_size"):
        out["pageSize"] = request.args.get("page_size")
    if request.args.get("page_token"):
        out["pageToken"] = request.args.get("page_token")
    if request.args.get("filter"):
        out["filter"] = request.args.get("filter")
    if request.args.get("order_by"):
        out["orderBy"] = request.args.get("order_by")
    return out


def _truthy(name: str) -> bool:
    v = request.args.get(name, "").lower()
    return v in ("1", "true", "yes", "on")


@bp.route("/health", methods=["GET"])
@login_required_api
def health():
    """
    Só configuração Flask + flags de .env — não chama o Google.
    Útil para ver rapidamente se variáveis existem e qual o host da requisição.
    """
    client = get_dv360_client()
    return jsonify(
        {
            "ok": True,
            "configured": client.is_configured(),
            "env": {
                "client_id_set": bool(client.client_id),
                "client_secret_set": bool(client.client_secret),
                "refresh_token_set": bool(client.refresh_token),
                "partner_id_set": bool(client.partner_id),
            },
            "api_base": client.api_base,
            "request_host": request.host,
            "url_root": request.url_root,
        }
    )


@pages_bp.route("/diagnostico", methods=["GET"])
@login_required
def diagnostico():
    """
    Relatório HTML gerado no servidor.

    Por defeito só mostra flags de .env (resposta imediata). Chamadas ao Google
    (OAuth + list_advertisers) só em ?run=1 para evitar timeout do browser
    ("invalid response") enquanto a rede demora.
    """
    run_tests = request.args.get("run", "").lower() in ("1", "true", "yes")
    client = DV360API(current_app.config)
    env_flags = {
        "DV360_CLIENT_ID": bool(client.client_id),
        "DV360_CLIENT_SECRET": bool(client.client_secret),
        "DV360_REFRESH_TOKEN": bool(client.refresh_token),
        "DV360_PARTNER_ID": bool(client.partner_id),
        "is_configured()": client.is_configured(),
    }
    connection: dict[str, Any] | None = None
    advertisers: dict[str, Any] | None = None
    advertisers_exc: str | None = None
    if run_tests:
        try:
            connection = client.test_connection()
        except Exception as e:
            logger.exception("DV360 diagnostico: test_connection")
            connection = {"success": False, "error": f"{type(e).__name__}: {e}"}
        if connection and connection.get("success"):
            try:
                advertisers = client.list_advertisers([], test_all=False)
            except Exception as e:
                logger.exception("DV360 diagnostico: list_advertisers")
                advertisers_exc = f"{type(e).__name__}: {e}"
    return render_template(
        "dv360_diagnostico.html",
        run_tests=run_tests,
        env_flags=env_flags,
        connection=connection,
        connection_json=_json_preview(connection) if connection is not None else "",
        advertisers=advertisers,
        advertisers_exc=advertisers_exc,
        advertisers_json=_json_preview(advertisers) if advertisers is not None else "",
        request_host=request.host,
        url_root=request.url_root,
    )


@bp.route("/connection", methods=["GET"])
@login_required_api
def connection():
    client = get_dv360_client()
    return jsonify(client.test_connection())


@bp.route("/advertisers", methods=["GET"])
@login_required_api
def advertisers():
    client = get_dv360_client()
    result = client.list_advertisers(_query_params(), test_all=_truthy("test_all"))
    return jsonify(result)


@bp.route("/partners", methods=["GET"])
@login_required_api
def partners():
    client = get_dv360_client()
    return jsonify(client.list_partners(_query_params()))


@bp.route("/campaigns", methods=["GET"])
@login_required_api
def campaigns():
    advertiser_id = request.args.get("advertiser_id", "").strip()
    if not advertiser_id:
        return jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}), 400
    client = get_dv360_client()
    return jsonify(client.list_campaigns(advertiser_id, _query_params()))


@bp.route("/insertion-orders", methods=["GET"])
@login_required_api
def insertion_orders():
    advertiser_id = request.args.get("advertiser_id", "").strip()
    if not advertiser_id:
        return jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}), 400
    client = get_dv360_client()
    return jsonify(client.list_insertion_orders(advertiser_id, _query_params()))


@bp.route("/line-items", methods=["GET"])
@login_required_api
def line_items():
    advertiser_id = request.args.get("advertiser_id", "").strip()
    if not advertiser_id:
        return jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}), 400
    client = get_dv360_client()
    return jsonify(client.list_line_items(advertiser_id, _query_params()))


@bp.route("/creatives", methods=["GET"])
@login_required_api
def creatives():
    advertiser_id = request.args.get("advertiser_id", "").strip()
    if not advertiser_id:
        return jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}), 400
    client = get_dv360_client()
    return jsonify(client.list_creatives(advertiser_id, _query_params()))


@bp.route("/google-audiences", methods=["GET"])
@login_required_api
def google_audiences_list():
    client = get_dv360_client()
    return jsonify(client.list_google_audiences(_query_params()))


@bp.route("/google-audiences/<google_audience_id>", methods=["GET"])
@login_required_api
def google_audience_one(google_audience_id: str):
    client = get_dv360_client()
    return jsonify(client.get_google_audience(google_audience_id))


@bp.route("/audiences/all", methods=["GET"])
@login_required_api
def audiences_all():
    adv = request.args.get("advertiser_id", "").strip() or None
    client = get_dv360_client()
    return jsonify(client.list_all_audiences(adv))


@bp.route("/audiences/<endpoint_type>", methods=["GET"])
@login_required_api
def audiences_by_type(endpoint_type: str):
    if endpoint_type not in DV360_ENDPOINTS:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"endpoint_type inválido. Use um de: {', '.join(DV360_ENDPOINTS)}",
                    "http_code": 400,
                }
            ),
            400,
        )
    adv = request.args.get("advertiser_id", "").strip() or None
    client = get_dv360_client()
    return jsonify(
        client.list_audiences(endpoint_type, adv, _query_params(), test_all=_truthy("test_all"))
    )


@bp.route("/audience/<audience_id>", methods=["GET"])
@login_required_api
def audience_resolve(audience_id: str):
    client = get_dv360_client()
    return jsonify(client.get_audience_data(audience_id))


@bp.route("/advertisers/<advertiser_id>/first-party/<audience_id>", methods=["GET"])
@login_required_api
def first_party_audience(advertiser_id: str, audience_id: str):
    client = get_dv360_client()
    return jsonify(client.get_first_party_audience(advertiser_id, audience_id))


@bp.route("/first-party-partner/<audience_id>", methods=["GET"])
@login_required_api
def first_party_partner_audience(audience_id: str):
    client = get_dv360_client()
    return jsonify(client.get_first_party_and_partner_audience(audience_id))


@bp.route("/combined/<audience_id>", methods=["GET"])
@login_required_api
def combined_audience(audience_id: str):
    client = get_dv360_client()
    return jsonify(client.get_combined_audience(audience_id))


@bp.route("/advertisers/<advertiser_id>/custom-lists/<custom_list_id>", methods=["GET"])
@login_required_api
def custom_list(advertiser_id: str, custom_list_id: str):
    client = get_dv360_client()
    return jsonify(client.get_custom_list(advertiser_id, custom_list_id))
