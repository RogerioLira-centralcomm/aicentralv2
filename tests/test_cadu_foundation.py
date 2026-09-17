from unittest import mock

from tests import test_cadu_family as family
from tests.test_product_portals import _app
from aicentralv2.product_domains import safe_product_target


class FoundationTest(family.FamilyTest):
    def test_read_only_gate_blocks_all_database_mutations(self):
        self.login()
        with mock.patch('aicentralv2.cadu_family.repository.get_db') as db:
            for method, path in (
                ('post', '/api/entities'), ('patch', '/api/entities/ci:example'),
                ('patch', '/api/profile'), ('post', '/api/actions/link-report-project'),
                ('post', '/api/actions/00000000-0000-0000-0000-000000000001/confirm'),
            ):
                with self.subTest(path=path):
                    result = getattr(self.client, method)('/familia' + path, json={}, headers={'X-CSRF-Token': 'token'})
                    self.assertEqual(result.status_code, 403)
            db.assert_not_called()

    def test_conversation_does_not_depend_on_workspace_write_flags(self):
        self.login()
        with mock.patch('aicentralv2.cadu_family.chat.prepare') as prepare:
            prepare.return_value = {'queued': True, 'run_id': '00000000-0000-0000-0000-000000000001',
                                    'conversation_id': '00000000-0000-0000-0000-000000000002'}
            response = self.post('conversations/send', {'profile': 'workspace', 'message': 'Olá'})
            self.assertEqual(response.status_code, 202)
            prepare.assert_called_once()

    def test_malformed_context_is_rejected_without_database_write(self):
        self.login()
        for value in (['not-an-object'], {'client_id': 12.5}, {'client_id': True},
                      {'client_id': 12, 'project_ref': ['ci:project']}):
            with self.subTest(value=value):
                self.assertEqual(self.post('context', value).status_code, 400)

    def test_auth_return_target_cannot_escape_configured_origins(self):
        with _app().app_context():
            for value in ('//evil.test', '/\\evil.test', '/%5cevil.test', '/%2fevil.test',
                          'https://user:pass@workspace.centralcomm.media/',
                          'https://workspace.centralcomm.media:444/',
                          'https://workspace.centralcomm.media:bad/',
                          'https://[invalid', '/safe%0d%0aLocation:evil',
                          'https://workspace.centralcomm.media.evil.test/'):
                with self.subTest(value=value):
                    self.assertEqual(safe_product_target(value, '/safe'), '/safe')
            self.assertEqual(safe_product_target('/familia/studio/copy-ads?format=3'), '/familia/studio/copy-ads?format=3')
            self.assertEqual(safe_product_target('https://workspace.centralcomm.media/familia/workspace/'),
                             'https://workspace.centralcomm.media/familia/workspace/')
