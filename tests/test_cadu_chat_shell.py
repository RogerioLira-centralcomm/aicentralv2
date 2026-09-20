"""Regression coverage for the authenticated shared chat shells."""
from unittest import TestCase

from flask import Flask
from aicentralv2.cadu_workspace.routes import bp
from tests.test_cadu_skills import ROOT


class ChatShellTest(TestCase):
    def setUp(self):
        app = Flask(__name__, template_folder=str(ROOT / 'aicentralv2/templates'))
        app.secret_key = 'test'
        app.register_blueprint(bp)
        app.context_processor(lambda: {'product_url': lambda product, path='': '/' + product + path})
        self.client = app.test_client()

    def test_workspace_conversation_route_moves_to_react_v2(self):
        with self.client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12)
        response = self.client.get('/conversas')
        self.assertEqual(response.status_code, 308)
        self.assertTrue(response.headers['Location'].endswith('/workspace/conversas-v2-lab'))
