from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import bp


def _client():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, cliente_id=12, family_csrf='known-token')
    return client


class WorkspaceProjectLifecycleTest(TestCase):
    def test_legacy_project_redirect_preserves_the_requested_view(self):
        response = _client().get('/workspace/app/projetos/p-1?legacy=1')
        self.assertEqual(response.status_code, 308)
        self.assertEqual(response.headers['Location'], '/projetos/p-1?legacy=1')

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_project_creation_requires_csrf(self, get_db):
        response = _client().post('/workspace/app/projetos', data={'name': 'Projeto novo'})
        self.assertEqual(response.status_code, 403)
        get_db.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.uuid4', return_value='project-1')
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_project_is_created_inside_active_organization(self, get_db, _uuid):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        get_db.return_value = connection
        response = _client().post('/workspace/app/projetos', data={
            '_csrf': 'known-token', 'name': 'Projeto novo',
            'description': 'Contexto inicial', 'instructions': 'Use dados aprovados.',
        })
        self.assertEqual(response.status_code, 303)
        sql, params = cursor.execute.call_args.args
        self.assertIn('INSERT INTO cadu_ci_projetos', sql)
        self.assertEqual(params[:3], ('project-1', 12, 7))
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_context_update_keeps_tenant_predicate(self, get_db, _project):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        get_db.return_value = connection
        response = _client().post('/workspace/app/projetos/p-1/contexto', data={
            '_csrf': 'known-token', 'name': 'Projeto revisado', 'color': '#176b5e',
        })
        self.assertEqual(response.status_code, 303)
        sql, params = cursor.execute.call_args.args
        self.assertIn('id_cliente = %s', sql)
        self.assertEqual(params[-2:], ('p-1', 12))

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value=None)
    def test_foreign_project_cannot_change_status(self, _project, get_db):
        response = _client().post('/workspace/app/projetos/foreign/status', data={
            '_csrf': 'known-token',
        })
        self.assertEqual(response.status_code, 404)
        get_db.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={
        'id': 'p-1', 'status': 'arquivado',
    })
    def test_archived_project_is_read_only_until_reactivated(self, _project, get_db):
        response = _client().post('/workspace/app/projetos/p-1/contexto', data={
            '_csrf': 'known-token', 'name': 'Tentativa de edição', 'color': '#176b5e',
        })
        self.assertEqual(response.status_code, 409)
        get_db.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.set_project_brand_link')
    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.project_brand_links', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brands', return_value=[{'id': 5}, {'id': 8}])
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    def test_only_organization_brands_can_be_linked(self, _project, _brands, _links, set_link):
        response = _client().post('/workspace/app/projetos/p-1/marcas', data={
            '_csrf': 'known-token', 'brand_ids': ['5', '999'],
        })
        self.assertEqual(response.status_code, 303)
        set_link.assert_called_once_with(12, 7, 'ci:p-1', 'studio:5', True)

    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.set_project_brand_link')
    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.project_brand_links', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brands', return_value=[{'id': 5}, {'id': 8}])
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    def test_multiple_organization_brands_can_be_linked(self, _project, _brands, _links, set_link):
        response = _client().post('/workspace/app/projetos/p-1/marcas', data={
            '_csrf': 'known-token', 'brand_ids': ['5', '8'],
        })
        self.assertEqual(response.status_code, 303)
        self.assertEqual(sorted(set_link.call_args_list, key=repr), sorted([
            mock.call(12, 7, 'ci:p-1', 'studio:5', True),
            mock.call(12, 7, 'ci:p-1', 'studio:8', True),
        ], key=repr))
