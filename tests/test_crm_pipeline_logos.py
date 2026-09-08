import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "aicentralv2/templates/crm_pipeline.html"
CSS = ROOT / "aicentralv2/static/css/cotacao_pipeline.css"
LIST_TEMPLATE = ROOT / "aicentralv2/templates/cadu_cotacoes.html"
LIST_CSS = ROOT / "aicentralv2/static/css/cotacao_lista.css"
DB = ROOT / "aicentralv2/db.py"


class CrmPipelineLogosContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = TEMPLATE.read_text()
        cls.css = CSS.read_text()
        cls.list_template = LIST_TEMPLATE.read_text()
        cls.list_css = LIST_CSS.read_text()
        cls.db = DB.read_text()

    def test_pipeline_receives_client_and_agency_logos(self):
        self.assertIn("web_cli.logo_url AS cliente_logo_url", self.db)
        self.assertIn("web_agn.logo_url AS agencia_logo_url", self.db)
        self.assertIn("pp_company_avatar(cotacao.cliente_nome", self.template)
        self.assertIn("pp_company_avatar(cotacao.agencia_nome", self.template)

    def test_real_logos_use_a_continuous_white_surface(self):
        self.assertIn(".pp-company-avatar img", self.css)
        self.assertIn("background: #fff;", self.css)

    def test_quote_list_shows_agency_then_final_client(self):
        self.assertIn("agn.nome_fantasia as agencia_nome", self.db)
        self.assertIn("web_cli.logo_url as cliente_logo_url", self.db)
        self.assertIn("web_agn.logo_url as agencia_logo_url", self.db)
        self.assertIn("cotacao.agencia_nome", self.list_template)
        self.assertIn("cotacao.cliente_nome", self.list_template)
        self.assertIn("cot-lista-identidade-seta", self.list_template)
        self.assertIn(".cot-lista-logo img", self.list_css)

    def test_pipeline_exposes_quote_type(self):
        self.assertIn("cot.tipo_comercial", self.db)
        self.assertIn("pp_quote_type(cotacao.tipo_comercial)", self.template)


if __name__ == "__main__":
    unittest.main()
