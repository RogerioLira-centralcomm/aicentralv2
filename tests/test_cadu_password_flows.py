from unittest import TestCase, mock

from flask import Flask, get_flashed_messages, jsonify, session

from aicentralv2 import db
from aicentralv2.routes import init_routes


USER = {'id_contato_cliente': 7, 'pk_id_tbl_cliente': 12, 'email': 'pessoa@cliente.test',
        'nome_completo': 'Pessoa', 'status': True, 'user_type': 'client'}


class PasswordFlowTest(TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY='local-test', TESTING=True,
            AUTH_URL='https://auth.centralcomm.media', WORKSPACE_URL='https://workspace.centralcomm.media',
            STUDIO_URL='https://studio.centralcomm.media', CENTRALX_URL='https://ai.centralcomm.media',
            CADU_URL='https://cadu.centralcomm.media', CADU_GOOGLE_NATIVE_ENABLED=True,
            SESSION_COOKIE_DOMAIN='centralcomm.media', SESSION_COOKIE_SECURE=True)
        init_routes(self.app)
        self.app.add_url_rule('/test-session', 'test_session', lambda: jsonify(user=session.get('user_id')))
        self.client = self.app.test_client()
        renderer = mock.patch('aicentralv2.routes.render_template', side_effect=lambda *a, **k: jsonify(messages=get_flashed_messages()))
        renderer.start(); self.addCleanup(renderer.stop)
        guard = mock.patch('aicentralv2.db.get_db', side_effect=AssertionError('Real database access forbidden'))
        guard.start(); self.addCleanup(guard.stop)

    def post(self, path, values):
        return self.client.post(path, data=values, base_url='https://auth.centralcomm.media')

    def test_customer_password_login_returns_to_studio_without_php(self):
        with mock.patch('aicentralv2.routes.db.verificar_credenciais', return_value=USER) as verify, \
             mock.patch('aicentralv2.routes.db.obter_cliente_por_id', return_value={'nome_fantasia': 'Cliente', 'status': True}):
            result = self.post('/login', {'email': USER['email'], 'password': 'test-password', 'next': 'https://studio.centralcomm.media/'})
        self.assertEqual(result.location, 'https://studio.centralcomm.media/')
        verify.assert_called_once_with(USER['email'], 'test-password')
        self.assertEqual(self.client.get('/test-session', base_url='https://studio.centralcomm.media').json['user'], 7)

    def test_inactive_organization_cannot_start_session(self):
        with mock.patch('aicentralv2.routes.db.verificar_credenciais', return_value=USER), \
             mock.patch('aicentralv2.routes.db.obter_cliente_por_id', return_value={'nome_fantasia': 'Cliente', 'status': False}):
            self.post('/login', {'email': USER['email'], 'password': 'test-password'})
        self.assertIsNone(self.client.get('/test-session', base_url='https://auth.centralcomm.media').json['user'])

    def test_logout_removes_identity_for_other_products(self):
        with self.client.session_transaction(base_url='https://auth.centralcomm.media') as current:
            current.update(user_id=7, family_context={'client_id': 12})
        result = self.client.get('/logout', base_url='https://studio.centralcomm.media')
        self.assertEqual(result.location, 'https://auth.centralcomm.media/login')
        for product in ('workspace', 'studio', 'planner', 'connect', 'skills'):
            self.assertIsNone(self.client.get('/test-session', base_url=f'https://{product}.centralcomm.media').json['user'])

    def test_recovery_has_same_visible_response_for_unknown_inactive_and_active(self):
        messages = []
        for contact in (None, {**USER, 'status': False}, USER):
            with mock.patch('aicentralv2.routes.db.obter_contato_por_email', return_value=contact), \
                 mock.patch('aicentralv2.routes.db.atualizar_reset_token'), \
                 mock.patch('aicentralv2.routes.send_password_reset_email') as send:
                result = self.post('/forgot-password', {'email': USER['email']})
                messages.append(result.json['messages'])
                if contact and contact['status']:
                    self.assertTrue(send.call_args.kwargs['reset_link'].startswith('https://auth.centralcomm.media/reset-password/'))
                else:
                    send.assert_not_called()
        self.assertEqual(messages[0], messages[1])
        self.assertEqual(messages[1], messages[2])

    def test_reset_token_consumed_in_parallel_cannot_change_password_or_send_email(self):
        with mock.patch('aicentralv2.routes.db.buscar_contato_por_token', return_value=USER), \
             mock.patch('aicentralv2.routes.db.gerar_senha_hash', return_value='hash'), \
             mock.patch('aicentralv2.routes.db.redefinir_senha_por_token', return_value=None) as reset, \
             mock.patch('aicentralv2.routes.send_password_changed_email') as send:
            result = self.post('/reset-password/test-token', {'password': 'long-test-password', 'confirm_password': 'long-test-password'})
            self.assertEqual(result.location, '/forgot-password')
            reset.assert_called_once_with('test-token', 'hash')
            send.assert_not_called()

    def test_reset_preserves_spaces_and_only_notifies_after_success(self):
        password = ' test-password '
        with mock.patch('aicentralv2.routes.db.buscar_contato_por_token', return_value=USER), \
             mock.patch('aicentralv2.routes.db.gerar_senha_hash', return_value='hash') as hash_password, \
             mock.patch('aicentralv2.routes.db.redefinir_senha_por_token', return_value=USER), \
             mock.patch('aicentralv2.routes.send_password_changed_email') as send:
            result = self.post('/reset-password/test-token', {'password': password, 'confirm_password': password})
            hash_password.assert_called_once_with(password)
            self.assertEqual(result.location, '/login')
            send.assert_called_once()

    def test_atomic_reset_rechecks_token_expiry_and_account_status(self):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = USER
        with mock.patch('aicentralv2.db.get_db', return_value=connection):
            self.assertEqual(db.redefinir_senha_por_token('token', 'hash'), USER)
        sql, values = cursor.execute.call_args.args
        self.assertEqual(values, ('hash', 'token'))
        for constraint in ('c.reset_token = %s', 'c.reset_token_expires > NOW()', 'c.status = TRUE', 'cli.status = TRUE', 'RETURNING'):
            self.assertIn(constraint, sql)
        connection.commit.assert_called_once()

    def test_atomic_reset_rolls_back_on_failure(self):
        connection = mock.MagicMock()
        connection.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError('failed')
        with mock.patch('aicentralv2.db.get_db', return_value=connection):
            with self.assertRaises(RuntimeError):
                db.redefinir_senha_por_token('token', 'hash')
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()

    def test_expired_token_and_mismatching_password_never_write(self):
        with mock.patch('aicentralv2.routes.db.buscar_contato_por_token', return_value=None), \
             mock.patch('aicentralv2.routes.db.redefinir_senha_por_token') as reset:
            result = self.post('/reset-password/expired', {'password': 'long-password', 'confirm_password': 'long-password'})
            self.assertEqual(result.location, '/forgot-password')
            reset.assert_not_called()
        with mock.patch('aicentralv2.routes.db.buscar_contato_por_token', return_value=USER), \
             mock.patch('aicentralv2.routes.db.redefinir_senha_por_token') as reset:
            self.post('/reset-password/token', {'password': 'long-password', 'confirm_password': 'different'})
            reset.assert_not_called()
