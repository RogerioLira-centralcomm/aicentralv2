import re
import unittest
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

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
            "_pi_card.html",
            "_campaign_rows.html",
            "_agency_group.html",
            "_summary.html",
            "_commercial_summary.html",
            "_billing_summary.html",
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
        row = (PARTIALS / "_pi_row.html").read_text()
        self.assertIn("data-pi-group-toggle", row)
        self.assertIn('aria-expanded="true"', row)
        self.assertIn("aria-controls=", row)
        self.assertIn("togglePiGroup", self.js)
        self.assertIn("data-campaign-parent", self.js)
        self.assertIn("setAttribute('aria-expanded'", self.js)
        self.assertIn("id=\"pi-{{ pi.id_pi }}\"", self.template)
        self.assertIn("data-pi-id", self.template)

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
        self.assertIn("PI / entidades", table)
        self.assertIn("Resultado mídia", table)
        self.assertIn("Resultado comercial", table)
        self.assertIn("Status financeiro", table)
        self.assertNotIn("<th>Campanhas</th>", table.split("pi-billing-head", 1)[1].split("</tr>", 1)[0])
        self.assertIn("Documentos", table)
        self.assertIn("pi-billing-finance", billing)
        self.assertIn("Valor líquido", billing)
        self.assertIn("Valor bruto", billing)
        self.assertIn("pi-billing-document-actions", billing)
        self.assertIn("fa-file-invoice", billing)
        self.assertIn("Sem NF", billing)
        self.assertIn("Abrir workspace", billing)
        self.assertNotIn("pi-billing-campaigns", billing)
        self.assertNotIn("pi-campaigns-always-open", campaign)
        self.assertIn("_billing_summary.html", self.template)
        self.assertIn("pi-billing-columns", self.template)
        self.assertIn("pi-row--billing", self.template)
        self.assertIn("pi-list-table--billing", self.template)
        self.assertNotIn("subStatusAtual === '4' && origemLista === 'operacao'", self.js)
        header = (PARTIALS / "_header_filters.html").read_text()
        self.assertIn("PIs enviados ao Financeiro", header)
        self.assertIn("Fila de faturamento", header)
        self.assertIn("origemEfetiva", self.js)
        self.assertIn("subStatusAtual === '4'", self.js)
        routes = ROUTES.read_text()
        self.assertIn("if not origem_lista and filtros.get('id_sub_status_pi') == 4", routes)
        self.assertIn("_garantir_indice_unico_whatsapp_mensagens", (ROOT / "aicentralv2/db.py").read_text())

    def test_internal_campaign_grid_matches_operational_tracking(self):
        for marker in (
            "buildCampaignDetailRowHtml",
            "pi-campaign-detail-row",
            "pi-inner-flight-cell",
            "pi-inner-delivery",
            "pi-inner-investment",
            "pi-campaign-status-pill",
        ):
            self.assertIn(marker, self.js)
        for label in ("Nome", "Cliente", "Responsável", "Veiculação", "Entrega", "Investimento", "Ações"):
            self.assertIn(f'data-label="{label}"', self.js)
        self.assertIn("pi-campaign-identity", self.js)
        self.assertIn("inherited('.pi-commercial-client')", self.js)
        self.assertIn("inherited('.pi-commercial-owner')", self.js)
        self.assertNotIn('data-label="Cliente" class="pi-campaign-detail-platform', self.js)
        self.assertNotIn("aria-hidden=\"true\"></td>", self.js)
        self.assertIn("camp-table--operational", self.js)
        self.assertIn(".pi-page .pi-list-table--hierarchy .pi-campaign-detail-row", self.css)

    def test_table_header_layout_keeps_static_header_above_rows(self):
        self.assertRegex(
            self.css,
            r"\.pi-list-surface\s*\{[^}]*overflow:\s*visible;",
        )
        self.assertRegex(
            self.css,
            r"\.pi-page \.pi-list-table\s*\{[^}]*border-collapse:\s*collapse;",
        )
        self.assertRegex(
            self.css,
            r"\.pi-page \.pi-list-table thead th\s*\{[^}]*position:\s*static;",
        )
        self.assertIn(".pi-page .pi-list-table thead {", self.css)
        self.assertIn("display: table-header-group;", self.css)
        self.assertIn("@media (min-width: 768px)", self.css)
        self.assertIn(".pi-page .pi-list-table--hierarchy > thead", self.css)
        self.assertIn("display: table-header-group;", self.css)
        self.assertNotIn("var(--pi-filter-height", self.css)
        for index, width in enumerate(("26%", "15%", "12%", "13%", "12%", "13%", "9%"), start=1):
            self.assertIn(f".pi-hierarchy-head th:nth-child({index}) {{ width: {width}; }}", self.css)
        self.assertIn(".pi-page .pi-list-table--hierarchy th,", self.css)
        self.assertIn("pi-list-surface--grid", self.template)
        self.assertIn("cx-table-scroll--grid", self.template)
        self.assertIn(".pi-page .cx-table-scroll--grid", self.css)
        self.assertIn("overflow-x: visible", self.css)
        self.assertIn("position: sticky", self.css)
        self.assertNotIn("@media (max-width: 1280px)", self.css)
        self.assertNotIn("updateListStickyOffsets", self.js)
        self.assertIn(".pi-page.pi-operation .camp-list-toolbar .camp-filter-control > i", self.css)
        self.assertIn(".pi-page.pi-operation .camp-list-toolbar .camp-filter-control input", self.css)

    def test_commercial_views_use_camp_list_header_like_acompanhamento(self):
        header = (PARTIALS / "_header_filters.html").read_text()
        table = (PARTIALS / "_table.html").read_text()
        card = (PARTIALS / "_pi_card.html").read_text()
        summary = (PARTIALS / "_commercial_summary.html").read_text()
        commercial_header = header.split("{% else %}", 1)[1]
        self.assertIn("pi-op-header camp-list-header", commercial_header)
        self.assertIn("camp-list-header__identity", commercial_header)
        self.assertIn("camp-list-toolbar", commercial_header)
        self.assertIn("camp-list-total", commercial_header)
        self.assertIn("camp-filter-field", commercial_header)
        self.assertIn('for="filtro_executivo"', commercial_header)
        self.assertIn("PIs em andamento", commercial_header)
        self.assertNotIn("pi-filter-toggle", commercial_header)
        self.assertIn("pi-operacao.css", self.template)
        self.assertIn("pi-operation camp-list-page", self.template)
        self.assertIn("camp-list-content", self.template)
        self.assertIn('class="sr-only">Executivo', header.split("{% else %}", 1)[0])
        self.assertIn("pi-list-table--hierarchy", self.template)
        self.assertIn("pi-hierarchy-columns", self.template)
        self.assertIn("Cliente", table)
        self.assertIn("Entrega", table)
        self.assertEqual(table.count("pi-hierarchy-head"), 1)
        self.assertIn("cadu_pi/_pi_card.html", self.template)
        self.assertIn("data-label=\"Investimento\"", card)
        self.assertIn("btn_expandir_todas", commercial_header)
        self.assertIn("<tfoot>", summary)
        self.assertIn("pi-commercial-summary__values", summary)
        self.assertIn("table-layout: fixed", self.css)
        self.assertIn(".pi-page.pi-operation.camp-list-page > .pi-op-header.camp-list-header", self.css)

    def test_shared_card_renders_the_three_commercial_statuses(self):
        env = Environment(loader=FileSystemLoader(ROOT / "aicentralv2/templates"))
        env.filters["format_brl"] = lambda value: f"R$ {float(value):.2f}"
        env.globals["url_for"] = lambda endpoint, **values: f"/pi/{values.get('id_pi', '')}"
        template = env.from_string(
            "{% import 'cadu_pi/_pi_row.html' as pi_row with context %}"
            "{% include 'cadu_pi/_pi_card.html' %}"
        )
        pi = {
            "id_pi": 176,
            "codigo_pi_cc": "PI-176",
            "titulo_pi": "None",
            "cliente_nome": "Cliente",
            "status_descricao": "Em andamento",
            "resp_comercial_nome": "Ana Silva",
            "periodo_inicio": date(2026, 9, 1),
            "periodo_fim": date(2026, 9, 30),
            "total_campanhas": 2,
            "valor_liquido": 100,
            "valor_bruto": 120,
            "camp_midia_prev_total": 80,
            "camp_midia_gasto_total": 40,
            "camp_pct_midia": 50,
        }
        for status in ("1", "2", "3"):
            rendered = template.render(
                pi=pi,
                sub_status_atual=status,
                lista_somente_leitura=False,
                nomes_meses={},
            )
            self.assertEqual(7, rendered.count("<td"))
            self.assertIn('data-label="Investimento"', rendered)
            self.assertIn("pi-group-toggle", rendered)
            self.assertIn(">—</strong>", rendered)
        self.assertIn("Mídia", rendered)

    def test_commercial_campaigns_use_flat_hierarchy_rows(self):
        self.assertIn("autoLoadHierarchyCampaigns", self.js)
        self.assertIn("buildCampaignDetailRowHtml", self.js)
        self.assertIn("sub_status_atual|string not in ['1', '2', '3', '4']", self.template)
        self.assertNotIn('<table class="camp-table camp-table--operational">', self.template)

    def test_mobile_cards_and_reduced_motion_are_explicit(self):
        self.assertIn("@media (max-width: 767px)", self.css)
        self.assertIn("content: attr(data-label)", self.css)
        card = (PARTIALS / "_pi_card.html").read_text()
        for label in ("Nome", "Cliente", "Responsável", "Veiculação", "Entrega", "Investimento", "Ações"):
            self.assertIn(f'data-label="{label}"', card)
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
        self.assertNotIn("--pi-list-header-height", self.css)

    def test_shared_card_keeps_status_flight_and_title_fallback(self):
        card = (PARTIALS / "_pi_card.html").read_text()
        row = (PARTIALS / "_pi_row.html").read_text()
        self.assertIn("pi-row--config", self.template)
        self.assertIn("<time datetime=", card)
        self.assertIn("pi-status-badge", card)
        self.assertIn("pi_row.title_text(pi)", card)
        self.assertIn("raw_title|lower in ['', 'none', 'null']", row)
        self.assertIn("{{- '—'", row)

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

    def test_operation_layout_uses_full_width_content_area(self):
        self.assertIn(".pi-page.pi-operation {", self.css)
        self.assertIn("max-width: none", self.css)
        self.assertRegex(
            self.css,
            r"\.pi-page\.pi-operation > \.pi-list-surface\.camp-list-content\s*\{[^}]*max-width:\s*none;",
        )

    def test_dedicated_script_owns_filters_and_lazy_expansion(self):
        for function_name in (
            "aplicarFiltros",
            "debounceAplicarFiltros",
            "buscarClientesFiltro",
            "filtrarMesesPorAno",
            "togglePiGroup",
            "toggleCampanhas",
            "toggleTodasCampanhas",
            "toggleAgenciaPis",
        ):
            self.assertIn(function_name, self.js)
        self.assertNotIn("function aplicarFiltros", self.template)
        self.assertNotIn("function buscarClientesFiltro", self.template)
        self.assertIn("/api/cadu-pi/", self.js)
        self.assertIn("/api/cadu_pi/", self.js)

    def test_faturamento_ref_queries_ignore_invalid_competencia(self):
        from aicentralv2 import db as dbmod
        self.assertIn("_MES_REF_SQL_VALIDO", dbmod.obter_meses_ref_pi.__globals__)
        self.assertIn("^[0-9]{1,2}/[0-9]{2,4}$", dbmod._MES_REF_SQL_VALIDO)
        self.assertIn("anexar_lista(pis)", ROUTES.read_text())
        self.assertIn("Falha ao anexar resultado financeiro na lista de PIs", ROUTES.read_text())

    def test_programmatic_platform_uses_inventory_mark_not_pro_icon(self):
        shared_js = (ROOT / "aicentralv2/static/js/campanhas-ui.js").read_text()
        self.assertIn("mark: 'programatica'", shared_js)
        self.assertIn("platform-logo--programatica", shared_js)
        self.assertNotIn("fa-chart-network", shared_js)
        self.assertIn(".platform-icon-wrap.is-programmatic", self.shared_css)

    def test_new_partials_do_not_introduce_daisyui_components(self):
        forbidden = re.compile(
            r'(?<!cx-)\b(?:modal-box|modal-action|btn-primary|btn-ghost|'
            r'badge-primary|alert-info|dropdown-content|menu-title)\b'
        )
        for path in PARTIALS.glob("*.html"):
            self.assertIsNone(forbidden.search(path.read_text()), path.name)


if __name__ == "__main__":
    unittest.main()
