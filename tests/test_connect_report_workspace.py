from unittest import TestCase, mock
from test_product_portals import _app
from aicentralv2.cadu_connect import report_workspace as workspace


ENTITIES = [
    {'ref': 'projects:1', 'name': 'Verão', 'kind': 'project', 'related_refs': ['studio:2']},
    {'ref': 'studio:2', 'name': 'Solar', 'kind': 'brand'},
    {'ref': 'studio:3', 'name': 'Outra', 'kind': 'brand'},
]
FORM = {'project_ref': 'projects:1', 'campaign_name': 'Verão Solar', 'brand_ref': 'studio:2'}


class ReportWorkspaceTests(TestCase):
    def test_brand_must_belong_to_project(self):
        with self.assertRaises(ValueError):
            workspace.validate_document(dict(FORM, brand_ref='studio:3'), ENTITIES)

    def test_unknown_project_and_invalid_dates_are_rejected(self):
        for changes in ({'project_ref': 'projects:999'}, {'start_date': '2026-10-01', 'end_date': '2026-09-01'}, {'accent': 'red; color:green'}):
            with self.assertRaises(ValueError):
                workspace.validate_document(dict(FORM, **changes), ENTITIES)

    def test_cobrand_default_preserves_external_id_as_string(self):
        document = workspace.validate_document(dict(FORM, external_campaign_id='000123'), ENTITIES)
        self.assertEqual(document['brand_mode'], 'cobrand')
        self.assertEqual(document['external_campaign_id'], '000123')

    def setUp(self):
        self.app = _app()
        self.client = self.app.test_client()
        self.headers = {'Host': 'connect.centralcomm.media'}
        with self.client.session_transaction(headers=self.headers) as sess:
            sess.update(user_id=1, family_csrf='test-token')
        self.context = {'organization_id': 1, 'client_id': 1, 'client_name': 'Aurora', 'role': 'member'}
        self.patches = [mock.patch.object(workspace.context, 'resolve', return_value=self.context),
                        mock.patch.object(workspace.context, 'inventory', return_value=ENTITIES),
                        mock.patch.object(workspace, 'available', return_value=False)]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_uninstalled_storage_renders_honest_disabled_workspace(self):
        response = self.client.get('/connect/relatorios', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('precisa ser instalado', html)
        self.assertIn('Marca + cliente', html)
        self.assertIn('A marca do projeto lidera', html)
        self.assertIn('Solar', html)

    def test_post_requires_csrf(self):
        response = self.client.post('/connect/relatorios', data=FORM, headers=self.headers)
        self.assertEqual(response.status_code, 403)

    def test_viewer_cannot_write(self):
        self.context['role'] = 'viewer'
        response = self.client.post('/connect/relatorios', data=dict(FORM, _csrf='test-token'), headers=self.headers)
        self.assertEqual(response.status_code, 403)

    def test_storage_missing_never_claims_save(self):
        response = self.client.post('/connect/relatorios', data=dict(FORM, _csrf='test-token'), headers=self.headers)
        self.assertEqual(response.status_code, 503)

    def test_inaccessible_report_returns_404(self):
        response = self.client.get('/connect/relatorios?report_id=99', headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_creation_commits_document_and_first_version(self):
        conn = mock.MagicMock()
        with mock.patch.object(workspace, 'available', return_value=True), mock.patch.object(workspace, 'get_db', return_value=conn), mock.patch.object(workspace, 'rows', return_value=[{'id': 12}]) as query:
            response = self.client.post('/connect/relatorios', data=dict(FORM, _csrf='test-token'), headers=self.headers)
        self.assertEqual(response.status_code, 302)
        self.assertIn('report_id=12', response.location)
        conn.commit.assert_called_once()
        self.assertIn('ON CONFLICT', query.call_args.args[0])
        self.assertIn('workspace_versions', conn.cursor.return_value.__enter__.return_value.execute.call_args.args[0])

    def test_stale_revision_does_not_overwrite(self):
        conn = mock.MagicMock()
        existing = {'id': 12, 'project_ref': 'projects:1', 'campaign_name': 'Verão Solar', 'revision': 3, 'document': {}}
        with mock.patch.object(workspace, 'available', return_value=True), mock.patch.object(workspace, 'get_db', return_value=conn), mock.patch.object(workspace, 'rows', side_effect=[[existing], [], []]):
            response = self.client.post('/connect/relatorios', data=dict(FORM, _csrf='test-token', report_id='12', revision='2', update_note='Mudou'), headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('versão mais recente', response.get_data(as_text=True))
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()
