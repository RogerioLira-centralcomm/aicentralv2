"""Testes do protótipo /crm-v3 (helpers + API mock)."""

import json
import unittest

from flask import Flask

from aicentralv2.crm_v3_helpers import (
    normalizar_telefone,
    parse_texto_contatos,
    pluralizar_contatos,
)
from aicentralv2.crm_v3_data import store
from aicentralv2.crm_v3_routes import bp


def _crm_v3_app():
    # Aponta o template_folder para o real do projeto para que a rota
    # `/crm-v3/` (que renderiza `crm_v3.html`) funcione dentro dos testes.
    import os
    template_folder = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "aicentralv2", "templates")
    )
    static_folder = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "aicentralv2", "static")
    )
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    app.config.update(SECRET_KEY="test-crm-v3", TESTING=True)
    app.register_blueprint(bp)
    return app


def _login(client, user_id=1, user_name="Executivo Teste"):
    """Injeta sessão para simular usuário logado (auth Fase 3)."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = user_name
        sess["user_email"] = "teste@centralx.com"
        sess["user_type"] = "admin"


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
        self.app = _crm_v3_app()
        self.client = self.app.test_client()
        _login(self.client)

    def test_api_bloqueia_sem_login(self):
        anon = self.app.test_client()  # sem chamar _login
        res = anon.get("/crm-v3/api/clientes")
        self.assertEqual(res.status_code, 401)
        data = json.loads(res.data)
        self.assertFalse(data["success"])

    def test_pagina_crm_v3_injeta_executivos_no_contexto(self):
        """Valida o contrato: a view passa `executivos` ao template.

        Faz monkeypatch do `render_template` para capturar o contexto e
        garante que a rota funciona sem banco (fallback = lista vazia).
        A renderização completa do template (com Tailwind/url_for/nav) é
        validada em smoke fora do unittest.
        """
        import aicentralv2.crm_v3_routes as routes
        captured = {}

        def fake_render(name, **ctx):
            captured["name"] = name
            captured["ctx"] = ctx
            return "OK"

        original = routes.render_template
        routes.render_template = fake_render
        try:
            res = self.client.get("/crm-v3/")
        finally:
            routes.render_template = original
        self.assertEqual(res.status_code, 200)
        self.assertEqual(captured["name"], "crm_v3.html")
        self.assertIn("executivos", captured["ctx"])
        # Sem banco disponível no ambiente de teste, a rota captura a
        # exceção e entrega lista vazia (fallback do template com mocks).
        self.assertIsInstance(captured["ctx"]["executivos"], list)

    def test_agencia_clientes_finais(self):
        """Paridade com /crm/api/agencia/<id>/clientes."""
        lista = json.loads(self.client.get("/crm-v3/api/clientes").data)["clientes"]
        agencia = next((c for c in lista if c.get("is_agencia")), None)
        self.assertIsNotNone(agencia, "seed deve conter pelo menos uma agência")
        res = self.client.get(f"/crm-v3/api/agencia/{agencia['id']}/clientes")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertGreater(data["total"], 0)
        for cli_final in data["clientes"]:
            self.assertFalse(cli_final["is_agencia"])
            self.assertEqual(cli_final["agencia_id"], agencia["id"])

    def test_agencia_clientes_finais_404(self):
        res = self.client.get("/crm-v3/api/agencia/inexistente/clientes")
        self.assertEqual(res.status_code, 404)

    def test_agencia_clientes_400_quando_nao_e_agencia(self):
        lista = json.loads(self.client.get("/crm-v3/api/clientes").data)["clientes"]
        nao_agencia = next((c for c in lista if not c.get("is_agencia")), None)
        self.assertIsNotNone(nao_agencia)
        res = self.client.get(f"/crm-v3/api/agencia/{nao_agencia['id']}/clientes")
        self.assertEqual(res.status_code, 400)

    def test_get_clientes(self):
        res = self.client.get("/crm-v3/api/clientes")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertIsInstance(data["clientes"], list)
        self.assertGreater(len(data["clientes"]), 0)
        cliente = data["clientes"][0]
        self.assertRegex(cliente["cnpj"], r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
        self.assertIn(
            cliente["classificacao_cliente"], ("Prospecção", "Ativo", "Geladeira")
        )
        self.assertIn(cliente["tipo"], ("Público", "Privado"))
        for campo in (
            "razao_social", "nome_fantasia", "perfil", "cidade", "uf",
            "segmento", "fonte", "data_cadastro", "responsavel",
        ):
            self.assertTrue(cliente[campo], campo)

    def test_post_contato_valido(self):
        res = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/contatos",
            data=json.dumps({
                "nome": "Teste API",
                "email": "teste.api@example.com",
                "telefone": "11988887777",
                "setor": "Compras",
                "status": "Ativo",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["contato"]["email"], "teste.api@example.com")
        self.assertEqual(data["contato"]["setor"], "Compras")
        self.assertEqual(data["contato"]["status"], "Ativo")

        updated = self.client.patch(
            f"/crm-v3/api/contatos/{data['contato']['id']}",
            json={"setor": "Marketing", "status": "Inativo"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["contato"]["setor"], "Marketing")
        self.assertEqual(updated.get_json()["contato"]["status"], "Inativo")

    def test_post_contato_sem_email(self):
        res = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/contatos",
            data=json.dumps({"nome": "Sem Email"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertFalse(data["success"])

    def test_parse_texto_api(self):
        res = self.client.post(
            "/crm-v3/api/contatos/parse-texto",
            data=json.dumps({"texto": "Ana;ana@test.com;11999998888"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["contatos"]), 1)

    def test_get_atividades(self):
        res = self.client.get("/crm-v3/api/clientes/auto-shopping/atividades")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertGreater(len(data["atividades"]), 0)
        self.assertEqual(data["atividades"][0]["data"], "2024-05-26")

    def test_patch_cliente_campos_seguindo_e_favorito(self):
        res = self.client.patch(
            "/crm-v3/api/clientes/auto-shopping",
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
            "/crm-v3/api/clientes/auto-shopping", json={"seguindo": "sim"}
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(invalid.get_json()["success"])
        missing = self.client.patch(
            "/crm-v3/api/clientes/inexistente", json={"favorito": True}
        )
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(missing.get_json()["success"])

    def test_cria_cliente_com_status_de_prazo_separado_de_seguindo(self):
        res = self.client.post(
            "/crm-v3/api/clientes",
            json={
                "nome": "Novo Cliente",
                "cnpj": "12.345.678/0001-90",
                "razao_social": "Novo Cliente Serviços Ltda.",
                "nome_fantasia": "Novo Cliente",
                "classificacao_cliente": "Ativo",
                "tipo": "Privado",
                "perfil": "direto",
                "cidade": "Recife",
                "uf": "pe",
                "segmento": "Serviços",
                "fonte": "Indicação",
                "data_cadastro": "2026-09-03",
                "responsavel": "Ana Souza",
                "seguindo": True,
            },
        )
        self.assertEqual(res.status_code, 201)
        cliente = res.get_json()["cliente"]
        self.assertEqual(cliente["status"], "sem-atividade")
        self.assertNotEqual(cliente["status"], "seguindo")
        self.assertFalse(cliente["seguindo"])
        self.assertFalse(cliente["favorito"])
        self.assertEqual(cliente["cnpj"], "12.345.678/0001-90")
        self.assertEqual(cliente["razao_social"], "Novo Cliente Serviços Ltda.")
        self.assertEqual(cliente["classificacao_cliente"], "Ativo")
        self.assertEqual(cliente["tipo"], "Privado")
        self.assertEqual(cliente["uf"], "PE")
        self.assertEqual(cliente["data_cadastro"], "2026-09-03")
        self.assertEqual(store.list_notas(cliente["id"]), [])

    def test_patch_cliente_atualiza_campos_realistas(self):
        res = self.client.patch(
            "/crm-v3/api/clientes/auto-shopping",
            json={
                "classificacao_cliente": "Geladeira",
                "tipo": "Público",
                "cidade": "Betim",
                "uf": "mg",
                "segmento": "Mobilidade",
                "fonte": "Licitação",
                "data_cadastro": "2025-01-10",
            },
        )
        self.assertEqual(res.status_code, 200)
        cliente = res.get_json()["cliente"]
        self.assertEqual(cliente["classificacao_cliente"], "Geladeira")
        self.assertEqual(cliente["tipo"], "Público")
        self.assertEqual(cliente["cidade"], "Betim")
        self.assertEqual(cliente["uf"], "MG")
        self.assertEqual(cliente["data_cadastro"], "2025-01-10")

    def test_cliente_valida_classificacao_e_data_cadastro(self):
        classificacao = self.client.post(
            "/crm-v3/api/clientes",
            json={"nome": "Inválido", "classificacao_cliente": "Lead"},
        )
        self.assertEqual(classificacao.status_code, 400)
        data = self.client.patch(
            "/crm-v3/api/clientes/auto-shopping",
            json={"data_cadastro": "03/09/2026"},
        )
        self.assertEqual(data.status_code, 400)

    def test_crud_objetivo(self):
        created = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/objetivos",
            json={"texto": "Fechar contrato", "prazo": "30/06"},
        )
        self.assertEqual(created.status_code, 201)
        objetivo = created.get_json()["objetivo"]
        updated = self.client.patch(
            f"/crm-v3/api/objetivos/{objetivo['id']}",
            json={"texto": "Fechar contrato anual", "concluido": True},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.get_json()["objetivo"]["concluido"])
        deleted = self.client.delete(f"/crm-v3/api/objetivos/{objetivo['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.get_json()["success"])
        self.assertEqual(
            self.client.patch(
                "/crm-v3/api/objetivos/inexistente", json={"texto": "x"}
            ).status_code,
            404,
        )

    def test_objetivo_exige_texto(self):
        res = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/objetivos", json={"prazo": "30/06"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()["success"])

    def test_crud_cotacao(self):
        created = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/cotacoes",
            json={
                "nome_campanha": "Plano anual 2027",
                "titulo": "Plano anual",
                "valor_total": 10000.50,
                "valor": "R$ 10.000,50",
                "status": "Rascunho",
                "periodo_inicio": "2027-01-01",
                "periodo_fim": "2027-12-31",
                "objetivo": "Institucional",
                "plataformas": [" TV Aberta ", "OOH", "tv aberta", ""],
            },
        )
        self.assertEqual(created.status_code, 201)
        cotacao = created.get_json()["cotacao"]
        self.assertRegex(cotacao["numero_cotacao"], r"^COT-202701-[A-F0-9]{4}$")
        self.assertEqual(cotacao["nome_campanha"], "Plano anual 2027")
        self.assertEqual(cotacao["titulo"], "Plano anual")
        self.assertEqual(cotacao["valor_total"], 10000.50)
        self.assertEqual(cotacao["valor"], "R$ 10.000,50")
        self.assertEqual(cotacao["status"], "rascunho")
        self.assertEqual(cotacao["status_canonico"], "Rascunho")
        self.assertEqual(cotacao["status_label"], "Rascunho")
        self.assertEqual(cotacao["objetivo"], "Institucional")
        # Plataformas: normalizadas (trim), sem vazias, sem duplicatas case-insensitive.
        self.assertEqual(cotacao["plataformas"], ["TV Aberta", "OOH"])
        updated = self.client.patch(
            f"/crm-v3/api/cotacoes/{cotacao['id']}",
            json={
                "status_canonico": "Em Acompanhamento",
                "valor_total": 12500,
                "periodo_fim": "2027-11-30",
                "objetivo": "Performance",
                "plataformas": "Google Ads, Meta Ads,Google Ads",
            },
        )
        self.assertEqual(updated.status_code, 200)
        item = updated.get_json()["cotacao"]
        self.assertEqual(item["status"], "em-acompanhamento")
        self.assertEqual(item["status_canonico"], "Em Acompanhamento")
        self.assertEqual(item["status_label"], "Em Acompanhamento")
        self.assertEqual(item["valor_total"], 12500.0)
        self.assertEqual(item["objetivo"], "Performance")
        # Aceita string CSV, normaliza e deduplica.
        self.assertEqual(item["plataformas"], ["Google Ads", "Meta Ads"])
        deleted = self.client.delete(f"/crm-v3/api/cotacoes/{cotacao['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(
            self.client.delete("/crm-v3/api/cotacoes/inexistente").status_code,
            404,
        )

    def test_cotacao_aceita_apenas_statuses_canonicos_e_aliases(self):
        created = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/cotacoes",
            json={
                "titulo": "Campanha",
                "status": "enviada",
                "valor": "R$ 2.500,75",
            },
        )
        self.assertEqual(created.status_code, 201)
        criada = created.get_json()["cotacao"]
        self.assertEqual(criada["valor_total"], 2500.75)
        cotacao_id = criada["id"]
        expected = {
            "Rascunho": "rascunho",
            "Enviada": "enviada",
            "Aprovada": "aprovada",
            "Rejeitada": "rejeitada",
            "Expirada": "expirada",
            "Em Acompanhamento": "em-acompanhamento",
        }
        for canonico, slug in expected.items():
            with self.subTest(status=canonico):
                res = self.client.patch(
                    f"/crm-v3/api/cotacoes/{cotacao_id}",
                    json={"status": canonico},
                )
                self.assertEqual(res.status_code, 200)
                item = res.get_json()["cotacao"]
                self.assertEqual(item["status"], slug)
                self.assertEqual(item["status_canonico"], canonico)

        invalid = self.client.patch(
            f"/crm-v3/api/cotacoes/{cotacao_id}",
            json={"status": "Cancelada"},
        )
        self.assertEqual(invalid.status_code, 400)
        legado = self.client.patch(
            f"/crm-v3/api/cotacoes/{cotacao_id}",
            json={"status": "negociacao"},
        )
        self.assertEqual(legado.status_code, 200)
        self.assertEqual(
            legado.get_json()["cotacao"]["status_canonico"], "Em Acompanhamento"
        )

    def test_cotacao_valida_periodo_e_valor_total(self):
        periodo = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/cotacoes",
            json={
                "titulo": "Período inválido",
                "periodo_inicio": "2027-12-31",
                "periodo_fim": "2027-01-01",
            },
        )
        self.assertEqual(periodo.status_code, 400)
        valor = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/cotacoes",
            json={"titulo": "Valor inválido", "valor_total": "dez mil"},
        )
        self.assertEqual(valor.status_code, 400)

    def test_crud_notas(self):
        listed = self.client.get("/crm-v3/api/clientes/auto-shopping/notas")
        self.assertEqual(listed.status_code, 200)
        self.assertGreaterEqual(len(listed.get_json()["notas"]), 1)
        created = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/notas",
            json={"texto": "Retornar na sexta", "autor": "Ana", "data": "2026-09-04"},
        )
        self.assertEqual(created.status_code, 201)
        nota = created.get_json()["nota"]
        updated = self.client.patch(
            f"/crm-v3/api/notas/{nota['id']}",
            json={"texto": "Retornar na segunda"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["nota"]["texto"], "Retornar na segunda")
        self.assertEqual(
            self.client.delete(f"/crm-v3/api/notas/{nota['id']}").status_code, 200
        )
        self.assertEqual(
            self.client.get("/crm-v3/api/clientes/inexistente/notas").status_code,
            404,
        )

    def test_notas_validam_texto_e_data_iso(self):
        missing_text = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/notas", json={}
        )
        self.assertEqual(missing_text.status_code, 400)
        invalid_date = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/notas",
            json={"texto": "Nota", "data": "04/09/2026"},
        )
        self.assertEqual(invalid_date.status_code, 400)
        self.assertFalse(invalid_date.get_json()["success"])

    def test_atividade_preserva_e_edita_campos_de_contrato(self):
        created = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/atividades",
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
            f"/crm-v3/api/atividades/{atividade['id']}",
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
            "/crm-v3/api/clientes/auto-shopping/atividades",
            json={"titulo": "Reunião", "data": "05/09/2026"},
        )
        self.assertEqual(created.status_code, 400)
        self.assertFalse(created.get_json()["success"])

    def test_store_reinicia_em_memoria(self):
        self.client.post(
            "/crm-v3/api/clientes", json={"nome": "Cliente temporário"}
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
