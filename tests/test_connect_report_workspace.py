"""Rotas legadas do editor de relatórios do Connect.

O editor server-side foi substituído pelo app React do Reports (2f0e8db8a);
as URLs antigas só redirecionam e recusam escrita, sem tocar no banco.
"""
from unittest import TestCase

from tests.test_product_portals import _app


class ReportWorkspaceLegacyRedirectTests(TestCase):
    def setUp(self):
        self.app = _app()
        self.client = self.app.test_client()
        self.headers = {'Host': 'connect.centralcomm.media'}

    def login(self):
        with self.client.session_transaction(headers=self.headers) as sess:
            sess.update(user_id=1, family_csrf='test-token')

    def test_legacy_pages_require_login(self):
        for path in ('/connect/relatorios', '/connect/importacoes', '/connect/importacoes/3/resolver'):
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assertIn(response.status_code, (302, 401))
                self.assertNotIn('#reports', response.headers.get('Location', ''))
                self.assertNotIn('#imports', response.headers.get('Location', ''))

    def test_legacy_pages_redirect_to_react_reports(self):
        self.login()
        expected = {
            '/connect/relatorios': '#reports',
            '/connect/importacoes': '#imports',
            '/connect/importacoes/3/resolver': '#imports',
        }
        for path, anchor in expected.items():
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers['Location'].endswith(anchor))

    def test_legacy_writes_are_gone(self):
        self.login()
        for path in ('/connect/relatorios', '/connect/importacoes', '/connect/importacoes/3/resolver'):
            with self.subTest(path=path):
                response = self.client.post(path, headers=self.headers, data={'_csrf': 'test-token'})
                self.assertIn(response.status_code, (403, 410))
