import unittest
from unittest.mock import patch

from flask import Flask

from aicentralv2.brevo_test_routes import bp
from aicentralv2.services.cadu_growth_email_templates import build_growth_email as build_growth_email_for_test
from aicentralv2.services.cadu_growth_email_templates import (
    BREVO_GROWTH_TEST_RECIPIENT,
    GROWTH_EMAIL_MODELS,
    render_growth_email,
    run_growth_email_test_suite,
)


@patch.dict("os.environ", {"CADU_SKILLS_ENABLED": "true"})  # inclui o modelo de Skills
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
                # CTA aponta para o domínio do próprio produto (product_url), não ao CADU_URL legado.
                from aicentralv2.product_domains import product_url
                self.assertIn(product_url(GROWTH_EMAIL_MODELS[key]['product']).rstrip('/'), html)
                self.assertIn(f"{GROWTH_EMAIL_MODELS[key]['product']}-band-v2.png", html)
                self.assertIn('class="brand-band"', html)
                self.assertIn("<strong>", html)
                self.assertNotIn("**", html)
                self.assertIn('name="color-scheme" content="light only"', html)
                self.assertIn("@media only screen and (max-width:620px)", html)
                self.assertIn("@media only screen and (max-width:380px)", html)
                self.assertIn('class="action-row"', html)
                self.assertIn('class="footer"', html)
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

    def test_primeiro_email_oficial_cobre_todas_as_familias(self):
        official_models = [
            "conversa-para-plano", "audiencias", "formatos",
            "connect-reports", "skills-conhecimento-reutilizavel",
        ]
        with self.app.app_context():
            result = run_growth_email_test_suite(dry_run=True, model_keys=official_models)
        self.assertTrue(result["success"])
        self.assertEqual(
            {GROWTH_EMAIL_MODELS[key]["product"] for key in official_models},
            {"workspace", "planner", "studio", "connect", "skills"},
        )

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
            session["user_type"] = "admin"; session["is_centralcomm"] = True
        with patch("aicentralv2.brevo_test_routes.run_growth_email_test_suite", return_value={"success": True, "dry_run": True, "sent": 0, "failed": 0, "results": []}) as suite, patch(
            "aicentralv2.brevo_test_routes.render_template", return_value="ok"
        ):
            response = client.post("/teste-brevo/cadu-growth", data={"mode": "preview", "models": "places"})
        self.assertEqual(response.status_code, 200)
        suite.assert_called_once_with(dry_run=True, model_keys=["places"])


if __name__ == "__main__":
    unittest.main()


class CaduGrowthRecurringModelsTests(unittest.TestCase):
    NEW = ("dicas-de-uso", "dicas-de-prompts", "plugins-agentes", "planner-radar", "studio-criar")

    def test_novos_modelos_tem_ilustracao_existente_e_cores_da_familia(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "aicentralv2" / "static" / "emails" / "growth"
        families = {"dicas-de-uso": "workspace", "dicas-de-prompts": "workspace", "plugins-agentes": "workspace",
                    "planner-radar": "planner", "studio-criar": "studio"}
        for key in self.NEW:
            model = GROWTH_EMAIL_MODELS[key]
            self.assertEqual(model["product"], families[key])
            self.assertTrue((root / model["illustration"]).exists(), key)
            self.assertLessEqual(len(model["default_body"].split()), 300, key)
            self.assertNotIn("Smart", model["title"] + model["subject"] + model["default_body"])

    def test_links_do_portal_apontam_para_artigos_publicos_existentes(self):
        from aicentralv2.cadu_workspace.routes import PUBLIC_ARTICLES
        for key in self.NEW:
            model = GROWTH_EMAIL_MODELS[key]
            for path in (model["cta_path"], model.get("secondary_path", "")):
                if path.startswith("/workspace/conteudos/"):
                    self.assertIn(path.rsplit("/", 1)[-1], PUBLIC_ARTICLES, path)

    def test_template_renderiza_ilustracao_botao_e_link_secundario(self):
        app = Flask(__name__, template_folder="../aicentralv2/templates")
        with app.test_request_context("/"):
            html = render_growth_email("planner-radar")
        self.assertIn("planner-radar.png", html)
        self.assertIn('class="button"', html)
        self.assertIn("Ler o guia do Radar", html)
        self.assertIn("#087D4D", html)

    def test_artigos_do_portal_sempre_usam_o_dominio_do_workspace(self):
        from aicentralv2.product_domains import product_url
        app = Flask(__name__, template_folder="../aicentralv2/templates")
        with app.test_request_context("/"):
            for key in ("planner-radar", "studio-criar"):
                url = build_growth_email_for_test(key)["params"]["SECONDARY_URL"]
                self.assertTrue(url.startswith(product_url("workspace", "/workspace/conteudos/")), url)
