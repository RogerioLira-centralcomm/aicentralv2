"""
API JSON interna para Display & Video 360 (OAuth + v4).
Requer sessão autenticada (login_required_api — 401 JSON, sem redirect HTML).

Página de diagnóstico (HTML, mesma sessão): GET /dv360/diagnostico
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from flask import Blueprint, current_app, jsonify, render_template, request

from aicentralv2.auth import login_required, login_required_api
from aicentralv2.services.dv360_client import DV360_ENDPOINTS, DV360API, get_dv360_client

logger = logging.getLogger(__name__)

bp = Blueprint("dv360", __name__, url_prefix="/api/dv360")
pages_bp = Blueprint("dv360_pages", __name__, url_prefix="/dv360")
parametros_bp = Blueprint("parametros", __name__, url_prefix="/parametros")


def _json_preview(obj: Any, max_len: int = 80000) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        s = repr(obj)
    if len(s) > max_len:
        return s[:max_len] + "\n\n... (saída truncada)"
    return s


def _campaign_finished_flight(
    client: Any, advertiser_id: str, campaign_id: str
) -> tuple[bool, Optional[dict[str, Any]]]:
    """True se o voo planejado já terminou (calendário), independentemente de entityStatus ACTIVE."""
    camp = client.get_campaign(str(advertiser_id).strip(), str(campaign_id).strip())
    if not camp.get("success"):
        return False, None
    lc = DV360API.infer_campaign_lifecycle_pt(camp.get("data") or {})
    if lc.get("code") == "FINISHED_FLIGHT":
        return True, lc
    return False, lc


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


@bp.route("/campaigns/geo-summaries", methods=["POST"])
@login_required_api
def campaign_geo_summaries():
    """
    Resumo de praça (geo) por campanha. Corpo JSON:
    {\"advertiser_id\": \"...\", \"campaign_ids\": [\"1\", \"2\", ...]} (máx. 80 ids por pedido).
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    advertiser_id = str(payload.get("advertiser_id") or "").strip()
    raw_ids = payload.get("campaign_ids") or []
    if not advertiser_id:
        return jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}), 400
    if not isinstance(raw_ids, list):
        return jsonify({"success": False, "error": "campaign_ids deve ser uma lista", "http_code": 400}), 400
    ids: list[str] = []
    for x in raw_ids[:80]:
        s = str(x).strip()
        if s and s not in ids:
            ids.append(s)
    client = get_dv360_client()
    summaries: dict[str, str] = {}
    errors: dict[str, str] = {}
    for cid in ids:
        pack = client.get_geo_summary_for_campaign(advertiser_id, cid)
        summary = str(pack.get("summary") or "—")
        summaries[cid] = summary
        if summary == "—":
            err_parts: list[str] = []
            if pack.get("campaign_geo_error"):
                err_parts.append(str(pack["campaign_geo_error"]))
            if pack.get("insertion_orders_error"):
                err_parts.append(str(pack["insertion_orders_error"]))
            if err_parts:
                errors[cid] = "; ".join(err_parts)
    return jsonify(
        {
            "success": True,
            "summaries": summaries,
            "errors": errors or None,
            "requested": len(ids),
        }
    )


@bp.route("/campaigns/<campaign_id>/detail", methods=["GET"])
@login_required_api
def campaign_detail(campaign_id: str):
    """Campanha + praça (geo) + estado. Query: advertiser_id obrigatório."""
    advertiser_id = request.args.get("advertiser_id", "").strip()
    if not advertiser_id:
        return jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}), 400
    cid = campaign_id.strip()
    client = get_dv360_client()
    camp = client.get_campaign(advertiser_id, cid)
    if not camp.get("success"):
        return jsonify(camp)
    pack = client.get_geo_summary_for_campaign(advertiser_id, cid)
    summary = str(pack.get("summary") or "—")
    regions = pack.get("regions") if isinstance(pack.get("regions"), list) else []
    geo_err = pack.get("campaign_geo_error")
    cdata = camp.get("data") or {}
    commercial = DV360API.summarize_campaign_commercial_snapshot(cdata)
    lifecycle = DV360API.infer_campaign_lifecycle_pt(cdata)
    return jsonify(
        {
            "success": True,
            "campaign": cdata,
            "lifecycle": lifecycle,
            "geo_summary": summary,
            "geo_regions": regions,
            "geo_source": pack.get("geo_source"),
            "geo_error": geo_err,
            "insertion_orders_error": pack.get("insertion_orders_error"),
            "campaign_metrics": commercial,
        }
    )


@bp.route("/campaigns/<campaign_id>", methods=["GET"])
@login_required_api
def campaign_one(campaign_id: str):
    """Detalhe de uma campanha (advertisers.campaigns.get). Query: advertiser_id obrigatório."""
    advertiser_id = request.args.get("advertiser_id", "").strip()
    if not advertiser_id:
        return jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}), 400
    client = get_dv360_client()
    return jsonify(client.get_campaign(advertiser_id, campaign_id.strip()))


@bp.route("/campaigns/<campaign_id>/pause", methods=["POST"])
@login_required_api
def campaign_pause(campaign_id: str):
    """Pausa campanha no DV360 (PATCH entityStatus=ENTITY_STATUS_PAUSED). Corpo JSON: {\"advertiser_id\": \"...\"}."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    advertiser_id = str(payload.get("advertiser_id") or "").strip()
    if not advertiser_id:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "advertiser_id é obrigatório no corpo JSON",
                    "http_code": 400,
                }
            ),
            400,
        )
    client = get_dv360_client()
    fin, lc_fin = _campaign_finished_flight(client, advertiser_id, campaign_id)
    if fin:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "O período planejado do voo já terminou; pausar ou reativar não se aplica.",
                    "http_code": 409,
                    "lifecycle": lc_fin,
                }
            ),
            409,
        )
    result = client.patch_campaign_entity_status(
        advertiser_id,
        campaign_id.strip(),
        "ENTITY_STATUS_PAUSED",
    )
    if isinstance(result, dict) and result.get("success") and isinstance(result.get("data"), dict):
        result = dict(result)
        result["lifecycle"] = DV360API.infer_campaign_lifecycle_pt(result["data"])
    return jsonify(result)


@bp.route("/campaigns/<campaign_id>/activate", methods=["POST"])
@login_required_api
def campaign_activate(campaign_id: str):
    """Ativa campanha no DV360 (PATCH entityStatus=ENTITY_STATUS_ACTIVE). Corpo JSON: {\"advertiser_id\": \"...\"}."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    advertiser_id = str(payload.get("advertiser_id") or "").strip()
    if not advertiser_id:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "advertiser_id é obrigatório no corpo JSON",
                    "http_code": 400,
                }
            ),
            400,
        )
    client = get_dv360_client()
    fin, lc_fin = _campaign_finished_flight(client, advertiser_id, campaign_id)
    if fin:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "O período planejado do voo já terminou; pausar ou reativar não se aplica.",
                    "http_code": 409,
                    "lifecycle": lc_fin,
                }
            ),
            409,
        )
    result = client.patch_campaign_entity_status(
        advertiser_id,
        campaign_id.strip(),
        "ENTITY_STATUS_ACTIVE",
    )
    if isinstance(result, dict) and result.get("success") and isinstance(result.get("data"), dict):
        result = dict(result)
        result["lifecycle"] = DV360API.infer_campaign_lifecycle_pt(result["data"])
    return jsonify(result)


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


@parametros_bp.route("/testesDV", methods=["GET"])
@login_required
def testes_dv():
    """Listar e pausar campanhas DV360 (chama APIs JSON com a sessão do browser)."""
    return render_template("parametros_testes_dv.html")
