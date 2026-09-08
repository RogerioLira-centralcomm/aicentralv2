import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "aicentralv2/templates/crm_v3/_drawer_atividade.html"
CSS = ROOT / "aicentralv2/static/css/tailwind/enterprise-system.css"
JS = ROOT / "aicentralv2/static/js/crm_v3_drawers.js"


class CrmV3ActivityUiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = TEMPLATE.read_text()
        cls.css = CSS.read_text()
        cls.js = JS.read_text()

    def test_activity_drawer_has_two_equal_work_areas(self):
        self.assertRegex(
            self.css,
            r"\.cx-atividade-editor-grid\s*\{[^}]*"
            r"grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)",
        )
        main = self.template.index('<main class="cx-atividade-editor-main">')
        side = self.template.index('<aside class="cx-atividade-editor-side">')
        self.assertLess(main, side)
        self.assertLess(self.template.index("Registro da atividade"), side)
        self.assertGreater(self.template.index("Preparar roteiro"), side)

    def test_activity_fields_are_unique_after_reorganization(self):
        ids = re.findall(r'\bid="([^"]+)"', self.template)
        duplicates = {value for value in ids if ids.count(value) > 1}
        self.assertEqual(set(), duplicates)
        for field in (
            "cx-ativ-titulo",
            "cx-ativ-data",
            "cx-ativ-responsavel",
            "cx-ativ-contato",
            "cx-ativ-desc",
            "cx-ativ-ia-instrucoes",
        ):
            self.assertIn(field, ids)

    def test_ai_is_progressive_and_does_not_replace_activity_record(self):
        self.assertIn("<details class=\"cx-atividade-side-tools\">", self.template)
        self.assertIn("Outras ações assistidas", self.template)
        self.assertIn("delete payload.descricao", self.js)
        self.assertIn("A descrição não foi alterada", self.js)
        self.assertIn("Aplicar no editor", self.js)

    def test_right_side_history_only_loads_scripts_and_revisions(self):
        self.assertIn("Roteiros disponíveis", self.template)
        self.assertIn("['gerar-roteiro', 'melhorar-texto']", self.js)
        self.assertIn("white-space: pre-wrap", self.css)

    def test_mobile_falls_back_to_one_column(self):
        self.assertIn("@media (max-width: 900px)", self.css)
        self.assertRegex(
            self.css,
            r"@media \(max-width: 900px\)[\s\S]*?"
            r"\.cx-atividade-editor-grid\s*\{[^}]*flex-direction:\s*column",
        )


if __name__ == "__main__":
    unittest.main()
