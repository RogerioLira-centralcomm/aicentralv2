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
        self.assertGreater(self.template.index("Assistente"), side)

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

    def test_ai_is_progressive_and_keeps_configuration_collapsed(self):
        self.assertIn("cx-atividade-ia-toolbar", self.template)
        self.assertIn("falar_sobre_canal", self.template)
        self.assertIn('value="apresentar_solucao"', self.template)
        self.assertIn('data-value="apresentar_solucao"', self.template)
        self.assertIn("data-canal-produtos", self.template)
        self.assertIn("Spotify", self.template)
        self.assertIn("payload.notas_executivo = payload.descricao", self.js)
        self.assertIn("delete payload.descricao", self.js)
        self.assertIn("canApply: false", self.js)
        self.assertIn("enrichAtividadeIaPayload", self.js)
        self.assertIn("archiveCurrentPreview", self.js)
        self.assertIn("ia/historico?limit=8&atividade_id=", self.js)
        self.assertIn("attachPendingIa", self.js)
        self.assertNotIn("data-atividade-modelo", self.template)
        self.assertNotIn("Usar modelo", self.template)
        self.assertNotIn("wireAtividadeModelo", self.js)
        self.assertNotIn("A descrição não foi alterada", self.js)

    def test_right_side_prioritizes_channel_result_and_keeps_history(self):
        toolbar = self.template.index("cx-atividade-ia-toolbar")
        output = self.template.index("data-ia-output")
        history = self.template.index("Histórico")
        self.assertLess(toolbar, output)
        self.assertLess(output, history)
        self.assertIn("['gerar-roteiro', 'melhorar-texto', 'gerar-comunicacao']", self.js)
        self.assertIn("renderAssistantResult", self.js)
        self.assertIn("Abrir WhatsApp", self.js)
        self.assertIn("Criar e-mail", self.js)
        self.assertIn("Copiar assunto", self.js)
        self.assertIn("Objeções e orientações adicionais", self.js)
        self.assertIn("encodeURIComponent(message)", self.js)
        self.assertIn("encodeURIComponent(contactEmail)", self.js)
        self.assertIn("if (phone)", self.js)
        self.assertIn("if (channel === 'email' && contactEmail)", self.js)
        self.assertIn("white-space: pre-wrap", self.css)

    def test_mobile_falls_back_to_one_column(self):
        self.assertIn("@media (max-width: 900px)", self.css)
        self.assertRegex(
            self.css,
            r"@media \(max-width: 900px\)[\s\S]*?"
            r"\.cx-atividade-editor-grid\s*\{[^}]*flex-direction:\s*column",
        )

    def test_meeting_schedule_is_conditional_and_deadline_is_prioritized(self):
        self.assertIn(">Prazo<", self.template)
        self.assertNotIn("background: #f7faf9", self.css.split(".cx-atividade-deadline", 1)[1][:180])
        self.assertIn('data-meeting-panel hidden', self.template)
        self.assertIn("Agenda da reunião", self.template)
        self.assertIn('data-meeting-field="duration_minutes"', self.template)
        self.assertIn('data-meeting-field="timezone"', self.template)
        self.assertIn('data-meeting-attendees', self.template)
        self.assertIn("Criar convite com Google Meet", self.template)
        self.assertIn("meetingEditor.toggle(val)", self.js)
        self.assertIn("payload.meeting = meetingEditor.payload()", self.js)
        self.assertIn("window.showConfirm({", self.js)
        self.assertNotIn("window.confirm(", self.js)
        self.assertIn("Prévia do convite", self.template)
        self.assertIn(".cx-meeting-panel[hidden]", self.css)


if __name__ == "__main__":
    unittest.main()
