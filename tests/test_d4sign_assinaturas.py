import unittest
from io import BytesIO
from unittest.mock import Mock, patch

from flask import Flask

from aicentralv2.assinaturas import service
from aicentralv2.assinaturas.helpers import serialize_document
from aicentralv2.assinaturas.routes import bp
from aicentralv2.services.d4sign_client import D4SignClient


class D4SignClientTest(unittest.TestCase):
    def test_embed_url_uses_production_host_and_signer(self):
        client = D4SignClient("token", "crypt", ambiente="producao")
        url = client.embed_url("doc-1", "apolo@centralcomm.media", "key-9")
        self.assertIn("secure.d4sign.com.br/embed/viewblob/doc-1", url)
        self.assertIn("email=apolo%40centralcomm.media", url)
        self.assertIn("key_signer=key-9", url)


class AssinaturasServiceTest(unittest.TestCase):
    def test_webhook_marks_signer_and_partial_status(self):
        document = {"id": 4, "tipo_vinculo": "interno", "id_vinculo": None}
        repo = Mock()
        repo.obter_por_uuid.return_value = document
        repo.listar_signatarios.return_value = [
            {"email": "a@centralcomm.media", "status": "assinado"},
            {"email": "b@centralcomm.media", "status": "pendente"},
        ]
        with patch.object(service, "integration_credentials") as credentials, patch.object(
            service, "_repo", return_value=repo
        ):
            credentials.get_configuration.return_value = {"webhook_secret": "hook"}
            result = service.processar_webhook(
                {
                    "uuid": "abc",
                    "type_post": "4",
                    "signer": {"email": "a@centralcomm.media"},
                },
                secret="hook",
            )
        self.assertTrue(result["ok"])
        repo.marcar_signatario.assert_called_once()
        repo.atualizar_status.assert_called_once_with(4, "parcialmente_assinado")

    def test_webhook_finalizes_and_closes_pi_checklist(self):
        document = {"id": 7, "tipo_vinculo": "pi", "id_vinculo": 99}
        repo = Mock()
        repo.obter_por_uuid.return_value = document
        repo.listar_signatarios.return_value = [
            {"email": "a@centralcomm.media", "status": "pendente"},
        ]
        with patch.object(service, "integration_credentials") as credentials, patch.object(
            service, "_repo", return_value=repo
        ), patch.object(service, "_concluir_checklist_pi") as checklist:
            credentials.get_configuration.return_value = {}
            service.processar_webhook({"uuid": "abc", "type_post": "1"})
        checklist.assert_called_once_with(99)
        repo.atualizar_status.assert_called_with(7, "finalizado")

    def test_serialize_document_counts_pending(self):
        payload = serialize_document(
            {
                "id": 1,
                "titulo": "NDA",
                "status": "aguardando_assinaturas",
                "tipo_vinculo": "interno",
                "signatarios": [
                    {"email": "a@x.com", "status": "pendente", "nome": "A"},
                    {"email": "b@x.com", "status": "assinado", "nome": "B"},
                ],
            }
        )
        self.assertEqual(payload["pendentes"], 1)
        self.assertEqual(payload["status_label"], "Aguardando assinaturas")


class AssinaturasApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="test", TESTING=True)
        self.app.register_blueprint(bp)
        self.client = self.app.test_client()

    def test_webhook_is_public(self):
        with patch.object(service, "processar_webhook", return_value={"ok": True}):
            response = self.client.post(
                "/assinaturas/api/webhook",
                json={"uuid": "abc", "type_post": "1"},
            )
        self.assertEqual(response.status_code, 200)

    def test_list_requires_login(self):
        response = self.client.get("/assinaturas/api")
        self.assertEqual(response.status_code, 401)

    def test_create_uses_uploaded_pdf(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_email"] = "apolo@centralcomm.media"
        created = {"id": 3, "titulo": "NDA"}
        with patch.object(service, "criar_documento", return_value=created) as create:
            response = self.client.post(
                "/assinaturas/api",
                data={
                    "titulo": "NDA",
                    "tipo_vinculo": "interno",
                    "signatarios": '[{"email":"apolo@centralcomm.media","nome":"Apolo"}]',
                    "arquivo": (BytesIO(b"%PDF-1.4"), "nda.pdf"),
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(create.called)


if __name__ == "__main__":
    unittest.main()
