"""Google Ads findings for the alert center: the recommendations the engine v2 already computes, kept as alerts.

Nothing new is measured here. Each recommendation of reports_google_ads_rules becomes an alert of the client (no site), so it
has state, owner, silence and history, and closes by itself when the recommendation stops appearing. Rules that point to a
broken pipe or a missed target are incidents; the rest are opportunities. No Google Ads API is used: only the data the two
scripts already sent.
"""
from datetime import timedelta

from .reports_google_ads_rules import RULES as GADS_RULES

PERIOD_DAYS = 30
# Pipe or target problems that need someone now; everything else in the Google Ads rules is an improvement to consider.
INCIDENT_RULES = frozenset({'script_stale', 'data_incomplete', 'cap_reached', 'flight_ended', 'pacing_over', 'cpa_above_target',
                            'roas_below_target', 'conversion_goal_risk', 'negative_conflict', 'campaign_without_conversion'})
_PREFIX = 'gads_'


def alert_rule(rule):
    return f'{_PREFIX}{rule}'


def alert_rules():
    """Catalog entries (same shape as reports_alert_rules.RULES values) for every Google Ads rule."""
    return {alert_rule(item['rule']): {'channel': 'google_ads', 'kind': 'incident' if item['rule'] in INCIDENT_RULES else 'opportunity',
                                       'severity': item['severity'], 'title': f"Google Ads: {item['title']}", 'when': item['when']}
            for item in GADS_RULES}


def _brl(value):
    return 'R$ ' + f'{value:,.2f}'.replace(',', '#').replace('.', ',').replace('#', '.')


def _impact(impact):
    kind, value = impact.get('kind'), float(impact.get('value') or 0)
    if kind == 'none' or not value:
        return None
    if kind == 'cost':
        return {'value': _brl(value), 'unit': 'text', 'label': 'gasto envolvido'}
    return {'value': round(value, 2), 'unit': 'count', 'label': str(kind)}


def finding_from_recommendation(item):
    label = (item.get('object') or {}).get('label') or ''
    title = item['title'] + (f': {label}' if label else '')
    evidence = [{'label': str(name), 'value': str(value), 'unit': 'text'} for name, value in item.get('evidence') or ()]
    return {'rule': alert_rule(item['rule']), 'subject_key': item['id'][:520], 'severity': item['severity'], 'title': title[:200],
            'summary': item['summary'], 'evidence': evidence, 'page_path': None, 'channel': 'google_ads',
            'kind': 'incident' if item['rule'] in INCIDENT_RULES else 'opportunity', 'impact': _impact(item.get('impact') or {}),
            'recommendations': [item['action']] if item.get('action') else []}


def findings_by_rule(recommendations):
    """Every Google Ads rule gets an entry, empty when it found nothing, so its old alerts are closed by the sync."""
    grouped = {alert_rule(item['rule']): [] for item in GADS_RULES}
    for item in recommendations:
        grouped[alert_rule(item['rule'])].append(finding_from_recommendation(item))
    return grouped


def evaluate_google_ads(client_id, today, analysis, sync, now):
    """analysis(scope, previous_scope) and sync(site, rule, findings, now) are injected so the worker and the tests share this."""
    from . import reports_google_ads as gads
    end = today
    start = end - timedelta(days=PERIOD_DAYS - 1)
    span = (end - start).days + 1
    scope = {'client': client_id, 'start': start, 'end': end, 'summary': gads.SUMMARY_KIND, 'chunk': gads.CHUNK_KIND, 'compare': 'previous',
             'account': None, 'campaign': None}
    previous = {'client': client_id, 'start': start - timedelta(days=span), 'end': start - timedelta(days=1), 'account': None, 'campaign': None}
    grouped = findings_by_rule(analysis(scope, previous)['recommendations'])
    for rule, findings in grouped.items():
        sync({'id': None, 'client_id': client_id}, rule, findings, now)
    return sum(len(findings) for findings in grouped.values())
