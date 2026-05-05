"""
Relatórios de desempenho DV360 via Bid Manager API v2 (alinhamento à UI).

Requer OAuth com scope doubleclickbidmanager (incluído em DV360_SCOPES em dv360_client).
Fluxo: criar Query ONE_TIME → run → poll reports.get → download CSV (URL em googleCloudStoragePath).

Referência: https://developers.google.com/bid-manager/guides/build-reports/create-query
"""
from __future__ import annotations

import csv
import io
import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

import requests

from aicentralv2.services.dv360_client import DV360API

logger = logging.getLogger(__name__)

# Intervalo entre polls e limite (~5 min)
_POLL_SLEEP_SEC = 3.0
_POLL_MAX_ATTEMPTS = 100

# Métricas STANDARD típicas para «Spent» + CPM entregue (moeda do anunciante)
_DEFAULT_METRICS = (
    "METRIC_BILLABLE_COST_ADVERTISER",
    "METRIC_TOTAL_MEDIA_COST_ADVERTISER",
    "METRIC_REVENUE_ADVERTISER",
    "METRIC_MEDIA_COST_ADVERTISER",
    "METRIC_MEDIA_COST_ECPM_ADVERTISER",
    "METRIC_IMPRESSIONS",
    "METRIC_CLICKS",
)
# Se a combinação completa falhar (400), tenta o mínimo compatível com STANDARD + campanha.
_METRICS_MINIMAL = (
    "METRIC_BILLABLE_COST_ADVERTISER",
    "METRIC_MEDIA_COST_ECPM_ADVERTISER",
    "METRIC_IMPRESSIONS",
    "METRIC_CLICKS",
)
# Relatório diário (groupBy DATE + MEDIA_PLAN): custo, impressões, cliques, eCPM
_DAILY_METRICS = (
    "METRIC_BILLABLE_COST_ADVERTISER",
    "METRIC_MEDIA_COST_ECPM_ADVERTISER",
    "METRIC_IMPRESSIONS",
    "METRIC_CLICKS",
)
_METRICS_DAILY_FALLBACK = (
    "METRIC_BILLABLE_COST_ADVERTISER",
    "METRIC_IMPRESSIONS",
    "METRIC_CLICKS",
)


def _http_ok(code: int) -> bool:
    return code in (200, 201, 202)


def _date_to_bm(d: date) -> dict[str, int]:
    return {"year": d.year, "month": d.month, "day": d.day}


def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (h or "").lower()).strip()


def _find_col_idx(headers: list[str], *must_include: str) -> Optional[int]:
    for i, h in enumerate(headers):
        n = _norm_header(h)
        if all(part in n for part in must_include):
            return i
    return None


def _parse_number_cell(val: str) -> Optional[float]:
    """
    Números do CSV do Google (en-US) e separadores pt-BR (1.234,56 / 308,45).
    Não usar replace(',', '') cegamente — destrói decimais BR.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s or s in ("--", "—", "-", "N/A", "n/a", "#N/A"):
        return None
    s = s.replace("R$", "").replace("US$", "").replace("\u00a0", " ").replace(" ", "").strip()
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif s.count(",") == 1 and re.search(r",\d{1,4}$", s):
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _pick_cost_column(header: list[str]) -> Optional[int]:
    """Escolhe coluna de custo/gasto (EN + PT-BR Report Builder)."""
    candidates: list[tuple[int, int]] = []
    for i, h in enumerate(header):
        n = _norm_header(h)
        score = 0
        if "billable" in n and "cost" in n:
            score += 10
        if "fatur" in n and "custo" in n:
            score += 10
        if "total" in n and "media" in n and "cost" in n:
            score += 9
        if "revenue" in n and "advertiser" in n:
            score += 8
        if "receita" in n and ("anunciante" in n or "advertiser" in n):
            score += 8
        if "media" in n and "cost" in n and "advertiser" in n and "ecpm" not in n and "viewable" not in n:
            score += 7
        if "client" in n and "cost" in n:
            score += 6
        if score > 0:
            candidates.append((score, i))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][1]


def _pick_ecpm_column(header: list[str]) -> Optional[int]:
    for i, h in enumerate(header):
        n = _norm_header(h)
        if "ecpm" in n or ("cpm" in n and "cost" in n) or ("custo" in n and "ecpm" in n):
            return i
    return _find_col_idx(header, "media", "cost", "ecpm", "advertiser")


def _pick_impressions_column(header: list[str]) -> Optional[int]:
    for i, h in enumerate(header):
        n = _norm_header(h)
        if "impress" in n or "impresso" in n:
            return i
    return None


def _pick_clicks_column(header: list[str]) -> Optional[int]:
    for i, h in enumerate(header):
        n = _norm_header(h)
        if "click" in n and "through" not in n and "rate" not in n:
            return i
    return None


def _pick_date_column(header: list[str]) -> Optional[int]:
    """Coluna de data (dia) no CSV do Bid Manager."""
    candidates: list[tuple[int, int]] = []
    for i, h in enumerate(header):
        n = _norm_header(h)
        score = 0
        if n == "date" or n.endswith(" date"):
            score += 10
        if "data" in n and "range" not in n and "start" not in n:
            score += 8
        if "day" in n and "week" not in n:
            score += 7
        if "dia" in n:
            score += 7
        if score > 0:
            candidates.append((score, i))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][1]


def _parse_date_cell(val: str) -> Optional[date]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s in ("--", "—", "-", "N/A", "n/a"):
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
            return date(y, m, d)
        except (ValueError, TypeError):
            pass
    m = re.match(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$", s)
    if m:
        try:
            d0, m0, y0 = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(y0, m0, d0)
        except (ValueError, TypeError):
            pass
    try:
        dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        return dt.date()
    except ValueError:
        pass
    return None


def _find_header_row_index(rows: list[list[str]]) -> int:
    """Relatórios DV360 podem ter linhas de título antes do cabeçalho."""
    key_fragments = (
        "billable",
        "fatur",
        "revenue",
        "receita",
        "campaign",
        "campanha",
        "media plan",
        "impression",
        "impresso",
        "cost",
        "custo",
    )
    best_i = 0
    best = 0
    for i, row in enumerate(rows[:30]):
        if not row:
            continue
        blob = " ".join(_norm_header(c) for c in row)
        hits = sum(1 for k in key_fragments if k in blob)
        if hits >= 2 and len([x for x in row if str(x).strip()]) >= 3:
            if hits > best:
                best = hits
                best_i = i
    return best_i


def parse_dv360_performance_csv(csv_bytes: bytes) -> dict[str, Any]:
    """
    Soma linhas de dados; custo: Billable / Total Media / Revenue / Media Cost (Advertiser).
    eCPM: coluna eCPM ou custo/impressões*1000.
    """
    out: dict[str, Any] = {
        "spent": None,
        "kpi_atual": None,
        "impressions": None,
        "clicks": None,
        "rows_used": 0,
        "columns_matched": {},
        "parse_hint": None,
    }
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 2:
        out["parse_hint"] = "CSV vazio ou só uma linha."
        return out

    hdr_idx = _find_header_row_index(rows)
    header = [str(c or "").strip() for c in rows[hdr_idx]]
    body_rows = rows[hdr_idx + 1 :]
    out["columns_matched"]["header_row_index"] = hdr_idx
    out["columns_matched"]["raw_header"] = header[:40]

    idx_cost = _pick_cost_column(header)
    if idx_cost is None:
        idx_cost = _find_col_idx(header, "billable", "cost")
    idx_ecpm = _pick_ecpm_column(header)
    idx_imp = _pick_impressions_column(header)
    idx_clk = _pick_clicks_column(header)

    out["columns_matched"]["spent_column_index"] = idx_cost
    out["columns_matched"]["ecpm_column_index"] = idx_ecpm
    out["columns_matched"]["impressions_column_index"] = idx_imp
    out["columns_matched"]["clicks_column_index"] = idx_clk

    total_cost = 0.0
    total_imp = 0.0
    total_clk = 0.0
    cost_any = False
    imp_any = False
    clk_any = False
    ecpm_samples: list[float] = []

    for row in body_rows:
        if not row or all(not str(x).strip() for x in row):
            continue
        if idx_cost is not None and idx_cost < len(row):
            v = _parse_number_cell(row[idx_cost])
            if v is not None:
                total_cost += v
                cost_any = True
                out["rows_used"] += 1
        if idx_imp is not None and idx_imp < len(row):
            iv = _parse_number_cell(row[idx_imp])
            if iv is not None:
                total_imp += iv
                imp_any = True
        if idx_clk is not None and idx_clk < len(row):
            cv = _parse_number_cell(row[idx_clk])
            if cv is not None:
                total_clk += cv
                clk_any = True
        if idx_ecpm is not None and idx_ecpm < len(row):
            ev = _parse_number_cell(row[idx_ecpm])
            if ev is not None:
                ecpm_samples.append(ev)

    if cost_any:
        out["spent"] = round(total_cost, 4)
    if imp_any:
        out["impressions"] = round(total_imp, 4)
    if clk_any:
        out["clicks"] = round(total_clk, 4)

    if idx_ecpm is not None and ecpm_samples:
        out["kpi_atual"] = round(sum(ecpm_samples) / len(ecpm_samples), 4)
    elif cost_any and imp_any and total_imp > 0:
        out["kpi_atual"] = round((total_cost / total_imp) * 1000.0, 4)

    if out["spent"] is None and out["kpi_atual"] is None:
        out["parse_hint"] = (
            "Não foi encontrada coluna de custo reconhecida no CSV; "
            "verifique cabeçalhos (Google pode usar nomes EN/PT)."
        )
    return out


def parse_dv360_performance_csv_daily(csv_bytes: bytes) -> dict[str, Any]:
    """
    Agrega linhas do CSV por dia (coluna de data).
    Devolve lista com spent, impressions, clicks, cpm, cpc por metric_date.
    """
    out: dict[str, Any] = {
        "daily": [],
        "rows_used": 0,
        "columns_matched": {},
        "parse_hint": None,
    }
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 2:
        out["parse_hint"] = "CSV vazio ou só uma linha."
        return out

    hdr_idx = _find_header_row_index(rows)
    header = [str(c or "").strip() for c in rows[hdr_idx]]
    body_rows = rows[hdr_idx + 1 :]
    out["columns_matched"]["header_row_index"] = hdr_idx
    out["columns_matched"]["raw_header"] = header[:40]

    idx_date = _pick_date_column(header)
    idx_cost = _pick_cost_column(header)
    if idx_cost is None:
        idx_cost = _find_col_idx(header, "billable", "cost")
    idx_ecpm = _pick_ecpm_column(header)
    idx_imp = _pick_impressions_column(header)
    idx_clk = _pick_clicks_column(header)

    out["columns_matched"]["date_column_index"] = idx_date
    out["columns_matched"]["spent_column_index"] = idx_cost
    out["columns_matched"]["ecpm_column_index"] = idx_ecpm
    out["columns_matched"]["impressions_column_index"] = idx_imp
    out["columns_matched"]["clicks_column_index"] = idx_clk

    if idx_date is None:
        out["parse_hint"] = "Coluna de data não encontrada no CSV (relatório precisa de groupBy DATE)."
        return out

    agg: dict[date, dict[str, Any]] = {}

    for row in body_rows:
        if not row or all(not str(x).strip() for x in row):
            continue
        if idx_date >= len(row):
            continue
        d_raw = row[idx_date]
        dkey = _parse_date_cell(d_raw)
        if dkey is None:
            continue
        bucket = agg.setdefault(
            dkey,
            {
                "spent": 0.0,
                "impressions": 0.0,
                "clicks": 0.0,
                "ecpm_sum": 0.0,
                "ecpm_n": 0,
                "cost_any": False,
                "imp_any": False,
                "clk_any": False,
            },
        )
        if idx_cost is not None and idx_cost < len(row):
            v = _parse_number_cell(row[idx_cost])
            if v is not None:
                bucket["spent"] += v
                bucket["cost_any"] = True
                out["rows_used"] += 1
        if idx_imp is not None and idx_imp < len(row):
            iv = _parse_number_cell(row[idx_imp])
            if iv is not None:
                bucket["impressions"] += iv
                bucket["imp_any"] = True
        if idx_clk is not None and idx_clk < len(row):
            cv = _parse_number_cell(row[idx_clk])
            if cv is not None:
                bucket["clicks"] += cv
                bucket["clk_any"] = True
        if idx_ecpm is not None and idx_ecpm < len(row):
            ev = _parse_number_cell(row[idx_ecpm])
            if ev is not None:
                bucket["ecpm_sum"] += ev
                bucket["ecpm_n"] += 1

    daily_list: list[dict[str, Any]] = []
    for dkey in sorted(agg.keys()):
        b = agg[dkey]
        spent = round(b["spent"], 4) if b["cost_any"] else None
        impressions = round(b["impressions"], 4) if b["imp_any"] else None
        clicks = round(b["clicks"], 4) if b["clk_any"] else None
        cpm = None
        if b["ecpm_n"] > 0:
            cpm = round(b["ecpm_sum"] / b["ecpm_n"], 6)
        elif spent is not None and impressions is not None and impressions > 0:
            cpm = round((float(spent) / float(impressions)) * 1000.0, 6)
        cpc = None
        if spent is not None and clicks is not None and clicks > 0:
            cpc = round(float(spent) / float(clicks), 6)
        daily_list.append(
            {
                "metric_date": dkey.isoformat(),
                "spent": spent,
                "impressions": impressions,
                "cpm": cpm,
                "clicks": clicks,
                "cpc": cpc,
            }
        )

    out["daily"] = daily_list
    if not daily_list and out["rows_used"] == 0:
        out["parse_hint"] = (
            "Sem linhas de dados agregáveis por data; confirme groupBy FILTER_DATE no relatório."
        )
    return out


def fetch_campaign_performance_from_reporting(
    client: DV360API,
    advertiser_id: str,
    campaign_id: str,
    start: date,
    end: date,
    *,
    metrics: tuple[str, ...] = _DEFAULT_METRICS,
) -> dict[str, Any]:
    """
    Cria relatório STANDARD filtrado por anunciante + campanha (FILTER_MEDIA_PLAN),
    intervalo CUSTOM_DATES, faz download do CSV e extrai spent + eCPM.

    Em caso de falha devolve success=False e error legível (403 = scope / consentimento).
    """
    aid = str(advertiser_id).strip()
    cid = str(campaign_id).strip()
    if not aid or not cid:
        return {"success": False, "error": "advertiser_id e campaign_id são obrigatórios.", "http_code": 400}

    tok = client.get_access_token()
    if not tok:
        return {
            "success": False,
            "error": client.oauth_failure_message_for_user(),
            "http_code": 401,
            "oauth_error_detail": client.last_oauth_error,
        }

    title = f"aicentral-{cid}-{start.isoformat()}_{end.isoformat()}"[:240]

    group_bys_variants: tuple[list[str], ...] = (
        ["FILTER_MEDIA_PLAN"],
        ["FILTER_DATE", "FILTER_MEDIA_PLAN"],
    )
    metric_variants: tuple[tuple[str, ...], ...] = (metrics, _METRICS_MINIMAL)
    create: dict[str, Any] = {}
    last_create_err = ""
    broken = False
    for mset in metric_variants:
        for gbs in group_bys_variants:
            query_body: dict[str, Any] = {
                "metadata": {
                    "title": title,
                    "format": "CSV",
                    "dataRange": {
                        "range": "CUSTOM_DATES",
                        "customStartDate": _date_to_bm(start),
                        "customEndDate": _date_to_bm(end),
                    },
                },
                "params": {
                    "type": "STANDARD",
                    "filters": [
                        {"type": "FILTER_ADVERTISER", "value": aid},
                        {"type": "FILTER_MEDIA_PLAN", "value": cid},
                    ],
                    "groupBys": gbs,
                    "metrics": list(mset),
                },
                "schedule": {"frequency": "ONE_TIME"},
            }
            create = client._post_bm("queries", query_body)
            if _http_ok(int(create.get("http_code") or 0)) and isinstance(create.get("data"), dict):
                broken = True
                break
            last_create_err = _bm_error_message(create) or str(create.get("text", ""))[:300]
            logger.info(
                "DV360 reporting: create rejeitada metrics=%s groupBys=%s: %s",
                mset,
                gbs,
                last_create_err,
            )
        if broken:
            break

    ch = int(create.get("http_code") or 0)
    if create.get("request_error") or ch == 0:
        return {
            "success": False,
            "error": (
                f"Sem ligação ao Bid Manager ({create.get('request_error') or 'timeout/rede'}). "
                "Confirme OAuth e rede."
            ),
            "http_code": 503,
        }
    if not _http_ok(ch) or not isinstance(create.get("data"), dict):
        err = _bm_error_message(create) or last_create_err
        if ch == 403:
            err += (
                " Confirme o scope https://www.googleapis.com/auth/doubleclickbidmanager na app OAuth "
                "e regenere o refresh token com esse consentimento."
            )
        return {
            "success": False,
            "error": err or "Falha ao criar query na Bid Manager API.",
            "http_code": ch or 502,
            "bid_manager_details": create.get("data"),
        }

    qdata = create["data"]
    query_id = str(qdata.get("queryId") or "").strip()
    if not query_id:
        return {
            "success": False,
            "error": "Resposta da API sem queryId.",
            "http_code": 502,
            "bid_manager_details": qdata,
        }

    run_body = {
        "dataRange": {
            "range": "CUSTOM_DATES",
            "customStartDate": _date_to_bm(start),
            "customEndDate": _date_to_bm(end),
        }
    }
    run = client._post_bm(f"queries/{query_id}:run", run_body)
    rh = int(run.get("http_code") or 0)
    if not _http_ok(rh) or not isinstance(run.get("data"), dict):
        code = rh
        err = _bm_error_message(run)
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": err or "Falha ao executar query (run).",
            "http_code": code or 502,
            "query_id": query_id,
            "bid_manager_details": run.get("data"),
        }

    rdata = run["data"]
    key = rdata.get("key") if isinstance(rdata.get("key"), dict) else {}
    report_id = str(key.get("reportId") or "").strip()
    if not report_id:
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": "Resposta run sem reportId.",
            "http_code": 502,
            "query_id": query_id,
        }

    report = _poll_report_until_done(client, query_id, report_id)
    if not report.get("success"):
        client._delete_bm(f"queries/{query_id}")
        return report

    rep = report["report"]
    meta = rep.get("metadata") if isinstance(rep.get("metadata"), dict) else {}
    status = meta.get("status") if isinstance(meta.get("status"), dict) else {}
    state = str(status.get("state") or "")

    if state == "FAILED":
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": "Relatório DV360 terminou em FAILED.",
            "http_code": 502,
            "query_id": query_id,
            "report_id": report_id,
        }

    gcs_path = meta.get("googleCloudStoragePath")
    if not gcs_path:
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": "Relatório sem googleCloudStoragePath (estado inesperado).",
            "http_code": 502,
            "query_id": query_id,
            "report_id": report_id,
        }

    dl = _download_report_url(str(gcs_path), timeout=max(60, client.timeout * 3))
    if not dl.get("success"):
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": dl.get("error", "Download do CSV falhou."),
            "http_code": int(dl.get("http_code") or 502),
            "query_id": query_id,
        }

    parsed = parse_dv360_performance_csv(dl["content"])
    parsed.update(
        {
            "success": True,
            "query_id": query_id,
            "report_id": report_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "source": "bid_manager_api_v2",
        }
    )

    try:
        client._delete_bm(f"queries/{query_id}")
    except Exception:
        logger.warning("DV360 reporting: não foi possível apagar query %s", query_id)

    return parsed


def fetch_campaign_daily_performance_from_reporting(
    client: DV360API,
    advertiser_id: str,
    campaign_id: str,
    start: date,
    end: date,
) -> dict[str, Any]:
    """
    Relatório STANDARD com groupBy FILTER_DATE + FILTER_MEDIA_PLAN — série diária no CSV.
    """
    aid = str(advertiser_id).strip()
    cid = str(campaign_id).strip()
    if not aid or not cid:
        return {"success": False, "error": "advertiser_id e campaign_id são obrigatórios.", "http_code": 400}

    tok = client.get_access_token()
    if not tok:
        return {
            "success": False,
            "error": client.oauth_failure_message_for_user(),
            "http_code": 401,
            "oauth_error_detail": client.last_oauth_error,
        }

    title = f"aicentral-daily-{cid}-{start.isoformat()}_{end.isoformat()}"[:240]
    group_bys_variants: tuple[list[str], ...] = (["FILTER_DATE", "FILTER_MEDIA_PLAN"],)
    metric_variants: tuple[tuple[str, ...], ...] = (
        _DAILY_METRICS,
        _METRICS_DAILY_FALLBACK,
        _METRICS_MINIMAL,
    )
    create: dict[str, Any] = {}
    last_create_err = ""
    broken = False
    for mset in metric_variants:
        for gbs in group_bys_variants:
            query_body: dict[str, Any] = {
                "metadata": {
                    "title": title,
                    "format": "CSV",
                    "dataRange": {
                        "range": "CUSTOM_DATES",
                        "customStartDate": _date_to_bm(start),
                        "customEndDate": _date_to_bm(end),
                    },
                },
                "params": {
                    "type": "STANDARD",
                    "filters": [
                        {"type": "FILTER_ADVERTISER", "value": aid},
                        {"type": "FILTER_MEDIA_PLAN", "value": cid},
                    ],
                    "groupBys": gbs,
                    "metrics": list(mset),
                },
                "schedule": {"frequency": "ONE_TIME"},
            }
            create = client._post_bm("queries", query_body)
            if _http_ok(int(create.get("http_code") or 0)) and isinstance(create.get("data"), dict):
                broken = True
                break
            last_create_err = _bm_error_message(create) or str(create.get("text", ""))[:300]
            logger.info(
                "DV360 reporting daily: create rejeitada metrics=%s groupBys=%s: %s",
                mset,
                gbs,
                last_create_err,
            )
        if broken:
            break

    ch = int(create.get("http_code") or 0)
    if create.get("request_error") or ch == 0:
        return {
            "success": False,
            "error": (
                f"Sem ligação ao Bid Manager ({create.get('request_error') or 'timeout/rede'}). "
                "Confirme OAuth e rede."
            ),
            "http_code": 503,
        }
    if not _http_ok(ch) or not isinstance(create.get("data"), dict):
        err = _bm_error_message(create) or last_create_err
        if ch == 403:
            err += (
                " Confirme o scope https://www.googleapis.com/auth/doubleclickbidmanager na app OAuth "
                "e regenere o refresh token com esse consentimento."
            )
        return {
            "success": False,
            "error": err or "Falha ao criar query na Bid Manager API.",
            "http_code": ch or 502,
            "bid_manager_details": create.get("data"),
        }

    qdata = create["data"]
    query_id = str(qdata.get("queryId") or "").strip()
    if not query_id:
        return {
            "success": False,
            "error": "Resposta da API sem queryId.",
            "http_code": 502,
            "bid_manager_details": qdata,
        }

    run_body = {
        "dataRange": {
            "range": "CUSTOM_DATES",
            "customStartDate": _date_to_bm(start),
            "customEndDate": _date_to_bm(end),
        }
    }
    run = client._post_bm(f"queries/{query_id}:run", run_body)
    rh = int(run.get("http_code") or 0)
    if not _http_ok(rh) or not isinstance(run.get("data"), dict):
        code = rh
        err = _bm_error_message(run)
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": err or "Falha ao executar query (run).",
            "http_code": code or 502,
            "query_id": query_id,
            "bid_manager_details": run.get("data"),
        }

    rdata = run["data"]
    key = rdata.get("key") if isinstance(rdata.get("key"), dict) else {}
    report_id = str(key.get("reportId") or "").strip()
    if not report_id:
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": "Resposta run sem reportId.",
            "http_code": 502,
            "query_id": query_id,
        }

    report = _poll_report_until_done(client, query_id, report_id)
    if not report.get("success"):
        client._delete_bm(f"queries/{query_id}")
        return report

    rep = report["report"]
    meta = rep.get("metadata") if isinstance(rep.get("metadata"), dict) else {}
    status = meta.get("status") if isinstance(meta.get("status"), dict) else {}
    state = str(status.get("state") or "")

    if state == "FAILED":
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": "Relatório DV360 terminou em FAILED.",
            "http_code": 502,
            "query_id": query_id,
            "report_id": report_id,
        }

    gcs_path = meta.get("googleCloudStoragePath")
    if not gcs_path:
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": "Relatório sem googleCloudStoragePath (estado inesperado).",
            "http_code": 502,
            "query_id": query_id,
            "report_id": report_id,
        }

    dl = _download_report_url(str(gcs_path), timeout=max(60, client.timeout * 3))
    if not dl.get("success"):
        client._delete_bm(f"queries/{query_id}")
        return {
            "success": False,
            "error": dl.get("error", "Download do CSV falhou."),
            "http_code": int(dl.get("http_code") or 502),
            "query_id": query_id,
        }

    parsed = parse_dv360_performance_csv_daily(dl["content"])
    parsed.update(
        {
            "success": True,
            "query_id": query_id,
            "report_id": report_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "source": "bid_manager_api_v2_daily",
        }
    )

    try:
        client._delete_bm(f"queries/{query_id}")
    except Exception:
        logger.warning("DV360 reporting daily: não foi possível apagar query %s", query_id)

    return parsed


def sync_campaign_daily_metrics_range(
    client: DV360API,
    advertiser_id: str,
    campaign_id: str,
    start: date,
    end: date,
) -> dict[str, Any]:
    """
    Tenta relatório único com data; se não houver linhas diárias, faz um pedido por dia (mais lento).
    """
    r = fetch_campaign_daily_performance_from_reporting(client, advertiser_id, campaign_id, start, end)
    daily = r.get("daily") if isinstance(r.get("daily"), list) else []
    if r.get("success") and daily:
        return r

    err_first = r.get("error")
    daily_out: list[dict[str, Any]] = []
    err_last: Optional[str] = None
    d = start
    while d <= end:
        one = fetch_campaign_performance_from_reporting(
            client, advertiser_id, campaign_id, d, d
        )
        if one.get("success"):
            spent = one.get("spent")
            imp = one.get("impressions")
            clk = one.get("clicks")
            kpi = one.get("kpi_atual")
            cpm = kpi
            if cpm is None and spent is not None and imp is not None and float(imp) > 0:
                cpm = round((float(spent) / float(imp)) * 1000.0, 6)
            cpc = None
            if spent is not None and clk is not None and float(clk) > 0:
                cpc = round(float(spent) / float(clk), 6)
            daily_out.append(
                {
                    "metric_date": d.isoformat(),
                    "spent": spent,
                    "impressions": imp,
                    "cpm": cpm,
                    "clicks": clk,
                    "cpc": cpc,
                }
            )
        else:
            err_last = one.get("error") or err_last
        d += timedelta(days=1)

    if daily_out:
        return {
            "success": True,
            "daily": daily_out,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "source": "bid_manager_api_v2_per_day_fallback",
            "fallback_note": err_first,
        }
    return {
        "success": False,
        "error": err_last or err_first or r.get("error") or "Sem dados diários.",
        "http_code": int(r.get("http_code") or 502),
        "daily": [],
    }


def _bm_error_message(res: dict[str, Any]) -> str:
    data = res.get("data")
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            if err.get("message"):
                return str(err["message"])
            st = err.get("status")
            if st:
                return f"{st}: {err.get('message') or ''}".strip()
    if res.get("text"):
        return str(res["text"])[:500]
    return ""


def _poll_report_until_done(
    client: DV360API, query_id: str, report_id: str
) -> dict[str, Any]:
    path = f"queries/{query_id}/reports/{report_id}"
    for attempt in range(_POLL_MAX_ATTEMPTS):
        gr = client._get_bm(path)
        code = int(gr.get("http_code") or 0)
        if code != 200 or not isinstance(gr.get("data"), dict):
            return {
                "success": False,
                "error": _bm_error_message(gr) or f"Erro HTTP {code} ao ler relatório.",
                "http_code": code or 502,
                "query_id": query_id,
            }
        rep = gr["data"]
        meta = rep.get("metadata") if isinstance(rep.get("metadata"), dict) else {}
        st = meta.get("status") if isinstance(meta.get("status"), dict) else {}
        state = str(st.get("state") or "")
        if state == "DONE":
            return {"success": True, "report": rep}
        if state == "FAILED":
            return {
                "success": False,
                "error": "Geração do relatório falhou (FAILED).",
                "http_code": 502,
                "query_id": query_id,
                "report": rep,
            }
        time.sleep(_POLL_SLEEP_SEC)

    return {
        "success": False,
        "error": "Timeout à espera do relatório Bid Manager.",
        "http_code": 504,
        "query_id": query_id,
    }


def _download_report_url(url: str, *, timeout: float) -> dict[str, Any]:
    """O URL devolvido pela API é normalmente HTTPS assinado (sem Bearer)."""
    try:
        r = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "http_code": 0}
    if r.status_code != 200:
        return {
            "success": False,
            "error": f"Download HTTP {r.status_code}",
            "http_code": r.status_code,
        }
    return {"success": True, "content": r.content}


def reporting_notes_success_pt(start: date, end: date) -> dict[str, str]:
    return {
        "spent": (
            f"Valor obtido via Bid Manager API (Billable / Total Media Cost), período "
            f"{start.isoformat()} a {end.isoformat()}, moeda do anunciante."
        ),
        "kpi_atual": (
            "eCPM de Media Cost (Advertiser Currency) ou derivado de custo/impressões no CSV."
        ),
    }
