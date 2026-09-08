import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "aicentralv2/templates/crm_v3.html"
CSS = ROOT / "aicentralv2/static/css/crm_v3.css"
JS = ROOT / "aicentralv2/static/js/crm_v3.js"
DRAWER_JS = ROOT / "aicentralv2/static/js/crm_v3_drawers.js"
DRAWER = ROOT / "aicentralv2/templates/crm_v3/_drawer_cotacao.html"
CLIENT_DRAWER = ROOT / "aicentralv2/templates/crm_v3/_drawer_cliente.html"
MODALS = ROOT / "aicentralv2/templates/crm_v3/_modals.html"
ENTERPRISE_CSS = ROOT / "aicentralv2/static/css/tailwind/enterprise-system.css"
COTACOES_FORM = ROOT / "aicentralv2/templates/cadu_cotacoes_form.html"
COTACAO_TIPOS = ROOT / "aicentralv2/cotacao_tipos.py"
DB = ROOT / "aicentralv2/db.py"
DEPLOY = ROOT / "deploy.sh"


class CrmV3MainUiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = TEMPLATE.read_text()
        cls.css = CSS.read_text()
        cls.js = JS.read_text()
        cls.drawer_js = DRAWER_JS.read_text()
        cls.drawer = DRAWER.read_text()
        cls.client_drawer = CLIENT_DRAWER.read_text()
        cls.modals = MODALS.read_text()
        cls.enterprise_css = ENTERPRISE_CSS.read_text()
        cls.cotacoes_form = COTACOES_FORM.read_text()
        cls.cotacao_tipos = COTACAO_TIPOS.read_text()
        cls.db = DB.read_text()
        cls.deploy = DEPLOY.read_text()

    def test_workspace_is_not_artificially_scaled(self):
        self.assertNotIn("zoom: 0.8", self.css)
        self.assertNotIn("width: 125%", self.css)

    def test_metrics_remain_one_row_until_mobile(self):
        desktop = self.css.split("@media (max-width: 767px)", 1)[0]
        self.assertIn("grid-template-columns: repeat(6, minmax(0, 1fr))", desktop)
        self.assertNotIn("repeat(3, minmax(0, 1fr))", desktop)

    def test_context_sidebar_becomes_an_explicit_drawer(self):
        for element_id in (
            "crm-v3-context-open",
            "crm-v3-context-close",
            "crm-v3-context-overlay",
        ):
            self.assertEqual(1, self.template.count(f'id="{element_id}"'))
        self.assertIn("initContextSidebar", self.js)
        self.assertIn("is-context-open", self.js)
        self.assertIn("aria-expanded", self.js)

    def test_operational_lists_own_their_vertical_scroll(self):
        self.assertRegex(
            self.css,
            r"\.crm-v3-section-atividades \.crm-v3-ativ-list,[\s\S]*?"
            r"overflow-y:\s*auto",
        )
        self.assertIn("scrollbar-gutter: stable", self.css)

    def test_activity_composer_prioritizes_user_input_and_date(self):
        self.assertIn("crm-v3-ativ-composer-main", self.template)
        self.assertIn("crm-v3-ativ-composer-controls", self.template)
        self.assertIn('data-activity-date-offset="0"', self.template)
        self.assertIn('data-activity-date-offset="1"', self.template)
        self.assertIn("function syncDatePresets()", self.js)
        self.assertIn("e.key === 'Enter' && e.shiftKey", self.js)
        self.assertIn(".crm-v3-ativ-composer-input", self.css)
        self.assertIn("font-size: 15px", self.css)

    def test_only_contextual_suggestion_remains_in_activity_column(self):
        render = self.js.split("function renderAtividades()", 1)[1].split(
            "// renderSidebarAtividades", 1
        )[0]
        self.assertNotIn("renderQuickAtividadesHTML", render)
        self.assertNotIn("bindQuickAtividades", render)
        self.assertIn("recomendação contextual", render)
        self.assertIn("crm-v3-next-action-details", self.js)
        self.assertIn(".crm-v3-next-action-details > summary", self.css)

    def test_tablet_keeps_client_navigation(self):
        tablet = re.search(
            r"@media \(max-width: 992px\) \{(?P<body>[\s\S]*?)\n\}",
            self.css,
        )
        self.assertIsNotNone(tablet)
        self.assertIn("grid-template-columns: 220px minmax(0, 1fr)", tablet.group("body"))
        self.assertNotIn(".crm-v3-col-clientes", tablet.group("body"))

    def test_notebook_density_does_not_use_transform_or_zoom(self):
        notebook = re.search(
            r"@media \(min-width: 993px\) and \(max-width: 1440px\) \{"
            r"(?P<body>[\s\S]*?)\n\}",
            self.css,
        )
        self.assertIsNotNone(notebook)
        self.assertNotIn("zoom:", notebook.group("body"))
        self.assertNotIn("scale(", notebook.group("body"))

    def test_quote_cards_only_keep_operational_summary(self):
        opened = self.js.split("function cotacaoCardAberta", 1)[1].split(
            "function cotacaoLinhaHistorico", 1
        )[0]
        self.assertNotIn("cotacao-plataformas", opened)
        self.assertNotIn("cotacao-objetivo", opened)
        self.assertIn('type="button"', opened)
        self.assertIn("crm-v3-cotacao-compact-head", opened)
        self.assertIn("window.crmV3Drawer.openCotacao", self.js)

    def test_quote_drawer_is_unified_and_legacy_modal_is_removed(self):
        self.assertIn("cx-cotacao-editor-grid", self.drawer)
        self.assertIn("cx-cotacao-editor-main", self.drawer)
        self.assertIn("cx-cotacao-editor-side", self.drawer)
        for field in ("status", "valor_total", "objetivo", "plataformas"):
            self.assertIn(f'data-field="{field}"', self.drawer)
        self.assertIn("cx-cot-open-full", self.drawer)
        self.assertNotIn('id="crm-v3-modal-cotacao"', self.modals)
        self.assertNotIn("openCotacaoModal", self.js)

    def test_quote_drawer_is_progressive_and_agent_suggestions_are_reviewable(self):
        self.assertIn('class="cx-cot-type-track"', self.drawer)
        self.assertEqual(4, self.drawer.count('data-cot-type="'))
        self.assertIn('<details class="cx-cot-refine"', self.drawer)
        for field in (
            "client_user_id",
            "agencia_user_id",
            "id_parceiro",
            "parceiro_user_id",
            "budget_estimado",
            "apresentacao_dados",
            "frequencia_impacto",
            "premissas",
            "observacoes_gerais",
        ):
            self.assertIn(f'data-field="{field}"', self.drawer)
        self.assertIn("wireCotacaoAgent", self.drawer_js)
        self.assertIn("/ia/sugerir-cotacao", self.drawer_js)
        self.assertIn("Campos vazios foram preenchidos", self.drawer_js)
        self.assertIn("applyCotacaoSuggestion", self.drawer_js)
        self.assertIn(".cx-cot-type-track", self.enterprise_css)
        self.assertIn(".cx-cot-agent", self.enterprise_css)

    def test_quote_type_is_single_and_media_remains_the_legacy_flow(self):
        for slug in ("midia", "parceiros", "formatos_interativos", "dados"):
            self.assertIn(f'value="{slug}"', self.drawer)
            self.assertIn(f'value="{slug}"', self.cotacoes_form)
        self.assertIn('data-field="tipo_comercial"', self.drawer)
        self.assertIn("validar_status_tipo_comercial", self.db)
        self.assertIn("O PI automático atual é exclusivo", self.db)
        self.assertIn(
            "migrations/run_add_tipo_comercial_to_cotacoes.py",
            self.deploy,
        )
        self.assertIn("destino_tipo_comercial", self.cotacao_tipos)

    def test_quote_cards_show_type_and_company_identity(self):
        self.assertIn("cotacaoTipoHtml(c)", self.js)
        self.assertIn("cotacaoIdentidadeHtml(c)", self.js)
        self.assertIn("data-cotacao-logo", self.js)
        self.assertIn(".crm-v3-cotacao-entity-avatar", self.css)
        self.assertIn(".crm-v3-cotacao-entity-avatar img", self.css)
        self.assertIn("background: #fff;", self.css)
        self.assertIn("crm-v3-cotacao-company-row", self.js)
        self.assertIn("Data inicial da campanha", self.js)
        self.assertNotIn("Cliente vinculado:", self.js)

    def test_agency_clients_can_be_managed_inside_quote_drawer(self):
        for element_id in (
            "cx-cot-agency-clients",
            "cx-cot-agency-list",
            "cx-cot-agency-add",
        ):
            self.assertIn(f'id="{element_id}"', self.drawer)
        self.assertNotIn('id="cx-cot-unlink-dialog"', self.drawer)
        self.assertIn("wireAgencyClientManager", self.drawer_js)
        self.assertIn("changeAgencyClientLink", self.drawer_js)
        self.assertIn("changeAgencyClientLink(wrapper, selected, false)", self.drawer_js)
        self.assertIn("method: active ? 'POST' : 'DELETE'", self.drawer_js)
        self.assertIn(".cx-agency-client-row", self.enterprise_css)
        self.assertIn('data-cot-media-only hidden', self.drawer)

    def test_non_media_drawer_preserves_media_fields_and_legacy_data(self):
        self.assertIn('data-field="plataformas"', self.drawer)
        self.assertIn("payload.tipo_comercial === 'midia'", self.drawer_js)
        self.assertIn("delete payload.plataformas", self.drawer_js)
        self.assertIn("element.id === 'cx-cot-agency-clients'", self.drawer_js)

    def test_quote_budget_uses_brl_mask_and_canonical_payload(self):
        self.assertIn('id="cx-cot-budget"', self.drawer)
        self.assertIn('inputmode="decimal"', self.drawer)
        self.assertIn('id="cx-cot-budget-value"', self.drawer)
        self.assertIn("function parseBudgetBr", self.drawer_js)
        self.assertIn("style: 'currency'", self.drawer_js)
        self.assertIn("wireBudgetCotacao(wrapper)", self.drawer_js)

    def test_quote_duration_excludes_start_day(self):
        duration = self.drawer_js.split("function contarDias", 1)[1].split(
            "function wireBudgetCotacao", 1
        )[0]
        self.assertIn("Math.round((b - a) / 86400000)", duration)
        self.assertNotIn("/ 86400000) + 1", duration)
        self.assertIn("cursor.setDate(cursor.getDate() + 1)", duration)

    def test_crm_does_not_use_blocking_confirmations_or_alerts(self):
        scripts = self.js + "\n" + self.drawer_js
        self.assertIsNone(re.search(r"\b(?:window\.)?confirm\s*\(", scripts))
        self.assertIsNone(re.search(r"\b(?:window\.)?alert\s*\(", scripts))
        self.assertNotIn('id="crm-v3-modal-confirm-obj"', self.modals)
        self.assertNotIn('id="cx-cot-unlink-dialog"', self.drawer)
        self.assertNotIn('role="alert"', self.template + self.modals)
        self.assertNotIn("cx-alert", self.modals)

    def test_client_editor_is_a_single_responsive_drawer(self):
        self.assertIn("crm-v3-cliente-editor-grid", self.client_drawer)
        self.assertIn("crm-v3-cliente-editor-main", self.client_drawer)
        self.assertIn("crm-v3-cliente-editor-side", self.client_drawer)
        self.assertIn("size: 'xl'", self.drawer_js)
        self.assertNotIn('id="crm-v3-modal-cliente"', self.modals)
        self.assertNotIn("openClienteModal", self.js)

    def test_client_address_is_collapsible_and_summarized(self):
        self.assertIn('<details class="crm-v3-cliente-address', self.client_drawer)
        self.assertIn('id="cx-cliente-endereco-resumo"', self.client_drawer)
        self.assertIn("wireClienteAddressSummary", self.drawer_js)

    def test_client_agencies_have_search_and_explicit_empty_state(self):
        self.assertIn('id="cx-drawer-cliente-agencia-search"', self.client_drawer)
        self.assertIn('id="cx-drawer-cliente-agencias-count"', self.client_drawer)
        self.assertIn("wireAgenciaSearch", self.drawer_js)
        self.assertIn("Nenhuma agência vinculada", self.drawer_js)
        self.assertNotIn('data-drawer-action="add-agencia"', self.client_drawer)

    def test_client_editor_stacks_on_tablet_and_mobile(self):
        self.assertRegex(
            self.css,
            r"@media \(max-width: 900px\)[\s\S]*?"
            r"\.crm-v3-cliente-editor-grid\s*\{[\s\S]*?"
            r"grid-template-columns:\s*1fr",
        )
        self.assertRegex(
            self.css,
            r"@media \(max-width: 640px\)[\s\S]*?"
            r"\.crm-v3-cliente-form-grid\s*\{[\s\S]*?"
            r"grid-template-columns:\s*1fr",
        )

    def test_web_tab_renders_social_links_only_when_available(self):
        self.assertIn('id="crm-v3-web-social-section"', self.template)
        self.assertIn('id="crm-v3-web-social-links"', self.template)
        self.assertIn("webExtras.social_links", self.js)
        self.assertIn("socialSec.hidden = validSocialLinks.length === 0", self.js)
        self.assertIn(".crm-v3-web-social-link:focus-visible", self.css)


if __name__ == "__main__":
    unittest.main()
