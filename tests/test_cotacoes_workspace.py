"""Testes do workspace comercial e de suas pendências derivadas."""

import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from aicentralv2 import cotacoes_routes


def cotacao_completa(status="Rascunho"):
    return {
        "id": 191,
        "client_id": 10,
        "responsavel_comercial": 20,
        "nome_campanha": "Campanha de teste",
        "objetivo_campanha": "Conversão",
        "periodo_inicio": "2026-09-01",
        "periodo_fim": "2026-09-30",
        "budget_estimado": 42000,
        "status": status,
        "link_publico_token": "token",
        "link_publico_ativo": True,
        "proposta_enviada_em": (
            "2026-09-08 10:00:00" if status != "Rascunho" else None
        ),
    }


def linha_completa():
    return {
        "id": 1,
        "plataforma": "Programática",
        "segmentacao": "Público de interesse",
        "objetivo_kpi": "CPM",
        "data_inicio": "2026-09-01",
        "data_fim": "2026-09-30",
        "investimento_bruto": 42000,
        "investimento_liquido": 33600,
    }


def anexo_pdf():
    return {
        "id": 1,
        "descricao": cotacoes_routes.DESCRICAO_ANEXO_PROPOSTA_PDF,
    }


class EstadoComercialCotacaoTest(unittest.TestCase):
    def test_estado_completo_nao_exige_audiencia_opcional(self):
        estado = cotacoes_routes.montar_estado_comercial_cotacao(
            cotacao_completa(status="Aprovada"),
            linhas=[linha_completa()],
            audiencias=[],
            anexos=[anexo_pdf()],
        )

        audiencia = next(item for item in estado["checklist"] if item["codigo"] == "audiencias")
        self.assertTrue(audiencia["opcional"])
        self.assertEqual(estado["progresso"]["concluidos"], estado["progresso"]["total"])
        self.assertIsNone(estado["proxima_pendencia"])

    def test_primeira_pendencia_aponta_para_dados(self):
        cotacao = cotacao_completa()
        cotacao["responsavel_comercial"] = None
        estado = cotacoes_routes.montar_estado_comercial_cotacao(cotacao)

        self.assertEqual(estado["proxima_pendencia"]["codigo"], "dados")
        self.assertIn("executivo responsável", estado["proxima_pendencia"]["evidencia"])
        self.assertLess(estado["progresso"]["percentual"], 100)

    def test_cotacao_enviada_recomenda_registrar_decisao(self):
        estado = cotacoes_routes.montar_estado_comercial_cotacao(
            cotacao_completa(status="Enviada"),
            linhas=[linha_completa()],
            anexos=[anexo_pdf()],
        )

        self.assertEqual(estado["proxima_pendencia"]["codigo"], "decisao")
        self.assertIn("aprovação ou rejeição", estado["proxima_pendencia"]["evidencia"])

    def test_cotacao_aprovada_nao_recomenda_nova_pendencia(self):
        cotacao = cotacao_completa(status="Aprovada")
        cotacao["link_publico_ativo"] = False
        estado = cotacoes_routes.montar_estado_comercial_cotacao(cotacao)

        self.assertIsNone(estado["proxima_pendencia"])
        self.assertIn("aprovada", estado["recomendacao"].lower())


class WorkspaceComercialRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY="test")
        self.app.register_blueprint(cotacoes_routes.bp)
        self.client = self.app.test_client()

    @patch.object(cotacoes_routes, "_serializar", side_effect=lambda value: value)
    @patch.object(cotacoes_routes.db, "obter_anexos_cotacao", return_value=[anexo_pdf()])
    @patch.object(cotacoes_routes.db, "obter_audiencias_cotacao", return_value=[])
    @patch.object(cotacoes_routes.db, "obter_linhas_cotacao", return_value=[linha_completa()])
    @patch.object(cotacoes_routes.db, "obter_cotacao_por_id", return_value=cotacao_completa())
    def test_endpoint_retorna_contrato_da_sidebar(self, *_mocks):
        with self.client.session_transaction() as sess:
            sess["user_id"] = 99

        response = self.client.get("/api/cotacoes/191/workspace-comercial")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(
            set(payload["data"]),
            {"status", "recomendacao", "proxima_pendencia", "checklist", "progresso"},
        )

    def test_template_preserva_secoes_e_adota_shell_erp(self):
        template = (
            Path(__file__).parents[1]
            / "aicentralv2"
            / "templates"
            / "cadu_cotacoes_detalhes.html"
        ).read_text()

        self.assertIn("{% extends 'base_erp.html' %}", template)
        self.assertIn("cotacoes/_sidebar_comercial.html", template)
        self.assertIn('data-section="itens"', template)
        self.assertIn('data-section="audiencias"', template)
        self.assertIn('data-section="historico"', template)
        self.assertIn('data-section="anexos"', template)
        self.assertIn("cot-op-table-wrap", template)


if __name__ == "__main__":
    unittest.main()
