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
        for name, result in [('actor', USER), ('clients', CLIENTS), ('entities', ENTITIES), ('entity_links', [])]:
            patch = mock.patch('aicentralv2.cadu_family.repository.' + name, return_value=result)
            setattr(self, name, patch.start())
            self.addCleanup(patch.stop)

    def login(self):
        with self.client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='token')

    def post(self, path, data):
        return self.client.post('/familia/api/' + path, json=data, headers={'X-CSRF-Token': 'token'})

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

    def test_history_read_checks_user_and_client(self):
        self.login()
        with mock.patch('aicentralv2.cadu_family.repository.conversation_messages', return_value=None) as read:
            response = self.client.get('/familia/api/conversations/foreign/messages')
        self.assertEqual(response.status_code, 404)
        read.assert_called_once_with(7, 12, 'foreign')
