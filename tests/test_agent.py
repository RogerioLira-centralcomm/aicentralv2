"""Contratos de segurança e comportamento básico do Agente CentralX."""

import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from aicentralv2.agent import bp
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

    def test_registry_contains_only_six_read_tools(self):
        self.assertEqual(len(TOOLS), 6)
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

    def test_context_only_completes_matching_entity_type(self):
        args = _contextual_arguments(
            "listar_contatos", {}, {"entity_type": "cliente", "entity_id": "1843"}
        )
        self.assertEqual(args["cliente_id"], "1843")
        unrelated = _contextual_arguments(
            "listar_contatos", {}, {"entity_type": "cotacao", "entity_id": "98037"}
        )
        self.assertNotIn("cliente_id", unrelated)

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
        self.assertIn("commercial.read.global", data["capabilities"])
        self.assertTrue(data["csrf_token"])

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


if __name__ == "__main__":
    unittest.main()
