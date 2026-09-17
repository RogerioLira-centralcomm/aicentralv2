from unittest import TestCase, mock

from aicentralv2.cadu_workspace import project_knowledge


class WorkspaceHybridKnowledgeTest(TestCase):
    def test_semantic_chunks_keep_section_and_overlap(self):
        text = "# Público\n\n" + ("A audiência valoriza clareza e praticidade. " * 80)
        chunks = project_knowledge.split(text, target=300, overlap=40)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(section == 'Público' for _content, section in chunks))
        self.assertIn(chunks[0][0][-30:], chunks[1][0])

    @mock.patch('aicentralv2.cadu_workspace.project_knowledge.requests.post')
    @mock.patch('aicentralv2.cadu_workspace.project_knowledge.resolve_openai_api_key', return_value='key')
    def test_index_records_provider_usage_model_and_hash(self, _key, post):
        response = mock.Mock()
        response.json.return_value = {
            'model': 'text-embedding-3-small', 'usage': {'total_tokens': 19},
            'data': [{'index': 0, 'embedding': [0.1] * project_knowledge.EMBEDDING_DIMENSIONS}],
        }
        post.return_value = response
        records, tokens, model = project_knowledge.index('Contexto confirmado para orientar este projeto.')
        self.assertEqual(tokens, 19)
        self.assertEqual(model, 'text-embedding-3-small')
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0].content_hash), 64)
        self.assertTrue(project_knowledge.vector_literal(records[0].embedding).startswith('['))
