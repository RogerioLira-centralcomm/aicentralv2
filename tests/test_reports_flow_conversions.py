"""Conversion journeys and page influence of a flow.

The endpoint part runs in a throwaway schema and is skipped unless CX_TEST_DATABASE_URL points to a database made for tests.
"""
import datetime
import json
import os
import uuid
from unittest import mock

import psycopg
import pytest
from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_flow_conversions as conv

_REAL_CONNECT = psycopg.connect   # the suite blocks psycopg.connect for every test; this one was captured at import
NOW = datetime.datetime.now(datetime.timezone.utc)
NODES = {'home': {'id': 'home', 'type': 'page', 'title': 'Home', 'path': '/'},
         'contato': {'id': 'contato', 'type': 'page', 'title': 'Contato', 'path': '/contato'},
         'ok': {'id': 'ok', 'type': 'conversion', 'title': 'Conversão', 'path': '/obrigado'}}


def _ev(event_id, kind, path, node=None, duration=None):
    return {'id': event_id, 'event_kind': kind, 'page_path': path, 'node_id': node, 'duration_ms': duration}


def test_steps_keep_off_flow_pages_collapse_repeats_and_stop_at_the_conversion():
    events = [_ev(1, 'page_view', '/', 'home'), _ev(2, 'page_leave', '/', duration=4200), _ev(3, 'page_view', '/', 'home'),
              _ev(4, 'page_view', '/Blog/CTV/'), _ev(5, 'page_view', '/contato', 'contato'),
              _ev(6, 'form_submit', '/contato'), _ev(7, 'page_view', '/obrigado', 'ok'), _ev(8, 'page_view', '/depois')]
    steps = conv.collapse_steps(events, NODES, {'/blog/ctv': 'Blog CTV'}, 7)
    assert [(step['path'], step['kind'], step['off_flow']) for step in steps] == [
        ('/', 'page', False), ('/blog/ctv', 'page', True), ('/contato', 'page', False),
        ('/contato', 'form', True), ('/obrigado', 'page', False)]
    assert steps[0]['seconds'] == 4 and steps[1]['title'] == 'Blog CTV' and steps[-1]['goal'] is True


def test_long_journeys_keep_both_ends():
    events = [_ev(index, 'page_view', f'/p{index}') for index in range(40)]
    steps = conv.collapse_steps(events, NODES, {}, 39)
    assert len(steps) == 30 and steps[10]['kind'] == 'gap' and steps[10]['hidden'] == 11
    assert steps[0]['path'] == '/p0' and steps[-1]['path'] == '/p39' and steps[-1]['goal']


def test_origins_separate_first_contact_last_non_direct_and_session():
    day = datetime.timedelta(days=1)
    prior = [{'started_at': NOW - 3 * day, 'platform': 'meta'}, {'started_at': NOW - day, 'platform': 'organic'}]
    assert conv.journey_origins('direct', prior) == {'first': 'meta', 'last_non_direct': 'organic', 'session': 'direct'}
    assert conv.journey_origins('direct', []) == {'first': 'direct', 'last_non_direct': 'direct', 'session': 'direct'}


def test_top_paths_group_off_flow_pages_by_section_and_need_two_conversions():
    def journey(*paths):
        return {'steps': [{'kind': 'page', 'path': path, 'off_flow': path.startswith('/blog'), 'title': path} for path in paths]}
    paths = conv.top_paths([journey('/', '/blog/a', '/obrigado'), journey('/', '/blog/b', '/blog/c', '/obrigado'), journey('/', '/obrigado')])
    assert paths == [{'steps': ['/', '/blog/*', '/obrigado'], 'conversions': 2}]


def test_influence_counts_each_page_once_per_conversion_and_withholds_rates_on_small_samples():
    def step(path, goal=False):
        return {'kind': 'page', 'path': path, 'goal': goal}
    journeys = [{'steps': [step('/'), step('/blog'), step('/blog'), step('/obrigado', True)], 'prior_sessions': [{'pages': ['/cases']}]},
                {'steps': [step('/blog'), step('/obrigado', True)], 'prior_sessions': [{'pages': ['/blog']}]}]
    rows = {row['path']: row for row in conv.page_influence(journeys, {'/blog': 40, '/': 30, '/cases': 5}, 200, {'/'}, {'/': NODES['home']}, {})}
    assert rows['/blog']['assisted'] == 2 and rows['/blog']['assisted_prior'] == 0 and rows['/blog']['share'] == 100.0
    assert rows['/cases']['assisted'] == 0 and rows['/cases']['assisted_prior'] == 1
    assert rows['/']['in_flow'] and rows['/']['position'] == 'start' and '/obrigado' not in rows
    assert rows['/blog']['rate_with'] is None   # 2 conversions: below MIN_RATE_CONVERSIONS


def test_influence_compares_rates_with_enough_sample():
    journeys = [{'steps': [{'kind': 'page', 'path': '/blog'}, {'kind': 'page', 'path': '/obrigado', 'goal': True}], 'prior_sessions': []}
                for _ in range(10)]
    row = conv.page_influence(journeys, {'/blog': 50}, 250, set(), {}, {})[0]
    assert row['rate_with'] == 20.0 and row['rate_without'] == 0.0


def test_off_flow_group():
    assert conv.off_flow_group('/') == '/' and conv.off_flow_group('/Sobre/') == '/sobre'
    assert conv.off_flow_group('/blog/ctv/x') == '/blog/*'


# --- endpoints against PostgreSQL -------------------------------------------------------------------------------

STUBS = '''
CREATE TABLE cadu_reports_campaigns(id BIGINT PRIMARY KEY, client_id BIGINT, account_id BIGINT);
CREATE TABLE cadu_reports_accounts(id BIGINT PRIMARY KEY, client_id BIGINT, platform TEXT);
CREATE TABLE cadu_reports_site_pages(client_id BIGINT, host TEXT, path TEXT, name TEXT, title TEXT);
CREATE TABLE cadu_reports_flow_events(id BIGSERIAL PRIMARY KEY, client_id BIGINT, tag_id UUID, session_id UUID, visitor_id UUID,
    event_kind TEXT, event_name TEXT, page_host TEXT, page_path TEXT, campaign_id BIGINT, duration_ms INT, utm_source TEXT,
    utm_campaign TEXT, click_id TEXT, referrer_host TEXT, step_id BIGINT, occurred_at TIMESTAMPTZ, flow_revision INT);
'''
TAG, FLOW = str(uuid.uuid4()), str(uuid.uuid4())
CONFIG = {'nodes': [{'id': 'src', 'type': 'source', 'source': 'google'}, *NODES.values()], 'edges': []}


@pytest.fixture
def client():
    url = os.getenv('CX_TEST_DATABASE_URL')
    if not url:
        pytest.skip('CX_TEST_DATABASE_URL não definida')
    from psycopg.rows import dict_row
    try:
        conn = _REAL_CONNECT(url, row_factory=dict_row, connect_timeout=3, autocommit=True)
    except Exception as failure:
        pytest.skip(f'PostgreSQL indisponível: {type(failure).__name__}')
    schema = f'flow_conv_{uuid.uuid4().hex[:8]}'
    cur = conn.cursor()
    cur.execute(f'CREATE SCHEMA {schema}')
    cur.execute(f'SET search_path TO {schema}')
    cur.execute(STUBS)
    cur.execute("INSERT INTO cadu_reports_site_pages VALUES (7,'site.com','/blog/ctv','Blog CTV',NULL)")

    def event(session, kind, path, minutes, revision=67, visitor=None, click=None):
        cur.execute('''INSERT INTO cadu_reports_flow_events(client_id,tag_id,session_id,visitor_id,event_kind,page_host,page_path,click_id,occurred_at,flow_revision)
            VALUES (7,%s,%s,%s,%s,'site.com',%s,%s,%s,%s)''',
            (TAG, session, visitor or session, kind, path, click, NOW - datetime.timedelta(minutes=minutes), revision))

    person, a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    event(a, 'page_view', '/', 3000, revision=65, visitor=person, click='IwAR123')          # earlier visit from Meta
    event(a, 'page_view', '/cases', 2999, revision=65, visitor=person)
    event(b, 'page_view', '/', 60, visitor=person)                                          # returns direct and converts
    event(b, 'page_view', '/blog/ctv', 59, visitor=person)
    event(b, 'page_view', '/contato', 58, visitor=person)
    event(b, 'page_view', '/obrigado', 57, visitor=person)
    event(c, 'page_view', '/blog/dooh', 30, click='Cj0KCQ')                                 # Google Ads click without UTM
    event(c, 'page_view', '/obrigado', 29)
    event(d, 'page_view', '/', 10)                                                          # did not convert
    flow = {'id': FLOW, 'client_id': 7, 'tag_id': TAG, 'status': 'published', 'published_revision': 67,
            'active_config': CONFIG, 'allowed_host': 'site.com', 'revoked_at': None}

    def rows(sql, params=()):
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []

    app, bp = Flask(__name__), Blueprint('flow_conversions_test', __name__)
    with mock.patch.object(conv, 'login_required_api', lambda view: view):
        conv.register(bp)
    app.register_blueprint(bp)
    from aicentralv2.cadu_connect import reports_flow
    with mock.patch.object(conv, '_rows', rows), mock.patch.object(conv, '_selection', lambda *a, **k: {'client_id': 7}), \
            mock.patch.object(reports_flow, '_flow_row', lambda *a, **k: dict(flow)):
        yield app.test_client()
    cur.execute(f'DROP SCHEMA {schema} CASCADE')
    conn.close()


def test_conversions_list_paths_prior_visits_and_origins(client):
    data = client.get(f'/api/v2/reports/flow/flows/{FLOW}/conversions?days=7').get_json()
    assert data['status'] == 'ready' and data['coverage'] == {'conversions': 2, 'identified': 1, 'complete': True}
    returning, paid = data['journeys'][1], data['journeys'][0]
    assert [step['path'] for step in returning['steps']] == ['/', '/blog/ctv', '/contato', '/obrigado']
    assert returning['steps'][1] == {'path': '/blog/ctv', 'kind': 'page', 'title': 'Blog CTV', 'node_id': None, 'off_flow': True}
    assert returning['origin'] == {'first': 'meta', 'last_non_direct': 'meta', 'session': 'direct'}
    assert returning['prior_sessions'][0]['pages'] == ['/', '/cases']
    assert paid['origin']['session'] == 'google' and not paid['identified']
    assert data['origin_labels']['google'] == 'Google Ads'


def test_influence_ranks_off_flow_pages_and_lists_drawn_pages_no_conversion_used(client):
    data = client.get(f'/api/v2/reports/flow/flows/{FLOW}/influence?days=7').get_json()
    assert data['conversions'] == 2 and data['sessions'] == 4 and not data['compare_rates']
    assert data['off_flow'] == []   # each off-flow page took part in one conversion only, below MIN_ASSISTED
    pages = {row['path']: row for row in data['pages']}
    assert pages['/']['assisted'] == 1 and pages['/contato']['assisted'] == 1
    with mock.patch.object(conv, 'MIN_ASSISTED', 1):
        data = client.get(f'/api/v2/reports/flow/flows/{FLOW}/influence?days=7').get_json()
    off = {row['path']: row for row in data['off_flow']}
    assert set(off) == {'/blog/ctv', '/blog/dooh', '/cases'}
    assert off['/blog/ctv']['after_node_id'] == 'home' and off['/cases']['assisted_prior'] == 1


def test_a_capped_read_never_compares_rates():
    journeys = [{'steps': [{'kind': 'page', 'path': '/blog'}, {'kind': 'page', 'path': '/obrigado', 'goal': True}], 'prior_sessions': []}
                for _ in range(10)]
    row = conv.page_influence(journeys, {'/blog': 50}, 250, set(), {}, {}, compare=False)[0]
    assert row['rate_with'] is None and row['rate_without'] is None


def test_live_origin_reads_a_paid_click_like_the_journey():
    from aicentralv2.cadu_connect.reports_flow_live import _event_origin
    from aicentralv2.cadu_connect.reports_flow_metrics import origin_platform
    assert origin_platform(_event_origin({'click_id': 'Cj0KCQ', 'referrer_host': 'site.com'})) == 'google'
    assert origin_platform(_event_origin({'click_id': 'IwAR1'})) == 'meta'
    assert _event_origin({'utm_source': 'Meta', 'click_id': 'Cj0'}) == 'utm:meta|'


def test_a_visitor_who_converted_before_shows_that_visit(client):
    # The fixture's returning person converts on the earlier visit too: it must appear as an earlier visit.
    from aicentralv2.cadu_connect import reports_flow_conversions as module
    rows = module._rows
    first = rows("SELECT session_id,visitor_id FROM cadu_reports_flow_events WHERE page_path='/cases'")[0]
    rows('''INSERT INTO cadu_reports_flow_events(client_id,tag_id,session_id,visitor_id,event_kind,page_host,page_path,occurred_at,flow_revision)
        VALUES (7,%s,%s,%s,'page_view','site.com','/obrigado',%s,65)''', (TAG, first['session_id'], first['visitor_id'], NOW - datetime.timedelta(minutes=2998)))
    rows('''INSERT INTO cadu_reports_flow_events(client_id,tag_id,session_id,event_kind,page_host,page_path,occurred_at,flow_revision)
        VALUES (7,%s,%s,'page_leave','site.com','/obrigado',%s,67)''', (TAG, uuid.uuid4(), NOW - datetime.timedelta(minutes=5)))
    data = client.get(f'/api/v2/reports/flow/flows/{FLOW}/conversions?days=7').get_json()
    assert data['coverage']['conversions'] == 3, 'a lone page_leave on the goal page is not a conversion'
    latest = next(journey for journey in data['journeys'] if journey['steps'][0]['path'] == '/' and len(journey['steps']) == 4)
    assert [visit['pages'] for visit in latest['prior_sessions']] == [['/', '/cases', '/obrigado']]
