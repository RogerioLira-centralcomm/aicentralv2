"""Contratos de segurança e comportamento básico do Agente CentralX."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask

from aicentralv2.agent import bp
from aicentralv2.agent.context_records import build_context_record, safe_context_url
from aicentralv2.agent.services.orchestrator import _contextual_arguments
from aicentralv2.agent.tools import commercial
from aicentralv2.agent.tools.registry import TOOLS, ToolValidationError, get_tool, validate_arguments
from aicentralv2.services.openrouter_service import OpenRouterError, chat_completion


class AgentContractsTest(unittest.TestCase):
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
        self.assertEqual(len(TOOLS), 13)
        self.assertIn("consultar_contato", TOOLS)
        self.assertIn("consultar_pi", TOOLS)
        self.assertIn("consultar_campanha", TOOLS)
        self.assertIn("preparar_alteracao_contato", TOOLS)
        self.assertTrue(all(tool.operation_type == "read" for tool in TOOLS.values()))
        self.assertTrue(all(not tool.confirmation_required for tool in TOOLS.values()))

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

    @patch("aicentralv2.agent.tools.commercial.get_store")
    def test_search_focuses_only_one_exact_result(self, mock_store):
        mock_store.return_value.search_clientes.return_value = [{
            "id": "7", "nome": "Acme", "responsavel": "Ana"
        }]
        exact = commercial.buscar_cliente("Acme")
        partial = commercial.buscar_cliente("Acm")
        self.assertEqual(exact["context_focus"]["entity_id"], "7")
        self.assertNotIn("context_focus", partial)

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


class AgentApiSecurityTest(unittest.TestCase):
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

    @patch("aicentralv2.agent.routes.storage.list_conversations", return_value=[])
    def test_internal_bootstrap_returns_capability_and_token(self, _mock_list):
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["user_name"] = "Teste"
            session["is_centralcomm"] = True
        response = self.client.get("/api/agent/bootstrap?module=crm&screen=clientes")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertIn("commercial.read.assigned", data["capabilities"])
        self.assertNotIn("commercial.read.global", data["capabilities"])
        self.assertTrue(data["csrf_token"])

    @patch("aicentralv2.agent.routes.storage.list_conversations", return_value=[])
    def test_admin_bootstrap_includes_global_commercial_access(self, _mock_list):
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["is_centralcomm"] = True
            session["user_type"] = "admin"
        data = self.client.get("/api/agent/bootstrap").get_json()["data"]
        self.assertIn("commercial.read.global", data["capabilities"])
        self.assertIn("commercial.write.global", data["capabilities"])

    @patch("aicentralv2.agent.routes.search_operational_records", return_value={"pis": [], "campaigns": []})
    @patch("aicentralv2.agent.routes.get_store")
    def test_commercial_search_forces_assigned_scope_for_regular_user(self, mock_store, _mock_ops):
        mock_store.return_value.search_clientes.return_value = []
        mock_store.return_value.search_cotacoes.return_value = []
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="client")
        response = self.client.get("/api/agent/commercial/search?q=acme&scope=all")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["scope"], "mine")
        mock_store.return_value.search_clientes.assert_called_once_with(
            "acme", 8, executivo_id=10
        )
        mock_store.return_value.search_cotacoes.assert_called_once_with(
            "acme", 8, executivo_id=10
        )

    @patch("aicentralv2.agent.routes.search_operational_records", return_value={"pis": [], "campaigns": []})
    @patch("aicentralv2.agent.routes.get_store")
    def test_commercial_search_all_is_available_to_admin(self, mock_store, _mock_ops):
        mock_store.return_value.search_clientes.return_value = []
        mock_store.return_value.search_cotacoes.return_value = []
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="admin")
        response = self.client.get("/api/agent/commercial/search?q=acme&scope=all")
        self.assertEqual(response.get_json()["data"]["scope"], "all")
        mock_store.return_value.search_clientes.assert_called_once_with(
            "acme", 8, executivo_id=None
        )

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

    @patch("aicentralv2.agent.routes.get_store")
    def test_regular_user_cannot_open_unassigned_client(self, mock_store):
        mock_store.return_value.get_cliente.return_value = {
            "id": "7", "nome": "Acme", "executivo_id": "99"
        }
        with self.client.session_transaction() as session:
            session.update(user_id=10, is_centralcomm=True, user_type="client")
        response = self.client.get("/api/agent/commercial/record/cliente/7")
        self.assertEqual(response.status_code, 404)

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
        self.assertTrue({"contacts", "quotes", "pis", "campaigns"}.issubset(keys))
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


if __name__ == "__main__":
    unittest.main()
