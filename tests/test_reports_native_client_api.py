from unittest import TestCase, mock

from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_access


class ReportsNativeClientApiTest(TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = 'reports-native-client-test'
        blueprint = Blueprint('reports_native_client_test', __name__)
        reports_access.register(blueprint)
        app.register_blueprint(blueprint)
        self.client = app.test_client()

    def create(self, role='admin'):
        with self.client.session_transaction() as session:
            session['user_id'] = 42
            session['family_csrf'] = 'csrf-test'
        selected = {'organization_id': 23, 'client_id': 1000000000,
                    'client_name': 'Reports atual', 'role': role, 'client_kind': 'reports'}
        cursor = mock.MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = {'id': 1000000010, 'name': 'Cliente novo',
                                        'slug': 'cliente-novo', 'status': 'active'}
        connection = mock.MagicMock()
        connection.cursor.return_value = cursor
        with mock.patch.object(reports_access, 'get_db', return_value=connection), \
             mock.patch('aicentralv2.cadu_connect.reports_v1._selection', return_value=selected), \
             mock.patch('aicentralv2.cadu_connect.reports_v1._write_guard') as write_guard, \
             mock.patch.object(reports_access.context, 'require_admin', side_effect=AssertionError('CRM admin guard called')):
            response = self.client.post('/api/v1/reports/clients', json={
                'client_id': 1000000000, 'name': 'Cliente novo',
            }, headers={'X-CSRF-Token': 'csrf-test'})
        return response, connection, write_guard

    def test_reports_admin_can_create_native_client_without_crm_admin_dependency(self):
        response, connection, write_guard = self.create('admin')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['client']['id'], 1000000010)
        connection.commit.assert_called_once()
        write_guard.assert_called_once()

    def test_viewer_cannot_create_native_client(self):
        response, connection, write_guard = self.create('viewer')
        self.assertEqual(response.status_code, 403)
        connection.cursor.assert_not_called()
        write_guard.assert_not_called()


if __name__ == '__main__':
    import unittest
    unittest.main()
