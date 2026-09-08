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


if __name__ == "__main__":
    unittest.main()
