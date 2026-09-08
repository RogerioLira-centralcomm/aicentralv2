"""Testes sem PostgreSQL da listagem operacional de campanhas."""

import unittest
from datetime import date
from pathlib import Path

from jinja2 import Environment

from aicentralv2.campanhas_pi_list import (
    build_campaign_list_filters,
    group_campaigns_by_status,
)


class CampanhasPiGroupingTest(unittest.TestCase):
    def test_ativas_vem_primeiro_e_historico_fica_ordenado(self):
        campanhas = [
            {"id_campanha": 2, "status_nome": "Finalizada", "periodo_fim": date(2026, 2, 1)},
            {"id_campanha": 1, "status_nome": "Ativa", "periodo_fim": date(2026, 1, 1)},
            {"id_campanha": 4, "status_nome": "Cancelada", "periodo_fim": date(2026, 4, 1)},
            {"id_campanha": 3, "status_nome": "ATIVA", "periodo_fim": date(2026, 3, 1)},
        ]

        grupos = group_campaigns_by_status(campanhas)

        self.assertEqual([c["id_campanha"] for c in grupos["active"]["campanhas"]], [3, 1])
        self.assertEqual([g["label"] for g in grupos["history"]], ["Finalizada", "Cancelada"])
        self.assertEqual(grupos["history_count"], 2)
        self.assertEqual(grupos["total_count"], 4)

    def test_status_ausente_tem_grupo_explicito_e_totais(self):
        grupos = group_campaigns_by_status(
            [
                {
                    "id_campanha": 7,
                    "status_nome": None,
                    "totalizador_gasto": "R$ 1.250,50",
                    "custo_midia_previsto": 2000,
                }
            ]
        )

        self.assertEqual(grupos["history"][0]["label"], "Sem status")
        self.assertEqual(grupos["history"][0]["total_gasto"], 1250.5)
        self.assertEqual(grupos["history"][0]["total_previsto"], 2000.0)


class CampanhasPiContractTest(unittest.TestCase):
    def test_filtros_ignoram_mes_e_status(self):
        filtros = build_campaign_list_filters(
            {
                "mes_ref_comp": "9/26",
                "id_status": "2",
                "resp_comercial": "12",
                "id_cliente": "174",
            }
        )

        self.assertEqual(filtros, {"resp_comercial": 12, "id_cliente": 174})

    def test_template_novo_e_sintaticamente_valido(self):
        project_root = Path(__file__).resolve().parents[1]
        template_path = project_root / "aicentralv2" / "templates" / "campanhas_pi_lista.html"
        source = template_path.read_text(encoding="utf-8")
        Environment().parse(source)
        row_source = (
            project_root
            / "aicentralv2"
            / "templates"
            / "campanhas_pi"
            / "_lista_row.html"
        ).read_text(encoding="utf-8")
        Environment().parse(row_source)

        self.assertIn("data-history-container", source)
        self.assertIn("camp-list-header", source)
        self.assertNotIn('id="filtroMesRef"', source[: source.index("{% if false %}")])
        self.assertNotIn("window.confirm(", source)
        self.assertNotIn("window.alert(", source)
        self.assertIn("requestCampConfirmation", source)
        self.assertIn("campActionStatus", source)
        for visible_metric in ("Orçado", "Realizado", "Restante", "Previsto"):
            self.assertIn(visible_metric, row_source)
        self.assertIn("camp-investment-bar", row_source)
        self.assertIn("camp-progress", row_source)

    def test_rota_usa_consulta_completa(self):
        project_root = Path(__file__).resolve().parents[1]
        source = (project_root / "aicentralv2" / "routes.py").read_text(encoding="utf-8")
        route_source = source[source.index("def campanhas_pi_lista():") :]
        route_source = route_source[: route_source.index("@app.route", 1)]

        self.assertIn("db.obter_campanhas_pi(filtros or None)", route_source)
        self.assertNotIn("obter_campanhas_pi_acompanhamento", route_source)


if __name__ == "__main__":
    unittest.main()
