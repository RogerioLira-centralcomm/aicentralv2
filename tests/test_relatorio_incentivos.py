"""Contratos do relatório de incentivos por cliente_id."""

import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from jinja2 import Environment

from aicentralv2 import db
from aicentralv2.financeiro import routes as financeiro_routes


class RecordingCursor:
    def __init__(self, rows=None):
        self.query = ""
        self.params = ()
        self.rows = rows or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()):
        self.query = " ".join(str(query).split())
        self.params = tuple(params)

    def fetchall(self):
        return self.rows


class RecordingConnection:
    def __init__(self, rows=None):
        self.cursor_instance = RecordingCursor(rows)
        self.rollback_called = False

    def cursor(self):
        return self.cursor_instance

    def rollback(self):
        self.rollback_called = True


class RelatorioIncentivosClienteIdTest(unittest.TestCase):
    def test_resumo_agrega_pelo_cliente_id_exato(self):
        connection = RecordingConnection()
        with patch.object(db, "get_db", return_value=connection):
            resultado = db.obter_relatorio_incentivos_agencias(ano_ref=26)

        self.assertEqual(resultado, [])
        query = connection.cursor_instance.query
        self.assertIn("GROUP BY p.id_cliente", query)
        self.assertIn("agg.id_cliente = i.cliente_id", query)
        self.assertIn("p.id_cliente IS NOT NULL", query)
        self.assertNotIn("GROUP BY p.id_agencia", query)

    def test_resumo_usa_liquido_para_faixa_e_provisionamento(self):
        connection = RecordingConnection(rows=[{
            "id": 1,
            "cliente_id": 174,
            "agencia_nome": "Cliente Teste",
            "agencia_razao": None,
            "total_pis": 2,
            "volume_liquido": 40_000,
        }])
        with (
            patch.object(db, "get_db", return_value=connection),
            patch.object(
                db,
                "obter_incentivo_fracao_por_cliente_volume",
                side_effect=[0.05, 0.06],
            ),
        ):
            resultado = db.obter_relatorio_incentivos_agencias(ano_ref=26)

        query = connection.cursor_instance.query
        self.assertIn("p.vr_liquido_pi", query)
        self.assertIn("AS volume_liquido", query)
        self.assertNotIn("p.vr_bruto_pi", query)
        self.assertEqual(resultado[0]["volume_liquido"], 40_000)
        self.assertEqual(resultado[0]["faixa_atual"], "50K")
        self.assertEqual(resultado[0]["perc_atual"], 5.0)
        self.assertEqual(resultado[0]["incentivo_provisionado"], 2_000)

    def test_modal_lista_pis_pelo_mesmo_cliente_id(self):
        connection = RecordingConnection()
        with patch.object(db, "get_db", return_value=connection):
            resultado = db.obter_pis_relatorio_incentivo_agencia(
                cliente_id=174,
                ano_ref=26,
            )

        self.assertEqual(resultado, [])
        query = connection.cursor_instance.query
        self.assertIn("p.id_cliente = %s", query)
        self.assertNotIn("p.id_agencia = %s", query)
        self.assertEqual(connection.cursor_instance.params[0], 174)

    def test_template_identifica_cadastro_e_cliente(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root
            / "aicentralv2"
            / "templates"
            / "financeiro"
            / "relatorio_incentivos.html"
        ).read_text(encoding="utf-8")
        Environment().parse(source)
        self.assertIn("Cadastros c/ incentivo", source)
        self.assertIn("Cliente / entidade", source)
        self.assertIn("entidade_nome", source)
        self.assertIn("Volume líquido", source)
        self.assertIn("linha.volume_liquido", source)
        self.assertIn("ID cadastro", source)
        self.assertIn("#{{ linha.cliente_id }}", source)
        self.assertNotIn("totais.volume_bruto", source)


class RelatorioIncentivosAnoPadraoTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_sem_parametro_prioriza_2026(self):
        with self.app.test_request_context("/financeiro/relatorio-incentivos"):
            self.assertEqual(
                financeiro_routes._ano_ref_relatorio_incentivos(),
                26,
            )

    def test_ano_vazio_mantem_opcao_todos_anos(self):
        with self.app.test_request_context(
            "/financeiro/relatorio-incentivos?ano="
        ):
            self.assertIsNone(
                financeiro_routes._ano_ref_relatorio_incentivos()
            )

    def test_ano_completo_e_normalizado(self):
        with self.app.test_request_context(
            "/financeiro/relatorio-incentivos?ano=2026"
        ):
            self.assertEqual(
                financeiro_routes._ano_ref_relatorio_incentivos(),
                26,
            )

    def test_pagina_inclui_todos_status_e_periodos(self):
        with (
            self.app.test_request_context(
                "/financeiro/relatorio-incentivos?ano=&mes_ref_comp="
            ),
            patch.object(
                financeiro_routes.main_db,
                "obter_relatorio_incentivos_agencias",
                return_value=[],
            ) as obter_relatorio,
            patch.object(
                financeiro_routes.main_db,
                "obter_anos_ref_pi",
                return_value=[26],
            ) as obter_anos,
            patch.object(
                financeiro_routes.main_db,
                "obter_meses_ref_pi",
                return_value=["9/26"],
            ) as obter_meses,
            patch.object(
                financeiro_routes,
                "render_template",
                return_value="OK",
            ),
        ):
            resposta = financeiro_routes.relatorio_incentivos.__wrapped__()

        self.assertEqual(resposta, "OK")
        obter_relatorio.assert_called_once_with(
            ano_ref=None,
            mes_ref_comp=None,
        )
        obter_anos.assert_called_once_with()
        obter_meses.assert_called_once_with()

    def test_modal_inclui_pis_de_todos_status(self):
        with (
            self.app.test_request_context(
                "/financeiro/api/relatorio-incentivos/pis?cliente_id=174"
            ),
            patch.object(
                financeiro_routes.main_db,
                "cliente_possui_incentivo",
                return_value=True,
            ),
            patch.object(
                financeiro_routes.main_db,
                "obter_pis_relatorio_incentivo_agencia",
                return_value=[],
            ) as obter_pis,
            patch.object(
                financeiro_routes.main_db,
                "obter_cliente_por_id",
                return_value={"nome_fantasia": "Filadélfia"},
            ),
        ):
            resposta = financeiro_routes.api_relatorio_incentivos_pis.__wrapped__()

        self.assertTrue(resposta.get_json()["success"])
        obter_pis.assert_called_once_with(
            cliente_id=174,
            ano_ref=26,
            mes_ref_comp=None,
        )


if __name__ == "__main__":
    unittest.main()
