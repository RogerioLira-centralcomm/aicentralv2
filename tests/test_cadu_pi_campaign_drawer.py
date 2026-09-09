"""Contratos de UI da edição do PI e de suas campanhas."""

import unittest
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]
PI_FORM = ROOT / "aicentralv2" / "templates" / "cadu_pi_form.html"
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
        cls.css = PI_CSS.read_text(encoding="utf-8")
        cls.email = EMAIL_BASE.read_text(encoding="utf-8")

    def test_template_jinja_permanece_valido(self):
        Environment().parse(self.form)
        Environment().parse(self.email)

    def test_campanhas_usam_drawer_medio_para_editar_e_visualizar(self):
        self.assertIn("campanha_editor_content", self.form)
        self.assertIn("campanha_view_content", self.form)
        self.assertGreaterEqual(self.form.count("window.cxDrawer.open({"), 2)
        self.assertGreaterEqual(self.form.count("size: 'md'"), 2)
        self.assertNotIn('id="modal_nova_campanha"', self.form)
        self.assertNotIn('id="modal_ver_campanha"', self.form)

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
            self.assertIn(f'name="{field}"', self.form)
        for title in ("Identificação", "Entrega e investimento", "Período e operação"):
            self.assertIn(title, self.form)
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
