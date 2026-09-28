from unittest import TestCase, mock

from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_supertag


class ReportsSuperTagConsentTest(TestCase):
    def setUp(self):
        app = Flask(__name__)
        bp = Blueprint('reports', __name__, url_prefix='/connect')
        reports_supertag.register(bp)
        app.register_blueprint(bp)
        self.client = app.test_client()
        self.site = {'id': 'site-id', 'public_id': 'public-id', 'allowed_host': 'example.test'}

    @mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
    def test_consent_preflight_is_allowed_for_the_configured_site(self, lookup):
        lookup.return_value = self.site
        response = self.client.options(
            '/connect/public/supertag/v1/public-id/consent',
            headers={'Origin': 'https://example.test',
                     'Access-Control-Request-Method': 'POST',
                     'Access-Control-Request-Headers': 'content-type'},
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://example.test')
        self.assertIn('POST', response.headers['Access-Control-Allow-Methods'])
        self.assertIn('Content-Type', response.headers['Access-Control-Allow-Headers'])

    @mock.patch('aicentralv2.cadu_connect.reports_supertag._site_by_public_id')
    def test_consent_choice_is_acknowledged_without_setting_a_cross_domain_cookie(self, lookup):
        lookup.return_value = self.site
        response = self.client.post(
            '/connect/public/supertag/v1/public-id/consent',
            headers={'Origin': 'https://example.test'},
            json={'analytics': False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'analytics': False})
        self.assertNotIn('Set-Cookie', response.headers)
