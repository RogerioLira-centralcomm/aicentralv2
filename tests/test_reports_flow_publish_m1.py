from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_flow


def _client(monkeypatch, config):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    blueprint = Blueprint('flow_m1', __name__)
    reports_flow.register(blueprint)
    app.register_blueprint(blueprint)
    monkeypatch.setattr(reports_flow, '_selection', lambda *_: {'client_id': 7})
    monkeypatch.setattr(reports_flow, '_write_guard', lambda *_: None)
    monkeypatch.setattr(reports_flow, 'lock_flow', lambda *_: None)
    monkeypatch.setattr(reports_flow, '_flow_row', lambda *_: {'id': 'flow', 'config': config, 'allowed_host': 'example.com'})
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    return client


def test_direct_publish_with_blocking_issue_returns_structured_422(monkeypatch):
    config = {'nodes': [{'id': 'entry', 'type': 'page', 'path': '/'}], 'edges': []}
    client = _client(monkeypatch, config)
    response = client.post('/api/v2/reports/flow/flows/flow/publish', json={'expected_revision': 1})
    assert response.status_code == 422
    assert response.json['error'] == 'pendencias_bloqueantes'
    assert any(item['code'] == 'no_conversion' for item in response.json['items'])


def test_empty_flow_reports_missing_measured_step(monkeypatch):
    client = _client(monkeypatch, {'nodes': [], 'edges': []})
    response = client.post('/api/v2/reports/flow/flows/flow/publish', json={'expected_revision': 1})
    assert response.status_code == 422
    assert any(item['code'] == 'no_measured_steps' for item in response.json['items'])
