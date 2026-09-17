from unittest import TestCase, mock
from pathlib import Path

from flask import Flask

from aicentralv2.cadu_workspace.routes import bp


def _app():
    root = Path(__file__).resolve().parents[1]
    app = Flask(__name__, template_folder=str(root / 'aicentralv2/templates'),
                static_folder=str(root / 'aicentralv2/static'))
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.add_url_rule('/login', 'login', lambda: 'login')
    app.register_blueprint(bp)
    app.context_processor(lambda: {'product_url': lambda *_: '/'})
    return app


DOCUMENT = {'id': 17, 'title': 'Plano de mídia', 'type': 'planejamento',
            'status': 'draft', 'html': '<p>Contexto</p>', 'is_owner': True}


class WorkspaceDocumentsTest(TestCase):
    def setUp(self):
        self.client = _app().test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')

    @mock.patch('aicentralv2.cadu_planner.docs.get_document', return_value=DOCUMENT)
    def test_document_opens_in_workspace_editor(self, get_document):
        response = self.client.get('/docs/17')
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Editor Cadu', html)
        self.assertIn('data-editor-content contenteditable="true"', html)
        get_document.assert_called_once_with(12, 7, 17)

    @mock.patch('aicentralv2.cadu_planner.docs.save_document')
    def test_document_save_uses_workspace_session_and_csrf(self, save_document):
        response = self.client.post('/docs/17', data={
            '_csrf': 'known-token', 'title': 'Plano atualizado',
            'status': 'published', 'html': '<p>Conteúdo revisto</p>',
        })
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['Location'], '/docs/17?saved=1')
        save_document.assert_called_once_with(12, 7, 17, {
            'title': 'Plano atualizado', 'status': 'published',
            'html': '<p>Conteúdo revisto</p>',
        })

    @mock.patch('aicentralv2.cadu_planner.docs.save_document')
    def test_document_save_rejects_missing_csrf(self, save_document):
        response = self.client.post('/docs/17', data={'title': 'Plano'})
        self.assertEqual(response.status_code, 403)
        save_document.assert_not_called()
