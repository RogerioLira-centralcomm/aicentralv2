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
            user_id=7, cliente_id=12, family_csrf='known-token',
            user_name='Nome antigo', user_type=role,
        )
    return client


class WorkspaceSettingsTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_profile_update_is_scoped_to_signed_in_user_and_organization(self, get_db):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id_contato_cliente': 7}
        get_db.return_value = connection
        client = _client()

        response = client.post('/workspace/app/perfil', data={
            '_csrf': 'known-token', 'name': 'Apolo Lira', 'phone': '(11) 99999-9999',
        })

        self.assertEqual(response.status_code, 303)
        sql, params = cursor.execute.call_args.args
        self.assertIn('id_contato_cliente = %s AND pk_id_tbl_cliente = %s', sql)
        self.assertEqual(params, ('Apolo Lira', '(11) 99999-9999', 'badge-ribbon.png', 7, 12))
        connection.commit.assert_called_once_with()
        with client.session_transaction() as session:
            self.assertEqual(session['user_name'], 'Apolo Lira')
            self.assertEqual(session['cadu_avatar_badge'], 'badge-ribbon.png')

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_profile_update_rejects_unknown_avatar_badge(self, get_db):
        response = _client().post('/workspace/app/perfil', data={
            '_csrf': 'known-token', 'name': 'Apolo Lira', 'phone': '',
            'avatar_badge': '../../nao-e-um-selo.png',
        })
        self.assertEqual(response.status_code, 400)
        get_db.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_profile_update_rejects_invalid_phone_before_database(self, get_db):
        response = _client().post('/workspace/app/perfil', data={
            '_csrf': 'known-token', 'name': 'Apolo Lira', 'phone': '<script>',
        })
        self.assertEqual(response.status_code, 400)
        get_db.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_member_cannot_change_organization(self, get_db):
        response = _client('client').post('/workspace/app/organizacao', data={
            '_csrf': 'known-token', 'trade_name': 'Empresa',
        })
        self.assertEqual(response.status_code, 403)
        get_db.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_organization_update_validates_state_and_keeps_tenant_scope(self, get_db):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [{'id_estado': 25}, {'id_cliente': 12}]
        get_db.return_value = connection

        response = _client().post('/workspace/app/organizacao', data={
            '_csrf': 'known-token',
            'trade_name': 'CentralComm', 'legal_name': 'Central Comunicação Ltda',
            'document': '12.345.678/0001-90', 'postal_code': '01.234-567',
            'street': 'Rua Exemplo', 'number': '10', 'complement': '5º andar',
            'district': 'Centro', 'city': 'São Paulo', 'state': 'SP',
        })

        self.assertEqual(response.status_code, 303)
        state_sql, state_params = cursor.execute.call_args_list[0].args
        update_sql, update_params = cursor.execute.call_args_list[1].args
        self.assertIn('tbl_estado', state_sql)
        self.assertEqual(state_params, ('SP',))
        self.assertIn('WHERE id_cliente = %s', update_sql)
        self.assertEqual(update_params[-1], 12)
        self.assertEqual(update_params[2], '12345678000190')
        self.assertEqual(update_params[3], '01234567')
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_organization_update_requires_csrf(self, get_db):
        response = _client().post('/workspace/app/organizacao', data={
            'trade_name': 'Empresa',
        })
        self.assertEqual(response.status_code, 403)
        get_db.assert_not_called()
