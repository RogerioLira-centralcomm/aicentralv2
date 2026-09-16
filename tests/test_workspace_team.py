from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import bp


def _client(role='admin'):
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(
            user_id=7, cliente_id=12, family_csrf='known-token', user_name='Apolo',
            user_type=role,
        )
    return client


class WorkspaceTeamTest(TestCase):
    @mock.patch('aicentralv2.db.criar_invite')
    def test_member_cannot_manage_invites(self, create):
        response = _client('client').post('/workspace/app/equipe/convites', data={
            '_csrf': 'known-token', 'email': 'pessoa@example.com', 'role': 'member',
        })
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    @mock.patch('aicentralv2.db.criar_invite')
    def test_invite_requires_csrf(self, create):
        response = _client().post('/workspace/app/equipe/convites', data={
            'email': 'pessoa@example.com', 'role': 'member',
        })
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    @mock.patch('aicentralv2.email_service.send_invite_email', return_value={'success': True})
    @mock.patch('aicentralv2.db.obter_planos_clientes', return_value=[])
    @mock.patch('aicentralv2.db.obter_invite_por_id', return_value={
        'id': 44, 'id_cliente': 12, 'invite_token': 'token', 'expires_at': 'soon',
    })
    @mock.patch('aicentralv2.db.criar_invite', return_value=44)
    @mock.patch('aicentralv2.db.verificar_convite_pendente', return_value=None)
    def test_invite_uses_active_organization(self, pending, create, _invite, _plans, send):
        response = _client().post('/workspace/app/equipe/convites', data={
            '_csrf': 'known-token', 'email': 'Pessoa@Example.com', 'role': 'admin',
        })
        self.assertEqual(response.status_code, 303)
        pending.assert_called_once_with('pessoa@example.com', 12)
        create.assert_called_once_with(12, 7, 'pessoa@example.com', 'admin')
        send.assert_called_once()

    @mock.patch('aicentralv2.db.cancelar_invite')
    @mock.patch('aicentralv2.email_service.send_invite_email', return_value={'success': False, 'error': 'provider'})
    @mock.patch('aicentralv2.db.obter_planos_clientes', return_value=[])
    @mock.patch('aicentralv2.db.obter_invite_por_id', return_value={
        'id': 44, 'id_cliente': 12, 'invite_token': 'token', 'expires_at': 'soon',
    })
    @mock.patch('aicentralv2.db.criar_invite', return_value=44)
    @mock.patch('aicentralv2.db.verificar_convite_pendente', return_value=None)
    def test_failed_delivery_cancels_new_invite(self, _pending, _create, _invite, _plans, _send, cancel):
        response = _client().post('/workspace/app/equipe/convites', data={
            '_csrf': 'known-token', 'email': 'pessoa@example.com', 'role': 'member',
        })
        self.assertEqual(response.status_code, 502)
        cancel.assert_called_once_with(44)

    @mock.patch('aicentralv2.db.reenviar_invite')
    @mock.patch('aicentralv2.db.obter_invite_por_id', return_value={
        'id': 44, 'id_cliente': 99, 'status': 'pending',
    })
    def test_foreign_invite_cannot_be_resent(self, _invite, resend):
        response = _client().post('/workspace/app/equipe/convites/44/reenviar', data={
            '_csrf': 'known-token',
        })
        self.assertEqual(response.status_code, 404)
        resend.assert_not_called()

    @mock.patch('aicentralv2.db.cancelar_invite')
    @mock.patch('aicentralv2.db.obter_invite_por_id', return_value={
        'id': 44, 'id_cliente': 99, 'status': 'pending',
    })
    def test_foreign_invite_cannot_be_cancelled(self, _invite, cancel):
        response = _client().post('/workspace/app/equipe/convites/44/cancelar', data={
            '_csrf': 'known-token',
        })
        self.assertEqual(response.status_code, 404)
        cancel.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_role_update_is_scoped_to_active_organization(self, get_db):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            {'id_contato_cliente': 9, 'status': True, 'user_type': 'client'},
            {'id_contato_cliente': 9},
        ]
        get_db.return_value = connection
        response = _client().post('/workspace/app/equipe/9/papel', data={
            '_csrf': 'known-token', 'role': 'readonly',
        })
        self.assertEqual(response.status_code, 303)
        update_sql, update_params = cursor.execute.call_args_list[-1].args
        self.assertIn('pk_id_tbl_cliente = %s', update_sql)
        self.assertEqual(update_params, ('readonly', 9, 12))
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_last_active_admin_cannot_be_deactivated(self, get_db):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            {'id_contato_cliente': 9, 'status': True, 'user_type': 'admin'},
            {'total': 1},
        ]
        get_db.return_value = connection
        response = _client().post('/workspace/app/equipe/9/status', data={
            '_csrf': 'known-token',
        })
        self.assertEqual(response.status_code, 409)
        connection.rollback.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_user_cannot_deactivate_self(self, get_db):
        response = _client().post('/workspace/app/equipe/7/status', data={
            '_csrf': 'known-token',
        })
        self.assertEqual(response.status_code, 409)
        get_db.assert_not_called()
