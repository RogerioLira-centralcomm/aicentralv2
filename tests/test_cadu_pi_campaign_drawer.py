"""Contratos de UI da edição do PI e de suas campanhas."""

import unittest
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]
PI_FORM = ROOT / "aicentralv2" / "templates" / "cadu_pi_form.html"
PI_CAMPAIGN_MODALS = ROOT / "aicentralv2" / "templates" / "cadu_pi" / "_campaign_modals.html"
PI_CSS = ROOT / "aicentralv2" / "static" / "css" / "pi-operacao.css"
EMAIL_BASE = (
    ROOT
    / "aicentralv2"
    / "templates"
    / "emails"
    / "externos"
    / "pi_operacao"
    / "base.html"
)


class CaduPiCampaignDrawerUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.form = PI_FORM.read_text(encoding="utf-8")
        cls.modals = PI_CAMPAIGN_MODALS.read_text(encoding="utf-8")
        cls.ui = cls.form + "\n" + cls.modals
        cls.css = PI_CSS.read_text(encoding="utf-8")
        cls.email = EMAIL_BASE.read_text(encoding="utf-8")

    def test_template_jinja_permanece_valido(self):
        Environment().parse(self.form)
        Environment().parse(self.modals)
        Environment().parse(self.email)

    def test_campanhas_usam_modal_enterprise_vanilla(self):
        self.assertIn("{% include 'cadu_pi/_campaign_modals.html' %}", self.form)
        self.assertIn('id="modal_campanha_pi"', self.modals)
        self.assertIn('id="modal_campanha_view_pi"', self.modals)
        self.assertIn('class="cx-modal pi-campaign-modal"', self.modals)
        self.assertIn("campanha_editor_content", self.modals)
        self.assertIn("campanha_view_content", self.modals)
        self.assertIn("dialog.showModal()", self.modals)
        self.assertIn("window.piOpenDialog", self.modals)
        self.assertNotIn("window.cxDrawer.open({", self.ui)
        self.assertNotIn('id="modal_nova_campanha"', self.ui)
        self.assertNotIn('id="modal_ver_campanha"', self.ui)
        self.assertIn("pi-campaign-card__edit", self.form)
        self.assertIn("id_sub_status_pi|string in ['1', '2', '3']", self.form)

    def test_editar_campanha_abre_o_formulario_no_clique(self):
        js = (ROOT / "aicentralv2" / "static" / "js" / "cadu_pi_operacao.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("legacyCampaignAction('edit')", js)
        self.assertIn("abrirModalEditarCampanha", js)
        self.assertIn("Não foi possível abrir o editor desta campanha.", js)

    def test_formulario_preserva_campos_e_secoes_operacionais(self):
        for field in (
            "nome_campanha",
            "obj_contratados",
            "valor_plataforma",
            "id_status",
            "periodo_inicio",
            "periodo_fim",
            "id_plataforma",
            "id_objetivos_campanha",
            "id_responsavel_operacao",
            "link_dash",
        ):
            self.assertIn(f'name="{field}"', self.modals)
        for title in ("Identificação", "Entrega e investimento", "Período e operação"):
            self.assertIn(title, self.modals)
        self.assertIn(".pi-campaign-editor-fields", self.css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", self.css)

    def test_cards_principais_tem_hierarquia_correta(self):
        self.assertIn(
            '<div class="pi-edit-card__head"><div><h2>Período</h2>',
            self.form,
        )
        self.assertIn("Configuração do cálculo", self.form)
        self.assertIn("Composição percentual", self.form)
        self.assertIn("Composição calculada", self.form)
        self.assertIn(".pi-finance-gross", self.css)

    def test_email_operacional_usa_marca_centralcomm(self):
        self.assertIn("logo_centralcomm_url", self.email)
        self.assertIn('alt="CentralComm Media"', self.email)
        self.assertNotIn("cadu-logo", self.email)
        self.assertNotIn("<span style=\"color:#06F17B;\">Cadu</span>", self.email)


if __name__ == "__main__":
    unittest.main()
