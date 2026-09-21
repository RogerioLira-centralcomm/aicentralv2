#!/usr/bin/env python3
"""Migrate Testes DV360 templates from DaisyUI to cx-* and extract assets."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_MAIN = ROOT / "aicentralv2/templates/parametros_testes_dv.html"
TEMPLATE_LEGADO = ROOT / "aicentralv2/templates/parametros_testes_dv_legado.html"
CSS_OUT = ROOT / "aicentralv2/static/css/testes-dv360.css"
JS_OUT = ROOT / "aicentralv2/static/js/testes-dv360.js"
CONFIG_PARTIAL = ROOT / "aicentralv2/templates/partials/testes_dv360_config.html"

REPLACEMENTS = [
    ("btn btn-outline btn-sm btn-square", "cx-btn cx-btn-outline cx-btn-sm cx-btn-icon"),
    ("btn btn-sm gap-1 normal-case bg-primary text-primary-content hover:brightness-95 border-0 shadow-sm", "cx-btn cx-btn-primary cx-btn-sm gap-1 normal-case"),
    ("btn btn-sm normal-case bg-success text-success-content hover:brightness-95 border-0 shadow-sm", "cx-btn cx-btn-success cx-btn-sm normal-case"),
    ("btn btn-warning btn-xs h-7 min-h-0 px-2 py-0 text-[11px] font-medium leading-tight normal-case shrink-0", "cx-btn cx-btn-warning cx-btn-xs h-7 min-h-0 px-2 py-0 text-[11px] font-medium leading-tight normal-case shrink-0"),
    ("btn btn-success btn-xs h-7 min-h-0 px-2 py-0 text-[11px] font-medium leading-tight normal-case shrink-0", "cx-btn cx-btn-success cx-btn-xs h-7 min-h-0 px-2 py-0 text-[11px] font-medium leading-tight normal-case shrink-0"),
    ("btn btn-warning btn-sm", "cx-btn cx-btn-warning cx-btn-sm"),
    ("btn btn-success btn-sm", "cx-btn cx-btn-success cx-btn-sm"),
    ("btn btn-secondary btn-sm", "cx-btn cx-btn-secondary cx-btn-sm"),
    ("btn btn-primary btn-sm", "cx-btn cx-btn-primary cx-btn-sm"),
    ("btn btn-outline btn-sm", "cx-btn cx-btn-outline cx-btn-sm"),
    ("btn btn-sm btn-outline", "cx-btn cx-btn-sm cx-btn-outline"),
    ("btn btn-ghost btn-xs", "cx-btn cx-btn-ghost cx-btn-xs"),
    ("btn btn-ghost btn-sm", "cx-btn cx-btn-ghost cx-btn-sm"),
    ("tabs tabs-boxed tabs-sm shadow-sm flex-wrap gap-y-2", "cx-tabs flex-wrap gap-y-2 shadow-sm"),
    ("tab tab-active", "cx-tab cx-tab-active"),
    ("badge badge-primary badge-sm", "cx-badge cx-badge-primary cx-badge-sm"),
    ("badge badge-outline", "cx-badge cx-badge-muted"),
    ("badge badge-success badge-sm", "cx-badge cx-badge-success cx-badge-sm"),
    ("badge badge-error badge-sm", "cx-badge cx-badge-error cx-badge-sm"),
    ("badge badge-sm", "cx-badge cx-badge-sm"),
    ("badge-primary", "cx-badge-primary"),
    ("badge-ghost", "cx-badge-muted"),
    ("table table-xs table-zebra", "cx-table cx-table-dense text-xs"),
    ("table table-sm table-zebra", "cx-table cx-table-dense"),
    ("table table-sm", "cx-table cx-table-dense"),
    ("select select-bordered select-sm", "cx-select cx-select-sm"),
    ("input input-bordered input-sm", "cx-input cx-input-sm"),
    ("alert alert-warning", "cx-alert cx-alert-warning"),
    ("alert alert-error", "cx-alert cx-alert-error"),
    ("alert alert-success", "cx-alert cx-alert-success"),
    ("alert alert-info", "cx-alert cx-alert-info"),
    ("modal-backdrop", "cx-modal-dismiss"),
    ("modal-action", "cx-modal-actions"),
    ("modal-box max-w-md", "cx-modal-panel cx-modal-panel-md"),
    ("modal-box", "cx-modal-panel"),
    ('class="modal"', 'class="cx-modal-shell"'),
    ("form-control", "cx-field"),
    ("label-text-alt", "cx-help"),
    ("label-text text-sm font-medium", "cx-label text-xs font-medium"),
    ("label-text text-xs font-medium", "cx-label text-xs font-medium"),
    ("label-text", "cx-label text-xs"),
    ("label py-0 pb-1.5", "cx-label-row py-0 pb-1.5"),
    ("label py-0 pb-1", "cx-label-row py-0 pb-1"),
    ("label py-0", "cx-label-row py-0"),
    ("card-body gap-4 py-5", "p-5 space-y-4"),
    ("card-body gap-4", "p-5 space-y-4"),
    ("card-body gap-3", "p-5 space-y-3"),
    ("card-body", "p-5"),
    ("card bg-base-100 border border-base-200 shadow-lg overflow-hidden", "border border-slate-200 rounded-xl bg-white shadow-lg overflow-hidden"),
    ("card bg-base-100 border border-base-200 shadow-sm", "border border-slate-200 rounded-xl bg-white shadow-sm"),
    ("collapse collapse-arrow bg-base-100 border border-base-200 shadow-sm rounded-lg", "border border-slate-200 rounded-xl bg-white shadow-sm"),
    ("collapse-title text-sm font-medium py-3 min-h-0", "text-sm font-medium py-3 px-4 cursor-pointer list-none"),
    ("collapse-content", "px-4 pb-4"),
    ("link link-primary", "text-[var(--cx-primary)] hover:underline"),
    ("'tab-active'", "'cx-tab-active'"),
    ("'alert-error'", "'cx-alert-error'"),
    ("'alert-success'", "'cx-alert-success'"),
    ("'alert-info'", "'cx-alert-info'"),
    ("'alert-warning'", "'cx-alert-warning'"),
    ("'alert'", "'cx-alert'"),
    ("classList.add('alert',", "classList.add('cx-alert',"),
    ("classList.remove('hidden', 'alert-error', 'alert-success', 'alert-info')", "classList.remove('hidden', 'cx-alert-error', 'cx-alert-success', 'cx-alert-info')"),
    ("'badge badge-sm '", "'cx-badge cx-badge-sm '"),
    ("'table table-xs table-zebra w-full'", "'cx-table cx-table-dense text-xs w-full'"),
]

TAB_FIX = re.compile(r'class="tab(?!\s+cx-tab)(\s|")')
SCRIPTS_BLOCK = (
    "{% block scripts %}\n"
    '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n'
    "{% include 'partials/testes_dv360_config.html' %}\n"
    '<script src="{{ url_for(\'static\', filename=\'js/testes-dv360.js\') }}?v=1"></script>\n'
    "{% endblock %}"
)
STYLES_BLOCK = (
    "{% block styles %}\n"
    '<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'css/testes-dv360.css\') }}?v=1">\n'
    "{% endblock %}"
)


def migrate_text(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    text = TAB_FIX.sub('class="cx-tab\\1', text)
    text = text.replace("classList.toggle('tab-active'", "classList.toggle('cx-tab-active'")
    text = text.replace('role="tab"', 'role="tab" data-cx-tab')
    return text


def transform_template(path: Path, *, extract_js: bool = False) -> tuple[str, str, str]:
    raw = path.read_text(encoding="utf-8")
    css = ""
    js = ""

    m_style = re.search(r"{% block styles %}\s*<style>(.*?)</style>\s*{% endblock %}", raw, re.DOTALL)
    if m_style:
        css = m_style.group(1).strip()
        raw = raw[: m_style.start()] + STYLES_BLOCK + raw[m_style.end() :]

    m_script_main = re.search(
        r"<script src=\"https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js\"></script>\s*<script>(.*?)</script>\s*{% endblock %}",
        raw,
        re.DOTALL,
    )
    m_script_legado = re.search(
        r"</div>\s*<script>\s*(.*?)</script>\s*(?:{% endblock %})?\s*$",
        raw,
        re.DOTALL,
    )

    if extract_js and m_script_main:
        js = m_script_main.group(1).strip()
        raw = raw[: m_script_main.start()] + SCRIPTS_BLOCK
    elif m_script_main:
        raw = raw[: m_script_main.start()] + SCRIPTS_BLOCK
    elif m_script_legado:
        raw = raw[: m_script_legado.start()] + "</div>\n{% endblock %}\n\n" + SCRIPTS_BLOCK

    content = migrate_text(raw)
    content = content.replace(
        '<div class="border border-slate-200 rounded-xl bg-white shadow-lg overflow-hidden">',
        '<div class="border border-slate-200 rounded-xl bg-white shadow-lg overflow-hidden" data-cx-tab-scope>',
        1,
    )
    if "{% endblock %}" not in content.split("{% block content %}")[-1]:
        content = content.rstrip() + "\n{% endblock %}\n"
    return content, css, js


def build_js(js_body: str) -> str:
    js_body = migrate_text(js_body)
    js_body = re.sub(r"^\(function \(\) \{\s*", "", js_body)
    js_body = re.sub(r"\}\)\(\);\s*$", "", js_body).strip()

    subs = [
        (r"var URL_IO_FOR_CAMPAIGN_TMPL = .*?;", "var URL_IO_FOR_CAMPAIGN_TMPL = C.urlIoForCampaignTmpl;"),
        (r"var URL_IO_SYNC_TMPL = .*?;", "var URL_IO_SYNC_TMPL = C.urlIoSyncTmpl;"),
        (r"var URL_LI_FOR_CAMPAIGN_TMPL = .*?;", "var URL_LI_FOR_CAMPAIGN_TMPL = C.urlLiForCampaignTmpl;"),
        (r"var URL_METRICS_SYNC_TMPL = .*?;", "var URL_METRICS_SYNC_TMPL = C.urlMetricsSyncTmpl;"),
        (r"var URL_METRICS_SAVE_TMPL = .*?;", "var URL_METRICS_SAVE_TMPL = C.urlMetricsSaveTmpl;"),
        (r"var URL_PERIOD_SAVE_TMPL = .*?;", "var URL_PERIOD_SAVE_TMPL = C.urlPeriodSaveTmpl;"),
        (r"var URL_METRICS_HISTORY_SYNC_TMPL = .*?;", "var URL_METRICS_HISTORY_SYNC_TMPL = C.urlMetricsHistorySyncTmpl;"),
        (r"var URL_METRICS_HISTORY_GET_TMPL = .*?;", "var URL_METRICS_HISTORY_GET_TMPL = C.urlMetricsHistoryGetTmpl;"),
        (r"var URL_LI_SYNC_TMPL = .*?;", "var URL_LI_SYNC_TMPL = C.urlLiSyncTmpl;"),
        (r"var URL_AUDIT_VIEW = .*?;", "var URL_AUDIT_VIEW = C.urlAuditView;"),
        (r"var URL_PAUSE_TMPL = .*?;", "var URL_PAUSE_TMPL = C.urlPauseTmpl;"),
        (r"var URL_ACTIVATE_TMPL = .*?;", "var URL_ACTIVATE_TMPL = C.urlActivateTmpl;"),
        (r"var CLIENT_MAPPINGS_URL = .*?;", "var CLIENT_MAPPINGS_URL = C.clientMappingsUrl;"),
        (r"var URL_CLIENTES_MAPEAMENTO_DV = .*?;", "var URL_CLIENTES_MAPEAMENTO_DV = C.urlClientesMapeamentoDv;"),
        (r"var URL_CLIENT_MAPPINGS_POST = .*?;", "var URL_CLIENT_MAPPINGS_POST = C.urlClientMappingsPost;"),
        (r"var URL_CAMPANHA_PI_ID_API = .*?;", "var URL_CAMPANHA_PI_ID_API = C.urlCampanhaPiIdApi;"),
        (r"var URL_ACOMP_PI_DV360 = .*?;", "var URL_ACOMP_PI_DV360 = C.urlAcompPiDv360;"),
    ]
    for pattern, repl in subs:
        js_body = re.sub(pattern, repl, js_body, count=1)

    js_body = js_body.replace(
        'return "{{ url_for(\'dv360.campaigns\') }}?" + q.toString();',
        "return C.urlCampaigns + '?' + q.toString();",
    )
    js_body = js_body.replace(
        'var url = "{{ url_for(\'dv360.campaign_detail\', campaign_id=\'__CID__\') }}".replace',
        "var url = C.urlCampaignDetail.replace",
    )
    js_body = js_body.replace(
        'jsonFetch("{{ url_for(\'dv360.advertisers\') }}")',
        "jsonFetch(C.urlAdvertisers)",
    )

    return (
        "(function () {\n"
        "  'use strict';\n"
        "  var cfgEl = document.getElementById('dv360-test-config');\n"
        "  var C = cfgEl ? JSON.parse(cfgEl.textContent || '{}') : {};\n"
        + js_body
        + "\n})();\n"
    )


def write_config_partial() -> None:
    CONFIG_PARTIAL.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PARTIAL.write_text(
        """<script type="application/json" id="dv360-test-config">
{
  "urlIoForCampaignTmpl": {{ url_for('dv360.campaigns_insertion_orders_for_campaign', campaign_id='__CID__') | tojson }},
  "urlIoSyncTmpl": {{ url_for('dv360.campaigns_insertion_orders_sync', campaign_id='__CID__') | tojson }},
  "urlLiForCampaignTmpl": {{ url_for('dv360.campaigns_line_items_for_campaign', campaign_id='__CID__') | tojson }},
  "urlMetricsSyncTmpl": {{ url_for('dv360.campaign_metrics_sync', campaign_id='__CID__') | tojson }},
  "urlMetricsSaveTmpl": {{ url_for('dv360.campaign_metrics_save', campaign_id='__CID__') | tojson }},
  "urlPeriodSaveTmpl": {{ url_for('dv360.campaign_report_period_save', campaign_id='__CID__') | tojson }},
  "urlMetricsHistorySyncTmpl": {{ url_for('dv360.campaign_metrics_history_sync', campaign_id='__CID__') | tojson }},
  "urlMetricsHistoryGetTmpl": {{ url_for('dv360.campaign_metrics_history_get', campaign_id='__CID__') | tojson }},
  "urlLiSyncTmpl": {{ url_for('dv360.campaigns_line_items_sync', campaign_id='__CID__') | tojson }},
  "urlAuditView": {{ url_for('dv360.dv360_audit_view') | tojson }},
  "urlCampaigns": {{ url_for('dv360.campaigns') | tojson }},
  "urlPauseTmpl": {{ url_for('dv360.campaign_pause', campaign_id='__CID__') | tojson }},
  "urlActivateTmpl": {{ url_for('dv360.campaign_activate', campaign_id='__CID__') | tojson }},
  "clientMappingsUrl": {% if session.get('user_type') in ('admin', 'superadmin') %}{{ url_for('dv360.client_mappings_list', all=1) | tojson }}{% else %}{{ url_for('dv360.client_mappings_list') | tojson }}{% endif %},
  "urlClientesMapeamentoDv": {{ url_for('dv360.clientes_para_mapeamento_dv') | tojson }},
  "urlClientMappingsPost": {{ url_for('dv360.client_mappings_create') | tojson }},
  "urlCampanhaPiIdApi": {{ url_for('dv360.campanha_pi_id_api') | tojson }},
  "urlAcompPiDv360": {{ url_for('dv360.campanhas_pi_acompanhamento_dv360') | tojson }},
  "urlCampaignDetail": {{ url_for('dv360.campaign_detail', campaign_id='__CID__') | tojson }},
  "urlAdvertisers": {{ url_for('dv360.advertisers') | tojson }}
}
</script>
""",
        encoding="utf-8",
    )


def main() -> int:
    main_content, css, js = transform_template(TEMPLATE_MAIN, extract_js=True)
    TEMPLATE_MAIN.write_text(main_content, encoding="utf-8")

    legado_content, _, _ = transform_template(TEMPLATE_LEGADO)
    TEMPLATE_LEGADO.write_text(legado_content, encoding="utf-8")

    CSS_OUT.write_text("/* Testes DV360 — layout (Design System Enterprise) */\n" + css + "\n", encoding="utf-8")
    JS_OUT.write_text(build_js(js), encoding="utf-8")
    write_config_partial()

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
