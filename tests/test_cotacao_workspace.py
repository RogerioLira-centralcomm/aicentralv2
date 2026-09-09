import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CotacaoWorkspaceContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes = (ROOT / "aicentralv2/cotacoes_routes.py").read_text()
        cls.crm_routes = (ROOT / "aicentralv2/crm_v3_routes.py").read_text()
        cls.app_routes = (ROOT / "aicentralv2/routes.py").read_text()
        cls.workspace = (
            ROOT / "aicentralv2/templates/cadu_cotacoes_workspace.html"
        ).read_text()
        cls.workspace_css = (
            ROOT / "aicentralv2/static/css/cotacao_workspace.css"
        ).read_text()
        cls.workspace_js = (
            ROOT / "aicentralv2/static/js/cotacao_workspace.js"
        ).read_text()
        cls.form = (
            ROOT / "aicentralv2/templates/cadu_cotacoes_form.html"
        ).read_text()
        cls.db = (ROOT / "aicentralv2/db.py").read_text()
        cls.migration = (
            ROOT / "migrations/add_cotacao_itens_especificos.sql"
        ).read_text()
        cls.deploy = (ROOT / "deploy.sh").read_text()
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

    def test_workspace_uses_data_left_and_control_sidebar_right(self):
        self.assertIn("cot-workspace-layout", self.workspace)
        self.assertIn("cot-workspace-sidebar", self.workspace)
        self.assertIn("cot-workspace-table", self.workspace)
        self.assertIn("Controle da cotação", self.workspace)
        self.assertIn("Editar dados", self.workspace)
        self.assertIn("Estrutura por produto", self.workspace)
        self.assertIn("grid-template-columns: minmax(0, 1fr) 20rem", self.workspace_css)
        self.assertIn("grid-column: 2", self.workspace_css)
        self.assertIn("@media (max-width: 900px)", self.workspace_css)

    def test_non_media_editing_stays_inside_the_workspace_family(self):
        self.assertIn("request.method == 'GET' and tipo_comercial != 'midia'", self.routes)
        self.assertIn("editar=1", self.routes)
        self.assertIn('id="cot-workspace-editor"', self.workspace)
        self.assertIn('form="cot-workspace-editor"', self.workspace)
        self.assertIn('name="apresentacao_dados"', self.workspace)
        self.assertIn('name="condicoes_comerciais"', self.workspace)
        self.assertIn("'apresentacao_dados': request.form.get", self.routes)

    def test_list_pipeline_crm_and_api_use_central_open_route(self):
        self.assertIn("/cotacoes/{{ cotacao.id }}/abrir", self.list_template)
        self.assertIn("`/cotacoes/${c.id}/abrir`", self.pipeline)
        self.assertIn('href="/cotacoes/${c.id}/abrir"', self.crm_js)
        self.assertIn('url_for("cotacoes.cotacao_abrir"', self.crm_routes)

    def test_creation_selector_explains_four_commercial_types(self):
        self.assertIn('class="cot-type-selector"', self.form)
        self.assertIn('name="tipo_comercial" value="midia"', self.form)
        self.assertIn('name="tipo_comercial" value="parceiros"', self.form)
        self.assertIn('name="tipo_comercial" value="formatos_interativos"', self.form)
        self.assertIn('name="tipo_comercial" value="dados"', self.form)
        self.assertIn("Definido na criação", self.form)

    def test_typed_workspace_has_editable_items_and_total(self):
        self.assertIn("data-typed-items", self.workspace)
        self.assertIn("data-item-dialog", self.workspace)
        self.assertIn("data-items-total", self.workspace)
        self.assertIn("api_itens_especificos_cotacao", self.routes)
        self.assertIn("api_reordenar_itens_especificos", self.routes)
        self.assertIn("valor_total_proposta = COALESCE", self.db)
        self.assertIn("O tipo da cotação não pode ser alterado", self.db)
        self.assertIn("data-action=\"delete\"", self.workspace_js)
        self.assertNotIn("window.confirm", self.workspace_js)
        self.assertIn("credentials: 'same-origin'", self.workspace_js)
        self.assertIn("const previousItems = items.slice()", self.workspace_js)
        self.assertIn("aria-busy", self.workspace_js)

    def test_specific_items_schema_is_deployed(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS cadu_cotacao_itens_especificos", self.migration)
        self.assertIn("metadata JSONB", self.migration)
        self.assertIn("ON DELETE CASCADE", self.migration)
        self.assertIn("run_add_cotacao_itens_especificos.py", self.deploy)

    def test_media_apis_remain_separate_but_commercial_approval_is_shared(self):
        self.assertIn(
            "Linhas de mídia não podem ser usadas neste tipo de cotação",
            self.app_routes,
        )
        self.assertIn(
            "Audiências pertencem apenas a cotações de Mídia",
            self.app_routes,
        )
        self.assertIn("and tipo_comercial == 'midia'", self.app_routes)
        self.assertNotIn(
            "A aprovação deste tipo exige o fluxo de PI específico",
            self.app_routes,
        )

    def test_creation_redirects_directly_to_selected_workspace(self):
        self.assertIn(
            "destino, _ = destino_tipo_comercial(kwargs['tipo_comercial'])",
            self.routes,
        )


if __name__ == "__main__":
    unittest.main()
