import pytest
from flask import Flask
from types import SimpleNamespace

from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.agent_v2.router import route_request
from aicentralv2.cadu_workspace.agent_v2 import service
from aicentralv2.cadu_workspace.mcp.registry import ToolForbidden, registry
from aicentralv2.cadu_workspace.workspace_action_policy import action_link


def test_destructive_entity_requests_route_to_workspace_links():
    assert route_request("excluir este projeto", has_project=True).action == "open_project_delete"
    assert route_request("mesclar este projeto com outro", has_project=True).action == "open_project_merge"
    assert route_request("apagar esta marca", has_brand=True).action == "open_brand_delete"


def test_destructive_routes_respect_negation_and_require_an_active_entity():
    assert route_request("não exclua este projeto", has_project=True).action != "open_project_delete"
    assert route_request("não quero apagar esta marca", has_brand=True).action != "open_brand_delete"
    assert route_request("excluir projeto").action == "select_project_for_delete"
    assert route_request("mesclar projetos").action == "select_project_for_merge"
    assert route_request("apagar marca").action == "select_brand_for_delete"


def test_workspace_action_links_open_the_correct_detail_dialog():
    project = action_link("open_project_merge", project_ref="ci:42", target_project_ref="ci:77")
    brand = action_link("open_brand_delete", brand_ref="studio:9")
    assert project["block"]["href"] == "/projetos/42?acao=mesclar&destino=77"
    assert brand["block"]["href"] == "/marcas/9?acao=apagar"


def test_mcp_rejects_workspace_only_operations_before_tool_lookup():
    context = RequestContext(organization_id=1, client_id=1, user_id=1,
                             conversation_id=None, surface="workspace", capabilities=("workspace",))
    with pytest.raises(ToolForbidden, match="Workspace"):
        registry.validate("workspace.delete_project", {}, context)


def test_workspace_link_response_does_not_call_provider(monkeypatch):
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_): pass

    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass
        def rollback(self): pass

    monkeypatch.setattr(service.provider, "events", lambda *_: (_ for _ in ()).throw(
        AssertionError("provider must not be called")))
    monkeypatch.setattr(service.repository, "rows", lambda *_: [{"status": "running"}])
    monkeypatch.setattr(service.repository, "get_db", lambda: Connection())
    monkeypatch.setattr(service.journal, "record", lambda _run, kind, payload, **_: {"event": kind, **(payload or {})})
    monkeypatch.setattr(service.journal, "complete_step", lambda *_: None)
    monkeypatch.setattr(service.journal, "waiting_actions", lambda *_: [])
    current = RequestContext(organization_id=1, client_id=1, user_id=1,
                             conversation_id="conversation", surface="workspace",
                             project_ref="ci:42", capabilities=("workspace",))
    run = {
        "run_id": "be777b36-a973-419c-802a-886bf1d125b0", "conversation_id": "conversation",
        "context": current, "route": {"action": "open_project_delete", "artifact_type": None},
        "policy": {"mode": "direct", "max_questions": 1, "max_next_steps": 1,
                   "max_answer_chars": 900, "artifact_in_chat": False},
        "resolved_context": SimpleNamespace(tool_calls=[], values={}), "provider_payload": {},
        "execution_mode": "fast", "runtime": {"id": "test", "config_version": "1"},
    }
    app = Flask(__name__)
    with app.app_context():
        output = "".join(service.stream(run))
    assert '"type": "workspace_action"' in output
    assert '"provider_duration_ms": 0' not in output
