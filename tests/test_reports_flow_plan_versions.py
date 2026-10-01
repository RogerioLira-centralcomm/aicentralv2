import json

from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_flow

PLAN = {'nodes': [{'id': 'lp', 'type': 'page', 'title': 'Oferta', 'status': 'planned'}], 'edges': []}


class FakeDb:
    commits = 0

    def commit(self):
        FakeDb.commits += 1


def _client(monkeypatch, draft, ready=True):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    blueprint = Blueprint('flow_plan', __name__)
    reports_flow.register(blueprint)
    app.register_blueprint(blueprint)
    calls = []

    def rows(sql, params=()):
        calls.append((sql, params))
        if 'to_regclass' in sql:
            return [{'ready': ready}]
        if 'INSERT INTO cadu_reports_flow_plan_versions' in sql:
            return [{'revision': params[2], 'name': params[3], 'note': params[5], 'created_by': params[6], 'created_at': '2026-10-01T10:00:00'}]
        if 'FROM cadu_reports_flow_plan_versions' in sql:
            return [{'revision': 4, 'name': 'Plano', 'note': 'Primeira versão', 'created_by': 1, 'created_at': '2026-10-01T10:00:00'}]
        raise AssertionError(sql)

    monkeypatch.setattr(reports_flow, '_rows', rows)
    monkeypatch.setattr(reports_flow, 'get_db', lambda: FakeDb())
    monkeypatch.setattr(reports_flow, '_selection', lambda *_: {'client_id': 7})
    monkeypatch.setattr(reports_flow, '_write_guard', lambda *_: None)
    monkeypatch.setattr(reports_flow, '_flow_row', lambda *_: {'id': 'flow'})
    monkeypatch.setattr(reports_flow, 'lock_flow', lambda *_: {'id': 'flow', 'name': 'Plano', 'draft_config': draft, 'draft_revision': 4})
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    return client, calls


def test_publishing_a_plan_snapshots_the_draft_without_touching_measurement(monkeypatch):
    client, calls = _client(monkeypatch, PLAN)
    response = client.post('/api/v2/reports/flow/flows/flow/plan-versions', json={'expected_revision': 4, 'note': '  Para   aprovação '})
    assert response.status_code == 201
    assert response.json['version']['revision'] == 4
    assert response.json['version']['note'] == 'Para aprovação'
    insert = next(params for sql, params in calls if 'INSERT INTO cadu_reports_flow_plan_versions' in sql)
    assert json.loads(insert[4]) == PLAN
    sql_text = ' '.join(sql for sql, _ in calls)
    assert 'cadu_reports_flow_registry' not in sql_text and 'cadu_reports_flow_steps' not in sql_text


def test_an_empty_plan_cannot_be_published(monkeypatch):
    client, _ = _client(monkeypatch, {'nodes': [], 'edges': []})
    response = client.post('/api/v2/reports/flow/flows/flow/plan-versions', json={'expected_revision': 4})
    assert response.status_code == 422


def test_plan_publication_needs_the_migration(monkeypatch):
    client, _ = _client(monkeypatch, PLAN, ready=False)
    assert client.post('/api/v2/reports/flow/flows/flow/plan-versions', json={'expected_revision': 4}).status_code == 503
    listing = client.get('/api/v2/reports/flow/flows/flow/plan-versions')
    assert listing.json == {'versions': [], 'ready': False}


def test_plan_versions_are_listed_newest_first(monkeypatch):
    client, calls = _client(monkeypatch, PLAN)
    listing = client.get('/api/v2/reports/flow/flows/flow/plan-versions')
    assert listing.json['ready'] is True
    assert listing.json['versions'][0]['note'] == 'Primeira versão'
    assert any('ORDER BY revision DESC' in sql for sql, _ in calls)
