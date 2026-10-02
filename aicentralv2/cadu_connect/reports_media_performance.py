"""Mídia → Desempenho: the Google Ads engine v2 detail (ad groups, keywords, search terms, devices, landing pages).

The engine already stores these tables daily; until now only the Página 360 read a slice of them. Amounts stay in
micros per account currency; when the selected accounts mix currencies the cost is returned as null.
"""
from datetime import date, timedelta

from flask import abort, jsonify, request

from ..auth import login_required_api
from .reports_v1 import _rows, _selection

TOP = 50
TABLES = ('cadu_reports_gads_ad_group_daily', 'cadu_reports_gads_keyword_daily', 'cadu_reports_gads_search_term_daily',
          'cadu_reports_gads_device_daily', 'cadu_reports_gads_landing_page_daily', 'cadu_reports_gads_campaign_settings')
SECTION_TABLE = {'ad_groups': TABLES[0], 'keywords': TABLES[1], 'search_terms': TABLES[2], 'devices': TABLES[3], 'landing_pages': TABLES[4]}
_SUMS = '''SUM(x.impressions)::bigint AS impressions,SUM(x.clicks)::bigint AS clicks,SUM(x.cost_micros)::bigint AS cost_micros,
    SUM(x.conversions)::numeric AS conversions,SUM(x.conversion_value_micros)::bigint AS conversion_value_micros'''
_WHERE = 'x.client_id=%(client)s AND x.metric_date>=%(start)s AND x.metric_date<=%(end)s'

_SQL = {
    'ad_groups': f'''SELECT x.campaign_name,x.ad_group_name,(ARRAY_AGG(x.ad_group_status ORDER BY x.metric_date DESC))[1] AS status,{_SUMS}
        FROM cadu_reports_gads_ad_group_daily x WHERE {_WHERE}
        GROUP BY x.account_id,x.ad_group_external_id,x.campaign_name,x.ad_group_name ORDER BY cost_micros DESC LIMIT {TOP}''',
    'keywords': f'''SELECT x.keyword_text,x.match_type,x.campaign_name,x.ad_group_name,
            (ARRAY_AGG(x.quality_score ORDER BY x.metric_date DESC) FILTER (WHERE x.quality_score IS NOT NULL))[1] AS quality_score,{_SUMS}
        FROM cadu_reports_gads_keyword_daily x WHERE {_WHERE}
        GROUP BY x.account_id,x.ad_group_external_id,x.criterion_external_id,x.keyword_text,x.match_type,x.campaign_name,x.ad_group_name
        ORDER BY cost_micros DESC LIMIT {TOP}''',
    'search_terms': f'''SELECT x.search_term,(ARRAY_AGG(x.term_status ORDER BY x.metric_date DESC))[1] AS status,{_SUMS}
        FROM cadu_reports_gads_search_term_daily x WHERE {_WHERE}
        GROUP BY x.term_hash,x.search_term ORDER BY cost_micros DESC LIMIT {TOP}''',
    'devices': f'''SELECT x.device,{_SUMS} FROM cadu_reports_gads_device_daily x WHERE {_WHERE}
        GROUP BY x.device ORDER BY cost_micros DESC''',
    'landing_pages': f'''SELECT x.page_host,x.page_path,COUNT(DISTINCT x.campaign_external_id)::int AS campaigns,{_SUMS}
        FROM cadu_reports_gads_landing_page_daily x WHERE {_WHERE}
        GROUP BY x.page_host,x.page_path ORDER BY cost_micros DESC LIMIT {TOP}''',
}
_SETTINGS_SQL = '''SELECT s.campaign_name,s.status,s.serving_status,s.channel_type,s.bidding_strategy_type,s.budget_micros,s.budget_shared,
        a.currency,s.updated_at
    FROM cadu_reports_gads_campaign_settings s JOIN cadu_reports_accounts a ON a.id=s.account_id
    WHERE s.client_id=%(client)s AND s.removed_at IS NULL ORDER BY s.budget_micros DESC NULLS LAST,s.campaign_name LIMIT 100'''
_CURRENCY_SQL = '''SELECT DISTINCT COALESCE(a.currency,'') AS currency FROM cadu_reports_accounts a
    WHERE a.client_id=%(client)s AND a.platform='google_ads' AND a.status<>'disabled' '''


def _period():
    try:
        end = date.fromisoformat(request.args.get('end_date') or date.today().isoformat())
        start = date.fromisoformat(request.args.get('start_date') or (end - timedelta(days=29)).isoformat())
    except ValueError:
        abort(400, description='Informe um intervalo de datas válido.')
    if start > end or (end - start).days > 365:
        abort(400, description='O período deve ter no máximo 366 dias.')
    return start, end


def register(bp):
    @bp.get('/api/v2/reports/media/performance')
    @login_required_api
    def reports_media_performance():
        """Google Ads detail for the period. Sections whose table is absent come back empty, never as an error."""
        selected = _selection()
        start, end = _period()
        exists = _rows('SELECT ' + ','.join(f"to_regclass('public.{name}') IS NOT NULL AS {name}" for name in TABLES))[0]
        scope = {'client': selected['client_id'], 'start': start, 'end': end}
        sections = {key: _rows(sql, scope) if exists[SECTION_TABLE[key]] else [] for key, sql in _SQL.items()}
        currencies = [row['currency'] for row in _rows(_CURRENCY_SQL, scope) if row['currency']]
        currency = currencies[0] if len(set(currencies)) == 1 else None
        if not currency:
            for rows in sections.values():
                for row in rows:
                    row['cost_micros'] = row['conversion_value_micros'] = None
        settings = _rows(_SETTINGS_SQL, scope) if exists['cadu_reports_gads_campaign_settings'] else []
        return jsonify(period={'start': start.isoformat(), 'end': end.isoformat()}, currency=currency,
                       has_data=any(sections.values()), settings=settings, **sections)
