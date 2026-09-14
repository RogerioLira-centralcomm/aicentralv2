import unittest
from datetime import date, timedelta
from pathlib import Path

from aicentralv2.apex_formatters import format_quotes_chart
from aicentralv2.cotacao_plano import (
    DASHBOARD_TIPOS,
    agregar_semanas_por_tipo,
    agregar_trimestres_por_tipo,
    cotacao_conta_em_relatorio,
    metricas_por_plano,
    parse_alvo_id,
    payload_haste,
    plano_sem_principal_viva,
    serializar_irma,
)


class CotacaoPlanoTest(unittest.TestCase):
    def test_sozinha_ja_conta(self):
        self.assertTrue(cotacao_conta_em_relatorio({"id": 1}))
        self.assertTrue(cotacao_conta_em_relatorio({"id": 1, "eh_principal": True}))
        self.assertFalse(cotacao_conta_em_relatorio({"id": 1, "eh_principal": False}))

    def test_metricas_nao_somam_irmas(self):
        cotacoes = [
            {
                "id": 1,
                "grupo_plano_id": "g1",
                "eh_principal": True,
                "status": "enviada",
                "valor_total_proposta": 100,
            },
            {
                "id": 2,
                "grupo_plano_id": "g1",
                "eh_principal": False,
                "status": "rascunho",
                "valor_total_proposta": 400,
            },
            {
                "id": 3,
                "grupo_plano_id": "g2",
                "eh_principal": True,
                "status": "aprovada",
                "valor_total_proposta": 50,
            },
        ]
        resumo = metricas_por_plano(cotacoes)
        self.assertEqual(1, resumo["oportunidades"])
        self.assertEqual(100, resumo["pipeline"])
        self.assertEqual(50, resumo["faturamento"])
        self.assertEqual(1, resumo["aprovadas"])

    def test_aviso_quando_principal_morre(self):
        irmas = [
            {"id": 1, "eh_principal": True, "status": "rejeitada"},
            {"id": 2, "eh_principal": False, "status": "rascunho"},
        ]
        self.assertTrue(plano_sem_principal_viva(irmas))

    def test_duplicar_nao_troca_quem_conta(self):
        original = {
            "id": 10,
            "numero_cotacao": "COT-A",
            "grupo_plano_id": "abc",
            "eh_principal": True,
            "valor_total_proposta": 200,
            "tipo_comercial": "midia",
            "status": "Enviada",
        }
        copia = {
            "id": 11,
            "numero_cotacao": "COT-B",
            "grupo_plano_id": "abc",
            "eh_principal": False,
            "valor_total_proposta": 200,
            "tipo_comercial": "midia",
            "status": "Rascunho",
        }
        haste = payload_haste(copia, [original, copia])
        self.assertTrue(haste["tem_irmas"])
        self.assertFalse(haste["eh_principal"])
        self.assertEqual("COT-A", haste["principal_numero"])
        self.assertEqual(1, sum(1 for item in haste["irmas"] if item["eh_principal"]))

    def test_grafico_empilha_quatro_tipos(self):
        semana = date(2026, 1, 5)
        rows = [
            {"semana": semana, "tipo_comercial": "midia", "total": 2, "valor_total": 80},
            {"semana": semana, "tipo_comercial": "dados", "total": 1, "valor_total": 20},
        ]
        weeks = agregar_semanas_por_tipo(rows, [semana])
        chart = format_quotes_chart(weeks)
        self.assertEqual(4, len(chart["series"]))
        self.assertEqual(
            ["Mídia", "Parceiros", "Formatos interativos", "Dados"],
            [serie["name"] for serie in chart["series"]],
        )
        self.assertEqual([2], chart["series"][0]["data"])
        self.assertEqual([20.0], chart["series"][3]["currencyValues"])
        self.assertEqual(DASHBOARD_TIPOS[0][2], chart["series"][0]["color"])

    def test_trimestre_soma_so_valor_informado(self):
        rows = [
            {"mes": "2026-01", "tipo_comercial": "midia", "total": 3, "valor_total": 30},
            {"mes": "2026-04", "tipo_comercial": "parceiros", "total": 1, "valor_total": 10},
        ]
        quarters = agregar_trimestres_por_tipo(rows)
        self.assertEqual(3, quarters[0]["total"])
        self.assertEqual(30, quarters[0]["valor_total"])
        self.assertEqual(1, quarters[1]["total"])
        self.assertEqual(1, quarters[1]["tipos"]["parceiros"]["quantidade"])

    def test_vincular_exige_alvo(self):
        with self.assertRaises(ValueError):
            parse_alvo_id(None)
        with self.assertRaises(ValueError):
            parse_alvo_id("")
        with self.assertRaises(ValueError):
            parse_alvo_id("abc")
        self.assertEqual(12, parse_alvo_id("12"))

    def test_serializar_marca_atual(self):
        irma = serializar_irma(
            {
                "id": 7,
                "numero_cotacao": "COT-X",
                "tipo_comercial": "parceiros",
                "valor_total_proposta": 12.5,
                "status_display": "Rascunho",
                "eh_principal": False,
                "grupo_plano_id": "g",
            },
            7,
        )
        self.assertTrue(irma["atual"])
        self.assertEqual("Parceiros", irma["tipo_comercial_label"])

    def test_js_nao_usa_alert_e_escapa_busca(self):
        js = (
            Path(__file__).resolve().parents[1]
            / "aicentralv2"
            / "static"
            / "js"
            / "cotacao_plano.js"
        ).read_text(encoding="utf-8")
        self.assertNotIn("window.alert", js)
        self.assertIn("escapeHtml", js)

    def test_haste_compacta_e_faixa(self):
        html = (
            Path(__file__).resolve().parents[1]
            / "aicentralv2"
            / "templates"
            / "cotacoes"
            / "_plano_haste.html"
        ).read_text(encoding="utf-8")
        self.assertIn("cot-plano-strip", html)
        self.assertIn("Usar esta nos relatórios", html)

    def test_migration_define_uma_principal_por_grupo(self):
        sql = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "add_cotacao_grupo_plano.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("grupo_plano_id", sql)
        self.assertIn("eh_principal", sql)
        self.assertIn("cadu_cotacoes_uma_principal_por_grupo", sql)


class CotacaoPlanoSemanasTest(unittest.TestCase):
    def test_semana_vazia_ainda_tem_tipos(self):
        week = date(2026, 2, 2)
        weeks = agregar_semanas_por_tipo([], [week, week + timedelta(days=7)])
        self.assertEqual(2, len(weeks))
        self.assertEqual(0, weeks[0]["total"])
        self.assertIn("midia", weeks[0]["tipos"])


if __name__ == "__main__":
    unittest.main()
