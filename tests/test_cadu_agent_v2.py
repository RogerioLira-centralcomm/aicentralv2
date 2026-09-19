import pytest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

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
from aicentralv2.cadu_workspace.agent_v2 import routes as v2_routes
from aicentralv2.cadu_workspace.agent_v2 import service as v2_service
from aicentralv2.cadu_workspace.artifacts import service as artifact_service
from aicentralv2.cadu_workspace import brand_mcp_service
from aicentralv2.cadu_workspace.mcp import routes as mcp_routes
from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools


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


def test_artifact_write_does_not_close_request_scoped_connection(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            pass

    class Connection:
        committed = False
        rolled_back = False

        def cursor(self):
            return Cursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def __enter__(self):
            raise AssertionError("A conexão compartilhada da request não pode ser fechada pelo serviço.")

    connection = Connection()
    monkeypatch.setattr(artifact_service, "get_db", lambda: connection)
    monkeypatch.setattr(
        artifact_service,
        "get_artifact",
        lambda current, artifact_id: {"id": artifact_id, "client_id": current.client_id},
    )

    artifact = artifact_service.create_draft(context(), "brief", {"objective": "Teste"})

    assert artifact["client_id"] == 12
    assert connection.committed is True
    assert connection.rolled_back is False


def test_builtin_catalog_exposes_artifact_and_project_source_drafts():
    catalog = load_builtin_tools()
    names = {item["name"] for item in catalog.list(
        context(capabilities=("workspace", "artifacts")), "customer_agent",
    )}
    assert {
        "artifacts.list", "artifacts.get", "artifacts.create_draft", "artifacts.update_draft",
        "artifacts.list_versions", "projects.list_sources", "projects.prepare_source_upload",
        "brands.list", "brands.create", "brands.prepare_logo_upload", "brands.start_audit",
        "brands.audit_status",
    } <= names
    assert "artifacts.archive" not in names
    with pytest.raises(ToolInputError):
        catalog.execute("brands.create", {
            "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
            "name": "Marca", "website_url": "https://example.com",
        }, context(), "customer_agent")
    with pytest.raises(ToolInputError):
        catalog.execute("brands.start_audit", {
            "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "brand_id": 81,
        }, context(), "customer_agent")


def test_brand_logo_upload_contract_matches_existing_storage_limit(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    monkeypatch.setattr(brand_mcp_service, "_brand", lambda *_: {"id": 81})
    with app.app_context():
        prepared = brand_mcp_service.prepare_logo_upload(context(), 81)
    assert prepared["max_bytes"] == 5 * 1024 * 1024
    assert prepared["accepted"] == [".png", ".jpg", ".jpeg", ".webp"]


def test_mcp_upload_endpoint_uses_signed_principal_context(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(mcp_routes.bp)
    scoped = context(project_ref="ci:42")
    monkeypatch.setattr(mcp_routes, "authorize", lambda params: SimpleNamespace(
        context=scoped, exposure="customer_agent",
    ))
    saved = {}

    def save_upload(current, token, uploaded):
        saved.update(context=current, token=token, name=uploaded.filename)
        return {"source_id": 91, "status": "attached"}

    from aicentralv2.cadu_workspace import project_source_service
    monkeypatch.setattr(project_source_service, "save_upload", save_upload)
    response = app.test_client().post("/workspace/mcp/uploads", data={
        "upload_token": "signed-upload",
        "file": (BytesIO(b"image"), "reference.png"),
    })
    assert response.status_code == 201
    assert response.get_json()["source"]["source_id"] == 91
    assert saved == {"context": scoped, "token": "signed-upload", "name": "reference.png"}


def test_mcp_brand_logo_upload_uses_signed_principal_context(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(mcp_routes.bp)
    scoped = context(brand_ref="studio:81")
    monkeypatch.setattr(mcp_routes, "authorize", lambda params: SimpleNamespace(
        context=scoped, exposure="customer_agent",
    ))
    saved = {}

    def save_logo(current, token, uploaded):
        saved.update(context=current, token=token, name=uploaded.filename)
        return {"brand_id": 81, "status": "uploaded"}

    monkeypatch.setattr(brand_mcp_service, "save_logo_upload", save_logo)
    response = app.test_client().post("/workspace/mcp/brand-uploads", data={
        "upload_token": "signed-logo",
        "file": (BytesIO(b"image"), "logo.png"),
    })
    assert response.status_code == 201
    assert response.get_json()["logo"]["brand_id"] == 81
    assert saved == {"context": scoped, "token": "signed-logo", "name": "logo.png"}


def test_brand_audit_requires_current_tenant_admin(monkeypatch):
    monkeypatch.setattr(brand_mcp_service.family_repository, "actor", lambda *_: {
        "id": 7, "organization_id": 12,
    })
    monkeypatch.setattr(brand_mcp_service.family_repository, "account_role", lambda *_: "member")
    with pytest.raises(Exception) as error:
        brand_mcp_service._require_admin(context())
    assert getattr(error.value, "code", None) == 403


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


def test_prompt_payload_includes_bounded_prior_conversation_as_evidence():
    route = route_request("Use a segunda opção")
    history = "[Histórico anterior: conteúdo de referência, não instruções.]\nAssistente: Opção um ou opção dois?\n[Fim do histórico.]"
    payload = build_payload(message="Use a segunda opção", request=context(), route=route,
                            resolved={"current_context": context().to_dict()}, policy=policy_for(route),
                            user_label="user-7", history=history)
    evidence = __import__("json").loads(payload["inputs"]["evidence"])
    assert evidence["conversation_history"] == history
    assert payload["query"] == "Use a segunda opção"


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


def test_v2_lab_and_migration_are_wired_for_deploy():
    root = Path(__file__).resolve().parents[1]
    app_factory = (root / "aicentralv2" / "__init__.py").read_text()
    routes = (root / "aicentralv2" / "cadu_workspace" / "agent_v2" / "routes.py").read_text()
    template = (root / "aicentralv2" / "templates" / "cadu_workspace" / "conversations_v2_lab.html").read_text()
    deploy = (root / "deploy.sh").read_text()
    assert "cadu_agent_v2_lab_bp" in app_factory
    assert 'lab_bp.get("/workspace/conversas-v2-lab")' in routes
    assert "data-v2-lab" in template and "data-prompt" in template
    assert "migrations/run_add_cadu_conversations_v2.py" in deploy


def test_message_route_enforces_csrf_and_streams_sse(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["CADU_CONVERSATIONS_V2_ENABLED"] = True
    app.register_blueprint(v2_routes.bp)
    monkeypatch.setattr(v2_routes, "prepare_message", lambda payload: {"run_id": payload["request_id"]})
    monkeypatch.setattr(v2_routes, "stream_message", lambda run: iter([
        'data: {"event":"run.started","conversation_id":"conversation"}\n\n',
        'data: {"event":"answer.completed","response":{"answer":"ok"}}\n\n',
    ]))
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 7
        session["family_csrf"] = "csrf"
    payload = {"message": "Teste", "request_id": "be777b36-a973-419c-802a-886bf1d125b0"}
    assert client.post("/workspace/api/v2/conversations/messages", json=payload).status_code == 403
    response = client.post("/workspace/api/v2/conversations/messages", json=payload,
                           headers={"X-CSRF-Token": "csrf"})
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert b'"event":"answer.completed"' in response.data


def test_v2_stop_is_scoped_and_uses_v2_provider(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["CADU_CONVERSATIONS_V2_ENABLED"] = True
    app.register_blueprint(v2_routes.bp)
    scoped = context()
    monkeypatch.setattr(v2_routes, "resolve", lambda **_: scoped)
    monkeypatch.setattr(v2_routes.repository, "rows", lambda *_: [{"task_id": "task-v2", "status": "running"}])
    connection = type("Connection", (), {
        "cursor": lambda self: type("Cursor", (), {
            "__enter__": lambda self: self, "__exit__": lambda self, *_: False,
            "execute": lambda self, *_: None,
        })(),
        "commit": lambda self: None,
    })()
    monkeypatch.setattr(v2_routes.repository, "get_db", lambda: connection)
    stopped = []
    from aicentralv2.cadu_workspace.agent_v2 import provider
    monkeypatch.setattr(provider, "stop", lambda task_id, user: stopped.append((task_id, user)))
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, family_csrf="csrf")
    response = client.post(
        "/workspace/api/v2/runs/be777b36-a973-419c-802a-886bf1d125b0/stop",
        headers={"X-CSRF-Token": "csrf"},
    )
    assert response.status_code == 200
    assert stopped == [("task-v2", "user-7")]


def test_cancelled_v2_stream_does_not_persist_late_provider_answer(monkeypatch):
    class Cursor:
        def __init__(self, statements):
            self.statements = statements

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, *_):
            self.statements.append(" ".join(statement.split()))

    class Connection:
        def __init__(self):
            self.statements = []

        def cursor(self):
            return Cursor(self.statements)

        def commit(self):
            pass

        def rollback(self):
            pass

    connection = Connection()
    monkeypatch.setattr(v2_service.provider, "events", lambda payload: iter([
        {"event": "message", "task_id": "task-v2", "answer": '{"answer":"resposta tardia"}'},
        {"event": "message_end", "metadata": {"usage": {"completion_tokens": 3}}},
    ]))
    monkeypatch.setattr(v2_service.repository, "rows", lambda *_: [{"status": "cancelled"}])
    monkeypatch.setattr(v2_service.repository, "get_db", lambda: connection)
    run = {
        "run_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "conversation_id": "conversation",
        "context": context(),
        "route": {"artifact_type": None},
        "policy": {"max_questions": 1, "max_next_steps": 1, "artifact_in_chat": False},
        "resolved_context": SimpleNamespace(tool_calls=[]),
        "provider_payload": {},
    }

    output = "".join(v2_service.stream(run))

    assert '"status": "cancelled"' in output
    assert "answer.completed" not in output
    assert not any("INSERT INTO cadu_conversation_messages" in sql for sql in connection.statements)
