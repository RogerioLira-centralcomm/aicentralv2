from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace import routes as workspace_routes


def _client():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(workspace_routes.bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, cliente_id=12, user_type='admin')
    return client


def _db(rows):
    cursor = mock.MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = list(rows)
    connection = mock.MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


class ProjectOwnedTest(TestCase):
    def test_project_image_checks_ownership_without_assembling_the_dossier(self):
        connection, cursor = _db([{'ok': 1}, {'file_bytes': b'png', 'mime': 'image/png', 'title': 'x'}])
        with mock.patch.object(workspace_routes, 'get_db', return_value=connection), \
                mock.patch.object(workspace_routes, '_workspace_project', side_effect=AssertionError('dossiê inteiro')) as dossier:
            response = _client().get('/workspace/app/projetos/00000000-0000-0000-0000-000000000001/imagens/5')
        self.assertEqual(response.status_code, 200)
        dossier.assert_not_called()
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn('id_cliente', cursor.execute.call_args_list[0].args[0])

    def test_project_of_another_client_is_a_404(self):
        connection, _cursor = _db([None])
        with mock.patch.object(workspace_routes, 'get_db', return_value=connection):
            response = _client().get('/workspace/app/projetos/00000000-0000-0000-0000-000000000001/imagens/5')
        self.assertEqual(response.status_code, 404)

    def test_database_error_denies_instead_of_allowing(self):
        connection = mock.MagicMock()
        connection.cursor.side_effect = RuntimeError('db')
        app = Flask(__name__)
        with app.app_context(), mock.patch.object(workspace_routes, 'get_db', return_value=connection):
            self.assertFalse(workspace_routes._project_owned(12, 'x'))


class EditableProjectQueuesReconciliationTest(TestCase):
    def test_mutating_routes_queue_one_resource_event_through_the_editable_guard(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY='test', TESTING=True)
        with app.test_request_context('/x', method='POST'):
            from flask import session
            session.update(user_id=7, cliente_id=12)
            with mock.patch.object(workspace_routes, '_workspace_project', return_value={'id': 'p1', 'status': 'ativo'}), \
                    mock.patch.object(workspace_routes.project_resource_service, 'notify_change') as notify:
                project = workspace_routes._editable_workspace_project(12, 'p1')
        self.assertEqual(project['id'], 'p1')
        notify.assert_called_once_with(12, 'ci:p1', 'workspace_write', actor_id=7)

    def test_a_failure_to_queue_never_blocks_the_edit(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY='test', TESTING=True)
        with app.test_request_context('/x', method='POST'):
            from flask import session
            session.update(user_id=7, cliente_id=12)
            with mock.patch.object(workspace_routes, '_workspace_project', return_value={'id': 'p1', 'status': 'ativo'}), \
                    mock.patch.object(workspace_routes.project_resource_service, 'notify_change', side_effect=RuntimeError('db')):
                self.assertEqual(workspace_routes._editable_workspace_project(12, 'p1')['id'], 'p1')

    def test_archived_project_is_not_queued(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY='test', TESTING=True)
        with app.test_request_context('/x', method='POST'):
            from werkzeug.exceptions import Conflict
            with mock.patch.object(workspace_routes, '_workspace_project', return_value={'id': 'p1', 'status': 'arquivado'}), \
                    mock.patch.object(workspace_routes.project_resource_service, 'notify_change') as notify:
                with self.assertRaises(Conflict):
                    workspace_routes._editable_workspace_project(12, 'p1')
        notify.assert_not_called()
