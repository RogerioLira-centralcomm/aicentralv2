from unittest import TestCase, mock

from flask import jsonify, session
import requests

from tests.test_product_portals import _app
from aicentralv2.cadu_identity.routes import _resolve_google_user
from aicentralv2.cadu_identity.google_oidc import GoogleLoginError, exchange_code


USER = {'id_contato_cliente': 7, 'pk_id_tbl_cliente': 12, 'email': 'pessoa@cliente.test',
        'nome_completo': 'Pessoa', 'status': True, 'cliente_status': True, 'user_type': 'client'}


class NativeIdentityTest(TestCase):
    def setUp(self):
        self.app = _app()
        self.app.config.update(CADU_GOOGLE_NATIVE_ENABLED=True, SESSION_COOKIE_SECURE=True,
                               SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
        self.app.add_url_rule('/test-session', 'test_session', lambda: jsonify(user=session.get('user_id')))
        self.client = self.app.test_client()

    def test_google_start_uses_native_cadu_provider(self):
        with mock.patch('aicentralv2.cadu_identity.routes.google_authorization_url', return_value='https://accounts.google.com/oauth') as authorize:
            response = self.client.get('/auth/google?next=https://studio.centralcomm.media/', base_url='https://auth.centralcomm.media')
            self.assertEqual(response.location, 'https://accounts.google.com/oauth')
            authorize.assert_called_once_with('cadu')

    def test_callback_rotates_session_and_shares_cookie_between_products(self):
        with self.client.session_transaction(base_url='https://auth.centralcomm.media') as current:
            current['google_auth_next'] = 'https://studio.centralcomm.media/'
            current['family_context'] = {'client_id': 999}
        with mock.patch('aicentralv2.cadu_identity.routes.exchange_code', return_value={'realm': 'cadu', 'email': USER['email'], 'sub': 'google-user'}), \
             mock.patch('aicentralv2.cadu_identity.routes.db.obter_contato_por_email', return_value=USER), \
             mock.patch('aicentralv2.cadu_identity.routes.db.obter_contato_por_id', return_value=USER), \
             mock.patch('aicentralv2.cadu_identity.routes.db.obter_cliente_por_id', return_value={'nome_fantasia': 'Cliente'}), \
             mock.patch('aicentralv2.cadu_identity.routes.db.get_db') as database:
            response = self.client.get('/auth/google/callback?code=test&state=test', base_url='https://auth.centralcomm.media')
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.location, 'https://studio.centralcomm.media/')
            database.assert_not_called()
        cookie = response.headers['Set-Cookie']
        for attribute in ('Domain=centralcomm.media', 'Secure', 'HttpOnly', 'SameSite=Lax'):
            self.assertIn(attribute, cookie)
        for product in ('workspace', 'studio', 'planner', 'connect', 'skills'):
            self.assertEqual(self.client.get('/test-session', base_url=f'https://{product}.centralcomm.media').json['user'], 7)
        self.assertIsNone(self.client.get('/test-session', base_url='https://unrelated.test').json['user'])
        with self.client.session_transaction(base_url='https://auth.centralcomm.media') as current:
            self.assertNotIn('family_context', current)

    def test_existing_account_and_active_organization_required(self):
        with self.app.app_context():
            for user in (None, {**USER, 'status': False}, {**USER, 'cliente_status': False}):
                with mock.patch('aicentralv2.cadu_identity.routes.db.obter_contato_por_email', return_value=USER), \
                     mock.patch('aicentralv2.cadu_identity.routes.db.obter_contato_por_id', return_value=user):
                    with self.assertRaises(GoogleLoginError):
                        _resolve_google_user({'realm': 'cadu', 'email': USER['email']})

    def test_network_failure_is_a_safe_login_error(self):
        with self.app.test_request_context('/'):
            session.update(google_auth_state='state', google_auth_nonce='nonce', google_auth_pkce='verifier', google_auth_realm='cadu')
            with mock.patch('aicentralv2.cadu_identity.google_oidc._configuration', return_value={'client_id': 'id', 'client_secret': 'secret', 'redirect_uri': 'https://auth.centralcomm.media/auth/google/callback'}), \
                 mock.patch('aicentralv2.cadu_identity.google_oidc.requests.post', side_effect=requests.Timeout('sensitive details')):
                with self.assertRaisesRegex(GoogleLoginError, 'conectar ao Google'):
                    exchange_code('code', 'state')
            self.assertNotIn('google_auth_state', session)
