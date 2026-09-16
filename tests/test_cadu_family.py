from pathlib import Path
from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_family import register
from aicentralv2.product_domains import product_url


ROOT = Path(__file__).resolve().parents[1]
USER = {'id': 7, 'organization_id': 12, 'role_id': 1, 'user_type': 'admin', 'name': 'Pessoa', 'email': 'a@example.test', 'phone': ''}
CLIENTS = [{'id': 12, 'name': 'Agência', 'role': 'admin'}, {'id': 24, 'name': 'Cliente autorizado', 'role': 'member'}]
ENTITIES = [{'ref': 'ci:project', 'name': 'Projeto', 'kind': 'project', 'source': 'ci'},
            {'ref': 'studio:3', 'name': 'Marca', 'kind': 'brand', 'source': 'studio'}]


class FamilyTest(TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(ROOT / 'aicentralv2/templates'),
                         static_folder=str(ROOT / 'aicentralv2/static'))
        self.app.config.update(SECRET_KEY='test-only', TESTING=True, CADU_FAMILY_ENABLED=True)
        self.app.context_processor(lambda: {'product_url': product_url})
        register(self.app)
        self.client = self.app.test_client()
        for name, result in [('actor', USER), ('clients', CLIENTS), ('entities', ENTITIES),
                             ('entity_links', []), ('project_brand_links', [])]:
            patch = mock.patch('aicentralv2.cadu_family.repository.' + name, return_value=result)
            setattr(self, name, patch.start())
            self.addCleanup(patch.stop)

    def login(self):
        with self.client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='token')

    def post(self, path, data):
        return self.client.post('/familia/api/' + path, json=data, headers={'X-CSRF-Token': 'token'})

    def put(self, path, data):
        return self.client.put('/familia/api/' + path, json=data, headers={'X-CSRF-Token': 'token'})

    def test_visitor_cannot_read_or_mutate(self):
        for path in ('context', 'conversations', 'conversations/id/messages'):
            self.assertEqual(self.client.get('/familia/api/' + path).status_code, 401)
        self.assertEqual(self.post('context', {'client_id': 12}).status_code, 401)
        self.assertEqual(self.post('conversations/send', {'message': 'test'}).status_code, 401)
        self.actor.assert_not_called()

    def test_switch_clears_old_entities_and_never_changes_organization(self):
        self.login()
        self.assertEqual(self.post('context', {'client_id': 12, 'project_ref': 'ci:project'}).status_code, 200)
        result = self.post('context', {'client_id': 24}).get_json()['context']
        self.assertEqual(result['organization_id'], 12)
        self.assertIsNone(result['project_ref'])
        with self.client.session_transaction() as session:
            self.assertEqual(session['cliente_id'], 12)

    def test_ungranted_client_and_foreign_project_rejected(self):
        self.login()
        self.assertEqual(self.post('context', {'client_id': 99}).status_code, 403)
        self.assertEqual(self.post('context', {'client_id': 12, 'project_ref': 'ci:foreign'}).status_code, 403)
        self.assertEqual(self.post('context', {'client_id': 12, 'project_ref': 'studio:3'}).status_code, 403)

    def test_revoked_grant_is_rechecked(self):
        self.login()
        self.post('context', {'client_id': 24})
        self.clients.return_value = CLIENTS[:1]
        self.assertEqual(self.client.get('/familia/api/context').status_code, 403)

    def test_profile_requires_csrf(self):
        self.login()
        with mock.patch('aicentralv2.cadu_family.repository.profile_update') as update:
            response = self.client.patch('/familia/api/profile', json={'name': 'New name'})
            self.assertEqual(response.status_code, 403)
            update.assert_not_called()

    def test_viewer_cannot_create_entity(self):
        self.login()
        self.clients.return_value = [{**CLIENTS[0], 'role': 'viewer'}]
        with mock.patch('aicentralv2.cadu_family.repository.create_entity') as create:
            self.assertEqual(self.post('entities', {'name': 'Teste', 'kind': 'project'}).status_code, 403)
            create.assert_not_called()

    def test_project_brand_link_requires_enabled_writes_and_authorized_entities(self):
        self.login()
        payload = {'project_ref': 'ci:project', 'brand_ref': 'studio:3', 'linked': True}
        with mock.patch('aicentralv2.cadu_family.repository.set_project_brand_link') as save:
            self.assertEqual(self.put('project-brand-links', payload).status_code, 403)
            save.assert_not_called()
            self.app.config['CADU_FAMILY_WRITES_ENABLED'] = True
            self.assertEqual(self.put('project-brand-links', payload).status_code, 200)
            save.assert_called_once_with(12, 7, 'ci:project', 'studio:3', True)
            self.assertEqual(self.put('project-brand-links', {**payload, 'brand_ref': 'ci:project'}).status_code, 403)

    def test_member_cannot_read_billing(self):
        self.login()
        self.actor.return_value = {**USER, 'user_type': 'client'}
        self.assertEqual(self.client.get('/familia/workspace/faturamento').status_code, 403)

    def test_visitor_panel_only_on_supported_products(self):
        for product in ('workspace', 'planner', 'connect', 'studio'):
            response = self.client.get(f'/familia/{product}/')
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertEqual('id="conversation-panel"' in html, product != 'studio')
        self.assertEqual(self.client.get('/familia/unknown/').status_code, 404)

    def test_authenticated_shell_has_compact_authorized_context(self):
        self.login()
        response = self.client.get('/familia/workspace/clientes')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('class="family-context-menu"', html)
        self.assertIn('Cliente selecionado', html)
        for field in ('client_id', 'brand_ref', 'project_ref'):
            self.assertIn(f'name="{field}"', html)
        self.assertIn('/familia/workspace/consumo', html)

    def test_guest_shell_does_not_expose_context_or_account_usage(self):
        html = self.client.get('/familia/workspace/').get_data(as_text=True)
        self.assertNotIn('class="family-context-menu"', html)
        self.assertNotIn('class="family-credits"', html)
        self.assertIn('Entrar na minha conta', html)

    def test_product_homepages_are_distinct_and_public(self):
        from aicentralv2.cadu_family.catalog import LANDINGS, PRODUCTS
        for product, landing in LANDINGS.items():
            with self.subTest(product=product):
                response = self.client.get(f'/familia/{product}/')
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn(landing['title'], html)
                self.assertIn('Experiência em migração', html)
                self.assertNotIn('id="family-context"', html)
                for module, _, _ in landing['links']:
                    self.assertIn(module, PRODUCTS[product]['modules'])
                    self.assertIn(f'/familia/{product}/{module}', html)
                asset = ROOT / 'aicentralv2/static/images/cadu/products' / landing['image']
                self.assertTrue(asset.is_file())
        self.actor.assert_not_called()

    def test_every_product_module_has_one_explicit_sidebar_group(self):
        from aicentralv2.cadu_family.catalog import PRODUCTS
        for product, spec in PRODUCTS.items():
            with self.subTest(product=product):
                grouped = [key for _, keys in spec['navigation'] for key in keys]
                self.assertCountEqual(grouped, spec['modules'])
                self.assertEqual(len(grouped), len(set(grouped)))

    def test_planner_exposes_places_as_an_internal_catalog(self):
        from aicentralv2.cadu_family.catalog import LANDINGS, PRODUCTS
        self.assertIn('places', PRODUCTS['planner']['modules'])
        self.assertIn('places', [key for _, keys in PRODUCTS['planner']['navigation'] for key in keys])
        self.assertIn('places', [key for key, _, _ in LANDINGS['planner']['links']])

    def test_workspace_home_only_lists_authorized_inventory(self):
        self.login()
        self.entities.return_value = [{**ENTITIES[0], 'name': '<script>untrusted</script>'}]
        response = self.client.get('/familia/workspace/')
        html = response.get_data(as_text=True)
        self.assertIn('Projetos do cliente selecionado', html)
        self.assertIn('&lt;script&gt;untrusted&lt;/script&gt;', html)
        self.assertNotIn('<script>untrusted</script>', html)
        self.entities.assert_called_with(12)

    def test_connect_home_does_not_query_reports(self):
        self.login()
        with mock.patch('aicentralv2.cadu_connect.repository.campaigns_for_client') as reports:
            self.assertEqual(self.client.get('/familia/connect/').status_code, 200)
            reports.assert_not_called()

    def test_pilot_product_switch_stays_on_python_family_routes(self):
        html = self.client.get('/familia/workspace/').get_data(as_text=True)
        for product in ('workspace', 'studio', 'planner', 'connect'):
            self.assertIn(f'href="/familia/{product}/"', html)

    def test_php_handoff_not_offered_for_different_client(self):
        self.login()
        self.post('context', {'client_id': 24})
        response = self.client.get('/familia/studio/link-tester')
        self.assertNotIn('/auth/sso/to-cadu', response.get_data(as_text=True))

    def test_studio_and_skills_cannot_select_shared_agent(self):
        from aicentralv2.cadu_family.catalog import PROFILES

        self.assertEqual(set(PROFILES), {'workspace', 'planner', 'connect'})
        self.login()
        for product in ('studio', 'skills'):
            with self.subTest(product=product):
                response = self.post('conversations/send', {
                    'message': 'Olá', 'profile': product,
                })
                self.assertEqual(response.status_code, 400)

    def test_backend_failure_is_not_empty_success(self):
        self.login()
        self.entities.side_effect = RuntimeError('database password must not leak')
        with mock.patch('aicentralv2.cadu_family.repository.get_db'):
            result = self.client.get('/familia/api/context')
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('password', result.get_data(as_text=True))

    def test_disabled_rollout_returns_not_found(self):
        self.app.config['CADU_FAMILY_ENABLED'] = False
        self.assertEqual(self.client.get('/familia/workspace/').status_code, 404)

    def test_planner_host_stays_available_when_the_family_rollout_is_disabled(self):
        self.app.config.update(CADU_FAMILY_ENABLED=False, PLANNER_URL='https://planner.centralcomm.media')
        self.app.add_url_rule('/cadu-assets/<family>/icon-<int:size>.png', 'cadu_maintenance_product_icon',
                              lambda family, size: '')
        response = self.client.get('/familia/planner/', headers={'Host': 'planner.centralcomm.media'})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Seu próximo plano começa aqui', html)
        self.assertNotIn('CentralX', html)

    def test_history_read_checks_user_and_client(self):
        self.login()
        with mock.patch('aicentralv2.cadu_family.repository.conversation_messages', return_value=None) as read:
            response = self.client.get('/familia/api/conversations/foreign/messages')
        self.assertEqual(response.status_code, 404)
        read.assert_called_once_with(7, 12, 'foreign')

    def test_planner_catalog_requires_authorized_actor(self):
        self.assertEqual(self.client.get('/familia/api/planner/catalog/canais').status_code, 401)
        self.login()
        with mock.patch('aicentralv2.cadu_planner.catalog.repository.catalog', return_value=[]) as catalog:
            response = self.client.get('/familia/api/planner/catalog/canais?q=video&limit=2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'kind': 'canais', 'records': []})
        catalog.assert_called_once_with('canais', 'video')

    def test_planner_catalog_rejects_unknown_kind_and_out_of_range_limit(self):
        self.login()
        self.assertEqual(self.client.get('/familia/api/planner/catalog/cotacoes').status_code, 404)
        self.assertEqual(self.client.get('/familia/api/planner/catalog/formatos?limit=31').status_code, 400)

    def test_planner_catalog_detail_uses_projected_row_and_auth_context(self):
        self.login()
        row = {'id': 3, 'name': 'Vídeo', 'description': 'Formato', 'dimensions': '1920×1080'}
        with mock.patch('aicentralv2.cadu_planner.catalog.repository.rows', return_value=[row]) as rows:
            response = self.client.get('/familia/api/planner/catalog/formatos/3')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'kind': 'formatos', 'record': row})
        sql, params = rows.call_args.args
        self.assertIn('FROM cadu_formatos', sql)
        self.assertEqual(params, (3,))

    def test_planner_catalog_cards_are_only_in_logged_in_planner(self):
        self.login()
        with mock.patch('aicentralv2.cadu_planner.pages.repository.catalog', return_value=[{'id': 1, 'name': 'Canal'}]):
            html = self.client.get('/familia/planner/canais').get_data(as_text=True)
        self.assertIn('planner-catalog-grid', html)
        self.assertIn('data-catalog-kind="canais"', html)
        self.assertIn('cadu_planner/catalog.js', html)
        self.assertNotIn('href="/familia/api/planner/catalog/', html)

    def test_planner_document_preview_requires_context_and_does_not_expose_html(self):
        self.assertEqual(self.client.get('/familia/api/planner/documents/3').status_code, 401)
        self.login()
        document = {'id': 3, 'title': 'Plano', 'type': 'briefing', 'status': 'published', 'is_owner': True}
        with mock.patch('aicentralv2.cadu_planner.docs.document_preview', return_value=(document, 'Texto seguro')) as preview:
            response = self.client.get('/familia/api/planner/documents/3')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'document': document, 'preview': 'Texto seguro'})
        preview.assert_called_once_with(12, 7, 3)

    def test_planner_document_index_requires_context(self):
        self.assertEqual(self.client.get('/familia/api/planner/documents').status_code, 401)
        self.login()
        with mock.patch('aicentralv2.cadu_planner.docs.list_documents', return_value=[]) as documents:
            response = self.client.get('/familia/api/planner/documents')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'documents': []})
        documents.assert_called_once_with(12, 7)

    def test_planner_docs_write_routes_require_flag_and_carry_authorized_context(self):
        self.login()
        payload = {'title': 'Plano', 'type': 'briefing', 'html': '<p>Seguro</p>'}
        with mock.patch('aicentralv2.cadu_planner.docs.create_document') as create:
            self.assertEqual(self.post('planner/docs', payload).status_code, 403)
            create.assert_not_called()
        self.app.config['CADU_FAMILY_WRITES_ENABLED'] = True
        document = {'id': 4, **payload, 'status': 'draft', 'is_owner': True}
        with mock.patch('aicentralv2.cadu_planner.docs.create_document', return_value=document) as create:
            response = self.post('planner/docs', payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), {'document': document})
        create.assert_called_once_with(12, 7, payload)

    def test_planner_docs_save_uses_context_and_csrf(self):
        self.login()
        self.app.config['CADU_FAMILY_WRITES_ENABLED'] = True
        saved = {'id': 4, 'title': 'Atualizado', 'status': 'published', 'is_owner': True}
        with mock.patch('aicentralv2.cadu_planner.docs.save_document', return_value=saved) as save:
            response = self.client.put('/familia/api/planner/docs/4', json={'title': 'Atualizado'},
                                       headers={'X-CSRF-Token': 'token'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'document': saved})
        save.assert_called_once_with(12, 7, 4, {'title': 'Atualizado'})
