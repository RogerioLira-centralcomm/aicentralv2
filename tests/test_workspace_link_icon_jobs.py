from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace import link_icon_jobs


class WorkspaceLinkIconJobsTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.get_db')
    def test_claim_respects_global_running_limit(self, get_db):
        connection = get_db.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'total': 2}
        self.assertIsNone(link_icon_jobs.claim(max_running=2))
        connection.commit.assert_called_once_with()
        self.assertNotIn('WITH candidate', '\n'.join(call.args[0] for call in cursor.execute.call_args_list))

    def test_enqueue_rejects_backlog_before_creating_paid_job(self):
        cursor = mock.MagicMock()
        cursor.fetchone.return_value = {'total': 50}
        with self.assertRaises(ValueError):
            link_icon_jobs.enqueue(cursor, job_id='job', client_id=12, user_id=7,
                                   target_type='project', target_id='link', project_id='project', host='example.com')
        self.assertEqual(cursor.execute.call_count, 1)

    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.threading.Thread')
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.finish')
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.generate_dock_icon', return_value=True)
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs._patch_metadata', return_value=True)
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.close_db')
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.claim')
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.reap_stale')
    def test_worker_processes_one_persisted_job(self, _reap, claim, _close, _patch, generate, finish, thread):
        claim.return_value = {'id':'00000000-0000-0000-0000-000000000001', 'client_id':12, 'user_id':7,
                              'target_type':'project', 'target_id':'00000000-0000-0000-0000-000000000002',
                              'project_id':'project-1', 'host':'example.com'}
        with Flask(__name__).app_context():
            self.assertTrue(link_icon_jobs.process_one())
        generate.assert_called_once()
        self.assertEqual(generate.call_args.kwargs['host'], 'example.com')
        finish.assert_called_once_with('00000000-0000-0000-0000-000000000001', True)
        thread.return_value.start.assert_called_once_with()

    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.threading.Thread')
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.finish')
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.generate_dock_icon')
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs._patch_metadata', return_value=False)
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.claim')
    @mock.patch('aicentralv2.cadu_workspace.link_icon_jobs.reap_stale')
    def test_deleted_link_is_not_sent_to_image_provider(self, _reap, claim, _patch, generate, finish, _thread):
        claim.return_value = {'id':'00000000-0000-0000-0000-000000000001', 'client_id':12, 'user_id':7,
                              'target_type':'dock', 'target_id':'00000000-0000-0000-0000-000000000002',
                              'project_id':None, 'host':'example.com'}
        with Flask(__name__).app_context():
            self.assertTrue(link_icon_jobs.process_one())
        generate.assert_not_called()
        finish.assert_called_once_with('00000000-0000-0000-0000-000000000001', False)
