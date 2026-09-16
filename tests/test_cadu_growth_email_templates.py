import unittest
from unittest.mock import patch

from flask import Flask

from aicentralv2.brevo_test_routes import bp
from aicentralv2.services.cadu_growth_email_templates import (
    BREVO_GROWTH_TEST_RECIPIENT,
    GROWTH_EMAIL_MODELS,
    render_growth_email,
    run_growth_email_test_suite,
)


class CaduGrowthEmailTemplateTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__,
            template_folder="../aicentralv2/templates",
        )
        self.app.secret_key = "growth-email-test"
        self.app.config.update(CADU_URL="https://cadu.centralcomm.media")
        self.app.register_blueprint(bp)

    def test_todos_os_modelos_renderizam_com_cta_e_texto(self):
        with self.app.app_context():
            for key in GROWTH_EMAIL_MODELS:
                html = render_growth_email(key)
                self.assertIn("CentralComm", html)
                self.assertIn("https://cadu.centralcomm.media", html)
                self.assertIn(f"{GROWTH_EMAIL_MODELS[key]['product']}-growth-v2.png", html)
                self.assertIn('class="email-illustration"', html)
                self.assertIn("<strong>", html)
                self.assertNotIn("**", html)
                self.assertIn('name="color-scheme" content="light only"', html)
                self.assertIn("@media only screen and (max-width:620px)", html)
                self.assertGreater(len(html), 900)

    def test_dry_run_executes_all_models_sem_brevo(self):
        with self.app.app_context(), patch("aicentralv2.services.cadu_growth_email_templates.get_brevo_product_service") as service:
            result = run_growth_email_test_suite(dry_run=True)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["results"]), len(GROWTH_EMAIL_MODELS))
        self.assertEqual(result["recipient"], BREVO_GROWTH_TEST_RECIPIENT)
        service.assert_not_called()

    def test_dry_run_executa_apenas_modelos_selecionados(self):
        with self.app.app_context():
            result = run_growth_email_test_suite(dry_run=True, model_keys=["places", "audiencias"])
        self.assertTrue(result["success"])
        self.assertEqual(result["selected_model_keys"], ["places", "audiencias"])
        self.assertEqual([item["model_key"] for item in result["results"]], ["places", "audiencias"])

    def test_suite_rejeita_selecao_vazia(self):
        with self.app.app_context():
            with self.assertRaisesRegex(ValueError, "Selecione"):
                run_growth_email_test_suite(dry_run=True, model_keys=[])

    def test_envio_isola_falha_de_um_modelo(self):
        def send(_app, cfg):
            if cfg["model_key"] == "places":
                raise RuntimeError("Brevo indisponível")
            return {"success": True, "messageId": f"test-{cfg['model_key']}"}

        with self.app.app_context(), patch(
            "aicentralv2.services.cadu_growth_email_templates._send_growth_test", side_effect=send
        ):
            result = run_growth_email_test_suite(dry_run=False)
        self.assertFalse(result["success"])
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["sent"], len(GROWTH_EMAIL_MODELS) - 1)

    def test_endpoint_exige_admin_e_aciona_suite(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch("aicentralv2.brevo_test_routes.run_growth_email_test_suite", return_value={"success": True, "dry_run": True, "sent": 0, "failed": 0, "results": []}) as suite, patch(
            "aicentralv2.brevo_test_routes.render_template", return_value="ok"
        ):
            response = client.post("/teste-brevo/cadu-growth", data={"mode": "preview", "models": "places"})
        self.assertEqual(response.status_code, 200)
        suite.assert_called_once_with(dry_run=True, model_keys=["places"])


if __name__ == "__main__":
    unittest.main()
