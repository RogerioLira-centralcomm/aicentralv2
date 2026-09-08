import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "aicentralv2/templates/crm_pipeline.html"
CSS = ROOT / "aicentralv2/static/css/cotacao_pipeline.css"
DB = ROOT / "aicentralv2/db.py"


class CrmPipelineLogosContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = TEMPLATE.read_text()
        cls.css = CSS.read_text()
        cls.db = DB.read_text()

    def test_pipeline_receives_client_and_agency_logos(self):
        self.assertIn("web_cli.logo_url AS cliente_logo_url", self.db)
        self.assertIn("web_agn.logo_url AS agencia_logo_url", self.db)
        self.assertIn("pp_company_avatar(cotacao.cliente_nome", self.template)
        self.assertIn("pp_company_avatar(cotacao.agencia_nome", self.template)

    def test_white_logos_have_contrasting_surface(self):
        self.assertIn(".pp-company-avatar", self.css)
        self.assertIn(
            "linear-gradient(135deg, #172033 0 50%, #f8fafc 50% 100%)",
            self.css,
        )

    def test_pipeline_exposes_quote_type(self):
        self.assertIn("cot.tipo_comercial", self.db)
        self.assertIn("pp_quote_type(cotacao.tipo_comercial)", self.template)


if __name__ == "__main__":
    unittest.main()
