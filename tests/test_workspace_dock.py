from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import _dock_appearance, _dock_external_url, bp


def _client():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, cliente_id=12, user_type='admin', family_csrf='known-token')
    return client


class WorkspaceDockTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.routes._user_home_preferences', side_effect=RuntimeError('preferences unavailable'))
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_common_dock_items', side_effect=RuntimeError('dock unavailable'))
    @mock.patch('aicentralv2.cadu_workspace.routes.credit_position', side_effect=RuntimeError('credits unavailable'))
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_onboarding_table_available', side_effect=RuntimeError('onboarding unavailable'))
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_projects', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brands', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.project_brand_links', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.project_resource_service.list_recent_resources', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes.render_template', return_value='workspace home')
    def test_home_render_survives_optional_database_failures(self, _render, _resources, _links,
                                                             _brands, _projects, _onboarding,
                                                             _credit, _dock, _preferences):
        response = _client().get('/app')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), 'workspace home')

    def test_dock_appearance_rejects_css_and_unknown_sizes(self):
        self.assertEqual(_dock_appearance({'background_color': '#AABBCC', 'icon_size': 'large'}),
                         {'background_color': '#aabbcc', 'icon_size': 'large'})
        self.assertEqual(_dock_appearance({'background_color': 'url(javascript:1)', 'icon_size': 'huge'}),
                         {'background_color': '', 'icon_size': 'medium'})

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_update_shortcut_persists_only_safe_appearance(self, get_db):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': '1', 'metadata': {'background_color': '#112233', 'icon_size': 'small'}}
        get_db.return_value = connection
        response = _client().patch('/workspace/api/dock/shortcuts/11111111-1111-1111-1111-111111111111',
                                   json={'background_color': '#112233', 'icon_size': 'small', 'css': 'bad'},
                                   headers={'X-CSRF-Token': 'known-token'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cursor.execute.call_args.args[1][0].obj,
                         {'background_color': '#112233', 'icon_size': 'small'})
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
        self.assertIn('ON CONFLICT (client_id,user_id,shortcut_type,target_ref) DO UPDATE', insert_sql)
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes._dock_shortcuts_available', return_value=True)
    def test_reorder_rejects_unhashable_ids_as_bad_request(self, _available):
        response = _client().post('/workspace/api/dock/shortcuts/order', json={'ids': [{}]}, headers={'X-CSRF-Token': 'known-token'})
        self.assertEqual(response.status_code, 400)

    @mock.patch('aicentralv2.cadu_workspace.routes._user_dock_shortcuts', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes._dock_shortcuts_available', return_value=True)
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_reorder_mixed_brand_and_project_preserves_unseen_shortcuts(self, get_db, _available, _shortcuts):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            {'id': 'link-shortcut'},
            {'id': 'brand-shortcut'},
            {'id': 'project-shortcut'},
        ]
        get_db.return_value = connection

        response = _client().post('/workspace/api/dock/shortcuts/order', json={
            'ids': ['project-shortcut', 'brand-shortcut'],
        }, headers={'X-CSRF-Token': 'known-token'})

        self.assertEqual(response.status_code, 200)
        updates = [call.args[1] for call in cursor.execute.call_args_list if 'SET position=' in call.args[0]]
        self.assertEqual([values[:2] for values in updates], [
            (0, 'link-shortcut'),
            (1, 'project-shortcut'),
            (2, 'brand-shortcut'),
        ])
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes._user_dock_shortcuts', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes._dock_shortcuts_available', return_value=True)
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_reorder_rejects_shortcuts_from_another_user(self, get_db, _available, _shortcuts):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [{'id': 'brand-shortcut'}]
        get_db.return_value = connection

        response = _client().post('/workspace/api/dock/shortcuts/order', json={
            'ids': ['foreign-shortcut'],
        }, headers={'X-CSRF-Token': 'known-token'})

        self.assertEqual(response.status_code, 400)
        connection.rollback.assert_called_once_with()

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

    def test_external_link_accepts_only_safe_https(self):
        self.assertEqual(_dock_external_url('https://trello.com/b/board'), 'https://trello.com/b/board')
        for value in ('javascript:alert(1)', 'http://gmail.com/', 'file:///tmp/a',
                      'https://user:secret@example.com/', 'https://example.com:444/',
                      'https://example.com/\nmalicious'):
            self.assertEqual(_dock_external_url(value), '')

    @mock.patch('aicentralv2.cadu_workspace.routes._dock_shortcuts_available', return_value=True)
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_external_link_is_saved_as_launch_only_shortcut(self, get_db, _available):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 'shortcut-1', 'shortcut_type': 'external', 'target_ref': 'hash',
                                        'project_ref': None, 'brand_ref': None, 'position': 0,
                                        'metadata': {'url': 'https://trello.com/b/board', 'title': 'Quadro'}}
        get_db.return_value = connection
        response = _client().post('/workspace/api/dock/shortcuts', json={
            'shortcut_type': 'external', 'url': 'https://trello.com/b/board', 'title': 'Quadro',
        }, headers={'X-CSRF-Token': 'known-token'})
        self.assertEqual(response.status_code, 201)
        values = cursor.execute.call_args.args[1]
        self.assertEqual(values[3], 'external')
        self.assertIsNone(values[5])
        self.assertIsNone(values[6])
        self.assertEqual(values[-1].obj['url'], 'https://trello.com/b/board')

    @mock.patch('aicentralv2.cadu_workspace.routes._dock_shortcuts_available', return_value=True)
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_capacity_is_enforced_by_api(self, get_db, _available):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'total': 32, 'already_saved': False}
        get_db.return_value = connection
        response = _client().post('/workspace/api/dock/shortcuts', json={
            'shortcut_type': 'external', 'url': 'https://trello.com/b/another', 'title': 'Outro quadro',
        }, headers={'X-CSRF-Token': 'known-token'})
        self.assertEqual(response.status_code, 409)
        connection.rollback.assert_called_once_with()
        self.assertNotIn('INSERT INTO cadu_workspace_dock_shortcuts',
                         '\n'.join(call.args[0] for call in cursor.execute.call_args_list))
