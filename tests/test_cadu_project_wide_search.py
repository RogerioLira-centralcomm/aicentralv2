"""Whole-project requests must reach the model with the project's saved data, not an empty result."""
import json

import pytest

from aicentralv2.cadu_workspace.agent_v2 import executor, retrieval_query as rq
from aicentralv2.cadu_workspace.agent_v2.context_resolver import PROJECT_WIDE_ACTIONS, _arguments
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools
from aicentralv2.cadu_workspace.mcp.tools import workspace
from tests import test_cadu_project_unified_search as fixtures

FIELDS = [
    {"id": "c1", "label": "Objetivo", "display_value": "Gerar leads B2B no segundo semestre"},
    {"id": "c2", "label": "Público", "display_value": "Decisores de TI no Sudeste"},
    {"id": "c3", "label": "Verba", "display_value": "R$ 50 mil para mídia paga"},
]
REQUEST = RequestContext(client_id=12, user_id=7, conversation_id=None, surface="workspace",
                         project_ref="ci:project-1", capabilities=("workspace",))


@pytest.fixture
def saved_project(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: fixtures._IndexStatusDb())
    monkeypatch.setattr(workspace, "_native_project_id", lambda context: "project-1")
    monkeypatch.setattr(workspace, "get_project_context", lambda *a, **k: {
        "projeto": {"nome": "Marketing"}, "fontes_verificadas": [], "retrieval_status": "complete",
        "context_status": "available", "direction": {}})
    monkeypatch.setattr(workspace.conversation_index, "available", lambda: False)
    monkeypatch.setattr(workspace.project_context_service, "context_items", lambda *_: [dict(item) for item in FIELDS])
    monkeypatch.setattr(workspace.project_resource_service, "list_for_context", lambda *_: {"resources": []})
    monkeypatch.setattr(workspace.project_task_service, "list_tasks", lambda *_: {"tasks": []})
    monkeypatch.setattr(workspace, "_search_project_conversation_history", lambda *_: [])
    monkeypatch.setattr(workspace, "_confirmed_project_memory", lambda *_: [])


@pytest.mark.parametrize("message", [
    "Estruture um briefing para este projeto e destaque somente o que ainda precisa ser decidido.",
    "o que ainda não foi definido no projeto?",
    "qual o status deste projeto?",
    "O que falta decidir?",
    "qual o público do projeto?",
    "algo totalmente sem relação com os campos",
])
def test_saved_project_fields_always_reach_the_model(saved_project, message):
    result = workspace.search_project_content(REQUEST, _arguments("workspace.search_project_content", REQUEST, message, "analysis", "answer"))
    labels = {row["label"] for row in result["results"] if row["result_type"] == "project_context"}
    assert labels == {"Objetivo", "Público", "Verba"}


def test_keyword_match_ranks_the_matching_field_first(saved_project):
    result = workspace.search_project_content(REQUEST, {"query": "qual o público do projeto?", "mode": "search"})
    assert result["results"][0]["label"] == "Público"


@pytest.mark.parametrize("action", sorted(PROJECT_WIDE_ACTIONS))
def test_whole_project_actions_use_the_overview_read(action):
    assert _arguments("workspace.search_project_content", REQUEST, "x", "analysis", action)["mode"] == "overview"


@pytest.mark.parametrize("message", ["o que ainda não foi definido no projeto?", "O que falta decidir?",
                                     "qual o status deste projeto?", "o que precisa ser decidido"])
def test_pending_style_questions_use_the_overview_read(message):
    assert _arguments("workspace.search_project_content", REQUEST, message, "analysis", "answer")["mode"] == "overview"


def test_a_pointed_question_stays_a_targeted_search():
    assert _arguments("workspace.search_project_content", REQUEST, "qual o público do projeto?",
                      "analysis", "answer")["mode"] == "search"


def test_briefing_reaches_the_prompt_with_the_project_data_through_the_real_path(saved_project, monkeypatch):
    monkeypatch.setattr(rq, "_llm_rewrite", lambda *_: "")
    monkeypatch.setattr(executor, "load_builtin_tools", load_builtin_tools)
    monkeypatch.setattr(workspace, "get_db", lambda: fixtures._IndexStatusDb())
    execution = executor.prepare_execution(
        "Estruture um briefing para este projeto e destaque somente o que ainda precisa ser decidido.", REQUEST)
    evidence = json.loads(execution["provider_payload"]["inputs"]["evidence"])["workspace.search_project_content"]
    assert {"Objetivo", "Público", "Verba"} <= {row.get("label") for row in evidence["results"]}
    assert execution["policy"]["briefing_readiness"]["project_grounded"] is True
    assert "Estruture o briefing no chat" in execution["provider_payload"]["inputs"]["core"]
