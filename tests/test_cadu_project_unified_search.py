"""The project search must distinguish saved data, metadata, and read content."""

from contextlib import nullcontext
from flask import Flask
import pytest

from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.mcp.tools import workspace
from aicentralv2.cadu_workspace.project_query import is_overview_query
from aicentralv2.cadu_workspace import project_resource_service


CONTEXT = RequestContext(
    organization_id=12, client_id=12, user_id=7, conversation_id=None,
    surface="workspace", project_ref="ci:project-1", capabilities=("workspace",),
)


@pytest.fixture(autouse=True)
def no_historical_conversations(monkeypatch, request):
    if not request.node.name.startswith("test_historical_project_search"):
        monkeypatch.setattr(workspace, "_search_project_conversation_history", lambda *_: [])
    if not request.node.name.startswith("test_confirmed_project_memory"):
        monkeypatch.setattr(workspace, "_confirmed_project_memory", lambda *_: [])


class _IndexStatusDb:
    def __init__(self, pending=False):
        self.pending = pending

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, *_):
        pass

    def fetchone(self):
        return {"available": True, "pending": self.pending}


def _project_packet():
    return {
        "projeto": {"nome": "Campanha de e-mail"},
        "direction": {"revision": 4},
        "fontes_verificadas": [{"fonte": "Pesquisa de público", "trecho": "Público B2B", "score": 0.2}],
    }


def test_search_combines_project_direction_resources_tasks_and_indexed_content(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: _IndexStatusDb())
    monkeypatch.setattr(workspace, "_native_project_id", lambda context: "project-1")
    monkeypatch.setattr(workspace, "get_project_context", lambda *_: _project_packet())
    monkeypatch.setattr(workspace.project_context_service, "context_items", lambda *_: [
        {"id": "context:custom:publico", "label": "Público", "display_value": "Público B2B"},
    ])
    monkeypatch.setattr(workspace.project_resource_service, "list_for_context", lambda *_: {
        "resources": [{"id": "resource-1", "resource_type": "link", "title": "Pesquisa de público",
                       "locator": "https://example.com/pesquisa", "metadata": {"description": "Referência B2B"}}],
    })
    monkeypatch.setattr(workspace.project_task_service, "list_tasks", lambda *_: {
        "tasks": [{"id": "task-1", "title": "Validar público B2B", "status": "todo"}],
    })

    result = workspace.search_project_content(CONTEXT, {"query": "público B2B"})

    assert {item["result_type"] for item in result["results"]} == {
        "project_context", "indexed_source", "project_resource", "project_activity",
    }
    assert result["results"][0]["result_type"] == "project_context"
    assert result["resource_results"][0]["evidence_level"] == "metadata_only"
    assert result["source_results"][0]["trecho"] == "Público B2B"
    assert result["unavailable_scopes"] == []


def test_search_includes_project_activity_saved_as_reference(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: _IndexStatusDb())
    monkeypatch.setattr(workspace, "_native_project_id", lambda context: "project-1")
    monkeypatch.setattr(workspace, "get_project_context", lambda *_: _project_packet())
    monkeypatch.setattr(workspace.project_context_service, "context_items", lambda *_: [])
    monkeypatch.setattr(workspace.project_resource_service, "list_for_context", lambda *_: {"resources": [{
        "id": "reference-1", "resource_type": "link", "title": "Reunião de campanha",
        "metadata": {"project_item_kind": "decision", "context_summary": "Aprovar campanha B2B",
                     "timeline": {"label": "Decisão de campanha", "occurred_at": "2026-09-23"}},
    }]})
    monkeypatch.setattr(workspace.project_task_service, "list_tasks", lambda *_: {"tasks": []})

    result = workspace.search_project_content(CONTEXT, {"query": "campanha B2B"})

    activity = result["activity_results"][0]
    assert activity["resource_id"] == "reference-1"
    assert activity["activity_kind"] == "decision"
    assert activity["evidence_level"] == "saved_project_metadata"


def test_overview_balances_context_sources_resources_and_tasks(monkeypatch):
    calls = []
    def project_context(*args, **kwargs):
        calls.append(kwargs)
        return _project_packet()

    monkeypatch.setattr(workspace, "get_db", lambda: _IndexStatusDb())
    monkeypatch.setattr(workspace, "_native_project_id", lambda context: "project-1")
    monkeypatch.setattr(workspace, "get_project_context", project_context)
    monkeypatch.setattr(workspace.project_context_service, "context_items", lambda *_: [
        {"id": f"context-{index}", "label": f"Direção {index}", "display_value": "Informação salva"}
        for index in range(20)
    ])
    monkeypatch.setattr(workspace.project_resource_service, "list_for_context", lambda *_: {
        "resources": [{"id": f"resource-{index}", "resource_type": "link", "title": f"Biblioteca {index}",
                       "metadata": {"description": "Referência da campanha"}} for index in range(20)],
    })
    monkeypatch.setattr(workspace.project_task_service, "list_tasks", lambda *_: {
        "tasks": [{"id": "task-1", "title": "Aprovar criativos", "status": "todo"}],
    })

    result = workspace.search_project_content(CONTEXT, {"query": "Visão geral de tudo sobre esse projeto"})

    assert calls == [{"result_limit": 12, "overview": True}]
    assert {item["result_type"] for item in result["results"]} == {
        "project_context", "indexed_source", "project_resource", "project_activity",
    }
    assert len(result["results"]) == 25


def test_generic_project_question_returns_saved_context_without_keyword_overlap(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: _IndexStatusDb())
    monkeypatch.setattr(workspace, "_native_project_id", lambda context: "project-1")
    monkeypatch.setattr(workspace, "get_project_context", lambda *_, **__: {
        **_project_packet(), "source_inventory": {"total": 2, "indexed": 1, "needs_index": 1},
    })
    monkeypatch.setattr(workspace.project_context_service, "context_items", lambda *_: [
        {"label": "Público", "display_value": "Empresas B2B"},
    ])
    monkeypatch.setattr(workspace.project_resource_service, "list_for_context", lambda *_: {"resources": [
        {"id": "resource-1", "resource_type": "file", "title": "Briefing de lançamento", "metadata": {}},
    ]})
    monkeypatch.setattr(workspace.project_task_service, "list_tasks", lambda *_: {"tasks": []})

    result = workspace.search_project_content(CONTEXT, {"query": "O que você sabe sobre esse projeto?"})

    assert result["mode"] == "overview"
    assert {item["result_type"] for item in result["results"]} >= {
        "project_context", "indexed_source", "project_resource",
    }
    assert "unindexed_sources" in result["unavailable_scopes"]


def test_project_overview_intent_keeps_specific_field_queries_as_searches():
    assert is_overview_query("O que você sabe sobre esse projeto?")
    assert is_overview_query("O que você tem sobre esse projeto?")
    assert is_overview_query("O que vc tem sobre esse projeto?")
    assert is_overview_query("Visão geral de tudo sobre esse projeto")
    assert not is_overview_query("Quem é o público desse projeto?")
    assert not is_overview_query("Qual é o orçamento desse projeto?")


def test_resource_read_uses_source_tables_while_registry_job_is_pending(monkeypatch):
    class Db:
        def transaction(self): return nullcontext()
        def cursor(self): return _IndexStatusDb(pending=True)

    monkeypatch.setattr(project_resource_service, "get_db", lambda: Db())
    monkeypatch.setattr(project_resource_service, "list_resources", lambda *_, **__: {
        "resources": [], "relations": [], "summary": {"total": 0},
    })
    monkeypatch.setattr(project_resource_service, "_relation", lambda *_: True)
    monkeypatch.setattr(project_resource_service, "_collect", lambda *_: [
        project_resource_service._record("workspace", "link:1", "link", "centralcomm.media"),
    ])

    result = project_resource_service.list_for_context(CONTEXT)

    assert result["resources"][0]["title"] == "centralcomm.media"
    assert result["registry_pending"] is True
    assert result["source"] == "source_tables"


def test_resource_read_uses_source_tables_when_registry_is_partially_populated(monkeypatch):
    class Db:
        def transaction(self): return nullcontext()
        def cursor(self): return _IndexStatusDb(pending=False)

    monkeypatch.setattr(project_resource_service, "get_db", lambda: Db())
    monkeypatch.setattr(project_resource_service, "list_resources", lambda *_, **__: {
        "resources": [{"id": "old", "title": "Fonte antiga"}], "relations": [], "summary": {"total": 1},
    })
    monkeypatch.setattr(project_resource_service, "_relation", lambda *_: True)
    monkeypatch.setattr(project_resource_service, "_collect", lambda *_: [
        project_resource_service._record("workspace", "link:2", "link", "Fonte atual"),
    ])

    result = project_resource_service.list_for_context(CONTEXT)

    assert [item["title"] for item in result["resources"]] == ["Fonte atual"]
    assert result["registry_pending"] is False


def test_search_reports_partial_inventory_failure_without_losing_saved_context(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: _IndexStatusDb())
    monkeypatch.setattr(workspace, "_native_project_id", lambda context: "project-1")
    monkeypatch.setattr(workspace, "get_project_context", lambda *_: _project_packet())
    monkeypatch.setattr(workspace.project_context_service, "context_items", lambda *_: [
        {"id": "context:standard:audience", "label": "Público", "display_value": "B2B"},
    ])
    monkeypatch.setattr(workspace.project_resource_service, "list_for_context",
                        lambda *_: (_ for _ in ()).throw(RuntimeError("registry unavailable")))
    monkeypatch.setattr(workspace.project_task_service, "list_tasks", lambda *_: {"tasks": []})

    with Flask(__name__).app_context():
        result = workspace.search_project_content(CONTEXT, {"query": "público"})

    assert result["unavailable_scopes"] == ["project_resources"]
    assert any(item["result_type"] == "project_context" for item in result["results"])


def test_search_marks_resource_index_as_pending(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: _IndexStatusDb(pending=True))
    monkeypatch.setattr(workspace, "_native_project_id", lambda context: "project-1")
    monkeypatch.setattr(workspace, "get_project_context", lambda *_: _project_packet())
    monkeypatch.setattr(workspace.project_context_service, "context_items", lambda *_: [])
    monkeypatch.setattr(workspace.project_resource_service, "list_for_context", lambda *_: {"resources": []})
    monkeypatch.setattr(workspace.project_task_service, "list_tasks", lambda *_: {"tasks": []})

    result = workspace.search_project_content(CONTEXT, {"query": "público"})

    assert result["resource_index_pending"] is True


def test_search_does_not_report_unavailable_sources_as_no_matches(monkeypatch):
    monkeypatch.setattr(workspace, "get_db", lambda: _IndexStatusDb())
    monkeypatch.setattr(workspace, "_native_project_id", lambda context: "project-1")
    monkeypatch.setattr(workspace, "get_project_context", lambda *_: {
        **_project_packet(), "fontes_verificadas": [], "retrieval_status": "unavailable",
    })
    monkeypatch.setattr(workspace.project_context_service, "context_items", lambda *_: [])
    monkeypatch.setattr(workspace.project_resource_service, "list_for_context", lambda *_: {"resources": []})
    monkeypatch.setattr(workspace.project_task_service, "list_tasks", lambda *_: {"tasks": []})

    result = workspace.search_project_content(CONTEXT, {"query": "público"})

    assert result["source_retrieval_status"] == "unavailable"
    assert "indexed_sources" in result["unavailable_scopes"]


def test_historical_project_search_uses_user_and_project_scope(monkeypatch):
    captured = {}
    def rows(sql, params):
        captured["sql"], captured["params"] = sql, params
        return [{"message_id": "m1", "conversation_id": "c1", "content": "Decidimos focar em B2B.",
                 "conversation_title": "Planejamento", "created_at": "2026-09-20", "text_rank": 0.4}]
    monkeypatch.setattr(workspace.repository, "rows", rows)

    results = workspace._search_project_conversation_history(CONTEXT, "decisões B2B", False)

    assert "binding.client_id=%s" in captured["sql"]
    assert "binding.organization_id" not in captured["sql"]
    assert "binding.project_ref=%s AND binding.user_id=%s" in captured["sql"]
    assert "message.role='user'" in captured["sql"]
    assert captured["params"][2:7] == (12, "ci:project-1", 7, 12, 7)
    assert results[0]["evidence_level"] == "user_statement"
    assert results[0]["message_id"] == "m1"


def test_historical_project_search_skips_generic_question(monkeypatch):
    monkeypatch.setattr(workspace.repository, "rows", lambda *_: pytest.fail("unexpected lookup"))
    assert workspace._search_project_conversation_history(CONTEXT, "O que você tem sobre esse projeto?", False) == []


def test_confirmed_project_memory_is_scoped_and_keeps_review_provenance(monkeypatch):
    captured = {}
    def rows(sql, params):
        captured['sql'], captured['params'] = sql, params
        return [{'id': 'memory-1', 'kind': 'decision', 'summary': 'Foco em B2B',
                 'reviewed_at': '2026-09-25', 'text_rank': 0.3}]
    monkeypatch.setattr(workspace.repository, 'rows', rows)

    result = workspace._confirmed_project_memory(CONTEXT, 'B2B')

    assert "client_id=%s AND status='confirmed'" in captured['sql']
    assert "organization_id" not in captured['sql']
    assert "scope='project' AND project_ref=%s" in captured['sql']
    assert captured['params'][2:] == (12, 'ci:project-1')
    assert result[0]['evidence_level'] == 'reviewed_project_memory'
    assert result[0]['memory_id'] == 'memory-1'


def test_search_checks_project_access_before_reading_context(monkeypatch):
    from aicentralv2.cadu_workspace.mcp.registry import ToolInputError

    def denied(_context):
        raise ToolInputError("Sem acesso")

    monkeypatch.setattr(workspace, "_native_project_id", denied)
    monkeypatch.setattr(workspace, "get_project_context", lambda *_: (_ for _ in ()).throw(AssertionError("read")))
    try:
        workspace.search_project_content(CONTEXT, {"query": "público"})
    except ToolInputError:
        pass
    else:
        raise AssertionError("A busca deve verificar o acesso antes de consultar dados")
