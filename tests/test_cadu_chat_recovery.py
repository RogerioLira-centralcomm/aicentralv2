from unittest import TestCase, mock
from uuid import uuid4

from flask import Flask
from werkzeug.exceptions import Conflict

from aicentralv2.cadu_family.routes import bp
from aicentralv2.cadu_workspace.conversations import recovery, service


class RecoveryTest(TestCase):
    def setUp(self):
        self.user = {'id': 7, 'organization_id': 12}
        self.id = str(uuid4())
        self.row = dict(run_id=self.id, conversation_id='thread', status='running',
                        user_id=7, client_id=14, organization_id=12, request_hash='hash')
        self.cur = mock.MagicMock()
        self.cur.fetchone.return_value = self.row

    def test_same_key_returns_projection_without_provider_details(self):
        result = recovery.existing_run(self.cur, self.id, self.user, 14, 'hash')
        self.assertEqual(result, dict(run_id=self.id, conversation_id='thread', status='running', recovered=True))
        self.assertIn('pg_advisory_xact_lock', self.cur.execute.call_args_list[0].args[0])
        self.assertEqual(len(self.cur.execute.call_args_list), 2)

    def test_changed_payload_old_hash_and_other_owners_are_rejected(self):
        for change in ({'request_hash': None}, {'request_hash': 'changed'},
                       {'user_id': 8}, {'client_id': 15}, {'organization_id': 99}):
            with self.subTest(change=change):
                self.cur.fetchone.return_value = {**self.row, **change}
                with self.assertRaises(Conflict):
                    recovery.existing_run(self.cur, self.id, self.user, 14, 'hash')

    def test_new_request_is_not_recovered(self):
        self.cur.fetchone.return_value = None
        self.assertIsNone(recovery.existing_run(self.cur, self.id, self.user, 14, 'hash'))

    def test_fingerprint_is_order_independent_but_binds_all_inputs(self):
        payload = dict(message='Olá', mode='ideias', profile='workspace', files=['file'], conversation_id=None)
        original = recovery.fingerprint(payload)
        self.assertEqual(original, recovery.fingerprint(dict(reversed(list(payload.items())))))
        self.assertEqual(original, recovery.fingerprint({**payload, 'request_id': str(uuid4())}))
        for key in payload:
            with self.subTest(key=key):
                self.assertNotEqual(original, recovery.fingerprint({**payload, key: 'changed'}))

    def test_state_query_scopes_conversation_and_returns_no_payload_or_task(self):
        with mock.patch.object(recovery.repository, 'rows', return_value=[]) as rows:
            self.assertIsNone(recovery.state(self.id, self.user, 14))
        sql, params = rows.call_args.args
        self.assertEqual(params, (self.id, 7, 14, 12, 7, 14, 7, 14))
        self.assertNotIn('task_id', sql)
        self.assertNotIn('request_hash', sql)

    def test_prepare_replay_does_not_check_balance_or_insert_messages(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        db = mock.MagicMock()
        previous = {'recovered': True, 'run_id': self.id}
        with app.test_request_context(), \
                mock.patch.object(service.dify, 'settings'), \
                mock.patch.object(service.context, 'identity', return_value=self.user), \
                mock.patch.object(service.context, 'inventory', return_value=[]), \
                mock.patch.object(service, 'modes', return_value=[{'id': 'ideias'}]), \
                mock.patch.object(service.repository, 'get_db', return_value=db), \
                mock.patch.object(recovery, 'existing_run', return_value=previous), \
                mock.patch.object(service, 'lock_organization_generation') as admission:
            result = service.prepare(dict(request_id=self.id, message='Olá', profile='workspace'), {'client_id': 14})
        self.assertEqual(result, previous)
        admission.assert_not_called()
        db.cursor.return_value.__enter__.return_value.execute.assert_not_called()
        db.rollback.assert_called_once()


class RecoveryRouteTest(TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY='test', TESTING=True, CADU_FAMILY_ENABLED=True,
                          CADU_FAMILY_CHAT_ENABLED=True, CADU_FAMILY_WRITES_ENABLED=True)
        app.register_blueprint(bp)
        self.client = app.test_client()
        self.id = str(uuid4())
        self.user = {'id': 7, 'organization_id': 12}
        for name, result in [('identity', self.user), ('resolve', {'client_id': 14, 'role': 'member'})]:
            patch = mock.patch('aicentralv2.cadu_family.routes.context.' + name, return_value=result)
            patch.start()
            self.addCleanup(patch.stop)

    def test_state_not_found_and_no_store(self):
        with mock.patch.object(recovery, 'state', return_value=None) as state:
            self.assertEqual(self.client.get('/familia/api/conversations/runs/' + self.id).status_code, 404)
            state.assert_called_once_with(self.id, self.user, 14)
            state.return_value = dict(run_id=self.id, status='completed', conversation_id='thread')
            response = self.client.get('/familia/api/conversations/runs/' + self.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.json['status'], 'completed')

    def test_replay_returns_json_without_starting_stream(self):
        with self.client.session_transaction() as session:
            session.update(user_id=7, family_csrf='token')
        with mock.patch('aicentralv2.cadu_family.routes.writable_context', return_value={'client_id':14}), \
                mock.patch('aicentralv2.cadu_family.chat.prepare', return_value={'recovered':True, 'run_id':self.id}), \
                mock.patch('aicentralv2.cadu_family.chat.stream') as stream:
            response = self.client.post('/familia/api/conversations/send', json={'profile':'workspace'}, headers={'X-CSRF-Token':'token'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['recovered'])
        stream.assert_not_called()
