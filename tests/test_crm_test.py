"""Testes do protótipo /teste-crm (helpers + API mock)."""

import json
import unittest

from flask import Flask

from aicentralv2.crm_test_helpers import (
    normalizar_telefone,
    parse_texto_contatos,
    pluralizar_contatos,
)
from aicentralv2.crm_test_data import store
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
        store.reset()
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
        self.assertEqual(data["atividades"][0]["data"], "2024-05-26")

    def test_patch_cliente_campos_seguindo_e_favorito(self):
        res = self.client.patch(
            "/teste-crm/api/clientes/auto-shopping",
            json={
                "nome": "Auto Shopping Atualizado",
                "responsavel": "Maria",
                "seguindo": False,
                "favorito": True,
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"], body["cliente"])
        self.assertEqual(body["cliente"]["nome"], "Auto Shopping Atualizado")
        self.assertEqual(body["cliente"]["responsavel"], "Maria")
        self.assertFalse(body["cliente"]["seguindo"])
        self.assertTrue(body["cliente"]["favorito"])

    def test_patch_cliente_valida_booleano_e_404(self):
        invalid = self.client.patch(
            "/teste-crm/api/clientes/auto-shopping", json={"seguindo": "sim"}
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(invalid.get_json()["success"])
        missing = self.client.patch(
            "/teste-crm/api/clientes/inexistente", json={"favorito": True}
        )
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(missing.get_json()["success"])

    def test_cria_cliente_com_status_de_prazo_separado_de_seguindo(self):
        res = self.client.post(
            "/teste-crm/api/clientes",
            json={"nome": "Novo Cliente", "seguindo": True},
        )
        self.assertEqual(res.status_code, 201)
        cliente = res.get_json()["cliente"]
        self.assertEqual(cliente["status"], "sem-atividade")
        self.assertNotEqual(cliente["status"], "seguindo")
        self.assertFalse(cliente["seguindo"])
        self.assertFalse(cliente["favorito"])
        self.assertEqual(store.list_notas(cliente["id"]), [])

    def test_crud_objetivo(self):
        created = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/objetivos",
            json={"texto": "Fechar contrato", "prazo": "30/06"},
        )
        self.assertEqual(created.status_code, 201)
        objetivo = created.get_json()["objetivo"]
        updated = self.client.patch(
            f"/teste-crm/api/objetivos/{objetivo['id']}",
            json={"texto": "Fechar contrato anual", "concluido": True},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.get_json()["objetivo"]["concluido"])
        deleted = self.client.delete(f"/teste-crm/api/objetivos/{objetivo['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.get_json()["success"])
        self.assertEqual(
            self.client.patch(
                "/teste-crm/api/objetivos/inexistente", json={"texto": "x"}
            ).status_code,
            404,
        )

    def test_objetivo_exige_texto(self):
        res = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/objetivos", json={"prazo": "30/06"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()["success"])

    def test_crud_cotacao(self):
        created = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/cotacoes",
            json={"titulo": "Plano anual", "valor": "R$ 10.000,00"},
        )
        self.assertEqual(created.status_code, 201)
        cotacao = created.get_json()["cotacao"]
        self.assertEqual(cotacao["status"], "rascunho")
        updated = self.client.patch(
            f"/teste-crm/api/cotacoes/{cotacao['id']}",
            json={"status": "enviada", "status_label": "Enviada"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["cotacao"]["status"], "enviada")
        deleted = self.client.delete(f"/teste-crm/api/cotacoes/{cotacao['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(
            self.client.delete("/teste-crm/api/cotacoes/inexistente").status_code,
            404,
        )

    def test_crud_notas(self):
        listed = self.client.get("/teste-crm/api/clientes/auto-shopping/notas")
        self.assertEqual(listed.status_code, 200)
        self.assertGreaterEqual(len(listed.get_json()["notas"]), 1)
        created = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/notas",
            json={"texto": "Retornar na sexta", "autor": "Ana", "data": "2026-09-04"},
        )
        self.assertEqual(created.status_code, 201)
        nota = created.get_json()["nota"]
        updated = self.client.patch(
            f"/teste-crm/api/notas/{nota['id']}",
            json={"texto": "Retornar na segunda"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["nota"]["texto"], "Retornar na segunda")
        self.assertEqual(
            self.client.delete(f"/teste-crm/api/notas/{nota['id']}").status_code, 200
        )
        self.assertEqual(
            self.client.get("/teste-crm/api/clientes/inexistente/notas").status_code,
            404,
        )

    def test_notas_validam_texto_e_data_iso(self):
        missing_text = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/notas", json={}
        )
        self.assertEqual(missing_text.status_code, 400)
        invalid_date = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/notas",
            json={"texto": "Nota", "data": "04/09/2026"},
        )
        self.assertEqual(invalid_date.status_code, 400)
        self.assertFalse(invalid_date.get_json()["success"])

    def test_atividade_preserva_e_edita_campos_de_contrato(self):
        created = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/atividades",
            json={
                "titulo": "Reunião",
                "data": "2026-09-04",
                "data_label": "Amanhã — 4 de setembro",
                "tipo": "reuniao",
                "responsavel": "LS",
            },
        )
        self.assertEqual(created.status_code, 201)
        atividade = created.get_json()["atividade"]
        self.assertEqual(atividade["data"], "2026-09-04")
        self.assertEqual(atividade["data_label"], "Amanhã — 4 de setembro")
        updated = self.client.patch(
            f"/teste-crm/api/atividades/{atividade['id']}",
            json={
                "data": "2026-09-05",
                "data_label": "Sábado — 5 de setembro",
                "tipo": "ligacao",
                "responsavel": "JP",
            },
        )
        self.assertEqual(updated.status_code, 200)
        item = updated.get_json()["atividade"]
        self.assertEqual(item["data"], "2026-09-05")
        self.assertEqual(item["tipo"], "ligacao")
        self.assertEqual(item["responsavel"], "JP")
        self.assertEqual(item["data_label"], "Sábado — 5 de setembro")

    def test_atividade_rejeita_data_nao_iso(self):
        created = self.client.post(
            "/teste-crm/api/clientes/auto-shopping/atividades",
            json={"titulo": "Reunião", "data": "05/09/2026"},
        )
        self.assertEqual(created.status_code, 400)
        self.assertFalse(created.get_json()["success"])

    def test_store_reinicia_em_memoria(self):
        self.client.post(
            "/teste-crm/api/clientes", json={"nome": "Cliente temporário"}
        )
        self.assertIsNotNone(
            next(
                (c for c in store.list_clientes() if c["nome"] == "Cliente temporário"),
                None,
            )
        )
        store.reset()
        self.assertIsNone(
            next(
                (c for c in store.list_clientes() if c["nome"] == "Cliente temporário"),
                None,
            )
        )


if __name__ == "__main__":
    unittest.main()
