import unittest
from pathlib import Path

from jinja2 import Environment


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

    def test_real_logos_use_a_continuous_dark_surface(self):
        self.assertIn(".pp-company-avatar img", self.css)
        self.assertIn("background: #172033;", self.css)
        self.assertIn("background: transparent;", self.css)

    def test_avatar_only_exists_when_there_is_a_logo(self):
        macro = self.template.split(
            "{% macro pp_company_avatar", 1
        )[1].split("{% endmacro %}", 1)[0]
        self.assertIn("{% if logo_url %}", macro)
        self.assertNotIn("(nome or '?')", macro)
        self.assertIn("closest('.pp-company-avatar').hidden=true", macro)

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

    def test_pipeline_header_is_compact_and_metrics_filter_cards(self):
        self.assertIn("max-height: 4rem;", self.css)
        self.assertIn('data-card-filter="ativas"', self.template)
        self.assertIn('data-card-filter="paradas"', self.template)
        self.assertIn("cardFilterAtivo", self.template)
        self.assertIn("data-days=", self.template)

    def test_pipeline_uses_human_readable_money(self):
        start = self.template.index("{% macro money_br")
        end = self.template.index("{%- endmacro %}", start) + len("{%- endmacro %}")
        macro = self.template[start:end]
        template = Environment().from_string(macro + "{{ money_br(valor) }}")

        self.assertEqual(" ".join(template.render(valor=500_200).split()), "500 mil")
        self.assertEqual(" ".join(template.render(valor=1_200_000).split()), "1,2 mi")

    def test_detail_uses_vanilla_drawer_structure(self):
        self.assertIn('class="pp-detail-head"', self.template)
        self.assertIn('class="pp-detail-facts"', self.template)
        self.assertIn('class="pp-detail-footer"', self.template)
        self.assertIn(".pp-detail-head", self.css)
        self.assertIn(".pp-detail-footer", self.css)


if __name__ == "__main__":
    unittest.main()
