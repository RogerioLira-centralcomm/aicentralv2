from unittest import TestCase, mock
from flask import Flask
from aicentralv2.cadu_family.routes import bp
from aicentralv2.cadu_family import repository


class HistoryTest(TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY='test', TESTING=True, CADU_FAMILY_ENABLED=True)
        app.register_blueprint(bp)
        self.client = app.test_client()
        self.user = {'id': 7, 'organization_id': 12}
        for name, value in [('identity', self.user), ('resolve', {'client_id': 12})]:
            patch = mock.patch('aicentralv2.cadu_family.routes.context.' + name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_history_returns_all_matching_conversations(self):
        records = [{'id': str(i), 'status': 'active'} for i in range(13)]
        with mock.patch.object(repository, 'conversation_history_all', return_value=records) as history:
            response = self.client.get('/familia/api/conversations?q=campanha')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['conversations'], records)
        self.assertNotIn('next_offset', response.json)
        history.assert_called_once_with(self.user, 12, query='campanha')

    def test_workspace_host_keeps_history_available_without_family_pages(self):
        self.client.application.config.update(
            CADU_FAMILY_ENABLED=False,
            WORKSPACE_URL='https://workspace.centralcomm.media',
        )
        with mock.patch.object(repository, 'conversation_history_all', return_value=[]) as history:
            response = self.client.get('/familia/api/conversations', headers={'Host': 'workspace.centralcomm.media'})
        self.assertEqual(response.status_code, 200)
        history.assert_called_once()

    def test_legacy_page_parameter_is_ignored(self):
        with mock.patch.object(repository, 'conversation_history_all', return_value=[]) as history:
            self.assertEqual(self.client.get('/familia/api/conversations?offset=20').status_code, 200)
            history.assert_called_once_with(self.user, 12, query='')

    def test_missing_conversation_does_not_reveal_context(self):
        with mock.patch.object(repository, 'conversation_messages', return_value=None), mock.patch.object(repository, 'conversation_context') as bound:
            self.assertEqual(self.client.get('/familia/api/conversations/foreign/messages').status_code, 404)
            bound.assert_not_called()

    def test_history_and_context_queries_bind_user_and_tenant(self):
        with mock.patch.object(repository, 'family_table_available', return_value=True), mock.patch.object(repository, 'rows', return_value=[]) as rows:
            repository.conversation_history_all(self.user, 12, query="' OR 1=1")
            sql, params = rows.call_args.args
            self.assertNotIn("' OR 1=1", sql)
            self.assertEqual(params, (7, 12, "%\' OR 1=1%", ['ativa', 'active', 'arquivada', 'archived'], 7, 12, 12,
                                      ['ativa', 'active'], 500))
            repository.conversation_context(self.user, 12, 'thread')
            self.assertEqual(rows.call_args.args[1], ('thread', 7, 12, 12))

    def test_archived_conversations_are_returned_with_the_history(self):
        rows = [{'id': 'active', 'status': 'active'}, {'id': 'archived', 'status': 'archived'}]
        with mock.patch.object(repository, 'conversation_history_all', return_value=rows):
            response = self.client.get('/familia/api/conversations')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['conversations'], rows)

    def test_mutation_requires_csrf_and_write_flag(self):
        with self.client.session_transaction() as session:
            session.update(user_id=7, family_csrf='token')
        with mock.patch.object(repository, 'update_conversation') as update:
            self.assertEqual(self.client.patch('/familia/api/conversations/id', json={'archived':True}).status_code, 403)
            self.assertEqual(self.client.patch('/familia/api/conversations/id', json={'archived':True}, headers={'X-CSRF-Token':'token'}).status_code, 403)
            update.assert_not_called()

    def test_mutation_validates_payload_and_scopes_owner(self):
        self.client.application.config['CADU_FAMILY_WRITES_ENABLED'] = True
        with self.client.session_transaction() as session:
            session.update(user_id=7, family_csrf='token')
        with mock.patch('aicentralv2.cadu_family.routes.writable_context', return_value={'client_id':12}), mock.patch.object(repository, 'update_conversation', return_value={'id':'id'}) as update:
            for payload in ({'archived':'yes'}, {'title':' '}, {'client_id':99}, []):
                self.assertEqual(self.client.patch('/familia/api/conversations/id', json=payload, headers={'X-CSRF-Token':'token'}).status_code, 400)
            update.assert_not_called()
            response = self.client.patch('/familia/api/conversations/id', json={'title':' Novo '}, headers={'X-CSRF-Token':'token'})
            self.assertEqual(response.status_code, 200)
            update.assert_called_once_with(7, 12, 'id', 'Novo', None)
            update.return_value = None
            self.assertEqual(self.client.patch('/familia/api/conversations/foreign', json={'archived':True}, headers={'X-CSRF-Token':'token'}).status_code, 404)
