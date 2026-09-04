"""Testes do protótipo /crm-v3 (helpers + API mock)."""

import json
import unittest

from flask import Flask

from aicentralv2.crm_v3_helpers import (
    normalizar_telefone,
    parse_texto_contatos,
    pluralizar_contatos,
    filtrar_vinculos_colisao_lookup,
    uf_por_capital_operacao,
    texto_sem_markdown,
    titulo_atividade_lista,
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

    def test_uf_por_capital_operacao(self):
        self.assertEqual(uf_por_capital_operacao("BELO HORIZONTE"), "MG")
        self.assertEqual(uf_por_capital_operacao("Belo Horizonte"), "MG")
        self.assertEqual(uf_por_capital_operacao("Rio de Janeiro"), "RJ")
        self.assertEqual(uf_por_capital_operacao("são paulo"), "SP")
        self.assertEqual(uf_por_capital_operacao("São Paulo"), "SP")
        self.assertIsNone(uf_por_capital_operacao("Contagem"))
        self.assertIsNone(uf_por_capital_operacao(""))

    def test_texto_sem_markdown_e_titulo_lista(self):
        bruto = "**Primeiro Contato - Isabel Matos**\n\n**Entrar em contato** com a gerente."
        self.assertEqual(
            texto_sem_markdown(bruto).splitlines()[0],
            "Primeiro Contato - Isabel Matos",
        )
        self.assertEqual(
            titulo_atividade_lista("**Primeiro Contato - Isabel Matos**", bruto),
            "Primeiro Contato - Isabel Matos",
        )
        longo = "A" * 100
        self.assertTrue(titulo_atividade_lista(longo).endswith("…"))
        self.assertEqual(len(titulo_atividade_lista(longo)), 91)


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

    def test_atividade_cria_e_edita_status_e_executivo(self):
        created = self.client.post(
            "/crm-v3/api/clientes/auto-shopping/atividades",
            json={
                "titulo": "Preparar reunião",
                "data": "2026-09-05",
                "status": "em_andamento",
                "executivo_id": "77",
            },
        )
        self.assertEqual(created.status_code, 201)
        atividade = created.get_json()["atividade"]
        self.assertEqual(atividade["status"], "em_andamento")
        self.assertEqual(atividade["executivo_id"], "77")

        updated = self.client.patch(
            f"/crm-v3/api/atividades/{atividade['id']}",
            json={"status": "concluida", "executivo_id": "88"},
        )
        self.assertEqual(updated.status_code, 200)
        atividade = updated.get_json()["atividade"]
        self.assertEqual(atividade["status"], "concluida")
        self.assertEqual(atividade["executivo_id"], "88")

    def test_roteiro_ia_recebe_foco_tom_e_instrucao(self):
        import aicentralv2.crm_v3_routes as routes

        captured = {}
        original_available = routes._openrouter_available
        original_call = routes._call_openrouter
        routes._openrouter_available = lambda: True

        def fake_call(system, user, **kwargs):
            captured["system"] = system
            captured["user"] = user
            return "Objetivo: preparar conversa\nRoteiro:\n- ouvir\nFechamento: combinar retorno"

        routes._call_openrouter = fake_call
        try:
            result = routes._montar_roteiro({
                "cliente_id": "auto-shopping",
                "titulo": "Reunião de descoberta",
                "tipo": "reuniao",
                "foco": "entender_necessidades",
                "tom": "consultivo",
                "instrucoes": "Antecipar objeções sobre prazo",
            })
        finally:
            routes._openrouter_available = original_available
            routes._call_openrouter = original_call

        self.assertEqual(result["source"], "openrouter")
        self.assertIn("Foco principal: Entender necessidades", captured["user"])
        self.assertIn("Tom da comunicação: Consultivo", captured["user"])
        self.assertIn("Antecipar objeções sobre prazo", captured["user"])

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


class CrmV3RepositoryUnitTest(unittest.TestCase):
    """Testes de unidade do `CrmV3Repository` com `_db()` stubado.

    Não tocam no Postgres — apenas validam mapeamento e regras de validação
    que ficam sob responsabilidade do repositório (o SQL em si é coberto
    pelas rotas do CRM legado, já testado em produção).
    """

    def setUp(self):
        from unittest.mock import MagicMock
        from aicentralv2 import crm_v3_repository as repo_mod

        self.repo_mod = repo_mod
        self.repo = repo_mod.CrmV3Repository()
        self.db = MagicMock()
        # Cliente sempre existe por padrão nos testes (validação inicial).
        self.db.obter_cliente_por_id.return_value = {"id_cliente": 1}
        self._orig_db = repo_mod._db
        repo_mod._db = lambda: self.db

    def tearDown(self):
        self.repo_mod._db = self._orig_db

    # ---- Atividades --------------------------------------------------

    def test_map_atividade_converte_data_iso(self):
        from datetime import date
        mapped = self.repo._map_atividade({
            "id": 42, "descricao": "Ligar", "data_atividade": date(2026, 9, 4),
            "status": "pendente", "titulo": "", "tipo": "ligacao",
            "responsavel_nome": "Luisa Santana",
        })
        self.assertEqual(mapped["data"], "2026-09-04")
        self.assertEqual(mapped["titulo"], "Ligar")  # fallback: descricao
        self.assertEqual(mapped["responsavel_iniciais"], "LS")

    def test_map_atividade_remove_markdown_do_titulo(self):
        mapped = self.repo._map_atividade({
            "id": 1,
            "titulo": "**Primeiro Contato - Isabel Matos**",
            "descricao": "**Entrar em contato com Isabel Matos** para apresentar a CENTRALCOMM.",
            "status": "pendente",
            "tipo": "ligacao",
            "responsavel_nome": "Apolo Lira",
            "responsavel_foto_url": "https://example.com/al.jpg",
        })
        self.assertEqual(mapped["titulo"], "Primeiro Contato - Isabel Matos")
        self.assertNotIn("**", mapped["descricao"])
        self.assertEqual(mapped["responsavel_foto_url"], "https://example.com/al.jpg")

    def test_create_atividade_valida_titulo_obrigatorio(self):
        with self.assertRaises(ValueError):
            self.repo.create_atividade("1", {"data": "2026-09-04"})

    def test_create_atividade_chama_db_com_defaults(self):
        self.db.criar_atividade_cliente.return_value = {"id": 99}
        self.db.obter_atividade_cliente_por_id.return_value = {
            "id": 99, "descricao": "Ligar", "data_atividade": "2026-09-04",
            "status": "pendente", "titulo": "Ligar",
        }
        result = self.repo.create_atividade(
            "1", {"titulo": "Ligar", "data": "2026-09-04"}
        )
        self.assertEqual(result["id"], "99")
        kwargs = self.db.criar_atividade_cliente.call_args.kwargs
        self.assertEqual(kwargs["descricao"], "Ligar")
        self.assertEqual(kwargs["data_atividade"], "2026-09-04")
        self.assertEqual(kwargs["tipo"], "atividade")
        self.assertEqual(kwargs["status"], "pendente")

    def test_create_atividade_persiste_status_e_responsavel(self):
        self.db.criar_atividade_cliente.return_value = {"id": 100}
        self.db.obter_atividade_cliente_por_id.return_value = {
            "id": 100, "descricao": "Apresentar proposta",
            "data_atividade": "2026-09-04", "status": "em_andamento",
            "titulo": "Apresentar proposta", "executivo_id": 77,
        }
        self.repo.create_atividade("1", {
            "titulo": "Apresentar proposta",
            "data": "2026-09-04",
            "status": "em_andamento",
            "executivo_id": "77",
        })
        kwargs = self.db.criar_atividade_cliente.call_args.kwargs
        self.assertEqual(kwargs["status"], "em_andamento")
        self.assertEqual(kwargs["executivo_id"], 77)

    def test_update_atividade_persiste_responsavel(self):
        self.db.atualizar_atividade_cliente.return_value = {"id": 1}
        self.db.obter_atividade_cliente_por_id.return_value = {
            "id": 1, "cliente_id": 9, "descricao": "Ligar",
            "data_atividade": "2026-09-04", "status": "pendente",
            "titulo": "Ligar", "executivo_id": 88,
        }
        self.repo.update_atividade("1", {"executivo_id": "88"})
        atividade_id, payload = self.db.atualizar_atividade_cliente.call_args.args
        self.assertEqual(atividade_id, "1")
        self.assertEqual(payload["executivo_id"], 88)

    def test_update_atividade_rejeita_status_invalido(self):
        with self.assertRaises(ValueError):
            self.repo.update_atividade("1", {"status": "wtf"})

    # ---- Objetivos ---------------------------------------------------

    def test_map_objetivo_traduz_conquistado_para_concluido(self):
        from datetime import date
        mapped = self.repo._map_objetivo({
            "id": 7, "texto": "Fechar Q3", "conquistado": True,
            "data_prazo": date(2026, 12, 31), "data_conquista": date(2026, 10, 1),
        })
        self.assertTrue(mapped["concluido"])
        self.assertEqual(mapped["prazo"], "2026-12-31")

    def test_update_objetivo_valida_concluido_boolean(self):
        # detail_before existe
        self.db.obter_objetivo_cliente_por_id.return_value = {
            "id": 1, "cliente_id": 1, "texto": "x", "conquistado": False,
        }
        with self.assertRaises(ValueError):
            self.repo.update_objetivo("1", {"concluido": "sim"})

    # ---- Cotações ----------------------------------------------------

    def test_prepare_cotacao_payload_converte_status_slug_para_label(self):
        payload = self.repo._prepare_cotacao_payload({
            "titulo": "Campanha", "status": "em-acompanhamento",
        })
        self.assertEqual(payload["status"], "Em Acompanhamento")
        self.assertEqual(payload["nome_campanha"], "Campanha")

    def test_prepare_cotacao_payload_valida_periodo_invertido(self):
        with self.assertRaises(ValueError):
            self.repo._prepare_cotacao_payload({
                "titulo": "X",
                "periodo_inicio": "2026-09-30",
                "periodo_fim": "2026-09-01",
            })

    def test_prepare_cotacao_payload_parseia_valor_brl(self):
        payload = self.repo._prepare_cotacao_payload({
            "titulo": "X", "valor": "R$ 12.500,00",
        })
        self.assertEqual(payload["valor_total_proposta"], 12500.0)

    def test_prepare_cotacao_payload_normaliza_plataformas(self):
        payload = self.repo._prepare_cotacao_payload({
            "titulo": "X", "plataformas": ["YouTube", " Meta ", ""],
        })
        self.assertEqual(payload["plataforma_campanha"], "YouTube, Meta")

    # ---- Notas (histórico append-only) -------------------------------

    def test_update_nota_e_delete_nota_sao_no_ops(self):
        self.assertEqual(self.repo.update_nota("1", {"texto": "x"}), (None, None))
        self.assertEqual(self.repo.delete_nota("1"), (False, None))

    def test_map_cliente_vinculos_usam_id_agencia_cliente(self):
        """GET /api/clientes/<id> quebrava com KeyError: 'id_cliente'.

        `listar_agencias_vinculadas_cliente` devolve `id_agencia_cliente`,
        não `id_cliente` (este último é o cliente-final, não a agência).
        """
        mapped = self.repo_mod._map_cliente({
            "id_cliente": 293,
            "nome_fantasia": "Cliente 293",
            "agencias_vinculadas": [
                {
                    "id": 9,
                    "id_agencia_cliente": 12,
                    "is_principal": True,
                    "nome_fantasia": "Agência Real",
                },
            ],
        })
        self.assertEqual(mapped["id"], "293")
        self.assertEqual(mapped["agencia_id"], "12")
        self.assertEqual(mapped["agencia_nome"], "Agência Real")
        self.assertEqual(
            mapped["agencias_vinculadas"],
            [{"agencia_id": "12", "is_principal": True, "nome": "Agência Real"}],
        )

    def test_map_cliente_nao_usa_pk_id_tbl_agencia_como_vinculo(self):
        """pk_id_tbl_agencia é lookup Sim/Não, não o id da agência-cliente.

        JOIN antigo `tbl_cliente.id_cliente = pk_id_tbl_agencia` associava
        ADALA (e outras fichas cujo id coincidia com o lookup) a clientes
        finais sem vínculo real em tbl_cliente_agencia.
        """
        mapped = self.repo_mod._map_cliente({
            "id_cliente": 400,
            "nome_fantasia": "Cliente direto",
            "pk_id_tbl_agencia": 1,
            "agencia_nome": "ADALA E ADALA NEGOCIOS IMOBILIÁRIOS",
            "agencias_vinculadas": [],
        })
        self.assertEqual(mapped["agencia_id"], "")
        self.assertEqual(mapped["agencia_nome"], "")
        self.assertEqual(mapped["agencias_vinculadas"], [])

    def test_filtrar_vinculos_colisao_lookup_ignora_adala_quando_ha_agencia_real(self):
        """id 1 no lookup Sim/Não não deve ganhar de DEZOITO no N:N."""
        vinculos = [
            {
                "id_agencia_cliente": 1,
                "is_principal": True,
                "nome_fantasia": "ADALA E ADALA NEGOCIOS IMOBILIÁRIOS",
                "agencia_key": True,
            },
            {
                "id_agencia_cliente": 88,
                "is_principal": False,
                "nome_fantasia": "DEZOITO COMUNICACAO LTDA",
                "agencia_key": True,
            },
        ]
        out = filtrar_vinculos_colisao_lookup(vinculos, {1, 2})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id_agencia_cliente"], 88)
        mapped = self.repo_mod._map_cliente({
            "id_cliente": 293,
            "nome_fantasia": "Cliente final",
            "agencias_vinculadas": out,
        })
        self.assertEqual(mapped["agencia_id"], "88")
        self.assertEqual(mapped["agencia_nome"], "DEZOITO COMUNICACAO LTDA")

    def test_filtrar_vinculos_colisao_lookup_mantem_adala_se_for_a_unica(self):
        vinculos = [{
            "id_agencia_cliente": 1,
            "is_principal": True,
            "nome_fantasia": "ADALA E ADALA NEGOCIOS IMOBILIÁRIOS",
        }]
        out = filtrar_vinculos_colisao_lookup(vinculos, {1, 2})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id_agencia_cliente"], 1)

    def test_stamp_atividade_badge_concluida_quando_nao_ha_pendente(self):
        mapped = self.repo_mod._stamp_atividade_badge({
            "metrics": {"proxima_atividade": None, "ultimo_contato": "Hoje"},
        })
        self.assertEqual(mapped["badge"], "Concluída")
        self.assertIsNone(mapped["proxima_atividade"])

    def test_stamp_atividade_badge_hoje(self):
        mapped = self.repo_mod._stamp_atividade_badge({
            "metrics": {
                "proxima_atividade": {"id": 1, "data": "2026-09-04", "titulo": "Ligar", "dias": 0},
            },
        })
        self.assertEqual(mapped["badge"], "Hoje")
        self.assertEqual(mapped["proxima_atividade"]["dias"], 0)

    def test_stamp_atividade_badge_sem_atividade(self):
        mapped = self.repo_mod._stamp_atividade_badge({"metrics": {}})
        self.assertEqual(mapped["badge"], "Sem atividade")


    def test_update_cliente_delega_para_atualizar_campos_cliente(self):
        # Mockamos `get_cliente` para não descer no `_map_cliente`
        # (que exige campos completos); só queremos verificar que o
        # PATCH parcial delega para `db.atualizar_campos_cliente` com
        # o payload correto.
        from unittest.mock import patch as _patch
        self.db.obter_cliente_por_id.return_value = {"id_cliente": 1}
        self.db.atualizar_campos_cliente.return_value = True
        with _patch.object(self.repo, "get_cliente", return_value={"id": "1"}):
            result = self.repo.update_cliente("1", {
                "cnpj": "123",
                "classificacao_cliente": "Ativo",
            })
        self.assertIsNotNone(result)
        self.db.atualizar_campos_cliente.assert_called_once_with(
            "1", {"cnpj": "123", "classificacao_cliente": "Ativo"}
        )


class CrmCepApiTest(unittest.TestCase):
    def setUp(self):
        self.app = _crm_v3_app()
        self.client = self.app.test_client()
        _login(self.client)

    def test_cep_invalido(self):
        res = self.client.get("/crm-v3/api/cep/123")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(json.loads(res.data)["success"])

    def test_cep_preenche_endereco(self):
        from unittest.mock import MagicMock, patch

        fake = MagicMock()
        fake.ok = True
        fake.json.return_value = {
            "logradouro": "Rua dos Guajajaras",
            "bairro": "Centro",
            "localidade": "Belo Horizonte",
            "uf": "mg",
        }
        with patch("requests.get", return_value=fake) as mocked:
            res = self.client.get("/crm-v3/api/cep/30120060")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["cidade"], "Belo Horizonte")
        self.assertEqual(data["data"]["uf"], "MG")
        self.assertEqual(data["data"]["bairro"], "Centro")
        mocked.assert_called_once()

    def test_cep_nao_encontrado(self):
        from unittest.mock import MagicMock, patch

        fake = MagicMock()
        fake.ok = True
        fake.json.return_value = {"erro": True}
        with patch("requests.get", return_value=fake):
            res = self.client.get("/crm-v3/api/cep/30130199")
        self.assertEqual(res.status_code, 404)
        self.assertFalse(json.loads(res.data)["success"])


if __name__ == "__main__":
    unittest.main()
