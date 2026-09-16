from unittest import TestCase, mock

from aicentralv2.cadu_workspace.conversations.service import project_knowledge_context, project_sources
from aicentralv2.cadu_workspace.conversations.legacy_results import project_message


class ChatProjectKnowledgeTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.conversations.service.repository.rows')
    def test_context_keeps_project_brand_and_citable_sources_in_one_client_scope(self, rows):
        rows.side_effect = [
            [{'nome': 'Lançamento', 'descricao': 'Novo produto', 'instrucoes': 'Seja claro',
              'publico': 'Pessoas em movimento', 'posicionamento': 'Prático', 'tom_de_voz': 'Direto'}],
            [{'name': 'Marca Cadu', 'sector': 'Serviços', 'brand_profile': '{"tone_of_voice":"Calmo"}'}],
            [{'titulo': 'Pesquisa de público', 'trecho': 'O público valoriza praticidade.'}],
        ]

        result = project_knowledge_context('ci:project-1', 'studio:11', 44, 'qual é o público?')

        self.assertIn('"projeto"', result)
        self.assertIn('"marca"', result)
        self.assertIn('"fontes_verificadas"', result)
        self.assertIn('Pesquisa de público', result)
        self.assertNotIn('score', result)
        self.assertEqual(rows.call_args_list[0].args[1], ('project-1', 44))
        self.assertEqual(rows.call_args_list[1].args[1], ('11', 44))
        self.assertEqual(rows.call_args_list[2].args[1][0:2], ('project-1', 44))

    @mock.patch('aicentralv2.cadu_workspace.conversations.service.repository.rows')
    def test_index_failure_keeps_the_explicit_project_context(self, rows):
        rows.side_effect = [
            [{'nome': 'Lançamento', 'descricao': '', 'instrucoes': '', 'publico': '', 'posicionamento': '', 'tom_de_voz': ''}],
            RuntimeError('legacy table missing'),
        ]

        result = project_knowledge_context('ci:project-1', None, 44, 'campanha')

        self.assertIn('Lançamento', result)
        self.assertIn('"fontes_verificadas": []', result)

    def test_non_canonical_project_reference_never_queries_context(self):
        with mock.patch('aicentralv2.cadu_workspace.conversations.service.repository.rows') as rows:
            self.assertEqual(project_knowledge_context('projects:99', 'studio:11', 44, 'teste'), '')
            rows.assert_not_called()

    def test_source_projection_never_uses_untrusted_fields(self):
        sources = project_sources('{"fontes_verificadas":[{"fonte":"Pesquisa","trecho":"Dado verificado","url":"https://fora"}]}')
        self.assertEqual(sources, [{'title': 'Pesquisa', 'excerpt': 'Dado verificado'}])

    def test_saved_message_normalizes_json_metadata_for_history_replay(self):
        message = project_message({
            'role': 'assistant', 'content': 'Resposta', 'files': [],
            'metadata': '{"project_sources":[{"title":"Pesquisa","excerpt":"Dado"}]}'
        })
        self.assertEqual(message['metadata']['project_sources'][0]['title'], 'Pesquisa')
