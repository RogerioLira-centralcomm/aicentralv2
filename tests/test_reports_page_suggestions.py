import copy
import datetime
from unittest import mock

import pytest
from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_pages as pages
from aicentralv2.cadu_connect.reports_page_metrics import build_metrics
from aicentralv2.cadu_connect.reports_page_suggestions import (
    RULES, build_suggestions, negative_covers, term_is_covered)

CAMPAIGN = {'account_id': 5, 'campaign_external_id': '111', 'campaign_name': 'Verão', 'currency': 'BRL',
            'clicks': 100, 'cost_micros': 50_000_000, 'conversions': 4.0}
TERM = {'account_id': 5, 'campaign_external_id': '111', 'ad_group_external_id': '2', 'term_hash': 'h1', 'search_term': 'tênis grátis',
        'campaign_name': 'Verão', 'currency': 'BRL', 'clicks': 25, 'cost_micros': 12_000_000, 'conversions': 0.0}
HEALTHY = {'latest': {'status': 'online', 'http_status': 200, 'duration_ms': 200}, 'timeline': [{'status': 'online'}] * 5}


def metrics(**overrides):
    base = build_metrics({'sessions': 100, 'views': 100, 'scroll_50': 60, 'measured_visits': 50, 'avg_active_ms': 9000},
                         {'entrances': 80, 'exits': 40, 'single_page': 20, 'converted': 10})
    return {**base, **overrides}


def ctx(**overrides):
    base = {'metrics': metrics(), 'previous': None, 'paid': {'available': True, 'campaigns': [CAMPAIGN], 'keywords': []},
            'health': HEALTHY, 'google_sessions': 90, 'candidate_terms': [], 'negatives': [], 'accounts_with_negatives': {5}}
    base.update(overrides)
    return base


def rules(result):
    return [item['rule'] for item in result['suggestions']]


def test_a_healthy_page_yields_no_suggestions_and_exposes_the_rules():
    result = build_suggestions(ctx())
    assert result['suggestions'] == [] and result['skipped'] == [] and len(result['rules']) == len(RULES)


@pytest.mark.parametrize('term,text,match,expected', [
    ('tênis grátis', 'tênis grátis', 'EXACT', True), ('tênis grátis hoje', 'tênis grátis', 'EXACT', False),
    ('comprar tênis grátis hoje', 'tênis grátis', 'PHRASE', True), ('grátis tênis', 'tênis grátis', 'PHRASE', False),
    ('grátis tênis hoje', 'tênis grátis', 'BROAD', True), ('tênis hoje', 'tênis grátis', 'BROAD', False),
    ('', 'x', 'BROAD', False), ('x', '', 'BROAD', False)])
def test_negative_match_types(term, text, match, expected):
    assert negative_covers(term, text, match) is expected


def test_negative_applies_only_at_its_own_level():
    base = {'account_id': 5, 'keyword_text': 'grátis', 'match_type': 'BROAD', 'campaign_external_id': None, 'ad_group_external_id': None, 'attached_campaign_ids': []}
    assert term_is_covered(TERM, [{**base, 'level': 'campaign', 'campaign_external_id': '111'}])
    assert not term_is_covered(TERM, [{**base, 'level': 'campaign', 'campaign_external_id': '999'}])
    assert term_is_covered(TERM, [{**base, 'level': 'ad_group', 'ad_group_external_id': '2'}])
    assert not term_is_covered(TERM, [{**base, 'level': 'ad_group', 'ad_group_external_id': '3'}])
    assert term_is_covered(TERM, [{**base, 'level': 'shared_list', 'attached_campaign_ids': ['111', '5']}])
    assert not term_is_covered(TERM, [{**base, 'level': 'shared_list', 'attached_campaign_ids': ['5']}])
    assert not term_is_covered(TERM, [{**base, 'level': 'campaign', 'campaign_external_id': '111', 'account_id': 6}])


def test_negative_candidate_has_evidence_and_respects_thresholds_and_coverage():
    covered = {'account_id': 5, 'level': 'campaign', 'campaign_external_id': '111', 'ad_group_external_id': None,
               'attached_campaign_ids': [], 'keyword_text': 'grátis', 'match_type': 'BROAD'}
    result = build_suggestions(ctx(candidate_terms=[TERM, {**TERM, 'term_hash': 'h2', 'search_term': 'sapato barato', 'clicks': 9},
                                                    {**TERM, 'term_hash': 'h3', 'search_term': 'tênis comprar', 'conversions': 1.0}]))
    assert rules(result) == ['negative_candidate']
    item = result['suggestions'][0]
    assert 'tênis grátis' in item['summary'] and {e['label'] for e in item['evidence']} >= {'Cliques', 'Custo', 'Conversões'}
    assert 'não altera a conta' in item['action']
    assert rules(build_suggestions(ctx(candidate_terms=[TERM], negatives=[covered]))) == []


def test_without_the_negative_snapshot_no_term_is_called_a_candidate_and_it_says_so():
    result = build_suggestions(ctx(candidate_terms=[TERM], accounts_with_negatives=set()))
    assert 'negative_candidate' not in rules(result) and any('negativas' in note for note in result['skipped'])


def test_missing_google_ads_data_is_reported_not_guessed():
    result = build_suggestions(ctx(paid={'available': False, 'reason': 'x'}))
    assert result['suggestions'] == [] and any('páginas de destino' in note for note in result['skipped'])


def test_page_down_with_paid_spend_is_the_top_suggestion():
    down = {'latest': {'status': 'offline', 'http_status': 503, 'duration_ms': 900}, 'timeline': [{'status': 'offline'}]}
    result = build_suggestions(ctx(health=down, candidate_terms=[TERM]))
    assert rules(result)[0] == 'paid_page_down' and result['suggestions'][0]['severity'] == 'high'
    free = {**CAMPAIGN, 'cost_micros': 0}
    assert 'paid_page_down' not in rules(build_suggestions(ctx(health=down, paid={'available': True, 'campaigns': [free], 'keywords': []})))


def test_campaign_without_conversion_needs_clicks_cost_and_zero_conversions():
    dead = {**CAMPAIGN, 'conversions': 0.0}
    assert rules(build_suggestions(ctx(paid={'available': True, 'campaigns': [dead], 'keywords': []}))) == ['campaign_without_conversion']
    few = {**dead, 'clicks': 29}
    assert build_suggestions(ctx(paid={'available': True, 'campaigns': [few], 'keywords': []}))['suggestions'] == []


def test_weak_engagement_requires_reliable_sample_and_paid_traffic():
    weak = metrics(exit_rate=80.0, scroll_50=10.0)
    assert 'weak_engagement' in rules(build_suggestions(ctx(metrics=weak)))
    assert 'weak_engagement' not in rules(build_suggestions(ctx(metrics={**weak, 'reliable': False})))
    assert 'weak_engagement' not in rules(build_suggestions(ctx(metrics=weak, paid={'available': True, 'campaigns': [{**CAMPAIGN, 'clicks': 5}], 'keywords': []})))
    assert 'weak_engagement' not in rules(build_suggestions(ctx(metrics={**weak, 'scroll_50': None})))


def test_tracking_gap_compares_ads_clicks_with_google_sessions():
    assert 'tracking_gap' in rules(build_suggestions(ctx(google_sessions=20)))
    assert 'tracking_gap' not in rules(build_suggestions(ctx(google_sessions=60)))
    assert 'tracking_gap' not in rules(build_suggestions(ctx(google_sessions=0, paid={'available': True, 'campaigns': [{**CAMPAIGN, 'clicks': 49}], 'keywords': []})))


def test_low_quality_score_only_counts_when_the_page_is_unstable():
    keyword = {'keyword_text': 'tênis', 'quality_score': 3, 'clicks': 40}
    paid = {'available': True, 'campaigns': [CAMPAIGN], 'keywords': [keyword, {**keyword, 'keyword_text': 'ok', 'quality_score': 8}]}
    assert 'low_quality_unstable_page' not in rules(build_suggestions(ctx(paid=paid)))
    slow = {'latest': {'status': 'online', 'http_status': 200, 'duration_ms': 2400}, 'timeline': [{'status': 'online'}]}
    flaky = {'latest': {'status': 'online', 'http_status': 200, 'duration_ms': 100}, 'timeline': [{'status': 'online'}, {'status': 'offline'}]}
    for health in (slow, flaky):
        result = build_suggestions(ctx(paid=paid, health=health))
        assert rules(result).count('low_quality_unstable_page') == 1 and 'tênis' in result['suggestions'][0]['summary']


def test_conversion_drop_needs_a_reliable_comparison():
    before = metrics(session_conversion_rate=10.0)
    drop = metrics(session_conversion_rate=6.0)
    assert 'conversion_drop' in rules(build_suggestions(ctx(metrics=drop, previous=before)))
    assert 'conversion_drop' not in rules(build_suggestions(ctx(metrics=metrics(session_conversion_rate=8.0), previous=before)))
    assert 'conversion_drop' not in rules(build_suggestions(ctx(metrics=drop, previous={**before, 'reliable': False})))
    assert 'conversion_drop' not in rules(build_suggestions(ctx(metrics=drop, previous=None)))


def test_suggestions_are_ordered_by_severity_and_every_item_has_evidence_and_an_action():
    down = {'latest': {'status': 'offline', 'http_status': 500, 'duration_ms': 100}, 'timeline': [{'status': 'offline'}]}
    result = build_suggestions(ctx(health=down, candidate_terms=[TERM], metrics=metrics(session_conversion_rate=5.0), previous=metrics(session_conversion_rate=10.0)))
    order = [item['severity'] for item in result['suggestions']]
    assert order == sorted(order, key={'high': 0, 'medium': 1, 'low': 2}.get)
    ids = [item['id'] for item in result['suggestions']]
    assert len(ids) == len(set(ids))
    assert all(item['evidence'] and item['action'] and item['anchor'] for item in result['suggestions'])


def test_the_input_is_not_mutated():
    data = ctx(candidate_terms=[TERM])
    snapshot = copy.deepcopy(data)
    build_suggestions(data)
    assert data == snapshot


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = 'test'
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    pages.register(bp)
    app.register_blueprint(bp)
    http = app.test_client()
    with http.session_transaction() as session:
        session['user_id'] = 1
    return http


def test_endpoint_wires_paid_origin_negatives_and_health_into_the_rules(client):
    from tests.test_reports_pages import fake_rows, SITE
    base = fake_rows()

    def rows(sql, params=()):
        if 'cadu_reports_gads_negative_keywords' in sql and 'to_regclass' not in sql:
            return [{'account_id': 5, 'level': 'campaign', 'campaign_external_id': '111', 'ad_group_external_id': None,
                     'attached_campaign_ids': [], 'keyword_text': 'barato', 'match_type': 'BROAD'}]
        if 'FROM cadu_reports_source_runs' in sql:
            return [{'id': 5}]
        if 'AS term_hash' in sql or 'HAVING SUM(t.clicks)' in sql:
            return [{**TERM, 'conversions': 0}, {**TERM, 'term_hash': 'h9', 'search_term': 'tênis barato', 'conversions': 0}]
        return base(sql, params)

    with mock.patch.object(pages, '_rows', rows), mock.patch.object(pages, '_selection', return_value={'client_id': 7, 'role': 'admin'}):
        body = client.get(f'/connect/api/v2/reports/pages/suggestions?site_id={SITE}&path=/LP/Verao/&days=30').get_json()
    terms = [item['evidence'][0]['value'] for item in body['suggestions'] if item['rule'] == 'negative_candidate']
    assert terms == ['tênis grátis'], 'o termo já coberto pela negativa "barato" não é sugerido'
    assert body['page']['path'] == '/lp/verao' and len(body['rules']) == len(RULES)
