from io import BytesIO
import json
from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import _brand_review_is_stale, _merge_brand_analysis, bp


def _app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    return app


def _client():
    client = _app().test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, cliente_id=12, user_type='admin', family_csrf='known-token')
    return client


class WorkspaceBrandsTest(TestCase):
    def test_interrupted_brand_review_becomes_retryable_after_timeout(self):
        self.assertTrue(_brand_review_is_stale({
            'status': 'running', 'created_at': '2020-01-01T00:00:00Z',
        }))
        self.assertFalse(_brand_review_is_stale({
            'status': 'pending_approval', 'created_at': '2020-01-01T00:00:00Z',
        }))

    def test_analysis_merge_preserves_reviewed_identity(self):
        merged = _merge_brand_analysis({
            'brand_profile': {
                'tone_of_voice': 'Tom aprovado',
                'target_audience': 'Público aprovado',
                'design_system_ads': {'revision': 4},
            },
            'analysis_metadata': {'previous': True},
        }, {
            'tone_of_voice': 'Sugestão automática',
            'target_audience': 'Outro público',
            'brand_summary': 'Resumo extraído do site.',
            'differentiators': ['Entrega rápida'],
            'analysis_metadata': {'model': 'brand-model', 'pages_analyzed': 3},
        })
        self.assertEqual(merged['profile']['tone_of_voice'], 'Tom aprovado')
        self.assertEqual(merged['profile']['target_audience'], 'Público aprovado')
        self.assertEqual(merged['profile']['brand_summary'], 'Resumo extraído do site.')
        self.assertEqual(merged['profile']['design_system_ads']['revision'], 4)
        self.assertTrue(merged['metadata']['previous'])
        self.assertEqual(merged['metadata']['pages_analyzed'], 3)

    def test_create_requires_session_csrf(self):
        response = _client().post('/workspace/app/marcas', data={'name': 'Marca segura'})
        self.assertEqual(response.status_code, 403)

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={'id': 81})
    def test_member_cannot_start_or_approve_brand_review(self, _brand):
        client = _client()
        with client.session_transaction() as session:
            session['user_type'] = 'client'
        response = client.post('/workspace/app/marcas/81/auditoria', data={
            '_csrf': 'known-token', 'website_url': 'https://example.com',
        })
        self.assertEqual(response.status_code, 403)
        response = client.post('/workspace/app/marcas/81/revisoes/aprovar', data={
            '_csrf': 'known-token',
        })
        self.assertEqual(response.status_code, 403)

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_create_assigns_brand_to_active_organization(self, get_db):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        response = _client().post('/workspace/app/marcas', data={
            '_csrf': 'known-token', 'name': 'Marca segura', 'sector': 'Serviços',
            'website_url': 'https://example.com', 'primary_color': '#176b5e',
            'secondary_color': '#dcece6',
        })

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['Location'], '/workspace/app/marcas/81')
        params = cursor.execute.call_args.args[1]
        self.assertEqual(params[0], 12)
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_identity_update_is_scoped_in_read_and_write(self, workspace_brand, get_db):
        workspace_brand.return_value = {'id': 81}
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        response = _client().post('/workspace/app/marcas/81/identidade', data={
            '_csrf': 'known-token', 'name': 'Marca segura',
            'tone_of_voice': 'Direto', 'brand_values': 'Clareza\nConfiança',
        })

        self.assertEqual(response.status_code, 303)
        workspace_brand.assert_called_once_with(12, 81)
        sql, params = cursor.execute.call_args.args
        self.assertIn('crm_client_id = %s', sql)
        self.assertEqual(params[-2:], (81, 12))

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value=None)
    def test_foreign_brand_cannot_be_updated(self, _workspace_brand, get_db):
        response = _client().post('/workspace/app/marcas/999/identidade', data={
            '_csrf': 'known-token', 'name': 'Outra marca',
        })
        self.assertEqual(response.status_code, 404)
        get_db.assert_not_called()

    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={'id': 81})
    def test_asset_upload_reuses_mature_storage_after_scope_check(self, _workspace_brand, service):
        response = _client().post('/workspace/app/marcas/81/ativos', data={
            '_csrf': 'known-token', 'role': 'reference',
            'images': (BytesIO(b'valid-image-placeholder'), 'referencia.png'),
        })
        self.assertEqual(response.status_code, 303)
        _workspace_brand.assert_called_once_with(12, 81)
        service.return_value.upload_client_brand_assets.assert_called_once()

    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value=None)
    def test_foreign_brand_assets_are_rejected_before_storage(self, _workspace_brand, service):
        response = _client().post('/workspace/app/marcas/999/ativos', data={
            '_csrf': 'known-token',
            'images': (BytesIO(b'valid-image-placeholder'), 'referencia.png'),
        })
        self.assertEqual(response.status_code, 404)
        service.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes._ensure_brand_audit_credit')
    @mock.patch('aicentralv2.cadu_workspace.routes.threading.Thread')
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_audit_queues_review_with_tenant_scope(self, workspace_brand, service, get_db, thread, ensure_credit):
        workspace_brand.return_value = {
            'id': 81, 'website_url': 'https://example.com',
            'brand_profile': {'tone_of_voice': 'Tom aprovado'},
            'analysis_metadata': {},
        }
        service.return_value.analyze_brand.return_value = {
            'sector': 'Serviços', 'website_url': 'https://example.com',
            'primary_color': '#176B5E', 'tone_of_voice': 'Tom sugerido',
            'brand_summary': 'Resumo extraído.',
            'analysis_metadata': {'model': 'brand-model', 'pages_analyzed': 2},
        }
        service.return_value.review_brand_analysis.return_value = [
            {'id': 'evidencias', 'status': 'ready'},
            {'id': 'estrategia', 'status': 'ready'},
            {'id': 'direcao_criativa', 'status': 'ready'},
        ]
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        response = _client().post('/workspace/app/marcas/81/auditoria', data={
            '_csrf': 'known-token', 'website_url': 'https://example.com',
        })

        self.assertEqual(response.status_code, 303)
        self.assertIn('audit=queued', response.headers['Location'])
        workspace_brand.assert_called_once_with(12, 81)
        ensure_credit.assert_called_once_with(12)
        service.assert_not_called()
        thread.return_value.start.assert_called_once_with()
        sql, params = cursor.execute.call_args.args
        self.assertIn('crm_client_id = %s', sql)
        self.assertEqual(params[-2:], (81, 12))
        self.assertIn('review_pack', params[0])
        self.assertIn('queued', params[0])
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={'id': 81})
    @mock.patch('aicentralv2.cadu_workspace.routes._ensure_brand_audit_credit')
    def test_audit_stops_before_queue_when_credits_are_unavailable(self, ensure_credit, _workspace_brand):
        from werkzeug.exceptions import Conflict
        ensure_credit.side_effect = Conflict(description='Não há créditos disponíveis para analisar esta marca.')

        response = _client().post('/workspace/app/marcas/81/auditoria', data={
            '_csrf': 'known-token', 'website_url': 'https://example.com',
        })

        self.assertEqual(response.status_code, 409)

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={'id': 81})
    @mock.patch('aicentralv2.cadu_workspace.routes._ensure_brand_audit_credit')
    def test_audit_returns_credit_guidance_to_the_async_form(self, ensure_credit, _workspace_brand):
        from werkzeug.exceptions import Conflict
        ensure_credit.side_effect = Conflict(description='Não há créditos disponíveis para analisar esta marca.')

        response = _client().post('/workspace/app/marcas/81/auditoria', data={
            '_csrf': 'known-token', 'website_url': 'https://example.com',
        }, headers={'Accept': 'application/json'})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json['error'], 'Não há créditos disponíveis para analisar esta marca.')

    @mock.patch('aicentralv2.cadu_workspace.routes._start_brand_review_job')
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.cadu_workspace.routes._ensure_brand_audit_credit')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_retry_reuses_the_saved_evidence_checkpoint(self, workspace_brand, _ensure_credit, get_db, start_job):
        checkpoint = {'brand_summary': 'Base já extraída.', 'tone_of_voice': 'Claro'}
        workspace_brand.return_value = {
            'id': 81, 'analysis_metadata': {'review_pack': {
                'status': 'failed', 'input': {'website_url': 'https://example.com'}, 'analysis': checkpoint,
            }},
        }
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        response = _client().post('/workspace/app/marcas/81/auditoria/repetir', data={'_csrf': 'known-token'})

        self.assertEqual(response.status_code, 303)
        self.assertEqual(start_job.call_args.kwargs['proposal'], checkpoint)
        persisted = json.loads(cursor.execute.call_args.args[1][0])
        self.assertEqual(persisted['review_pack']['analysis'], checkpoint)

    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value=None)
    def test_foreign_brand_cannot_be_audited(self, workspace_brand, service):
        response = _client().post('/workspace/app/marcas/999/auditoria', data={
            '_csrf': 'known-token', 'website_url': 'https://example.com',
        })
        self.assertEqual(response.status_code, 404)
        workspace_brand.assert_called_once_with(12, 999)
        service.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_approval_promotes_pending_proposal_only_after_human_action(self, workspace_brand, get_db):
        workspace_brand.return_value = {
            'id': 81, 'brand_profile': {'tone_of_voice': 'Tom aprovado'},
            'analysis_metadata': {'review_pack': {
                'status': 'pending_approval',
                'analysis': {
                    'sector': 'Serviços', 'tone_of_voice': 'Tom proposto',
                    'brand_summary': 'Resumo aprovado.',
                    'analysis_metadata': {'model': 'brand-model'},
                },
                'reviews': [{'id': 'evidencias', 'status': 'ready'}],
            }},
        }
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        response = _client().post('/workspace/app/marcas/81/revisoes/aprovar', data={
            '_csrf': 'known-token',
        })

        self.assertEqual(response.status_code, 303)
        sql, params = cursor.execute.call_args.args
        self.assertIn('brand_profile = %s::jsonb', sql)
        self.assertIn('Resumo aprovado.', params[6])
        self.assertIn('approved', params[7])
        self.assertEqual(params[-2:], (81, 12))
        connection.commit.assert_called_once_with()
