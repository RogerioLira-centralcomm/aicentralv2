"""
API JSON interna para Display & Video 360 (OAuth + v4).
Requer sessão autenticada (login_required_api — 401 JSON, sem redirect HTML).

Página de diagnóstico (HTML, mesma sessão): GET /dv360/diagnostico
"""
from __future__ import annotations

import io
import json
import logging
from typing import Any, Dict, List, Optional

from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from openpyxl import Workbook
from openpyxl.styles import Font
from psycopg.errors import UniqueViolation

from aicentralv2 import db
from aicentralv2.campanha_pi_metrics import (
    anexar_preco_metrica_campanha,
    meses_ref_pi_seguros,
    parse_brl_float,
    parse_volume_float,
    sigla_metrica_preco,
)
from aicentralv2.auth import get_current_user, login_required, login_required_api
from aicentralv2.services.dv360_client import DV360_ENDPOINTS, DV360API, get_dv360_client
from aicentralv2.services.dv360_reporting import (
    fetch_campaign_performance_from_reporting,
    sync_campaign_daily_metrics_range,
)

logger = logging.getLogger(__name__)

# GET Campaign / IOs de configuração não expõem «Spent» entregue nem «KPI actual» da UI; ver sync JSON metrics_notes.
DV360_METRICS_API_NOTES: dict[str, str] = {
    "spent": (
        "A coluna Spent do DV360 (gasto entregue) não vem do GET Campaign; plannedSpend é orçamento "
        "planejado, não gasto. É necessária a Reporting API para alinhar à interface."
    ),
    "kpi_atual": (
        "O campo kpi do pedido de inserção v4 é a meta (Goal) em «kpiAmountMicros», não o KPI entregue. "
        "KPI actual na UI requer métricas de desempenho (Reporting API)."
    ),
}


def _preview_hint_campaign_metrics_sync(
    *,
    include_reporting: bool,
    reporting_success: bool,
    reporting_error: Optional[str],
    d_start: date,
    d_end: date,
    spent_present: bool,
    kpi_atual_present: bool,
) -> str:
    """Uma linha para a UI — sem duplicar DV360_METRICS_API_NOTES."""
    if include_reporting and reporting_success:
        parts = [
            "Budget e KPI goal: GET Campaign (API DV360).",
            f"Spent e KPI entregue (eCPM): relatório Bid Manager ({d_start.isoformat()} a {d_end.isoformat()})."
            if (spent_present or kpi_atual_present)
            else f"Relatório Bid Manager corrido ({d_start.isoformat()} a {d_end.isoformat()}); sem linhas de custo/eCPM no período.",
            "Pronto para gravar na base com «Guardar».",
        ]
        return " ".join(parts)
    if include_reporting and reporting_error:
        err = (reporting_error or "erro desconhecido").strip()
        if len(err) > 240:
            err = err[:237] + "…"
        return (
            f"Budget e KPI goal: GET Campaign (API DV360). Relatório Bid Manager falhou: {err} "
            "«Guardar» persiste só budget/meta/KPI goal preenchidos pelo GET Campaign."
        )
    if not include_reporting:
        return (
            "Só dados de configuração (GET Campaign). «Guardar» persiste budget, KPI goal e tipo; spent/kpi entregue ficam em branco se não vierem doutra fonte."
        )
    return (
        "Pré-visualização mista. «Guardar na base» grava todos os campos numéricos enviados em metrics."
    )


def _metrics_provenance_payload(
    *,
    reporting_success: bool,
    spent_present: bool,
    kpi_atual_present: bool,
) -> dict[str, Optional[str]]:
    """Origem dos campos (para JSON / eventual badge na UI)."""
    return {
        "budget": "dv360_campaign_api",
        "kpi_goal": "dv360_campaign_api",
        "kpi_type": "dv360_campaign_api",
        "spent": "bid_manager_report" if (reporting_success and spent_present) else None,
        "kpi_atual": "bid_manager_report" if (reporting_success and kpi_atual_present) else None,
    }


def _parse_iso_date_optional(raw: Any) -> Optional[date]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
            return date(y, m, d)
        except (TypeError, ValueError):
            return None
    return None


def _coalesce_report_bounds(
    d_start: Optional[date], d_end: Optional[date]
) -> Optional[tuple[date, date]]:
    """Um único limite → dia único; dois limites → intervalo (ordena se necessário)."""
    if d_start is None and d_end is None:
        return None
    if d_start is not None and d_end is not None:
        if d_start > d_end:
            d_start, d_end = d_end, d_start
        return d_start, d_end
    if d_start is not None:
        return d_start, d_start
    assert d_end is not None
    return d_end, d_end


def _flight_planned_dates_from_campaign_json(cdata: dict) -> tuple[Optional[date], Optional[date]]:
    """Datas de voo em campaignFlight.plannedDates (mesma leitura que summarize_campaign_commercial_snapshot)."""
    cf = cdata.get("campaignFlight")
    if not isinstance(cf, dict):
        return None, None
    pd = cf.get("plannedDates")
    if not isinstance(pd, dict):
        return None, None
    sd_raw, ed_raw = pd.get("startDate"), pd.get("endDate")
    sd_iso = DV360API._dv360_format_date(sd_raw) if sd_raw else ""
    ed_iso = DV360API._dv360_format_date(ed_raw) if ed_raw else ""
    d_s = DV360API._dv360_iso_to_date(sd_iso) if sd_iso else None
    d_e = DV360API._dv360_iso_to_date(ed_iso) if ed_iso else None
    return d_s, d_e


def _parse_sync_body_date_fields(payload: dict) -> tuple[Optional[date], Optional[date], Optional[str]]:
    """
    start_date / end_date no corpo do sync: strings ISO ou omitidos.
    Devolve (start, end, erro_pt) — erro se valor presente e inválido.
    """
    raw_s = payload.get("start_date")
    raw_e = payload.get("end_date")
    has_s = raw_s is not None and str(raw_s).strip() != ""
    has_e = raw_e is not None and str(raw_e).strip() != ""
    if not has_s and not has_e:
        return None, None, None
    ds = _parse_iso_date_optional(raw_s) if has_s else None
    if has_s and ds is None:
        return None, None, "start_date inválido (use YYYY-MM-DD)"
    de = _parse_iso_date_optional(raw_e) if has_e else None
    if has_e and de is None:
        return None, None, "end_date inválido (use YYYY-MM-DD)"
    return ds, de, None


def _resolve_campaign_metrics_report_period(
    payload: dict,
    mapping_row: Any,
    cdata: dict,
) -> tuple[date, date, str]:
    """
    Prioridade: body (start_date/end_date) > dv360_campaigns > voo planejado > últimos 30 dias.
    Devolve (d_start, d_end, source) com source em body|table|flight|last_30d.
    """
    bs, be, err = _parse_sync_body_date_fields(payload)
    if err:
        raise ValueError(err)
    bounds = _coalesce_report_bounds(bs, be)
    if bounds is not None:
        d0, d1 = bounds
        return d0, d1, "body"

    row = dict(mapping_row) if mapping_row else {}
    rs = _parse_iso_date_optional(row.get("report_start_date"))
    re_ = _parse_iso_date_optional(row.get("report_end_date"))
    bounds = _coalesce_report_bounds(rs, re_)
    if bounds is not None:
        d0, d1 = bounds
        return d0, d1, "table"

    fs, fe = _flight_planned_dates_from_campaign_json(cdata if isinstance(cdata, dict) else {})
    bounds = _coalesce_report_bounds(fs, fe)
    if bounds is not None:
        d0, d1 = bounds
        return d0, d1, "flight"

    d_end = date.today()
    d_start = d_end - timedelta(days=30)
    return d_start, d_end, "last_30d"


def _dv360_audit_uid() -> Optional[int]:
    try:
        uid = get_current_user()
        return int(uid) if uid is not None else None
    except (TypeError, ValueError):
        return None


def _dv360_audit_write(
    entity_table: str,
    entity_pk: Optional[str],
    action: str,
    *,
    summary: Optional[str] = None,
    diff: Optional[Any] = None,
) -> None:
    try:
        db.registrar_dv360_audit(
            entity_table,
            entity_pk,
            action,
            changed_by=_dv360_audit_uid(),
            summary=summary,
            diff=diff,
        )
    except Exception:
        logger.exception("dv360_audit_write")


def _dv360_collect_insertion_orders_all(
    client: Any, advertiser_id: str, campaign_id: str
) -> Dict[str, Any]:
    cid = campaign_id.strip()
    params: Dict[str, Any] = {"pageSize": 500, "filter": f'campaignId="{cid}"'}
    all_ios: List[Any] = []
    while True:
        api_resp = client.list_insertion_orders(advertiser_id, params)
        if not api_resp.get("success"):
            return api_resp
        data = api_resp.get("data") or {}
        ios = data.get("insertionOrders") or []
        if isinstance(ios, list):
            all_ios.extend(ios)
        npt = data.get("nextPageToken")
        if not npt:
            break
        params["pageToken"] = str(npt)
    return {"success": True, "insertionOrders": all_ios}


def _dv360_collect_line_items_all(
    client: Any, advertiser_id: str, campaign_id: str
) -> Dict[str, Any]:
    cid = campaign_id.strip()
    params: Dict[str, Any] = {"pageSize": 500, "filter": f'campaignId="{cid}"'}
    all_li: List[Any] = []
    while True:
        api_resp = client.list_line_items(advertiser_id, params)
        if not api_resp.get("success"):
            return api_resp
        data = api_resp.get("data") or {}
        lis = data.get("lineItems") or []
        if isinstance(lis, list):
            all_li.extend(lis)
        npt = data.get("nextPageToken")
        if not npt:
            break
        params["pageToken"] = str(npt)
    return {"success": True, "lineItems": all_li}


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


def _campaign_filter_query_params(campaign_id: str) -> dict[str, Any]:
    """pageSize/pageToken/orderBy da query HTTP + filtro fixo por campanha (`campaignId`)."""
    cid = campaign_id.strip()
    out: dict[str, Any] = dict(_query_params())
    out["filter"] = f'campaignId="{cid}"'
    return out


def _truthy(name: str) -> bool:
    v = request.args.get(name, "").lower()
    return v in ("1", "true", "yes", "on")


def _dv360_campaign_db_for_json(row: Any) -> Optional[dict[str, Any]]:
    """Serializa linha dv360_campaigns para JSON (NUMERIC → float; datas relatório → ISO)."""
    if not row:
        return None
    d = dict(row)
    for k in ("budget", "spent", "kpi_goal", "kpi_atual"):
        v = d.get(k)
        if v is not None and isinstance(v, Decimal):
            d[k] = float(v)
    for dk in ("report_start_date", "report_end_date"):
        dv = _parse_iso_date_optional(d.get(dk))
        d[dk] = dv.isoformat() if dv is not None else None
    return d


def _dv360_parse_metric_value(val: Any, label: str = "valor") -> Optional[float]:
    """JSON metrics: None ou número → float opcional; >= 0."""
    if val is None:
        return None
    if isinstance(val, str) and not str(val).strip():
        return None
    try:
        v = float(val)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{label} inválido") from e
    if v < 0:
        raise ValueError(f"{label} deve ser >= 0")
    return v


def _dv360_parse_manual_metric_field(payload: dict[str, Any], key: str) -> Any:
    """
    Campo opcional no PUT: omitido → Ellipsis; null ou string vazia → None; número → float >= 0.
    """
    if key not in payload:
        return ...
    raw = payload.get(key)
    if raw is None:
        return None
    if isinstance(raw, str) and not str(raw).strip():
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{key} inválido") from e
    if v < 0:
        raise ValueError(f"{key} deve ser >= 0")
    return v


def _insertion_order_db_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    """Converte uma linha dv360_insertion_orders para chaves camelCase como na API DV360."""
    ut = row.get("update_time")
    if ut is not None and hasattr(ut, "isoformat"):
        ut_out = ut.isoformat()
    elif ut is not None:
        ut_out = str(ut)
    else:
        ut_out = None

    def _j(val: Any) -> Any:
        return val

    return {
        "insertionOrderId": str(row["insertion_order_id"]),
        "name": row.get("name"),
        "advertiserId": row.get("advertiser_id"),
        "campaignId": row.get("campaign_id"),
        "displayName": row.get("display_name"),
        "entityStatus": row.get("entity_status"),
        "insertionOrderType": row.get("insertion_order_type"),
        "billableOutcome": row.get("billable_outcome"),
        "optimizationObjective": row.get("optimization_objective"),
        "reservationType": row.get("reservation_type"),
        "updateTime": ut_out,
        "pacing": _j(row.get("pacing")),
        "frequencyCap": _j(row.get("frequency_cap")),
        "kpi": _j(row.get("kpi")),
        "budget": _j(row.get("budget")),
        "bidStrategy": _j(row.get("bid_strategy")),
        "partnerCosts": _j(row.get("partner_costs")),
        "integrationDetails": _j(row.get("integration_details")),
    }


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
    mapping_row = db.obter_dv360_campaign_por_campaigns_id(cid)
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
            "dv360_campaign_db": _dv360_campaign_db_for_json(mapping_row),
        }
    )


@bp.route("/campaigns/<campaign_id>/insertion-orders", methods=["GET"])
@login_required_api
def campaigns_insertion_orders_for_campaign(campaign_id: str):
    """
    Pedidos de inserção da campanha (`filter=campaignId="..."`). Query: advertiser_id obrigatório.

    Se existir mapeamento em dv360_campaigns e a tabela dv360_insertion_orders tiver linhas para essa
    campanha, devolve os dados a partir da BD (sem chamar o Google), salvo `force_api=1` na query
    (Recarregar na UI volta a ler só na API DV360).
    """
    advertiser_id = request.args.get("advertiser_id", "").strip()
    if not advertiser_id:
        return jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}), 400
    cid = campaign_id.strip()
    force_api = _truthy("force_api")

    if not force_api:
        mapping = db.obter_dv360_campaign_por_campaigns_id(cid)
        if mapping:
            dv360_campaign_pk = int(mapping["id"])
            if db.contar_dv360_insertion_orders_por_dv360_campaign(dv360_campaign_pk) > 0:
                rows = db.listar_dv360_insertion_orders_completos_por_dv360_campaign(dv360_campaign_pk)
                ios = [_insertion_order_db_row_to_api(r) for r in rows]
                return jsonify(
                    {
                        "success": True,
                        "data": {"insertionOrders": ios},
                        "http_code": 200,
                        "source": "database",
                    }
                )

    client = get_dv360_client()
    api_out = client.list_insertion_orders(
        advertiser_id, _campaign_filter_query_params(cid)
    )
    if isinstance(api_out, dict):
        api_out = dict(api_out)
        api_out["source"] = "api"
    return jsonify(api_out)


@bp.route("/campaigns/<campaign_id>/insertion-orders/sync", methods=["POST"])
@login_required_api
def campaigns_insertion_orders_sync(campaign_id: str):
    """
    Lista IOs na API DV360 (apenas GET / leitura) e faz UPSERT em dv360_insertion_orders.
    Não envia alterações ao DV360: sem PATCH/POST/DELETE no Google; escrita só em PostgreSQL.

    Corpo JSON: {\"advertiser_id\": \"...\"}.
    Requer linha em dv360_campaigns com campaigns_id = campaign_id (string DV360).
    Paginação completa via nextPageToken.
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    advertiser_id = str(payload.get("advertiser_id") or "").strip()
    if not advertiser_id:
        return (
            jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}),
            400,
        )
    cid = campaign_id.strip()
    mapping = db.obter_dv360_campaign_por_campaigns_id(cid)
    if not mapping:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Esta campanha DV360 ainda não está mapeada em dv360_campaigns. "
                        "Associe-a primeiro na aba 'Acomp. PI (DV360)'."
                    ),
                    "missing_mapping": True,
                    "http_code": 409,
                }
            ),
            409,
        )
    dv360_campaign_pk = int(mapping["id"])

    client = get_dv360_client()
    api_resp = _dv360_collect_insertion_orders_all(client, advertiser_id, cid)
    if not api_resp.get("success"):
        code = int(api_resp.get("http_code") or 502)
        return jsonify(api_resp), code

    ios = api_resp.get("insertionOrders") or []
    if not isinstance(ios, list):
        ios = []

    created = 0
    updated = 0
    errors: List[dict[str, Any]] = []
    for io in ios:
        if not isinstance(io, dict):
            continue
        try:
            res = db.upsert_dv360_insertion_order(dv360_campaign_pk, io)
            if res.get("inserted"):
                created += 1
            else:
                updated += 1
        except Exception as e:
            logger.exception("DV360 insertion order upsert")
            errors.append(
                {
                    "insertion_order_id": io.get("insertionOrderId"),
                    "error": f"{type(e).__name__}: {e}",
                }
            )

    total_db = db.contar_dv360_insertion_orders_por_dv360_campaign(dv360_campaign_pk)

    _dv360_audit_write(
        "dv360_insertion_orders",
        str(dv360_campaign_pk),
        "update",
        summary=f"sync IOs campaign={cid} created={created} updated={updated}",
    )

    return jsonify(
        {
            "success": True,
            "total_api": len(ios),
            "created": created,
            "updated": updated,
            "errors": errors or None,
            "dv360_campaign_id": dv360_campaign_pk,
            "total_db": total_db,
        }
    )


@bp.route("/campaigns/<campaign_id>/line-items/sync", methods=["POST"])
@login_required_api
def campaigns_line_items_sync(campaign_id: str):
    """
    Lista line items na API (GET) e grava em dv360_line_items.
    Requer IOs já sincronizados em dv360_insertion_orders para resolver insertionOrderId.

    Corpo JSON: {\"advertiser_id\": \"...\"}.
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    advertiser_id = str(payload.get("advertiser_id") or "").strip()
    if not advertiser_id:
        return (
            jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}),
            400,
        )
    cid = campaign_id.strip()
    mapping = db.obter_dv360_campaign_por_campaigns_id(cid)
    if not mapping:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Esta campanha DV360 ainda não está mapeada em dv360_campaigns. "
                        "Associe-a primeiro na aba 'Acomp. PI (DV360)'."
                    ),
                    "missing_mapping": True,
                    "http_code": 409,
                }
            ),
            409,
        )
    dv360_campaign_pk = int(mapping["id"])

    client = get_dv360_client()
    api_resp = _dv360_collect_line_items_all(client, advertiser_id, cid)
    if not api_resp.get("success"):
        code = int(api_resp.get("http_code") or 502)
        return jsonify(api_resp), code

    lis = api_resp.get("lineItems") or []
    if not isinstance(lis, list):
        lis = []

    created = 0
    updated = 0
    skipped: List[dict[str, Any]] = []
    errors: List[dict[str, Any]] = []
    for li in lis:
        if not isinstance(li, dict):
            continue
        ioid = li.get("insertionOrderId")
        if ioid is None or str(ioid).strip() == "":
            skipped.append({"line_item_id": li.get("lineItemId"), "reason": "sem insertionOrderId"})
            continue
        pk = db.obter_dv360_insertion_order_internal_id(dv360_campaign_pk, str(ioid))
        if pk is None:
            skipped.append(
                {
                    "line_item_id": li.get("lineItemId"),
                    "insertion_order_id": str(ioid),
                    "reason": "IO não encontrado na BD — execute insertion-orders/sync primeiro.",
                }
            )
            continue
        try:
            res = db.upsert_dv360_line_item(pk, li)
            if res.get("inserted"):
                created += 1
            else:
                updated += 1
        except Exception as e:
            logger.exception("DV360 line item upsert")
            errors.append(
                {
                    "line_item_id": li.get("lineItemId"),
                    "error": f"{type(e).__name__}: {e}",
                }
            )

    total_db = db.contar_dv360_line_items_por_dv360_campaign(dv360_campaign_pk)

    _dv360_audit_write(
        "dv360_line_items",
        str(dv360_campaign_pk),
        "update",
        summary=f"sync line items campaign={cid} created={created} updated={updated}",
    )

    return jsonify(
        {
            "success": True,
            "total_api": len(lis),
            "created": created,
            "updated": updated,
            "skipped": skipped or None,
            "errors": errors or None,
            "dv360_campaign_id": dv360_campaign_pk,
            "total_db": total_db,
        }
    )


@bp.route("/campaigns/<campaign_id>/period", methods=["POST"])
@login_required_api
def campaign_report_period_save(campaign_id: str):
    """
    Grava report_start_date / report_end_date em dv360_campaigns (período do relatório Bid Manager).

    Corpo JSON: report_start_date, report_end_date — cada um YYYY-MM-DD, null ou omitido para limpar
    só se enviado explicitamente como null; omitido = manter valor na BD.
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    cid = campaign_id.strip()
    mapping = db.obter_dv360_campaign_por_campaigns_id(cid)
    if not mapping:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Esta campanha DV360 ainda não está mapeada em dv360_campaigns. "
                        "Associe-a primeiro na aba 'Acomp. PI (DV360)'."
                    ),
                    "missing_mapping": True,
                    "http_code": 409,
                }
            ),
            409,
        )

    def _field_from_payload(key: str) -> tuple[Any, bool]:
        """(valor date|None, presente_no_json)."""
        if key not in payload:
            return None, False
        raw = payload.get(key)
        if raw is None or (isinstance(raw, str) and not str(raw).strip()):
            return None, True
        d = _parse_iso_date_optional(raw)
        if d is None:
            raise ValueError(f"{key} inválido (use YYYY-MM-DD)")
        return d, True

    try:
        new_s, pres_s = _field_from_payload("report_start_date")
        new_e, pres_e = _field_from_payload("report_end_date")
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "http_code": 400}), 400

    cur_s = _parse_iso_date_optional(mapping.get("report_start_date"))
    cur_e = _parse_iso_date_optional(mapping.get("report_end_date"))
    out_s = new_s if pres_s else cur_s
    out_e = new_e if pres_e else cur_e

    if out_s is not None and out_e is not None and out_s > out_e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "report_start_date não pode ser posterior a report_end_date.",
                    "http_code": 400,
                }
            ),
            400,
        )

    db_s = new_s if pres_s else mapping.get("report_start_date")
    db_e = new_e if pres_e else mapping.get("report_end_date")

    pk = int(mapping["id"])
    db.atualizar_dv360_campaign_periodo(pk, report_start_date=db_s, report_end_date=db_e)
    row = db.obter_dv360_campaign_por_campaigns_id(cid)
    _dv360_audit_write(
        "dv360_campaigns",
        str(pk),
        "update",
        summary=f"report period campaign={cid}",
        diff={"report_start_date": str(db_s) if db_s is not None else None, "report_end_date": str(db_e) if db_e is not None else None},
    )
    return jsonify(
        {
            "success": True,
            "dv360_campaign_db": _dv360_campaign_db_for_json(row),
        }
    )


@bp.route("/campaigns/<campaign_id>/metrics/history/sync", methods=["POST"])
@login_required_api
def campaign_metrics_history_sync(campaign_id: str):
    """
    Obtém série diária (Bid Manager) e grava em dv360_campaign_metrics_daily.

    Corpo JSON: advertiser_id (obrigatório), start_date, end_date (YYYY-MM-DD).
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    advertiser_id = str(payload.get("advertiser_id") or "").strip()
    if not advertiser_id:
        return (
            jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}),
            400,
        )
    cid = campaign_id.strip()
    mapping = db.obter_dv360_campaign_por_campaigns_id(cid)
    if not mapping:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Esta campanha DV360 ainda não está mapeada em dv360_campaigns. "
                        "Associe-a primeiro na aba 'Acomp. PI (DV360)'."
                    ),
                    "missing_mapping": True,
                    "http_code": 409,
                }
            ),
            409,
        )
    dv360_campaign_pk = int(mapping["id"])

    raw_s = payload.get("start_date")
    raw_e = payload.get("end_date")
    ds = _parse_iso_date_optional(raw_s)
    de = _parse_iso_date_optional(raw_e)
    if ds is None or de is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "start_date e end_date são obrigatórios (YYYY-MM-DD).",
                    "http_code": 400,
                }
            ),
            400,
        )
    if ds > de:
        ds, de = de, ds

    client = get_dv360_client()
    rpt = sync_campaign_daily_metrics_range(client, advertiser_id, cid, ds, de)
    if not rpt.get("success"):
        code = int(rpt.get("http_code") or 502)
        return jsonify(rpt), code

    daily = rpt.get("daily") if isinstance(rpt.get("daily"), list) else []
    rows_written = 0
    for row in daily:
        if not isinstance(row, dict):
            continue
        md = _parse_iso_date_optional(row.get("metric_date"))
        if md is None:
            continue
        db.upsert_dv360_campaign_metrics_daily_row(
            dv360_campaign_pk,
            md,
            spent=row.get("spent"),
            impressions=row.get("impressions"),
            cpm=row.get("cpm"),
            clicks=row.get("clicks"),
            cpc=row.get("cpc"),
            source=str(rpt.get("source") or "bid_manager"),
        )
        rows_written += 1

    _dv360_audit_write(
        "dv360_campaign_metrics_daily",
        str(dv360_campaign_pk),
        "update",
        summary=f"history sync {ds.isoformat()}..{de.isoformat()} rows={rows_written}",
    )

    return jsonify(
        {
            "success": True,
            "rows_written": rows_written,
            "daily_preview": daily[:31],
            "source": rpt.get("source"),
            "fallback_note": rpt.get("fallback_note"),
            "dv360_campaign_id": dv360_campaign_pk,
        }
    )


@bp.route("/campaigns/<campaign_id>/metrics/history", methods=["GET"])
@login_required_api
def campaign_metrics_history_get(campaign_id: str):
    """Série gravada em dv360_campaign_metrics_daily (opcional start_date / end_date query)."""
    cid = campaign_id.strip()
    mapping = db.obter_dv360_campaign_por_campaigns_id(cid)
    if not mapping:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Esta campanha DV360 ainda não está mapeada em dv360_campaigns. "
                        "Associe-a primeiro na aba 'Acomp. PI (DV360)'."
                    ),
                    "missing_mapping": True,
                    "http_code": 409,
                }
            ),
            409,
        )
    dv360_campaign_pk = int(mapping["id"])
    qs = request.args.get("start_date")
    qe = request.args.get("end_date")
    ds = _parse_iso_date_optional(qs) if qs else None
    de = _parse_iso_date_optional(qe) if qe else None
    if ds is not None and de is not None:
        rows = db.listar_dv360_campaign_metrics_daily(dv360_campaign_pk, ds, de)
    elif ds is not None:
        rows = db.listar_dv360_campaign_metrics_daily(dv360_campaign_pk, ds, ds)
    elif de is not None:
        rows = db.listar_dv360_campaign_metrics_daily(dv360_campaign_pk, de, de)
    else:
        rows = db.listar_dv360_campaign_metrics_daily(dv360_campaign_pk)
    return jsonify({"success": True, "data": rows, "dv360_campaign_id": dv360_campaign_pk})


@bp.route("/audit/view", methods=["POST"])
@login_required_api
def dv360_audit_view():
    """Regista visualização de recurso DV360 (ex.: página testes)."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    resource = str(payload.get("resource") or "").strip()[:128]
    resource_key = str(payload.get("resource_key") or "").strip()[:256]
    if not resource:
        return jsonify({"success": False, "error": "resource é obrigatório", "http_code": 400}), 400
    try:
        rid = db.registrar_dv360_audit(
            "dv360_view",
            None,
            "view",
            changed_by=_dv360_audit_uid(),
            summary=f"{resource}",
            resource=resource,
            resource_key=resource_key or None,
        )
    except Exception as e:
        logger.exception("dv360_audit_view")
        return jsonify({"success": False, "error": str(e), "http_code": 500}), 500
    return jsonify({"success": True, "id": rid})


@bp.route("/audit/recent", methods=["GET"])
@login_required_api
def dv360_audit_recent():
    """Últimas entradas de auditoria DV360 (admin / diagnóstico)."""
    if not _is_dv_session_admin():
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403
    et = request.args.get("entity_table")
    lim_raw = request.args.get("limit", "200")
    try:
        lim = int(lim_raw)
    except (TypeError, ValueError):
        lim = 200
    rows = db.listar_dv360_audit_recent(entity_table=et or None, limit=lim)
    return jsonify({"success": True, "data": rows})


@bp.route("/campaigns/<campaign_id>/metrics/sync", methods=["POST"])
@login_required_api
def campaign_metrics_sync(campaign_id: str):
    """
    GET Campaign (budget + KPI goal) + Bid Manager v2 (spent + eCPM entregues), sem gravar na BD.

      Corpo JSON:
      advertiser_id (obrigatório)
      start_date, end_date (opcional, YYYY-MM-DD) — override pontual do período do relatório.
      Sem override no corpo: usa report_start_date/report_end_date da BD; senão voo planejado;
      senão últimos 30 dias (fim = hoje).
      include_reporting (opcional, default true) — se false, só GET Campaign.
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    advertiser_id = str(payload.get("advertiser_id") or "").strip()
    if not advertiser_id:
        return (
            jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}),
            400,
        )
    cid = campaign_id.strip()
    mapping = db.obter_dv360_campaign_por_campaigns_id(cid)
    if not mapping:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Esta campanha DV360 ainda não está mapeada em dv360_campaigns. "
                        "Associe-a primeiro na aba 'Acomp. PI (DV360)'."
                    ),
                    "missing_mapping": True,
                    "http_code": 409,
                }
            ),
            409,
        )
    client = get_dv360_client()
    camp = client.get_campaign(advertiser_id, cid)
    if not camp.get("success"):
        code = int(camp.get("http_code") or 502)
        return jsonify(camp), code

    cdata = camp.get("data") or {}
    if not isinstance(cdata, dict):
        cdata = {}
    metrics = DV360API.extract_campaign_metrics_for_db(cdata)

    include_reporting = payload.get("include_reporting")
    if include_reporting is None:
        include_reporting = True
    elif isinstance(include_reporting, str):
        include_reporting = include_reporting.lower() in ("1", "true", "yes", "on")

    reporting_info: Optional[dict[str, Any]] = None
    reporting_error: Optional[str] = None
    reporting_success = False

    try:
        d_start, d_end, period_src = _resolve_campaign_metrics_report_period(payload, mapping, cdata)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "http_code": 400}), 400

    period_used = {
        "start": d_start.isoformat(),
        "end": d_end.isoformat(),
        "source": period_src,
    }

    if include_reporting:
        rpt = fetch_campaign_performance_from_reporting(
            client, advertiser_id, cid, d_start, d_end
        )
        if rpt.get("success"):
            reporting_success = True
            if rpt.get("spent") is not None:
                metrics["spent"] = rpt["spent"]
            if rpt.get("kpi_atual") is not None:
                metrics["kpi_atual"] = rpt["kpi_atual"]
            reporting_info = {
                "source": rpt.get("source"),
                "query_id": rpt.get("query_id"),
                "rows_used": rpt.get("rows_used"),
                "impressions": rpt.get("impressions"),
                "clicks": rpt.get("clicks"),
                "start_date": rpt.get("start_date"),
                "end_date": rpt.get("end_date"),
                "parse_hint": rpt.get("parse_hint"),
                "columns_matched": rpt.get("columns_matched"),
            }
        else:
            reporting_error = rpt.get("error") or "Relatório Bid Manager indisponível."
            if int(rpt.get("http_code") or 0) in (401, 403):
                reporting_error = (
                    f"{reporting_error} "
                    "Confirme o scope doubleclickbidmanager e volte a gerar o refresh token com consentimento completo."
                )

    spent_present = metrics.get("spent") is not None
    kpi_atual_present = metrics.get("kpi_atual") is not None
    preview_hint_pt = _preview_hint_campaign_metrics_sync(
        include_reporting=bool(include_reporting),
        reporting_success=reporting_success,
        reporting_error=reporting_error,
        d_start=d_start,
        d_end=d_end,
        spent_present=spent_present,
        kpi_atual_present=kpi_atual_present,
    )

    out: dict[str, Any] = {
        "success": True,
        "metrics": metrics,
        "preview_hint_pt": preview_hint_pt,
        "metrics_provenance": _metrics_provenance_payload(
            reporting_success=reporting_success,
            spent_present=spent_present,
            kpi_atual_present=kpi_atual_present,
        ),
        "metrics_notes": {"summary": preview_hint_pt},
        "reporting_date_start": d_start.isoformat(),
        "reporting_date_end": d_end.isoformat(),
        "period_used": period_used,
        "dv360_campaign_db": _dv360_campaign_db_for_json(mapping),
    }
    if reporting_info is not None:
        out["reporting"] = reporting_info
    if reporting_error is not None:
        out["reporting_error"] = reporting_error
    return jsonify(out)


@bp.route("/campaigns/<campaign_id>/metrics/save", methods=["POST"])
@login_required_api
def campaign_metrics_save(campaign_id: str):
    """
    Grava em dv360_campaigns budget, spent, kpi_goal, kpi_atual, kpi_type (corpo \"metrics\").

    O mesmo objeto ``metrics`` devolvido por POST .../metrics/sync (incl. spent/kpi do Bid Manager, se houver).
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        metrics = dict(payload) if payload else {}
        metrics.pop("advertiser_id", None)
    cid = campaign_id.strip()
    mapping = db.obter_dv360_campaign_por_campaigns_id(cid)
    if not mapping:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Esta campanha DV360 ainda não está mapeada em dv360_campaigns. "
                        "Associe-a primeiro na aba 'Acomp. PI (DV360)'."
                    ),
                    "missing_mapping": True,
                    "http_code": 409,
                }
            ),
            409,
        )
    dv360_campaign_pk = int(mapping["id"])
    try:
        budget = _dv360_parse_metric_value(metrics.get("budget"), "budget")
        spent = _dv360_parse_metric_value(metrics.get("spent"), "spent")
        kpi_goal = _dv360_parse_metric_value(metrics.get("kpi_goal"), "kpi_goal")
        kpi_atual = _dv360_parse_metric_value(metrics.get("kpi_atual"), "kpi_atual")
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "http_code": 400}), 400

    kt_raw = metrics.get("kpi_type")
    if kt_raw is not None and str(kt_raw).strip():
        kpi_type = str(kt_raw).strip()[:64]
    else:
        kpi_type = None

    ok = db.atualizar_dv360_campaign_metricas_api(
        dv360_campaign_pk,
        budget=budget,
        spent=spent,
        kpi_goal=kpi_goal,
        kpi_atual=kpi_atual,
        kpi_type=kpi_type,
    )
    if not ok:
        return (
            jsonify({"success": False, "error": "Registo dv360_campaigns não encontrado", "http_code": 404}),
            404,
        )
    refreshed = db.obter_dv360_campaign_por_campaigns_id(cid)
    _dv360_audit_write(
        "dv360_campaigns",
        str(dv360_campaign_pk),
        "update",
        summary=f"metrics save campaign={cid}",
    )
    return jsonify({"success": True, "dv360_campaign_db": _dv360_campaign_db_for_json(refreshed)})


@bp.route("/campaigns/<campaign_id>/metrics", methods=["PUT"])
@login_required_api
def campaign_metrics_manual(campaign_id: str):
    """
    Actualiza spent e kpi_atual (relatório manual). Corpo JSON: {\"spent\", \"kpi_atual\"}
    (cada um opcional; null ou string vazia limpa a coluna; valores numéricos >= 0).
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    cid = campaign_id.strip()
    mapping = db.obter_dv360_campaign_por_campaigns_id(cid)
    if not mapping:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Esta campanha DV360 ainda não está mapeada em dv360_campaigns. "
                        "Associe-a primeiro na aba 'Acomp. PI (DV360)'."
                    ),
                    "missing_mapping": True,
                    "http_code": 409,
                }
            ),
            409,
        )
    dv360_campaign_pk = int(mapping["id"])
    try:
        spent = _dv360_parse_manual_metric_field(payload, "spent")
        kpi_atual = _dv360_parse_manual_metric_field(payload, "kpi_atual")
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "http_code": 400}), 400

    try:
        ok = db.atualizar_dv360_campaign_metricas_manuais(
            dv360_campaign_pk, spent=spent, kpi_atual=kpi_atual
        )
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "http_code": 400}), 400

    if not ok:
        return (
            jsonify({"success": False, "error": "Registo dv360_campaigns não encontrado", "http_code": 404}),
            404,
        )
    refreshed = db.obter_dv360_campaign_por_campaigns_id(cid)
    _dv360_audit_write(
        "dv360_campaigns",
        str(dv360_campaign_pk),
        "update",
        summary=f"metrics manual campaign={cid}",
    )
    return jsonify({"success": True, "dv360_campaign_db": _dv360_campaign_db_for_json(refreshed)})


@bp.route("/campaigns/<campaign_id>/line-items", methods=["GET"])
@login_required_api
def campaigns_line_items_for_campaign(campaign_id: str):
    """Line items da campanha (`filter=campaignId="..."`). Query: advertiser_id obrigatório."""
    advertiser_id = request.args.get("advertiser_id", "").strip()
    if not advertiser_id:
        return jsonify({"success": False, "error": "advertiser_id é obrigatório", "http_code": 400}), 400
    client = get_dv360_client()
    return jsonify(
        client.list_line_items(advertiser_id, _campaign_filter_query_params(campaign_id))
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


def _is_dv_session_admin() -> bool:
    return session.get("user_type") in ("admin", "superadmin")


def _session_cliente_id() -> Optional[int]:
    cid = session.get("cliente_id")
    if cid is None:
        return None
    try:
        return int(cid)
    except (TypeError, ValueError):
        return None


def _pode_aceder_cliente(cliente_id: int) -> bool:
    if _is_dv_session_admin():
        return True
    sid = _session_cliente_id()
    return sid is not None and sid == int(cliente_id)


@bp.route("/client-mappings", methods=["GET"])
@login_required_api
def client_mappings_list():
    """
    Lista mapeamentos dv360_advertisers para um cliente (com nome_fantasia via JOIN).
    Administradores: ?all=1 lista todos; senão query cliente_id obrigatório.
    Utilizador normal: só o próprio cliente (ignora all=1).
    """
    q_cid = request.args.get("cliente_id", type=int)
    if _is_dv_session_admin() and _truthy("all"):
        rows = db.listar_todos_dv360_advertisers_com_cliente()
        return jsonify({"success": True, "data": rows})

    if _is_dv_session_admin():
        if q_cid is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "cliente_id é obrigatório para administradores (ou use all=1)",
                        "http_code": 400,
                    }
                ),
                400,
            )
        target = q_cid
    else:
        sid = _session_cliente_id()
        if sid is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Sessão sem cliente associado",
                        "http_code": 400,
                    }
                ),
                400,
            )
        if q_cid is not None and q_cid != sid:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Acesso negado a outro cliente",
                        "http_code": 403,
                    }
                ),
                403,
            )
        target = sid

    if not _pode_aceder_cliente(target):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    rows = db.listar_dv360_advertisers_por_cliente(target)
    return jsonify({"success": True, "data": rows})


@bp.route("/clientes-para-mapeamento-dv", methods=["GET"])
@login_required_api
def clientes_para_mapeamento_dv():
    """
    Lista clientes para o modal de novo mapeamento em dv360_advertisers (id_cliente, nome_fantasia, razao_social).
    Administradores: todos os clientes (ordenados por nome_fantasia). Utilizador normal: só o da sessão.
    """
    if _is_dv_session_admin():
        rows = db.obter_clientes_para_filtro()
        return jsonify({"success": True, "data": rows})
    sid = _session_cliente_id()
    if sid is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Sessão sem cliente associado",
                    "http_code": 400,
                }
            ),
            400,
        )
    cli = db.obter_cliente_por_id(sid)
    nome = (cli or {}).get("nome_fantasia") or "—"
    razao = (cli or {}).get("razao_social")
    return jsonify(
        {
            "success": True,
            "data": [{"id_cliente": sid, "nome_fantasia": nome, "razao_social": razao}],
        }
    )


@bp.route("/client-mappings", methods=["POST"])
@login_required_api
def client_mappings_create():
    """Cria mapeamento cliente_id + dv_anunciante_id."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    raw_cid = payload.get("cliente_id")
    dv_anunciante_id = payload.get("dv_anunciante_id")
    try:
        cliente_id = int(raw_cid)
    except (TypeError, ValueError):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "cliente_id inválido ou em falta",
                    "http_code": 400,
                }
            ),
            400,
        )

    if not _pode_aceder_cliente(cliente_id):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    try:
        new_id = db.criar_dv360_advertiser(cliente_id, dv_anunciante_id)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "http_code": 400}), 400

    if new_id is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Este dv_anunciante_id já está em uso noutro mapeamento",
                    "http_code": 409,
                }
            ),
            409,
        )

    row = db.obter_dv360_advertiser_por_id(new_id)
    _dv360_audit_write(
        "dv360_advertisers",
        str(new_id),
        "insert",
        summary=f"cliente={cliente_id} dv_anunciante={dv_anunciante_id}",
    )
    return jsonify({"success": True, "data": row}), 201


@bp.route("/client-mappings/<int:mapping_id>", methods=["PATCH"])
@login_required_api
def client_mappings_update(mapping_id: int):
    """Atualiza dv_anunciante_id de um mapeamento existente."""
    row = db.obter_dv360_advertiser_por_id(mapping_id)
    if not row:
        return jsonify({"success": False, "error": "Registo não encontrado", "http_code": 404}), 404
    if not _pode_aceder_cliente(int(row["cliente_id"])):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    dv_anunciante_id = payload.get("dv_anunciante_id")

    try:
        ok = db.atualizar_dv360_advertiser(mapping_id, dv_anunciante_id)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "http_code": 400}), 400

    if not ok:
        return jsonify({"success": False, "error": "Registo não encontrado", "http_code": 404}), 404

    updated = db.obter_dv360_advertiser_por_id(mapping_id)
    _dv360_audit_write(
        "dv360_advertisers",
        str(mapping_id),
        "update",
        summary=f"dv_anunciante_id={dv_anunciante_id}",
    )
    return jsonify({"success": True, "data": updated})


@bp.route("/client-mappings/<int:mapping_id>", methods=["DELETE"])
@login_required_api
def client_mappings_delete(mapping_id: int):
    """Remove um mapeamento por id."""
    row = db.obter_dv360_advertiser_por_id(mapping_id)
    if not row:
        return jsonify({"success": False, "error": "Registo não encontrado", "http_code": 404}), 404
    if not _pode_aceder_cliente(int(row["cliente_id"])):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    db.excluir_dv360_advertiser(mapping_id)
    _dv360_audit_write(
        "dv360_advertisers",
        str(mapping_id),
        "delete",
        summary=f"cliente={row.get('cliente_id')} dv={row.get('dv_anunciante_id')}",
    )
    return jsonify({"success": True, "data": {"id": mapping_id}})


@bp.route("/pi-dv360-campaigns", methods=["GET"])
@login_required_api
def pi_dv360_campaigns_list():
    """
    Lista mapeamentos dv360_campaigns.
    Administradores: ?all=1 lista todos (com JOIN campanha/cliente).
    Caso contrário: query campanha_id obrigatório; filtro por acesso ao cliente da campanha PI.
    """
    q_camp = request.args.get("campanha_id", type=int)
    if _is_dv_session_admin() and _truthy("all"):
        rows = db.listar_todos_dv360_campaigns()
        return jsonify({"success": True, "data": rows})

    if q_camp is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "campanha_id é obrigatório (ou use all=1 como administrador)",
                    "http_code": 400,
                }
            ),
            400,
        )

    camp = db.obter_campanha_pi_por_id(q_camp)
    if not camp or camp.get("id_cliente") is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Campanha PI não encontrada",
                    "http_code": 404,
                }
            ),
            404,
        )

    if not _pode_aceder_cliente(int(camp["id_cliente"])):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    rows = db.listar_dv360_campaigns_por_campanha(q_camp)
    return jsonify({"success": True, "data": rows})


@bp.route("/pi-dv360-campaigns", methods=["POST"])
@login_required_api
def pi_dv360_campaigns_create():
    """Cria mapeamento campanha_id (PI) + campaigns_id (DV360)."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    raw_camp = payload.get("campanha_id")
    campaigns_id = payload.get("campaigns_id")
    try:
        campanha_id = int(raw_camp)
    except (TypeError, ValueError):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "campanha_id inválido ou em falta",
                    "http_code": 400,
                }
            ),
            400,
        )

    camp = db.obter_campanha_pi_por_id(campanha_id)
    if not camp or camp.get("id_cliente") is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Campanha PI não encontrada",
                    "http_code": 404,
                }
            ),
            404,
        )

    if not _pode_aceder_cliente(int(camp["id_cliente"])):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    try:
        new_id = db.criar_dv360_campaign(campanha_id, campaigns_id)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "http_code": 400}), 400
    except UniqueViolation:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Este campaigns_id já está em uso noutro mapeamento",
                    "http_code": 409,
                }
            ),
            409,
        )

    if new_id is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Este campaigns_id já está em uso noutro mapeamento",
                    "http_code": 409,
                }
            ),
            409,
        )

    row = db.obter_dv360_campaign_por_id(new_id)
    return jsonify({"success": True, "data": row}), 201


@bp.route("/pi-dv360-campaigns/<int:mapping_id>", methods=["PATCH"])
@login_required_api
def pi_dv360_campaigns_update(mapping_id: int):
    """Atualiza campanha_id e/ou campaigns_id."""
    row = db.obter_dv360_campaign_por_id(mapping_id)
    if not row:
        return jsonify({"success": False, "error": "Registo não encontrado", "http_code": 404}), 404

    old_camp = db.obter_campanha_pi_por_id(int(row["campanha_id"]))
    if not old_camp or old_camp.get("id_cliente") is None:
        return jsonify({"success": False, "error": "Campanha PI não encontrada", "http_code": 404}), 404
    if not _pode_aceder_cliente(int(old_camp["id_cliente"])):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    new_campanha_id = None
    if "campanha_id" in payload:
        try:
            new_campanha_id = int(payload.get("campanha_id"))
        except (TypeError, ValueError):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "campanha_id inválido",
                        "http_code": 400,
                    }
                ),
                400,
            )
        other = db.obter_campanha_pi_por_id(new_campanha_id)
        if not other or other.get("id_cliente") is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Campanha PI não encontrada",
                        "http_code": 404,
                    }
                ),
                404,
            )
        if not _pode_aceder_cliente(int(other["id_cliente"])):
            return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    campaigns_id = payload.get("campaigns_id") if "campaigns_id" in payload else None

    if new_campanha_id is None and campaigns_id is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Envie campanha_id e/ou campaigns_id",
                    "http_code": 400,
                }
            ),
            400,
        )

    try:
        ok = db.atualizar_dv360_campaign(
            mapping_id,
            campanha_id=new_campanha_id,
            campaigns_id=campaigns_id,
        )
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "http_code": 400}), 400
    except UniqueViolation:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Este campaigns_id já está em uso noutro mapeamento",
                    "http_code": 409,
                }
            ),
            409,
        )

    if not ok:
        return jsonify({"success": False, "error": "Registo não encontrado", "http_code": 404}), 404

    updated = db.obter_dv360_campaign_por_id(mapping_id)
    return jsonify({"success": True, "data": updated})


@bp.route("/pi-dv360-campaigns/<int:mapping_id>", methods=["DELETE"])
@login_required_api
def pi_dv360_campaigns_delete(mapping_id: int):
    """Remove um mapeamento PI ↔ DV360 por id."""
    row = db.obter_dv360_campaign_por_id(mapping_id)
    if not row:
        return jsonify({"success": False, "error": "Registo não encontrado", "http_code": 404}), 404

    camp = db.obter_campanha_pi_por_id(int(row["campanha_id"]))
    if not camp or camp.get("id_cliente") is None:
        return jsonify({"success": False, "error": "Campanha PI não encontrada", "http_code": 404}), 404
    if not _pode_aceder_cliente(int(camp["id_cliente"])):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    db.excluir_dv360_campaign(mapping_id)
    return jsonify({"success": True, "data": {"id": mapping_id}})


@bp.route("/campanhas-pi-com-id-api", methods=["GET"])
@login_required_api
def campanhas_pi_com_id_api():
    """Lista campanhas PI do cliente mapeado em dv360_advertisers para o advertiser DV360."""
    advertiser_id = (request.args.get("advertiser_id") or "").strip()
    if not advertiser_id:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "advertiser_id é obrigatório",
                    "http_code": 400,
                }
            ),
            400,
        )

    cliente_id = db.obter_cliente_id_por_dv_anunciante_id(advertiser_id)
    if cliente_id is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Nenhum mapeamento em dv360_advertisers para este anunciante. "
                        "Associe o cliente em dv360_advertisers primeiro."
                    ),
                    "http_code": 404,
                    "code": "NO_DV_MAPPING",
                }
            ),
            404,
        )

    if not _pode_aceder_cliente(cliente_id):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    rows = db.obter_campanhas_pi({"id_cliente": cliente_id}) or []
    cids = [int(r["id_campanha"]) for r in rows if r.get("id_campanha") is not None]
    grouped = db.listar_dv360_campaigns_agrupados_por_campanhas(cids)
    data = []
    for r in rows:
        ic = int(r["id_campanha"])
        dv = grouped.get(ic, [])
        data.append(
            {
                "id_campanha": ic,
                "nome_campanha": r.get("nome_campanha"),
                "mes_ref_comp": r.get("mes_ref_comp"),
                "codigo_pi": r.get("codigo_pi"),
                "dv360_campaigns": dv,
                "campaigns_id": dv[0]["campaigns_id"] if dv else None,
            }
        )
    return jsonify({"success": True, "data": data, "cliente_id": cliente_id})


@bp.route("/campanha-pi-id-api", methods=["POST", "PATCH"])
@login_required_api
def campanha_pi_id_api():
    """
    Grava o vínculo PI ↔ DV360 em dv360_campaigns.
    Remove mapeamentos anteriores desta campanha PI e, se campaigns_id não for vazio, insere uma linha.
    Aceita campaigns_id ou id_api (legado) no JSON.
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    raw_ic = payload.get("id_campanha")
    try:
        id_campanha = int(raw_ic)
    except (TypeError, ValueError):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "id_campanha inválido ou em falta",
                    "http_code": 400,
                }
            ),
            400,
        )

    camp = db.obter_campanha_pi_por_id(id_campanha)
    if not camp:
        return jsonify({"success": False, "error": "Campanha PI não encontrada.", "http_code": 404}), 404

    try:
        cid_cli = int(camp["id_cliente"])
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Campanha inválida.", "http_code": 400}), 400

    if not _pode_aceder_cliente(cid_cli):
        return jsonify({"success": False, "error": "Acesso negado", "http_code": 403}), 403

    raw_c = payload.get("campaigns_id")
    if raw_c is None and "id_api" in payload:
        raw_c = payload.get("id_api")
    if raw_c is not None and not isinstance(raw_c, str):
        raw_c = str(raw_c)

    db.excluir_dv360_campaigns_por_campanha(id_campanha)
    campaigns_norm = (raw_c or "").strip() if raw_c is not None else ""

    if campaigns_norm:
        try:
            new_id = db.criar_dv360_campaign(id_campanha, campaigns_norm)
        except ValueError as e:
            return jsonify({"success": False, "error": str(e), "http_code": 400}), 400
        except UniqueViolation:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Este campaigns_id já está em uso noutro mapeamento",
                        "http_code": 409,
                    }
                ),
                409,
            )
        if new_id is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Este campaigns_id já está em uso noutro mapeamento",
                        "http_code": 409,
                    }
                ),
                409,
            )

    mappings_raw = db.listar_dv360_campaigns_por_campanha(id_campanha)
    dv360_campaigns = [
        {"id": m["id"], "campaigns_id": m["campaigns_id"]} for m in (mappings_raw or [])
    ]
    first_c = dv360_campaigns[0]["campaigns_id"] if dv360_campaigns else None
    return jsonify(
        {
            "success": True,
            "data": {
                "id_campanha": id_campanha,
                "campaigns_id": first_c,
                "dv360_campaigns": dv360_campaigns,
            },
        }
    )


def _serialize_campanha_acompanhamento_dv360_row(
    c: dict[str, Any],
    agora: datetime,
    dv360_mappings: Optional[List[Dict[str, Any]]] = None,
) -> dict[str, Any]:
    er = anexar_preco_metrica_campanha(c)
    obj_val = parse_volume_float(er.get("obj_contratados"))
    ating_val = parse_volume_float(er.get("totalizador_atingido"))
    pct_obj = int(round((ating_val / obj_val) * 100)) if obj_val > 0 else 0
    prev_val = parse_brl_float(er.get("valor_plataforma")) or 0.0
    gasto_val = parse_brl_float(er.get("totalizador_gasto")) or 0.0
    pct_inv = int(round((gasto_val / prev_val) * 100)) if prev_val > 0 else 0
    diff_gasto = gasto_val - prev_val
    link_count = (1 if er.get("googled_pi_princ") else 0) + (1 if er.get("link_dash") else 0)

    dias_restantes = None
    pf = er.get("periodo_fim")
    if pf is not None:
        try:
            dend = pf.date() if hasattr(pf, "date") else pf
            dias_restantes = (dend - agora.date()).days
        except (TypeError, ValueError):
            dias_restantes = None

    restante_obj = obj_val - ating_val
    maps = dv360_mappings or []
    dv360_out: List[Dict[str, Any]] = []
    for m in maps:
        cid = m.get("campaigns_id")
        if cid is None or str(cid).strip() == "":
            continue
        dv360_out.append(
            {"id": m.get("id"), "campaigns_id": str(cid).strip()}
        )
    campaigns_id_first = dv360_out[0]["campaigns_id"] if dv360_out else None
    campaigns_ids_search = " ".join(x["campaigns_id"] for x in dv360_out)
    first_map = maps[0] if maps else {}

    def _iso_date(x: Any) -> Optional[str]:
        if x is None:
            return None
        if hasattr(x, "strftime"):
            try:
                return x.strftime("%Y-%m-%d")
            except Exception:
                return None
        return str(x)

    sigla = sigla_metrica_preco(er.get("objetivo_nome"), er.get("preco_metrica_modalidade"))

    return {
        "id_campanha": er.get("id_campanha"),
        "codigo_pi": er.get("codigo_pi"),
        "nome_campanha": er.get("nome_campanha"),
        "cliente_nome": er.get("cliente_nome"),
        "executivo_nome": er.get("executivo_nome"),
        "mes_ref_comp": er.get("mes_ref_comp"),
        "periodo_inicio": _iso_date(er.get("periodo_inicio")),
        "periodo_fim": _iso_date(er.get("periodo_fim")),
        "dias_restantes": dias_restantes,
        "objetivo_nome": er.get("objetivo_nome"),
        "status_nome": er.get("status_nome"),
        "plataforma_nome": er.get("plataforma_nome"),
        "preco_metrica_brl": er.get("preco_metrica_brl"),
        "preco_metrica_sigla": sigla,
        "obj_val": obj_val,
        "ating_val": ating_val,
        "pct_obj": pct_obj,
        "restante_obj": restante_obj,
        "link_count": link_count,
        "gasto_val": gasto_val,
        "prev_val": prev_val,
        "pct_inv": pct_inv,
        "diff_gasto": diff_gasto,
        "dv360_campaigns": dv360_out,
        "campaigns_id": campaigns_id_first,
        "campaigns_ids_search": campaigns_ids_search,
        "report_periodo_inicio": _iso_date(first_map.get("report_start_date")),
        "report_periodo_fim": _iso_date(first_map.get("report_end_date")),
    }


@bp.route("/campanhas-pi-acompanhamento-dv360", methods=["GET"])
@login_required_api
def campanhas_pi_acompanhamento_dv360():
    """Listagem tipo Acompanhamento: só campanhas PI com plataforma DV360 + mapeamentos dv360_campaigns."""
    plat_id = db.obter_id_plataforma_dv360()
    warn = None
    if plat_id is None:
        warn = (
            "Nenhuma plataforma DV360 encontrada. Defina PI_PLATAFORMA_DV360_ID no .env ou "
            "cadastre uma plataforma com «DV360» na descrição."
        )

    mes_ref_comp = (request.args.get("mes_ref_comp") or "").strip()
    if not mes_ref_comp:
        now = datetime.now()
        mes_ref_comp = f"{now.month}/{now.strftime('%y')}"

    filtros: dict[str, Any] = {"mes_ref_comp": mes_ref_comp}
    if plat_id is not None:
        filtros["id_plataforma"] = plat_id

    id_status = request.args.get("id_status", type=int)
    if id_status is not None:
        filtros["id_status"] = id_status
    resp = request.args.get("resp_comercial", type=int)
    if resp is not None:
        filtros["resp_comercial"] = resp

    if _is_dv_session_admin():
        qcliente = request.args.get("id_cliente", type=int)
        if qcliente is not None:
            filtros["id_cliente"] = qcliente
    else:
        sid = _session_cliente_id()
        if sid is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Cliente não identificado na sessão.",
                        "http_code": 403,
                    }
                ),
                403,
            )
        filtros["id_cliente"] = sid

    if plat_id is None:
        return jsonify(
            {
                "success": True,
                "data": [],
                "warn": warn,
                "filtros_aplicados": filtros,
            }
        )

    rows_raw = db.obter_campanhas_pi(filtros) or []
    cids = [int(r["id_campanha"]) for r in rows_raw if r.get("id_campanha") is not None]
    grouped = db.listar_dv360_campaigns_agrupados_por_campanhas(cids)
    agora = datetime.now()
    data = [
        _serialize_campanha_acompanhamento_dv360_row(
            dict(r), agora, grouped.get(int(r["id_campanha"]), [])
        )
        for r in rows_raw
    ]
    out: dict[str, Any] = {
        "success": True,
        "data": data,
        "filtros_aplicados": filtros,
        "id_plataforma_dv360": plat_id,
    }
    if warn:
        out["warn"] = warn
    return jsonify(out)


@parametros_bp.route("/testesDV", methods=["GET"])
@login_required
def testes_dv():
    """Listar e pausar campanhas DV360 (chama APIs JSON com a sessão do browser)."""
    now = datetime.now()
    default_mes = f"{now.month}/{now.strftime('%y')}"
    vendedores = db.obter_vendedores_centralcomm()
    statuses = db.obter_status_campanha()
    try:
        meses_ref = db.obter_meses_ref_campanha_pi()
    except Exception as ex_m:
        current_app.logger.warning("obter_meses_ref_campanha_pi (testesDV): %s", ex_m)
        meses_ref = []
    meses_ref = meses_ref_pi_seguros(meses_ref, default_mes)
    if not meses_ref:
        meses_ref = [default_mes]
    return render_template(
        "parametros_testes_dv.html",
        statuses=statuses or [],
        vendedores=vendedores or [],
        meses_ref=meses_ref,
        filtros_acompanhamento_dv360={"mes_ref_comp": default_mes},
        url_campanhas_pi_lista=url_for("campanhas_pi_lista"),
        is_dv_acompanhamento_admin=_is_dv_session_admin(),
        clientes_simples=(
            db.obter_clientes_simples() if _is_dv_session_admin() else []
        ),
    )


def _lista_old_kpi_filtros_from_request():
    mes_ref_comp = (request.args.get('mes_ref_comp') or '').strip()
    filtros = {}
    if mes_ref_comp:
        filtros['mes_ref_comp'] = mes_ref_comp
    return filtros


def _lista_old_kpi_carregar(filtros):
    campanhas_raw = db.obter_campanhas_pi_lista_old_kpi(filtros or None)
    campanhas = [anexar_preco_metrica_campanha(c) for c in (campanhas_raw or [])]

    total_meta = 0.0
    total_atingido = 0.0
    total_volume_kpi = 0.0
    total_investimento_kpi = 0.0
    for row in campanhas:
        total_meta += parse_volume_float(row.get('obj_contratados'))
        total_atingido += parse_volume_float(row.get('totalizador_atingido'))
        vol_kpi = row.get('volume_kpi')
        if vol_kpi is not None and float(vol_kpi) > 0:
            total_volume_kpi += float(vol_kpi)
        inv_kpi = row.get('investimento_kpi_brl')
        if inv_kpi is not None and float(inv_kpi) > 0:
            total_investimento_kpi += float(inv_kpi)

    footer_totais = {
        'total_campanhas': len(campanhas),
        'total_meta': total_meta,
        'total_atingido': total_atingido,
        'total_volume_kpi': total_volume_kpi,
        'total_investimento_kpi': total_investimento_kpi,
    }
    return campanhas, footer_totais


def _lista_old_kpi_fmt_num_br(value, decimals=2):
    if value is None:
        return ''
    try:
        n = float(value)
    except (TypeError, ValueError):
        return ''
    if decimals == 0:
        s = f'{n:,.0f}'
    else:
        s = f'{n:,.{decimals}f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def _lista_old_kpi_fmt_periodo(c):
    return (c.get('mes_ref_comp') or '').strip()


def _lista_old_kpi_fmt_valor_kpi(c):
    preco = c.get('preco_metrica_brl')
    if preco is None:
        return ''
    return f'R$ {_lista_old_kpi_fmt_num_br(preco)}'


def _lista_old_kpi_xlsx_cell(value):
    if value is None:
        return ''
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _lista_old_kpi_xlsx_response(header, rows, filename):
    """Gera .xlsx nativo — colunas corretas e acentos preservados no Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'OLD KPI'
    ws.append([_lista_old_kpi_xlsx_cell(c) for c in header])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append([_lista_old_kpi_xlsx_cell(c) for c in row])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


_LISTA_OLD_KPI_HEADER = [
    'PI',
    'Período',
    'Campanha',
    'Cliente',
    'Agência',
    'Praça',
    'Formato',
    'KPI',
    'Volume - Meta',
    'Volume - Atingido',
    'Volume usado (KPI)',
    'Investimento mídia (KPI)',
    'ValorKPI',
    'Status PI',
]


def _lista_old_kpi_export_rows(campanhas, footer_totais):
    rows = []
    for c in campanhas:
        meta_val = parse_volume_float(c.get('obj_contratados'))
        ating_val = parse_volume_float(c.get('totalizador_atingido'))
        vol_kpi = c.get('volume_kpi')
        vol_kpi_f = float(vol_kpi) if vol_kpi is not None else 0.0
        inv_kpi = c.get('investimento_kpi_brl')
        rows.append([
            c.get('codigo_pi') or '',
            _lista_old_kpi_fmt_periodo(c),
            c.get('nome_campanha') or '',
            c.get('cliente_nome') or '',
            c.get('agencia_nome') or '',
            c.get('praca') or '',
            c.get('formato') or '',
            c.get('kpi_nome') or '',
            _lista_old_kpi_fmt_num_br(meta_val, 0) if meta_val > 0 else '',
            _lista_old_kpi_fmt_num_br(ating_val, 0) if ating_val > 0 else '',
            _lista_old_kpi_fmt_num_br(vol_kpi_f, 0) if vol_kpi_f > 0 else '',
            _lista_old_kpi_fmt_num_br(inv_kpi) if inv_kpi is not None else '',
            _lista_old_kpi_fmt_valor_kpi(c),
            c.get('sub_status_pi_nome') or c.get('status_pi_nome') or '',
        ])
    rows.append([
        'TOTAL',
        '',
        f"{footer_totais['total_campanhas']} campanha(s)",
        '', '', '', '', '',
        _lista_old_kpi_fmt_num_br(footer_totais['total_meta'], 0) if footer_totais['total_meta'] > 0 else '',
        _lista_old_kpi_fmt_num_br(footer_totais['total_atingido'], 0) if footer_totais['total_atingido'] > 0 else '',
        _lista_old_kpi_fmt_num_br(footer_totais['total_volume_kpi'], 0) if footer_totais['total_volume_kpi'] > 0 else '',
        _lista_old_kpi_fmt_num_br(footer_totais['total_investimento_kpi']) if footer_totais['total_investimento_kpi'] else '',
        '',
        '',
    ])
    return _LISTA_OLD_KPI_HEADER, rows


@parametros_bp.route("/listaOLDKPI", methods=["GET"])
@login_required
def lista_old_kpi():
    """Lista legada de campanhas PI ordenada por PI (formato, praça, KPI, meta, objetivo)."""
    try:
        filtros = _lista_old_kpi_filtros_from_request()
        campanhas, footer_totais = _lista_old_kpi_carregar(filtros)

        try:
            meses_ref = db.obter_meses_ref_campanha_pi()
        except Exception as ex_m:
            current_app.logger.warning("obter_meses_ref_campanha_pi (listaOLDKPI): %s", ex_m)
            meses_ref = []

        return render_template(
            "parametros_lista_old_kpi.html",
            campanhas=campanhas,
            filtros=filtros,
            meses_ref=meses_ref or [],
            footer_totais=footer_totais,
        )
    except Exception as e:
        current_app.logger.error("Erro listaOLDKPI: %s", e, exc_info=True)
        flash('Erro ao carregar lista de campanhas. Tente novamente.', 'error')
        return redirect(url_for('parametros.lista_old_kpi'))


@parametros_bp.route("/listaOLDKPI/export", methods=["GET"])
@login_required
def lista_old_kpi_export():
    """Exporta a lista OLD KPI em Excel (.xlsx)."""
    try:
        filtros = _lista_old_kpi_filtros_from_request()
        campanhas, footer_totais = _lista_old_kpi_carregar(filtros)
        header, rows = _lista_old_kpi_export_rows(campanhas, footer_totais)

        mes_suffix = filtros.get('mes_ref_comp', 'todos').replace('/', '-')
        filename = f"lista_OLD_KPI_{mes_suffix}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        return _lista_old_kpi_xlsx_response(header, rows, filename)
    except Exception as e:
        current_app.logger.error("Erro export listaOLDKPI: %s", e, exc_info=True)
        flash('Erro ao exportar lista de campanhas.', 'error')
        return redirect(url_for('parametros.lista_old_kpi'))


@parametros_bp.route("/testesDV/legado", methods=["GET"])
@login_required
def testes_dv_legado():
    """Cópia preservada da UI Testes DV360; mesma lógica que testes_dv, template legado."""
    now = datetime.now()
    default_mes = f"{now.month}/{now.strftime('%y')}"
    vendedores = db.obter_vendedores_centralcomm()
    statuses = db.obter_status_campanha()
    try:
        meses_ref = db.obter_meses_ref_campanha_pi()
    except Exception as ex_m:
        current_app.logger.warning("obter_meses_ref_campanha_pi (testesDV/legado): %s", ex_m)
        meses_ref = []
    meses_ref = meses_ref_pi_seguros(meses_ref, default_mes)
    if not meses_ref:
        meses_ref = [default_mes]
    return render_template(
        "parametros_testes_dv_legado.html",
        statuses=statuses or [],
        vendedores=vendedores or [],
        meses_ref=meses_ref,
        filtros_acompanhamento_dv360={"mes_ref_comp": default_mes},
        url_campanhas_pi_lista=url_for("campanhas_pi_lista"),
        is_dv_acompanhamento_admin=_is_dv_session_admin(),
        clientes_simples=(
            db.obter_clientes_simples() if _is_dv_session_admin() else []
        ),
    )
