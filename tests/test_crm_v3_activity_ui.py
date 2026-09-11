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
        self.assertLess(self.template.index("Cliente / empresa"), self.template.index("Detalhes da atividade"))
        self.assertLess(self.template.index("Detalhes da atividade"), self.template.index("Planejamento e prazo"))
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
            "cx-ativ-status",
        ):
            self.assertIn(field, ids)

    def test_ai_is_progressive_and_keeps_configuration_collapsed(self):
        self.assertIn('<details class="cx-atividade-ia-topics"', self.template)
        self.assertIn('<div class="cx-drawer-field cx-atividade-kit" data-canal-produtos>', self.template)
        self.assertIn('<details class="cx-atividade-ia-refine"', self.template)
        self.assertIn('<section class="cx-atividade-ia-history"', self.template)
        self.assertNotIn('<details class="cx-atividade-ia-products"', self.template)
        self.assertNotIn('<details class="cx-atividade-ia-history"', self.template)
        self.assertNotIn("data-canal-chips", self.template)
        self.assertNotIn("data-canal-filter", self.template)
        self.assertLess(
            self.template.index("data-canal-suggest"),
            self.template.index("data-ia-topics"),
        )
        self.assertLess(
            self.template.index("data-ia-output"),
            self.template.index("data-ia-history-section"),
        )
        self.assertIn("data-ia-history-empty", self.template)
        self.assertIn("As gerações desta atividade aparecem aqui.", self.template)
        self.assertIn("data-canal-select", self.template)
        self.assertIn("data-collapse-state", self.template)
        self.assertIn("function syncAssistantCollapses", self.js)
        self.assertIn("collapseOptional", self.js)
        self.assertIn("Usar neste texto", self.js)
        self.assertIn("cx-atividade-ia-toolbar", self.template)
        self.assertIn("Rumo e tom", self.template)
        self.assertIn("data-chip-optional", self.template)
        self.assertIn("falar_sobre_canal", self.template)
        self.assertIn('data-value="apresentar_solucao"', self.template)
        self.assertIn('data-value="estudar"', self.template)
        self.assertIn('data-value="linkedin"', self.template)
        self.assertIn("Abrir LinkedIn", self.js)
        self.assertIn("data-canal-produtos", self.template)
        self.assertNotIn("data-canal-produtos hidden", self.template)
        self.assertIn("data-ia-brief-meta", self.template)
        self.assertNotIn("data-ia-brief-lines", self.template)
        self.assertIn("data-ia-brief", self.template)
        self.assertIn("syncAssistantBriefing", self.js)
        self.assertIn("_canalCleared", self.js)
        self.assertIn("Spotify", self.template)
        self.assertIn("Interativos", self.template)
        self.assertIn("data-canal-ficha", self.template)
        self.assertIn("data-open-canais", self.template)
        self.assertIn("cx-btn cx-btn-primary cx-atividade-ia-generate", self.template)
        self.assertIn("cx-btn cx-btn-ghost cx-btn-sm", self.template)
        self.assertIn('<small data-collapse-state>opcional</small>', self.template)
        self.assertNotIn("o texto já escrito", self.template)
        self.assertNotIn(" · ", self.template)
        self.assertNotIn("cadência", self.template)
        self.assertRegex(
            self.css,
            r"\.cx-atividade-editor-side\s*\{[^}]*background:\s*var\(--cx-surface-muted\)",
        )
        self.assertIn(".cx-atividade-editor-side .cx-drawer-ia-output", self.css)
        self.assertIn("display: block", self.css.split(".cx-atividade-editor-side .cx-drawer-ia-output", 1)[1][:180])
        self.assertIn("<textarea id=\"cx-ativ-ia-instrucoes\"", self.template)
        self.assertIn("wireCanalPicker", self.js)
        self.assertIn("openDrawerCanais", self.js)
        self.assertIn("payload.notas_executivo = payload.descricao", self.js)
        self.assertIn("if (activityType !== 'atividade')", self.js)
        self.assertIn("delete payload.descricao", self.js)
        self.assertLess(
            self.js.index("if (activityType !== 'atividade')"),
            self.js.index("delete payload.descricao"),
        )
        self.assertIn("canApply: false", self.js)
        self.assertIn("canApply: activityType === 'atividade'", self.js)
        self.assertIn("enrichAtividadeIaPayload", self.js)
        self.assertIn("destinatario", self.js)
        self.assertIn("responsavel_interno", self.js)
        self.assertIn("archiveCurrentPreview", self.js)
        self.assertIn("ia/historico?limit=8&atividade_id=", self.js)
        self.assertIn("attachPendingIa", self.js)
        self.assertIn("startInlineEdit", self.js)
        self.assertIn("appendHistoryActions", self.js)
        self.assertIn("wireAtividadeAssistente", self.js)
        self.assertIn("/ia/modelo-estilo", self.js)
        self.assertNotIn("/ia/sugerir-data", self.js)
        self.assertIn("addBusinessDays", self.js)
        self.assertIn("wireAtividadeAutosave", self.js)
        self.assertIn("persistAtividade", self.js)
        self.assertIn("mountAtividadeHeaderChrome", self.js)
        self.assertNotIn("breadcrumb: 'CRM v3 · Atividade'", self.js)
        self.assertNotIn("function submitAtividade", self.js)
        self.assertIn("data-ia-style-section", self.template)
        self.assertNotIn("data-atividade-modelo", self.template)
        self.assertNotIn("Usar modelo", self.template)
        self.assertNotIn("wireAtividadeModelo", self.js)
        self.assertNotIn("A descrição não foi alterada", self.js)

    def test_right_side_prioritizes_channel_result_and_keeps_history(self):
        toolbar = self.template.index("cx-atividade-ia-toolbar")
        output = self.template.index("data-ia-output")
        style = self.template.index("Modelo ativo")
        history = self.template.index("Histórico")
        self.assertLess(toolbar, output)
        self.assertLess(output, style)
        self.assertLess(style, history)
        self.assertIn("['gerar-roteiro', 'melhorar-texto', 'gerar-comunicacao']", self.js)
        self.assertIn("renderAssistantResult", self.js)
        self.assertIn("Abrir WhatsApp", self.js)
        self.assertIn("Criar e-mail", self.js)
        self.assertIn("Editar texto", self.js)
        self.assertIn("Aplicar modelo", self.js)
        self.assertIn("Copiar conteúdo", self.js)
        self.assertIn("Sem contato selecionado — saudação genérica aplicada.", self.js)
        self.assertIn("Copiar assunto", self.js)
        self.assertIn("Copiar mensagem", self.js)
        self.assertIn("Copiar tudo", self.js)
        self.assertIn("styleModelNames", self.js)
        self.assertIn("contato_nome", self.js)
        self.assertIn("Objeções e orientações adicionais", self.js)
        self.assertIn("encodeURIComponent(message)", self.js)
        self.assertIn("encodeURIComponent(contactEmail)", self.js)
        self.assertIn("if (phone)", self.js)
        self.assertIn("if (channel === 'email' && contactEmail)", self.js)
        self.assertIn(".cx-atividade-editor-side .cx-drawer-ia-output", self.css)
        self.assertIn("display: block", self.css.split(".cx-atividade-editor-side .cx-drawer-ia-output", 1)[1][:180])
        self.assertIn("white-space: pre-wrap", self.css)
        self.assertIn(".cx-atividade-ia-history-editor input", self.css)
        self.assertIn(".cx-atividade-ia-history-editor-actions", self.css)
        self.assertIn("maxlength=\"50000\"", self.template)
        self.assertIn("0/50000", self.template)
        self.assertIn("Sugerir prazo", self.template)
        self.assertIn("2 dias úteis", self.template)
        self.assertNotIn("Sugerir data com IA", self.template)
        self.assertNotIn("Você também pode registrar atividades passadas.", self.template)
        self.assertIn("data-status-select", self.template)
        self.assertIn("data-status-field", self.template)
        self.assertIn('[data-chip-group="tipo"]', self.css)
        self.assertRegex(
            self.css,
            r'\[data-chip-group="tipo"\]\s*\{[^}]*flex-wrap:\s*nowrap',
        )
        self.assertIn("c.principal", self.js)
        self.assertIn("form._flushAtividadeSave", self.js)
        self.assertIn("refreshAtividadeLists", self.js)
        self.assertIn("Registro atualizado.", self.js)
        self.assertNotIn(">Ativ.<", self.template)
        self.assertIn('name="tipo" data-field="tipo" value="email"', self.template)
        self.assertIn('data-value="email" role="radio" aria-checked="true"', self.template)
        self.assertIn("tipoVal === 'atividade'", self.js)
        self.assertIn("tipoField.value = 'email'", self.js)
        self.assertIn("Defesa do planejamento", self.js)
        self.assertIn(">Zap<", self.template)
        self.assertIn(">Plano<", self.template)
        self.assertNotIn(">WhatsApp<", self.template)
        self.assertNotIn(">Documento<", self.template)
        self.assertNotIn(">Planejamento<", self.template)

    def test_mobile_falls_back_to_one_column(self):
        self.assertIn("@media (max-width: 1024px)", self.css)
        self.assertRegex(
            self.css,
            r"@media \(max-width: 1024px\)[\s\S]*?"
            r"\.cx-atividade-editor-grid\s*\{[^}]*flex-direction:\s*column",
        )

    def test_meeting_schedule_is_conditional_and_deadline_is_prioritized(self):
        self.assertIn(">Prazo<", self.template)
        self.assertNotIn("background: #f7faf9", self.css.split(".cx-atividade-deadline", 1)[1][:180])
        self.assertIn('data-meeting-panel hidden', self.template)
        self.assertIn("Agenda da reunião", self.template)
        self.assertIn('data-meeting-field="duration_minutes"', self.template)
        self.assertIn('data-meeting-field="timezone"', self.template)
        self.assertIn("data-meeting-attendees", self.template)
        self.assertIn("Criar convite com Google Meet", self.template)
        self.assertIn("meetingEditor.toggle(val)", self.js)
        self.assertIn("payload.meeting = meetingEditor.payload()", self.js)
        self.assertIn("window.showConfirm({", self.js)
        self.assertNotIn("window.confirm(", self.js)
        self.assertIn("Prévia do convite", self.template)
        self.assertIn(".cx-meeting-panel[hidden]", self.css)


if __name__ == "__main__":
    unittest.main()
