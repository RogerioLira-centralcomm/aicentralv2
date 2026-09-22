from io import BytesIO
import json
from pathlib import Path
from unittest import TestCase, mock

from flask import Flask
from jinja2 import FileSystemLoader
from werkzeug.exceptions import BadRequest

from aicentralv2.product_domains import product_url
from aicentralv2.cadu_workspace.routes import (
    _automatic_brand_decision, _authorized_dock_target, _brand_review_is_stale, _dock_shortcuts_available, _merge_brand_analysis,
    _brand_review_pack, _normalized_website_url, _resolve_workspace_context, _user_dock_shortcuts,
    _workspace_context_catalog,
    _save_brand_review_job, bp,
)


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
    def test_automatic_decision_publishes_only_when_every_evidence_gate_passes(self):
        decision = _automatic_brand_decision(
            {'sources': ['https://a.test', 'https://b.test', 'https://c.test', 'https://d.test']},
            {'coverage': {'official_pages': 4, 'approved_visuals': 10, 'contacts': 1, 'addresses': 1, 'policies': 1}},
            {'status': 'ready', 'blocked_fields': [], 'confidence': .9,
             'quality_dimensions': {'identity': .8, 'visual': .8, 'marketing': .8, 'presence': .8, 'sources': .8}},
            'deep',
        )
        self.assertTrue(decision['approved'])

    def test_automatic_decision_aborts_when_a_small_brand_lacks_evidence(self):
        decision = _automatic_brand_decision(
            {'sources': ['https://a.test']},
            {'coverage': {'official_pages': 1, 'approved_visuals': 1}},
            {'status': 'needs_review', 'blocked_fields': ['brand_summary'], 'confidence': .5, 'quality_dimensions': {}},
            'deep',
        )
        self.assertFalse(decision['approved'])
        self.assertFalse(decision['deep_recommended'])
        self.assertTrue(decision['reasons'])

    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.project_brand_links')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_projects')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brands')
    def test_context_catalog_uses_explicit_tenant_owned_links(self, brands, projects, links):
        brands.return_value = [
            {'id': 81, 'name': 'Marca A', 'display_logo': '/a.png', 'display_color': '#111111', 'display_initials': 'MA'},
        ]
        projects.return_value = [
            {'id': 'p-1', 'nome': 'Projeto A', 'status': 'ativo'},
        ]
        links.return_value = [
            {'project_ref': 'ci:p-1', 'brand_ref': 'studio:81'},
            {'project_ref': 'ci:foreign', 'brand_ref': 'studio:81'},
            {'project_ref': 'ci:p-1', 'brand_ref': 'studio:foreign'},
        ]

        catalog = _workspace_context_catalog(12)

        self.assertEqual(catalog['links'], [{'project_ref': 'ci:p-1', 'brand_ref': 'studio:81'}])
        self.assertEqual(catalog['projects'][0]['brand_refs'], ['studio:81'])
        self.assertEqual(catalog['brands'][0]['ref'], 'studio:81')
        brands.assert_called_with(12)
        projects.assert_called_with(12)
        links.assert_called_once_with(12)

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_context_catalog')
    def test_context_resolver_selects_only_a_unique_explicit_brand(self, catalog):
        catalog.return_value = {
            'brands': [{'ref': 'studio:81', 'name': 'Marca A'}, {'ref': 'studio:82', 'name': 'Marca B'}],
            'projects': [
                {'ref': 'ci:one', 'name': 'Projeto único', 'brand_refs': ['studio:81']},
                {'ref': 'ci:many', 'name': 'Projeto múltiplo', 'brand_refs': ['studio:81', 'studio:82']},
            ],
            'links': [],
        }

        unique = _resolve_workspace_context(12, 'ci:one')
        ambiguous = _resolve_workspace_context(12, 'ci:many')
        mismatch = _resolve_workspace_context(12, 'ci:one', 'studio:82')

        self.assertEqual(unique['brand_ref'], 'studio:81')
        self.assertFalse(unique['ambiguous_brand'])
        self.assertIsNone(ambiguous['brand_ref'])
        self.assertTrue(ambiguous['ambiguous_brand'])
        self.assertIsNone(mismatch['brand_ref'])

    @mock.patch('aicentralv2.cadu_workspace.routes._resolve_workspace_context')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_context_catalog')
    def test_context_api_is_scoped_to_the_active_workspace(self, catalog, resolve):
        catalog.return_value = {'brands': [], 'projects': [], 'links': []}
        resolve.return_value = {'project_ref': None, 'brand_ref': None, 'project': None, 'brand': None, 'ambiguous_brand': False}
        client = _client()

        catalog_response = client.get('/workspace/api/context/catalog')
        resolve_response = client.get('/workspace/api/context/resolve?project_ref=ci:p-1&brand_ref=studio:81')

        self.assertEqual(catalog_response.status_code, 200)
        self.assertEqual(resolve_response.status_code, 200)
        catalog.assert_called_once_with(12)
        resolve.assert_called_once_with(12, 'ci:p-1', 'studio:81')

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db', side_effect=RuntimeError('database unavailable'))
    def test_dock_database_failure_does_not_break_workspace_home(self, _get_db):
        with _app().app_context():
            self.assertFalse(_dock_shortcuts_available())
            self.assertEqual(_user_dock_shortcuts(12, 7), [])

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_projects')
    def test_dock_project_target_requires_the_current_agency_project(self, projects):
        projects.return_value = [{'id': 'p-1', 'nome': 'Projeto permitido', 'brand_logo_url': '/logo.png'}]
        self.assertEqual(_authorized_dock_target(12, 'project', 'ci:p-1')['id'], 'p-1')
        self.assertIsNone(_authorized_dock_target(12, 'project', 'ci:outro-projeto'))
        projects.assert_called_with(12, status='todos')

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brands')
    def test_dock_brand_target_requires_a_principal_logo(self, brands):
        brands.return_value = [
            {'id': 81, 'name': 'Sem logo', 'display_logo': ''},
            {'id': 82, 'name': 'Com logo', 'display_logo': 'https://cdn/logo.png'},
        ]
        self.assertIsNone(_authorized_dock_target(12, 'brand', '81'))
        self.assertEqual(_authorized_dock_target(12, 'brand', '82')['name'], 'Com logo')

    def test_normal_domain_becomes_https_url(self):
        self.assertEqual(_normalized_website_url('centralcomm.media'), 'https://centralcomm.media')

    def test_website_url_rejects_non_web_scheme(self):
        with _app().test_request_context():
            with self.assertRaises(BadRequest):
                _normalized_website_url('ftp://example.com')

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_review_progress_update_uses_the_current_client_schema(self, get_db):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'analysis_metadata': {'review_pack': {'job_id': 'job-1', 'status': 'queued'}}}
        get_db.return_value = connection

        with _app().app_context():
            self.assertTrue(_save_brand_review_job(12, 81, 'job-1', status='running'))

        update_sql = cursor.execute.call_args_list[-1].args[0]
        self.assertIn('UPDATE cx_clients SET analysis_metadata', update_sql)
        self.assertNotIn('updated_at', update_sql)
        connection.commit.assert_called_once_with()

    def test_interrupted_brand_review_becomes_retryable_after_timeout(self):
        self.assertTrue(_brand_review_is_stale({
            'status': 'running', 'created_at': '2020-01-01T00:00:00Z',
        }))
        self.assertFalse(_brand_review_is_stale({
            'status': 'pending_approval', 'created_at': '2020-01-01T00:00:00Z',
        }))

    def test_empty_brand_review_starts_as_not_started(self):
        self.assertEqual(_brand_review_pack({'analysis_metadata': {}})['status'], 'not_started')

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
        brand_insert = next(
            call for call in cursor.execute.call_args_list
            if 'INSERT INTO cx_clients' in call.args[0]
        )
        params = brand_insert.args[1]
        self.assertEqual(params[0], 12)
        self.assertGreaterEqual(connection.commit.call_count, 1)

    @mock.patch('aicentralv2.cadu_workspace.routes._start_brand_review_job')
    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.set_project_brand_link')
    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.project_brand_links', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.cadu_workspace.routes._brand_audit_credit_gate', return_value=None)
    @mock.patch('aicentralv2.cadu_workspace.routes._editable_workspace_project', return_value={'id': 'p-1'})
    def test_project_brand_import_normalizes_url_and_associates_brand(
            self, _project, _gate, get_db, _links, associate, start_job):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        response = _client().post('/workspace/app/projetos/p-1/marcas/importar', data={
            '_csrf': 'known-token', 'brand_name': 'Centralcomm', 'website_url': 'centralcomm.media',
        }, headers={'Accept': 'application/json'})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(cursor.execute.call_args.args[1][2], 'https://centralcomm.media')
        associate.assert_called_once_with(12, 7, 'ci:p-1', 'studio:81', True)
        start_job.assert_called_once()

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
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_identity_form_persists_extended_manual_fields(self, workspace_brand, get_db):
        workspace_brand.return_value = {'id': 81, 'brand_profile': {}}
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        response = _client().post('/workspace/app/marcas/81/identidade', data={
            '_csrf': 'known-token', 'name': 'Marca segura',
            'visual_motifs': 'Linhas orgânicas\nFotografia humana',
            'mandatory_elements': 'Logo principal',
            'forbidden_elements': 'Promessas absolutas',
        })

        self.assertEqual(response.status_code, 303)
        payload = json.loads(cursor.execute.call_args.args[1][6])
        self.assertEqual(payload['visual_motifs'], ['Linhas orgânicas', 'Fotografia humana'])
        self.assertEqual(payload['mandatory_elements'], ['Logo principal'])
        self.assertEqual(payload['forbidden_elements'], ['Promessas absolutas'])
        self.assertNotIn('color_palette', payload)
        self.assertNotIn('fonts', payload)

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
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={'id': 81})
    def test_logo_upload_sets_the_uploaded_logo_as_primary(self, _workspace_brand, service):
        response = _client().post('/workspace/app/marcas/81/ativos', data={
            '_csrf': 'known-token', 'role': 'logo',
            'images': (BytesIO(b'valid-image-placeholder'), 'logo.png'),
        })

        self.assertEqual(response.status_code, 303)
        args = service.return_value.upload_client_brand_assets.call_args.args
        self.assertEqual((args[0], args[2], args[3]), (81, True, 'logo'))

    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={'id': 81})
    def test_imported_reference_can_be_promoted_to_primary_logo(self, _workspace_brand, service):
        response = _client().post('/workspace/app/marcas/81/ativos/44/logo', data={
            '_csrf': 'known-token',
        })

        self.assertEqual(response.status_code, 303)
        _workspace_brand.assert_called_once_with(12, 81)
        service.return_value.promote_client_brand_asset_to_logo.assert_called_once_with(81, 44)

    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={'id': 81})
    def test_brand_asset_can_be_deleted_within_active_workspace(self, _workspace_brand, service):
        response = _client().post('/workspace/app/marcas/81/ativos/44/apagar', data={
            '_csrf': 'known-token',
        })

        self.assertEqual(response.status_code, 303)
        _workspace_brand.assert_called_once_with(12, 81)
        service.return_value.delete_brand_asset.assert_called_once_with(81, 44)

    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_member_cannot_delete_brand_asset(self, _workspace_brand, service):
        client = _client()
        with client.session_transaction() as session:
            session['user_type'] = 'client'

        response = client.post('/workspace/app/marcas/81/ativos/44/apagar', data={
            '_csrf': 'known-token',
        })

        self.assertEqual(response.status_code, 403)
        _workspace_brand.assert_not_called()
        service.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.set_project_brand_link')
    @mock.patch('aicentralv2.cadu_workspace.routes.family_repository.project_brand_links')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brands')
    @mock.patch('aicentralv2.cadu_workspace.routes._editable_workspace_project', return_value={'id': 'p-1'})
    def test_additive_project_brand_link_preserves_existing_brands(
            self, _project, brands, links, set_link):
        brands.return_value = [{'id': 81}, {'id': 82}]
        links.return_value = [{'project_ref': 'ci:p-1', 'brand_ref': 'studio:81'}]

        response = _client().post('/workspace/app/projetos/p-1/marcas', data={
            '_csrf': 'known-token', 'add_brand_id': '82',
        })

        self.assertEqual(response.status_code, 303)
        set_link.assert_called_once_with(12, 7, 'ci:p-1', 'studio:82', True)

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_member_cannot_update_brand_identity(self, _workspace_brand):
        client = _client()
        with client.session_transaction() as session:
            session['user_type'] = 'client'

        response = client.post('/workspace/app/marcas/81/identidade', data={
            '_csrf': 'known-token', 'name': 'Marca segura',
        })

        self.assertEqual(response.status_code, 403)
        _workspace_brand.assert_not_called()

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
    @mock.patch('aicentralv2.cadu_workspace.brand_audit_jobs.enqueue')
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_audit_queues_review_with_tenant_scope(self, workspace_brand, service, get_db, enqueue, ensure_credit):
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
            {'id': 'ampliacao', 'status': 'ready'},
            {'id': 'revisor_central', 'status': 'ready'},
        ]
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        response = _client().post('/workspace/app/marcas/81/auditoria', data={
            '_csrf': 'known-token', 'website_url': 'https://example.com', 'confirmed_cost': 'true',
        })

        self.assertEqual(response.status_code, 303)
        self.assertIn('audit=queued', response.headers['Location'])
        workspace_brand.assert_called_once_with(12, 81)
        ensure_credit.assert_called_once_with(12)
        service.assert_not_called()
        enqueue.assert_called_once()
        queued_job = enqueue.call_args.args[0]
        self.assertEqual((queued_job['client_id'], queued_job['user_id'], queued_job['brand_id']), (12, 7, 81))
        sql, params = cursor.execute.call_args.args
        self.assertIn('crm_client_id = %s', sql)
        self.assertEqual(params[-2:], (81, 12))
        self.assertIn('review_pack', params[0])
        self.assertIn('queued', params[0])
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes._start_brand_review_job')
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.cadu_workspace.routes._ensure_brand_audit_credit')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    def test_audit_preserves_uploaded_logo_family_as_references(
            self, service, workspace_brand, _ensure_credit, get_db, _start_job):
        workspace_brand.return_value = {
            'id': 81, 'website_url': 'https://example.com', 'analysis_metadata': {},
        }
        connection = mock.MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        response = _client().post('/workspace/app/marcas/81/auditoria', data={
            '_csrf': 'known-token', 'website_url': 'https://example.com', 'confirmed_cost': 'true',
            'images': [
                (BytesIO(b'logo-horizontal'), 'logo-horizontal.png'),
                (BytesIO(b'logo-simbolo'), 'logo-simbolo.png'),
            ],
        })

        self.assertEqual(response.status_code, 303)
        args = service.return_value.upload_client_brand_assets.call_args.args
        self.assertEqual((args[0], args[2], args[3]), (81, False, 'reference'))
        self.assertEqual(len(args[1]), 2)

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
                'reviews': [
                    {'id': 'evidencias', 'status': 'ready'},
                    {'id': 'revisor_central', 'status': 'ready', 'blocked_fields': []},
                ],
            }},
        }
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 81}
        get_db.return_value = connection

        with mock.patch('aicentralv2.cadu_workspace.routes._fill_empty_project_identity_from_brand'), \
             mock.patch('aicentralv2.cadu_workspace.routes._sync_approved_brand_to_projects'), \
             mock.patch('aicentralv2.cadu_workspace.routes._send_brand_approval_email'), \
             mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService'):
            response = _client().post('/workspace/app/marcas/81/revisoes/aprovar', data={
                '_csrf': 'known-token',
            })

        self.assertEqual(response.status_code, 303)
        sql, params = cursor.execute.call_args.args
        self.assertIn('brand_profile = %s::jsonb', sql)
        self.assertIn('Resumo aprovado.', params[7])
        self.assertIn('approved', params[8])
        self.assertEqual(params[-2:], (81, 12))
        connection.commit.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_approval_requires_a_ready_central_consolidation(self, workspace_brand, get_db):
        workspace_brand.return_value = {
            'id': 81,
            'analysis_metadata': {'review_pack': {
                'status': 'pending_approval',
                'analysis': {'brand_summary': 'Proposta ainda bloqueada.'},
                'reviews': [{'id': 'revisor_central', 'status': 'needs_review', 'blocked_fields': ['positioning']}],
            }},
        }

        response = _client().post('/workspace/app/marcas/81/revisoes/aprovar', data={
            '_csrf': 'known-token',
        })

        self.assertEqual(response.status_code, 409)
        self.assertIn('consolidação central', response.get_data(as_text=True))
        get_db.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_projects', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes._brand_linked_projects', return_value=[])
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand')
    def test_brand_detail_renders_the_hero_action_only_after_approval(
            self, workspace_brand, linked_projects, projects):
        workspace_brand.return_value = {
            'id': 81, 'name': 'Marca aprovada', 'sector': 'Serviços',
            'website_url': 'https://example.com', 'primary_color': '#176b5e',
            'secondary_color': '#dcece6', 'display_logo': '', 'display_initials': 'MA',
            'seed_visuals': {'hero': ''}, 'assets': [], 'brand_profile': {},
            'analysis_metadata': {'review_pack': {'status': 'approved'}},
            'readiness': {'score': 100, 'missing': []}, 'crm_client_id': 12,
            'tone_of_voice': '',
        }

        client = _client()
        client.application.jinja_loader = FileSystemLoader(
            str(Path(__file__).resolve().parents[1] / 'aicentralv2' / 'templates')
        )
        client.application.jinja_env.globals['product_url'] = product_url
        client.application.add_url_rule(
            '/observabilidade', endpoint='cadu_agent_v2_lab.observability_page',
            view_func=lambda: '',
        )
        response = client.get('/marcas/81')

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('"brandMode": true', html)
        self.assertIn('/workspace/app/marcas/81/hero/gerar', html)

    @mock.patch('aicentralv2.creative_modeling_service.CreativeModelingService')
    @mock.patch('aicentralv2.cadu_workspace.routes.CaduCreditConnector')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={
        'id': 81, 'analysis_metadata': {'review_pack': {'status': 'pending_approval'}},
    })
    def test_brand_hero_is_not_available_outside_projects(self, _brand, credits, service):
        response = _client().post('/workspace/app/marcas/81/hero/gerar', data={
            '_csrf': 'known-token',
        })

        self.assertEqual(response.status_code, 409)
        self.assertIn('Heroes são exclusivos de projetos', response.get_data(as_text=True))
        credits.assert_not_called()
        service.assert_not_called()

    @mock.patch('aicentralv2.creative_brand_analysis.search_recent_brand_creatives',
                side_effect=RuntimeError('serviço externo indisponível'))
    @mock.patch('aicentralv2.services.integration_credentials.resolve_firecrawl_api_key', return_value='key')
    @mock.patch('aicentralv2.cadu_credit_connector.CaduCreditConnector')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={'id': 81, 'name': 'Marca'})
    def test_recent_brand_references_return_service_unavailable_instead_of_500(
            self, _brand, credits, _key, search):
        credits.return_value.authorize_firecrawl.return_value = 1
        response = _client().post('/workspace/app/marcas/81/ativos/referencias-recentes', data={
            '_csrf': 'known-token',
        })

        self.assertEqual(response.status_code, 503)
        self.assertIn('referências recentes', response.get_data(as_text=True))
        search.assert_called_once()

    @mock.patch('aicentralv2.creative_brand_analysis.search_recent_brand_creatives')
    @mock.patch('aicentralv2.services.integration_credentials.resolve_firecrawl_api_key', return_value='key')
    @mock.patch('aicentralv2.cadu_credit_connector.CaduCreditConnector')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_brand', return_value={'id': 81, 'name': 'Marca'})
    def test_recent_brand_references_expose_insufficient_credits(
            self, _brand, credits, _key, search):
        from aicentralv2.cadu_tool_billing import InsufficientToolCredits

        credits.return_value.authorize_firecrawl.side_effect = InsufficientToolCredits('Saldo insuficiente.')
        response = _client().post('/workspace/app/marcas/81/ativos/referencias-recentes', data={
            '_csrf': 'known-token',
        })

        self.assertEqual(response.status_code, 409)
        self.assertIn('Saldo insuficiente', response.get_data(as_text=True))
        search.assert_not_called()
