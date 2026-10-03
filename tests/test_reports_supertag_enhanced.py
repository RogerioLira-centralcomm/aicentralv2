"""Enhanced measurement (GA4-like switches per site), the one-line snippet and gtag-style event parameters."""
import json
import uuid
from unittest import mock

import pytest
from flask import Blueprint, Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect import reports_supertag
from aicentralv2.cadu_connect import reports_supertag_leads as leads
from tests.test_reports_supertag import FakeDb, fake_rows, raw_event

SITE_ID = str(uuid.uuid4())
ALL_ON = {key: True for key in reports_supertag.ENHANCED_KEYS}


def site(config=None):
    return {'id': SITE_ID, 'client_id': 7, 'public_id': 'pub', 'allowed_host': 'example.test',
            'config': config or {}, 'config_version': 4}


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.config['SECRET_KEY'] = 'test-secret'
    flask_app.config['CONNECT_URL'] = 'https://reports.example.test'
    bp = Blueprint('reports', __name__, url_prefix='/connect')
    reports_supertag.register(bp)
    flask_app.register_blueprint(bp)
    leads._ready_tables.clear()
    return flask_app


# ---------------------------------------------------------------- config

@pytest.mark.parametrize('config', [{}, None, {'enhanced': None}, {'enhanced': 'x'}, {'enhanced': {}},
                                    {'visibility_enabled': False, 'audience_days': 90}])
def test_old_or_missing_configs_measure_everything(config):
    assert reports_supertag.enhanced_settings(config) == ALL_ON


def test_only_explicit_false_turns_a_switch_off():
    settings = reports_supertag.enhanced_settings({'enhanced': {'scroll': False, 'video': 0, 'outbound': None}})
    assert settings == {**ALL_ON, 'scroll': False}


@mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
def test_public_config_carries_the_resolved_switches(lookup, app):
    lookup.return_value = site({'enhanced': {'downloads': False}})
    body = app.test_client().get('/connect/public/supertag/v1/pub/config.json',
                                 headers={'Origin': 'https://example.test'}).get_json()
    assert body['enhanced'] == {**ALL_ON, 'downloads': False}
    lookup.return_value = site()
    old = app.test_client().get('/connect/public/supertag/v1/pub/config.json',
                                headers={'Origin': 'https://example.test'}).get_json()
    assert old['enhanced'] == ALL_ON


def _patch(app, payload, config=None):
    current = {'id': SITE_ID, 'label': 'Site', 'allowed_host': 'example.test', 'config': config or {}, 'config_version': 1}
    captured = {}

    def answer(sql, params=()):
        if 'FOR UPDATE' in sql:
            return [current]
        if sql.lstrip().startswith('UPDATE cadu_reports_supertag_sites'):
            captured['config'] = json.loads(params[2])
            return [{'id': SITE_ID, 'public_id': 'abc', 'label': 'Site', 'allowed_host': 'example.test', 'enabled': True,
                     'config': captured['config'], 'config_version': 2, 'created_at': None, 'updated_at': None,
                     'revoked_at': None}]
        return []
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    with mock.patch.object(reports_supertag, '_selection', return_value={'client_id': 7, 'role': 'admin'}), \
            mock.patch.object(reports_supertag, '_write_guard'), \
            mock.patch.object(reports_supertag, 'get_db', return_value=FakeDb()), \
            mock.patch.object(reports_supertag, '_rows', side_effect=answer):
        response = client.patch(f'/connect/api/v2/reports/supertag/sites/{SITE_ID}', json=payload)
    return response, captured


def test_saving_one_switch_keeps_the_others_resolved(app):
    response, captured = _patch(app, {'enhanced': {'scroll': False}}, config={'enhanced': {'video': False}})
    assert response.status_code == 200
    assert captured['config']['enhanced'] == {**ALL_ON, 'scroll': False, 'video': False}
    response, captured = _patch(app, {'enhanced': {'video': True}}, config={'enhanced': {'video': False}})
    assert captured['config']['enhanced']['video'] is True


@pytest.mark.parametrize('value', [{'scroll': 'no'}, {'unknown': False}, {}, [], 'off', {'forms': None}])
def test_invalid_switches_are_refused(value, app):
    response, captured = _patch(app, {'enhanced': value})
    assert response.status_code == 400 and not captured


# ---------------------------------------------------------------- snippet

def test_snippet_is_one_tag_with_only_the_site_id(app):
    with app.test_request_context('/'):
        snippet = reports_supertag._supertag_snippet({'public_id': 'abc123'})
    assert snippet.splitlines()[1] == '<script async src="https://reports.example.test/v1/supertag.js" data-cadu-site="abc123"></script>'
    assert 'data-cadu-config' not in snippet and len(snippet.splitlines()) == 3


# ---------------------------------------------------------------- new event kinds

def test_new_automatic_events_validate_without_leaking_urls_or_contacts():
    current = site()
    stored = reports_supertag._event(raw_event(kind='outbound_click', data={'link_host': 'Parceiro.com.br'}), current)
    assert json.loads(stored[10]) == {'link_host': 'parceiro.com.br'}
    stored = reports_supertag._event(raw_event(kind='file_download', data={'file_ext': 'pdf'}), current)
    assert json.loads(stored[10]) == {'file_ext': 'pdf'}
    stored = reports_supertag._event(raw_event(kind='contact_click', data={'channel': 'email'}), current)
    assert json.loads(stored[10]) == {'channel': 'email'}
    for data in ({'action': 'start'}, {'action': 'progress', 'percent': 50}, {'action': 'complete'}):
        assert json.loads(reports_supertag._event(raw_event(kind='video', data=data), current)[10]) == data


@pytest.mark.parametrize('kind,data', [
    ('outbound_click', {'link_host': 'parceiro.com/oferta?email=a@b.com'}),
    ('outbound_click', {'link_host': 'a@b.com'}),
    ('outbound_click', {}),
    ('outbound_click', {'href': 'https://parceiro.com'}),
    ('file_download', {'file_ext': 'PDF?x=1'}),
    ('file_download', {'file_name': 'contrato-maria.pdf'}),
    ('contact_click', {'channel': 'phone', 'number': '11999999999'}),
    ('contact_click', {'channel': 'mailto:ana@example.com'}),
    ('video', {'action': 'progress', 'percent': 33}),
    ('video', {'action': 'start', 'percent': 25}),
    ('video', {'action': 'seek'}),
    ('custom_event', {'value': 'abc'}),
    ('custom_event', {'currency': 'reais'}),
    ('custom_event', {'email': 'ana@example.com'}),
])
def test_values_outside_the_contract_are_refused(kind, data):
    extra = {'event_name': 'lead'} if kind == 'custom_event' else {}
    with pytest.raises(BadRequest):
        reports_supertag._event(raw_event(kind=kind, data=data, **extra), site())


def test_gtag_style_value_and_currency_are_kept():
    stored = reports_supertag._event(raw_event(kind='conversion', event_name='compra', data={'value': 120.456, 'currency': 'BRL'}), site())
    assert json.loads(stored[10]) == {'value': 120.46, 'currency': 'BRL'}


# ---------------------------------------------------------------- switches enforced by the server

@pytest.mark.parametrize('switch,kind,data', [
    ('scroll', 'scroll_depth', {'depth': 50}),
    ('clicks', 'click', {'x': 1, 'y': 2}),
    ('outbound', 'outbound_click', {'link_host': 'parceiro.com'}),
    ('downloads', 'file_download', {'file_ext': 'pdf'}),
    ('contacts', 'contact_click', {'channel': 'phone'}),
    ('forms', 'form_submit', {'valid': True}),
    ('video', 'video', {'action': 'start'}),
])
def test_switched_off_kinds_are_dropped(switch, kind, data):
    off = site({'enhanced': {switch: False}})
    with pytest.raises(BadRequest):
        reports_supertag._event(raw_event(kind=kind, data=data), off)
    # Other switches stay untouched and page views are always measured.
    assert reports_supertag._event(raw_event(), off)[5] == 'page_view'


def test_whatsapp_click_without_contacts_feeds_the_click_map_or_is_dropped():
    data = {'x': 10, 'y': 20}
    assert reports_supertag._event(raw_event(kind='whatsapp_click', data=data), site({'enhanced': {'contacts': False}}))[5] == 'click'
    with pytest.raises(BadRequest):
        reports_supertag._event(raw_event(kind='whatsapp_click', data=data), site({'enhanced': {'contacts': False, 'clicks': False}}))
    assert reports_supertag._event(raw_event(kind='whatsapp_click', data=data), site())[5] == 'whatsapp_click'


@mock.patch('aicentralv2.cadu_connect.reports_supertag.get_db')
@mock.patch('aicentralv2.cadu_connect.reports_supertag._fanout_flow_events')
@mock.patch('aicentralv2.cadu_connect.reports_supertag._rows', side_effect=fake_rows)
@mock.patch('aicentralv2.cadu_connect.reports_supertag_leads._rows', side_effect=fake_rows)
@mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
def test_collect_counts_switched_off_events_as_rejected_without_error(lookup, _lead_rows, _rows, _fanout, get_db, app):
    # A browser may still run with a cached config where scroll was on: the server drops those events quietly.
    lookup.return_value = site({'enhanced': {'scroll': False}})
    db = FakeDb()
    get_db.return_value = db
    page, scroll = raw_event(path='/produto'), raw_event(kind='scroll_depth', data={'depth': 25})
    response = app.test_client().post('/connect/public/supertag/v1/pub/collect', headers={'Origin': 'https://example.test'},
                                      data=json.dumps({'events': [page, scroll]}), content_type='text/plain')
    assert response.status_code == 202
    assert response.get_json()['accepted'] == 1 and response.get_json()['rejected'] == 1
    assert [row[0] for row in db.executemany_calls[0][1]] == [page['event_id']]


@mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
def test_lead_is_not_stored_when_form_measurement_is_off(lookup, app):
    lookup.return_value = site({'enhanced': {'forms': False}})
    body = {'event_id': str(uuid.uuid4()), 'session_id': str(uuid.uuid4()), 'path': '/', 'email': 'ana@example.com'}
    with mock.patch.object(leads, 'store_lead') as store:
        response = app.test_client().post('/connect/public/supertag/v1/pub/lead', headers={'Origin': 'https://example.test'},
                                          data=json.dumps(body), content_type='text/plain')
    assert response.status_code == 202 and response.get_json() == {'accepted': 0}
    store.assert_not_called()
