import pytest

from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.agent_v2.response_policy import budget_for, policy_for
from aicentralv2.cadu_workspace.agent_v2.router import route_request
from aicentralv2.cadu_workspace.agent_v2.guardrails import normalize_response
from aicentralv2.cadu_workspace.agent_v2.prompt_assembler import build_payload
from aicentralv2.cadu_workspace.mcp.registry import (
    ToolDefinition,
    ToolForbidden,
    ToolInputError,
    ToolRegistry,
)
from aicentralv2.cadu_workspace.mcp.authorization import MCPUnauthorized, authorize, issue
from flask import Flask


def context(**overrides):
    values = {
        "organization_id": 12,
        "client_id": 12,
        "user_id": 7,
        "conversation_id": "conversation",
        "surface": "conversations",
        "project_ref": None,
        "capabilities": ("workspace",),
    }
    values.update(overrides)
    return RequestContext(**values)


def test_context_never_allows_cross_tenant_selection():
    with pytest.raises(ValueError):
        context(client_id=99)


def test_brief_creation_is_artifact_first_and_bounded():
    route = route_request("Estruture um briefing para esse projeto", has_project=True)
    assert route.action == "create_brief"
    assert route.response_mode == "artifact_first"
    assert route.artifact_type == "brief"
    assert route.needs_context == ("project", "brand")
    assert policy_for(route)["max_questions"] == 2
    assert budget_for(route).max_llm_calls == 1


def test_project_search_uses_one_semantic_tool():
    route = route_request("Pesquise nos documentos do projeto o que definimos sobre orçamento", has_project=True)
    assert route.action == "search_project"
    assert route.needs_tools == ("workspace.search_project_content",)
    assert "studio" not in route.needs_context
    assert "reports" not in route.needs_context


def test_cross_domain_report_comparison_gets_high_budget_only_when_needed():
    route = route_request("Compare o resultado de agosto com o plano de mídia", surface="reports", has_project=True)
    assert route.action == "compare_report_to_plan"
    assert route.needs_context == ("project", "reports", "media_plan")
    assert budget_for(route).max_llm_calls == 2


def test_simple_request_does_not_load_context_or_tools():
    route = route_request("Melhore este título")
    assert route.response_mode == "direct"
    assert route.needs_context == ()
    assert route.needs_tools == ()


def test_registry_enforces_capability_and_project_before_handler():
    called = []
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="planner.read", description="Read", capability="planner", effect="read",
        input_schema={"type": "object"}, handler=lambda *_: called.append(True), requires_project=True,
    ))
    with pytest.raises(ToolForbidden):
        registry.execute("planner.read", {}, context())
    with pytest.raises(ToolInputError):
        registry.execute("planner.read", {}, context(capabilities=("planner",)))
    assert called == []


def test_registry_executes_in_process_for_authorized_context():
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="workspace.echo", description="Echo", capability="workspace", effect="read",
        input_schema={"type": "object"}, handler=lambda current, values: {
            "client_id": current.client_id, "value": values["value"]
        },
    ))
    assert registry.execute("workspace.echo", {"value": "ok"}, context()) == {"client_id": 12, "value": "ok"}


def test_registry_enforces_declared_input_schema_before_handler():
    called = []
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="workspace.search", description="Search", capability="workspace", effect="read",
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "minLength": 2, "maxLength": 20},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "additionalProperties": False,
        },
        handler=lambda *_: called.append(True),
    ))
    for invalid in ({}, {"query": "x"}, {"query": "ok", "limit": 0}, {"query": "ok", "extra": True}):
        with pytest.raises(ToolInputError):
            registry.execute("workspace.search", invalid, context())
    assert called == []
    registry.execute("workspace.search", {"query": "ok", "limit": 2}, context())
    assert called == [True]


def test_prompt_payload_is_compact_and_does_not_inject_unrequested_domains():
    route = route_request("Melhore este título")
    payload = build_payload(message="Melhore este título", request=context(), route=route,
                            resolved={"current_context": context().to_dict()}, policy=policy_for(route),
                            user_label="user-7")
    serialized = __import__("json").dumps(payload, ensure_ascii=False)
    assert len(serialized) < 4000
    assert "workspace_da_equipe" not in serialized
    assert "catalogo_midia_cadu" not in serialized
    assert "user_profile_context" not in serialized


def test_response_policy_caps_questions_even_if_provider_ignores_instruction():
    response = normalize_response({
        "answer": "Atualizei o briefing.",
        "questions": ["Pergunta 1?", "Pergunta 2?", "Pergunta 3?"],
        "confidence": "high",
    }, {"max_questions": 2, "artifact_in_chat": False})
    assert response.questions == ["Pergunta 1?", "Pergunta 2?"]


def test_response_policy_caps_and_sanitizes_actions():
    response = normalize_response({
        "answer": "Próximo passo definido.",
        "actions": [
            {"id": "  first  ", "label": "  Criar plano  ", "prompt": "  Faça o plano.  ", "extra": "drop"},
            {"id": "second", "label": "Revisar plano", "prompt": "Revise."},
            {"id": "third", "label": "Publicar", "prompt": "Publique."},
        ],
    }, {"max_questions": 0, "max_next_steps": 2, "artifact_in_chat": False})
    assert response.actions == [
        {"id": "first", "label": "Criar plano", "prompt": "Faça o plano."},
        {"id": "second", "label": "Revisar plano", "prompt": "Revise."},
    ]


def test_normalizer_bounds_artifact_fields_and_citations():
    response = normalize_response({
        "answer": "Briefing iniciado.",
        "artifact_patch": {
            "title": "  Briefing  ",
            "summary": "  Base inicial  ",
            "fields": [{"key": " público ", "value": " moradores locais ", "state": "unknown"}],
        },
        "citations": [{"title": " Fonte ", "url": " https://example.com ", "excerpt": " Trecho "}],
    }, {"max_questions": 0, "max_next_steps": 0, "artifact_in_chat": False})
    assert response.artifact_patch["fields"] == [
        {"key": "público", "value": "moradores locais", "state": "inferred"}
    ]
    assert response.citations == [
        {"title": "Fonte", "url": "https://example.com", "excerpt": "Trecho"}
    ]


def test_mcp_delegation_preserves_scoped_context_and_rejects_tampering():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    scoped = context(project_ref="ci:42", capabilities=("workspace", "planner"))
    with app.test_request_context("/"):
        token = issue(scoped)
    with app.test_request_context("/", headers={"Authorization": "Bearer " + token}):
        delegated = authorize({}).context
        assert delegated.client_id == 12
        assert delegated.project_ref == "ci:42"
        assert delegated.capabilities == ("workspace", "planner")
    with app.test_request_context("/", headers={"Authorization": "Bearer " + token + "x"}):
        with pytest.raises(MCPUnauthorized):
            authorize({})


def test_registry_exposure_prevents_internal_tools_from_leaking_to_customer_agents():
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="internal.audit", description="Audit", capability="workspace", effect="read",
        input_schema={"type": "object"}, handler=lambda *_: {}, exposures=("internal",),
    ))
    assert [item["name"] for item in registry.list(context(), "customer_agent")] == []
    with pytest.raises(ToolForbidden):
        registry.execute("internal.audit", {}, context(), "customer_agent")


def test_normalizer_accepts_fenced_json_without_showing_the_envelope():
    response = normalize_response('''```json
    {"answer":"Conclusão objetiva.","questions":[],"confidence":"high"}
    ```''', {"max_questions": 1, "artifact_in_chat": False})
    assert response.answer == "Conclusão objetiva."
    assert response.confidence == "high"
