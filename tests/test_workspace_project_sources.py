from io import BytesIO
from pathlib import Path
from unittest import TestCase, mock
from zipfile import ZipFile

from flask import Flask
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_workspace import project_sources
from aicentralv2.cadu_workspace.routes import bp


def _app(instance_path=None):
    app = Flask(__name__, instance_path=instance_path) if instance_path else Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    return app


class WorkspaceProjectSourcesTest(TestCase):
    def test_text_upload_is_normalized_for_indexing(self):
        result = project_sources.validate_upload(FileStorage(
            stream=BytesIO('Briefing aprovado para a campanha.'.encode()),
            filename='briefing.md', content_type='text/markdown',
        ))
        self.assertEqual(result['name'], 'briefing.md')
        self.assertEqual(result['mime'], 'text/markdown')
        self.assertIn('Briefing aprovado', result['text'])

    def test_docx_is_read_without_trusting_its_extension(self):
        package = BytesIO()
        with ZipFile(package, 'w') as archive:
            archive.writestr('word/document.xml',
                             '<w:document xmlns:w="urn:w"><w:body><w:p><w:r><w:t>Diretriz segura para a marca.</w:t></w:r></w:p></w:body></w:document>')
        result = project_sources.validate_upload(FileStorage(
            stream=BytesIO(package.getvalue()), filename='diretrizes.docx',
        ))
        self.assertIn('Diretriz segura', result['text'])

    def test_binary_disguised_as_text_is_rejected(self):
        with self.assertRaises(BadRequest):
            project_sources.validate_upload(FileStorage(
                stream=BytesIO(b'conteudo\x00binario que nao pode entrar'), filename='ata.txt',
            ))

    def test_private_path_cannot_escape_the_workspace_storage(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(BadRequest):
                project_sources.resolve_private_path(folder, '../segredo.txt')

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes._persist_project_source', return_value=91)
    def test_upload_requires_csrf_before_writing(self, persist, _project):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')
        response = client.post('/workspace/app/projetos/p-1/fontes/arquivos', data={
            'file': (BytesIO(b'conteudo valido para o projeto e para a equipe'), 'contexto.txt'),
        })
        self.assertEqual(response.status_code, 403)
        persist.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes._persist_project_source', return_value=91)
    def test_valid_text_upload_is_saved_privately(self, persist, _project):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            client = _app(folder).test_client()
            with client.session_transaction() as session:
                session.update(user_id=7, cliente_id=12, family_csrf='known-token')
            response = client.post('/workspace/app/projetos/p-1/fontes/arquivos', data={
                '_csrf': 'known-token',
                'file': (BytesIO(b'Contexto aprovado para orientar todo o projeto.'), 'contexto.txt'),
            })
            self.assertEqual(response.status_code, 303)
            args = persist.call_args.args
            self.assertEqual(args[0:4], (12, 'p-1', 'contexto.txt', 'Contexto aprovado para orientar todo o projeto.'))
            self.assertTrue((Path(folder) / args[6]).is_file())

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project')
    def test_status_projection_does_not_expose_private_paths(self, project):
        project.return_value = {'id': 'p-1', 'files': [{
            'id': 8, 'nome_arquivo': 'guia.pdf', 'indexing_status': 'indexing',
            'word_count': 0, 'erro_msg': None, 'storage_path': 'workspace_project_sources/12/p-1/a.pdf',
        }]}
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12)
        response = client.get('/workspace/api/projetos/p-1/fontes')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['sources'], [{
            'id': 8, 'name': 'guia.pdf', 'status': 'indexing', 'words': 0, 'error': '',
        }])

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    def test_url_import_blocks_local_addresses(self, _project):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')
        response = client.post('/workspace/app/projetos/p-1/fontes/urls', data={
            '_csrf': 'known-token', 'url': 'http://127.0.0.1/admin',
        })
        self.assertEqual(response.status_code, 400)

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes._persist_project_source', return_value=92)
    @mock.patch('aicentralv2.cadu_workspace.routes.project_sources.extract_public_url')
    def test_url_import_marks_the_source_as_workspace_owned(self, extract, persist, _project):
        extract.return_value = {
            'url': 'https://example.com/guia', 'name': 'Guia',
            'mime': 'text/uri-list', 'text': 'Conteúdo suficiente para orientar o projeto.',
        }
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')
        response = client.post('/workspace/app/projetos/p-1/fontes/urls', data={
            '_csrf': 'known-token', 'url': 'https://example.com/guia',
        })
        self.assertEqual(response.status_code, 303)
        self.assertEqual(persist.call_args.args[6], 'workspace-url:https://example.com/guia')

    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes._project_source')
    @mock.patch('aicentralv2.cadu_workspace.routes.get_db')
    def test_legacy_source_cannot_be_removed_by_the_new_workspace(self, get_db, source, _project):
        source.return_value = {'id': 5, 'storage_path': 'uploads/projetos/12/p-1/legado.pdf'}
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')
        response = client.post('/workspace/app/projetos/p-1/fontes/5/remover', data={
            '_csrf': 'known-token',
        })
        self.assertEqual(response.status_code, 409)
        get_db.assert_not_called()
