from unittest import TestCase, mock

from flask import Flask

from aicentralv2.cadu_workspace.routes import _chunk_project_note, bp


def _app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    return app


class WorkspaceProjectNotesTest(TestCase):
    def test_chunker_preserves_paragraphs_and_splits_large_blocks(self):
        chunks = _chunk_project_note('Primeiro parágrafo.\n\n' + ('contexto ' * 500), limit=120)
        self.assertGreater(len(chunks), 2)
        self.assertEqual(chunks[0], 'Primeiro parágrafo.')
        self.assertTrue(all(len(chunk) <= 120 for chunk in chunks))

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_note_is_stored_as_completed_source_and_searchable_chunks(self, get_db, _project):
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
