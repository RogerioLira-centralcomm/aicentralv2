"""Contratos de segurança e comportamento básico do Agente CentralX."""

import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask

from aicentralv2.agent import bp
from aicentralv2.agent.context_records import build_context_record, safe_context_url
from aicentralv2.agent.services.orchestrator import SYSTEM_POLICY, _contextual_arguments, _sanitize_markdown_links
from aicentralv2.agent.tools import commercial
from aicentralv2.agent.tools.registry import TOOLS, ToolValidationError, get_tool, validate_arguments
from aicentralv2.crm_v3_repository import StoreUnavailable
from aicentralv2.services.openrouter_service import OpenRouterError, chat_completion


class AgentContractsTest(unittest.TestCase):
    def test_assistant_links_only_allow_centralx_domain(self):
        content = (
            "[Cliente interno](/crm-v3/#cliente=237) "
            "[Cliente CentralX](https://ai.centralcomm.media/clientes/237) "
            "[Link inventado](https://example.com/clientes/237)"
        )
        sanitized = _sanitize_markdown_links(content)
        self.assertIn("[Cliente interno](/crm-v3/#cliente=237)", sanitized)
        self.assertIn("[Cliente CentralX](https://ai.centralcomm.media/clientes/237)", sanitized)
        self.assertNotIn("example.com", sanitized)
        self.assertIn("Link inventado", sanitized)

    def test_registry_rejects_unknown_and_extra_arguments(self):
        with self.assertRaises(ToolValidationError):
            get_tool("executar_sql")
        tool = get_tool("buscar_cliente")
        with self.assertRaises(ToolValidationError):
            validate_arguments(tool, {"query": "COPASA", "sql": "DELETE"})

    def test_registry_enforces_result_limit(self):
        tool = get_tool("buscar_cliente")
        with self.assertRaises(ToolValidationError):
            validate_arguments(tool, {"query": "COPASA", "limit": 21})

    def test_registry_contains_only_allowlisted_read_tools(self):
        self.assertEqual(len(TOOLS), 26)
        self.assertIn("buscar_cotacao", TOOLS)
        self.assertIn("consultar_contato", TOOLS)
        self.assertIn("consultar_atividade", TOOLS)
        self.assertIn("consultar_pi", TOOLS)
        self.assertIn("consultar_campanha", TOOLS)
        self.assertIn("listar_pis_cliente", TOOLS)
        self.assertIn("listar_campanhas_pi", TOOLS)
        self.assertIn("consultar_operacao_pi", TOOLS)
        self.assertIn("resumir_operacao", TOOLS)
        self.assertIn("listar_objetivos", TOOLS)
        self.assertIn("listar_notas_fiscais", TOOLS)
        self.assertIn("listar_reembolsos", TOOLS)
        self.assertIn("resumir_financeiro", TOOLS)
        self.assertIn("preparar_alteracao_contato", TOOLS)
        self.assertIn("listar_canais_plataformas", TOOLS)
        self.assertIn("buscar_audiencias", TOOLS)
        self.assertIn("listar_formatos", TOOLS)
        self.assertTrue(all(tool.operation_type == "read" for tool in TOOLS.values()))
        self.assertTrue(all(not tool.confirmation_required for tool in TOOLS.values()))

    def test_agent_policy_searches_instead_of_asking_for_ids(self):
        self.assertIn("Nunca peça ao usuário ID", SYSTEM_POLICY)
        self.assertIn("buscar_cotacao", SYSTEM_POLICY)
        self.assertIn("buscar_audiencias", SYSTEM_POLICY)
        self.assertIn("PARE", SYSTEM_POLICY)
        self.assertIn("ano corrente", SYSTEM_POLICY)
        self.assertIn("Não simule raciocínio interno", SYSTEM_POLICY)
        self.assertIn("prazo=hoje|semana|atrasadas", SYSTEM_POLICY)
        self.assertIn("consultar_atividade", SYSTEM_POLICY)

    def test_context_completes_agency_alias_as_cliente_id(self):
        args = _contextual_arguments(
            "listar_cotacoes", {}, {"entity_type": "agencia", "entity_id": "42"}
        )
        self.assertEqual(args["cliente_id"], "42")
        search = _contextual_arguments(
            "buscar_cliente", {"query": "INDIE"},
            {"entity_type": "cliente", "entity_id": "98", "entity_label": "INDIE"},
        )
        self.assertEqual(search["query"], "INDIE")
        self.assertNotIn("cliente_id", search)

    @patch("aicentralv2.agent.tools.commercial.db")
    def test_catalog_tools_expose_platform_audience_and_format(self, mock_db):
        mock_db.buscar_canais_plataformas.return_value = [{
            "id": 3, "nome": "DV360", "canais": "Display, Vídeo",
            "total_audiencias": 18,
        }]
        mock_db.buscar_audiencias.return_value = [{
            "id": 8, "nome": "Intenção automotiva",
            "plataforma_id": 3, "plataforma_nome": "DV360",
            "perfil_socioeconomico": "AB", "cpm_venda": 12,
        }]
        mock_db.buscar_formatos_comerciais.return_value = [{
            "nome": "Display 300x250", "tipo": "Formato", "total_usos": 9,
        }]
        self.assertEqual(
            commercial.listar_canais_plataformas()["data"][0]["title"], "DV360"
        )
        self.assertEqual(
            commercial.buscar_audiencias("automotiva")["data"][0]["platform"],
            "DV360",
        )
        self.assertEqual(
            commercial.listar_formatos()["data"][0]["usage_count"], 9
        )

    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_global_client_search_exposes_responsible_and_safe_link(self, mock_store):
        mock_store.return_value.search_clientes.return_value = [{
            "id": "1843",
            "nome": "COPASA MG",
            "tipo_label": "Cliente final",
            "responsavel": "Executiva Central",
        }]
        result = commercial.buscar_cliente("COPASA")
        item = result["display"]["items"][0]
        self.assertTrue(result["success"])
        self.assertEqual(item["responsible"], "Executiva Central")
        self.assertEqual(item["url"], "/crm-v3/#cliente=1843")
        self.assertEqual(item["entity_subtype"], "cliente_final")
        self.assertEqual(item["type_label"], "Cliente final")

    def test_parses_brazilian_currency_text(self):
        self.assertEqual(commercial._number("R$ 8.000,00"), 8000.0)
        self.assertEqual(commercial._number("3.351,35"), 3351.35)

    def test_search_focus_ignores_accents(self):
        self.assertEqual(commercial._normalized("Lápis raro"), "lapis raro")

    @patch("aicentralv2.agent.tools.commercial.PiOperacaoRepository")
    def test_client_pi_list_accepts_agency_owned_records(self, repository):
        repository.return_value.listar_pis_cliente.return_value = [{
            "id_pi": 118, "codigo_pi_cc": "83633", "titulo_pi": "CAMPANHA SEGURANÇA",
        }]
        with patch("aicentralv2.agent.tools.commercial.get_store") as mock_store:
            mock_store.return_value.get_cliente.return_value = {
                "id": "80", "nome": "LAPIS RARO", "executivo_id": "5",
            }
            result = commercial.listar_pis_cliente(
                "80", status="Em andamento", _allow_global=True
            )
        self.assertEqual(result["metadata"]["count"], 1)
        repository.return_value.listar_pis_cliente.assert_called_once()

    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_assigned_tool_search_passes_executive_filter(self, mock_store):
        mock_store.return_value.search_clientes.return_value = []
        commercial.buscar_cliente(
            "COPASA", _viewer_user_id=33, _allow_global=False
        )
        mock_store.return_value.search_clientes.assert_called_once_with(
            "COPASA", 10, executivo_id=33
        )

    def test_context_only_completes_matching_entity_type(self):
        args = _contextual_arguments(
            "listar_contatos", {}, {"entity_type": "cliente", "entity_id": "1843"}
        )
        self.assertEqual(args["cliente_id"], "1843")
        unrelated = _contextual_arguments(
            "listar_contatos", {}, {"entity_type": "cotacao", "entity_id": "98037"}
        )
        self.assertNotIn("cliente_id", unrelated)
        self.assertEqual(
            _contextual_arguments(
                "consultar_pi", {}, {"entity_type": "pi", "entity_id": "72"}
            )["pi_id"],
            "72",
        )
        self.assertEqual(
            _contextual_arguments(
                "listar_pis_cliente", {},
                {"entity_type": "cliente", "entity_id": "1843"},
            )["cliente_id"],
            "1843",
        )
        self.assertEqual(
            _contextual_arguments(
                "listar_campanhas_pi", {},
                {"entity_type": "pi", "entity_id": "72"},
            )["pi_id"],
            "72",
        )
        self.assertEqual(
            _contextual_arguments(
                "listar_atividades", {},
                {"entity_type": "cliente", "entity_id": "1843"},
            )["cliente_id"],
            "1843",
        )
        self.assertEqual(
            _contextual_arguments(
                "consultar_atividade", {},
                {"entity_type": "atividade", "entity_id": "55"},
            )["atividade_id"],
            "55",
        )

    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_search_focuses_only_one_exact_result(self, mock_store):
        mock_store.return_value.search_clientes.return_value = [{
            "id": "7", "nome": "Acme", "responsavel": "Ana"
        }]
        exact = commercial.buscar_cliente("Acme")
        partial = commercial.buscar_cliente("Acm")
        self.assertEqual(exact["context_focus"]["entity_id"], "7")
        self.assertNotIn("context_focus", partial)

    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_ambiguous_client_search_does_not_focus_and_exposes_subtype(self, mock_store):
        mock_store.return_value.search_clientes.return_value = [
            {"id": "42", "nome": "AGÊNCIA INDIE", "is_agencia": True, "tipo_label": "Agência", "responsavel": "Demétrius"},
            {"id": "98", "nome": "CLIENTE FINAL AGÊNCIA INDIE", "is_agencia": False, "tipo_label": "Cliente final", "responsavel": "Demétrius"},
        ]
        result = commercial.buscar_cliente("INDIE")
        self.assertTrue(result["ambiguous"])
        self.assertNotIn("context_focus", result)
        self.assertEqual(result["display"]["items"][0]["entity_subtype"], "agencia")
        self.assertEqual(result["display"]["items"][1]["entity_subtype"], "cliente_final")
        self.assertIn("semelhantes", result["display"]["summary"])

    @patch("aicentralv2.agent.tools.commercial.PiOperacaoRepository")
    def test_operational_summary_exposes_real_counts_and_delivery(self, repository):
        repository.return_value.resumo_operacao.return_value = {
            "pis_por_status": [{
                "status_descricao": "Em andamento",
                "total_pis": 3,
                "valor_bruto": 150000,
            }],
            "campanhas_por_status": [{
                "status_descricao": "Ativa",
                "total_campanhas": 5,
                "objetivo_contratado": 1000,
                "objetivo_atingido": 640,
                "total_gasto": 32000,
                "custo_orcado": 50000,
            }],
            "campanhas_por_plataforma": [{
                "plataforma": "DV360",
                "total_campanhas": 5,
            }],
        }
        result = commercial.resumir_operacao()
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["total_pis"], 3)
        self.assertEqual(result["data"]["total_campaigns"], 5)
        self.assertEqual(
            result["data"]["campaigns_by_status"][0]["delivery_percent"], 64.0
        )

    @patch("aicentralv2.agent.tools.commercial.PiOperacaoRepository")
    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_lists_pis_from_client_context(self, store, repository):
        store.return_value.get_cliente.return_value = {"id": "7", "nome": "Acme"}
        repository.return_value.listar_pis_cliente.return_value = [{
            "id_pi": 20,
            "titulo_pi": "PI Acme",
            "sub_status_descricao": "Em andamento",
            "vr_bruto_pi": 50000,
        }]
        result = commercial.listar_pis_cliente("7", status="Em andamento")
        self.assertEqual(result["data"][0]["type"], "pi")
        self.assertEqual(result["data"][0]["client"], "Acme")
        self.assertEqual(result["data"][0]["value"], 50000.0)

    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_open_quotes_empty_returns_structured_empty_and_skips_vinculos(self, mock_store):
        store = mock_store.return_value
        store.get_cliente.return_value = {
            "id": "42", "nome": "AGÊNCIA INDIE", "is_agencia": True, "tipo_label": "Agência",
        }
        store.list_cotacoes.return_value = [
            {"id": "1", "titulo": "Rascunho 100K", "status_label": "Rascunho", "valor_total": 0},
        ]
        store.search_clientes.return_value = [
            {"id": "42", "nome": "AGÊNCIA INDIE", "is_agencia": True},
            {"id": "98", "nome": "CLIENTE FINAL AGÊNCIA INDIE", "is_agencia": False, "tipo_label": "Cliente final"},
        ]
        result = commercial.listar_cotacoes("42", status="aberta", _allow_global=True)
        store.list_cotacoes.assert_called_with("42", include_vinculados=False)
        self.assertEqual(result["display"]["type"], "empty")
        self.assertTrue(result["display"]["empty"]["actions"])
        self.assertEqual(result["display"]["empty"]["related_candidates"][0]["id"], "98")

    @patch("aicentralv2.agent.tools.commercial.PiOperacaoRepository")
    def test_lists_campaigns_with_operational_metrics(self, repository):
        repository.return_value.obter_pi.return_value = {
            "id_pi": 20, "cliente_nome": "Acme"
        }
        repository.return_value.listar_campanhas.return_value = [{
            "id_campanha": 30,
            "id_pi": 20,
            "nome_campanha": "Always on",
            "obj_contratados": 1000,
            "totalizador_atingido": 750,
            "totalizador_gasto": 30000,
            "custo_midia_orcado": 40000,
        }]
        result = commercial.listar_campanhas_pi("20")
        self.assertEqual(result["data"][0]["type"], "campanha")
        self.assertEqual(result["data"][0]["delivery_percent"], 75.0)
        self.assertEqual(result["data"][0]["spent"], 30000.0)

    @patch("aicentralv2.agent.tools.commercial.PiOperacaoService")
    def test_operational_pi_exposes_sla_checklist_and_health(self, service):
        service.return_value.estado_completo.return_value = {
            "pi": {"id_pi": 20, "titulo_pi": "PI Acme"},
            "resumo": {"total_campanhas": 2},
            "sla": {"status": "no_prazo"},
            "saude": {"status": "atencao"},
            "timeline": [{"codigo": "campanha_iniciada", "concluida": True}],
            "checklist_operacional": {
                "progresso": {"concluidos": 4, "total": 10, "percentual": 40}
            },
            "recomendacoes": [{"titulo": "Validar criativos"}],
        }
        result = commercial.consultar_operacao_pi("20")
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["summary"]["total_campanhas"], 2.0)
        self.assertEqual(
            result["data"]["operational_checklist"]["progresso"]["percentual"],
            40.0,
        )
        self.assertEqual(result["context_focus"]["entity_type"], "pi")

    @patch.dict("os.environ", {}, clear=True)
    def test_openrouter_key_is_resolved_lazily(self):
        with self.assertRaises(OpenRouterError):
            chat_completion([{"role": "user", "content": "teste"}])

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @patch("aicentralv2.services.openrouter_service.requests.post")
    def test_openrouter_uses_operational_generation_settings(self, mock_post):
        response = MagicMock()
        response.json.return_value = {
            "model": "openai/gpt-4o-mini",
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        }
        mock_post.return_value = response
        chat_completion(
            [{"role": "user", "content": "teste"}],
            tools=[{"type": "function", "function": {"name": "buscar_cliente"}}],
        )
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "openai/gpt-4o-mini")
        self.assertEqual(payload["temperature"], 0.15)
        self.assertEqual(payload["top_p"], 0.9)
        self.assertEqual(payload["top_k"], 40)
        self.assertFalse(payload["parallel_tool_calls"])

    def test_dates_and_quote_codes_use_brazilian_format(self):
        from aicentralv2.agent.presenters import document_hints, format_date_br, format_period_br
        self.assertEqual(format_date_br("2026-08-21"), "21/08/2026")
        self.assertEqual(format_period_br("2026-08-21", "2027-02-20"), "21/08/2026 — 20/02/2027")
        self.assertEqual(format_date_br("2026-09-10T09:42:00"), "10/09/2026 às 09:42")
        hints = document_hints("PI_036826.pdf COT-202608-3867DA", [{"name": "PI_036826.pdf"}])
        self.assertIn("36826", hints["pis"])
        self.assertIn("COT-202608-3867DA", hints["quotes"])

    @patch("aicentralv2.agent.tools.commercial.PiOperacaoRepository")
    def test_buscar_pi_uses_exact_number_before_search(self, repository):
        repository.return_value.obter_pi_por_numero.return_value = {
            "id_pi": 36826,
            "titulo_pi": "App Behavior — Conta Premiada",
            "codigo_pi_cc": "036826",
            "sub_status_descricao": "Em andamento",
            "cliente_nome": "COPASA MG",
            "vr_liquido_pi": "33600",
            "periodo_inicio": "2026-08-13",
            "responsavel_comercial_nome": "Luisa Santana",
            "responsavel_comercial_foto_url": "/static/fotos/luisa.jpg",
        }
        result = commercial.buscar_pi("PI 36826")
        repository.return_value.buscar_pis.assert_not_called()
        self.assertEqual(result["display"]["type"], "pi_summary")
        self.assertEqual(result["display"]["summary"], "Encontrei o PI.")
        self.assertEqual(result["display"]["items"][0]["start"], "13/08/2026")

    @patch("aicentralv2.agent.tools.commercial.PiOperacaoRepository")
    def test_resumir_operacao_defaults_to_current_year_status_summary(self, repository):
        repository.return_value.resumo_operacao.return_value = {
            "pis_por_status": [{"status_descricao": "Finalizado", "total_pis": 113, "valor_bruto": 1}],
            "campanhas_por_status": [],
            "campanhas_por_plataforma": [],
        }
        result = commercial.resumir_operacao(escopo="pis")
        self.assertEqual(result["display"]["type"], "status_summary")
        self.assertIn("Período", result["display"]["period"]["label"])
        self.assertTrue(result["display"]["period"]["value"])
        labels = [item["label"] for item in result["display"]["actions"]]
        self.assertNotIn("Finalizado", labels)

    @patch("aicentralv2.db.listar_itens_especificos_cotacao")
    @patch("aicentralv2.db.obter_audiencias_cotacao")
    @patch("aicentralv2.db.obter_linhas_cotacao")
    @patch("aicentralv2.db.calcular_totais_financeiros_cotacao")
    def test_quote_context_exposes_kind_values_and_disclosures(
        self, mock_totals, mock_linhas, mock_aud, mock_extras
    ):
        mock_linhas.return_value = [{
            "id": 1, "plataforma": "Meta Ads", "formato": "Performance",
            "objetivo_kpi": "CPC", "valor_unitario_negociado": 1.82,
            "volume_contratado": 65000, "investimento_liquido": 45000,
            "investimento_bruto": 56250, "custo_midia": 28000,
            "val_tech_fee": 1400, "val_com_vendas": 2240,
        }]
        mock_aud.return_value = []
        mock_extras.return_value = []
        mock_totals.return_value = {
            "valor_liquido": 120000, "valor_bruto": 150000, "total_custo_midia": 91500,
        }
        store = MagicMock()
        quote = {
            "id": "91",
            "titulo": "AG. INDIE IMOBILIÁRIO 150K",
            "numero_cotacao": "COT-202608-3867DA",
            "cliente_id": "7",
            "agencia_id": "",
            "status_label": "Rascunho",
            "tipo_comercial": "midia",
            "tipo_comercial_label": "Mídia",
            "periodo_inicio": "2026-08-21",
            "periodo_fim": "2027-02-20",
            "objetivo": "Alcance",
            "plataformas": ["Meta Ads", "YouTube"],
        }
        store.get_cotacao.return_value = quote
        store.get_cliente.return_value = {"id": "7", "nome": "CLIENTE FINAL AGÊNCIA INDIE"}
        pi_repo = MagicMock()
        pi_repo.listar_pis_cliente.return_value = []
        payload = build_context_record(
            "cotacao", "91", store, lambda *_: True, lambda *_: True, pi_repo
        )
        facts = {item["label"]: item["value"] for item in payload["facts"]}
        self.assertEqual(payload["identity"]["kind"], "Mídia")
        self.assertEqual(payload["identity"]["code"], "COT-202608-3867DA")
        self.assertEqual(facts["Período"], "21/08/2026 — 20/02/2027")
        self.assertIn("R$ 150.000,00", facts["Valor bruto"])
        self.assertIn("R$ 120.000,00", facts["Valor líquido"])
        self.assertEqual(payload["platforms"], ["Meta Ads", "YouTube"])
        self.assertEqual(payload["quote_items"][0]["title"], "Meta Ads")
        self.assertTrue(payload["price_breakdown"])
        labels = [item["label"] for item in payload["actions"]]
        self.assertIn("Abrir cotação", labels)
        self.assertIn("Preparar follow-up", labels)
        self.assertNotIn("Copiar link", labels)
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(SECRET_KEY="agent-test", TESTING=True)
        self.app.register_blueprint(bp)
        self.client = self.app.test_client()

    def test_requires_session(self):
        response = self.client.get("/api/agent/bootstrap")
        self.assertEqual(response.status_code, 401)

    def test_denies_external_user(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["is_centralcomm"] = False
        response = self.client.get("/api/agent/bootstrap")
        self.assertEqual(response.status_code, 403)

    def test_post_requires_agent_csrf(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["is_centralcomm"] = True
        response = self.client.post("/api/agent/conversations", json={"context": {}})
        self.assertEqual(response.status_code, 403)

    @patch("aicentralv2.agent.routes.db.obter_usuario_por_id")
    @patch("aicentralv2.agent.routes.storage.list_conversations", return_value=[])
    def test_internal_bootstrap_returns_capability_and_token(self, _mock_list, mock_user):
        mock_user.return_value = {
            "nome_completo": "Teste",
            "foto_url": "/static/uploads/contatos/teste.jpg",
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["user_name"] = "Teste"
            session["is_centralcomm"] = True
        response = self.client.get("/api/agent/bootstrap?module=crm&screen=clientes")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertIn("commercial.read.assigned", data["capabilities"])
        self.assertIn("commercial.read.global", data["capabilities"])
        self.assertNotIn("commercial.write.global", data["capabilities"])
        self.assertTrue(data["csrf_token"])
        self.assertEqual(data["user"]["photo_url"], "/static/uploads/contatos/teste.jpg")

    @patch("aicentralv2.agent.routes.db.obter_usuario_por_id", return_value={})
    @patch("aicentralv2.agent.routes.storage.list_conversations", return_value=[])
    def test_admin_bootstrap_includes_global_commercial_access(self, _mock_list, _mock_user):
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["is_centralcomm"] = True
            session["user_type"] = "admin"
        data = self.client.get("/api/agent/bootstrap").get_json()["data"]
        self.assertIn("commercial.read.global", data["capabilities"])
        self.assertIn("commercial.write.global", data["capabilities"])

    @patch("aicentralv2.agent.routes.db.buscar_audiencias", return_value=[])
    @patch("aicentralv2.agent.routes.db.buscar_canais_plataformas", return_value=[])
    @patch("aicentralv2.agent.routes.search_operational_records", return_value={"pis": [], "campaigns": []})
    @patch("aicentralv2.agent.routes.get_store")
    def test_commercial_search_all_is_available_to_regular_user(
        self, mock_store, _mock_ops, _mock_channels, _mock_audiences
    ):
        mock_store.return_value.search_clientes.return_value = []
        mock_store.return_value.search_cotacoes.return_value = []
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="client")
        response = self.client.get("/api/agent/commercial/search?q=acme&scope=all")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["scope"], "all")
        mock_store.return_value.search_clientes.assert_called_once_with(
            "acme", 8, executivo_id=None
        )
        mock_store.return_value.search_cotacoes.assert_called_once_with(
            "acme", 8, executivo_id=None
        )

    @patch("aicentralv2.agent.routes.db.buscar_audiencias", return_value=[])
    @patch("aicentralv2.agent.routes.db.buscar_canais_plataformas", return_value=[])
    @patch("aicentralv2.agent.routes.search_operational_records", return_value={"pis": [], "campaigns": []})
    @patch("aicentralv2.agent.routes.get_store")
    def test_commercial_search_mine_still_filters_regular_user(
        self, mock_store, _mock_ops, _mock_channels, _mock_audiences
    ):
        mock_store.return_value.search_clientes.return_value = []
        mock_store.return_value.search_cotacoes.return_value = []
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="client")
        response = self.client.get("/api/agent/commercial/search?q=acme&scope=mine")
        self.assertEqual(response.get_json()["data"]["scope"], "mine")
        mock_store.return_value.search_clientes.assert_called_once_with(
            "acme", 8, executivo_id=10
        )

    @patch("aicentralv2.agent.routes.db.buscar_audiencias", return_value=[])
    @patch("aicentralv2.agent.routes.db.buscar_canais_plataformas", return_value=[])
    @patch("aicentralv2.agent.routes.search_operational_records", return_value={"pis": [], "campaigns": []})
    @patch("aicentralv2.agent.routes.get_store")
    def test_commercial_search_all_is_available_to_admin(
        self, mock_store, _mock_ops, _mock_channels, _mock_audiences
    ):
        mock_store.return_value.search_clientes.return_value = []
        mock_store.return_value.search_cotacoes.return_value = []
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="admin")
        response = self.client.get("/api/agent/commercial/search?q=acme&scope=all")
        self.assertEqual(response.get_json()["data"]["scope"], "all")
        mock_store.return_value.search_clientes.assert_called_once_with(
            "acme", 8, executivo_id=None
        )

    @patch("aicentralv2.agent.routes.storage.rollback_failed_transaction")
    @patch("aicentralv2.agent.routes.db.obter_usuario_por_id", return_value={})
    @patch("aicentralv2.agent.routes.get_store")
    @patch("aicentralv2.agent.routes.storage.list_conversations", side_effect=RuntimeError("db down"))
    def test_bootstrap_stays_online_when_history_fails(self, _mock_list, mock_store, _mock_user, _rollback):
        mock_store.side_effect = StoreUnavailable("crm down")
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="client")
        response = self.client.get(
            "/api/agent/bootstrap?module=crm&screen=cliente&entity_type=cliente&entity_id=7"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertTrue(data["csrf_token"])
        self.assertIsNone(data["active_conversation"])
        self.assertEqual(data["insights"]["entity"], None)

    @patch("aicentralv2.agent.routes.db.buscar_audiencias", return_value=[])
    @patch("aicentralv2.agent.routes.db.buscar_canais_plataformas", return_value=[])
    @patch("aicentralv2.agent.routes.storage.rollback_failed_transaction")
    @patch("aicentralv2.agent.routes.search_operational_records", return_value={"pis": [{"id": "1"}], "campaigns": []})
    @patch("aicentralv2.agent.routes.get_store")
    def test_commercial_search_returns_partial_results_when_crm_fails(
        self, mock_store, _mock_ops, _rollback, _mock_channels, _mock_audiences
    ):
        store = mock_store.return_value
        store.search_clientes.side_effect = RuntimeError("unaccent missing")
        store.search_cotacoes.return_value = []
        store.search_contatos.return_value = []
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="admin")
        response = self.client.get("/api/agent/commercial/search?q=acme&scope=all")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["data"]
        self.assertEqual(payload["clients"], [])
        self.assertEqual(payload["pis"][0]["id"], "1")
        self.assertEqual(payload["channels"], [])
        self.assertEqual(payload["audiences"], [])

    @patch("aicentralv2.agent.routes.db.buscar_audiencias", return_value=[
        {"id": 8, "nome": "Intenção automotiva", "plataforma_nome": "DV360", "perfil_socioeconomico": "AB"},
    ])
    @patch("aicentralv2.agent.routes.db.buscar_canais_plataformas", return_value=[
        {"id": 3, "nome": "DV360", "canais": "Display", "total_audiencias": 18},
    ])
    @patch("aicentralv2.agent.routes.search_operational_records", return_value={"pis": [], "campaigns": []})
    @patch("aicentralv2.agent.routes.get_store")
    def test_commercial_search_includes_channels_and_audiences(
        self, mock_store, _mock_ops, _mock_channels, _mock_audiences
    ):
        mock_store.return_value.search_clientes.return_value = []
        mock_store.return_value.search_cotacoes.return_value = []
        mock_store.return_value.search_contatos.return_value = []
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="admin")
        payload = self.client.get("/api/agent/commercial/search?q=dv360&scope=all").get_json()["data"]
        self.assertEqual(payload["channels"][0]["nome"], "DV360")
        self.assertEqual(payload["audiences"][0]["nome"], "Intenção automotiva")

    @patch("aicentralv2.agent.routes.db.buscar_audiencias", return_value=[])
    @patch("aicentralv2.agent.routes.db.buscar_canais_plataformas", return_value=[])
    @patch("aicentralv2.agent.routes.storage.rollback_failed_transaction")
    @patch("aicentralv2.agent.routes.search_operational_records", return_value={"pis": [], "campaigns": []})
    @patch("aicentralv2.agent.routes.get_store", side_effect=StoreUnavailable("crm down"))
    def test_commercial_search_survives_store_unavailable(
        self, _mock_store, _mock_ops, _rollback, _mock_channels, _mock_audiences
    ):
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="admin")
        response = self.client.get("/api/agent/commercial/search?q=acme&scope=all")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["data"]
        self.assertEqual(payload["clients"], [])
        self.assertEqual(payload["quotes"], [])

    @patch("aicentralv2.agent.tools.commercial.storage.rollback_failed_transaction")
    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_client_search_query_failure_is_not_empty_success(self, mock_store, _rollback):
        mock_store.return_value.search_clientes.side_effect = RuntimeError("sql")
        result = commercial.buscar_cliente("COPASA")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "query_failed")

    @patch("aicentralv2.agent.routes.build_insights")
    @patch("aicentralv2.agent.routes.get_store")
    def test_client_update_requires_owner_and_csrf(self, mock_store, mock_insights):
        store = mock_store.return_value
        store.get_cliente.return_value = {
            "id": "7", "nome": "Acme", "executivo_id": "10"
        }
        store.update_cliente.return_value = {
            "id": "7", "nome": "Acme Nova", "executivo_id": "10"
        }
        store.list_contatos.return_value = []
        store.list_atividades.return_value = []
        store.list_cotacoes.return_value = []
        mock_insights.return_value = {"entity": None, "alerts": [], "prompts": []}
        with self.client.session_transaction() as session:
            session.update(
                user_id=10,
                is_centralcomm=True,
                user_type="client",
                agent_csrf_token="token",
            )
        denied = self.client.patch(
            "/api/agent/commercial/clients/7", json={"nome": "Acme Nova"}
        )
        self.assertEqual(denied.status_code, 403)
        updated = self.client.patch(
            "/api/agent/commercial/clients/7",
            json={"nome": "Acme Nova", "campo_perigoso": "ignorado"},
            headers={"X-Agent-CSRF-Token": "token"},
        )
        self.assertEqual(updated.status_code, 200)
        store.update_cliente.assert_called_once_with("7", {"nome": "Acme Nova"})

    @patch("aicentralv2.agent.routes.PiOperacaoRepository")
    @patch("aicentralv2.agent.routes.get_store")
    def test_regular_user_can_read_unassigned_client_but_cannot_edit(self, mock_store, mock_pi):
        store = mock_store.return_value
        store.get_cliente.return_value = {
            "id": "7", "nome": "Acme", "executivo_id": "99"
        }
        store.list_contatos.return_value = []
        store.list_atividades.return_value = []
        store.list_cotacoes.return_value = []
        mock_pi.return_value.listar_pis_cliente.return_value = []
        with self.client.session_transaction() as session:
            session.update(
                user_id=10,
                is_centralcomm=True,
                user_type="client",
                agent_csrf_token="token",
            )
        opened = self.client.get("/api/agent/commercial/record/cliente/7")
        self.assertEqual(opened.status_code, 200)
        denied = self.client.patch(
            "/api/agent/commercial/clients/7",
            json={"nome": "Acme Nova"},
            headers={"X-Agent-CSRF-Token": "token"},
        )
        self.assertEqual(denied.status_code, 404)

    @patch("aicentralv2.agent.routes.PiOperacaoRepository")
    @patch("aicentralv2.agent.routes.get_store")
    def test_quote_record_returns_client_and_detail_url(self, mock_store, mock_pi_repo):
        store = mock_store.return_value
        store.get_cotacao.return_value = {
            "id": "91",
            "titulo": "Campanha",
            "cliente_id": "7",
            "executivo_id": "10",
        }
        store.get_cliente.return_value = {"id": "7", "nome": "Acme"}
        mock_pi_repo.return_value.listar_pis_cliente.return_value = []
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="client")
        response = self.client.get("/api/agent/commercial/record/cotacao/91")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["client"]["nome"], "Acme")
        self.assertEqual(data["url"], "/cotacoes/91/detalhes")

    @patch("aicentralv2.agent.routes.get_store")
    def test_contact_change_requires_confirmation_and_csrf(self, mock_store):
        store = mock_store.return_value
        store.get_contato.return_value = {
            "id": "15", "cliente_id": "7", "nome": "Ana", "email": "ana@acme.com"
        }
        store.get_cliente.return_value = {
            "id": "7", "nome": "Acme", "executivo_id": "10"
        }
        store.update_contato.return_value = (
            {
                "id": "15", "cliente_id": "7", "nome": "Ana",
                "email": "ana@acme.com", "telefone": "(31) 99999-0000",
            },
            "7",
        )
        with self.client.session_transaction() as session:
            session.update(
                user_id=10, is_centralcomm=True, user_type="client",
                agent_csrf_token="token",
            )
        denied = self.client.post(
            "/api/agent/context/contact-changes",
            json={"confirmed": False, "operation": "update_contact"},
            headers={"X-Agent-CSRF-Token": "token"},
        )
        self.assertEqual(denied.status_code, 400)
        updated = self.client.post(
            "/api/agent/context/contact-changes",
            json={
                "confirmed": True,
                "operation": "update_contact",
                "contato_id": "15",
                "changes": {
                    "nome": "Ana",
                    "telefone": "(31) 99999-0000",
                    "campo_perigoso": "ignorado",
                },
            },
            headers={"X-Agent-CSRF-Token": "token"},
        )
        self.assertEqual(updated.status_code, 200)
        sent = store.update_contato.call_args.args[1]
        self.assertNotIn("campo_perigoso", sent)
        self.assertEqual(sent["telefone"], "(31) 99999-0000")

    @patch("aicentralv2.agent.routes.build_insights")
    @patch("aicentralv2.agent.routes.storage.list_conversations", return_value=[])
    def test_insights_endpoint_requires_internal_user(self, _mock_list, mock_insights):
        mock_insights.return_value = {"entity": None, "alerts": [], "prompts": []}
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["is_centralcomm"] = True
        response = self.client.get("/api/agent/insights")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["alerts"], [])


class AgentInsightsTest(unittest.TestCase):
    def test_insights_without_entity_have_prompts_only(self):
        from aicentralv2.agent.insights import build_insights
        data = build_insights({})
        self.assertIsNone(data["entity"])
        self.assertEqual(data["alerts"], [])
        self.assertTrue(data["prompts"])
        labels = {item["label"] for item in data["prompts"]}
        self.assertIn("Buscar cliente", labels)
        self.assertIn("Buscar agência", labels)

    @patch("aicentralv2.agent.insights.get_store")
    def test_insights_for_client_include_overdue_and_open_quotes(self, mock_store):
        from aicentralv2.agent.insights import build_insights
        store = mock_store.return_value
        store.get_cliente.return_value = {"id": "1843", "nome": "COPASA MG"}
        store.list_atividades.return_value = [
            {"status": "pendente", "data_prazo": "2020-01-01", "titulo": "Follow-up"},
        ]
        store.list_cotacoes.return_value = [
            {"status": "enviada", "status_label": "Enviada", "titulo": "Campanha", "data": "01/01/2026"},
        ]
        data = build_insights({"entity_type": "cliente", "entity_id": "1843", "entity_label": "COPASA MG"})
        self.assertEqual(data["entity"]["label"], "COPASA MG")
        ids = {item["id"] for item in data["alerts"]}
        self.assertIn("overdue_activities", ids)
        self.assertIn("open_campaigns", ids)

    def test_agency_suggestions_differ_from_final_client(self):
        from aicentralv2.agent.insights import suggestion_prompts
        agency = {item["label"] for item in suggestion_prompts({
            "entity_type": "cliente", "entity_id": "42", "entity_subtype": "agencia",
        })}
        client = {item["label"] for item in suggestion_prompts({
            "entity_type": "cliente", "entity_id": "98", "entity_subtype": "cliente_final",
        })}
        self.assertIn("Clientes finais", agency)
        self.assertIn("Cotações abertas", client)
        self.assertNotIn("Buscar cliente", agency)
        self.assertNotIn("Buscar um PI", client)

    @patch("aicentralv2.agent.insights.get_store")
    def test_quote_insights_recommend_follow_up(self, mock_store):
        from aicentralv2.agent.insights import build_insights
        mock_store.return_value.get_cotacao.return_value = {
            "id": "91",
            "titulo": "Campanha",
            "status_label": "Enviada",
            "objetivo": "Conversão",
        }
        data = build_insights({
            "entity_type": "cotacao",
            "entity_id": "91",
            "entity_label": "Campanha",
        })
        self.assertEqual(data["entity"]["type"], "cotacao")
        self.assertIn("quote_follow_up", {item["id"] for item in data["alerts"]})


class AgentActivityContractTest(unittest.TestCase):
    def test_activity_due_buckets(self):
        from aicentralv2.agent.presenters import activity_due_bucket
        today = date(2026, 9, 10)
        self.assertEqual(activity_due_bucket({"data_prazo": "2026-09-10"}, today), "hoje")
        self.assertEqual(activity_due_bucket({"data_prazo": "2026-09-11"}, today), "semana")
        self.assertEqual(activity_due_bucket({"data_prazo": "2026-09-17"}, today), "semana")
        self.assertEqual(activity_due_bucket({"data_prazo": "2026-09-18"}, today), "")
        self.assertEqual(activity_due_bucket({"data_prazo": "2026-09-09"}, today), "atrasadas")
        self.assertEqual(activity_due_bucket({"data": "2026-09-10"}, today), "hoje")

    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_listar_atividades_hoje_isolates_due_today(self, mock_store):
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        store = mock_store.return_value
        store.get_cliente.return_value = {"id": "7", "nome": "Acme", "executivo_id": "33"}
        store.list_atividades.return_value = [
            {"id": "1", "titulo": "Hoje", "status": "pendente", "data_prazo": today, "cliente_id": "7"},
            {"id": "2", "titulo": "Amanhã", "status": "pendente", "data_prazo": tomorrow, "cliente_id": "7"},
            {"id": "3", "titulo": "Atrasada", "status": "pendente", "data_prazo": "2020-01-01", "cliente_id": "7"},
        ]
        result = commercial.listar_atividades(
            cliente_id="7", prazo="hoje", _viewer_user_id=33
        )
        self.assertEqual([item["id"] for item in result["display"]["items"]], ["1"])
        self.assertEqual(result["display"]["type"], "activity_list")

    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_listar_atividades_without_prazo_returns_counts_only(self, mock_store):
        today = date.today().isoformat()
        store = mock_store.return_value
        store.list_atividades_responsavel.return_value = [
            {"id": "1", "titulo": "Hoje", "status": "pendente", "data_prazo": today},
            {"id": "2", "titulo": "Atrasada", "status": "pendente", "data_prazo": "2020-01-01"},
        ]
        result = commercial.listar_atividades(_viewer_user_id=33)
        self.assertEqual(result["display"]["type"], "status_summary")
        labels = {item["label"]: item["count"] for item in result["display"]["groups"][0]["items"]}
        self.assertEqual(labels["Hoje"], 1)
        self.assertEqual(labels["Atrasadas"], 1)
        self.assertIn("Hoje 1", result["display"]["summary"])
        store.list_atividades_responsavel.assert_called_once_with(executivo_id=33)


class ContextRecordContractTest(unittest.TestCase):
    def setUp(self):
        self.store = MagicMock()
        self.pi_repo = MagicMock()
        self.allow = lambda _record: True

    def test_client_context_distinguishes_operational_stage_and_relations(self):
        self.store.get_cliente.return_value = {
            "id": "7", "nome": "Acme", "responsavel": "Ana"
        }
        self.store.list_contatos.return_value = [{
            "id": "15", "nome": "Bruno", "cargo": "Mídia",
            "telefone": "(31) 99999-0000", "email": "bruno@acme.com",
        }]
        self.store.list_cotacoes.return_value = [{"id": "9", "titulo": "Plano 2026"}]
        self.pi_repo.listar_pis_cliente.return_value = [{
            "id_pi": 20, "titulo_pi": "PI Acme"
        }]
        self.pi_repo.listar_campanhas.return_value = [{
            "id_campanha": 30, "nome_campanha": "Always on"
        }]
        data = build_context_record(
            "cliente", "7", self.store, self.allow, self.allow, self.pi_repo
        )
        facts = {item["label"]: item["value"] for item in data["facts"]}
        keys = {item["key"] for item in data["relations"]}
        self.assertEqual(facts["Etapa"], "Em operação")
        self.assertTrue({"contacts", "quotes", "pis", "campaigns", "activities"}.issubset(keys))
        self.assertEqual(data["identity"]["type_label"], "Cliente final")
        contacts = next(item for item in data["relations"] if item["key"] == "contacts")
        self.assertEqual(contacts["items"][0]["phone"], "(31) 99999-0000")
        self.assertIn("Mídia", contacts["items"][0]["subtitle"])

    def test_contact_context_omits_empty_facts(self):
        self.store.get_contato.return_value = {
            "id": "15", "cliente_id": "7", "nome": "Bruno",
            "cargo": "Mídia", "telefone": "", "email": "bruno@acme.com",
        }
        self.store.get_cliente.return_value = {"id": "7", "nome": "Acme"}
        data = build_context_record(
            "contato", "15", self.store, self.allow, self.allow, self.pi_repo
        )
        labels = {item["label"] for item in data["facts"]}
        self.assertIn("Cargo", labels)
        self.assertIn("E-mail", labels)
        self.assertNotIn("Telefone", labels)

    def test_activity_context_includes_copyable_history(self):
        self.store.get_atividade.return_value = {
            "id": "55",
            "titulo": "Follow-up Copasa",
            "status": "pendente",
            "tipo": "ligacao",
            "data": "2026-09-08",
            "data_prazo": "2026-09-10",
            "cliente_id": "7",
            "cliente_nome": "Acme",
            "responsavel": "Ana",
            "responsavel_foto_url": "/static/ana.jpg",
            "contato_nome": "Bruno",
        }
        self.store.get_cliente.return_value = {"id": "7", "nome": "Acme", "is_agencia": False}
        self.store.get_cotacao.return_value = None
        self.store.list_ai_history.return_value = [{
            "id": "9",
            "function": "gerar-comunicacao",
            "content": {"assunto": "Reunião", "mensagem": "Olá, Bruno"},
            "created_at": "2026-09-09",
        }]
        data = build_context_record(
            "atividade", "55", self.store, self.allow, self.allow, self.pi_repo
        )
        facts = {item["label"]: item["value"] for item in data["facts"]}
        self.assertEqual(data["type"], "atividade")
        self.assertEqual(data["identity"]["type_label"], "Atividade")
        self.assertEqual(facts["Prazo"], "10/09/2026")
        self.assertEqual(facts["Contato"], "Bruno")
        self.assertEqual(data["history"][0]["subject"], "Reunião")
        self.assertEqual(data["history"][0]["message"], "Olá, Bruno")
        self.assertTrue(any(item["kind"] == "open" for item in data["actions"]))
        self.store.list_ai_history.assert_called_once_with(
            "7", limit=20, atividade_id="55"
        )

    def test_external_context_url_rejects_unsafe_protocols_and_credentials(self):
        self.assertEqual(safe_context_url("javascript:alert(1)", True), "")
        self.assertEqual(safe_context_url("https://user:pass@example.com", True), "")
        self.assertEqual(
            safe_context_url("https://dashboard.example.com/campanha/7", True),
            "https://dashboard.example.com/campanha/7",
        )


class AgentWorkspaceContractTest(unittest.TestCase):
    def test_workspace_contains_search_record_and_sync_contracts(self):
        root = Path(__file__).resolve().parents[1]
        shell = (root / "aicentralv2/templates/agent/shell.html").read_text()
        agent_js = (root / "aicentralv2/static/js/agent/agent.js").read_text()
        crm_js = (root / "aicentralv2/static/js/crm_v3.js").read_text()
        self.assertIn("cx-agent-commercial-query", shell)
        self.assertIn("cx-agent-record-body", shell)
        self.assertIn("centralx:entity-updated", agent_js)
        self.assertIn("centralx:entity-updated", crm_js)
        self.assertIn("/api/agent/context/", agent_js)
        self.assertIn("dock.dataset.contextWall", agent_js)
        self.assertIn("mailto:", agent_js)
        self.assertIn("data-contact-confirm", agent_js)
        self.assertIn("cx-agent-more-menu", shell)
        self.assertIn("cx-agent-composer-suggestions", shell)
        self.assertNotIn("data-agent-tab=\"actions\"", shell)
        self.assertIn("appendMessage('assistant', String(content || ''), display)", agent_js)
        self.assertIn("cx-agent-message-cards", agent_js)
        self.assertNotIn("renderDisplay(body, display);", agent_js)
        self.assertNotIn("Ver contexto", agent_js)
        self.assertIn("cx-agent-entity-row", agent_js)
        self.assertIn("Usar como contexto", agent_js)
        self.assertIn("cx-agent-consulting", shell)
        self.assertIn("cx-agent-clear-conversation", shell)
        self.assertIn("cx-agent-media-dialog", shell)
        self.assertIn("Consultando cotação", agent_js)
        self.assertNotIn("cx-agent-thinking", agent_js)
        self.assertIn("quote_summary", agent_js)
        self.assertIn("data-open-drive", agent_js)
        self.assertNotIn("['atividade', 'canal', 'audiencia']", agent_js)
        self.assertIn("Abrir atividade", agent_js)
        self.assertIn("renderActivityHistory", agent_js)
        self.assertIn("Consultando atividades", agent_js)
        self.assertIn("activity_summary", agent_js)


if __name__ == "__main__":
    unittest.main()
