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


DOCUMENT = {'id': 'doc_8013fefa59ce84c9_1786454296', 'title': 'Plano de mídia', 'type': 'planejamento',
            'status': 'draft', 'html': '<p>Contexto</p>', 'is_owner': True}


class WorkspaceDocumentsTest(TestCase):
    def setUp(self):
        self.client = _app().test_client()
        with self.client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')

    @mock.patch('aicentralv2.cadu_planner.docs.get_document', return_value=DOCUMENT)
    def test_document_opens_in_workspace_editor(self, get_document):
        response = self.client.get(f"/docs/{DOCUMENT['id']}")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Editor Cadu', html)
        self.assertIn('data-editor-content contenteditable="true"', html)
        self.assertIn('data-public-root=', html)
        get_document.assert_called_once_with(12, 7, DOCUMENT['id'])

    @mock.patch('aicentralv2.cadu_planner.docs.save_document')
    def test_document_save_uses_workspace_session_and_csrf(self, save_document):
        response = self.client.post(f"/docs/{DOCUMENT['id']}", data={
            '_csrf': 'known-token', 'title': 'Plano atualizado',
            'status': 'published', 'html': '<p>Conteúdo revisto</p>',
        })
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['Location'], f"/docs/{DOCUMENT['id']}?saved=1")
        save_document.assert_called_once_with(12, 7, DOCUMENT['id'], {
            'title': 'Plano atualizado', 'status': 'published',
            'html': '<p>Conteúdo revisto</p>',
        })

    @mock.patch('aicentralv2.cadu_planner.docs.save_document')
    def test_document_save_rejects_missing_csrf(self, save_document):
        response = self.client.post(f"/docs/{DOCUMENT['id']}", data={'title': 'Plano'})
        self.assertEqual(response.status_code, 403)
        save_document.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_documents_list_renders_string_document_ids(self, get_db):
        cursor = get_db.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [{
            'id': DOCUMENT['id'], 'titulo': DOCUMENT['title'], 'tipo': DOCUMENT['type'],
            'status': DOCUMENT['status'], 'updated_at': None,
        }]

        response = self.client.get('/docs')

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'/docs/{DOCUMENT["id"]}', response.get_data(as_text=True))

    @mock.patch('aicentralv2.cadu_planner.docs.create_document', return_value=DOCUMENT)
    def test_conversation_text_becomes_an_editable_workspace_document(self, create_document):
        response = self.client.post('/workspace/api/documentos', json={
            'title': 'Leitura de mercado', 'content': '# Leitura\nConteúdo estruturado para o projeto.',
            'sources': [{'title': 'Fonte pública', 'url': 'https://example.com/source'}],
        }, headers={'X-CSRF-Token': 'known-token'})
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()['document']
        self.assertEqual(payload['id'], DOCUMENT['id'])
        self.assertEqual(payload['editor_url'], f'/docs/{DOCUMENT["id"]}')
        saved = create_document.call_args.args[2]
        self.assertEqual(saved['project_id'], None)
        self.assertIn('Fontes consultadas', saved['html'])

    @mock.patch('aicentralv2.cadu_planner.docs.share_document', return_value={**DOCUMENT, 'share_enabled': True, 'share_token': 'public-token'})
    @mock.patch('aicentralv2.cadu_planner.docs.save_document', return_value={**DOCUMENT, 'status': 'published'})
    @mock.patch('aicentralv2.cadu_planner.docs.create_document', return_value={**DOCUMENT, 'id': 'gallery-1'})
    def test_gallery_requires_https_images_and_publishes_only_selected_ones(self, create_document, save_document, share_document):
        response = self.client.post('/workspace/api/artefatos/galeria', json={
            'title': 'Seleção criativa',
            'images': ['https://cdn.example/one.png', 'http://unsafe.example/two.png', 'https://cdn.example/one.png'],
        }, headers={'X-CSRF-Token': 'known-token'})
        self.assertEqual(response.status_code, 200)
        created = create_document.call_args.args[2]
        self.assertIn('https://cdn.example/one.png', created['html'])
        self.assertNotIn('http://unsafe.example/two.png', created['html'])
        save_document.assert_called_once_with(12, 7, 'gallery-1', {'status': 'published'})
        share_document.assert_called_once_with(12, 7, 'gallery-1', True)
