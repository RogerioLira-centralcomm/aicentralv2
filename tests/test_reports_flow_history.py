"""Flow metrics across publications: events of older publications are read with the drawing on screen.

The SQL part runs in a throwaway schema and is skipped unless CX_TEST_DATABASE_URL points to a database made for tests.
"""
import datetime
import json
import os
import uuid

import psycopg
import pytest

from aicentralv2.cadu_connect.reports_flow_history import matched_events_cte, node_match_json, publications_in_period

_REAL_CONNECT = psycopg.connect   # the suite blocks psycopg.connect for every test; this one was captured at import
NOW = datetime.datetime.now(datetime.timezone.utc)
TAG, CLIENT = str(uuid.uuid4()), 7

STUBS = '''
CREATE TABLE cadu_reports_campaigns(id BIGINT PRIMARY KEY, client_id BIGINT, account_id BIGINT);
CREATE TABLE cadu_reports_accounts(id BIGINT PRIMARY KEY, client_id BIGINT, platform TEXT);
CREATE TABLE cadu_reports_flow_events(id BIGSERIAL PRIMARY KEY, client_id BIGINT, tag_id UUID, session_id UUID,
    event_kind TEXT, event_name TEXT, page_host TEXT, page_path TEXT, campaign_id BIGINT, duration_ms INT,
    occurred_at TIMESTAMPTZ, flow_revision INT);
'''

# v67 drew /blog as a step and turned /obrigado into a conversion; v65 had neither.
CURRENT = {'nodes': [
    {'id': 'home', 'type': 'page', 'path': '/'},
    {'id': 'blog', 'type': 'page', 'path': '/blog/'},
    {'id': 'contato', 'type': 'page', 'path': '/contato', 'host': 'www.site.com'},
    {'id': 'obrigado', 'type': 'conversion', 'path': '/obrigado'},
    {'id': 'zap', 'type': 'whatsapp', 'path': '/contato'},
    {'id': 'futura', 'type': 'page', 'path': '/em-breve', 'status': 'planned'},
    {'id': 'nota', 'type': 'note'},
]}


def test_node_json_keeps_only_measured_nodes_with_an_address():
    rows = json.loads(node_match_json(CURRENT))
    assert [row['node_id'] for row in rows] == ['home', 'blog', 'contato', 'obrigado', 'zap']
    assert rows[2]['host'] == 'www.site.com' and rows[0]['host'] is None
    assert node_match_json(None) == '[]'


def test_publications_are_listed_newest_first_and_mark_the_current_one():
    rows = [{'flow_revision': 65, 'events': 10, 'first_event_at': NOW, 'last_event_at': NOW},
            {'flow_revision': 67, 'events': 3, 'first_event_at': None, 'last_event_at': None},
            {'flow_revision': None, 'events': 1}]
    items = publications_in_period(rows, 67)
    assert [(item['revision'], item['current']) for item in items] == [(67, True), (65, False)]
    assert items[1]['first_event_at'] == NOW.isoformat()


@pytest.fixture
def db():
    url = os.getenv('CX_TEST_DATABASE_URL')
    if not url:
        pytest.skip('CX_TEST_DATABASE_URL não definida')
    from psycopg.rows import dict_row
    try:
        conn = _REAL_CONNECT(url, row_factory=dict_row, connect_timeout=3, autocommit=True)
    except Exception as failure:
        pytest.skip(f'PostgreSQL indisponível: {type(failure).__name__}')
    schema = f'flow_history_{uuid.uuid4().hex[:8]}'
    cur = conn.cursor()
    cur.execute(f'CREATE SCHEMA {schema}')
    cur.execute(f'SET search_path TO {schema}')
    cur.execute(STUBS)
    yield cur
    cur.execute(f'DROP SCHEMA {schema} CASCADE')
    conn.close()


def _event(cur, revision, kind, path, host='site.com', name=None, session=None, minutes=0):
    cur.execute('''INSERT INTO cadu_reports_flow_events(client_id,tag_id,session_id,event_kind,event_name,page_host,page_path,occurred_at,flow_revision)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (CLIENT, TAG, session or uuid.uuid4(), kind, name, host, path, NOW - datetime.timedelta(minutes=minutes), revision))
    return cur.fetchone()['id']


def _mapped(cur, config, pinned=None):
    where = 'e.client_id=%s AND e.tag_id=%s' + (' AND e.flow_revision=%s' if pinned else '')
    sql = matched_events_cte(where, 'e.id,e.event_kind,e.event_name,e.page_host,e.page_path,e.flow_revision') + \
        ' SELECT id,node_id FROM mapped'
    cur.execute(sql, (node_match_json(config), CLIENT, TAG, *([pinned] if pinned else [])))
    return {row['id']: row['node_id'] for row in cur.fetchall()}


def test_older_publications_are_read_with_the_current_drawing(db):
    blog = _event(db, 65, 'page_view', '/Blog')               # not drawn in v65; trailing slash and case differ
    thanks = _event(db, 65, 'page_view', '/obrigado/')        # a plain page in v65, a conversion now
    stored = _event(db, 66, 'conversion', '/obrigado')         # stored as conversion by a publication that had the step
    contact = _event(db, 67, 'page_view', '/contato', host='site.com')   # node host has www.
    zap = _event(db, 67, 'whatsapp_click', '/contato')
    leave = _event(db, 65, 'page_leave', '/')
    other = _event(db, 67, 'page_view', '/sobre')
    mapped = _mapped(db, CURRENT)
    assert mapped[blog] == 'blog' and mapped[thanks] == 'obrigado' and mapped[stored] == 'obrigado'
    assert mapped[contact] == 'contato' and mapped[zap] == 'zap' and mapped[leave] == 'home'
    assert mapped[other] is None


def test_a_conversion_rule_outranks_the_page_at_the_same_address(db):
    config = {'nodes': [{'id': 'p', 'type': 'page', 'path': '/obrigado'},
                        {'id': 'c', 'type': 'conversion', 'path': '/obrigado'}]}
    view = _event(db, 67, 'page_view', '/obrigado')
    assert _mapped(db, config)[view] == 'c'


def test_named_conversion_matches_only_its_event(db):
    config = {'nodes': [{'id': 'lead', 'type': 'conversion', 'path': '/contato', 'event_name': 'lead'}]}
    named = _event(db, 67, 'conversion', '/contato', name='lead')
    other = _event(db, 67, 'conversion', '/contato', name='compra')
    view = _event(db, 67, 'page_view', '/contato')
    mapped = _mapped(db, config)
    assert mapped[named] == 'lead' and mapped[other] is None and mapped[view] is None


def test_a_chosen_publication_reads_only_its_own_events(db):
    old = _event(db, 65, 'page_view', '/')
    new = _event(db, 67, 'page_view', '/')
    mapped = _mapped(db, CURRENT, pinned=67)
    assert new in mapped and old not in mapped
