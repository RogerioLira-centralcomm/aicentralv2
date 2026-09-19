import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from flask import Blueprint, Flask

from aicentralv2.integration_settings_routes import (
    register_integration_settings_routes,
)
from aicentralv2.services import integration_credentials
from aicentralv2.services import openrouter_service


ROOT = Path(__file__).resolve().parents[1]


class IntegrationCredentialsServiceTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test",
            INTEGRATION_CREDENTIALS_KEY=Fernet.generate_key().decode(),
            GOOGLE_OAUTH_CLIENT_ID="",
            GOOGLE_OAUTH_CLIENT_SECRET="",
            GOOGLE_OAUTH_REDIRECT_URI="",
            HIGGSFIELD_API_KEY="",
        )
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_encrypts_structured_secret_without_plaintext(self):
        encrypted = integration_credentials.encrypt_secrets(
            {"client_secret": "google-secret"}
        )
        self.assertNotIn("google-secret", encrypted)
        self.assertEqual(
            integration_credentials.decrypt_secrets(encrypted)["client_secret"],
            "google-secret",
        )

    def test_encrypts_with_secret_key_when_dedicated_key_is_unset(self):
        self.app.config["INTEGRATION_CREDENTIALS_KEY"] = ""
        encrypted = integration_credentials.encrypt_secrets(
            {"api_key": "dify-secret"}
        )
        self.assertNotIn("dify-secret", encrypted)
        self.assertEqual(
            integration_credentials.decrypt_secrets(encrypted)["api_key"],
            "dify-secret",
        )

    def test_summary_never_returns_secret(self):
        encrypted = integration_credentials.encrypt_secrets(
            {"api_key": "higgsfield-secret"}
        )
        record = {
            "provider": "higgsfield",
            "public_config": {"workspace_id": "workspace-1"},
            "encrypted_secret": encrypted,
            "status": "active",
        }
        with patch(
            "aicentralv2.db.obter_credencial_integracao", return_value=record
        ):
            summary = integration_credentials.get_summary("higgsfield")
        self.assertTrue(summary["configured"])
        self.assertTrue(summary["has_secret"])
        self.assertNotIn("api_key", summary)
        self.assertNotIn("higgsfield-secret", str(summary))

    def test_openrouter_summary_uses_environment_until_saved(self):
        self.app.config["OPENROUTER_API_KEY"] = "or-env-key"
        self.app.config["AGENT_OPENROUTER_MODEL"] = "openai/gpt-4o-mini"
        with patch("aicentralv2.db.obter_credencial_integracao", return_value=None):
            summary = integration_credentials.get_summary("openrouter")
        self.assertEqual(summary["source"], "environment")
        self.assertTrue(summary["configured"])
        self.assertTrue(summary["has_secret"])
        self.assertEqual(summary["public_config"]["default_model"], "openai/gpt-4o-mini")
        self.app.config["CREATIVE_IMAGE_MODEL"] = "openai/gpt-image-2"
        with patch("aicentralv2.db.obter_credencial_integracao", return_value=None):
            summary = integration_credentials.get_summary("openrouter")
        self.assertEqual(summary["public_config"]["image_model"], "openai/gpt-image-2")
        self.assertNotIn("or-env-key", str(summary))

    def test_firecrawl_summary_uses_environment_until_saved(self):
        self.app.config["FIRECRAWL_API_KEY"] = "fc-env-test"
        with patch("aicentralv2.db.obter_credencial_integracao", return_value=None):
            summary = integration_credentials.get_summary("firecrawl")
            self.assertEqual(
                integration_credentials.resolve_firecrawl_api_key(),
                "fc-env-test",
            )
        self.assertEqual(summary["source"], "environment")
        self.assertTrue(summary["configured"])
        self.assertTrue(summary["has_secret"])
        self.assertNotIn("fc-env-test", str(summary))
        self.assertNotIn("api_key", summary)

    def test_dify_summary_and_runtime_configuration_use_environment(self):
        self.app.config["CADU_DIFY_API_KEY"] = "dify-env-test"
        self.app.config["CADU_DIFY_BASE_URL"] = "https://dify.example/v1"
        with patch("aicentralv2.db.obter_credencial_integracao", return_value=None):
            summary = integration_credentials.get_summary("dify")
            url, key = integration_credentials.resolve_dify_configuration()
        self.assertEqual((url, key), ("https://dify.example/v1", "dify-env-test"))
        self.assertTrue(summary["configured"])
        self.assertTrue(summary["has_secret"])
        self.assertNotIn("dify-env-test", str(summary))
        self.assertNotIn("api_key", summary)

    def test_dify_summary_uses_live_environment_when_database_secret_is_unreadable(self):
        self.app.config["CADU_DIFY_API_KEY"] = "dify-env-test"
        self.app.config["CADU_DIFY_BASE_URL"] = "https://dify.example/v1"
        old_cipher = Fernet(Fernet.generate_key()).encrypt(b'{"api_key":"old-key"}').decode()
        record = {"provider": "dify", "public_config": {"base_url": "https://api.dify.ai/v1"}, "encrypted_secret": old_cipher, "status": "active"}
        with patch("aicentralv2.db.obter_credencial_integracao", return_value=record):
            summary = integration_credentials.get_summary("dify")
        self.assertEqual(summary["source"], "environment")
        self.assertTrue(summary["configured"])
        self.assertFalse(summary["unreadable_secret"])

    def test_brevo_summary_uses_environment_until_saved(self):
        self.app.config["BREVO_API_KEY"] = "brevo-env-test"
        with patch("aicentralv2.db.obter_credencial_integracao", return_value=None):
            summary = integration_credentials.get_summary("brevo")
            self.assertEqual(
                integration_credentials.resolve_brevo_api_key(),
                "brevo-env-test",
            )
        self.assertEqual(summary["source"], "environment")
        self.assertTrue(summary["configured"])
        self.assertTrue(summary["has_secret"])
        self.assertNotIn("brevo-env-test", str(summary))
        self.assertNotIn("api_key", summary)

    def test_openai_summary_uses_environment_until_saved(self):
        self.app.config["OPENAI_API_KEY"] = "sk-proj-env-test"
        self.app.config["OPENAI_DEFAULT_MODEL"] = "gpt-5-mini"
        self.app.config["OPENAI_IMAGE_MODEL"] = "gpt-image-2"
        with patch("aicentralv2.db.obter_credencial_integracao", return_value=None):
            summary = integration_credentials.get_summary("openai")
        self.assertEqual(summary["source"], "environment")
        self.assertTrue(summary["configured"])
        self.assertTrue(summary["has_secret"])
        self.assertEqual(summary["public_config"]["default_model"], "gpt-5-mini")
        self.assertEqual(summary["public_config"]["image_model"], "gpt-image-2")
        self.assertNotIn("sk-proj-env-test", str(summary))
        self.assertNotIn("api_key", summary)

    def test_unreadable_secret_does_not_break_summaries(self):
        record = {
            "provider": "d4sign",
            "public_config": {
                "uuid_safe": "1b4259e5-8c30-42be-9220-a06852cd4c46",
                "ambiente": "producao",
            },
            "encrypted_secret": "gAAAAABunreadable",
            "status": "active",
        }
        with patch(
            "aicentralv2.db.obter_credencial_integracao", return_value=record
        ):
            summary = integration_credentials.get_summary("d4sign")
        self.assertFalse(summary["configured"])
        self.assertTrue(summary["unreadable_secret"])
        self.assertEqual(
            summary["public_config"]["uuid_safe"],
            "1b4259e5-8c30-42be-9220-a06852cd4c46",
        )

    def test_empty_secret_preserves_existing_database_value(self):
        encrypted = integration_credentials.encrypt_secrets(
            {"client_secret": "existing-secret"}
        )
        record = {
            "provider": "google_calendar",
            "public_config": {
                "client_id": "client-id",
                "redirect_uri": "https://centralx.example/perfil/google/callback",
            },
            "encrypted_secret": encrypted,
            "status": "active",
        }
        with patch(
            "aicentralv2.db.salvar_credencial_integracao"
        ) as save, patch(
            "aicentralv2.db.obter_credencial_integracao", return_value=record
        ):
            integration_credentials.save_configuration(
                "google_calendar",
                {
                    "client_id": "client-id",
                    "redirect_uri": "https://centralx.example/perfil/google/callback",
                    "client_secret": "",
                },
                updated_by=7,
            )
        self.assertIsNone(save.call_args.args[2])
        self.assertEqual(save.call_args.args[3], 7)


class IntegrationCredentialsApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="test", TESTING=True)
        bp = Blueprint("parametros_test", __name__, url_prefix="/parametros")
        register_integration_settings_routes(bp)
        self.app.register_blueprint(bp)
        self.client = self.app.test_client()

    def test_api_requires_admin(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 4
            session["user_type"] = "client"
        response = self.client.get("/parametros/api/integrations")
        self.assertEqual(response.status_code, 403)

    def test_admin_lists_only_masked_summaries(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch.object(
            integration_credentials,
            "list_summaries",
            return_value=[{
                "provider": "google_calendar",
                "configured": True,
                "has_secret": True,
                "secret_mask": "••••••••",
                "public_config": {"client_id": "client-id"},
            }],
        ):
            response = self.client.get("/parametros/api/integrations")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertNotIn("client_secret", str(payload))
        self.assertNotIn("encrypted_secret", str(payload))


class IntegrationCredentialsContractTest(unittest.TestCase):
    def test_migration_deploy_menu_and_ui_are_wired(self):
        migration = (
            ROOT / "migrations/add_system_integration_credentials.sql"
        ).read_text()
        deploy = (ROOT / "deploy.sh").read_text()
        menu = (ROOT / "aicentralv2/templates/base_erp.html").read_text()
        template = (
            ROOT / "aicentralv2/templates/parametros/integracoes.html"
        ).read_text()
        self.assertIn("system_integration_credentials", migration)
        self.assertIn("encrypted_secret", migration)
        self.assertIn("run_add_system_integration_credentials.py", deploy)
        self.assertIn("parametros.integracoes", menu)
        self.assertIn("Google Calendar e Meet", template)
        self.assertIn("Higgsfield", template)
        self.assertIn("OpenRouter", template)
        self.assertIn("OpenAI", template)
        self.assertIn("Firecrawl", template)
        self.assertIn("Dify — Conversas Cadu", template)
        self.assertIn('data-integration-form="openrouter"', template)
        self.assertIn('data-integration-form="openai"', template)
        self.assertIn('data-integration-form="firecrawl"', template)
        self.assertIn('data-integration-form="dify"', template)
        self.assertIn("run_add_openrouter_integration_credential.py", deploy)
        self.assertIn("run_add_openai_integration_credential.py", deploy)
        self.assertIn("run_add_firecrawl_integration_credential.py", deploy)
        self.assertIn("run_add_dify_integration_credential.py", deploy)
        self.assertIn("run_add_brevo_integration_credential.py", deploy)
        self.assertIn("run_add_openrouter_gpt_image_2.py", deploy)
        image_sql = (ROOT / "migrations/add_openrouter_gpt_image_2.sql").read_text()
        self.assertIn("openai/gpt-image-2", image_sql)
        self.assertIn('name="image_model"', template)
        self.assertIn("D4Sign", template)
        self.assertIn("assinaturas.mesa", menu)
        self.assertIn("run_add_d4sign_assinaturas.py", deploy)
        self.assertNotIn("value=\"{{", template)
        openrouter_sql = (
            ROOT / "migrations/add_openrouter_integration_credential.sql"
        ).read_text()
        self.assertIn("openrouter", openrouter_sql)
        self.assertIn("d4sign", openrouter_sql)
        openai_sql = (ROOT / "migrations/add_openai_integration_credential.sql").read_text()
        self.assertIn("openai", openai_sql)
        firecrawl_sql = (
            ROOT / "migrations/add_firecrawl_integration_credential.sql"
        ).read_text()
        self.assertIn("firecrawl", firecrawl_sql)
        brevo_sql = (
            ROOT / "migrations/add_brevo_integration_credential.sql"
        ).read_text()
        self.assertIn("brevo", brevo_sql)
        d4sign_sql = (ROOT / "migrations/add_d4sign_assinaturas.sql").read_text()
        self.assertIn("openai", d4sign_sql)
        self.assertIn("firecrawl", d4sign_sql)
        self.assertIn("brevo", d4sign_sql)
        self.assertIn("google_login_cadu", d4sign_sql)
        self.assertIn("google_login_centralx", d4sign_sql)
        self.assertIn("d4sign", d4sign_sql)
        google_login_sql = (ROOT / "migrations/add_google_login_credentials.sql").read_text()
        self.assertIn("brevo", google_login_sql)
        self.assertIn("d4sign", google_login_sql)


class OpenAIDirectRoutingTest(unittest.TestCase):
    def test_strips_openrouter_prefix_for_openai_api(self):
        self.assertEqual(openrouter_service.openai_model_slug("openai/gpt-5-mini"), "gpt-5-mini")
        self.assertEqual(openrouter_service.openai_model_slug("gpt-image-2"), "gpt-image-2")
        self.assertTrue(openrouter_service.is_openai_family("openai/gpt-5.4"))
        self.assertTrue(openrouter_service.model_omits_sampling("openai/gpt-5.4"))
        self.assertTrue(openrouter_service.model_omits_sampling("openai/gpt-5-mini"))
        self.assertFalse(openrouter_service.model_omits_sampling("openai/gpt-4o-mini"))
        self.assertFalse(openrouter_service.is_openai_family("anthropic/claude-sonnet-4"))
        self.assertEqual(
            openrouter_service.message_text({"content": [{"type": "text", "text": '{"ok": true}'}]}),
            '{"ok": true}',
        )

    def test_direct_openai_needs_key_and_gpt_family(self):
        with patch.object(openrouter_service, "resolve_openai_api_key", return_value=""):
            self.assertFalse(openrouter_service.uses_direct_openai("openai/gpt-5-mini"))
        with patch.object(openrouter_service, "resolve_openai_api_key", return_value="sk-test"):
            self.assertTrue(openrouter_service.uses_direct_openai("openai/gpt-5-mini"))
            self.assertFalse(openrouter_service.uses_direct_openai("anthropic/claude-sonnet-4"))

    def test_chat_hits_openai_when_key_is_configured(self):
        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                    "model": "gpt-5-mini",
                    "usage": {"total_tokens": 4},
                }

        with patch.object(openrouter_service, "resolve_openai_api_key", return_value="sk-test"), patch(
            "aicentralv2.services.openrouter_service.requests.post", return_value=_Resp()
        ) as post:
            result = openrouter_service.chat_completion(
                [{"role": "user", "content": "oi"}],
                model="openai/gpt-5-mini",
            )
        self.assertEqual(result["message"]["content"], "ok")
        self.assertEqual(post.call_args.args[0], openrouter_service.OPENAI_CHAT_URL)
        self.assertEqual(post.call_args.kwargs["json"]["model"], "gpt-5-mini")
        self.assertNotIn("top_k", post.call_args.kwargs["json"])
        self.assertNotIn("max_tokens", post.call_args.kwargs["json"])
        self.assertNotIn("temperature", post.call_args.kwargs["json"])
        self.assertIn("max_completion_tokens", post.call_args.kwargs["json"])
        self.assertEqual(post.call_args.kwargs["json"].get("reasoning_effort"), "low")

    def test_chat_provider_openrouter_ignora_chave_openai(self):
        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                    "model": "openai/gpt-4o-mini",
                    "usage": {},
                }

        with patch.object(openrouter_service, "resolve_openai_api_key", return_value="sk-test"), patch.object(
            openrouter_service, "resolve_api_key", return_value="or-test"
        ), patch("aicentralv2.services.openrouter_service.requests.post", return_value=_Resp()) as post:
            result = openrouter_service.chat_completion(
                [{"role": "user", "content": "oi"}],
                model="openai/gpt-4o-mini",
                provider="openrouter",
            )
        self.assertEqual(result["message"]["content"], "ok")
        self.assertEqual(post.call_args.args[0], openrouter_service.OPENROUTER_URL)

    def test_image_refs_go_to_openai_edits(self):
        import base64

        class _Resp:
            status_code = 200
            headers = {"content-type": "image/jpeg"}
            content = b"\xff\xd8\xffjpg-bytes"

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "data": [{"b64_json": base64.b64encode(b"png").decode("ascii")}],
                    "model": "gpt-image-2",
                    "usage": {},
                }

        with patch.object(openrouter_service, "resolve_openai_api_key", return_value="sk-test"), patch(
            "aicentralv2.creative_modeling_storage._validated_public_asset_url",
            side_effect=lambda value: value,
        ), patch(
            "aicentralv2.services.openrouter_service.requests.get", return_value=_Resp()
        ), patch(
            "aicentralv2.services.openrouter_service.requests.post", return_value=_Resp()
        ) as post:
            result = openrouter_service.generate_image(
                "fachada",
                model="openai/gpt-image-2",
                input_references=["https://images.adsttc.com/confins.jpg"],
            )
        self.assertTrue(result["b64_json"])
        self.assertEqual(post.call_args.args[0], openrouter_service.OPENAI_IMAGE_EDIT_URL)
        self.assertEqual(post.call_args.kwargs["data"]["model"], "gpt-image-2")
        self.assertEqual(post.call_args.kwargs["files"][0][0], "image[]")

    def test_image_falha_dupla_permanece_controlada_e_acionavel(self):
        with patch.object(openrouter_service, "uses_direct_openai", return_value=True), patch.object(
            openrouter_service, "_openai_generate_image",
            side_effect=openrouter_service.OpenRouterError("OpenAI indisponível"),
        ), patch.object(
            openrouter_service, "_openrouter_generate_image",
            side_effect=openrouter_service.OpenRouterError("saldo OpenRouter insuficiente"),
        ):
            with self.assertRaisesRegex(
                openrouter_service.OpenRouterError,
                "dois provedores.*saldo OpenRouter insuficiente",
            ):
                openrouter_service.generate_image("fachada", model="openai/gpt-image-2")

    def test_referencia_webp_mantem_mime_e_extensao_no_multipart(self):
        raw, mime, name = openrouter_service._reference_bytes(
            "data:image/webp;base64,d2VicA==", 0
        )

        self.assertEqual(raw, b"webp")
        self.assertEqual(mime, "image/webp")
        self.assertEqual(name, "ref0.webp")

    def test_referencia_global_vira_url_publica_apenas_no_openrouter(self):
        app = Flask(__name__)
        app.config["STUDIO_URL"] = "https://studio.centralcomm.media"
        with app.app_context():
            payload = openrouter_service._openrouter_reference_payload({
                "model": "openai/gpt-image-2",
                "input_references": [{
                    "type": "image_url",
                    "image_url": {"url": "/static/images/cadu/studio/references/feed/feed-mask-07.webp"},
                }],
            })

        self.assertEqual(
            payload["input_references"][0]["image_url"]["url"],
            "https://studio.centralcomm.media/static/images/cadu/studio/references/feed/feed-mask-07.webp",
        )

    def test_openai_le_referencia_global_diretamente_do_disco(self):
        app = Flask(
            __name__, static_folder=str(ROOT / "aicentralv2" / "static")
        )
        with app.app_context():
            raw, mime, name = openrouter_service._reference_bytes(
                "/static/images/cadu/studio/references/feed/feed-mask-07.webp", 0
            )

        self.assertGreater(len(raw), 1000)
        self.assertEqual(mime, "image/webp")
        self.assertEqual(name, "ref0.webp")

    def test_referencia_invalida_nao_e_descartada_silenciosamente(self):
        with self.assertRaisesRegex(ValueError, "referências de imagem é inválida"):
            openrouter_service.generate_image(
                "fachada", model="openai/gpt-image-2",
                input_references=["blob:referencia-local"],
            )


if __name__ == "__main__":
    unittest.main()
