import json
import uuid

from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_flow, reports_flow_previews, reports_flow_probe, reports_supertag

FLOW_ID = str(uuid.uuid4())
PLAN = {'nodes': [{'id': 'lp', 'type': 'page', 'title': 'Oferta', 'status': 'planned', 'x': 0, 'y': 0}], 'edges': []}


class FakeDb:
    def commit(self):
        pass


def _client(monkeypatch, rows):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    blueprint = Blueprint('flow_plan_only', __name__)
    reports_flow.register(blueprint)
    reports_flow_previews.register(blueprint)
    reports_flow_probe.register(blueprint)
    app.register_blueprint(blueprint)
    calls = []

    def recorder(sql, params=()):
        calls.append((sql, params))
        return rows(sql, params)

    monkeypatch.setattr(reports_flow, '_rows', recorder)
    monkeypatch.setattr(reports_flow, 'get_db', lambda: FakeDb())
    monkeypatch.setattr(reports_flow, '_selection', lambda *_: {'client_id': 7})
    monkeypatch.setattr(reports_flow, '_write_guard', lambda *_: None)
    monkeypatch.setattr(reports_flow, '_new_flow_code', lambda: 'CF_PLANO1')
    monkeypatch.setattr(reports_flow, '_client_tag_urls', lambda *_: {})
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    return client, calls


def test_a_plan_is_created_without_site_tag_or_super_tag(monkeypatch):
    def rows(sql, params):
        assert 'cadu_reports_site_tags' not in sql and 'supertag' not in sql
        if 'INSERT INTO cadu_reports_flow_registry' in sql:
            return [{'id': params[0], 'site_id': None, 'tag_id': None, 'flow_code': params[2], 'name': params[3], 'status': 'draft',
                     'config': json.loads(params[4]), 'draft_revision': 1, 'published_revision': None}]
        raise AssertionError(sql)
    client, calls = _client(monkeypatch, rows)
    response = client.post('/api/v2/reports/flow/flows', json={'name': 'Plano Black Friday', 'plan_only': True, 'config': PLAN})
    assert response.status_code == 201
    assert response.json['flow']['allowed_host'] == ''
    assert response.json['flow']['tag_id'] is None and response.json['tag'] is None
    insert = next(sql for sql, _ in calls if 'INSERT INTO cadu_reports_flow_registry' in sql)
    assert 'NULL,%s,%s::jsonb,%s,NULL' in insert


def test_a_plan_without_site_cannot_carry_measured_steps(monkeypatch):
    client, _ = _client(monkeypatch, lambda sql, params: [])
    live = {'nodes': [{'id': 'home', 'type': 'page', 'title': 'Home', 'path': '/', 'x': 0, 'y': 0}], 'edges': []}
    assert client.post('/api/v2/reports/flow/flows', json={'name': 'Plano', 'plan_only': True, 'config': live}).status_code == 400


def test_site_bound_actions_explain_that_the_plan_needs_a_site(monkeypatch):
    client, calls = _client(monkeypatch, lambda sql, params: [{'tag_id': None}] if 'SELECT tag_id' in sql else [])
    for method, path in (('get', 'discoveries'), ('post', 'discover'), ('post', 'publish'), ('post', 'probe'), ('post', 'previews')):
        response = getattr(client, method)(f'/api/v2/reports/flow/flows/{FLOW_ID}/{path}', json={} if method == 'post' else None)
        assert response.status_code == 409, path
        assert response.json['error'] == 'site_required', path


def test_the_guard_leaves_flows_with_site_and_plan_actions_alone(monkeypatch):
    def rows(sql, params):
        if 'SELECT tag_id' in sql:
            raise AssertionError('plan versions do not need a site')
        if 'to_regclass' in sql:
            return [{'ready': True}]
        return []
    monkeypatch.setattr(reports_flow, '_flow_row', lambda *_: {'id': FLOW_ID})
    client, _ = _client(monkeypatch, rows)
    assert client.get(f'/api/v2/reports/flow/flows/{FLOW_ID}/plan-versions').status_code == 200


def test_connecting_a_site_creates_the_tag_and_links_the_installation(monkeypatch):
    monkeypatch.setattr(reports_supertag, 'ensure_supertag_site', lambda selected, host, name: ({'id': 'site-1', 'allowed_host': host}, True))

    def rows(sql, params):
        if 'FOR UPDATE' in sql:
            return [{'id': FLOW_ID, 'name': 'Plano', 'tag_id': None, 'draft_config': PLAN}]
        if 'INSERT INTO cadu_reports_site_tags' in sql:
            return [{'id': 'tag-1', 'label': params[2], 'allowed_host': params[3], 'public_key': 'k', 'created_at': None, 'revoked_at': None, 'tag_kind': 'flow'}]
        if 'UPDATE cadu_reports_flow_registry SET tag_id' in sql:
            return [{'id': FLOW_ID, 'site_id': params[1], 'tag_id': params[0], 'updated_at': None}]
        raise AssertionError(sql)
    client, calls = _client(monkeypatch, rows)
    response = client.post(f'/api/v2/reports/flow/flows/{FLOW_ID}/site', json={'allowed_host': 'https://www.Exemplo.com.br/'})
    assert response.status_code == 200
    assert response.json['flow'] == {'id': FLOW_ID, 'site_id': 'site-1', 'tag_id': 'tag-1', 'updated_at': None, 'allowed_host': 'www.exemplo.com.br'}


def test_a_flow_that_already_has_a_site_is_not_reconnected(monkeypatch):
    client, _ = _client(monkeypatch, lambda sql, params: [{'id': FLOW_ID, 'name': 'Plano', 'tag_id': 'tag-1', 'draft_config': PLAN}])
    assert client.post(f'/api/v2/reports/flow/flows/{FLOW_ID}/site', json={'allowed_host': 'exemplo.com.br'}).status_code == 409
