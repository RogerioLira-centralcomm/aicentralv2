"""Cadu agent and MCP flows around the Reports Link Tester: routing, analysis choice, receipts, digest and AI review."""
import pytest

from aicentralv2.cadu_workspace.agent_v2.action_executor import ALLOWED_ACTION_TOOLS, _completion
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.agent_v2.router import route_request
from aicentralv2.cadu_workspace.agent_v2.task_planner import _link_review_step, link_test_mode
from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools

RUN_ID = "1384246d-0455-41e1-89cc-547f43252cc1"


def ctx():
    return RequestContext(client_id=12, user_id=7, conversation_id="c", surface="conversations", capabilities=("reports",))


@pytest.mark.parametrize("message", [
    "testa o link https://x.com/?utm_source=a",
    "o site centralcomm.media está pronto para agentes de IA?",
    "a super tag está instalada em centralcomm.media?",
    "verifique o pixel e as tags de https://loja.com.br",
    "o llms.txt de anthropic.com está ok? confere a presença para IA do site",
])
def test_site_questions_route_to_the_link_tester(message):
    route = route_request(message)
    assert (route.domain, route.action, route.requires_confirmation) == ("reports", "link_test", True)


def test_unrelated_requests_do_not_become_link_tests():
    for message in ("como está o desempenho da campanha de setembro?", "crie um post para o instagram sobre IA"):
        assert route_request(message).action != "link_test"


@pytest.mark.parametrize("message,mode", [
    ("Teste a UTM de https://example.com/?utm_source=cadu", "destination"),
    ("a super tag está instalada em centralcomm.media?", "media"),
    ("confira o GA4 e o pixel da Meta em loja.com.br", "media"),
    ("o site loja.com.br aparece para o ChatGPT?", "agentic"),
    ("tags do site prontas para agentes de IA? loja.com.br", "agentic"),
])
def test_the_analysis_follows_the_question(message, mode):
    assert link_test_mode(message) == mode


def test_review_request_becomes_a_confirmed_paid_action():
    message = f"Revise o teste de link {RUN_ID}"
    route = route_request(message)
    assert route.action == "link_review"
    step = _link_review_step(message)
    assert step["name"] == "reports.review_link_test" and step["requires_confirmation"] is True
    assert step["arguments"] == {"run_id": RUN_ID}
    assert "reports.review_link_test" in ALLOWED_ACTION_TOOLS


def test_link_test_receipt_shows_score_points_and_review_shortcut():
    completion = _completion("reports.link_test", {
        "run_id": RUN_ID, "mode": "media", "score": 54, "status_label": "Medição parcial", "summary": "Resumo.",
        "final_url": "https://centralcomm.media/", "platforms": [{"name": "Google Tag Manager", "ids": ["GTM-1"], "where": "code"}],
        "highlights": [{"tone": "ok", "text": "Cadu Super Tag instalada no código da página."}], "capture_note": None,
    })
    types = [block["type"] for block in completion["blocks"]]
    assert types[:3] == ["activity", "metrics", "insights"]
    review = completion["blocks"][2]["items"][-1]
    assert review["prompt"] == f"Revise o teste de link {RUN_ID}"


def test_agent_digest_drops_raw_inventory_and_share_token(monkeypatch):
    from aicentralv2.cadu_workspace.mcp.tools import reports
    monkeypatch.setattr(reports.operations, "execute", lambda request_id, current, tool_name, payload, operation: operation())
    monkeypatch.setattr(reports.link_tester, "test", lambda *_, **__: {
        "run_id": "run-1", "kind": "media", "score": 54, "public_token": "secret-token", "status_label": "x", "summary": "y",
        "final_url": "https://a.com/", "highlights": [], "alerts": [],
        "evidence": {"screenshot": "/connect/public/link-tests/secret-token/screenshot",
                     "inventory": {"platforms": [{"name": "Meta Pixel", "ids": ["123456789"], "where": "injected", "script_loads": 2}],
                                   "scripts": {"external": 40, "third_party": 30, "injected": 5, "blocking_in_code": 3,
                                               "list": [{"src": f"https://cdn{i}.com/x.js"} for i in range(40)]},
                                   "consent": {"tools": [], "consent_mode": False}, "events": {}}},
    })
    result = load_builtin_tools().execute("reports.link_test", {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "confirmed": True, "url": "https://a.com", "mode": "media",
    }, ctx(), "internal")
    assert "secret-token" not in str(result)
    assert result["has_screenshot"] is True
    assert result["platforms"] == [{"name": "Meta Pixel", "ids": ["123456789"], "where": "injected"}]
    assert "cdn1.com" not in str(result)  # the script list stays out of the model context


def test_review_tool_is_internal_only():
    registry = load_builtin_tools()
    internal = {tool["name"] for tool in registry.list(ctx(), "internal")}
    public = {tool["name"] for tool in registry.list(ctx(), "customer_agent")}
    assert "reports.review_link_test" in internal
    assert "reports.review_link_test" not in public
    assert {"reports.list_link_tests", "reports.get_link_test"} <= public
