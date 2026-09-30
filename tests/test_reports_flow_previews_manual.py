from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_flow_previews
from aicentralv2.services import integration_credentials


def test_previews_only_schedule_selected_page_after_explicit_request(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    blueprint = Blueprint('flow_previews_manual', __name__)
    reports_flow_previews.register(blueprint)
    app.register_blueprint(blueprint)
    config = {'nodes': [
        {'id': 'first', 'type': 'page', 'path': '/first'},
        {'id': 'second', 'type': 'page', 'path': '/second'},
    ]}
    flow = {'site_id': 'site', 'config': config, 'active_config': config,
            'allowed_host': 'example.com', 'revoked_at': None}
    scheduled = []
    monkeypatch.setattr(reports_flow_previews, '_selection', lambda: {'client_id': 7})
    monkeypatch.setattr(reports_flow_previews, '_flow_row', lambda *_: flow)
    monkeypatch.setattr(reports_flow_previews, '_write_guard', lambda *_: None)
    monkeypatch.setattr(reports_flow_previews, '_root', lambda: tmp_path)
    monkeypatch.setattr(reports_flow_previews, '_schedule', lambda *args, **kwargs: scheduled.append(args[2]) or True)
    monkeypatch.setattr(integration_credentials, 'resolve_firecrawl_api_key', lambda: 'test-key')
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    endpoint = '/api/v2/reports/flow/flows/flow/previews?client_id=7'

    assert client.get(endpoint).status_code == 200
    assert scheduled == []
    assert client.post(endpoint, json={}).status_code == 400
    assert scheduled == []
    assert client.post(endpoint, json={'node_id': 'first'}).status_code == 200
    assert scheduled == ['https://example.com/first']
    assert client.get(endpoint).status_code == 200
    assert scheduled == ['https://example.com/first']
