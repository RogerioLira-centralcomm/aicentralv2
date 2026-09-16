import json
from unittest import TestCase

from aicentralv2.cadu_workspace.conversations.legacy_results import project_message, saved_images, readable_documents


class LegacyResultsTest(TestCase):
    def test_image_results_preserve_urls_and_hide_tool_inputs(self):
        url = 'https://old.example/image.png?token=x%2By'
        message = {'role':'assistant', 'content':'Pronto', 'tool_calls':[
            {'tool':'image_generate', 'params':{'prompt':'private'}, 'result':{'image_url':url}},
            {'tool':'image_generate', 'result':{'success':True, 'data':{'url':url}}}]}
        result = project_message(message)
        self.assertEqual(result['files'], [{'name':'Criativo gerado', 'url':url}])
        self.assertNotIn('tool_calls', result)
        self.assertNotIn('private', json.dumps(result))
        self.assertIn('tool_calls', message)  # No mutation of stored input.

    def test_unknown_tools_errors_and_input_urls_are_not_results(self):
        calls = [{'tool':'web_search', 'result':{'url':'https://example.com'}},
                 {'tool':'image_generate', 'params':{'url':'https://example.com'}},
                 {'tool':'image_generate', 'result':{'success':False, 'url':'https://example.com'}},
                 {'tool':'image_generate', 'result':{'url':'javascript:alert(1)'}}, None]
        self.assertEqual(saved_images(calls), [])
        self.assertEqual(saved_images('{invalid'), [])

    def test_json_string_and_existing_attachment_deduplication(self):
        url = 'https://old.example/creative'
        calls = json.dumps([{'tool':'image_generate', 'result':{'url':url}}])
        result = project_message({'role':'assistant', 'files':[{'name':'Original', 'url':url}], 'tool_calls':calls})
        self.assertEqual(result['files'], [{'name':'Original', 'url':url}])

    def test_smart_docs_become_readable_without_changing_other_text(self):
        content = 'Antes\n<!--SMART_DOC:' + json.dumps({'titulo':'Plano', 'conteudo':'Meta\n- Alcance'}) + '-->\nDepois'
        result = readable_documents(content)
        self.assertIn('Plano\n\nMeta\n- Alcance', result)
        self.assertTrue(result.startswith('Antes'))
        self.assertTrue(result.endswith('Depois'))
        self.assertNotIn('SMART_DOC', result)

    def test_unknown_incomplete_and_empty_documents_are_preserved(self):
        for text in ('<!--SMART_DOC:{bad}-->', '<!--SMART_DOC:{', '<!--SMART_DOC:{"conteudo":""}-->'):
            self.assertEqual(readable_documents(text), text)

    def test_user_content_is_not_interpreted_as_a_tool_result(self):
        text = '<!--SMART_DOC:{"conteudo":"example"}-->'
        result = project_message({'role':'user', 'content':text, 'tool_calls':[
            {'tool':'image_generate', 'result':{'url':'https://example.com'}}]})
        self.assertEqual(result['content'], text)
        self.assertEqual(result['files'], [])
