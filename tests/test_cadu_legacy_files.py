from unittest import TestCase, mock
from flask import Flask
from aicentralv2.cadu_workspace.conversations.legacy_files import project_files, safe_url
from aicentralv2.cadu_family import repository


class LegacyFilesTest(TestCase):
    def test_old_and_new_links_are_preserved_without_rewriting(self):
        for field in ('url', 'file_url', 'remote_url', 'download_url'):
            url = 'https://old.example/uploads/a.png?signature=abc%2B123&expires=1'
            self.assertEqual(project_files([{'filename': 'Criativo', field: url}]),
                             [{'name': 'Criativo', 'url': url}])
        self.assertEqual(safe_url('https://new.example/file'), 'https://new.example/file')

    def test_unsafe_or_ambiguous_urls_have_no_link(self):
        for url in ('javascript:alert(1)', 'data:text/html,test', '//evil.example/a',
                    'https://user:password@example.com/a', 'https://example.com:bad/a',
                    'https://example.com/\nfile', 'https://example.com\\evil', '/uploads/file'):
            with self.subTest(url=url):
                self.assertIsNone(safe_url(url))

    def test_relative_links_require_explicit_legacy_base(self):
        self.assertEqual(safe_url('uploads/a.png?token=x', 'https://old.example/cadu/'),
                         'https://old.example/cadu/uploads/a.png?token=x')
        self.assertIsNone(safe_url('//evil.example/a', 'https://old.example/'))
        self.assertIsNone(safe_url('file', 'javascript:alert(1)'))

    def test_json_and_malformed_records_are_bounded(self):
        self.assertEqual(project_files('[{"name":"Plano","id":"provider-id"}]'), [{'name':'Plano', 'url':None}])
        for value in (None, '{}', 'invalid', 123):
            self.assertEqual(project_files(value), [])
        self.assertEqual(len(project_files([{'name':'a'}] * 101)), 100)
        self.assertEqual(project_files([None, 12, {'name': {'bad': 1}}]), [{'name':'Arquivo', 'url':None}])

    def test_history_checks_owner_before_reading_files_and_never_writes(self):
        app = Flask(__name__)
        with app.app_context(), mock.patch.object(repository, 'rows', return_value=[]) as rows:
            self.assertIsNone(repository.conversation_messages(7, 12, 'foreign'))
            self.assertEqual(rows.call_count, 1)
            self.assertEqual(rows.call_args.args[1], ('foreign', 7, 12))
        with app.app_context(), mock.patch.object(repository, 'rows', side_effect=[
                [{'id':'owned'}], [{'id':'msg', 'content':'Olá', 'files':[{'url':'https://old.example/a', 'provider_id':'secret'}]}]]) as rows:
            result = repository.conversation_messages(7, 12, 'owned')
            self.assertEqual(result[0]['files'], [{'name':'Arquivo', 'url':'https://old.example/a'}])
            self.assertTrue(all(call.args[0].lstrip().startswith('SELECT') for call in rows.call_args_list))
