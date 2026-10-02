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

    def create(self, role='admin', access_scope='all'):
        with self.client.session_transaction() as session:
            session['user_id'] = 42
            session['family_csrf'] = 'csrf-test'
        selected = {'organization_id': 23, 'client_id': 1000000000, 'client_name': 'Reports atual',
                    'role': role, 'access_scope': access_scope, 'client_kind': 'reports'}
        created = [{'id': 1000000010, 'name': 'Cliente novo', 'slug': 'cliente-novo', 'status': 'active'}]
        connection = mock.MagicMock()
        with mock.patch.object(reports_access, 'get_db', return_value=connection), \
             mock.patch('aicentralv2.cadu_connect.reports_v1._selection', return_value=selected), \
             mock.patch('aicentralv2.cadu_connect.reports_v1._write_guard') as write_guard, \
             mock.patch('aicentralv2.cadu_connect.reports_v1._rows', return_value=created) as rows:
            response = self.client.post('/api/v2/reports/customers', json={
                'client_id': 1000000000, 'name': 'Cliente novo',
            }, headers={'X-CSRF-Token': 'csrf-test'})
        return response, connection, write_guard, rows

    def test_reports_admin_can_create_a_customer(self):
        response, connection, write_guard, rows = self.create('admin')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['customer']['id'], 1000000010)
        self.assertEqual(rows.call_args.args[1][1:3], ('Cliente novo', 'cliente-novo'))
        connection.commit.assert_called_once()
        write_guard.assert_called_once()

    def test_viewer_cannot_create_a_customer(self):
        response, connection, write_guard, rows = self.create('viewer')
        self.assertEqual(response.status_code, 403)
        rows.assert_not_called()
        connection.commit.assert_not_called()
        write_guard.assert_not_called()

    def test_an_admin_limited_to_some_customers_cannot_create_one(self):
        response, connection, write_guard, rows = self.create('admin', access_scope='selected')
        self.assertEqual(response.status_code, 403)
        rows.assert_not_called()


if __name__ == '__main__':
    import unittest
    unittest.main()
