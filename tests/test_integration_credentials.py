import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from flask import Blueprint, Flask

from aicentralv2.integration_settings_routes import (
    register_integration_settings_routes,
)
from aicentralv2.services import integration_credentials


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
        self.assertIn('data-integration-form="openrouter"', template)
        self.assertIn("run_add_openrouter_integration_credential.py", deploy)
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


if __name__ == "__main__":
    unittest.main()
