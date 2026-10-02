"""Mídia → Google Ads: the engine v2 data read as a Google Ads report, with recommendations in execution order.

Reads only what the script already stores (cadu_reports_gads_*, campaign daily metrics and the run summaries).
Amounts come in micros and are returned in currency units; a client mixing currencies gets costs as null.
"""
from datetime import date, datetime, timedelta, timezone

from flask import abort, jsonify, request

from ..auth import login_required_api
from .reports_google_ads_rules import RULES, build_recommendations, keyword_conflicts, term_action
from .reports_v1 import _rows, _selection

SUMMARY_KIND = 'google_ads_engine_v2'
CHUNK_KIND = 'google_ads_engine_v2_chunk'
TERMS_LIMIT = 500
REMOVED_DAYS = 30
_M = '''SUM(x.impressions)::bigint AS impressions,SUM(x.clicks)::bigint AS clicks,SUM(x.cost_micros)::bigint AS cost_micros,
    SUM(x.conversions)::numeric AS conversions,SUM(x.conversion_value_micros)::bigint AS value_micros'''
_P = 'x.client_id=%(client)s AND x.metric_date BETWEEN %(start)s AND %(end)s'

_ACCOUNTS_SQL = '''SELECT a.id,a.name,a.external_id,a.currency,a.status,
        (SELECT r.created_at FROM cadu_reports_source_runs r WHERE r.client_id=a.client_id AND r.source_kind=%(summary)s
            AND regexp_replace(r.metadata->>'account_id','\\D','','g')=regexp_replace(a.external_id,'\\D','','g')
            ORDER BY r.created_at DESC LIMIT 1) AS last_run_at,
        (SELECT r.metadata FROM cadu_reports_source_runs r WHERE r.client_id=a.client_id AND r.source_kind=%(summary)s
            AND regexp_replace(r.metadata->>'account_id','\\D','','g')=regexp_replace(a.external_id,'\\D','','g')
            ORDER BY r.created_at DESC LIMIT 1) AS last_run,
        GREATEST((SELECT MAX(n.last_seen_at) FROM cadu_reports_gads_negative_keywords n WHERE n.account_id=a.id),
            (SELECT MAX(r.created_at) FROM cadu_reports_source_runs r WHERE r.client_id=a.client_id AND r.source_kind=%(chunk)s
                AND r.status='completed' AND r.metadata->>'dataset'='negative_keywords'
                AND regexp_replace(r.metadata->>'account_id','\\D','','g')=regexp_replace(a.external_id,'\\D','','g'))) AS negatives_at
    FROM cadu_reports_accounts a
    WHERE a.client_id=%(client)s AND a.platform='google_ads' AND a.account_kind='advertiser' AND a.status<>'disabled'
    ORDER BY a.name'''

_CAMPAIGNS_SQL = f'''SELECT x.account_id,x.campaign_external_id,
        (ARRAY_AGG(x.campaign_name ORDER BY x.metric_date DESC))[1] AS campaign_name,{_M},
        COUNT(DISTINCT x.metric_date) FILTER (WHERE x.cost_micros>0)::int AS active_days
    FROM cadu_reports_gads_ad_group_daily x WHERE {_P}
    GROUP BY x.account_id,x.campaign_external_id'''
_SETTINGS_SQL = '''SELECT account_id,campaign_external_id,campaign_name,status,serving_status,channel_type,
        bidding_strategy_type,budget_micros,budget_shared
    FROM cadu_reports_gads_campaign_settings WHERE client_id=%(client)s AND removed_at IS NULL'''
_TOTALS_SQL = f'''SELECT {_M} FROM cadu_reports_gads_ad_group_daily x WHERE {_P}'''
_DAILY_SQL = f'''SELECT x.metric_date AS date,{_M} FROM cadu_reports_gads_ad_group_daily x WHERE {_P}
    GROUP BY x.metric_date ORDER BY x.metric_date'''
_TERMS_SQL = f'''SELECT x.account_id,x.campaign_external_id,x.ad_group_external_id,x.term_hash,
        (ARRAY_AGG(x.search_term ORDER BY x.metric_date DESC))[1] AS search_term,
        (ARRAY_AGG(x.term_status ORDER BY x.metric_date DESC))[1] AS status,
        (ARRAY_AGG(x.campaign_name ORDER BY x.metric_date DESC))[1] AS campaign_name,
        (ARRAY_AGG(x.ad_group_name ORDER BY x.metric_date DESC))[1] AS ad_group_name,{_M}
    FROM cadu_reports_gads_search_term_daily x WHERE {_P}
    GROUP BY x.account_id,x.campaign_external_id,x.ad_group_external_id,x.term_hash
    ORDER BY cost_micros DESC LIMIT {TERMS_LIMIT}'''
_KEYWORDS_SQL = f'''SELECT x.account_id,x.campaign_external_id,x.ad_group_external_id,x.criterion_external_id,
        x.keyword_text,x.match_type,
        (ARRAY_AGG(x.keyword_status ORDER BY x.metric_date DESC))[1] AS status,
        (ARRAY_AGG(x.quality_score ORDER BY x.metric_date DESC) FILTER (WHERE x.quality_score IS NOT NULL))[1] AS quality_score,
        (ARRAY_AGG(x.campaign_name ORDER BY x.metric_date DESC))[1] AS campaign_name,
        (ARRAY_AGG(x.ad_group_name ORDER BY x.metric_date DESC))[1] AS ad_group_name,{_M}
    FROM cadu_reports_gads_keyword_daily x WHERE {_P}
    GROUP BY x.account_id,x.campaign_external_id,x.ad_group_external_id,x.criterion_external_id,x.keyword_text,x.match_type
    ORDER BY cost_micros DESC LIMIT {TERMS_LIMIT}'''
_DEVICES_SQL = f'''SELECT x.device,{_M} FROM cadu_reports_gads_device_daily x WHERE {_P} GROUP BY x.device ORDER BY cost_micros DESC'''
_NEGATIVES_SQL = '''SELECT n.id,n.account_id,n.level,n.campaign_external_id,n.campaign_name,n.ad_group_external_id,n.ad_group_name,
        n.shared_set_external_id,n.shared_set_name,n.attached_campaign_ids,n.keyword_text,n.match_type,
        n.first_seen_at,n.last_seen_at,n.removed_at
    FROM cadu_reports_gads_negative_keywords n
    WHERE n.client_id=%(client)s AND (n.removed_at IS NULL OR n.removed_at > NOW() - INTERVAL '30 days')
    ORDER BY n.removed_at NULLS FIRST,n.level,n.shared_set_name,n.campaign_name,n.keyword_text'''
_CURRENCY_SQL = '''SELECT DISTINCT COALESCE(currency,'') AS currency FROM cadu_reports_accounts
    WHERE client_id=%(client)s AND platform='google_ads' AND account_kind='advertiser' AND status<>'disabled' '''

_TABLES = ('cadu_reports_gads_ad_group_daily', 'cadu_reports_gads_search_term_daily', 'cadu_reports_gads_keyword_daily',
           'cadu_reports_gads_device_daily', 'cadu_reports_gads_negative_keywords', 'cadu_reports_gads_campaign_settings')


def _period():
    try:
        end = date.fromisoformat(request.args.get('end_date') or date.today().isoformat())
        start = date.fromisoformat(request.args.get('start_date') or (end - timedelta(days=29)).isoformat())
    except ValueError:
        abort(400, description='Informe um intervalo de datas válido.')
    if start > end or (end - start).days > 365:
        abort(400, description='O período deve ter no máximo 366 dias.')
    return start, end


def _ready():
    row = _rows('SELECT ' + ','.join(f"to_regclass('public.{name}') IS NOT NULL AS {name}" for name in _TABLES))[0]
    return all(row.values())


def _money(rows):
    """Micros → currency units, plus the ratios a Google Ads report reads first."""
    for row in rows:
        cost = row.pop('cost_micros', None)
        value = row.pop('value_micros', None)
        row['cost'] = None if cost is None else round(cost / 1e6, 2)
        row['conversion_value'] = None if value is None else round(value / 1e6, 2)
        clicks, impressions, conversions = int(row.get('clicks') or 0), int(row.get('impressions') or 0), float(row.get('conversions') or 0)
        row['conversions'] = round(conversions, 2)
        row['ctr'] = round(clicks * 100 / impressions, 2) if impressions else None
        row['cpc'] = round(row['cost'] / clicks, 2) if row['cost'] is not None and clicks else None
        row['cpa'] = round(row['cost'] / conversions, 2) if row['cost'] is not None and conversions else None
        row['roas'] = round(row['conversion_value'] / row['cost'], 2) if row['cost'] and row['conversion_value'] else None
    return rows


def _scope():
    selected = _selection()
    start, end = _period()
    span = (end - start).days + 1
    return selected, {'client': selected['client_id'], 'start': start, 'end': end, 'summary': SUMMARY_KIND, 'chunk': CHUNK_KIND}, \
        {'client': selected['client_id'], 'start': start - timedelta(days=span), 'end': start - timedelta(days=1)}


def _currency(scope):
    found = {row['currency'] for row in _rows(_CURRENCY_SQL, scope) if row['currency']}
    return next(iter(found)) if len(found) == 1 else None


def _accounts(scope):
    accounts = _rows(_ACCOUNTS_SQL, scope)
    for account in accounts:
        run = account.pop('last_run') or {}
        account['datasets'] = run.get('datasets') or []
        account['timed_out'] = bool(run.get('timed_out'))
    return accounts


def _terms(scope, negatives, known):
    terms = _money(_rows(_TERMS_SQL, scope))
    for term in terms:
        term['action'] = term_action({**term, 'cost': term['cost']}, negatives, term['account_id'] in known)
    return terms


def _known(accounts):
    now = datetime.now(timezone.utc)
    return {a['id'] for a in accounts if a.get('negatives_at') and (now - (a['negatives_at'] if a['negatives_at'].tzinfo else a['negatives_at'].replace(tzinfo=timezone.utc))).days < 7}


def _empty(start, end):
    return jsonify(ready=False, period={'start': start.isoformat(), 'end': end.isoformat()}, accounts=[], totals={}, previous={},
                   daily=[], campaigns=[], recommendations=[], rules=RULES, currency=None)


def register(bp):
    @bp.get('/api/v2/reports/google-ads/summary')
    @login_required_api
    def reports_google_ads_summary():
        """Account health, totals vs previous period, campaigns with settings, and recommendations in execution order."""
        selected, scope, previous_scope = _scope()
        if not _ready():
            return _empty(scope['start'], scope['end'])
        accounts = _accounts(scope)
        totals = _money(_rows(_TOTALS_SQL, scope))[0]
        previous = _money(_rows(_TOTALS_SQL, previous_scope))[0]
        settings = {(row['account_id'], row['campaign_external_id']): row for row in _rows(_SETTINGS_SQL, scope)}
        campaigns = _money(_rows(_CAMPAIGNS_SQL, scope))
        for campaign in campaigns:
            setting = settings.pop((campaign['account_id'], campaign['campaign_external_id']), {})
            campaign.update({key: setting.get(key) for key in ('status', 'serving_status', 'channel_type', 'bidding_strategy_type', 'budget_shared')})
            campaign['budget'] = round(setting['budget_micros'] / 1e6, 2) if setting.get('budget_micros') is not None else None
            campaign['daily_spend'] = round(campaign['cost'] / campaign['active_days'], 2) if campaign['cost'] is not None and campaign['active_days'] else None
            campaign['budget_usage'] = round(campaign['daily_spend'] * 100 / campaign['budget'], 1) if campaign.get('daily_spend') and campaign['budget'] else None
        # Enabled campaigns with no spend in the period still belong in the list.
        for setting in settings.values():
            if setting.get('status') == 'ENABLED':
                campaigns.append({'account_id': setting['account_id'], 'campaign_external_id': setting['campaign_external_id'],
                                  'campaign_name': setting['campaign_name'], 'impressions': 0, 'clicks': 0, 'cost': 0, 'conversions': 0,
                                  'conversion_value': 0, 'ctr': None, 'cpc': None, 'cpa': None, 'roas': None, 'active_days': 0,
                                  'status': setting['status'], 'serving_status': setting['serving_status'], 'channel_type': setting['channel_type'],
                                  'bidding_strategy_type': setting['bidding_strategy_type'], 'budget_shared': setting['budget_shared'],
                                  'budget': round(setting['budget_micros'] / 1e6, 2) if setting.get('budget_micros') is not None else None,
                                  'daily_spend': None, 'budget_usage': None})
        campaigns.sort(key=lambda row: -(row['cost'] or 0))
        negatives = [row for row in _rows(_NEGATIVES_SQL, scope) if row['removed_at'] is None]
        known = _known(accounts)
        terms = _terms(scope, negatives, known)
        keywords = _money(_rows(_KEYWORDS_SQL, scope))
        devices = _money(_rows(_DEVICES_SQL, scope))
        recommendations = build_recommendations(accounts=accounts, campaigns=campaigns, terms=terms, keywords=keywords,
                                                devices=devices, negatives=negatives, totals=totals)
        for account in accounts:
            for key in ('last_run_at', 'negatives_at'):
                account[key] = account[key].isoformat() if account.get(key) else None
        return jsonify(ready=True, period={'start': scope['start'].isoformat(), 'end': scope['end'].isoformat()}, currency=_currency(scope),
                       accounts=accounts, totals=totals, previous=previous, daily=_money(_rows(_DAILY_SQL, scope)),
                       campaigns=campaigns, recommendations=recommendations, rules=RULES,
                       counts={'negate': sum(t['action'] == 'negate' for t in terms), 'add_keyword': sum(t['action'] == 'add_keyword' for t in terms)})

    @bp.get('/api/v2/reports/google-ads/search-terms')
    @login_required_api
    def reports_google_ads_search_terms():
        """Search terms with the action each one calls for and whether a negative already covers it."""
        selected, scope, _ = _scope()
        if not _ready():
            return jsonify(ready=False, terms=[], currency=None)
        accounts = _accounts(scope)
        negatives = [row for row in _rows(_NEGATIVES_SQL, scope) if row['removed_at'] is None]
        known = _known(accounts)
        return jsonify(ready=True, currency=_currency(scope), terms=_terms(scope, negatives, known), limit=TERMS_LIMIT,
                       negatives_known=bool(known))

    @bp.get('/api/v2/reports/google-ads/keywords')
    @login_required_api
    def reports_google_ads_keywords():
        selected, scope, _ = _scope()
        if not _ready():
            return jsonify(ready=False, keywords=[], currency=None)
        return jsonify(ready=True, currency=_currency(scope), keywords=_money(_rows(_KEYWORDS_SQL, scope)), limit=TERMS_LIMIT)

    @bp.get('/api/v2/reports/google-ads/negatives')
    @login_required_api
    def reports_google_ads_negatives():
        """Active negatives by level, the ones removed in the last 30 days, and the active keywords each one blocks."""
        selected, scope, _ = _scope()
        if not _ready():
            return jsonify(ready=False, negatives=[], conflicts=[])
        rows = _rows(_NEGATIVES_SQL, scope)
        active = [row for row in rows if row['removed_at'] is None]
        keywords = [k for k in _money(_rows(_KEYWORDS_SQL, scope)) if int(k.get('impressions') or 0) > 0]
        conflicts = [{'negative_id': item['negative']['id'], 'keyword': item['keyword']['keyword_text'],
                      'campaign_name': item['keyword']['campaign_name'], 'ad_group_name': item['keyword']['ad_group_name'],
                      'cost': item['keyword']['cost']} for item in keyword_conflicts(keywords, active)]
        blocked = {item['negative_id'] for item in conflicts}
        for row in rows:
            row['blocks_keyword'] = row['id'] in blocked
        return jsonify(ready=True, negatives=rows, conflicts=conflicts, removed_days=REMOVED_DAYS)
