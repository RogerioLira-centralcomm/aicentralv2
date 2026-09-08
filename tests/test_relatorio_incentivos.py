"""Contratos do relatório de incentivos por cliente_id."""

import unittest
from pathlib import Path
from unittest.mock import patch

from jinja2 import Environment

from aicentralv2 import db


class RecordingCursor:
    def __init__(self):
        self.query = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=()):
        self.query = " ".join(str(query).split())
        self.params = tuple(params)

    def fetchall(self):
        return []


class RecordingConnection:
    def __init__(self):
        self.cursor_instance = RecordingCursor()
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


if __name__ == "__main__":
    unittest.main()
