"""Testes do protótipo /teste-crm (helpers + API mock)."""

import json
import unittest

from flask import Flask

from aicentralv2.crm_test_helpers import (
    normalizar_telefone,
    parse_texto_contatos,
    pluralizar_contatos,
)
from aicentralv2.crm_test_routes import bp


def _crm_test_app():
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app


class CrmTestHelpersTest(unittest.TestCase):
    def test_pluralizar_contatos(self):
        self.assertEqual(pluralizar_contatos(0), "0 contatos")
        self.assertEqual(pluralizar_contatos(1), "1 contato")
        self.assertEqual(pluralizar_contatos(2), "2 contatos")
        self.assertEqual(pluralizar_contatos(10), "10 contatos")

    def test_normalizar_telefone(self):
        self.assertEqual(normalizar_telefone("(31) 99399-9939"), "5531993999939")
        self.assertEqual(normalizar_telefone("5531993999939"), "5531993999939")
        self.assertEqual(normalizar_telefone(""), "")
        self.assertEqual(normalizar_telefone(None), "")

    def test_parse_texto_contatos_valido(self):
        texto = "João Silva;joao@empresa.com;11999999999;Gerente\nMaria;maria@empresa.com"
        rows = parse_texto_contatos(texto)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["nome"], "João Silva")
        self.assertEqual(rows[0]["email"], "joao@empresa.com")
        self.assertEqual(rows[0]["telefone"], "11999999999")
        self.assertEqual(rows[0]["cargo"], "Gerente")

    def test_parse_texto_contatos_vazio(self):
        self.assertEqual(parse_texto_contatos(""), [])
        self.assertEqual(parse_texto_contatos("   \n  "), [])

    def test_parse_texto_contatos_lixo(self):
        self.assertEqual(parse_texto_contatos("sem email aqui"), [])
        self.assertEqual(parse_texto_contatos("nome;invalido"), [])


class CrmTestApiTest(unittest.TestCase):
    def setUp(self):
        self.app = _crm_test_app()
        self.client = self.app.test_client()

    def test_get_clientes(self):
        res = self.client.get("/teste-crm/api/clientes")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertIsInstance(data["clientes"], list)
        self.assertGreater(len(data["clientes"]), 0)

    def test_post_contato_valido(self):
        res = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/contatos",
            data=json.dumps({
                "nome": "Teste API",
                "email": "teste.api@example.com",
                "telefone": "11988887777",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["contato"]["email"], "teste.api@example.com")

    def test_post_contato_sem_email(self):
        res = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/contatos",
            data=json.dumps({"nome": "Sem Email"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertFalse(data["success"])

    def test_parse_texto_api(self):
        res = self.client.post(
            "/teste-crm/api/contatos/parse-texto",
            data=json.dumps({"texto": "Ana;ana@test.com;11999998888"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["contatos"]), 1)

    def test_get_atividades(self):
        res = self.client.get("/teste-crm/api/clientes/auto-shopping/atividades")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertGreater(len(data["atividades"]), 0)


if __name__ == "__main__":
    unittest.main()
