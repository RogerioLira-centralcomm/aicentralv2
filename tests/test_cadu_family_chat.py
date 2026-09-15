import json
from unittest import TestCase, mock

from aicentralv2.cadu_family import chat


class ChatStreamTest(TestCase):
    def setUp(self):
        self.run = {'run_id': 'run', 'conversation_id': 'conversation',
                    'organization_id': 12, 'user_id': 7, 'payload': {'user': 'user-7'}}
        self.db = mock.MagicMock()
        patch = mock.patch.object(chat.repository, 'get_db', return_value=self.db)
        patch.start()
        self.addCleanup(patch.stop)

    def events(self, provider_events):
        with mock.patch.object(chat.dify, 'events', return_value=iter(provider_events)):
            return [json.loads(value.removeprefix('data: ')) for value in chat.stream(self.run)]

    def test_completed_stream_persists_usage_and_response(self):
        events = self.events([
            {'event': 'message', 'answer': 'Olá', 'conversation_id': 'provider'},
            {'event': 'message_end', 'metadata': {'usage': {'prompt_tokens': 10, 'completion_tokens': 2}}},
        ])
        self.assertEqual([item['event'] for item in events], ['start', 'message', 'done'])
        self.assertEqual(events[-1]['status'], 'completed')
        calls = self.db.cursor.return_value.__enter__.return_value.execute.call_args_list
        usage = [call.args[1] for call in calls if 'INSERT INTO cadu_token_usage' in call.args[0]]
        self.assertEqual([(row[2], row[3], row[4], row[5]) for row in usage],
                         [(12, 7, 'entrada', 10), (12, 7, 'saida', 2)])
        self.db.commit.assert_called_once()

    def test_incomplete_response_is_not_reported_as_completed(self):
        events = self.events([{'event': 'message', 'answer': 'Parcial'}])
        self.assertEqual(events[-1]['status'], 'failed')
        self.assertEqual(events[-2]['event'], 'error')
        calls = self.db.cursor.return_value.__enter__.return_value.execute.call_args_list
        message = next(call.args[1] for call in calls if 'INSERT INTO cadu_conversation_messages' in call.args[0])
        self.assertEqual(message[2], 'Parcial')

    def test_disconnect_stops_provider_and_saves_partial_response(self):
        with mock.patch.object(chat.dify, 'events', return_value=iter([
            {'event': 'message', 'answer': 'Parcial', 'task_id': 'task-1'},
        ])), mock.patch.object(chat.dify, 'stop') as stop:
            stream = chat.stream(self.run)
            next(stream)
            next(stream)
            stream.close()
            stop.assert_called_once_with('task-1', 'user-7')
        calls = self.db.cursor.return_value.__enter__.return_value.execute.call_args_list
        status = next(call.args[1][0] for call in calls if 'SET status = %s' in call.args[0])
        self.assertEqual(status, 'stopped')
