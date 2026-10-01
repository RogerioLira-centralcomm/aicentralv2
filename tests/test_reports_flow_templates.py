import json
import uuid

from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_flow_templates
from aicentralv2.cadu_connect.reports_flow_templates import template_config

PLAN = {'schema_version': 3, 'tags': ['Leads'], 'viewport': {'zoom': 1}, 'blueprintGoalConfirmed': True,
        'settings': {'publication_note': 'v2 para o cliente', 'grid': True}, 'nodes': [
    {'id': 'meta', 'type': 'source', 'kind': 'traffic.meta', 'title': 'Meta', 'x': 0, 'y': 0, 'forecast': {'visits': 1000, 'cost': 500},
     'segment': {'name': 'Remarketing', 'kind': 'remarketing'},
     'media': {'objective': 'leads', 'creatives': [{'id': 'c1', 'name': 'Vídeo', 'format': 'video', 'status': 'aprovado'}],
               'setup': [{'id': 's1', 'text': 'Pixel', 'done': True}], 'utm': {'source': 'facebook'}}},
    {'id': 'lp', 'type': 'page', 'kind': 'page.landing', 'title': 'Oferta', 'x': 400, 'y': 0, 'path': '/oferta', 'host': 'cliente.com',
     'status': 'live', 'campaign_id': 9, 'evidence': 'Página encontrada', 'spec': {'goal': 'Converter', 'owner': 'Ana', 'due_date': '2026-10-10'}},
    {'id': 'lead', 'type': 'conversion', 'kind': 'conversion.lead', 'title': 'Lead', 'x': 800, 'y': 0, 'forecast': {'value': 90}},
    {'id': 'nota', 'type': 'note', 'kind': 'annotation.note', 'title': 'Combinados', 'x': 0, 'y': 300, 'checklist': [{'text': 'Aprovar', 'done': True}]},
], 'edges': [{'id': 'e1', 'from': 'meta', 'to': 'lp', 'variant': 'direct', 'forecast': {'rate': 100}}]}


def test_a_template_keeps_the_plan_and_drops_campaign_facts():
    template = template_config(PLAN)
    meta, lp, lead, note = template['nodes']
    assert 'forecast' not in meta and meta['segment'] == {'name': 'Remarketing', 'kind': 'remarketing'}
    assert meta['media']['creatives'][0]['status'] == 'rascunho' and meta['media']['setup'][0]['done'] is False
    assert meta['media']['utm'] == {'source': 'facebook'}
    assert lp['status'] == 'planned' and lp['spec'] == {'goal': 'Converter'}
    assert not {'path', 'host', 'campaign_id', 'evidence'} & set(lp)
    assert lead['forecast'] == {'value': 90}
    assert note['checklist'] == [{'text': 'Aprovar', 'done': False}]
    assert template['edges'][0]['forecast'] == {'rate': 100}
    assert 'viewport' not in template and 'blueprintGoalConfirmed' not in template
    assert template['settings'] == {'grid': True} and template['tags'] == ['Leads']
    assert PLAN['nodes'][1]['path'] == '/oferta'


class FakeDb:
    def commit(self):
        pass


def _client(monkeypatch, rows):
    app = Flask(__name__)
    app.secret_key = 'test-only'
    blueprint = Blueprint('flow_templates', __name__)
    reports_flow_templates.register(blueprint)
    app.register_blueprint(blueprint)
    calls = []
    monkeypatch.setattr(reports_flow_templates, '_rows', lambda sql, params=(): calls.append((sql, params)) or rows(sql, params))
    monkeypatch.setattr(reports_flow_templates, 'get_db', lambda: FakeDb())
    monkeypatch.setattr(reports_flow_templates, '_selection', lambda *_: {'client_id': 7})
    monkeypatch.setattr(reports_flow_templates, '_write_guard', lambda *_: None)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    return client, calls


def test_saving_a_template_stores_the_clean_plan_for_the_client(monkeypatch):
    def rows(sql, params):
        if 'to_regclass' in sql:
            return [{'ready': True}]
        if 'INSERT INTO cadu_reports_flow_templates' in sql:
            return [{'id': params[0], 'name': params[2], 'description': params[3], 'sector': params[4], 'config': json.loads(params[5]), 'created_by': params[6], 'created_at': None}]
        raise AssertionError(sql)
    client, _ = _client(monkeypatch, rows)
    response = client.post('/api/v2/reports/flow/templates', json={'name': ' Leads  imobiliário ', 'sector': 'Imobiliário', 'config': PLAN})
    assert response.status_code == 201
    saved = response.json['template']
    assert saved['name'] == 'Leads imobiliário' and saved['sector'] == 'Imobiliário'
    assert all('path' not in node for node in saved['config']['nodes'])
    assert client.post('/api/v2/reports/flow/templates', json={'name': '', 'config': PLAN}).status_code == 400
    assert client.post('/api/v2/reports/flow/templates', json={'name': 'Vazio', 'config': {'nodes': [], 'edges': []}}).status_code == 422


def test_templates_are_scoped_to_the_client_and_need_the_migration(monkeypatch):
    client, calls = _client(monkeypatch, lambda sql, params: [{'ready': False}] if 'to_regclass' in sql else [])
    assert client.get('/api/v2/reports/flow/templates').json == {'templates': [], 'ready': False}
    assert client.post('/api/v2/reports/flow/templates', json={'name': 'X', 'config': PLAN}).status_code == 503
    client, calls = _client(monkeypatch, lambda sql, params: [{'ready': True}] if 'to_regclass' in sql else [])
    assert client.delete(f'/api/v2/reports/flow/templates/{uuid.uuid4()}').status_code == 404
    assert client.delete('/api/v2/reports/flow/templates/nao-e-uuid').status_code == 404
    assert any('client_id=%s' in sql and params[-1] == 7 for sql, params in calls if 'DELETE' in sql)
