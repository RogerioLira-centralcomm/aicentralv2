from unittest import TestCase, mock

from aicentralv2.cadu_workspace.conversations import catalog_tools


class ChatCatalogToolsTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.conversations.catalog_tools.catalog.query')
    def test_planner_projects_interactive_search_as_a_safe_catalog_card(self, query):
        query.return_value = [{'id': 8, 'name': 'Quiz em tela cheia'}]

        card = catalog_tools.project({'tool': 'interativo_buscar', 'input': {'q': 'quiz', 'limit': 2}}, 'planner')

        self.assertEqual(card, {'event': 'catalog', 'catalog_kind': 'interativos', 'records': [{'id': 8, 'name': 'Quiz em tela cheia'}]})
        query.assert_called_once_with('interativos', 'quiz', 2)

    @mock.patch('aicentralv2.cadu_workspace.conversations.catalog_tools.catalog.detail')
    def test_planner_projects_interactive_detail_with_only_its_declared_id(self, detail):
        detail.return_value = {'id': 31, 'name': 'Enquete'}

        card = catalog_tools.project({'tool_name': 'interactive_detail', 'tool_input': '{"id":31}'}, 'planner')

        self.assertEqual(card['records'], [{'id': 31, 'name': 'Enquete'}])
        detail.assert_called_once_with('interativos', 31)

    @mock.patch('aicentralv2.cadu_workspace.conversations.catalog_tools.catalog.query')
    def test_catalog_tool_never_runs_outside_the_planner_profile(self, query):
        self.assertIsNone(catalog_tools.project({'tool': 'interativo_buscar', 'input': {'q': 'quiz'}}, 'workspace'))
        query.assert_not_called()

    @mock.patch('aicentralv2.cadu_planner.docs.document_preview')
    def test_planner_projects_a_document_preview_only_for_the_bound_actor_and_client(self, preview):
        preview.return_value = ({'id': 9, 'title': 'Resumo', 'type': 'brief', 'status': 'draft',
                                 'is_owner': True, 'html': '<p>privado</p>'}, 'Resumo seguro para leitura.')

        card = catalog_tools.project({'tool': 'document_preview', 'input': {'id': 9}}, 'planner', 44, 7)

        self.assertEqual(card, {'event': 'document', 'document': {
            'id': 9, 'title': 'Resumo', 'type': 'brief', 'status': 'draft', 'updated_at': None, 'is_owner': True,
        }, 'preview': 'Resumo seguro para leitura.'})
        preview.assert_called_once_with(44, 7, 9)

    @mock.patch('aicentralv2.cadu_planner.docs.document_preview')
    def test_document_preview_requires_bound_client_and_actor(self, preview):
        card = catalog_tools.project({'tool': 'document_preview', 'input': {'id': 9}}, 'planner')
        self.assertIsNone(card)
        preview.assert_not_called()

    @mock.patch('aicentralv2.cadu_planner.plans.list_plans')
    def test_workspace_projects_only_the_bound_actors_plans(self, list_plans):
        list_plans.return_value = [{'id': 'plan-1', 'title': 'Lançamento', 'status': 'draft',
                                    'briefing': {'notes': 'privado'}, 'share_token': 'secret'}]

        card = catalog_tools.project({'tool': 'plan_list', 'input': {}}, 'workspace', 44, 7)

        self.assertEqual(card, {'event': 'catalog', 'catalog_kind': 'planos', 'records': [{
            'id': 'plan-1', 'title': 'Lançamento', 'objective': None, 'status': 'draft',
            'campaign_name': None, 'updated_at': None, 'item_count': None,
        }]})
        list_plans.assert_called_once_with(44, 7)
