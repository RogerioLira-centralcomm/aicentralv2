import unittest
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "aicentralv2/templates/crm_pipeline.html"
CSS = ROOT / "aicentralv2/static/css/cotacao_pipeline.css"
LIST_TEMPLATE = ROOT / "aicentralv2/templates/cadu_cotacoes.html"
LIST_CSS = ROOT / "aicentralv2/static/css/cotacao_lista.css"
DB = ROOT / "aicentralv2/db.py"
ROUTES = ROOT / "aicentralv2/routes.py"


class CrmPipelineLogosContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = TEMPLATE.read_text()
        cls.css = CSS.read_text()
        cls.list_template = LIST_TEMPLATE.read_text()
        cls.list_css = LIST_CSS.read_text()
        cls.db = DB.read_text()
        cls.routes = ROUTES.read_text()

    def test_pipeline_receives_client_and_agency_logos(self):
        self.assertIn("web_cli.logo_url AS cliente_logo_url", self.db)
        self.assertIn("web_agn.logo_url AS agencia_logo_url", self.db)
        self.assertIn("pp_company_avatar(cotacao.cliente_nome", self.template)
        self.assertIn("pp_company_avatar(cotacao.agencia_nome", self.template)

    def test_real_logos_use_a_continuous_dark_surface(self):
        self.assertIn(".pp-company-avatar img", self.css)
        self.assertIn("background: #172033;", self.css)
        self.assertIn("background: transparent;", self.css)

    def test_avatar_only_exists_when_there_is_a_logo(self):
        macro = self.template.split(
            "{% macro pp_company_avatar", 1
        )[1].split("{% endmacro %}", 1)[0]
        self.assertIn("{% if logo_url %}", macro)
        self.assertNotIn("(nome or '?')", macro)
        self.assertIn("closest('.pp-company-avatar').hidden=true", macro)

    def test_quote_list_shows_agency_then_final_client(self):
        self.assertIn("agn.nome_fantasia as agencia_nome", self.db)
        self.assertIn("web_cli.logo_url as cliente_logo_url", self.db)
        self.assertIn("web_agn.logo_url as agencia_logo_url", self.db)
        self.assertIn("cotacao.agencia_nome", self.list_template)
        self.assertIn("cotacao.cliente_nome", self.list_template)
        self.assertIn("cot-lista-identidade-seta", self.list_template)
        self.assertIn(".cot-lista-logo img", self.list_css)

    def test_pipeline_exposes_quote_type(self):
        self.assertIn("cot.tipo_comercial", self.db)
        self.assertIn("pp_quote_type(cotacao.tipo_comercial)", self.template)

    def test_pipeline_header_is_compact_and_metrics_filter_cards(self):
        self.assertIn("max-height: 4rem;", self.css)
        self.assertIn('data-card-filter="ativas"', self.template)
        self.assertIn('data-card-filter="paradas"', self.template)
        self.assertIn("cardFilterAtivo", self.template)
        self.assertIn("data-days=", self.template)

    def test_pipeline_uses_human_readable_money(self):
        start = self.template.index("{% macro money_br")
        end = self.template.index("{%- endmacro %}", start) + len("{%- endmacro %}")
        macro = self.template[start:end]
        template = Environment().from_string(macro + "{{ money_br(valor) }}")

        self.assertEqual(" ".join(template.render(valor=500_200).split()), "500 mil")
        self.assertEqual(" ".join(template.render(valor=1_200_000).split()), "1,2 mi")

    def test_detail_uses_vanilla_drawer_structure(self):
        self.assertIn('class="pp-detail-head"', self.template)
        self.assertIn('class="pp-detail-facts"', self.template)
        self.assertIn('class="pp-detail-footer"', self.template)
        self.assertIn(".pp-detail-head", self.css)
        self.assertIn(".pp-detail-footer", self.css)

    def test_pipeline_has_five_shared_commercial_stages(self):
        self.assertIn(
            "['Rascunho', 'Enviada', 'Em Acompanhamento', 'Próximo de Aprovar', 'Aprovada']",
            self.template,
        )
        self.assertIn("'Em Acompanhamento': []", self.db)
        self.assertIn("'Próximo de Aprovar': []", self.db)
        self.assertNotIn("cot.tipo_comercial = 'midia'", self.db)

    def test_cards_expose_owner_next_action_and_sla(self):
        self.assertIn("cotacao.proxima_acao", self.template)
        self.assertIn('class="pp-owner"', self.template)
        self.assertIn('class="pp-sla is-', self.template)
        self.assertIn("SLA {{ dias }}/{{ sla_limite }} dias", self.template)
        self.assertIn("pa.data_prazo AS proxima_acao_data", self.db)

    def test_drag_rules_and_loss_are_explicit(self):
        self.assertIn("originalStatus === 'Rascunho' && novoStatus === 'Enviada'", self.template)
        self.assertIn("originalStatus === 'Em Acompanhamento'", self.template)
        self.assertIn("window.showConfirm", self.template)
        self.assertIn("api_pipeline_marcar_perda", self.routes)
        self.assertIn("motivos_validos = {'Preço', 'Concorrente', 'Timing', 'Escopo', 'Outro'}", self.routes)
        self.assertIn("f'[PERDA] {motivo}'", self.routes)

    def test_next_action_uses_existing_activities(self):
        self.assertIn("api_pipeline_proxima_acao", self.routes)
        self.assertIn("db.atualizar_atividade_cliente", self.routes)
        self.assertIn("db.criar_atividade_cliente", self.routes)
        self.assertIn("salvarProximaAcao", self.template)

    def test_history_is_a_floating_accessible_sidebar(self):
        self.assertIn('id="pp_history_sidebar"', self.template)
        self.assertIn('id="pp_history_backdrop"', self.template)
        self.assertIn("api_pipeline_historico", self.routes)
        self.assertIn("win_rate", self.routes)
        self.assertIn("ticket_medio", self.routes)
        self.assertIn(".pp-history-sidebar.is-open", self.css)
        self.assertIn("e.key.toLowerCase() === 'h'", self.template)

    def test_pipeline_assets_have_responsive_contract(self):
        self.assertIn("cotacao_pipeline.css') }}?v=6", self.template)
        self.assertIn("scroll-snap-type: x proximity", self.css)
        self.assertIn("@media (max-width: 640px)", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)


if __name__ == "__main__":
    unittest.main()
