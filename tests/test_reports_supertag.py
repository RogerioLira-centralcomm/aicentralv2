import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase, mock

from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_supertag

ROOT = Path(__file__).resolve().parents[1]
SITE_ID = str(uuid.uuid4())


def raw_event(kind='page_view', path='/lp', **extra):
    event = {'event_id': str(uuid.uuid4()), 'visitor_id': str(uuid.uuid4()), 'session_id': str(uuid.uuid4()),
             'kind': kind, 'path': path, 'attribution': {}, 'data': {}, 'viewport_width': 390, 'viewport_height': 800,
             'occurred_at': datetime.now(timezone.utc).isoformat()}
    event.update(extra)
    return event


class FakeDb:
    def __init__(self):
        self.executemany_calls = []
        self.committed = False

    def cursor(self):
        db = self

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def executemany(self, sql, rows):
                db.executemany_calls.append((sql, list(rows)))

        return Cursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def fake_rows(sql, params=()):
    if 'RETURNING event_count' in sql:
        return [{'event_count': 1}]
    if 'to_regclass' in sql:
        return [{'ready': False}]
    return []


class SuperTagAppTest(TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret'
        bp = Blueprint('reports', __name__, url_prefix='/connect')
        reports_supertag.register(bp)
        app.register_blueprint(bp)
        self.app = app
        self.client = app.test_client()
        self.site = {'id': SITE_ID, 'client_id': 7, 'public_id': 'public-id', 'allowed_host': 'example.test',
                     'config': {}, 'config_version': 3}
        reports_supertag.leads._ready_tables.clear()


class ReportsSuperTagWithoutConsentTest(SuperTagAppTest):
    """The tag no longer asks for consent: that is the website's job. Only an explicit opt-out stops it."""

    @mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
    def test_consent_endpoint_still_answers_cached_tags(self, lookup):
        lookup.return_value = self.site
        preflight = self.client.options('/connect/public/supertag/v1/public-id/consent', headers={
            'Origin': 'https://example.test', 'Access-Control-Request-Method': 'POST'})
        self.assertEqual(preflight.status_code, 204)
        self.assertEqual(preflight.headers['Access-Control-Allow-Origin'], 'https://example.test')
        response = self.client.post('/connect/public/supertag/v1/public-id/consent',
                                    headers={'Origin': 'https://example.test'}, json={'analytics': False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'analytics': False})
        self.assertNotIn('Set-Cookie', response.headers)
        anything = self.client.post('/connect/public/supertag/v1/public-id/consent',
                                    headers={'Origin': 'https://example.test'}, json={'x': 1})
        self.assertEqual(anything.status_code, 200)

    def test_events_without_consent_field_are_accepted(self):
        stored = reports_supertag._event(raw_event(), self.site)
        self.assertEqual(stored[5], 'page_view')

    def test_cached_tags_that_still_send_consent_are_accepted(self):
        for value in ('granted', 'denied', None):
            self.assertEqual(reports_supertag._event(raw_event(consent=value), self.site)[5], 'page_view')

    @mock.patch('aicentralv2.cadu_connect.reports_supertag.get_db')
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._fanout_flow_events')
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._rows', side_effect=fake_rows)
    @mock.patch('aicentralv2.cadu_connect.reports_supertag_leads._rows', side_effect=fake_rows)
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
    def test_collect_never_answers_403_for_missing_consent(self, lookup, _lead_rows, _rows, _fanout, get_db):
        lookup.return_value = self.site
        db = FakeDb()
        get_db.return_value = db
        response = self.client.post('/connect/public/supertag/v1/public-id/collect',
                                    headers={'Origin': 'https://example.test'},
                                    data=json.dumps({'events': [raw_event()]}), content_type='text/plain')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()['accepted'], 1)
        self.assertTrue(db.committed)

    @mock.patch('aicentralv2.cadu_connect.reports_supertag.get_db')
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._fanout_flow_events')
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._rows', side_effect=fake_rows)
    @mock.patch('aicentralv2.cadu_connect.reports_supertag_leads._rows', side_effect=fake_rows)
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
    def test_identify_without_consent_is_accepted(self, lookup, lead_rows, rows, _fanout, get_db):
        lookup.return_value = self.site
        get_db.return_value = FakeDb()
        visitor = str(uuid.uuid4())

        def answer(sql, params=()):
            if 'RETURNING visitor_id' in sql:
                return [{'visitor_id': visitor}]
            if 'RETURNING id' in sql:
                return [{'id': str(uuid.uuid4())}]
            return fake_rows(sql, params)
        rows.side_effect = answer
        response = self.client.post('/connect/public/supertag/v1/public-id/identify',
                                    headers={'Origin': 'https://example.test'},
                                    json={'visitor_id': visitor, 'session_id': str(uuid.uuid4()),
                                          'email': 'ana@example.com', 'path': '/contato'})
        self.assertEqual(response.status_code, 200)

    @mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
    def test_public_config_has_no_consent_settings(self, lookup):
        lookup.return_value = {**self.site, 'config': {'consent_mode': 'manual', 'consent_required': True,
                                                       'form_capture': {'fields': ['empresa']}}}
        body = self.client.get('/connect/public/supertag/v1/public-id/config.json',
                               headers={'Origin': 'https://example.test'}).get_json()
        self.assertNotIn('consent_mode', body)
        self.assertNotIn('consent_required', body)
        self.assertEqual(body['form_capture'], {'enabled': True, 'fields': ['empresa']})

    def test_snippet_has_no_consent_attribute(self):
        with self.app.test_request_context('/'):
            snippet = reports_supertag._supertag_snippet({'public_id': 'abc'})
        self.assertNotIn('consent', snippet)
        self.assertIn('data-cadu-site="abc"', snippet)

    def test_tag_source_and_minified_file_have_no_consent_gate(self):
        for name in ('cadu-supertag-v1.js', 'cadu-supertag-v1.min.js'):
            source = (ROOT / 'aicentralv2/static/cadu_connect' / name).read_text()
            for gone in ('data-cadu-consent', 'showConsentPrompt', 'OnetrustActiveGroups', 'Cookiebot', '__tcfapi',
                         "consent:'granted'", 'consent:"granted"'):
                self.assertNotIn(gone, source, f'{name}: {gone}')
            self.assertIn('/lead', source, name)
            self.assertIn('cadu:consent', source, name)


class ReportsSuperTagPoisonedBatchTest(SuperTagAppTest):
    """C9: one invalid event must not make the whole batch fail (the tag would resend it forever)."""

    @mock.patch('aicentralv2.cadu_connect.reports_supertag.get_db')
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._fanout_flow_events')
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._rows', side_effect=fake_rows)
    @mock.patch('aicentralv2.cadu_connect.reports_supertag_leads._rows', side_effect=fake_rows)
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
    def test_invalid_event_is_dropped_and_the_rest_is_stored(self, lookup, _lead_rows, _rows, _fanout, get_db):
        lookup.return_value = self.site
        db = FakeDb()
        get_db.return_value = db
        good, bad = raw_event(path='/produto'), raw_event(kind='nope')
        response = self.client.post('/connect/public/supertag/v1/public-id/collect', headers={'Origin': 'https://example.test'},
                                    data=json.dumps({'events': [bad, good]}), content_type='text/plain')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()['accepted'], 1)
        self.assertEqual(response.get_json()['rejected'], 1)
        inserted = db.executemany_calls[0][1]
        self.assertEqual([row[0] for row in inserted], [good['event_id']])

    @mock.patch('aicentralv2.cadu_connect.reports_supertag.get_db')
    @mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
    def test_batch_with_only_invalid_events_answers_202_without_touching_the_database(self, lookup, get_db):
        lookup.return_value = self.site
        response = self.client.post('/connect/public/supertag/v1/public-id/collect', headers={'Origin': 'https://example.test'},
                                    data=json.dumps({'events': [raw_event(path='sem-barra')]}), content_type='text/plain')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json(), {'accepted': 0, 'rejected': 1})
        get_db.assert_not_called()

    @mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
    def test_foreign_origin_is_still_refused(self, lookup):
        lookup.return_value = self.site
        response = self.client.post('/connect/public/supertag/v1/public-id/collect', headers={'Origin': 'https://evil.test'},
                                    data=json.dumps({'events': [raw_event()]}), content_type='text/plain')
        self.assertEqual(response.status_code, 403)

    def test_paths_with_query_or_email_and_field_values_stay_forbidden(self):
        from werkzeug.exceptions import BadRequest
        for event in (raw_event(path='/lp?email=a@b.com'), raw_event(path='/lp#x'),
                      raw_event(kind='form_submit', data={'email': 'a@b.com'}),
                      raw_event(kind='form_submit', data={'valid': 'yes'})):
            with self.assertRaises(BadRequest):
                reports_supertag._event(event, self.site)
        stored = reports_supertag._event(raw_event(kind='form_submit', data={'form_id': 'contato', 'valid': False}), self.site)
        self.assertEqual(json.loads(stored[10]), {'form_id': 'contato', 'valid': False})


class ReportsSuperTagSettingsTest(SuperTagAppTest):
    def _patch(self, payload, config=None):
        current = {'id': SITE_ID, 'label': 'Site', 'allowed_host': 'example.test', 'config': config or {}, 'config_version': 1}
        captured = {}

        def answer(sql, params=()):
            if 'FOR UPDATE' in sql:
                return [current]
            if sql.lstrip().startswith('UPDATE cadu_reports_supertag_sites'):
                captured['config'] = json.loads(params[2])
                return [{'id': SITE_ID, 'public_id': 'abc', 'label': 'Site', 'allowed_host': 'example.test', 'enabled': True,
                         'config': captured['config'], 'config_version': 2, 'created_at': None, 'updated_at': None, 'revoked_at': None}]
            return []
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        with mock.patch.object(reports_supertag, '_selection', return_value={'client_id': 7, 'role': 'admin'}), \
                mock.patch.object(reports_supertag, '_write_guard'), \
                mock.patch.object(reports_supertag, 'get_db', return_value=FakeDb()), \
                mock.patch.object(reports_supertag, '_rows', side_effect=answer):
            response = self.client.patch(f'/connect/api/v2/reports/supertag/sites/{SITE_ID}', json=payload)
        return response, captured

    def test_consent_mode_is_no_longer_a_setting(self):
        response, _ = self._patch({'consent_mode': 'manual'})
        self.assertEqual(response.status_code, 400)

    def test_saving_rules_drops_old_consent_keys_and_snippet_has_no_consent(self):
        response, captured = self._patch(
            {'conversion_rules': [{'type': 'path', 'match': 'exact', 'value': '/obrigado'}],
             'form_capture': {'fields': ['empresa'], 'confirm': 'valid_submit'}},
            config={'consent_mode': 'manual', 'consent_required': True, 'retention_days': 365})
        self.assertNotIn('consent_mode', captured['config'])
        self.assertNotIn('consent_required', captured['config'])
        self.assertEqual(captured['config']['conversion_rules'], [{'type': 'path', 'match': 'exact', 'value': '/obrigado'}])
        self.assertEqual(captured['config']['form_capture'], {'fields': ['empresa'], 'confirm': 'valid_submit'})
        self.assertNotIn('consent', response.get_json()['site']['snippet'])


class ReportsSuperTagSiteCustomerTest(SuperTagAppTest):
    """Every site belongs to a client (advertiser) once the account has any active one."""

    def _call(self, method, path, payload, has_customers=True, site_customer=None):
        created = []

        def answer(sql, params=()):
            if 'FROM cadu_reports_customers' in sql:
                return [{'id': 1}] if has_customers else []
            if 'FROM cadu_reports_supertag_sites' in sql and 'FOR UPDATE' in sql:
                return [{'id': SITE_ID, 'label': 'Site', 'allowed_host': 'example.test', 'config': {}, 'config_version': 1, 'customer_id': site_customer}]
            return []
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        with mock.patch.object(reports_supertag, '_selection', return_value={'client_id': 7, 'role': 'admin'}), \
                mock.patch.object(reports_supertag, '_write_guard'), \
                mock.patch.object(reports_supertag, 'get_db', return_value=FakeDb()), \
                mock.patch.object(reports_supertag, '_customer_id', side_effect=lambda _selected, value: int(value) if value else None), \
                mock.patch.object(reports_supertag, 'ensure_supertag_site', side_effect=lambda *a: created.append(a) or ({'id': SITE_ID, 'customer_id': None}, True)), \
                mock.patch.object(reports_supertag, '_rows', side_effect=answer):
            response = getattr(self.client, method)(path, json=payload)
        return response, created

    def test_create_without_client_is_refused_when_clients_exist(self):
        response, created = self._call('post', '/connect/api/v2/reports/supertag/sites', {'label': 'Site', 'allowed_host': 'example.test'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('cliente', response.get_json()['description'] if response.is_json else response.get_data(as_text=True))
        self.assertEqual(created, [])

    def test_create_without_client_is_allowed_when_the_account_has_none(self):
        response, created = self._call('post', '/connect/api/v2/reports/supertag/sites', {'label': 'Site', 'allowed_host': 'example.test'}, has_customers=False)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(created), 1)

    def test_create_with_client_links_it(self):
        response, created = self._call('post', '/connect/api/v2/reports/supertag/sites', {'label': 'Site', 'allowed_host': 'example.test', 'customer_id': 1})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['site']['customer_id'], 1)

    def test_site_cannot_be_unlinked_from_its_client(self):
        response, _ = self._call('patch', f'/connect/api/v2/reports/supertag/sites/{SITE_ID}', {'customer_id': None}, site_customer=1)
        self.assertEqual(response.status_code, 400)
