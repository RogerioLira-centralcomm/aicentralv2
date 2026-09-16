import json
from unittest import TestCase, mock
from uuid import uuid4

from flask import Flask
from aicentralv2.cadu_family.routes import bp
from aicentralv2.cadu_workspace.conversations import jobs, service, recovery


class JobsTest(TestCase):
    def setUp(self):
        self.db = mock.MagicMock()
        self.cur = self.db.cursor.return_value.__enter__.return_value
        patch = mock.patch.object(jobs.repository, 'get_db', return_value=self.db)
        patch.start()
        self.addCleanup(patch.stop)

    def test_enqueue_does_not_commit_separately_from_admission(self):
        jobs.enqueue(self.cur, {'run_id':'id', 'payload':{'query':'hello'}})
        self.assertIn('INSERT INTO cadu_family_chat_jobs', self.cur.execute.call_args.args[0])
        self.db.commit.assert_not_called()

    def test_claim_is_durable_and_only_selects_unclaimed_jobs(self):
        self.cur.fetchone.return_value = {'payload':{'run_id':'id'}}
        self.assertEqual(jobs.claim(), {'run_id':'id'})
        sql = self.cur.execute.call_args.args[0]
        self.assertIn('SKIP LOCKED', sql)
        self.assertIn('claimed_at IS NULL', sql)
        self.db.commit.assert_called_once()

    def test_empty_queue_never_calls_provider(self):
        with mock.patch.object(jobs, 'claim', return_value=None), mock.patch.object(service, 'stream') as stream:
            self.assertFalse(jobs.process_one())
            stream.assert_not_called()

    def test_worker_consumes_and_persists_events_without_http_connection(self):
        def source():
            yield 'data: ' + json.dumps({'event':'message', 'text':'Olá'})
            yield 'data: ' + json.dumps({'event':'done', 'status':'completed'})
        with mock.patch.object(jobs, 'claim', return_value={'run_id':'id'}), \
                mock.patch.object(service, 'stream', return_value=source()), \
                mock.patch.object(jobs, 'append_event') as append:
            self.assertTrue(jobs.process_one())
        self.assertEqual(append.call_count, 2)
        self.assertIn('finished_at', self.cur.execute.call_args.args[0])

    def test_worker_failure_closes_generator_but_does_not_release_claim(self):
        closed = []
        def source():
            try:
                yield 'data: {"event":"message","text":"partial"}'
            finally:
                closed.append(True)
        with mock.patch.object(jobs, 'claim', return_value={'run_id':'id'}), \
                mock.patch.object(service, 'stream', return_value=source()), \
                mock.patch.object(jobs, 'append_event', side_effect=RuntimeError('database failure')):
            with self.assertRaises(RuntimeError):
                jobs.process_one()
        self.assertEqual(closed, [True])
        self.cur.execute.assert_not_called()

    def test_cancel_pending_serializes_with_claim_and_does_not_call_dify(self):
        self.cur.fetchone.return_value = {'run_id':'id'}
        self.assertTrue(jobs.cancel_pending('id'))
        self.assertIn('claimed_at IS NULL', self.cur.execute.call_args_list[0].args[0])
        self.assertIn("status = 'stopped'", self.cur.execute.call_args_list[1].args[0])
        self.db.commit.assert_called_once()

    def test_events_are_bounded_and_scoped_by_run_and_cursor(self):
        with mock.patch.object(jobs.repository, 'rows', return_value=[{'id':25, 'event':{'event':'done'}}]) as rows:
            self.assertEqual(jobs.page('id', 20)['next_cursor'], 25)
        self.assertEqual(rows.call_args.args[1], ('id', 20))
        self.assertIn('LIMIT 100', rows.call_args.args[0])


class JobRoutesTest(TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY='test', TESTING=True, CADU_FAMILY_ENABLED=True,
                          CADU_FAMILY_CHAT_ENABLED=True, CADU_FAMILY_WRITES_ENABLED=True,
                          CADU_CHAT_WORKER_ENABLED=True)
        app.register_blueprint(bp)
        self.client = app.test_client()
        self.id = str(uuid4())

    def test_event_endpoint_checks_ownership_before_reading_journal(self):
        with mock.patch('aicentralv2.cadu_family.routes.context.identity', return_value={'id':7}), \
                mock.patch('aicentralv2.cadu_family.routes.context.resolve', return_value={'client_id':12}), \
                mock.patch.object(recovery, 'state', return_value=None), \
                mock.patch.object(jobs, 'page') as page:
            self.assertEqual(self.client.get('/familia/api/conversations/runs/' + self.id + '/events').status_code, 404)
            page.assert_not_called()

    def test_event_endpoint_validates_cursor(self):
        with mock.patch('aicentralv2.cadu_family.routes.context.identity', return_value={'id':7}), \
                mock.patch('aicentralv2.cadu_family.routes.context.resolve', return_value={'client_id':12}), \
                mock.patch.object(recovery, 'state', return_value={'status':'running'}), \
                mock.patch.object(jobs, 'page', return_value={'events':[], 'next_cursor':3}) as page:
            for cursor in ('-1', 'invalid', '9223372036854775808'):
                self.assertEqual(self.client.get('/familia/api/conversations/runs/' + self.id + '/events?after=' + cursor).status_code, 400)
            page.assert_not_called()
            response = self.client.get('/familia/api/conversations/runs/' + self.id + '/events?after=3')
            self.assertEqual(response.json['status'], 'running')
            page.assert_called_once_with(self.id, 3)

    def test_queue_acceptance_does_not_start_provider_in_request(self):
        with self.client.session_transaction() as session:
            session.update(user_id=7, family_csrf='token')
        with mock.patch('aicentralv2.cadu_family.routes.writable_context', return_value={'client_id':12}), \
                mock.patch('aicentralv2.cadu_family.chat.prepare', return_value={'queued':True, 'run_id':self.id, 'conversation_id':'thread'}), \
                mock.patch('aicentralv2.cadu_family.chat.stream') as stream:
            response = self.client.post('/familia/api/conversations/send', json={'profile':'workspace'}, headers={'X-CSRF-Token':'token'})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json['accepted'])
        stream.assert_not_called()

    def test_worker_cli_disabled_by_default(self):
        self.client.application.config['CADU_CHAT_WORKER_ENABLED'] = False
        with mock.patch.object(jobs, 'process_one') as process:
            result = self.client.application.test_cli_runner().invoke(args=['cadu_family', 'chat-worker-once'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('desabilitado', result.output)
        process.assert_not_called()

    def test_state_only_advertises_replay_for_an_authorized_durable_job(self):
        with mock.patch('aicentralv2.cadu_family.routes.context.identity', return_value={'id':7}), \
                mock.patch('aicentralv2.cadu_family.routes.context.resolve', return_value={'client_id':12}), \
                mock.patch.object(recovery, 'state', return_value=None) as state, \
                mock.patch.object(jobs.repository, 'rows', return_value=[{'run_id':self.id}]) as rows:
            url = '/familia/api/conversations/runs/' + self.id
            self.assertEqual(self.client.get(url).status_code, 404)
            rows.assert_not_called()
            state.return_value = {'status':'running', 'conversation_id':'thread'}
            self.assertTrue(self.client.get(url).json['replay'])
            rows.return_value = []
            self.assertFalse(self.client.get(url).json['replay'])
            rows.reset_mock()
            self.client.application.config['CADU_CHAT_WORKER_ENABLED'] = False
            self.assertFalse(self.client.get(url).json['replay'])
            rows.assert_not_called()
