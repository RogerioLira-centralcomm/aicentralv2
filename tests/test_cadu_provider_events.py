import json
from unittest import TestCase

from aicentralv2.cadu_workspace.conversations.provider_events import ProviderEvents
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
