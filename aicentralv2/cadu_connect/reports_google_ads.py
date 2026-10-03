"""Mídia → Google Ads: the engine v2 data read as a Google Ads report, with recommendations in execution order.

Reads only what the script already stores (cadu_reports_gads_*, campaign daily metrics and the run summaries).
Amounts come in micros and are returned in currency units; a client mixing currencies gets costs as null.
"""
import calendar
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask import abort, jsonify, request

from ..auth import login_required_api
from .reports_google_ads_actions import recommendation_actions
from . import reports_google_ads_negatives as negative_review
from .reports_google_ads_rules import RULES, build_recommendations, keyword_conflicts, term_action
from ..db import get_db
from .reports_v1 import _column_exists, _rows, _selection, _write_guard

SUMMARY_KIND = 'google_ads_engine_v2'
CHUNK_KIND = 'google_ads_engine_v2_chunk'
TERMS_LIMIT = 500
REMOVED_DAYS = 30
_M = '''SUM(x.impressions)::bigint AS impressions,SUM(x.clicks)::bigint AS clicks,SUM(x.cost_micros)::bigint AS cost_micros,
    SUM(x.conversions)::numeric AS conversions,SUM(x.conversion_value_micros)::bigint AS value_micros'''
# Optional narrowing to one media account / one campaign (header selector); both params are None when everything is wanted.
_AF = '(%(account)s::int IS NULL OR {t}account_id=%(account)s)'
_CF = '(%(campaign)s::text IS NULL OR {t}campaign_external_id::text=%(campaign)s)'
_SCOPE_X = _AF.format(t='x.') + ' AND ' + _CF.format(t='x.')
_P = 'x.client_id=%(client)s AND x.metric_date BETWEEN %(start)s AND %(end)s AND ' + _SCOPE_X

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
        AND (%(account)s::int IS NULL OR a.id=%(account)s)
    ORDER BY a.name'''

_CAMPAIGNS_SQL = f'''SELECT x.account_id,x.campaign_external_id,
        (ARRAY_AGG(x.campaign_name ORDER BY x.metric_date DESC))[1] AS campaign_name,{_M},
        COUNT(DISTINCT x.metric_date) FILTER (WHERE x.cost_micros>0)::int AS active_days
    FROM cadu_reports_gads_ad_group_daily x WHERE {_P}
    GROUP BY x.account_id,x.campaign_external_id'''
_SETTINGS_SQL = '''SELECT account_id,campaign_external_id,campaign_name,status,serving_status,channel_type,
        bidding_strategy_type,budget_micros,budget_shared{targets}
    FROM cadu_reports_gads_campaign_settings WHERE client_id=%(client)s AND removed_at IS NULL
        AND ''' + _AF.format(t='') + ' AND ' + _CF.format(t='')
# Month-to-date and recent pace per campaign, independent of the period on screen.
_PACING_SQL = '''SELECT x.account_id,x.campaign_external_id,
        SUM(x.cost_micros) FILTER (WHERE x.metric_date>=%(month_start)s)::bigint AS mtd_cost_micros,
        SUM(x.conversions) FILTER (WHERE x.metric_date>=%(month_start)s)::numeric AS mtd_conversions,
        SUM(x.cost_micros) FILTER (WHERE x.metric_date>%(today)s - 7 AND x.metric_date<%(today)s)::bigint AS last7_cost_micros,
        SUM(x.conversions) FILTER (WHERE x.metric_date>%(today)s - 7 AND x.metric_date<%(today)s)::numeric AS last7_conversions,
        SUM(x.cost_micros) FILTER (WHERE x.metric_date>%(today)s - 3)::bigint AS last3_cost_micros
    FROM cadu_reports_gads_ad_group_daily x
    WHERE x.client_id=%(client)s AND x.metric_date>=LEAST(%(month_start)s,%(today)s - 7)
    GROUP BY x.account_id,x.campaign_external_id'''
_CAMPAIGN_IDS_SQL = '''SELECT id,account_id,external_id FROM cadu_reports_campaigns WHERE client_id=%(client)s AND account_id IS NOT NULL'''
_GOALS_SQL = '''SELECT g.campaign_id,g.objective,g.monthly_budget_cap,g.total_budget_cap,g.flight_start,g.flight_end,g.target_cpa,
        g.target_roas,g.target_conversions_month,g.notes,g.updated_at,c.account_id,c.external_id AS campaign_external_id,
        (SELECT SUM(x.cost_micros) FROM cadu_reports_gads_ad_group_daily x WHERE x.account_id=c.account_id
            AND x.campaign_external_id=c.external_id AND g.flight_start IS NOT NULL AND x.metric_date>=g.flight_start
            AND (g.flight_end IS NULL OR x.metric_date<=g.flight_end))::bigint AS flight_cost_micros
    FROM cadu_reports_campaign_goals g JOIN cadu_reports_campaigns c ON c.id=g.campaign_id WHERE g.client_id=%(client)s'''
_HISTORY_SQL = '''SELECT observed_at,status,bidding_strategy_type,budget_micros,target_cpa_micros,target_roas
    FROM cadu_reports_gads_campaign_settings_history
    WHERE client_id=%(client)s AND account_id=%(account)s AND campaign_external_id=%(campaign)s
    ORDER BY observed_at DESC LIMIT 50'''
OBJECTIVES = ('leads', 'sales', 'traffic', 'awareness', 'app')
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
        AND ''' + _AF.format(t='n.') + ' AND ' + _CF.format(t='n.') + '''
    ORDER BY n.removed_at NULLS FIRST,n.level,n.shared_set_name,n.campaign_name,n.keyword_text'''
_CURRENCY_SQL = '''SELECT DISTINCT COALESCE(currency,'') AS currency FROM cadu_reports_accounts
    WHERE client_id=%(client)s AND platform='google_ads' AND account_kind='advertiser' AND status<>'disabled'
        AND (%(account)s::int IS NULL OR id=%(account)s) '''

# Every campaign the Google Ads scripts have seen (registered or not) with the ids the selector needs.
_SCOPE_INDEX_SQL = '''SELECT s.account_id,s.campaign_external_id::text AS campaign_external_id,s.campaign_name,s.status,
        (SELECT c.id FROM cadu_reports_campaigns c WHERE c.client_id=%(client)s AND c.account_id=s.account_id
            AND c.external_id=s.campaign_external_id::text LIMIT 1) AS linked_id
    FROM (SELECT DISTINCT ON (account_id,campaign_external_id) account_id,campaign_external_id,campaign_name,status
        FROM (SELECT account_id,campaign_external_id,campaign_name,status,0 AS rank
                FROM cadu_reports_gads_campaign_settings WHERE client_id=%(client)s AND removed_at IS NULL
            UNION ALL SELECT account_id,campaign_external_id,(ARRAY_AGG(campaign_name ORDER BY metric_date DESC))[1],NULL,1
                FROM cadu_reports_gads_ad_group_daily WHERE client_id=%(client)s GROUP BY account_id,campaign_external_id) u
        ORDER BY account_id,campaign_external_id,rank) s
    JOIN cadu_reports_accounts a ON a.id=s.account_id AND a.client_id=%(client)s AND a.platform='google_ads' AND a.status<>'disabled'
    ORDER BY (s.status='ENABLED') DESC NULLS LAST,s.campaign_name'''

_UNLINKED_SQL = '''SELECT s.account_id,a.name AS account_name,s.campaign_external_id,s.campaign_name,s.status,s.channel_type,
        s.bidding_strategy_type,s.last_seen
    FROM (SELECT DISTINCT ON (account_id,campaign_external_id) account_id,campaign_external_id,campaign_name,status,channel_type,
            bidding_strategy_type,last_seen
        FROM (SELECT account_id,campaign_external_id,campaign_name,status,channel_type,bidding_strategy_type,NULL::date AS last_seen,0 AS rank
                FROM cadu_reports_gads_campaign_settings WHERE client_id=%(client)s AND removed_at IS NULL
            UNION ALL SELECT account_id,campaign_external_id,campaign_name,NULL,NULL,NULL,MAX(metric_date),1
                FROM cadu_reports_gads_ad_group_daily WHERE client_id=%(client)s GROUP BY account_id,campaign_external_id,campaign_name) u
        ORDER BY account_id,campaign_external_id,rank,last_seen DESC NULLS LAST) s
    JOIN cadu_reports_accounts a ON a.id=s.account_id AND a.client_id=%(client)s
    WHERE NOT EXISTS (SELECT 1 FROM cadu_reports_campaigns c WHERE c.account_id=s.account_id AND c.external_id=s.campaign_external_id::text)
    ORDER BY (s.status='ENABLED') DESC NULLS LAST,a.name,s.campaign_name'''

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
        if isinstance(row.get('date'), date):
            row['date'] = row['date'].isoformat()
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


def _comparison(start, end, mode):
    """The window compared against: the previous span of the same length, or the same dates one year earlier."""
    if mode == 'year':
        def back(day):
            try:
                return day.replace(year=day.year - 1)
            except ValueError:
                return day - timedelta(days=365)
        return back(start), back(end)
    span = (end - start).days + 1
    return start - timedelta(days=span), start - timedelta(days=1)


def _narrowing(client_id):
    """(account id, campaign external id) from ?scope_account / ?scope_campaign, checked against the client; (None, None) = all."""
    account, campaign = request.args.get('scope_account', ''), request.args.get('scope_campaign', '')
    # A campaign the scripts saw but nobody registered is picked as "<account id>:<Google campaign id>".
    native = re.fullmatch(r'(\d{1,12}):(\d{1,20})', campaign)
    if native:
        if not _rows("SELECT 1 FROM cadu_reports_accounts WHERE id=%s AND client_id=%s AND platform='google_ads'", (int(native[1]), client_id)):
            abort(404, description='Campanha não encontrada para este cliente.')
        return int(native[1]), native[2]
    if campaign.isdigit():
        row = _rows('SELECT account_id,external_id FROM cadu_reports_campaigns WHERE id=%s AND client_id=%s AND account_id IS NOT NULL',
                    (int(campaign), client_id))
        if not row:
            abort(404, description='Campanha não encontrada para este cliente.')
        return row[0]['account_id'], str(row[0]['external_id'])
    if account.isdigit():
        if not _rows('SELECT 1 FROM cadu_reports_accounts WHERE id=%s AND client_id=%s', (int(account), client_id)):
            abort(404, description='Fonte de dados não encontrada para este cliente.')
        return int(account), None
    return None, None


def _scope():
    selected = _selection()
    start, end = _period()
    mode = request.args.get('compare') if request.args.get('compare') in ('previous', 'year') else 'previous'
    before_start, before_end = _comparison(start, end, mode)
    account, campaign = _narrowing(selected['client_id'])
    return selected, {'client': selected['client_id'], 'start': start, 'end': end, 'summary': SUMMARY_KIND, 'chunk': CHUNK_KIND,
                      'compare': mode, 'account': account, 'campaign': campaign}, \
        {'client': selected['client_id'], 'start': before_start, 'end': before_end, 'account': account, 'campaign': campaign}


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


def _goals_ready():
    return bool(_rows("SELECT to_regclass('public.cadu_reports_campaign_goals') IS NOT NULL AS ready")[0]['ready'])


def _today():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).date()


def _attach_goals(scope, campaigns):
    """Campaign id (to save goals), the goal itself and the month pace that the goal rules read."""
    today = _today()
    month_start = today.replace(day=1)
    days_left = calendar.monthrange(today.year, today.month)[1] - today.day
    ids = {(row['account_id'], str(row['external_id'])): row['id'] for row in _rows(_CAMPAIGN_IDS_SQL, scope)}
    pace = {(row['account_id'], row['campaign_external_id']): row for row in
            _rows(_PACING_SQL, {'client': scope['client'], 'month_start': month_start, 'today': today})}
    goals = {(row['account_id'], str(row['campaign_external_id'])): row for row in _rows(_GOALS_SQL, scope)} if _goals_ready() else {}
    for campaign in campaigns:
        key = (campaign['account_id'], str(campaign['campaign_external_id']))
        campaign['campaign_id'] = ids.get(key)
        row = pace.get(key) or {}
        mtd = (row.get('mtd_cost_micros') or 0) / 1e6
        daily = (row.get('last7_cost_micros') or 0) / 1e6 / 7
        mtd_conv = float(row.get('mtd_conversions') or 0)
        daily_conv = float(row.get('last7_conversions') or 0) / 7
        campaign['pacing'] = {'mtd_cost': round(mtd, 2), 'mtd_conversions': round(mtd_conv, 2), 'daily_avg': round(daily, 2),
                              'days_left': days_left, 'projected_cost': round(mtd + daily * days_left, 2),
                              'projected_conversions': round(mtd_conv + daily_conv * days_left, 1),
                              'last3_cost': round((row.get('last3_cost_micros') or 0) / 1e6, 2)}
        goal = goals.get(key)
        if goal:
            campaign['pacing']['flight_cost'] = round((goal.pop('flight_cost_micros') or 0) / 1e6, 2)
            goal = {k: (float(v) if isinstance(v, Decimal) else v.isoformat() if isinstance(v, (date, datetime)) else v)
                    for k, v in goal.items() if k not in ('account_id', 'campaign_external_id')}
            goal['flight_ended'] = bool(goal.get('flight_end') and date.fromisoformat(goal['flight_end']) < today)
        campaign['goal'] = goal


def _money_value(payload, key, maximum=1e9):
    value = payload.get(key)
    if value in (None, ''):
        return None
    try:
        parsed = Decimal(str(value).replace(',', '.'))
    except InvalidOperation:
        abort(400, description=f'Valor inválido em {key}.')
    if parsed < 0 or parsed > Decimal(str(maximum)):
        abort(400, description=f'Valor fora do limite em {key}.')
    return parsed


def _day_value(payload, key):
    value = payload.get(key)
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        abort(400, description=f'Data inválida em {key}.')


def _analysis(scope, previous_scope):
    """Everything the Google Ads summary and the per-account portfolio read, for one (possibly narrowed) scope."""
    accounts = _accounts(scope)
    totals = _money(_rows(_TOTALS_SQL, scope))[0]
    previous = _money(_rows(_TOTALS_SQL, previous_scope))[0]
    targets = _column_exists('cadu_reports_gads_campaign_settings', 'target_cpa_micros')
    settings = {(row['account_id'], row['campaign_external_id']): row for row in
                _rows(_SETTINGS_SQL.format(targets=',target_cpa_micros,target_roas' if targets else ''), scope)}
    campaigns = _money(_rows(_CAMPAIGNS_SQL, scope))
    before = {(row['account_id'], row['campaign_external_id']): row for row in _money(_rows(_CAMPAIGNS_SQL, previous_scope))}
    for campaign in campaigns:
        setting = settings.pop((campaign['account_id'], campaign['campaign_external_id']), {})
        campaign.update({key: setting.get(key) for key in ('status', 'serving_status', 'channel_type', 'bidding_strategy_type', 'budget_shared')})
        campaign['target_cpa'] = round(setting['target_cpa_micros'] / 1e6, 2) if setting.get('target_cpa_micros') else None
        campaign['target_roas'] = float(setting['target_roas']) if setting.get('target_roas') else None
        prior = before.get((campaign['account_id'], campaign['campaign_external_id']))
        campaign['previous'] = {key: prior.get(key) for key in ('cost', 'clicks', 'conversions', 'cpa', 'roas')} if prior else None
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
    _attach_goals(scope, campaigns)
    negatives = [row for row in _rows(_NEGATIVES_SQL, scope) if row['removed_at'] is None]
    known = _known(accounts)
    terms = _terms(scope, negatives, known)
    keywords = _money(_rows(_KEYWORDS_SQL, scope))
    devices = _money(_rows(_DEVICES_SQL, scope))
    recommendations = build_recommendations(accounts=accounts, campaigns=campaigns, terms=terms, keywords=keywords,
                                            devices=devices, negatives=negatives, totals=totals)
    return {'accounts': accounts, 'totals': totals, 'previous': previous, 'campaigns': campaigns, 'negatives': negatives,
            'terms': terms, 'keywords': keywords, 'devices': devices, 'recommendations': recommendations}


def register(bp):
    @bp.put('/api/v2/reports/google-ads/goals/<int:campaign_id>')
    @login_required_api
    def reports_google_ads_goal(campaign_id):
        """Save what the team wants from a campaign. Empty fields clear the target."""
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        if not _goals_ready():
            abort(503, description='Aplique a migração add_reports_google_ads_history_goals.sql para registrar metas.')
        if not _rows('SELECT id FROM cadu_reports_campaigns WHERE id=%s AND client_id=%s', (campaign_id, selected['client_id'])):
            abort(404, description='Campanha não encontrada.')
        objective = payload.get('objective') or None
        if objective is not None and objective not in OBJECTIVES:
            abort(400, description='Objetivo inválido.')
        conversions = payload.get('target_conversions_month')
        try:
            conversions = int(conversions) if conversions not in (None, '') else None
        except (TypeError, ValueError):
            abort(400, description='Meta de conversões inválida.')
        start, end = _day_value(payload, 'flight_start'), _day_value(payload, 'flight_end')
        if start and end and end < start:
            abort(400, description='A data final deve ser depois da inicial.')
        values = {'campaign': campaign_id, 'client': selected['client_id'], 'objective': objective,
                  'monthly': _money_value(payload, 'monthly_budget_cap'), 'total': _money_value(payload, 'total_budget_cap'),
                  'start': start, 'end': end, 'cpa': _money_value(payload, 'target_cpa'), 'roas': _money_value(payload, 'target_roas', 1000),
                  'conversions': conversions, 'notes': str(payload.get('notes') or '')[:1000] or None, 'user': selected['user_id']}
        _rows('''INSERT INTO cadu_reports_campaign_goals (campaign_id,client_id,objective,monthly_budget_cap,total_budget_cap,flight_start,
                flight_end,target_cpa,target_roas,target_conversions_month,notes,updated_by,updated_at)
            VALUES (%(campaign)s,%(client)s,%(objective)s,%(monthly)s,%(total)s,%(start)s,%(end)s,%(cpa)s,%(roas)s,%(conversions)s,%(notes)s,%(user)s,NOW())
            ON CONFLICT (campaign_id) DO UPDATE SET objective=EXCLUDED.objective,monthly_budget_cap=EXCLUDED.monthly_budget_cap,
                total_budget_cap=EXCLUDED.total_budget_cap,flight_start=EXCLUDED.flight_start,flight_end=EXCLUDED.flight_end,
                target_cpa=EXCLUDED.target_cpa,target_roas=EXCLUDED.target_roas,target_conversions_month=EXCLUDED.target_conversions_month,
                notes=EXCLUDED.notes,updated_by=EXCLUDED.updated_by,updated_at=NOW()
            RETURNING campaign_id''', values)
        get_db().commit()
        return jsonify(saved=True)

    @bp.get('/api/v2/reports/google-ads/campaigns/<int:account_id>/<campaign_external_id>/history')
    @login_required_api
    def reports_google_ads_campaign_history(account_id, campaign_external_id):
        """Changes of status, bidding, budget and targets as the script observed them."""
        selected = _selection()
        if not _rows("SELECT to_regclass('public.cadu_reports_gads_campaign_settings_history') IS NOT NULL AS ready")[0]['ready']:
            return jsonify(history=[], ready=False)
        rows = _rows(_HISTORY_SQL, {'client': selected['client_id'], 'account': account_id, 'campaign': campaign_external_id[:20]})
        for row in rows:
            row['budget'] = round(row.pop('budget_micros') / 1e6, 2) if row.get('budget_micros') is not None else None
            row['target_cpa'] = round(row.pop('target_cpa_micros') / 1e6, 2) if row.get('target_cpa_micros') else None
            row['target_roas'] = float(row['target_roas']) if row.get('target_roas') else None
        return jsonify(history=rows, ready=True)

    @bp.get('/api/v2/reports/google-ads/unlinked-campaigns')
    @login_required_api
    def reports_google_ads_unlinked_campaigns():
        """Campaigns the script already sent that have no Reports campaign yet, so they can be created with the right ids."""
        selected = _selection()
        if not _ready():
            return jsonify(campaigns=[])
        rows = _rows(_UNLINKED_SQL, {'client': selected['client_id']})
        for row in rows:
            row['campaign_external_id'] = str(row['campaign_external_id'])
            row['last_seen'] = row['last_seen'].isoformat() if row.get('last_seen') else None
        return jsonify(campaigns=rows)

    @bp.get('/api/v2/reports/google-ads/scope')
    @login_required_api
    def reports_google_ads_scope():
        """Sources (Google Ads advertiser accounts) and campaigns for the header selector, registered or not."""
        selected = _selection()
        if not _ready():
            return jsonify(accounts=[], campaigns=[])
        accounts = [{'id': row['id'], 'name': row['name'], 'external_id': row['external_id'], 'platform': 'google_ads', 'status': row['status']}
                    for row in _rows(_ACCOUNTS_SQL, {'client': selected['client_id'], 'summary': SUMMARY_KIND, 'chunk': CHUNK_KIND, 'account': None})]
        campaigns = [{'id': f"{row['account_id']}:{row['campaign_external_id']}", 'account_id': row['account_id'], 'name': row['campaign_name'],
                      'status': row['status'], 'linked_id': row['linked_id']}
                     for row in _rows(_SCOPE_INDEX_SQL, {'client': selected['client_id']})]
        return jsonify(accounts=accounts, campaigns=campaigns)

    @bp.get('/api/v2/reports/google-ads/summary')
    @login_required_api
    def reports_google_ads_summary():
        """Account health, totals vs previous period, campaigns with settings, and recommendations in execution order."""
        selected, scope, previous_scope = _scope()
        if not _ready():
            return _empty(scope['start'], scope['end'])
        analysis = _analysis(scope, previous_scope)
        accounts, totals, previous = analysis['accounts'], analysis['totals'], analysis['previous']
        campaigns, terms, recommendations = analysis['campaigns'], analysis['terms'], analysis['recommendations']
        # What already happened to each recommendation through the Ações script (queued, applied, undone).
        queued = recommendation_actions(scope['client'], [item['id'] for item in recommendations if item.get('proposal')])
        for item in recommendations:
            item['queued'] = queued.get(item['id'])
        for account in accounts:
            for key in ('last_run_at', 'negatives_at'):
                account[key] = account[key].isoformat() if account.get(key) else None
        return jsonify(ready=True, period={'start': scope['start'].isoformat(), 'end': scope['end'].isoformat()}, currency=_currency(scope),
                       compare={'mode': scope['compare'], 'start': previous_scope['start'].isoformat(), 'end': previous_scope['end'].isoformat()},
                       goals_ready=_goals_ready(), accounts=accounts, totals=totals, previous=previous, daily=_money(_rows(_DAILY_SQL, scope)),
                       previous_daily=_money(_rows(_DAILY_SQL, previous_scope)),
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

    def _negatives_state(scope):
        rows = _rows(_NEGATIVES_SQL, scope)
        active = [row for row in rows if row['removed_at'] is None]
        keywords = [k for k in _money(_rows(_KEYWORDS_SQL, scope)) if int(k.get('impressions') or 0) > 0]
        terms = _money(_rows(_TERMS_SQL, scope))
        conflicts = [{'negative_id': item['negative']['id'], 'keyword': item['keyword']['keyword_text'],
                      'campaign_name': item['keyword']['campaign_name'], 'ad_group_name': item['keyword']['ad_group_name'],
                      'cost': item['keyword']['cost']} for item in keyword_conflicts(keywords, active)]
        blocked = {item['negative_id'] for item in conflicts}
        for row in rows:
            row['blocks_keyword'] = row['id'] in blocked
        scored = negative_review.score_negatives(rows, keywords, terms, blocked)
        return rows, scored, keywords, terms, conflicts

    @bp.get('/api/v2/reports/google-ads/negatives')
    @login_required_api
    def reports_google_ads_negatives():
        """Active negatives with score and group, the ones removed in the last 30 days, and the keywords each one blocks."""
        selected, scope, _ = _scope()
        if not _ready():
            return jsonify(ready=False, negatives=[], conflicts=[])
        rows, scored, _, _, conflicts = _negatives_state(scope)
        return jsonify(ready=True, negatives=rows, conflicts=conflicts, removed_days=REMOVED_DAYS,
                       groups=negative_review.GROUPS, summary=negative_review.summary(scored))

    @bp.post('/api/v2/reports/google-ads/negatives/review')
    @login_required_api
    def reports_google_ads_negatives_review():
        """Agente revisor: reads the account's keywords and converting terms and rules on each negative. Suggests only."""
        selected, scope, _ = _scope()
        _write_guard(selected)
        if not _ready():
            abort(409, description='Google Ads ainda não conectado.')
        _, scored, keywords, terms, _ = _negatives_state(scope)
        try:
            reviews = negative_review.review(scored, keywords, terms)
        except negative_review.ReviewError as exc:
            abort(502, description=str(exc))
        return jsonify(reviews={str(key): value for key, value in reviews.items()}, ai_confidence=negative_review.AI_CONFIDENCE)
