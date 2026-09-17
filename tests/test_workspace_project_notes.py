from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import _chunk_project_note, _workspace_rich_text, bp


def _app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    return app


class WorkspaceProjectNotesTest(TestCase):
    def test_project_context_markdown_is_rendered_as_safe_structure(self):
        rendered = str(_workspace_rich_text('**Faça:**\n- Use dados aprovados\n- Cite a fonte'))
        self.assertIn('<strong>Faça:</strong>', rendered)
        self.assertIn('<ul><li>Use dados aprovados</li>', rendered)
        self.assertNotIn('**Faça:**', rendered)

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_legacy_project_image_is_served_from_authorized_database_bytes(self, get_db, _project):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {
            'file_bytes': b'legacy-image',
            'mime': 'image/jpeg',
            'title': 'Peça de campanha',
        }
        get_db.return_value = connection
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12)

        response = client.get('/workspace/app/projetos/p-1/imagens/57')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/jpeg')
        self.assertEqual(response.data, b'legacy-image')
        sql = str(cursor.execute.call_args.args[0])
        self.assertIn('cadu_docs_client_images', sql)
        self.assertIn('id_cliente = %s', sql)

    def test_chunker_preserves_paragraphs_and_splits_large_blocks(self):
        chunks = _chunk_project_note('Primeiro parágrafo.\n\n' + ('contexto ' * 500), limit=120)
        self.assertGreater(len(chunks), 2)
        self.assertEqual(chunks[0], 'Primeiro parágrafo.')
        self.assertTrue(all(len(chunk) <= 120 for chunk in chunks))

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes.charge_project_rag')
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_note_is_stored_as_completed_source_and_searchable_chunks(self, get_db, charged, _project):
        connection = mock.MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'id': 91}
        get_db.return_value = connection
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')

        response = client.post('/workspace/app/projetos/p-1/fontes/notas', data={
            'title': 'Decisões da reunião',
            'content': 'A campanha prioriza alcance qualificado.\n\nO tom deve ser direto e seguro.',
            '_csrf': 'known-token',
        })

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['Location'], '/workspace/app/projetos/p-1')
        sql = '\n'.join(str(call.args[0]) for call in cursor.execute.call_args_list)
        self.assertIn('INSERT INTO cadu_ci_projeto_arquivos', sql)
        self.assertIn('INSERT INTO cadu_ci_chunks', sql)
        self.assertIn('UPDATE cadu_ci_projetos', sql)
        charged.assert_called_once()
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    def test_note_requires_enough_reviewed_context(self, _project):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')
        response = client.post('/workspace/app/projetos/p-1/fontes/notas', data={
            'title': 'Breve', 'content': 'Curto', '_csrf': 'known-token',
        })
        self.assertEqual(response.status_code, 400)
