from pathlib import Path
from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import bp as workspace_bp, brand_api_bp
from aicentralv2.creative_modeling_routes import register_creative_modeling_routes
from aicentralv2.product_domains import product_url


ROOT = Path(__file__).resolve().parents[1]


def _app():
    app = Flask(
        __name__,
        template_folder=str(ROOT / 'aicentralv2' / 'templates'),
        static_folder=str(ROOT / 'aicentralv2' / 'static'),
    )
    app.config.update(
        SECRET_KEY='test', TESTING=True,
        WORKSPACE_URL='https://workspace.test', STUDIO_URL='https://studio.test',
        AUTH_URL='https://auth.test', CADU_URL='https://cadu.test',
        PLANNER_URL='https://planner.test', CONNECT_URL='https://connect.test',
        SKILLS_URL='https://skills.test', CENTRALX_URL='https://centralx.test',
    )
    register_creative_modeling_routes(brand_api_bp)
    app.register_blueprint(workspace_bp)
    app.register_blueprint(brand_api_bp)
    app.context_processor(lambda: {'product_url': product_url, 'cadu_nav_credit': None})
    return app


def _client():
    client = _app().test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, cliente_id=12, user_name='Pessoa', user_email='pessoa@example.test')
    return client


class WorkspaceBrandSystemTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_advanced_system_renders_inside_workspace(self, workspace_brand):
        workspace_brand.return_value = {'id': 81, 'name': 'Marca segura'}
        response = _client().get('/workspace/app/marcas/81/sistema')
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('workspace-brand-system-shell', html)
        self.assertIn('Sistema de marca', html)
        self.assertNotIn('Sistema avançado no Studio', html)
        workspace_brand.assert_called_once_with(12, 81)

    @mock.patch('aicentralv2.creative_modeling_routes._workspace_brand_ids', return_value={81})
    @mock.patch('aicentralv2.creative_modeling_routes._service')
    def test_client_directory_is_filtered_to_tenant_brands(self, service, _brand_ids):
        service.return_value.list_clients.return_value = [
            {'id': 81, 'name': 'Permitida'}, {'id': 999, 'name': 'Outra organização'},
        ]
        response = _client().get('/workspace/api/clients')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data'], [{'id': 81, 'name': 'Permitida'}])

    @mock.patch('aicentralv2.creative_modeling_routes._workspace_brand_ids', return_value={81})
    @mock.patch('aicentralv2.creative_modeling_routes._service')
    def test_foreign_brand_mutation_is_rejected_before_service(self, service, _brand_ids):
        response = _client().put('/workspace/api/clients/999', json={'name': 'Invasão'})
        self.assertEqual(response.status_code, 403)
        self.assertIn('não pertence', response.get_json()['error'])
        service.return_value.update_client.assert_not_called()

    @mock.patch('aicentralv2.creative_modeling_routes._workspace_brand_ids', return_value={81})
    @mock.patch('aicentralv2.creative_modeling_routes._service')
    def test_native_brand_mutation_reaches_existing_service(self, service, _brand_ids):
        service.return_value.update_client.return_value = {'id': 81, 'name': 'Atualizada'}
        response = _client().put('/workspace/api/clients/81', json={'name': 'Atualizada'})
        self.assertEqual(response.status_code, 200)
        service.return_value.update_client.assert_called_once_with(81, {'name': 'Atualizada'})

    @mock.patch('aicentralv2.creative_modeling_routes._workspace_brand_ids', return_value={81})
    @mock.patch('aicentralv2.creative_modeling_routes._service')
    def test_advanced_editor_cannot_delete_workspace_history(self, service, _brand_ids):
        response = _client().delete('/workspace/api/clients/81')
        self.assertEqual(response.status_code, 403)
        self.assertIn('Preserve o histórico', response.get_json()['error'])
        service.return_value.delete_client.assert_not_called()

    @mock.patch('aicentralv2.creative_modeling_routes._service')
    def test_cross_tenant_legacy_source_directory_is_not_exposed(self, service):
        response = _client().get('/workspace/api/brand-sources')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data'], [])
        service.return_value.list_brand_sources.assert_not_called()
