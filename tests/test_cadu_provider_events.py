import json
from unittest import TestCase, mock

from aicentralv2.cadu_workspace.conversations.provider_events import ProviderEvents
from aicentralv2.cadu_workspace.conversations import catalog_tools
from aicentralv2.cadu_planner import docs
from tests.test_cadu_family_chat import ChatStreamTest


class ProviderProjectionTest(TestCase):
    def test_text_chunk_and_final_authoritative_answer(self):
        adapter = ProviderEvents()
        self.assertEqual(adapter.feed({'event': 'text_chunk', 'data': {'text': 'Rascunho'}}),
                         [{'event': 'message', 'text': 'Rascunho'}])
        self.assertEqual(adapter.feed({'event': 'message_end', 'answer': 'Final'}),
                         [{'event': 'replace', 'text': 'Final'}])
        self.assertTrue(adapter.completed)
        self.assertEqual(adapter.answer, 'Final')

    def test_workflow_answer_waits_for_chat_terminal_confirmation(self):
        adapter = ProviderEvents()
        adapter.feed({'event': 'workflow_finished', 'data': {'status': 'succeeded', 'outputs': {'answer': 'Plano'}}})
        self.assertEqual(adapter.answer, 'Plano')
        self.assertFalse(adapter.completed)
        self.assertEqual(adapter.feed({'event': 'message_end', 'answer': 'Plano'}), [])
        self.assertTrue(adapter.completed)

    def test_reasoning_tool_inputs_and_internal_titles_are_never_forwarded(self):
        adapter = ProviderEvents()
        events = []
        for kind in ('agent_thought', 'thinking', 'message_thinking', 'tool_call', 'node_started'):
            events += adapter.feed({'event': kind, 'thought': 'PRIVATE', 'thinking': 'PRIVATE',
                                    'tool_input': 'PRIVATE', 'observation': 'PRIVATE',
                                    'data': {'title': 'PRIVATE', 'outputs': {'secret': 'PRIVATE'}}})
        self.assertNotIn('PRIVATE', json.dumps(events))
        self.assertEqual(adapter.answer, '')
        self.assertTrue(all(item['event'] == 'progress' for item in events))

    def test_repeated_progress_does_not_flood_client(self):
        adapter = ProviderEvents()
        self.assertEqual(len(adapter.feed({'event': 'node_started'})), 1)
        self.assertEqual(adapter.feed({'event': 'node_finished'}), [])

    def test_workflow_failure_cannot_become_success(self):
        for status in ('failed', 'stopped', 'partial-succeeded'):
            adapter = ProviderEvents()
            with self.assertRaises(ValueError):
                adapter.feed({'event': 'workflow_finished', 'data': {'status': status}})
            adapter.feed({'event': 'message_end'})
            self.assertFalse(adapter.completed)

    def test_structures_are_not_stringified_into_customer_answer(self):
        adapter = ProviderEvents()
        for kind in ('message', 'agent_message', 'message_replace', 'message_end'):
            self.assertEqual(adapter.feed({'event': kind, 'answer': {'private': 'secret'}, 'metadata': []}), [])
        self.assertEqual(adapter.answer, '')

    def test_unknown_and_file_events_do_not_expose_unvalidated_urls(self):
        adapter = ProviderEvents()
        self.assertEqual(adapter.feed({'event': 'message_file', 'url': 'https://private/secret'}), [])
        self.assertEqual(adapter.feed({'event': 'custom', 'data': 'secret'}), [])
        self.assertEqual(adapter.feed(None), [])

    def test_delta_repetitions_are_preserved_and_replacement_can_clear(self):
        adapter = ProviderEvents()
        for _ in range(2):
            adapter.feed({'event': 'message', 'answer': 'ha'})
        self.assertEqual(adapter.answer, 'haha')
        self.assertEqual(adapter.feed({'event': 'message_replace', 'answer': ''}), [{'event': 'replace', 'text': ''}])


class CatalogToolProjectionTest(TestCase):
    def test_only_planner_allowlisted_tool_gets_projected_card(self):
        with mock.patch.object(catalog_tools.catalog, 'query', return_value=[{'id': 1, 'name': 'Vídeo'}]) as query:
            card = catalog_tools.project({'event': 'tool_call', 'tool': 'channel_search', 'tool_input': '{"search":"vídeo","limit":2}'}, 'planner')
        self.assertEqual(card, {'event': 'catalog', 'catalog_kind': 'canais', 'records': [{'id': 1, 'name': 'Vídeo'}]})
        query.assert_called_once_with('canais', 'vídeo', 2)

    def test_tool_card_rejects_unknown_tools_and_non_channel_workspace_catalogs(self):
        with mock.patch.object(catalog_tools.catalog, 'query') as query:
            # Conversas is allowed to surface channel, audience and format
            # references; the wider Planner catalogs stay scoped to Planner.
            self.assertIsNone(catalog_tools.project({'tool': 'place_search', 'tool_input': '{}'}, 'workspace'))
            self.assertIsNone(catalog_tools.project({'tool': 'web_scrape', 'tool_input': '{}'}, 'planner'))
        query.assert_not_called()

    def test_untrusted_tool_input_is_bounded_and_invalid_input_is_not_executed(self):
        with mock.patch.object(catalog_tools.catalog, 'query') as query:
            self.assertIsNone(catalog_tools.project({'tool': 'channel_search', 'tool_input': '{bad'}, 'planner'))
            self.assertIsNone(catalog_tools.project({'tool': 'channel_search', 'tool_input': 'x' * 4097}, 'planner'))
        query.assert_not_called()

    def test_detail_rejects_missing_id_and_catalog_errors_do_not_break_stream(self):
        self.assertIsNone(catalog_tools.project({'tool': 'format_detail', 'tool_input': '{}'}, 'planner'))
        with mock.patch.object(catalog_tools.catalog, 'detail', side_effect=RuntimeError('private')):
            self.assertIsNone(catalog_tools.project({'tool': 'format_detail', 'tool_input': '{"id": 2}'}, 'planner'))


class PlannerDocumentPreviewTest(TestCase):
    def test_preview_never_returns_stored_html(self):
        raw = {'id': 4, 'title': 'Teste', 'type': 'doc', 'status': 'draft', 'updated_at': 'now', 'is_owner': True,
               'html': '<h1>Plano</h1><script>alert(1)</script><p>Seguro</p>'}
        with mock.patch.object(docs, 'get_document', return_value=raw):
            document, preview = docs.document_preview(12, 7, 4)
        self.assertNotIn('html', document)
        self.assertNotIn('<script>', preview)
        self.assertIn('Plano', preview)
        self.assertIn('Seguro', preview)


class RichStreamPersistenceTest(ChatStreamTest):
    def test_final_only_answer_is_delivered_and_saved(self):
        events = self.events([{'event': 'message_end', 'answer': 'Resposta completa'}])
        self.assertEqual(events[1], {'event': 'replace', 'text': 'Resposta completa'})
        calls = self.db.cursor.return_value.__enter__.return_value.execute.call_args_list
        message = next(call.args[1] for call in calls if 'INSERT INTO cadu_conversation_messages' in call.args[0])
        self.assertEqual(message[2], 'Resposta completa')
        self.assertEqual(events[-1]['status'], 'completed')

    def test_workflow_failure_preserves_partial_without_success(self):
        events = self.events([{'event': 'text_chunk', 'data': {'text': 'Parcial'}},
                              {'event': 'workflow_finished', 'data': {'status': 'failed'}}])
        self.assertEqual(events[1]['text'], 'Parcial')
        self.assertEqual(events[-1]['status'], 'failed')

    def test_error_after_message_end_is_not_saved_as_success(self):
        events = self.events([{'event': 'message_end', 'answer': 'Parcial'}, {'event': 'error'}])
        self.assertEqual(events[-1]['status'], 'failed')

    def test_planner_catalog_card_is_emitted_without_exposing_tool_input(self):
        self.run['profile'] = 'planner'
        with mock.patch('aicentralv2.cadu_workspace.conversations.catalog_tools.catalog.query', return_value=[{'id': 2, 'name': 'Social'}]):
            events = self.events([{'event': 'tool_call', 'tool': 'channel_search', 'tool_input': '{"search":"social"}'},
                                  {'event': 'message_end'}])
        card = next(item for item in events if item['event'] == 'catalog')
        self.assertEqual(card['records'], [{'id': 2, 'name': 'Social'}])
        self.assertNotIn('tool_input', card)
