import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CotacaoWorkspaceContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes = (ROOT / "aicentralv2/cotacoes_routes.py").read_text()
        cls.crm_routes = (ROOT / "aicentralv2/crm_v3_routes.py").read_text()
        cls.workspace = (
            ROOT / "aicentralv2/templates/cadu_cotacoes_workspace.html"
        ).read_text()
        cls.workspace_css = (
            ROOT / "aicentralv2/static/css/cotacao_workspace.css"
        ).read_text()
        cls.list_template = (
            ROOT / "aicentralv2/templates/cadu_cotacoes.html"
        ).read_text()
        cls.pipeline = (
            ROOT / "aicentralv2/templates/crm_pipeline.html"
        ).read_text()
        cls.crm_js = (ROOT / "aicentralv2/static/js/crm.js").read_text()

    def test_workspace_is_exclusive_to_non_media_types(self):
        self.assertIn(
            "@bp.route('/cotacoes/<int:cotacao_id>/workspace')",
            self.routes,
        )
        self.assertIn("if tipo == 'midia':", self.routes)
        self.assertIn("cotacoes.cotacao_detalhes", self.routes)
        self.assertIn("cotacoes.cotacao_workspace", self.routes)

    def test_workspace_uses_full_width_sidebar_and_tables(self):
        self.assertIn("cot-workspace-layout", self.workspace)
        self.assertIn("cot-workspace-sidebar", self.workspace)
        self.assertIn("cot-workspace-table", self.workspace)
        self.assertIn("Editar cabeçalho", self.workspace)
        self.assertIn("Sem linhas, audiências ou cálculo de Mídia", self.workspace)
        self.assertIn("grid-template-columns: 17rem minmax(0, 1fr)", self.workspace_css)
        self.assertIn("@media (max-width: 900px)", self.workspace_css)

    def test_list_pipeline_crm_and_api_use_central_open_route(self):
        self.assertIn("/cotacoes/{{ cotacao.id }}/abrir", self.list_template)
        self.assertIn("`/cotacoes/${c.id}/abrir`", self.pipeline)
        self.assertIn('href="/cotacoes/${c.id}/abrir"', self.crm_js)
        self.assertIn('url_for("cotacoes.cotacao_abrir"', self.crm_routes)


if __name__ == "__main__":
    unittest.main()
