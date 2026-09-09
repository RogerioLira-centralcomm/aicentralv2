import unittest
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "aicentralv2" / "templates"
STATIC = ROOT / "aicentralv2" / "static"


class PiMobileUiContractTest(unittest.TestCase):
    def _source(self, path):
        return path.read_text(encoding="utf-8")

    def test_templates_mobile_sao_sintaticamente_validos(self):
        paths = [
            TEMPLATES / "cadu_pi_form.html",
            TEMPLATES / "campanhas_pi_detalhe.html",
            TEMPLATES / "pi_operacao" / "_mobile_tabs.html",
            TEMPLATES / "pi_operacao" / "_mobile_summary.html",
            TEMPLATES / "pi_operacao" / "_sidebar.html",
        ]
        environment = Environment()
        for path in paths:
            with self.subTest(path=path.name):
                environment.parse(self._source(path))

    def test_detalhes_compartilham_as_tres_areas_moveis(self):
        tabs = self._source(TEMPLATES / "pi_operacao" / "_mobile_tabs.html")
        pi_detail = self._source(TEMPLATES / "cadu_pi_form.html")
        campaign_detail = self._source(TEMPLATES / "campanhas_pi_detalhe.html")
        sidebar = self._source(TEMPLATES / "pi_operacao" / "_sidebar.html")

        for view in ("summary", "edit", "operation"):
            self.assertIn(f'data-mobile-tab="{view}"', tabs)
        self.assertIn('role="tablist"', tabs)
        self.assertIn("pi_operacao/_mobile_summary.html", pi_detail)
        self.assertIn('data-mobile-panel="edit"', pi_detail)
        self.assertIn('class="pi-mobile-savebar"', pi_detail)
        self.assertIn('data-mobile-panel="summary"', campaign_detail)
        self.assertIn('data-mobile-panel="edit"', campaign_detail)
        self.assertIn('data-mobile-panel="operation"', sidebar)

    def test_campanha_tem_diarios_em_cards_sem_perder_tabela(self):
        source = self._source(TEMPLATES / "campanhas_pi_detalhe.html")
        css = self._source(STATIC / "css" / "pi-operacao.css")

        self.assertIn('class="campaign-daily-table"', source)
        self.assertIn('data-label="Atingido"', source)
        self.assertIn(".campaign-daily-table td::before", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", css)

    def test_css_corrige_header_sidebar_modais_e_safe_area(self):
        css = self._source(STATIC / "css" / "pi-operacao.css")

        self.assertIn(".campaign-detail-header .pi-op-title-wrap { flex-basis: auto; }", css)
        self.assertIn(".pi-mobile-tabs", css)
        self.assertIn('[data-mobile-view="operation"] [data-mobile-panel="operation"]', css)
        self.assertIn("env(safe-area-inset-bottom, 0px)", css)
        self.assertIn("body:has(.pi-operation) .cx-modal-panel", css)
        self.assertIn("max-height: 100dvh !important", css)

    def test_javascript_controla_estado_foco_e_superficie_unica(self):
        operation_js = self._source(STATIC / "js" / "cadu_pi_operacao.js")
        campaign_js = self._source(STATIC / "js" / "campanha_pi_detalhe.js")

        self.assertIn("function setMobileView(", operation_js)
        self.assertIn("mobileViewFromHash", operation_js)
        self.assertIn("root.addEventListener('invalid'", operation_js)
        self.assertIn("window.location.href = campaignDetailUrl", operation_js)
        self.assertIn("mostrarArea:", operation_js)
        self.assertNotIn("window.alert(", operation_js + campaign_js)
        self.assertNotIn("window.confirm(", operation_js + campaign_js)

    def test_sidebar_oferece_navegacao_circular_entre_pi_e_campanhas(self):
        sidebar = self._source(TEMPLATES / "pi_operacao" / "_sidebar.html")
        operation_js = self._source(STATIC / "js" / "cadu_pi_operacao.js")

        self.assertIn('id="pi-route-pi"', sidebar)
        self.assertIn('id="pi-route-campaigns"', sidebar)
        self.assertIn('id="pi-route-prev"', sidebar)
        self.assertIn('id="pi-route-next"', sidebar)
        self.assertIn("function renderRouteMap(", operation_js)
        self.assertIn("% campaigns.length", operation_js)
        self.assertIn('id="pi-origin-facts"', sidebar)
        self.assertIn('id="pi-origin-client"', sidebar)
        self.assertIn('id="pi-origin-agency"', sidebar)
        self.assertNotIn('id="pi-origin-owner"', sidebar)
        self.assertNotIn('id="pi-origin-campaign-count"', sidebar)
        self.assertIn("function renderPiOrigin(", operation_js)
        self.assertIn("new Intl.DateTimeFormat('pt-BR'", operation_js)

    def test_sidebar_exibe_contexto_complementar_e_datas_brasileiras(self):
        sidebar = self._source(TEMPLATES / "pi_operacao" / "_sidebar.html")
        operation_js = self._source(STATIC / "js" / "cadu_pi_operacao.js")
        repository = self._source(ROOT / "aicentralv2" / "pi_operacao_repository.py")

        self.assertIn('id="pi-origin-agency-row"', sidebar)
        self.assertIn('id="pi-origin-partner-row"', sidebar)
        self.assertIn('id="pi-origin-period"', sidebar)
        self.assertNotIn('id="pi-origin-owner"', sidebar)
        self.assertNotIn('id="pi-origin-campaign-count"', sidebar)
        self.assertIn("new Intl.DateTimeFormat('pt-BR'", operation_js)
        self.assertIn("timeZone: 'UTC'", operation_js)
        self.assertIn("if (partnerRow) partnerRow.hidden = !partner;", operation_js)
        self.assertIn("parc.nome_fantasia AS parceiro_nome", repository)
        self.assertIn('p."Id_parc_reg" AS id_parceiro', repository)
        self.assertIn('parc.id_cliente = p."Id_parc_reg"', repository)

    def test_vinculos_da_cotacao_ficam_bloqueados_e_integrados_aos_contatos(self):
        pi_detail = self._source(TEMPLATES / "cadu_pi_form.html")
        css = self._source(STATIC / "css" / "pi-operacao.css")
        routes = self._source(ROOT / "aicentralv2" / "routes.py")

        self.assertIn("vinculos_cotacao_bloqueados", pi_detail)
        self.assertIn('id="details_contatos"', pi_detail)
        self.assertIn("Cliente e contatos", pi_detail)
        self.assertIn("Vínculos definidos pela cotação de origem", pi_detail)
        self.assertIn("user_is_executivo or vinculos_cotacao_bloqueados", pi_detail)
        self.assertIn("if not vinculos_cotacao_bloqueados", pi_detail)
        for field in ("id_cliente", "id_agencia", "id_parceiro"):
            self.assertIn(f'type="hidden" name="{field}"', pi_detail)
        self.assertIn("if (PI_VINCULOS_COTACAO) return;", pi_detail)
        self.assertIn(".pi-edit-parties.is-locked input:disabled", css)
        self.assertIn("if pi.get('cotacao_id'):", routes)
        self.assertIn("data['id_cliente'] = pi.get('id_cliente')", routes)
        self.assertIn("data['id_agencia'] = pi.get('id_agencia')", routes)
        self.assertIn("data['id_parceiro'] = pi.get('id_parceiro')", routes)

    def test_campanhas_usam_drawer_vanilla_medio(self):
        pi_detail = self._source(TEMPLATES / "cadu_pi_form.html")

        self.assertIn('id="campanha_editor_source"', pi_detail)
        self.assertIn('id="campanha_view_source"', pi_detail)
        self.assertIn("window.cxDrawer.open({", pi_detail)
        self.assertIn("size: 'md'", pi_detail)
        self.assertIn("pi-campaign-editor-section", pi_detail)
        self.assertNotIn('id="modal_nova_campanha"', pi_detail)
        self.assertNotIn('id="modal_ver_campanha"', pi_detail)

    def test_preview_email_exige_comunicacao_e_usa_area_unica(self):
        sidebar = self._source(TEMPLATES / "pi_operacao" / "_sidebar.html")
        operation_js = self._source(STATIC / "js" / "cadu_pi_operacao.js")
        email_base = self._source(
            TEMPLATES / "emails" / "externos" / "pi_operacao" / "base.html"
        )

        self.assertIn('class="pi-email-preview-content"', sidebar)
        self.assertIn("Selecione uma comunicação para gerar a prévia.", operation_js)
        self.assertIn("communicationCatalog.find(", operation_js)
        self.assertIn("logo_centralcomm_url", email_base)
        self.assertNotIn("cadu-logo-variant-2.png", email_base)

    def test_sidebar_desktop_usa_rolagem_unica_e_mobile_preserva_drawer(self):
        css = self._source(STATIC / "css" / "pi-operacao.css")

        self.assertIn(".pi-op-sidebar { position: static;", css)
        self.assertIn(".pi-op-sidebar__scroll { min-width: 0; max-height: none; overflow: visible;", css)
        self.assertIn("overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain;", css)
        self.assertIn(".pi-op-layout:has(> .pi-op-sidebar)", css)

    def test_envio_de_email_expoe_destinatarios_e_exige_modal(self):
        sidebar = self._source(TEMPLATES / "pi_operacao" / "_sidebar.html")
        operation_js = self._source(STATIC / "js" / "cadu_pi_operacao.js")
        css = self._source(STATIC / "css" / "pi-operacao.css")

        self.assertIn('id="pi-confirm-details"', sidebar)
        self.assertIn('id="pi-email-dialog"', sidebar)
        self.assertIn('id="pi-email-frame"', sidebar)
        self.assertIn('sandbox=""', sidebar)
        self.assertIn("details: recipients", operation_js)
        self.assertIn("Revise quem receberá esta comunicação", operation_js)
        self.assertIn("emailDialog.showModal()", operation_js)
        self.assertIn("frame.srcdoc = data.html", operation_js)
        self.assertIn("pi-email-preview-content", sidebar)
        self.assertIn("Selecione uma comunicação para gerar a prévia.", operation_js)
        self.assertIn(".pi-email-dialog {", css)
        self.assertIn(".pi-confirm-dialog.is-email .pi-confirm-dialog__actions { justify-content: flex-start; }", css)

    def test_edicao_do_pi_usa_superficie_vanilla_semantica(self):
        pi_detail = self._source(TEMPLATES / "cadu_pi_form.html")
        css = self._source(STATIC / "css" / "pi-operacao.css")

        for class_name in (
            "pi-edit-surface",
            "pi-origin-quote",
            "pi-edit-section",
            "pi-edit-card",
            "pi-edit-disclosure",
        ):
            self.assertIn(class_name, pi_detail)
            self.assertIn(f".{class_name}", css)


if __name__ == "__main__":
    unittest.main()
