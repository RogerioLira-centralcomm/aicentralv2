from unittest import TestCase, mock

from aicentralv2.cadu_workspace.conversations.service import project_knowledge_context, project_sources
from aicentralv2.cadu_workspace.conversations.legacy_results import project_message


class ChatProjectKnowledgeTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.conversations.service.repository.rows')
    def test_context_keeps_project_brand_and_citable_sources_in_one_client_scope(self, rows):
        rows.side_effect = [
            [{'nome': 'Lançamento', 'descricao': 'Novo produto', 'instrucoes': 'Seja claro',
              'publico': 'Pessoas em movimento', 'posicionamento': 'Prático', 'tom_de_voz': 'Direto'}],
            [{'name': 'Marca Cadu', 'sector': 'Serviços', 'website_url': 'https://marca.example',
              'brand_profile': '{"tone_of_voice":"Calmo"}'}],
            [{'titulo': 'Pesquisa de público', 'trecho': 'O público valoriza praticidade.'}],
            [{'total': 2, 'indexed': 1, 'needs_index': 1}],
        ]

        result = project_knowledge_context('ci:project-1', 'studio:11', 44, 'qual é o público?')

        self.assertIn('"projeto"', result)
        self.assertIn('"marca"', result)
        self.assertIn('https://marca.example', result)
        self.assertIn('"fontes_verificadas"', result)
        self.assertIn('Pesquisa de público', result)
        self.assertIn('"needs_index": 1', result)
        self.assertNotIn('score', result)
        self.assertEqual(rows.call_args_list[0].args[1], ('project-1', 44))
        self.assertEqual(rows.call_args_list[1].args[1], ('11', 44))
        self.assertEqual(rows.call_args_list[2].args[1][1:3], ('project-1', 44))
        self.assertIn("s.purpose='knowledge_source'", rows.call_args_list[2].args[0])
        self.assertIn("s.indexing_status='completed'", rows.call_args_list[2].args[0])
        self.assertEqual(rows.call_args_list[3].args[1], ('project-1', 44))

    @mock.patch('aicentralv2.cadu_workspace.conversations.service.repository.rows')
    def test_index_failure_keeps_the_explicit_project_context(self, rows):
        rows.side_effect = [
            [{'nome': 'Lançamento', 'descricao': '', 'instrucoes': '', 'publico': '', 'posicionamento': '', 'tom_de_voz': ''}],
            RuntimeError('legacy table missing'),
        ]

        result = project_knowledge_context('ci:project-1', None, 44, 'campanha')

        self.assertIn('Lançamento', result)
        self.assertIn('"fontes_verificadas": []', result)

    @mock.patch('aicentralv2.cadu_workspace.conversations.service.repository.rows')
    def test_strict_index_failure_is_not_reported_as_empty_search(self, rows):
        rows.side_effect = [
            [{'nome': 'Lançamento', 'descricao': '', 'instrucoes': '', 'publico': '', 'posicionamento': '', 'tom_de_voz': ''}],
            RuntimeError('index unavailable'),
        ]
        with self.assertRaises(RuntimeError):
            project_knowledge_context('ci:project-1', None, 44, 'campanha', strict_retrieval=True)

    def test_non_canonical_project_reference_never_queries_context(self):
        with mock.patch('aicentralv2.cadu_workspace.conversations.service.repository.rows') as rows:
            self.assertEqual(project_knowledge_context('projects:99', 'studio:11', 44, 'teste'), '')
            rows.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.conversations.service.project_knowledge.query_embedding')
    @mock.patch('aicentralv2.cadu_workspace.conversations.service.repository.rows')
    def test_overview_reads_each_indexed_source_without_embedding_the_question(self, rows, embedding):
        rows.side_effect = [
            [{'nome': 'Oriente 2026', 'descricao': 'Campanha regional'}],
            [{'titulo': 'Briefing', 'trecho': 'Objetivo: empresas locais', 'source_id': 3,
              'chunk_id': 12, 'score': 0}],
            [{'total': 2, 'indexed': 1, 'needs_index': 1}],
        ]

        result = project_knowledge_context('ci:project-1', None, 44,
                                           'O que você sabe sobre esse projeto?', overview=True)

        embedding.assert_not_called()
        self.assertIn('Briefing', result)
        self.assertIn('"needs_index": 1', result)
        self.assertIn('"retrieval_status": "overview"', result)

    def test_source_projection_never_uses_untrusted_fields(self):
        sources = project_sources('{"fontes_verificadas":[{"fonte":"Pesquisa","trecho":"Dado verificado","url":"https://fora"}]}')
        self.assertEqual(sources, [{'title': 'Pesquisa', 'excerpt': 'Dado verificado'}])

    def test_saved_message_normalizes_json_metadata_for_history_replay(self):
        message = project_message({
            'role': 'assistant', 'content': 'Resposta', 'files': [],
            'metadata': '{"project_sources":[{"title":"Pesquisa","excerpt":"Dado"}]}'
        })
        self.assertEqual(message['metadata']['project_sources'][0]['title'], 'Pesquisa')
