"""Mídia → Criativos e anúncios: the portfolio view. One row per Google Ads account of the client in use, ranked by how much
there is to fix, built from the same analysis that feeds the Central de ações (so the totals always agree with it)."""
from flask import jsonify

from ..auth import login_required_api
from . import reports_google_ads as gads
from .reports_v1 import _rows

MAX_ACCOUNTS = 25
LOW_QUALITY_SCORE = 4
WEAK_STRENGTHS = ('POOR', 'AVERAGE')
GAP_FORMULA = 'prioridade alta × 3 + média × 2 + baixa × 1 + anúncios fracos × 2 + palavras com Índice de Qualidade ≤ 4'


def _table_ready(name):
    return bool(_rows('SELECT to_regclass(%s) IS NOT NULL AS ready', (f'public.{name}',))[0]['ready'])


def account_row(account, analysis, weak_ads):
    recommendations = analysis['recommendations']
    count = lambda severity: sum(1 for item in recommendations if item['severity'] == severity)
    terms = analysis['terms']
    low_quality = sum(1 for row in analysis['keywords']
                      if row.get('quality_score') and row['quality_score'] <= LOW_QUALITY_SCORE and (row.get('cost') or 0) > 0)
    problems = [item['name'] for item in account.get('datasets') or [] if item.get('status') in ('error', 'truncated', 'skipped')]
    row = {
        'id': account['id'], 'name': account['name'], 'external_id': account['external_id'], 'platform': 'google_ads',
        'cost': analysis['totals'].get('cost') or 0, 'conversions': analysis['totals'].get('conversions') or 0,
        'waste_cost': round(sum(term.get('cost') or 0 for term in terms if term['action'] == 'negate'), 2),
        'waste_terms': sum(1 for term in terms if term['action'] == 'negate'),
        'opportunities': sum(1 for term in terms if term['action'] == 'add_keyword'),
        'low_quality_keywords': low_quality,
        'high': count('high'), 'medium': count('medium'), 'low': count('low'),
        'at_stake': round(sum(item['impact']['value'] for item in recommendations if item['impact']['kind'] == 'cost'), 2),
        'pending_changes': sum(1 for item in recommendations if item.get('proposal') and not item.get('queued')),
        'weak_ads': weak_ads,  # None until the account's script sends ads (engine 2.2)
        'last_run_at': account['last_run_at'].isoformat() if account.get('last_run_at') else None,
        'collection_problems': problems,
    }
    row['gap'] = row['high'] * 3 + row['medium'] * 2 + row['low'] + (weak_ads or 0) * 2 + low_quality
    return row


def portfolio(scope, previous_scope):
    """Rows for every advertiser account in scope, most work first. Narrowing by account/campaign does not apply here."""
    base = {**scope, 'account': None, 'campaign': None}
    accounts = gads._accounts(base)[:MAX_ACCOUNTS]
    ads_ready = _table_ready('cadu_reports_gads_ads')
    rows = []
    for account in accounts:
        mine = {**scope, 'account': account['id'], 'campaign': None}
        before = {**previous_scope, 'account': account['id'], 'campaign': None}
        analysis = gads._analysis(mine, before)
        weak = None
        if ads_ready:
            found = _rows('''SELECT COUNT(*)::int AS weak FROM cadu_reports_gads_ads
                WHERE client_id=%s AND account_id=%s AND removed_at IS NULL AND status='ENABLED' AND ad_strength = ANY(%s)''',
                          (scope['client'], account['id'], list(WEAK_STRENGTHS)))
            ads_seen = _rows('SELECT 1 FROM cadu_reports_gads_ads WHERE client_id=%s AND account_id=%s LIMIT 1', (scope['client'], account['id']))
            weak = found[0]['weak'] if ads_seen else None
        rows.append(account_row(account, analysis, weak))
    rows.sort(key=lambda row: (-row['gap'], -row['cost']))
    return rows


def register(bp):
    @bp.get('/api/v2/reports/assets/portfolio')
    @login_required_api
    def reports_assets_portfolio():
        selected, scope, previous_scope = gads._scope()
        if not gads._ready():
            return jsonify(ready=False, accounts=[], formula=GAP_FORMULA)
        return jsonify(ready=True, formula=GAP_FORMULA, currency=gads._currency({**scope, 'account': None}),
                       period={'start': scope['start'].isoformat(), 'end': scope['end'].isoformat()},
                       accounts=portfolio(scope, previous_scope))
