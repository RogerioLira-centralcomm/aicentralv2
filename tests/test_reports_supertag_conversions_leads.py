import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
from cryptography.fernet import Fernet
from flask import Blueprint, Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect import reports_supertag
from aicentralv2.cadu_connect import reports_supertag_leads as leads
from tests.test_reports_supertag import FakeDb, fake_rows, raw_event

SITE_ID = str(uuid.uuid4())
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def prepared(kind='page_view', path='/obrigado', session=None, data=None, name=None, event_id=None):
    return (event_id or str(uuid.uuid4()), SITE_ID, 7, str(uuid.uuid4()), session or str(uuid.uuid4()), kind, name, path,
            None, '{}', json.dumps(data or {}), 390, 800, NOW)


def site(config=None):
    return {'id': SITE_ID, 'client_id': 7, 'public_id': 'pub', 'allowed_host': 'example.test', 'config': config or {}}


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.config['SECRET_KEY'] = 'test-secret'
    bp = Blueprint('reports', __name__, url_prefix='/connect')
    reports_supertag.register(bp)
    flask_app.register_blueprint(bp)
    leads._ready_tables.clear()
    return flask_app


# ---------------------------------------------------------------- rules

@pytest.mark.parametrize('rule,path,expected', [
    ({'type': 'path', 'match': 'exact', 'value': '/obrigado'}, '/obrigado/', True),
    ({'type': 'path', 'match': 'exact', 'value': '/obrigado'}, '/obrigado-2', False),
    ({'type': 'path', 'match': 'prefix', 'value': '/obrigad'}, '/obrigada.php', True),
    ({'type': 'path', 'match': 'prefix', 'value': '/obrigado'}, '/contato', False),
    ({'type': 'path', 'match': 'segment', 'value': 'thank'}, '/en/thank-you', True),
    ({'type': 'path', 'match': 'segment', 'value': 'confirmac'}, '/Confirmacao', True),
])
def test_path_rules(rule, path, expected):
    assert leads.rule_matches(rule, 'page_view', None, path, {}) is expected


def test_valid_form_rule_ignores_invalid_submits_and_filters_by_form():
    rule = {'type': 'valid_form', 'form_id': 'contato'}
    assert leads.rule_matches(rule, 'form_submit', None, '/', {'valid': True, 'form_id': 'contato'})
    assert not leads.rule_matches(rule, 'form_submit', None, '/', {'valid': False, 'form_id': 'contato'})
    assert not leads.rule_matches(rule, 'form_submit', None, '/', {'valid': True, 'form_id': 'outro'})
    # Older tags without the flag only fire after the browser accepted the form.
    assert leads.rule_matches({'type': 'valid_form'}, 'form_submit', None, '/', {})


def test_event_name_rule():
    rule = {'type': 'event_name', 'value': 'lead_enviado'}
    assert leads.rule_matches(rule, 'custom_event', 'lead_enviado', '/', {})
    assert not leads.rule_matches(rule, 'custom_event', 'outro', '/', {})
    assert not leads.rule_matches(rule, 'page_view', 'lead_enviado', '/', {})


def test_sites_without_rules_use_the_thank_you_defaults():
    derived = leads.derive_conversions(site(), [prepared(path='/obrigado.php'), prepared(path='/produtos')])
    assert len(derived) == 1
    assert derived[0][5] == 'conversion' and derived[0][6] == 'pagina_obrigado' and derived[0][7] == '/obrigado.php'
    assert json.loads(derived[0][10])['derived_from'] == 'page_view'


def test_saved_rules_replace_the_defaults_and_defaults_can_be_turned_off():
    custom = site({'conversion_rules': [{'type': 'path', 'match': 'exact', 'value': '/fim'}]})
    assert leads.derive_conversions(custom, [prepared(path='/obrigado')]) == []
    assert len(leads.derive_conversions(custom, [prepared(path='/fim')])) == 1
    assert leads.derive_conversions(site({'conversion_defaults': False}), [prepared(path='/obrigado')]) == []


def test_derived_conversion_is_idempotent_per_source_event():
    source = prepared(path='/obrigado')
    first = leads.derive_conversions(site(), [source])[0][0]
    again = leads.derive_conversions(site(), [source])[0][0]
    other = leads.derive_conversions(site(), [prepared(path='/obrigado')])[0][0]
    assert first == again == str(uuid.uuid5(uuid.UUID(SITE_ID), f'supertag-conversion:{SITE_ID}:{source[0]}'))
    assert first != other


def test_reloaded_thank_you_page_and_explicit_conversion_count_once():
    session = str(uuid.uuid4())
    assert leads.derive_conversions(site(), [prepared(session=session), prepared(session=session)]).__len__() == 1
    assert leads.derive_conversions(site(), [prepared(session=session)], {(session, '/obrigado')}) == []
    explicit = prepared(kind='conversion', session=session, name='lead')
    assert leads.derive_conversions(site(), [explicit, prepared(session=session)]) == []


def test_invalid_submit_never_converts():
    config = site({'conversion_rules': [{'type': 'valid_form'}]})
    assert leads.derive_conversions(config, [prepared('form_submit', '/contato', data={'valid': False})]) == []
    derived = leads.derive_conversions(config, [prepared('form_submit', '/contato', data={'valid': True})])
    assert derived[0][6] == 'formulario_enviado'


@pytest.mark.parametrize('rules', [
    [{'type': 'path', 'match': 'exact', 'value': '/contato/ana@example.com'}],
    [{'type': 'path', 'match': 'exact', 'value': '/com espaço'}],
    [{'type': 'path', 'match': 'exact', 'value': '   '}],
    [{'type': 'path', 'match': 'segment', 'value': 'a/b'}],
    [{'type': 'path', 'match': 'segment', 'value': 'x'}],
    [{'type': 'path', 'match': 'contains', 'value': '/a'}],
    [{'type': 'event_name', 'value': '1x'}],
    [{'type': 'valid_form', 'extra': True}],
    [{'type': 'unknown'}],
    [{'type': 'path', 'value': '/a', 'name': '1_conversao'}],
    [{'type': 'event_name', 'value': 'lead-enviado'}],
    [{'type': 'valid_form', 'form_id': 'form contato'}],
    [{'type': 'event_name', 'value': 'a'}] * 21,
])
def test_invalid_rules_are_refused(rules, app):
    with app.test_request_context('/'):
        with pytest.raises(BadRequest):
            leads.validate_conversion_rules(rules)


def test_valid_rules_are_normalized(app):
    with app.test_request_context('/'):
        clean = leads.validate_conversion_rules([{'type': 'path', 'value': ' /obrigado '},
                                                 {'type': 'valid_form', 'form_id': None}, {'type': 'event_name', 'value': 'lead'}])
    assert clean == [{'type': 'path', 'match': 'prefix', 'value': '/obrigado'}, {'type': 'valid_form'},
                     {'type': 'event_name', 'value': 'lead'}]


def test_suggestions_skip_paths_already_covered(app):
    rows = [{'page_path': '/obrigado', 'views': 4, 'last_at': NOW}, {'page_path': '/sucesso', 'views': 2, 'last_at': NOW}]
    with app.test_request_context('/'), mock.patch.object(leads, '_rows', return_value=rows) as query:
        found = leads.conversion_suggestions(site({'conversion_rules': [{'type': 'path', 'match': 'exact', 'value': '/obrigado'}]}))
    assert [item['path'] for item in found] == ['/sucesso']
    assert found[0]['rule'] == {'type': 'path', 'match': 'exact', 'value': '/sucesso', 'name': 'pagina_obrigado'}
    assert leads.SUGGESTION_PATTERN in query.call_args[0][1]


@mock.patch('aicentralv2.cadu_connect.reports_supertag.get_db')
@mock.patch('aicentralv2.cadu_connect.reports_supertag._fanout_flow_events')
@mock.patch('aicentralv2.cadu_connect.reports_supertag._rows', side_effect=fake_rows)
@mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
def test_collect_stores_the_derived_conversion_with_the_page_view(lookup, _rows, fanout, get_db, app):
    lookup.return_value = site()
    db = FakeDb()
    get_db.return_value = db
    event = raw_event(path='/obrigado')
    with mock.patch.object(leads, '_rows', side_effect=fake_rows):
        response = app.test_client().post('/connect/public/supertag/v1/pub/collect', headers={'Origin': 'https://example.test'},
                                          data=json.dumps({'events': [event]}), content_type='text/plain')
    assert response.status_code == 202 and response.get_json()['conversions'] == 1
    inserted = db.executemany_calls[0][1]
    assert [row[5] for row in inserted] == ['page_view', 'conversion']
    assert inserted[1][0] == leads.derived_event_id(SITE_ID, event['event_id'])
    # Flows keep mapping the thank-you page themselves; derived conversions are not mirrored there.
    assert all(item[5] != 'conversion' for item in fanout.call_args[0][1])


# ---------------------------------------------------------------- encryption and capture

def test_lead_values_are_encrypted_with_their_own_derived_key(app):
    with app.app_context():
        token = leads.encrypt('maria@example.com')
        assert 'maria' not in token
        assert leads.decrypt(token) == 'maria@example.com'
        expected = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b'centralx:supertag-leads:v1:test-secret').digest()))
        assert expected.decrypt(token.encode()).decode() == 'maria@example.com'
        integration = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b'centralx:integration-credentials:v1:test-secret').digest()))
        with pytest.raises(Exception):
            integration.decrypt(token.encode())


def test_dedicated_key_is_preferred(app):
    key = Fernet.generate_key()
    app.config['SUPERTAG_LEADS_KEY'] = key.decode()
    with app.app_context():
        token = leads.encrypt({'empresa': 'ACME'})
        assert json.loads(Fernet(key).decrypt(token.encode())) == {'empresa': 'ACME'}
        assert leads.decrypt(token, as_json=True) == {'empresa': 'ACME'}


def test_sensitive_fields_and_values_are_never_kept():
    config = {'form_capture': {'fields': ['empresa', 'senha', 'cpf', 'mensagem', 'codigo']}}
    clean = leads.clean_fields({'empresa': 'ACME', 'senha': 'x', 'cpf': '123.456.789-09', 'mensagem': 'oi',
                                'codigo': '4111 1111 1111 1111', 'nao_configurado': 'y'}, config)
    assert clean == {'empresa': 'ACME', 'mensagem': 'oi'}
    assert leads.clean_contact('123.456.789-09', 'nao-e-email', 'abc') == ('', '', '')
    assert leads.clean_contact('  Maria   Silva ', 'maria@example.com', '+55 11 98888-7777') == \
        ('Maria Silva', 'maria@example.com', '+55 11 98888-7777')


@pytest.mark.parametrize('name', ['senha', 'user_password', 'cartao', 'cvv', 'cpf', 'cnpj', 'rg', 'csrf_token', 'g-recaptcha'])
def test_form_capture_refuses_sensitive_field_names(name, app):
    with app.test_request_context('/'):
        with pytest.raises(BadRequest):
            leads.validate_form_capture({'fields': [name]})


def test_masks():
    assert leads.mask_email('maria@example.com') == 'ma•••@example.com'
    assert leads.mask_phone('(11) 98888-7777') == '••••7777'
    assert leads.mask_name('Maria da Silva') == 'Maria S.'


def _lead_body(**extra):
    body = {'event_id': str(uuid.uuid4()), 'visitor_id': str(uuid.uuid4()), 'session_id': str(uuid.uuid4()),
            'form_id': 'contato', 'path': '/contato', 'occurred_at': datetime.now(timezone.utc).isoformat(),
            'name': 'Maria Silva', 'email': 'maria@example.com', 'phone': '(11) 98888-7777',
            'fields': {'empresa': 'ACME', 'senha': 'nunca'}}
    body.update(extra)
    return body


def _post_lead(app, body, config=None, conversion=None):
    calls = []

    def answer(sql, params=()):
        calls.append((sql, params))
        if 'to_regclass' in sql:
            return [{'ready': True}]
        if 'RETURNING event_count' in sql:
            return [{'event_count': 1}]
        if "event_kind='conversion'" in sql and sql.lstrip().startswith('SELECT'):
            return conversion or []
        if 'INSERT INTO cadu_reports_supertag_leads' in sql:
            return [{'id': 'lead-1'}]
        return []
    with mock.patch.object(reports_supertag, '_site_by_public_id', return_value=site(config)), \
            mock.patch.object(leads, '_rows', side_effect=answer), \
            mock.patch.object(leads, 'get_db', return_value=FakeDb()):
        response = app.test_client().post('/connect/public/supertag/v1/pub/lead', headers={'Origin': 'https://example.test'},
                                          data=json.dumps(body), content_type='text/plain')
    insert = next((params for sql, params in calls if 'INSERT INTO cadu_reports_supertag_leads' in sql), None)
    return response, insert


def test_lead_endpoint_stores_encrypted_contact_pending_until_a_conversion(app):
    app.config['SUPERTAG_LEADS_KEY'] = Fernet.generate_key().decode()
    response, insert = _post_lead(app, _lead_body(), {'form_capture': {'fields': ['empresa']}})
    assert response.status_code == 202 and response.get_json() == {'accepted': 1}
    flat = json.dumps([str(value) for value in insert])
    for plain in ('maria@example.com', 'Maria Silva', '98888', 'ACME', 'nunca'):
        assert plain not in flat
    assert insert[6] == 'form' and insert[7] == 'contato' and insert[8] == '/contato'
    assert insert[11] == 'pending' and insert[10] is None
    with app.app_context():
        assert leads.decrypt(insert[13]) == 'maria@example.com'
        assert leads.decrypt(insert[15], as_json=True) == {'empresa': 'ACME'}
    assert len(insert[16]) == 64 and len(insert[17]) == 64


def test_lead_is_confirmed_when_the_thank_you_conversion_already_arrived(app):
    _, insert = _post_lead(app, _lead_body(), conversion=[{'occurred_at': NOW, 'derived_from': 'page_view'}])
    assert insert[11] == 'rule' and insert[10] == NOW
    _, insert = _post_lead(app, _lead_body(), conversion=[{'occurred_at': NOW, 'derived_from': None}])
    assert insert[11] == 'conversion'


def test_valid_submit_option_counts_the_lead_directly(app):
    _, insert = _post_lead(app, _lead_body(), {'form_capture': {'confirm': 'valid_submit'}})
    assert insert[11] == 'valid_submit' and insert[10] is not None


def test_lead_is_not_stored_when_capture_is_disabled_even_if_an_old_tag_sends_it(app):
    response, insert = _post_lead(app, _lead_body(), {'form_capture': {'enabled': False}})
    assert response.status_code == 202 and response.get_json() == {'accepted': 0}
    assert insert is None


def test_lead_from_foreign_origin_or_with_unknown_keys_is_refused(app):
    with mock.patch.object(reports_supertag, '_site_by_public_id', return_value=site()):
        client = app.test_client()
        assert client.post('/connect/public/supertag/v1/pub/lead', headers={'Origin': 'https://evil.test'},
                           data=json.dumps(_lead_body()), content_type='text/plain').status_code == 403
        assert client.post('/connect/public/supertag/v1/pub/lead', headers={'Origin': 'https://example.test'},
                           data=json.dumps(_lead_body(password='x')), content_type='text/plain').status_code == 400
        assert client.post('/connect/public/supertag/v1/pub/lead', headers={'Origin': 'https://example.test'},
                           data='x' * (leads.MAX_LEAD_BYTES + 10), content_type='text/plain').status_code == 413


def test_conversion_confirms_pending_leads_of_the_same_session_within_30_minutes(app):
    conversion = prepared(kind='conversion', data={'derived_from': 'page_view'})
    with app.app_context(), mock.patch.object(leads, '_rows', side_effect=lambda sql, params=(): [{'ready': True}] if 'to_regclass' in sql else []) as rows:
        leads.confirm_leads(SITE_ID, [conversion])
    sql, params = rows.call_args_list[-1][0]
    assert 'UPDATE cadu_reports_supertag_leads' in sql and 'confirmed_at IS NULL' in sql
    assert params[1] == 'rule' and params[3] == conversion[4]
    assert params[4] == NOW - timedelta(minutes=30)


def test_lead_rows_are_masked_for_viewers_and_full_for_editors(app):
    with app.app_context():
        row = {'id': 'a', 'site_id': 'b', 'session_id': 'c', 'confirmation': 'pending', 'utm_campaign': 'promo',
               'display_name_enc': leads.encrypt('Maria da Silva'), 'email_enc': leads.encrypt('maria@example.com'),
               'phone_enc': leads.encrypt('11988887777'), 'fields_enc': leads.encrypt({'empresa': 'ACME'})}
        viewer = leads.lead_row(dict(row), can_reveal=False)
        editor = leads.lead_row(dict(row), can_reveal=True)
    assert viewer['name'] == 'Maria S.' and viewer['email'] == 'ma•••@example.com' and viewer['fields'] == {'empresa': '•••'}
    assert editor['name'] == 'Maria da Silva' and editor['fields'] == {'empresa': 'ACME'}
    assert editor['email'] == 'ma•••@example.com'  # revealed only on demand
    assert viewer['status'] == 'pending' and viewer['campaign'] == 'promo'


def test_viewer_cannot_reveal_a_contact(app):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
        with mock.patch.object(leads, '_selection', return_value={'client_id': 7, 'role': 'viewer'}):
            assert client.get(f'/connect/api/v2/reports/supertag/leads/{uuid.uuid4()}/contact').status_code == 403


def test_deleting_a_lead_is_scoped_to_the_client(app):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
        with mock.patch.object(leads, '_selection', return_value={'client_id': 7, 'role': 'admin'}), \
                mock.patch.object(leads, '_write_guard'), mock.patch.object(leads, 'get_db', return_value=FakeDb()), \
                mock.patch.object(leads, '_rows', side_effect=lambda sql, params=(): [{'ready': True}] if 'to_regclass' in sql else [{'id': 'x'}]) as rows:
            response = client.delete(f'/connect/api/v2/reports/supertag/leads/{uuid.uuid4()}')
    assert response.status_code == 200
    sql, params = rows.call_args_list[-1][0]
    assert 'DELETE FROM cadu_reports_supertag_leads' in sql and params[1] == 7


def test_leads_list_uses_the_period_and_client_scope(app):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['family_csrf'] = 'tok'
        with mock.patch.object(leads, '_selection', return_value={'client_id': 7, 'role': 'member'}), \
                mock.patch.object(leads, '_rows', side_effect=lambda sql, params=(): [{'ready': True}] if 'to_regclass' in sql else []) as rows:
            body = client.get('/connect/api/v2/reports/supertag/leads?start_date=2026-09-01&end_date=2026-09-30').get_json()
    assert body['ready'] and body['can_reveal'] and body['csrf'] == 'tok' and body['leads'] == []
    sql, params = rows.call_args_list[-1][0]
    assert 's.client_id=%(client)s' in sql and params['client'] == 7 and 'since' in params and '{site}' not in sql


def test_purge_removes_expired_leads():
    from scripts import purge_reports_supertag_events as purge
    executed = []
    cursor = mock.MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.execute.side_effect = lambda sql, *args: executed.append(sql)
    cursor.rowcount = 0
    cursor.fetchone.return_value = (True,)
    connection = mock.MagicMock()
    connection.cursor.return_value = cursor
    with mock.patch.object(purge.psycopg, 'connect', return_value=connection):
        purge.main()
    assert any('DELETE FROM cadu_reports_supertag_leads' in sql and 'expires_at <= NOW()' in sql for sql in executed)


# ---------------------------------------------------------------- dedupe per (site, session, conversion) in 5 min

def stored(item, at=None, derived_from=None):
    return {'event_id': item[0], 'session_id': item[4], 'event_name': item[6], 'page_path': item[7],
            'occurred_at': at or item[13], 'derived_from': derived_from}


def explicit_conversion(session, name='lead', path='/obrigado', at=NOW):
    item = prepared(kind='conversion', path=path, session=session, name=name)
    return item[:13] + (at,)


def test_dedupe_keeps_the_explicit_conversion_over_the_rule_in_the_same_batch():
    session = str(uuid.uuid4())
    explicit = explicit_conversion(session, name='pagina_obrigado', path='/contato')
    derived = leads.derive_conversions(site(), [prepared(session=session)])
    kept, dropped = leads.dedupe_conversions(derived + [explicit])
    assert kept == [explicit] and dropped == derived
    # trackConversion fired on the thank-you page itself is the same conversion, whatever its name.
    same_page = explicit_conversion(session, name='lead')
    kept, dropped = leads.dedupe_conversions(derived + [same_page])
    assert kept == [same_page] and dropped == derived


def test_dedupe_window_is_five_minutes_and_first_stored_wins():
    session = str(uuid.uuid4())
    first = explicit_conversion(session, at=NOW - timedelta(minutes=4))
    again = explicit_conversion(session)
    assert leads.dedupe_conversions([again], [stored(first)]) == ([], [again])
    old = explicit_conversion(session, at=NOW - timedelta(minutes=6))
    assert leads.dedupe_conversions([again], [stored(old)]) == ([again], [])
    # A later batch of an earlier event (out of order) is a duplicate too.
    late = explicit_conversion(session, at=NOW - timedelta(minutes=3))
    assert leads.dedupe_conversions([late], [stored(again)]) == ([], [late])


def test_different_conversion_names_or_sessions_keep_counting():
    session = str(uuid.uuid4())
    lead, purchase = explicit_conversion(session, 'lead', '/a'), explicit_conversion(session, 'compra', '/b')
    other_session = explicit_conversion(str(uuid.uuid4()), 'lead', '/a')
    kept, dropped = leads.dedupe_conversions([lead, purchase, other_session])
    assert len(kept) == 3 and dropped == []
    # A form rule on another page and a thank-you page of the same session are different conversions.
    form = leads.derive_conversions(site({'conversion_rules': [{'type': 'valid_form'}]}),
                                    [prepared('form_submit', '/contato', session=session, data={'valid': True})])
    assert leads.dedupe_conversions(form, [stored(lead)])[0] == form


def _collect(app, events, existing_events=(), conversions=()):
    """Posts a batch; the database answers with the given stored events (by id) and stored conversions."""
    db = FakeDb()
    calls = []

    def answer(sql, params=()):
        calls.append((sql, params))
        if 'RETURNING event_count' in sql:
            return [{'event_count': 1}]
        if 'to_regclass' in sql:
            return [{'ready': True}]
        if sql.lstrip().startswith('SELECT event_id FROM cadu_reports_supertag_events'):
            return [{'event_id': event_id} for event_id in existing_events]
        if "event_kind='conversion'" in sql and "'derived_from' AS derived_from" in sql:
            return list(conversions)
        return []
    with mock.patch.object(reports_supertag, '_site_by_public_id', return_value=site()), \
            mock.patch.object(reports_supertag, 'get_db', return_value=db), \
            mock.patch.object(reports_supertag, '_fanout_flow_events'), \
            mock.patch.object(reports_supertag, '_rows', side_effect=answer), \
            mock.patch.object(leads, '_rows', side_effect=answer):
        response = app.test_client().post('/connect/public/supertag/v1/pub/collect', headers={'Origin': 'https://example.test'},
                                          data=json.dumps({'events': events}), content_type='text/plain')
    inserted = db.executemany_calls[0][1] if db.executemany_calls else []
    return response, inserted, calls


def test_thank_you_page_after_an_explicit_conversion_in_another_batch_counts_once(app):
    session = str(uuid.uuid4())
    explicit_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    already = {'event_id': str(uuid.uuid4()), 'session_id': session, 'event_name': 'lead', 'page_path': '/obrigado',
               'occurred_at': explicit_at, 'derived_from': None}
    response, inserted, _ = _collect(app, [raw_event(path='/obrigado', session_id=session)], conversions=[already])
    assert response.status_code == 202
    body = response.get_json()
    assert body['conversions'] == 0 and body['deduped'] == 1 and body['accepted'] == 1
    assert [row[5] for row in inserted] == ['page_view']


def test_explicit_conversion_after_the_rule_in_another_batch_is_not_stored(app):
    session = str(uuid.uuid4())
    derived_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    already = {'event_id': str(uuid.uuid4()), 'session_id': session, 'event_name': 'pagina_obrigado',
               'page_path': '/obrigado', 'occurred_at': derived_at, 'derived_from': 'page_view'}
    explicit = raw_event('conversion', '/obrigado', session_id=session, event_name='pagina_obrigado')
    other = raw_event('conversion', '/obrigado', session_id=session, event_name='compra')
    with mock.patch.object(leads, 'confirm_leads') as confirm:
        response, inserted, _ = _collect(app, [explicit, other], conversions=[already])
    body = response.get_json()
    assert response.status_code == 202 and body['deduped'] == 1 and body['accepted'] == 1 and body['rejected'] == 0
    # Named by the site with another name, compra counts even on the thank-you page.
    assert [row[6] for row in inserted] == ['compra']
    # The duplicate still happened: it may confirm a pending lead.
    assert {item[6] for item in confirm.call_args[0][1]} == {'pagina_obrigado', 'compra'}


def test_same_conversion_outside_the_window_counts_again(app):
    session = str(uuid.uuid4())
    old = {'event_id': str(uuid.uuid4()), 'session_id': session, 'event_name': 'lead', 'page_path': '/obrigado',
           'occurred_at': datetime.now(timezone.utc) - timedelta(minutes=6), 'derived_from': None}
    response, inserted, _ = _collect(app, [raw_event('conversion', '/obrigado', session_id=session, event_name='lead')],
                                     conversions=[old])
    assert response.get_json()['deduped'] == 0 and [row[5] for row in inserted] == ['conversion']


def test_resending_the_same_batch_neither_duplicates_nor_fails(app):
    session = str(uuid.uuid4())
    page = raw_event(path='/obrigado', session_id=session)
    explicit = raw_event('conversion', '/obrigado', session_id=session, event_name='lead')
    first, inserted, _ = _collect(app, [page, explicit])
    assert first.get_json()['conversions'] == 0 and [row[5] for row in inserted] == ['page_view', 'conversion']
    stored_conversion = {'event_id': explicit['event_id'], 'session_id': session, 'event_name': 'lead',
                         'page_path': '/obrigado', 'occurred_at': inserted[1][13], 'derived_from': None}
    again, inserted, _ = _collect(app, [page, explicit], existing_events=[page['event_id'], explicit['event_id']],
                                  conversions=[stored_conversion])
    assert again.status_code == 202 and again.get_json()['conversions'] == 0 and again.get_json()['deduped'] == 0
    # ON CONFLICT DO NOTHING absorbs the resent rows; no new derived conversion is created.
    assert all(row[0] in (page['event_id'], explicit['event_id']) for row in inserted)


def test_batches_of_one_session_are_serialized_before_the_event_locks(app):
    session = str(uuid.uuid4())
    _, _, calls = _collect(app, [raw_event(path='/obrigado', session_id=session), raw_event(session_id=session)])
    locks = [params[1] for sql, params in calls if 'pg_advisory_xact_lock' in sql]
    assert locks[0] == f'session:{session}' and len(locks) == 3
    assert not any(key.startswith('session:') for key in locks[1:])


def test_pending_lead_is_still_confirmed_by_the_thank_you_page(app):
    session = str(uuid.uuid4())
    response, _, calls = _collect(app, [raw_event(path='/obrigado', session_id=session)])
    assert response.get_json()['conversions'] == 1
    update = next(params for sql, params in calls if 'UPDATE cadu_reports_supertag_leads' in sql)
    assert update[1] == 'rule' and update[3] == session


def test_backfill_skips_a_conversion_already_counted_in_the_window():
    from scripts import backfill_reports_supertag_conversions as backfill
    session = str(uuid.uuid4())
    page = {'event_id': uuid.uuid4(), 'site_id': SITE_ID, 'client_id': 7, 'visitor_id': None, 'session_id': session,
            'event_kind': 'page_view', 'event_name': None, 'page_path': '/obrigado', 'referrer_host': None,
            'attribution': '{}', 'event_data': '{}', 'viewport_width': 1, 'viewport_height': 1,
            'occurred_at': NOW, 'expires_at': NOW + timedelta(days=90)}
    explicit = dict(page, event_id=uuid.uuid4(), event_kind='conversion', event_name='lead', page_path='/contato',
                    occurred_at=NOW - timedelta(minutes=10))
    form_page = dict(page, event_id=uuid.uuid4(), event_kind='page_view', page_path='/obrigado-2',
                     session_id=str(uuid.uuid4()))
    lead_same_name = dict(explicit, event_id=uuid.uuid4(), session_id=form_page['session_id'],
                          event_name='pagina_obrigado', occurred_at=NOW - timedelta(minutes=2))
    rows = [explicit, page, lead_same_name, form_page]
    executed = []
    cursor = mock.MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.execute.side_effect = lambda sql, params=(): executed.append((sql, params))
    cursor.fetchone.side_effect = [{'id': SITE_ID, 'client_id': 7, 'config': {}}, {'ready': False}]
    recheck = [{'session_id': form_page['session_id'], 'event_name': 'pagina_obrigado', 'page_path': '/contato',
                'occurred_at': lead_same_name['occurred_at'], 'derived_from': None}]
    cursor.fetchall.side_effect = [rows, recheck]
    cursor.rowcount = 1
    connection = mock.MagicMock()
    connection.cursor.return_value = cursor
    with mock.patch.object(backfill.psycopg, 'connect', return_value=connection), \
            mock.patch('sys.argv', ['backfill', '--site', 'pub', '--apply']):
        backfill.main()
    inserts = [params for sql, params in executed if 'INSERT INTO cadu_reports_supertag_events' in sql]
    # The first session converts on /obrigado (the explicit lead was 10 min earlier); the second one already had
    # pagina_obrigado 2 min before, so its thank-you page is not counted again.
    assert [(params[4], params[7]) for params in inserts] == [(session, '/obrigado')]
    assert any('pg_advisory_xact_lock' in sql and params[1] == f'session:{session}' for sql, params in executed)
