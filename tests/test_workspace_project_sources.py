from io import BytesIO
from pathlib import Path
from unittest import TestCase, mock
from zipfile import ZipFile

from flask import Flask
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_workspace import project_sources
from aicentralv2.cadu_workspace.routes import bp
from aicentralv2.training_studio.extract import validate_public_url


def _app(instance_path=None):
    app = Flask(__name__, instance_path=instance_path) if instance_path else Flask(__name__)
    app.config.update(SECRET_KEY='test', TESTING=True)
    app.register_blueprint(bp)
    return app


class WorkspaceProjectSourcesTest(TestCase):
    @mock.patch('aicentralv2.cadu_workspace.routes.credit_position', return_value={
        'configured': True, 'available': 2_500_000, 'monthly': 2_700_000,
    })
    def test_credit_summary_exposes_the_shared_live_balance(self, credit_position):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=174)
        response = client.get('/workspace/api/creditos/resumo')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['available'], 2_500_000)
        credit_position.assert_called_once_with(174)

    @mock.patch('aicentralv2.training_studio.extract.socket.getaddrinfo', return_value=[(None, None, None, None, ('8.8.8.8', 443))])
    def test_url_without_protocol_is_normalized_to_https(self, _addresses):
        self.assertEqual(
            validate_public_url('www.exemplo.com.br/guia'),
            'https://www.exemplo.com.br/guia',
        )

    def test_url_with_an_unsupported_scheme_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_public_url('ftp://exemplo.com.br/arquivo')

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

    def test_note_uses_durable_index_queue_when_enabled(self):
        app = _app()
        app.config['CADU_PROJECT_INDEX_ASYNC_ENABLED'] = True
        with mock.patch('aicentralv2.cadu_workspace.routes._editable_workspace_project', return_value={'id': 'p-1'}), \
             mock.patch('aicentralv2.cadu_workspace.routes._persist_project_source') as persist, \
             mock.patch('aicentralv2.cadu_workspace.routes.project_index_service.persist_pending_source', return_value=41), \
             mock.patch('aicentralv2.cadu_workspace.routes.get_db') as get_db, \
             mock.patch('aicentralv2.cadu_workspace.project_index_jobs.enqueue', return_value='job-1') as enqueue:
            connection = mock.MagicMock()
            get_db.return_value = connection
            client = app.test_client()
            with client.session_transaction() as session:
                session.update(user_id=7, cliente_id=12, family_csrf='known-token')
            response = client.post('/workspace/app/projetos/p-1/fontes/notas', data={
                '_csrf': 'known-token',
                'title': 'Diretriz aprovada',
                'content': 'Contexto aprovado para orientar todo o projeto e a equipe.',
            }, headers={'Accept': 'application/json'})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json(), {
            'ok': True, 'source_id': 41, 'job_id': 'job-1', 'status': 'queued',
        })
        persist.assert_not_called()
        enqueue.assert_called_once_with(12, 'p-1', 41, 7)
        connection.commit.assert_called_once_with()

    def test_upload_uses_durable_index_queue_when_enabled(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            app = _app(folder)
            app.config['CADU_PROJECT_INDEX_ASYNC_ENABLED'] = True
            with mock.patch('aicentralv2.cadu_workspace.routes._editable_workspace_project', return_value={'id': 'p-1'}), \
                 mock.patch('aicentralv2.cadu_workspace.routes._persist_project_source') as persist, \
                 mock.patch('aicentralv2.cadu_workspace.routes.project_index_service.persist_pending_source', return_value=42), \
                 mock.patch('aicentralv2.cadu_workspace.routes.get_db') as get_db, \
                 mock.patch('aicentralv2.cadu_workspace.project_index_jobs.enqueue', return_value='job-2') as enqueue:
                connection = mock.MagicMock()
                get_db.return_value = connection
                client = app.test_client()
                with client.session_transaction() as session:
                    session.update(user_id=7, cliente_id=12, family_csrf='known-token')
                response = client.post('/workspace/app/projetos/p-1/fontes/arquivos', data={
                    '_csrf': 'known-token',
                    'file': (BytesIO(b'Contexto aprovado para orientar todo o projeto.'), 'contexto.txt'),
                }, headers={'Accept': 'application/json'})

            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.get_json()['job_id'], 'job-2')
            persist.assert_not_called()
            enqueue.assert_called_once_with(12, 'p-1', 42, 7)
            pending_path = Path(folder) / 'workspace_project_sources' / '12' / 'p-1'
            self.assertTrue(any(pending_path.glob('*.txt')))

    def test_note_falls_back_to_sync_when_queue_migration_is_missing(self):
        app = _app()
        app.config['CADU_PROJECT_INDEX_ASYNC_ENABLED'] = True
        with mock.patch('aicentralv2.cadu_workspace.routes._editable_workspace_project', return_value={'id': 'p-1'}), \
             mock.patch('aicentralv2.cadu_workspace.routes._persist_project_source', return_value=43) as persist, \
             mock.patch('aicentralv2.cadu_workspace.routes.project_index_service.persist_pending_source', return_value=43), \
             mock.patch('aicentralv2.cadu_workspace.routes.get_db') as get_db, \
             mock.patch('aicentralv2.cadu_workspace.project_index_jobs.enqueue', return_value=None), \
             mock.patch('aicentralv2.cadu_workspace.routes._remove_pending_project_source') as remove_pending:
            get_db.return_value = mock.MagicMock()
            client = app.test_client()
            with client.session_transaction() as session:
                session.update(user_id=7, cliente_id=12, family_csrf='known-token')
            response = client.post('/workspace/app/projetos/p-1/fontes/notas', data={
                '_csrf': 'known-token',
                'title': 'Diretriz legada',
                'content': 'Contexto aprovado para orientar o fallback síncrono.',
            })

        self.assertEqual(response.status_code, 303)
        persist.assert_called_once()
        remove_pending.assert_called_once_with(12, 'p-1', 43)

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

    @mock.patch('aicentralv2.cadu_workspace.routes.threading.Thread')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes._queue_project_url_source', return_value=92)
    @mock.patch('aicentralv2.cadu_workspace.routes.project_sources.extract_public_url')
    @mock.patch('aicentralv2.cadu_credit_connector.CaduCreditConnector.authorize_firecrawl')
    def test_url_import_marks_the_source_as_workspace_owned(self, _authorize, extract, queue, _project, thread):
        extract.return_value = {
            'url': 'https://example.com/guia', 'name': 'Guia',
            'mime': 'text/uri-list', 'text': 'Conteúdo suficiente para orientar o projeto.',
        }
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')
        with mock.patch('aicentralv2.training_studio.extract.socket.getaddrinfo',
                        return_value=[(None, None, None, None, ('8.8.8.8', 443))]):
            response = client.post('/workspace/app/projetos/p-1/fontes/urls', data={
                '_csrf': 'known-token', 'url': 'https://example.com/guia',
            })
        self.assertEqual(response.status_code, 303)
        thread.return_value.start.assert_called_once()
        queue.assert_called_once_with(12, 'p-1', 7, 'https://example.com/guia')
        extract.assert_not_called()

    @mock.patch('aicentralv2.cadu_workspace.routes.threading.Thread')
    @mock.patch('aicentralv2.cadu_workspace.routes._workspace_project', return_value={'id': 'p-1'})
    @mock.patch('aicentralv2.cadu_workspace.routes._queue_project_url_source', return_value=93)
    @mock.patch('aicentralv2.cadu_credit_connector.CaduCreditConnector.authorize_firecrawl')
    def test_url_import_queues_scrape_without_blocking_the_browser(self, _authorize, queue, _project, thread):
        client = _app().test_client()
        with client.session_transaction() as session:
            session.update(user_id=7, cliente_id=12, family_csrf='known-token')
        with mock.patch('aicentralv2.training_studio.extract.socket.getaddrinfo',
                        return_value=[(None, None, None, None, ('8.8.8.8', 443))]):
            response = client.post('/workspace/app/projetos/p-1/fontes/urls', data={
                '_csrf': 'known-token', 'url': 'www.exemplo.com.br/guia',
            }, headers={'Accept': 'application/json'})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()['status'], 'queued')
        self.assertEqual(response.get_json()['source_id'], 93)
        queue.assert_called_once_with(12, 'p-1', 7, 'https://www.exemplo.com.br/guia')
        thread.return_value.start.assert_called_once()

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
