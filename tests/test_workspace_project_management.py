from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import bp


def _client():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, user_type='admin', cliente_id=12, family_csrf='known-token')
    return client


class WorkspaceProjectManagementTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'source', 'nome': 'Projeto antigo'})
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_delete_requires_the_exact_project_name(self, get_db, _project):
        response = _client().post('/workspace/app/projetos/source/excluir', data={'_csrf': 'known-token', 'confirmation_name': 'outro nome'})
        self.assertEqual(response.status_code, 400)
        get_db.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'source', 'nome': 'Projeto antigo'})
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_delete_is_tenant_scoped_and_committed(self, get_db, _project):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        get_db.return_value = connection
        response = _client().post('/workspace/app/projetos/source/excluir', data={'_csrf': 'known-token', 'confirmation_name': 'Projeto antigo'})
        self.assertEqual(response.status_code, 303)
        sql, params = cursor.execute.call_args.args
        self.assertIn('id_cliente = %s', sql)
        self.assertEqual(params, ('source', 12))
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', side_effect=[
        {'id': 'source', 'nome': 'Antigo', 'status': 'ativo'}, {'id': 'target', 'nome': 'Atual', 'status': 'ativo'},
    ])
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_merge_moves_every_project_scope_and_preserves_target_brand(self, get_db, _projects):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'table_name': 'available'}
        get_db.return_value = connection
        response = _client().post('/workspace/app/projetos/source/mesclar', data={'_csrf': 'known-token', 'target_project_id': 'target'})
        self.assertEqual(response.status_code, 303)
        statements = '\n'.join(str(call.args[0]) for call in cursor.execute.call_args_list)
        for table in ('cadu_family_project_access', 'cadu_family_project_visibility', 'cadu_workspace_ingestion_sessions',
                      'cadu_project_index_jobs', 'google_workspace_resource_links', 'cadu_user_memories',
                      'cadu_working_memories', 'cadu_workspace_dock_shortcuts'):
            self.assertIn(table, statements)
        self.assertIn('NOT EXISTS (SELECT 1 FROM cadu_family_project_brands existing', statements)
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', side_effect=[
        {'id': 'source', 'nome': 'Antigo', 'status': 'ativo'}, {'id': 'target', 'nome': 'Atual', 'status': 'ativo'},
    ])
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_merge_rolls_back_everything_on_database_failure(self, get_db, _projects):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = RuntimeError('database unavailable')
        get_db.return_value = connection
        response = _client().post('/workspace/app/projetos/source/mesclar', data={'_csrf': 'known-token', 'target_project_id': 'target'})
        self.assertEqual(response.status_code, 503)
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
