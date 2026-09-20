from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import bp


def _client():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, cliente_id=12, user_type='admin', family_csrf='known-token')
    return client


class WorkspaceDockTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.routes._authorized_dock_target', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes._dock_shortcuts_available', return_value=True)
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_save_shortcut_uses_idempotent_conflict_without_named_constraint(self, get_db, _available, _authorized):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {
            'id': 'shortcut-1', 'shortcut_type': 'project', 'target_ref': 'ci:p-1',
            'project_ref': 'ci:p-1', 'brand_ref': None, 'position': 0, 'metadata': {},
        }
        get_db.return_value = connection

        response = _client().post('/workspace/api/dock/shortcuts', json={
            'shortcut_type': 'project', 'target_ref': 'ci:p-1', 'project_ref': 'ci:p-1',
        }, headers={'X-CSRF-Token': 'known-token'})

        self.assertEqual(response.status_code, 201)
        insert_sql = cursor.execute.call_args.args[0]
        self.assertIn('ON CONFLICT DO UPDATE', insert_sql)
        self.assertNotIn('ON CONFLICT (client_id,user_id,shortcut_type,target_ref)', insert_sql)
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes._dock_shortcuts_available', return_value=True)
    def test_reorder_rejects_unhashable_ids_as_bad_request(self, _available):
        response = _client().post('/workspace/api/dock/shortcuts/order', json={'ids': [{}]}, headers={'X-CSRF-Token': 'known-token'})
        self.assertEqual(response.status_code, 400)

    @mock.patch('aicentralv2.cadu_workspace.routes._authorized_dock_target', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes._dock_shortcuts_available', return_value=True)
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_save_rolls_back_and_returns_service_unavailable_on_database_failure(self, get_db, _available, _authorized):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = RuntimeError('database failure')
        get_db.return_value = connection

        response = _client().post('/workspace/api/dock/shortcuts', json={
            'shortcut_type': 'project', 'target_ref': 'ci:p-1',
        }, headers={'X-CSRF-Token': 'known-token'})

        self.assertEqual(response.status_code, 503)
        connection.rollback.assert_called_once_with()
