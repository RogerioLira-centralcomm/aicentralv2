from unittest import TestCase

from tests.test_product_portals import _app


class WorkspaceAccountRoutesTest(TestCase):
    def setUp(self):
        self.client = _app().test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, user_name='Apolo')

    def test_short_account_routes_are_canonical(self):
        for path in ('/uso', '/plano', '/equipe', '/perfil', '/faturas'):
            response = self.client.get(path, headers={'Host': 'workspace.centralcomm.media'})
            self.assertEqual(response.status_code, 200)

    def test_account_aliases_redirect_to_the_new_canonical_pages(self):
        for alias, canonical in (
            ('/conta', '/perfil'),
            ('/creditos', '/uso'),
            ('/planos', '/plano'),
            ('/faturamento', '/faturas'),
        ):
            response = self.client.get(f'{alias}?ref=sidebar', headers={'Host': 'workspace.centralcomm.media'})
            self.assertEqual(response.status_code, 308)
            self.assertTrue(response.headers['Location'].endswith(f'{canonical}?ref=sidebar'))

    def test_legacy_credit_url_redirects_to_short_route(self):
        response = self.client.get('/workspace/app/creditos?ref=sidebar', headers={'Host': 'workspace.centralcomm.media'})
        self.assertEqual(response.status_code, 308)
        self.assertTrue(response.headers['Location'].endswith('/uso?ref=sidebar'))
