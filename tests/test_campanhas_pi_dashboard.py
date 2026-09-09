"""Contratos do painel operacional de campanhas, sem banco e sem navegador."""

import unittest
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment

from aicentralv2.campanhas_pi_dashboard import (
    build_month_comparison,
    build_platform_series,
    month_reference,
    previous_month_reference,
    prioritize_active_campaigns,
    project_campaign_health,
    summarize_campaigns,
)


ROOT = Path(__file__).resolve().parents[1]


def active_campaign(**changes):
    today = date(2026, 9, 8)
    row = {
        "id_campanha": 1,
        "nome_campanha": "Campanha teste",
        "cliente_nome": "CentralComm",
        "status_nome": "Ativa",
        "periodo_inicio": today - timedelta(days=50),
        "periodo_fim": today + timedelta(days=50),
        "obj_contratados": 1000,
        "totalizador_atingido": 500,
        "custo_midia_previsto": 10000,
        "totalizador_gasto": 5000,
        "ultimo_diario_data": today,
        "id_responsavel_operacao": 7,
        "responsavel_operacao_nome": "Operação",
    }
    row.update(changes)
    return row


class CampaignDashboardMetricsTest(unittest.TestCase):
    def test_referencia_de_janeiro_volta_para_dezembro(self):
        day = date(2026, 1, 5)
        self.assertEqual(month_reference(day), "1/26")
        self.assertEqual(previous_month_reference(day), "12/25")
        self.assertEqual(previous_month_reference("1/26"), "12/25")

    def test_campanha_no_ritmo_fica_saudavel(self):
        row = project_campaign_health(active_campaign(), today=date(2026, 9, 8))
        self.assertEqual(row["health_severity"], "healthy")
        self.assertEqual(row["pct_objetivo"], 50)
        self.assertEqual(row["periodo_pct_elapsed"], 50)

    def test_atraso_de_entrega_e_excesso_de_investimento_sao_criticos(self):
        row = project_campaign_health(
            active_campaign(totalizador_atingido=180, totalizador_gasto=12000),
            today=date(2026, 9, 8),
        )
        self.assertEqual(row["health_severity"], "critical")
        self.assertGreater(row["desvio_entrega"], 25)
        self.assertGreater(row["pct_custo_midia"], 100)
        self.assertTrue(row["has_delivery_target"])
        self.assertTrue(row["has_investment_plan"])

    def test_dados_ausentes_nao_sao_tratados_como_percentual_zero(self):
        row = project_campaign_health(
            active_campaign(
                periodo_inicio=None,
                periodo_fim=None,
                obj_contratados=None,
                custo_midia_previsto=None,
                valor_plataforma=None,
                id_responsavel_operacao=None,
                responsavel_operacao_nome=None,
            ),
            today=date(2026, 9, 8),
        )
        self.assertFalse(row["has_period_data"])
        self.assertFalse(row["has_delivery_target"])
        self.assertFalse(row["has_investment_plan"])
        self.assertFalse(row["has_operation_owner"])
        self.assertFalse(row["health_classifiable"])
        self.assertEqual(row["health_severity"], "unclassified")

    def test_diario_desatualizado_prazo_curto_e_dados_ausentes_geram_acao(self):
        today = date(2026, 9, 8)
        row = project_campaign_health(
            active_campaign(
                periodo_fim=today + timedelta(days=3),
                totalizador_atingido=300,
                ultimo_diario_data=today - timedelta(days=8),
                id_responsavel_operacao=None,
                responsavel_operacao_nome=None,
            ),
            today=today,
            stale_days=3,
        )
        self.assertEqual(row["health_severity"], "unclassified")
        self.assertGreaterEqual(row["health_issue_count"], 3)

    def test_fila_ordena_por_severidade_e_prazo(self):
        today = date(2026, 9, 8)
        healthy = active_campaign(id_campanha=1)
        critical = active_campaign(
            id_campanha=2,
            totalizador_atingido=50,
            totalizador_gasto=14000,
        )
        ordered = prioritize_active_campaigns([healthy, critical], today=today)
        self.assertEqual([row["id_campanha"] for row in ordered], [2, 1])

    def test_resumo_separa_ativas_de_encerradas(self):
        rows = [
            active_campaign(),
            active_campaign(id_campanha=2, status_nome="Finalizada"),
        ]
        summary = summarize_campaigns(rows)
        self.assertEqual(summary["campanhas"], 2)
        self.assertEqual(summary["campanhas_ativas"], 1)

    def test_deltas_e_serie_de_plataformas(self):
        comparison = build_month_comparison(
            {"campanhas_ativas": 12, "gasto": 150},
            {"campanhas_ativas": 10, "gasto": 100},
        )
        self.assertEqual(comparison["campanhas_ativas"]["delta"], 20)
        self.assertEqual(comparison["gasto"]["delta"], 50)
        series = build_platform_series(
            [{"plataforma_nome": "Meta", "gasto": 200}],
            [{"plataforma_nome": "Google", "gasto": 100}],
        )
        self.assertEqual(series["labels"], ["Google", "Meta"])
        self.assertEqual(series["atual"], [0, 200])
        self.assertEqual(series["anterior"], [100, 0])


class CampaignDashboardContractTest(unittest.TestCase):
    def test_templates_sao_validos_e_dashboard_e_vanilla(self):
        template = (ROOT / "aicentralv2/templates/campanhas_pi.html").read_text()
        row = (
            ROOT
            / "aicentralv2/templates/campanhas_pi/_dashboard_campaign_row.html"
        ).read_text()
        dialog = (
            ROOT
            / "aicentralv2/templates/campanhas_pi/_dashboard_edit_dialog.html"
        ).read_text()
        env = Environment()
        for source in (template, row, dialog):
            env.parse(source)

        self.assertIn("campanhas-dashboard.css", template)
        self.assertIn("campanhas_dashboard.js", template)
        self.assertIn("js/vendor/apexcharts.min.js", template)
        self.assertNotIn("<style", template)
        self.assertNotIn("<script>\n", template)
        self.assertNotIn("cdn.jsdelivr", template)
        self.assertNotIn("Chart.js", template)
        self.assertNotIn("sidebar", template.lower())
        self.assertIn("<progress", row)
        self.assertIn("Informe a meta", row)
        self.assertIn("Responsável não definido", row)
        self.assertIn("responsavel_operacao_foto_url", row)
        self.assertIn("Sem classificação", row)
        self.assertIn("data-edit-campaign", row)
        self.assertIn("campanha_pi_detalhe", row)
        self.assertIn("<dialog", dialog)

    def test_javascript_nao_usa_dialogos_nativos(self):
        source = (
            ROOT / "aicentralv2/static/js/campanhas_dashboard.js"
        ).read_text()
        self.assertNotIn("window.alert(", source)
        self.assertNotIn("window.confirm(", source)
        self.assertNotIn("alert(", source)
        self.assertNotIn("confirm(", source)
        self.assertIn("new window.ApexCharts", source)
        self.assertIn("showModal()", source)
        self.assertIn("row.tem_periodo && row.tem_meta", source)
        css = (
            ROOT / "aicentralv2/static/css/campanhas-dashboard.css"
        ).read_text()
        self.assertIn(".campaign-dashboard [hidden]", css)
        self.assertIn("grid-template-columns: 108px", css)

    def test_rota_separa_recortes_sem_restauracao_legada(self):
        source = (ROOT / "aicentralv2/routes.py").read_text()
        route = source[source.index("def campanhas_pi():") :]
        route = route[: route.index("def _redirect_campanhas_pi_preservar_filtros")]
        self.assertIn("obter_campanhas_dashboard_ativas", route)
        self.assertIn("obter_campanhas_dashboard_encerradas(5)", route)
        self.assertIn("obter_status_dashboard_campanhas", route)
        self.assertIn("'tem_periodo': row.get('has_period_data'", route)
        self.assertIn("'tem_meta': row.get('has_delivery_target'", route)
        self.assertNotIn("_restored", route)
        self.assertNotIn("top_clientes", route)
        db_source = (ROOT / "aicentralv2/db.py").read_text()
        self.assertIn(
            "resp_op.foto_url AS responsavel_operacao_foto_url",
            db_source,
        )


if __name__ == "__main__":
    unittest.main()
