from io import BytesIO
from unittest import TestCase, mock
from zipfile import ZipFile

from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from tests.test_cadu_family import FamilyTest
from aicentralv2.cadu_workspace.conversations import attachments
from aicentralv2.cadu_workspace.conversations.guardrails import classify_intent, require_available_intent
from werkzeug.exceptions import Conflict


class AttachmentValidationTest(TestCase):
    @staticmethod
    def office_package(part):
        data = BytesIO()
        with ZipFile(data, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr(part, '<document/>')
        return data.getvalue()

    def test_image_content_is_verified_not_browser_mime(self):
        data = BytesIO(); Image.new('RGB', (2, 2)).save(data, format='PNG'); data.seek(0)
        file, kind, size = attachments.validate(FileStorage(data, filename='../../imagem.png', content_type='text/html'))
        self.assertEqual(file.filename, 'imagem.png')
        self.assertEqual(file.mimetype, 'image/png')
        self.assertEqual(kind, 'image')
        self.assertGreater(size, 0)

    def test_rejects_disguised_image_binary_text_empty_and_unsupported_files(self):
        for name, data in [('fake.png', b'<script>alert(1)</script>'), ('fake.txt', b'\x00binary'),
                           ('empty.txt', b''), ('file.svg', b'<svg/>'), ('file.docx', b'PK')]:
            with self.subTest(name=name), self.assertRaises(BadRequest):
                attachments.validate(FileStorage(BytesIO(data), filename=name))

    def test_bounded_read_even_when_content_length_is_missing(self):
        with mock.patch.object(attachments, 'MAX_BYTES', 3), self.assertRaises(RequestEntityTooLarge):
            attachments.validate(FileStorage(BytesIO(b'abcd'), filename='a.txt'))

    def test_multipart_body_is_bounded_before_form_parsing(self):
        oversized = mock.MagicMock(content_length=None, stream=BytesIO(b'a' * (65536 + 5)))
        with mock.patch.object(attachments, 'MAX_BYTES', 3), self.assertRaises(RequestEntityTooLarge):
            attachments.bound_multipart_request(oversized)
        declared = mock.MagicMock(content_length=65540)
        with mock.patch.object(attachments, 'MAX_BYTES', 3), self.assertRaises(RequestEntityTooLarge):
            attachments.bound_multipart_request(declared)
        declared.stream.read.assert_not_called()

    def test_text_does_not_need_local_disk_storage(self):
        file, kind, _ = attachments.validate(FileStorage(BytesIO('Olá'.encode()), filename='a.md'))
        self.assertEqual(kind, 'document')
        self.assertEqual(file.mimetype, 'text/markdown')

    def test_validates_real_office_packages_without_extracting_them(self):
        for name, part, mime in (
            ('brief.docx', 'word/document.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            ('dados.xlsx', 'xl/workbook.xml', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('roteiro.pptx', 'ppt/presentation.xml', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'),
        ):
            with self.subTest(name=name):
                file, kind, _ = attachments.validate(FileStorage(BytesIO(self.office_package(part)), filename=name))
                self.assertEqual(kind, 'document')
                self.assertEqual(file.mimetype, mime)

    def test_upload_saves_scoped_reference_without_exposing_provider_id(self):
        db = mock.MagicMock()
        with mock.patch.object(attachments.repository, 'get_db', return_value=db), \
             mock.patch.object(attachments.repository, 'family_table_available', return_value=True), \
             mock.patch.object(attachments.dify, 'upload', return_value='private-provider-reference') as provider:
            result = attachments.upload(FileStorage(BytesIO(b'hello'), filename='demo.txt'), {'id':7}, {'client_id':24})
        self.assertNotIn('private-provider-reference', str(result))
        self.assertEqual(provider.call_args.args[1], 'user-7')
        params = db.cursor.return_value.__enter__.return_value.execute.call_args.args[1]
        self.assertEqual(params[1:4], (7,24,'private-provider-reference'))
        db.commit.assert_called_once()

    def test_missing_schema_does_not_send_bytes_to_provider(self):
        with mock.patch.object(attachments.repository, 'get_db'), \
             mock.patch.object(attachments.repository, 'family_table_available', return_value=False), \
             mock.patch.object(attachments.dify, 'upload') as provider, self.assertRaises(BadRequest):
            attachments.upload(FileStorage(BytesIO(b'hello'), filename='demo.txt'), {'id':7}, {'client_id':24})
        provider.assert_not_called()

    def test_text_and_confirmations_do_not_trigger_image_tools(self):
        for message in ('Crie o texto para a imagem', 'Agora crie a legenda do post', 'não, pode seguir', 'ok manda'):
            self.assertIn(require_available_intent(message), ('text', 'continuation'))

    def test_explicit_unmigrated_tools_are_not_silently_sent(self):
        for message in ('Crie uma imagem de produto', 'Pesquise na web sobre mídia', 'Testa esse link https://example.org', 'Tira um print de example.org'):
            with self.subTest(message=message), self.assertRaises(Conflict):
                require_available_intent(message)
        self.assertEqual(classify_intent('Como organizar meu projeto?'), 'conversation')


class AttachmentRouteTest(FamilyTest):
    def upload(self, **extra):
        return self.client.post('/familia/api/conversations/uploads',
            data={'file': (BytesIO(b'conteudo'), 'a.txt'), **extra}, headers={'X-CSRF-Token': 'token'})

    def test_guest_cannot_upload_but_chat_does_not_depend_on_workspace_writes(self):
        with mock.patch.object(attachments, 'upload', return_value={'id': 'file-id'}) as upload:
            self.assertEqual(self.upload().status_code, 401)
            self.login()
            self.assertEqual(self.upload().status_code, 201)
            upload.assert_called_once()

    def test_csrf_is_required_but_upload_does_not_depend_on_a_feature_flag(self):
        self.login(); self.app.config['CADU_FAMILY_WRITES_ENABLED'] = True
        self.assertEqual(self.client.post('/familia/api/conversations/uploads').status_code, 403)
        with mock.patch.object(attachments, 'upload', return_value={'id': 'file-id'}):
            self.assertEqual(self.upload().status_code, 201)

    def test_upload_uses_server_identity_and_selected_client(self):
        self.login(); self.app.config.update(CADU_FAMILY_WRITES_ENABLED=True, CADU_FAMILY_CHAT_ENABLED=True)
        with mock.patch.object(attachments, 'upload', return_value={'id': 'file-id'}) as upload:
            response = self.upload(user='attacker', client_id='999')
            self.assertEqual(response.status_code, 201)
            self.assertEqual(upload.call_args.args[1]['id'], 7)
            self.assertEqual(upload.call_args.args[2]['client_id'], 12)

    def test_capabilities_require_a_configured_provider_and_guest_has_no_access(self):
        self.assertEqual(self.client.get('/familia/api/conversations/capabilities').status_code, 401)
        self.login()
        data = self.client.get('/familia/api/conversations/capabilities').get_json()
        self.assertFalse(data['attachments']); self.assertFalse(data['send'])
        self.assertEqual(data['max_files'], 3)
        self.assertIn('conexão do Cadu', data['reason'])

    def test_capabilities_explain_when_dify_is_not_ready(self):
        self.login()
        self.app.config.update(CADU_FAMILY_WRITES_ENABLED=True, CADU_FAMILY_CHAT_ENABLED=True,
                               CADU_DIFY_API_KEY='')
        data = self.client.get('/familia/api/conversations/capabilities').get_json()
        self.assertFalse(data['send'])
        self.assertIn('conexão do Cadu', data['reason'])

    def test_preflight_does_not_call_dify_or_write(self):
        self.login()
        with mock.patch('aicentralv2.cadu_family.dify.events') as provider:
            self.assertEqual(self.post('conversations/preflight', {'message': 'Crie uma imagem'}).status_code, 409)
            self.assertEqual(self.post('conversations/preflight', {'message': 'Crie o texto da imagem'}).status_code, 200)
            provider.assert_not_called()
