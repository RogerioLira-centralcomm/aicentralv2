import re
import unittest
from pathlib import Path

from jinja2 import Environment

from aicentralv2.campanhas_pi_list import group_pis_by_invoice_status


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "aicentralv2/templates/cadu_pi.html"
PARTIALS = ROOT / "aicentralv2/templates/cadu_pi"
CSS = ROOT / "aicentralv2/static/css/cadu-pi-list.css"
SHARED_CSS = ROOT / "aicentralv2/static/css/campanhas-ui.css"
JS = ROOT / "aicentralv2/static/js/cadu_pi_list.js"
ROUTES = ROOT / "aicentralv2/routes.py"


class CaduPiListUiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = TEMPLATE.read_text()
        cls.css = CSS.read_text()
        cls.shared_css = SHARED_CSS.read_text()
        cls.js = JS.read_text()

    def test_list_is_componentized_without_changing_modal_area(self):
        expected = {
            "_header_filters.html",
            "_table.html",
            "_pi_row.html",
            "_campaign_rows.html",
            "_agency_group.html",
            "_summary.html",
            "_operation_billing_cells.html",
        }
        self.assertTrue(expected.issubset({path.name for path in PARTIALS.glob("*.html")}))
        for name in expected - {"_pi_row.html"}:
            self.assertIn(f"cadu_pi/{name}", self.template)
        self.assertIn("import 'cadu_pi/_pi_row.html'", self.template)
        self.assertIn("modal_nf", self.template)
        self.assertIn("modal_spedy", self.template)
        self.assertIn("modal_andamento", self.template)

    def test_filter_contract_and_restore_markers_are_preserved(self):
        header = (PARTIALS / "_header_filters.html").read_text()
        for field in (
            "resp_comercial",
            "id_cliente",
            "mes_ref_comp",
            "ano_ref_comp",
            "busca",
            "tipo_entidade",
        ):
            self.assertIn(field, header)
        for marker in (
            "'_f'",
            "'_restored'",
            "cc_filtro_exec",
            "cc_filtro_mes",
            "cc_filtro_ano_",
            "cc_filtro_tipo_entidade_",
        ):
            self.assertIn(marker, self.js)

    def test_all_operational_variants_remain_in_template(self):
        for status in ("'1'", "'2'", "'3'", "'4'", "'6'"):
            self.assertIn(status, self.template)
        for origin in ("faturamento", "nf_emitida", "operacao"):
            self.assertIn(origin, self.template + self.js)
        self.assertIn("visao_por_agencia", self.template)
        self.assertIn("agencias_grupo", self.template)
        self.assertIn("pi_footer_totais", (PARTIALS / "_summary.html").read_text())

    def test_expansion_keeps_deep_links_and_accessibility_state(self):
        campaign = (PARTIALS / "_campaign_rows.html").read_text()
        row = (PARTIALS / "_pi_row.html").read_text()
        for marker in ("camp-collapse-", "camp-content-"):
            self.assertIn(marker, campaign)
        self.assertIn("data-campaign-toggle", row)
        self.assertIn('aria-expanded="false"', row)
        self.assertIn("aria-controls=", row)
        self.assertIn("setAttribute('aria-expanded'", self.js)
        self.assertIn("id=\"pi-{{ pi.id_pi }}\"", self.template)

    def test_campaigns_use_natural_height_and_no_nested_vertical_scroll(self):
        campaign = (PARTIALS / "_campaign_rows.html").read_text()
        self.assertNotIn("pi-camp-scroll", campaign)
        self.assertRegex(
            self.css,
            r"\.pi-page \.pi-camp-scroll\s*\{[^}]*overflow:\s*visible;[^}]*max-height:\s*none;",
        )
        self.assertIn("overflow-y: visible", self.css)
        self.assertNotIn("pi-row-sticky-expanded", self.js)

    def test_operation_billing_view_groups_finance_documents_and_nf(self):
        table = (PARTIALS / "_table.html").read_text()
        billing = (PARTIALS / "_operation_billing_cells.html").read_text()
        campaign = (PARTIALS / "_campaign_rows.html").read_text()
        self.assertIn("pi-billing-head", table)
        self.assertIn("Cliente e relacionamento", table)
        self.assertIn("Financeiro", table)
        self.assertIn("Documentos", table)
        self.assertIn("pi-billing-finance", billing)
        self.assertIn("Valor líquido", billing)
        self.assertIn("Valor bruto", billing)
        self.assertIn("pi-billing-document-actions", billing)
        self.assertIn("fa-file-invoice", billing)
        self.assertIn("Sem NF", billing)
        self.assertIn("origem_lista == 'operacao' %}7", campaign)
        self.assertIn("pi-row--billing", self.template)
        self.assertIn("pi-list-table--billing", self.template)

    def test_internal_campaign_grid_matches_operational_tracking(self):
        for marker in (
            "camp-table--operational",
            "pi-inner-flight-cell",
            "pi-inner-unit-cost",
            "pi-inner-delivery",
            "pi-inner-investment",
        ):
            self.assertIn(marker, self.js)
        for label in ("Veiculação", "Custo unitário", "Entrega", "Investimento"):
            self.assertIn(label, self.js)
        self.assertIn(".pi-page .camp-table--operational", self.css)
        self.assertIn("border-left: 4px solid #5f8f89", self.css)

    def test_mobile_cards_and_reduced_motion_are_explicit(self):
        self.assertIn("@media (max-width: 720px)", self.css)
        self.assertIn("content: attr(data-label)", self.css)
        self.assertIn("assignMobileCellLabels", self.js)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)

    def test_invoice_queue_groups_statuses_with_count_and_subtotal(self):
        groups = group_pis_by_invoice_status([
            {"id_pi": 1, "nf_status": 3, "nf_valor": "R$ 300,00"},
            {"id_pi": 2, "nf_status": 1, "nf_valor": 100},
            {"id_pi": 3, "nf_status": 2, "nf_valor": "200,50"},
            {"id_pi": 4, "nf_status": 1, "nf_valor": 50},
            {"id_pi": 5, "nf_status": 99, "nf_valor": None},
        ])
        self.assertEqual(
            [group["key"] for group in groups],
            ["nf-emitida", "aguardando-pagamento", "pagamento-realizado", "sem-status"],
        )
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(groups[0]["subtotal"], 150.0)
        self.assertEqual(groups[1]["subtotal"], 200.5)
        self.assertEqual(groups[-1]["pis"][0]["id_pi"], 5)
        routes = ROUTES.read_text()
        self.assertIn("group_pis_by_invoice_status", routes)
        self.assertIn("grupos_status_nf=grupos_status_nf", routes)

    def test_invoice_view_has_collapsible_groups_and_wider_client_column(self):
        Environment().parse(self.template)
        table = (PARTIALS / "_table.html").read_text()
        campaign = (PARTIALS / "_campaign_rows.html").read_text()
        self.assertIn("grupos_status_nf", self.template)
        self.assertIn("data-nf-group-toggle", self.template)
        self.assertIn('aria-expanded="true"', self.template)
        self.assertIn("data-nf-group-item", self.template)
        self.assertIn("data-nf-group-item", campaign)
        self.assertIn("pi-list-table--fiscal", self.template)
        self.assertIn("pi-col-client", self.template)
        self.assertIn("Cliente", table)
        self.assertIn(".pi-list-table--fiscal .pi-col-client { width: 24%; }", self.css)
        self.assertIn("toggleInvoiceGroup", self.js)

    def test_invoice_actions_are_neutral_and_status_change_refreshes_groups(self):
        fiscal_start = self.template.index('<div class="pi-nf-cell">')
        fiscal_end = self.template.index("{% else %}", fiscal_start)
        fiscal_markup = self.template[fiscal_start:fiscal_end]
        self.assertIn("pi-nf-state", fiscal_markup)
        self.assertIn("pi-nf-action", fiscal_markup)
        self.assertIn("Registrar pagamento", fiscal_markup)
        for color_class in ("bg-yellow-100", "bg-blue-100", "bg-green-100"):
            self.assertNotIn(color_class, fiscal_markup)
        self.assertIn("document.querySelector('.pi-page--fiscal')", self.template)
        self.assertIn("window.location.reload()", self.template)

    def test_invoice_header_is_full_bleed_and_measures_sticky_offset(self):
        header = (PARTIALS / "_header_filters.html").read_text()
        self.assertIn("Notas fiscais dos PIs", header)
        self.assertIn("pi-list-header--fiscal", header)
        self.assertIn(".pi-page--fiscal", self.css)
        self.assertIn("top: var(--erp-topbar-h", self.css)
        self.assertIn("--pi-list-header-height", self.css)
        self.assertIn("updateListStickyOffsets", self.js)

    def test_configuration_row_keeps_status_and_flight_compact(self):
        self.assertIn("pi-row--config", self.template)
        self.assertIn("pi-config-date-range", self.template)
        self.assertIn("pi-config-duration", self.template)
        self.assertIn("<time datetime=", self.template)
        self.assertRegex(
            self.css,
            r"\.pi-page \.pi-list-table tbody \.pi-row--config > td\s*\{"
            r"[^}]*padding-top:\s*0\.55rem;"
            r"[^}]*padding-bottom:\s*0\.55rem;"
            r"[^}]*vertical-align:\s*middle;",
        )
        self.assertRegex(
            self.css,
            r"\.pi-config-title\s*\{[^}]*text-overflow:\s*ellipsis;"
            r"[^}]*white-space:\s*nowrap;",
        )
        self.assertRegex(
            self.css,
            r"\.pi-config-status\s*\{[^}]*white-space:\s*nowrap;",
        )
        self.assertIn(".pi-config-head th:nth-child(4) { width: 16%; }", self.css)
        self.assertIn(".pi-config-head th:nth-child(7) { width: 10%; }", self.css)

    def test_closed_sidebar_is_removed_from_layout_and_viewport(self):
        self.assertIn(
            'id="piSidebarOverlay" onclick="fecharSidebarPi()" hidden aria-hidden="true"',
            self.template,
        )
        self.assertIn(
            'id="piSidebarPanel" hidden aria-hidden="true"',
            self.template,
        )
        self.assertIn("transform: translateX(calc(100% + 2rem))", self.shared_css)
        self.assertIn(".sidebar-panel[hidden]", self.shared_css)
        self.assertNotIn("right: -480px", self.shared_css)
        self.assertIn("panel.hidden = false", self.js)
        self.assertIn("panel.hidden = true", self.js)
        self.assertIn("document.body.classList.add('sidebar-open')", self.js)

    def test_new_list_css_has_no_text_smaller_than_twelve_pixels(self):
        small_px = re.findall(r"font-size:\s*(?:[0-9]|1[01])px", self.css)
        small_rem = re.findall(r"font-size:\s*0\.(?:[0-6]\d*|7[0-4]\d*)rem", self.css)
        self.assertEqual([], small_px)
        self.assertEqual([], small_rem)

    def test_dedicated_script_owns_filters_and_lazy_expansion(self):
        for function_name in (
            "aplicarFiltros",
            "debounceAplicarFiltros",
            "buscarClientesFiltro",
            "filtrarMesesPorAno",
            "toggleCampanhas",
            "toggleTodasCampanhas",
            "toggleAgenciaPis",
        ):
            self.assertIn(function_name, self.js)
        self.assertNotIn("function aplicarFiltros", self.template)
        self.assertNotIn("function buscarClientesFiltro", self.template)
        self.assertIn("/api/cadu-pi/", self.js)
        self.assertIn("/api/cadu_pi/", self.js)

    def test_new_partials_do_not_introduce_daisyui_components(self):
        forbidden = re.compile(
            r'(?<!cx-)\b(?:modal-box|modal-action|btn-primary|btn-ghost|'
            r'badge-primary|alert-info|dropdown-content|menu-title)\b'
        )
        for path in PARTIALS.glob("*.html"):
            self.assertIsNone(forbidden.search(path.read_text()), path.name)


if __name__ == "__main__":
    unittest.main()
