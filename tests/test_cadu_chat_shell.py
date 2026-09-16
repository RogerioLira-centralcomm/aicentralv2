"""Regression coverage for the authenticated shared chat shells."""
from html.parser import HTMLParser
from unittest import TestCase

from flask import Flask
from aicentralv2.cadu_workspace.routes import bp
from tests.test_cadu_skills import ROOT


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.items = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


class ChatShellTest(TestCase):
    def setUp(self):
        app = Flask(__name__, template_folder=str(ROOT / 'aicentralv2/templates'))
        app.secret_key = 'test'
        app.register_blueprint(bp)
        app.context_processor(lambda: {'product_url': lambda product, path='': '/' + product + path})
        self.client = app.test_client()

    def test_workspace_conversation_has_one_complete_composer_without_user_variable(self):
        with self.client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12)
        response = self.client.get('/workspace/app/conversas')
        self.assertEqual(response.status_code, 200)
        elements = Elements(response.get_data(as_text=True)).items
        for element_id in ('conversation-panel', 'conversation-message', 'conversation-mode', 'conversation-send', 'conversation-new'):
            self.assertEqual(sum(attrs.get('id') == element_id for _, attrs in elements), 1, element_id)
        body = next(attrs for tag, attrs in elements if tag == 'body')
        self.assertEqual(body['data-product'], 'workspace')
        self.assertEqual(body['data-authenticated'], 'true')
        panel = next(attrs for _, attrs in elements if attrs.get('id') == 'conversation-panel')
        self.assertNotIn('hidden', panel)
        self.assertEqual(panel['data-conversation-page'], 'true')
        self.assertFalse(any(attrs.get('id') == 'conversation-open' for _, attrs in elements))
        token = next(attrs['content'] for tag, attrs in elements if tag == 'meta' and attrs.get('name') == 'csrf-token')
        with self.client.session_transaction() as session:
            self.assertEqual(token, session['family_csrf'])
