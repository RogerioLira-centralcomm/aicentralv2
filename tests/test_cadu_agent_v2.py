import pytest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext, execution_mode_for
from aicentralv2.cadu_workspace.agent_v2.response_policy import (
    budget_for, policy_for, requested_answer_chars, requested_output_tokens,
)
from aicentralv2.cadu_workspace.agent_v2.router import route_request
from aicentralv2.cadu_workspace.agent_v2.executor import briefing_readiness
from aicentralv2.cadu_workspace.agent_v2.task_planner import build_task_plan
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
from aicentralv2.cadu_workspace.agent_v2 import journal
from aicentralv2.cadu_workspace.artifacts import service as artifact_service
from aicentralv2.cadu_workspace import brand_mcp_service
from aicentralv2.cadu_workspace import project_source_service
from aicentralv2.cadu_workspace import project_resource_jobs
from aicentralv2.cadu_workspace.mcp import routes as mcp_routes
from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools

ROOT = Path(__file__).resolve().parents[1]


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


def test_context_keeps_agency_and_selected_client_as_distinct_boundaries():
    selected = context(client_id=99)
    assert selected.organization_id == 12
    assert selected.client_id == 99


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


def test_artifact_schema_matches_runtime_types():
    sql = (ROOT / "migrations" / "add_cadu_conversations_v2.sql").read_text(encoding="utf-8")
    for artifact_type in ("project_map", "html", "meeting_summary", "meeting_agenda"):
        assert artifact_type in sql
    assert "cadu_workspace_artifacts_type_check" in sql


def test_link_reader_is_an_allowed_personal_artifact_type():
    migration = (ROOT / "migrations" / "add_cadu_link_reader_artifact.sql").read_text(encoding="utf-8")
    rollback = (ROOT / "migrations" / "rollback_cadu_link_reader_artifact.sql").read_text(encoding="utf-8")
    base_schema = (ROOT / "migrations" / "add_cadu_conversations_v2.sql").read_text(encoding="utf-8")
    assert "link_reader" in artifact_service.ALLOWED_TYPES
    assert "link_reader" in migration
    assert "cadu_workspace_artifacts_type_check" in base_schema
    assert "WHERE type = 'link_reader'" in rollback
    assert "RAISE EXCEPTION" in rollback


def test_link_reader_rollback_is_not_a_forward_admin_migration():
    from aicentralv2 import admin_migrations_routes

    assert admin_migrations_routes._ROLLBACK_SQL_RX.match("rollback_cadu_link_reader_artifact.sql")
    assert not admin_migrations_routes._ROLLBACK_SQL_RX.match("add_cadu_link_reader_artifact.sql")
    discovered = {item["name"]: item for item in admin_migrations_routes._discover_migrations()}
    assert discovered["add_cadu_link_reader_artifact.sql"]["runnable"] is True
    assert discovered["rollback_cadu_link_reader_artifact.sql"]["runnable"] is False


def test_personal_link_reference_persists_without_project(monkeypatch):
    calls = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, query, params): calls.append((query, params))

    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass
        def rollback(self): raise AssertionError("Não deve fazer rollback")

    personal = context(project_ref=None)
    monkeypatch.setattr(artifact_service, "get_db", lambda: Connection())
    monkeypatch.setattr(artifact_service, "get_artifact", lambda current, artifact_id: {"id": artifact_id, "project_ref": current.project_ref, "type": "link_reader"})

    artifact = artifact_service.create_draft(personal, "link_reader", {"url": "https://example.com"}, title="Exemplo")

    insert_params = calls[0][1]
    assert insert_params[3] is None
    assert insert_params[5] == "link_reader"
    assert artifact["project_ref"] is None


def test_builtin_catalog_exposes_artifact_and_project_source_drafts():
    catalog = load_builtin_tools()
    names = {item["name"] for item in catalog.list(
        context(capabilities=("workspace", "artifacts")), "customer_agent",
    )}
    assert {
        "artifacts.list", "artifacts.get", "artifacts.create_draft", "artifacts.update_draft",
        "artifacts.list_versions", "projects.list_sources", "projects.list_resources", "projects.inspect_file_support",
        "projects.prepare_source_upload", "projects.classify_intake", "projects.create_link_reference",
        "brands.list", "brands.prepare_logo_upload",
        "brands.audit_status",
    } <= names
    planner_names = {item["name"] for item in catalog.list(
        context(capabilities=("planner",)), "customer_agent",
    )}
    assert {
        "planner.list_plans", "planner.search_catalog", "planner.get_brief", "planner.get_media_plan",
        "planner.list_link_tests", "planner.get_link_test",
    } <= planner_names
    internal_planner_names = {item["name"] for item in catalog.list(
        context(capabilities=("planner",)), "internal",
    )}
    assert "planner.link_test" in internal_planner_names
    assert "planner.link_test" not in planner_names
    internal_names = {item["name"] for item in catalog.list(
        context(capabilities=("workspace", "artifacts")), "internal",
    )}
    assert {"brands.create", "brands.start_audit"} <= internal_names
    assert "projects.reindex_source" in internal_names
    assert "projects.create_note" in internal_names
    assert "workspace.create_project" in internal_names
    assert {"workspace.update_project_context", "workspace.set_project_status"} <= internal_names
    assert "workspace.link_current_brand" in internal_names
    assert not {"brands.create", "brands.start_audit"} & names
    assert "artifacts.archive" not in names
    with pytest.raises(ToolInputError):
        catalog.execute("brands.create", {
            "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
            "name": "Marca", "website_url": "https://example.com",
        }, context(), "internal")
    with pytest.raises(ToolInputError):
        catalog.execute("brands.start_audit", {
            "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "brand_id": 81,
        }, context(), "internal")
    with pytest.raises(ToolInputError):
        catalog.execute("planner.link_test", {
            "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
            "confirmed": False, "url": "https://example.com", "mode": "destination",
        }, context(capabilities=("planner",)), "internal")


def test_planner_link_test_is_idempotent_and_hides_share_token(monkeypatch):
    from aicentralv2.cadu_workspace.mcp.tools import planner

    captured = {}

    def execute(request_id, current, tool_name, payload, operation):
        captured.update(request_id=request_id, current=current, tool_name=tool_name, payload=payload)
        return operation()

    monkeypatch.setattr(planner.operations, "execute", execute)
    monkeypatch.setattr(planner.link_tester, "test", lambda *_, **__: {
        "run_id": "run-1", "public_token": "must-not-reach-agent", "score": 91,
    })
    result = load_builtin_tools().execute("planner.link_test", {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "confirmed": True, "url": "https://example.com", "mode": "destination",
    }, context(capabilities=("planner",)), "internal")

    assert result == {"run_id": "run-1", "score": 91}
    assert captured["tool_name"] == "planner.link_test"
    assert captured["payload"] == {"url": "https://example.com", "mode": "destination"}


def test_mcp_operation_reuses_completed_result_without_running_again(monkeypatch):
    from aicentralv2.cadu_workspace.mcp import operations

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_): pass
        def fetchone(self):
            return {"input_hash": operations.sha256(b'{"value":1}').hexdigest(),
                    "status": "completed", "result": {"receipt": "existing"}, "stale": False}

    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass
        def rollback(self): pass

    monkeypatch.setattr(operations, "get_db", lambda: Connection())
    called = []
    result = operations.execute(
        "be777b36-a973-419c-802a-886bf1d125b0", context(), "planner.link_test", {"value": 1},
        lambda: called.append(True),
    )

    assert result == {"receipt": "existing"}
    assert called == []


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


def test_prepare_project_upload_seals_request_id_in_intent(monkeypatch):
    captured = {}

    def prepare(current, **values):
        captured.update(current=current, **values)
        return {"upload_token": "signed"}

    monkeypatch.setattr(project_source_service, "prepare_upload", prepare)
    current = context(project_ref="ci:42")
    result = load_builtin_tools().execute("projects.prepare_source_upload", {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "use_as_knowledge": True,
    }, current, "customer_agent")

    assert result == {"upload_token": "signed"}
    assert captured["request_id"] == "be777b36-a973-419c-802a-886bf1d125b0"
    assert captured["use_as_knowledge"] is True


def test_intake_classification_keeps_links_and_chat_text_out_of_the_index():
    link = project_source_service.classify_intake(url="https://example.com/reuniao")
    note = project_source_service.classify_intake(text="Ata da reunião: decisões e próximos passos.")
    brief = project_source_service.classify_intake(filename="briefing-campanha.pdf", mime_type="application/pdf")

    assert link["purpose"] == "project_attachment"
    assert link["index_recommended"] is False
    assert note["artifact_type"] == "meeting_summary"
    assert note["purpose"] == "artifact"
    assert brief["category"] == "brief"
    assert brief["purpose"] == "knowledge_source"


def test_project_link_is_an_explicit_confirmed_reference_action():
    message = "Adicione este link ao projeto: https://docs.google.com/document/d/abc"
    route = route_request(message, has_project=True)
    action = next(step for step in build_task_plan(route, budget_for(route), message) if step["kind"] == "action")

    assert route.action == "create_project_link"
    assert action["name"] == "projects.create_link_reference"
    assert action["arguments"]["url"].startswith("https://docs.google.com/")


def test_bare_link_stays_a_reference_and_explicit_read_is_allowed():
    bare = route_request("https://example.com/article")
    explicit = route_request("Entenda este link: https://example.com/article")

    assert bare.action == "register_link_reference"
    assert not bare.needs_tools
    assert explicit.action == "read_web_page"
    assert explicit.needs_tools == ("web.read",)


def test_user_facing_plans_never_exceed_four_steps():
    route = route_request("Abra e resuma https://example.com/article")
    plan = build_task_plan(route, budget_for(route), "Abra e resuma https://example.com/article")

    assert len(plan) <= 4
    assert plan[-1]["kind"] == "generate"


def test_project_commands_route_to_real_registry_capabilities():
    listing = route_request("Liste os links e arquivos deste projeto", has_project=True)
    sources = route_request("Mostre as fontes indexadas do projeto", has_project=True)
    creation = route_request('Crie um projeto chamado "Campanha Primavera"')

    assert listing.action == "list_project_resources"
    assert listing.needs_tools == ("projects.list_resources",)
    assert sources.needs_tools == ("projects.list_sources",)
    assert creation.response_mode == "decision"
    assert creation.artifact_type is None
    action = next(step for step in build_task_plan(creation, budget_for(creation), 'Crie um projeto chamado "Campanha Primavera"')
                  if step["kind"] == "action")
    assert action["name"] == "workspace.create_project"
    assert action["requires_confirmation"] is True


def test_project_archive_is_a_confirmed_workspace_action():
    route = route_request("Arquive este projeto", has_project=True)
    action = next(step for step in build_task_plan(route, budget_for(route), "Arquive este projeto")
                  if step["kind"] == "action")
    assert route.action == "set_project_status"
    assert action["name"] == "workspace.set_project_status"
    assert action["arguments"]["status"] == "arquivado"


def test_linking_a_project_brand_requires_an_explicit_brand_context():
    missing = route_request("Vincule esta marca ao projeto", has_project=True)
    ready = route_request("Vincule esta marca ao projeto", has_project=True, has_brand=True)
    assert missing.action == "select_brand_for_project"
    assert missing.response_mode == "clarification"
    action = next(step for step in build_task_plan(ready, budget_for(ready), "Vincule esta marca ao projeto")
                  if step["kind"] == "action")
    assert action["name"] == "workspace.link_current_brand"
    assert action["arguments"]["linked"] is True


def test_reindexing_a_source_requires_its_explicit_identifier():
    route = route_request("Reprocesse o arquivo 42", has_project=True)
    action = next(step for step in build_task_plan(route, budget_for(route), "Reprocesse o arquivo 42")
                  if step["kind"] == "action")
    assert route.action == "reindex_project_source"
    assert action["name"] == "projects.reindex_source"
    assert action["arguments"] == {"source_id": 42}


def test_project_document_edits_do_not_trigger_costly_reindexing():
    update = route_request("Atualize o documento do projeto com a nova oferta", has_project=True)
    missing_source = route_request("Reprocesse este arquivo", has_project=True)

    assert update.action != "reindex_project_source"
    assert missing_source.action == "select_project_source"
    assert missing_source.response_mode == "clarification"


def test_project_note_is_a_confirmed_knowledge_source_action():
    message = 'Adicione a nota "Decisão de mídia": Priorizar LinkedIn para gestores B2B e validar o CPL na primeira semana.'
    route = route_request(message, has_project=True)
    action = next(step for step in build_task_plan(route, budget_for(route), message) if step["kind"] == "action")
    assert route.action == "create_project_note"
    assert action["name"] == "projects.create_note"
    assert action["arguments"]["title"] == "Decisão de mídia"


def test_incomplete_project_note_asks_only_for_the_missing_payload():
    route = route_request("Adicione uma nota ao projeto", has_project=True)
    plan = build_task_plan(route, budget_for(route), "Adicione uma nota ao projeto")

    assert route.action == "clarify_project_note"
    assert route.response_mode == "clarification"
    assert not [step for step in plan if step["kind"] == "action"]


def test_project_note_reuses_a_matching_knowledge_source(monkeypatch):
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_): pass
        def fetchone(self):
            return {"id": 91, "name": "Decisão de mídia", "tokens": 20, "category": "research"}

    class Connection:
        committed = False
        def cursor(self): return Cursor()
        def commit(self): self.committed = True
        def rollback(self): raise AssertionError("A consulta duplicada não deve falhar")

    connection = Connection()
    monkeypatch.setattr(project_source_service, "_project_id", lambda _: "42")
    monkeypatch.setattr(project_source_service, "get_db", lambda: connection)
    monkeypatch.setattr(project_source_service.project_knowledge, "index",
                        lambda _: (_ for _ in ()).throw(AssertionError("Não deve reindexar conteúdo duplicado")))
    monkeypatch.setattr(project_source_service, "_schedule_resource_reconciliation",
                        lambda *_: "queued")

    result = project_source_service.create_note(
        context(project_ref="ci:42"), title="Decisão de mídia",
        content="Priorizar LinkedIn para gestores B2B e validar o CPL na primeira semana.",
    )

    assert result["source_id"] == 91
    assert result["idempotent_replay"] is True
    assert connection.committed is True


def test_reindex_domain_errors_are_safe_tool_errors(monkeypatch):
    from aicentralv2.cadu_workspace.mcp.tools import projects

    monkeypatch.setattr(projects.project_index_service, "reindex_source",
                        lambda *_: (_ for _ in ()).throw(ValueError("Fonte indisponível para reindexação.")))
    monkeypatch.setattr(projects.operations, "execute", lambda _id, _context, _tool, _payload, operation: operation())

    with pytest.raises(ToolInputError, match="Fonte indisponível"):
        load_builtin_tools().execute("projects.reindex_source", {
            "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "confirmed": True, "source_id": 91,
        }, context(project_ref="ci:42"), "internal")


def test_registry_reconciliation_falls_back_to_an_idempotent_repair(monkeypatch):
    from aicentralv2.cadu_workspace import project_resource_service

    monkeypatch.setattr(project_resource_service, "notify_change",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("queue unavailable")))
    repaired = []
    monkeypatch.setattr(project_resource_service, "reconcile",
                        lambda *args: repaired.append(args) or {"available": True})

    app = Flask(__name__)
    with app.app_context():
        assert project_source_service._schedule_resource_reconciliation(context(project_ref="ci:42"), 91) == "reconciled"
    assert repaired == [(12, "ci:42", 7)]


def test_create_project_tool_writes_canonical_project_only_after_confirmation(monkeypatch):
    from aicentralv2.cadu_workspace.mcp.tools import workspace

    captured = {}
    monkeypatch.setattr(workspace.repository, "create_entity", lambda client_id, user_id, payload: captured.update(
        client_id=client_id, user_id=user_id, payload=payload) or "ci:project-1")
    monkeypatch.setattr(workspace.operations, "execute", lambda request_id, current, tool_name, payload, operation: operation())
    result = load_builtin_tools().execute("workspace.create_project", {
        "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "name": "Campanha Primavera", "confirmed": True,
    }, context(), "internal")

    assert result == {"project_ref": "ci:project-1", "name": "Campanha Primavera", "status": "created"}
    assert captured["payload"]["kind"] == "project"


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


def test_brief_creation_starts_with_a_bounded_discovery():
    route = route_request("Estruture um briefing para esse projeto", has_project=True)
    assert route.action == "create_brief"
    assert route.response_mode == "clarification"
    assert route.artifact_type is None
    assert route.needs_context == ("project", "brand")
    assert policy_for(route)["max_questions"] == 1
    assert budget_for(route).max_llm_calls == 1


def test_intermediate_mode_keeps_room_for_substantive_answers():
    route = route_request("Analise a trajetória desta marca")
    policy = policy_for(route)
    assert route.response_mode == "analysis"
    assert policy["max_answer_chars"] == 6000


def test_explicit_word_count_expands_the_answer_allowance():
    assert requested_answer_chars("Escreva um texto com cerca de 600 palavras") == 4800
    assert requested_answer_chars("Escreva um guia com 2.500 palavras") == 20000
    assert requested_output_tokens("Escreva um guia com 2.500 palavras") == 5000
    assert requested_answer_chars("Responda de forma breve") == 0
    assert requested_output_tokens("Responda de forma breve") == 0


def test_project_link_classifier_covers_collaboration_and_media_platforms():
    from aicentralv2.cadu_workspace.project_source_service import describe_link

    youtube = describe_link("https://youtu.be/video-id")
    assert youtube["provider"] == "youtube"
    assert youtube["resource_kind"] == "video"
    assert youtube["access_type"] == "public"
    assert youtube["embed_type"] == "youtube"

    ads = describe_link("https://ads.tiktok.com/business/creativecenter")
    assert ads["provider"] == "tiktok_ads"
    assert ads["access_type"] == "authenticated"
    assert ads["connector_recommended"] is True

    notion = describe_link("https://example.notion.site/Plano-123")
    assert notion["provider"] == "notion"
    assert notion["access_type"] == "public"


def test_analysis_response_preserves_multiple_paragraphs():
    response = normalize_response(
        "Primeiro parágrafo com a análise.\n\nSegundo parágrafo com a conclusão.",
        {"mode": "analysis", "max_answer_chars": 6000, "max_questions": 0, "max_next_steps": 0},
    )
    assert "Primeiro parágrafo" in response.answer
    assert "Segundo parágrafo" in response.answer


def test_brief_readiness_requires_four_of_five_campaign_inputs_before_artifact():
    incomplete = briefing_readiness("Quero uma campanha para a marca.")
    complete = briefing_readiness(
        "Objetivo: gerar leads para o produto. Público: gestores B2B. "
        "Oferta: demonstração gratuita. Canais: LinkedIn e Google. Prazo: outubro."
    )
    assert incomplete["complete"] is False
    assert incomplete["percent"] < 80
    assert complete["complete"] is True
    assert complete["percent"] >= 80


def test_brief_discovery_discards_a_provider_artifact_before_readiness():
    response = normalize_response({
        "answer": "Vamos começar pelo resultado que a campanha precisa gerar.",
        "artifact_patch": {"title": "Briefing vazio", "fields": [{"key": "Objetivo", "value": "", "state": "missing"}]},
    }, {"mode": "clarification", "max_questions": 1, "max_next_steps": 1,
        "max_answer_chars": 360, "allow_artifact": False})
    assert response.artifact_patch is None


def test_payload_asks_to_resolve_a_missing_project_brand_before_using_it():
    route = route_request("Analise este criativo", has_project=True)
    payload = build_payload(
        message="Analise este criativo", request=context(project_ref="ci:42", brand_ref=None), route=route,
        resolved={}, policy={"mode": "analysis"}, user_label="user-12",
    )
    assert "vincular uma marca existente ou criar uma nova" in payload["inputs"]["core"]


def test_direct_dense_answer_never_becomes_an_implicit_artifact():
    response = normalize_response("""A resposta possui detalhes suficientes para ser longa.

- Primeiro ponto relevante.
- Segundo ponto relevante.
- Terceiro ponto relevante.
- Quarto ponto relevante.
""", {
        "mode": "direct",
        "max_answer_chars": 360,
        "max_questions": 0,
        "max_next_steps": 0,
        "allow_artifact": False,
    })
    assert response.artifact_patch is None
    assert "artefato ao lado" not in response.answer.lower()


def test_project_search_uses_one_semantic_tool():
    route = route_request("Pesquise nos documentos do projeto o que definimos sobre orçamento", has_project=True)
    assert route.action == "search_project"
    assert route.needs_tools == ("workspace.search_project_content",)
    assert "studio" not in route.needs_context
    assert "reports" not in route.needs_context


def test_project_readout_routes_dense_work_to_an_editable_artifact():
    route = route_request(
        "Faça uma leitura de partida do projeto Nike: objetivo, entregas, riscos e decisões.",
        has_project=True,
    )
    assert route.action == "project_readout"
    assert route.response_mode == "artifact_first"
    assert route.artifact_type == "executive_summary"
    assert route.needs_tools == ("workspace.search_project_content",)

    missing_context = route_request(
        "Faça uma leitura de partida do projeto Nike: objetivo, entregas, riscos e decisões.",
        has_project=False,
    )
    assert missing_context.action == "select_project_for_readout"
    assert missing_context.response_mode == "clarification"
    assert missing_context.artifact_type is None


def test_project_file_classification_never_decides_knowledge_usage():
    result = project_source_service._classify(
        {"name": "plano-de-midia.pdf", "suffix": ".pdf"}, None,
        "Plano de mídia para o lançamento",
    )
    assert result["category"] == "media_plan"
    assert "use_as_knowledge" not in result


def test_manual_project_file_category_has_priority():
    result = project_source_service._classify(
        {"name": "dados.csv", "suffix": ".csv"}, "research", "",
    )
    assert result == {
        "category": "research", "status": "manual", "confidence": 1.0,
        "reason": "Categoria informada pelo usuário.",
    }


def test_project_file_support_never_claims_unknown_content_is_understood():
    assert project_source_service.inspect_file_support("briefing.pdf")["can_index"] is True
    image = project_source_service.inspect_file_support("referencia.webp", "image/webp")
    assert image["status"] == "attachment_only"
    assert image["can_index"] is False
    spreadsheet = project_source_service.inspect_file_support("investimento.xlsx")
    assert spreadsheet["status"] == "needs_adapter"
    assert spreadsheet["format_family"] == "spreadsheet"
    unknown = project_source_service.inspect_file_support("material.indd")
    assert unknown["status"] == "unsupported"


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


def test_execution_modes_are_bounded_by_route():
    simple = route_request("Melhore este título")
    brief = route_request("Crie um briefing para o projeto", has_project=True)
    assert execution_mode_for(simple, "") == "fast"
    assert execution_mode_for(simple, "agentic") == "analysis"
    assert execution_mode_for(brief, "") == "analysis"
    assert budget_for(simple, "fast").max_tool_calls == 1
    assert budget_for(brief, "agentic").max_duration_ms == 240000


def test_agentic_decision_persists_checkpoint_and_event_atomically(monkeypatch):
    results = iter([{"id": "run"}, {"id": "step", "kind": "action", "name": "publish", "status": "running",
                                     "input_snapshot": {"name": "publish"}},
                    {"sequence": 4}])

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, *_args, **_kwargs): pass
        def fetchone(self): return next(results)

    cursor = Cursor()

    class Connection:
        committed = 0
        rolled_back = 0
        def cursor(self): return cursor
        def commit(self): self.committed += 1
        def rollback(self): self.rolled_back += 1

    connection = Connection()
    monkeypatch.setattr(journal.repository, "get_db", lambda: connection)
    result = journal.decide_step("run", "step", 12, 7, True, "Aprovado")
    assert result["status"] == "running"
    assert connection.committed == 1
    assert connection.rolled_back == 0


def test_link_test_route_creates_a_sealed_confirmation_step():
    from aicentralv2.cadu_workspace.agent_v2.task_planner import build_task_plan

    route = route_request("Teste a UTM de https://example.com/landing?utm_source=cadu")
    plan = build_task_plan(route, budget_for(route, "agentic"),
                           "Teste a UTM de https://example.com/landing?utm_source=cadu")
    action = next(step for step in plan if step["kind"] == "action")

    assert route.action == "link_test"
    assert route.requires_confirmation is True
    assert action["name"] == "planner.link_test"
    assert action["arguments"] == {
        "url": "https://example.com/landing?utm_source=cadu", "mode": "media",
    }
    assert action["requires_confirmation"] is True
    assert len(action["request_id"]) == 36


def test_approved_action_executes_only_the_sealed_tool_and_arguments(monkeypatch):
    from aicentralv2.cadu_workspace.agent_v2 import action_executor

    captured = {}

    class Registry:
        def execute(self, name, arguments, current, exposure):
            captured.update(name=name, arguments=arguments, current=current, exposure=exposure)
            return {"run_id": "link-run", "score": 88}

    monkeypatch.setattr(action_executor, "load_builtin_tools", lambda: Registry())
    current = context(capabilities=("planner",))
    receipt = action_executor.execute({
        "kind": "action", "status": "running", "name": "planner.link_test",
        "input_snapshot": {
            "kind": "action", "name": "planner.link_test",
            "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
            "arguments": {"url": "https://example.com", "mode": "destination"},
        },
    }, current)

    assert captured == {
        "name": "planner.link_test",
        "arguments": {
            "url": "https://example.com", "mode": "destination",
            "request_id": "be777b36-a973-419c-802a-886bf1d125b0", "confirmed": True,
        },
        "current": current, "exposure": "internal",
    }
    assert receipt["result"]["run_id"] == "link-run"
    assert receipt["completion"]["answer"] == "Ação concluída."


def test_project_note_action_emits_a_semantic_completion_item(monkeypatch):
    from aicentralv2.cadu_workspace.agent_v2 import action_executor

    class Registry:
        def execute(self, *_):
            return {"source_id": 91, "name": "Decisão de mídia", "registry_sync": "queued"}

    monkeypatch.setattr(action_executor, "load_builtin_tools", lambda: Registry())
    receipt = action_executor.execute({
        "kind": "action", "status": "running", "name": "projects.create_note",
        "input_snapshot": {"name": "projects.create_note", "request_id": "be777b36-a973-419c-802a-886bf1d125b0",
                           "arguments": {"title": "Decisão de mídia", "content": "Priorizar LinkedIn para gestores B2B."}},
    }, context())

    assert receipt["completion"]["refresh_context"] is True
    assert receipt["completion"]["blocks"][0]["type"] == "sources"


def test_resource_worker_reclaims_stale_jobs_with_backoff(monkeypatch):
    calls = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def execute(self, sql, params=()): calls.append((sql, params))
        def fetchone(self): return None

    class Connection:
        def cursor(self): return Cursor()
        def commit(self): pass
        def rollback(self): pass

    monkeypatch.setattr(project_resource_jobs, "get_db", lambda: Connection())
    assert project_resource_jobs.claim() is None
    sql = calls[0][0]
    assert "SKIP LOCKED" in sql
    assert "started_at < NOW()-INTERVAL '10 minutes'" in sql
    assert "next_attempt_at <= NOW()" in sql


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
    assert len(serialized) < 8000
    assert "workspace_da_equipe" not in serialized
    assert "catalogo_midia_cadu" not in serialized
    assert payload["inputs"]["user_profile_context"] == payload["inputs"]["current_context"]
    assert payload["inputs"]["projeto_context"] == payload["inputs"]["evidence"]


def test_prompt_legacy_aliases_are_derived_from_the_v2_contract():
    route = route_request("Explique CPM")
    payload = build_payload(
        message="Explique CPM", request=context(), route=route,
        resolved={"current_context": context().to_dict()}, policy=policy_for(route),
        user_label="user-7", history="Assistente: contexto anterior",
    )
    inputs = payload["inputs"]
    assert inputs["skill_context"] == inputs["core"]
    assert inputs["projeto_context"] == inputs["evidence"]
    assert inputs["user_profile_context"] == inputs["current_context"]
    assert inputs["user_memory_context"] == "Assistente: contexto anterior"
    assert inputs["is_first_message"] == "false"


def test_response_repairs_leaked_orchestrator_wrapper_before_display():
    response = normalize_response({
        "answer": "Projeto usado: geral. Decisão proposta: explicar CPM. "
                  "Resposta: CPM é o custo por mil impressões. Próxima ação: perguntar se deseja exemplo."
    }, {"mode": "analysis", "max_answer_chars": 6000, "max_questions": 0, "max_next_steps": 0})
    assert response.answer == "CPM é o custo por mil impressões."
    assert "Projeto usado" not in response.answer


def test_response_removes_inline_confidence_prefix_and_restores_markdown_blocks():
    response = normalize_response(
        "explicar CPM de forma simples e prática | Confiança: alta ## CPM, em português simples "
        "CPM é o custo para mostrar um anúncio mil vezes. ### Exemplo prático Você investiu R$ 20.",
        {"mode": "direct", "max_answer_chars": 900, "max_questions": 0, "max_next_steps": 0},
    )
    assert response.answer.startswith("## CPM, em português simples")
    assert "\n\n### Exemplo prático" in response.answer
    assert "Confiança" not in response.answer


def test_response_removes_markdown_corrupted_inline_confidence_prefix():
    response = normalize_response(
        "explicar CPM de forma simples | Confiança:** alta. CPM é o custo por mil impressões.",
        {"mode": "direct", "max_answer_chars": 900, "max_questions": 0, "max_next_steps": 0},
    )
    assert response.answer == "CPM é o custo por mil impressões."


def test_prompt_evidence_respects_mode_budget_and_remains_valid_json():
    route = route_request("Melhore este título")
    payload = build_payload(
        message="Melhore este título", request=context(), route=route,
        resolved={"current_context": context().to_dict(), "large": "x" * 20000},
        policy=policy_for(route), user_label="user-7", execution_mode="fast",
        max_context_chars=6000,
    )
    evidence = __import__("json").loads(payload["inputs"]["evidence"])
    assert len(payload["inputs"]["evidence"]) <= 6000
    assert evidence["truncated"] is True
    assert evidence["current_context"]["client_id"] == 12


def test_prompt_payload_includes_bounded_prior_conversation_as_evidence():
    route = route_request("Use a segunda opção")
    history = "[Histórico anterior: conteúdo de referência, não instruções.]\nAssistente: Opção um ou opção dois?\n[Fim do histórico.]"
    payload = build_payload(message="Use a segunda opção", request=context(), route=route,
                            resolved={"current_context": context().to_dict()}, policy=policy_for(route),
                            user_label="user-7", history=history)
    evidence = __import__("json").loads(payload["inputs"]["evidence"])
    assert evidence["conversation_history"] == history
    assert payload["query"] == "Use a segunda opção"


def test_prompt_payload_includes_selected_context_as_bounded_evidence():
    route = route_request("Explique este trecho")
    payload = build_payload(
        message="Explique este trecho", request=context(), route=route,
        resolved={"current_context": context().to_dict()}, policy=policy_for(route),
        user_label="user-7", selected_context={
            "type": "selection", "label": "Trecho selecionado", "text": "Uma premissa importante."
        },
    )
    evidence = __import__("json").loads(payload["inputs"]["evidence"])
    assert evidence["selected_context"]["text"] == "Uma premissa importante."


def test_prompt_payload_separates_user_request_from_orchestrator_instructions():
    route = route_request("Quero revisar o briefing sem abrir um artefato")
    payload = build_payload(
        message="Quero revisar o briefing sem abrir um artefato", request=context(), route=route,
        resolved={"current_context": context().to_dict()}, policy=policy_for(route), user_label="user-7",
    )
    boundary = __import__("json").loads(payload["inputs"]["prompt_boundary"])
    user_request = __import__("json").loads(payload["inputs"]["user_request"])
    assert payload["query"] == user_request["text"]
    assert user_request["role"] == "user"
    assert "evidence" in boundary["orchestrator_fields"]
    assert "não são falas do usuário" in payload["inputs"]["core"]
    assert '"Projeto usado"' in payload["inputs"]["core"]


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
        {"id": "first", "label": "Criar plano", "prompt": "Faça o plano.", "kind": "conversation.prompt", "requires_confirmation": False},
        {"id": "second", "label": "Revisar plano", "prompt": "Revise.", "kind": "conversation.prompt", "requires_confirmation": False},
    ]


def test_response_blocks_are_typed_bounded_and_safe():
    response = normalize_response({
        "answer": "Escolha uma direção para continuar.",
        "blocks": [
            {"type": "decision", "title": "Direção", "items": [
                {"id": "a", "title": "Editorial", "description": "Mais autoral.",
                 "recommended": True, "prompt": "Use a direção editorial.", "html": "drop"},
            ]},
            {"type": "files", "title": "Arquivos", "items": [
                {"title": "Briefing", "kind": "Google Docs", "url": "https://docs.google.com/document/1"},
                {"title": "Inválido", "url": "javascript:alert(1)"},
            ]},
            {"type": "unknown", "items": [{"title": "Descartar"}]},
        ],
    }, {"max_questions": 0, "max_next_steps": 0, "max_answer_chars": 320})
    assert response.blocks == [
        {"type": "decision", "title": "Direção", "summary": "", "items": [{
            "id": "a", "title": "Editorial", "detail": "Mais autoral.",
            "recommended": True, "prompt": "Use a direção editorial.",
        }]},
        {"type": "files", "title": "Arquivos", "summary": "", "items": [
            {"id": "item-1", "title": "Briefing", "detail": "", "kind": "Google Docs",
             "url": "https://docs.google.com/document/1", "artifact_id": "", "editor_url": "",
             "editable_copy_url": "", "download_url": ""},
            {"id": "item-2", "title": "Inválido", "detail": "", "kind": "Arquivo", "url": "",
             "artifact_id": "", "editor_url": "", "editable_copy_url": "", "download_url": ""},
        ]},
    ]


def test_response_blocks_do_not_replace_the_editorial_answer():
    answer = "\n\n".join([
        "Esta é a análise principal que deve permanecer integralmente na conversa.",
        "O componente abaixo complementa a leitura, mas não substitui a resposta.",
    ])
    response = normalize_response({
        "text": {"content": answer},
        "ui": {"blocks": [{"type": "questions", "title": "Para continuar", "items": [
            {"title": "Qual é o público prioritário?", "prompt": "O público prioritário é "},
        ]}]},
    }, {"mode": "analysis", "max_questions": 1, "max_next_steps": 0, "max_answer_chars": 6000})
    assert response.answer == answer
    assert response.blocks[0]["type"] == "questions"


def test_response_blocks_dedupe_ids_parse_boolean_strings_and_cap_density():
    response = normalize_response({
        "answer": "Escolha uma opção.",
        "blocks": [{"type": "decision", "items": [
            {"id": "same", "title": f"Opção {index}", "recommended": "false"}
            for index in range(8)
        ]}] * 3,
    }, {"mode": "decision", "max_questions": 0, "max_next_steps": 0, "max_answer_chars": 320})
    assert len(response.blocks) == 2
    assert len(response.blocks[0]["items"]) == 5
    assert len({item["id"] for item in response.blocks[0]["items"]}) == 5
    assert not any(item["recommended"] for item in response.blocks[0]["items"])


def test_response_blocks_support_compact_context_outputs():
    response = normalize_response({
        "answer": "A campanha ainda precisa de uma decisão.",
        "blocks": [
            {"type": "summary", "text": "Defina o público antes de escolher os canais."},
            {"type": "source_group", "title": "Fontes usadas", "items": [
                {"id": "briefing", "title": "Briefing da campanha", "resource_id": "resource-1"},
            ]},
            {"type": "warning", "title": "Dado ausente", "text": "O prazo ainda não foi informado."},
        ],
    }, {"mode": "analysis", "max_questions": 0, "max_next_steps": 0, "max_answer_chars": 320})
    assert [block["type"] for block in response.blocks] == ["summary", "source_group", "warning"]
    assert response.blocks[0]["text"] == "Defina o público antes de escolher os canais."
    assert response.blocks[1]["items"][0]["resource_id"] == "resource-1"


def test_response_blocks_normalize_single_source_output():
    response = normalize_response({
        "answer": "Consultei a fonte principal.",
        "blocks": [{
            "type": "source", "title": "Fonte principal",
            "resource": {"id": "resource-2", "title": "Plano de mídia", "kind": "artifact"},
        }],
    }, {"mode": "direct", "max_questions": 0, "max_next_steps": 0, "max_answer_chars": 320})
    assert response.blocks[0]["items"][0]["id"] == "resource-2"
    assert response.blocks[0]["items"][0]["kind"] == "artifact"


def test_dense_plain_answer_without_an_artifact_route_stays_in_chat():
    response = normalize_response("Um diagnóstico longo sem estrutura " * 40, {
        "mode": "analysis", "max_answer_chars": 320, "max_questions": 0,
        "max_next_steps": 0, "artifact_fallback_title": "Diagnóstico",
    })
    assert response.artifact_patch is None
    assert "artefato ao lado" not in response.answer.lower()


def test_plain_decision_list_becomes_an_interactive_decision_block():
    response = normalize_response("Escolha uma direção:\n- Editorial: mais autoral\n- Urbana: mais energia", {
        "mode": "decision", "max_answer_chars": 320, "max_questions": 0, "max_next_steps": 0,
    })
    assert response.answer == "Escolha uma direção:"
    assert response.blocks[0]["type"] == "decision"
    assert [item["title"] for item in response.blocks[0]["items"]] == ["Editorial", "Urbana"]


def test_normalizer_bounds_artifact_fields_and_citations():
    response = normalize_response({
        "answer": "Briefing iniciado.",
        "artifact_patch": {
            "title": "  Briefing  ",
            "summary": "  Base inicial  ",
            "fields": [{"key": " público ", "value": " moradores locais ", "state": "unknown"}],
        },
        "citations": [{"title": " Fonte ", "url": " https://example.com ", "excerpt": " Trecho "}],
    }, {"max_questions": 0, "max_next_steps": 0, "artifact_in_chat": False, "allow_artifact": True})
    assert response.artifact_patch["fields"] == [
        {"key": "público", "value": "moradores locais", "state": "inferred"}
    ]
    assert response.citations == [
        {"title": "Fonte", "url": "https://example.com", "excerpt": "Trecho"}
    ]


def test_artifact_first_recovers_dense_markdown_into_editable_sections():
    response = normalize_response("""### 1) Objetivo
**Fato:** lançar a campanha no próximo trimestre.

### 2) Entregas esperadas
- mensagem central
- plano de ativação

### 3) Riscos
- prazo ainda não confirmado
""", {
        "mode": "artifact_first",
        "artifact_type": "executive_summary",
        "artifact_fallback_title": "Leitura inicial do projeto",
        "artifact_chat_message": "Concluí a leitura inicial. Veja o artefato ao lado.",
        "max_answer_chars": 420,
        "max_questions": 1,
        "max_next_steps": 2,
        "allow_artifact": True,
    })
    assert response.answer == "Concluí a leitura inicial. Veja o artefato ao lado."
    assert response.artifact_patch["title"] == "Leitura inicial do projeto"
    assert [field["key"] for field in response.artifact_patch["fields"]] == [
        "1) Objetivo", "2) Entregas esperadas", "3) Riscos",
    ]
    assert "• mensagem central" in response.artifact_patch["fields"][1]["value"]


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


def test_registry_rejects_tool_output_that_breaks_its_published_contract():
    from aicentralv2.cadu_workspace.mcp.registry import ToolOutputError

    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="workspace.summary", description="Summary", capability="workspace", effect="read",
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}}},
        handler=lambda *_: {"name": "Contrato antigo"},
    ))
    with pytest.raises(ToolOutputError):
        registry.execute("workspace.summary", {}, context())


def test_registry_enforces_array_volume_limits():
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="workspace.bounded", description="Bounded", capability="workspace", effect="read",
        input_schema={
            "type": "object", "required": ["items"],
            "properties": {"items": {"type": "array", "maxItems": 2, "items": {"type": "string"}}},
            "additionalProperties": False,
        },
        handler=lambda _context, arguments: arguments,
    ))
    with pytest.raises(ToolInputError):
        registry.execute("workspace.bounded", {"items": ["a", "b", "c"]}, context())


def test_normalizer_accepts_fenced_json_without_showing_the_envelope():
    response = normalize_response('''```json
    {"answer":"Conclusão objetiva.","questions":[],"confidence":"high"}
    ```''', {"max_questions": 1, "artifact_in_chat": False})
    assert response.answer == "Conclusão objetiva."
    assert response.confidence == "medium"


def test_provider_source_block_does_not_upgrade_confidence_without_a_citation():
    response = normalize_response({
        "answer": "Resposta com fonte declarada.", "confidence": "high",
        "blocks": [{"type": "source_group", "title": "Fonte", "items": [{"title": "Não verificada"}]}],
    }, {"max_questions": 0, "max_next_steps": 0, "max_answer_chars": 320})
    assert response.confidence == "medium"


def test_v2_lab_and_migration_are_wired_for_deploy():
    root = Path(__file__).resolve().parents[1]
    app_factory = (root / "aicentralv2" / "__init__.py").read_text()
    routes = (root / "aicentralv2" / "cadu_workspace" / "agent_v2" / "routes.py").read_text()
    template = (root / "aicentralv2" / "templates" / "cadu_workspace" / "conversations_v2_lab.html").read_text()
    deploy = (root / "deploy.sh").read_text()
    assert "cadu_agent_v2_lab_bp" in app_factory
    assert 'lab_bp.get("/workspace/conversas-v2-lab")' in routes
    assert "cadu-conversations-v2-root" in template
    assert "cadu-conversations-v2-bootstrap" in template
    assert "conversations/react/app.js" in template
    assert "migrations/run_add_cadu_conversations_v2.py" in deploy


def test_published_message_route_enforces_csrf_and_streams_without_rollout_404(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["CADU_CONVERSATIONS_V2_ENABLED"] = False
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


def test_v2_page_creates_csrf_token_when_opened_directly(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(v2_routes.lab_bp)
    monkeypatch.setattr(v2_routes, "render_template", lambda *_args, **_kwargs: "ok")
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 7

    assert client.get("/workspace/conversas-v2-lab").status_code == 200
    with client.session_transaction() as session:
        assert len(session["family_csrf"]) >= 32


def test_public_html_artifact_does_not_require_a_session_and_keeps_tailwind_runtime(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(v2_routes.public_bp)
    monkeypatch.setattr(v2_routes, "get_public_artifact", lambda _artifact_id: {
        "id": _artifact_id, "type": "html", "title": "Relatório público", "status": "published",
        "content": {"html": "<main class='min-h-screen p-6'>Dados<script>alert(2)</script></main>", "css": ".x{color:red}", "js": "document.body.dataset.ready='1'", "logo_url": "/static/logo.svg", "primary_color": "#176b5e"},
    })

    response = app.test_client().get("/public/cadu/artifacts/11111111-1111-4111-8111-111111111111")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"/static/css/tailwind/artifact.css" in response.data
    assert b"data-cadu-brand-header" in response.data
    assert "sandbox allow-scripts" in response.headers["Content-Security-Policy"]
    assert "style-src 'self' 'unsafe-inline' http://localhost" in response.headers["Content-Security-Policy"]
    assert b"--cadu-brand-primary:#176b5e" in response.data
    assert b"/static/logo.svg" in response.data
    assert b"alert(2)" not in response.data
    assert b"Relat\xc3\xb3rio p\xc3\xbablico" in response.data
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_html_runtime_markup_keeps_tailwind_classes_and_removes_script_tags():
    response = normalize_response({
        "answer": "Página pronta.",
        "artifact_patch": {
            "title": "Página", "html": "<main class='p-6' onclick='alert(1)'><script>alert(2)</script><h1>OK</h1></main>",
            "css": ".x{color:red}", "js": "document.body.dataset.ready='1'", "logo_url": "/static/logo.svg",
            "primary_color": "#176b5e",
        },
    }, {"allow_artifact": True, "artifact_type": "html", "mode": "artifact_first", "max_questions": 0, "max_next_steps": 0})

    html = response.artifact_patch["html"]
    assert "class=\"p-6\"" in html
    assert "onclick" not in html
    assert "<script" not in html
    assert response.artifact_patch["logo_url"] == "/static/logo.svg"


def test_analysis_answer_preserves_natural_sentence_boundaries():
    response = normalize_response(
        {"answer": "A Nike combina performance e cultura. A oportunidade está em comunidade."},
        {"mode": "analysis", "max_questions": 0, "max_next_steps": 0},
    )

    assert response.answer == "A Nike combina performance e cultura. A oportunidade está em comunidade."


def test_html_artifact_publish_returns_public_url_with_csrf(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(v2_routes.public_bp)
    app.register_blueprint(v2_routes.bp)
    scoped = context(conversation_id="conversation")
    monkeypatch.setattr(v2_routes, "resolve", lambda **_: scoped)
    monkeypatch.setattr(v2_routes, "publish_artifact", lambda _current, artifact_id: {
        "id": artifact_id, "type": "html", "status": "published", "title": "Página",
    })
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 7
        session["family_csrf"] = "csrf"

    response = client.post(
        "/workspace/api/v2/artifacts/11111111-1111-4111-8111-111111111111/publish",
        json={"conversation_id": "conversation"}, headers={"X-CSRF-Token": "csrf"},
    )

    assert response.status_code == 200
    assert response.json["artifact"]["status"] == "published"
    assert response.json["url"].endswith("/public/cadu/artifacts/11111111-1111-4111-8111-111111111111")


def test_html_artifact_unpublish_revokes_public_status_with_csrf(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(v2_routes.bp)
    scoped = context(conversation_id="conversation")
    monkeypatch.setattr(v2_routes, "resolve", lambda **_: scoped)
    monkeypatch.setattr(v2_routes, "unpublish_artifact", lambda _current, artifact_id: {
        "id": artifact_id, "type": "html", "status": "draft", "title": "Página",
    })
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 7
        session["family_csrf"] = "csrf"

    response = client.post(
        "/workspace/api/v2/artifacts/11111111-1111-4111-8111-111111111111/unpublish",
        json={"conversation_id": "conversation"}, headers={"X-CSRF-Token": "csrf"},
    )

    assert response.status_code == 200
    assert response.json["artifact"]["status"] == "draft"


def test_brand_identity_route_accepts_the_brand_id_and_returns_context(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(v2_routes.bp)
    scoped = context(conversation_id=None)
    monkeypatch.setattr(v2_routes, "resolve", lambda **_: scoped)
    monkeypatch.setattr(v2_routes.repository, "entities", lambda *_: [{"ref": "studio:31", "kind": "brand"}])
    monkeypatch.setattr(v2_routes.repository, "project_brand_links", lambda *_: [])
    monkeypatch.setattr("aicentralv2.cadu_workspace.routes._workspace_brands", lambda *_: [{
        "id": 31, "name": "CentralComm", "display_logo": "/logo.png",
        "brand_profile": {"positioning": "Comunicação clara"},
        "primary_color": "#176b5e", "secondary_color": "#102a2a",
    }])
    monkeypatch.setattr("aicentralv2.cadu_workspace.routes._workspace_projects", lambda *_args, **_kwargs: [])
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 7

    response = client.get("/workspace/api/v2/brands/31/identity")

    assert response.status_code == 200
    assert response.json["artifact"]["content"]["name"] == "CentralComm"


def test_v2_stop_is_scoped_and_uses_v2_provider(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["CADU_CONVERSATIONS_V2_ENABLED"] = True
    app.register_blueprint(v2_routes.bp)
    scoped = context()
    monkeypatch.setattr(v2_routes, "resolve", lambda **_: scoped)
    monkeypatch.setattr(v2_routes.repository, "rows", lambda *_: [
        {"task_id": "task-v2", "status": "running", "execution_mode": "agentic"}
    ])
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
    monkeypatch.setattr(provider, "stop", lambda task_id, user, mode: stopped.append((task_id, user, mode)))
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=7, family_csrf="csrf")
    response = client.post(
        "/workspace/api/v2/runs/be777b36-a973-419c-802a-886bf1d125b0/stop",
        headers={"X-CSRF-Token": "csrf"},
    )
    assert response.status_code == 200
    assert stopped == [("task-v2", "user-7", "agentic")]


def test_v2_credit_admission_error_is_machine_readable():
    from werkzeug.exceptions import Conflict

    app = Flask(__name__)
    with app.app_context():
        response, status = v2_routes.api_error(Conflict(
            description="Saldo insuficiente: esta execução estima 8000 tokens e há 0 disponíveis."
        ))

    assert status == 409
    assert response.get_json() == {
        "error": "Saldo insuficiente: esta execução estima 8000 tokens e há 0 disponíveis.",
        "code": "credits_insufficient",
        "details": {"required_tokens": 8000, "available_tokens": 0},
    }


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
    monkeypatch.setattr(v2_service.provider, "events", lambda payload, mode: iter([
        {"event": "message", "task_id": "task-v2", "answer": '{"answer":"resposta tardia"}'},
        {"event": "message_end", "metadata": {"usage": {"completion_tokens": 3}}},
    ]))
    monkeypatch.setattr(v2_service.repository, "rows", lambda sql, *_: (
        [] if "cadu_agent_run_steps" in sql else [{"status": "cancelled"}]
    ))
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

    app = Flask(__name__)
    with app.app_context():
        output = "".join(v2_service.stream(run))

    assert '"status": "cancelled"' in output
    assert "answer.completed" not in output
    assert not any("INSERT INTO cadu_conversation_messages" in sql for sql in connection.statements)


def test_failed_v2_stream_emits_only_one_terminal_event(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            pass

        def rollback(self):
            pass

    def fail_provider(*_):
        raise v2_service.provider.ProviderUnavailable("provider offline")
        yield

    monkeypatch.setattr(v2_service.provider, "events", fail_provider)
    monkeypatch.setattr(v2_service.repository, "rows", lambda *_: [{"status": "running"}])
    monkeypatch.setattr(v2_service.repository, "get_db", lambda: Connection())
    monkeypatch.setattr(v2_service.journal, "record", lambda _run, kind, payload, **_: {"event": kind, **payload})
    monkeypatch.setattr(v2_service.journal, "complete_step", lambda *_: None)
    monkeypatch.setattr(v2_service.journal, "waiting_actions", lambda *_: [])
    run = {
        "run_id": "be777b36-a973-419c-802a-886bf1d125b0",
        "conversation_id": "conversation",
        "context": context(),
        "route": {"artifact_type": None},
        "policy": {"max_questions": 1, "max_next_steps": 1, "artifact_in_chat": False},
        "resolved_context": SimpleNamespace(tool_calls=[]),
        "provider_payload": {},
        "execution_mode": "analysis",
    }

    app = Flask(__name__)
    with app.app_context():
        output = "".join(v2_service.stream(run))

    assert output.count('"event": "run.failed"') == 1
    assert '"event": "run.completed"' not in output
    assert '"code": "provider_unavailable"' in output
    assert "temporariamente indisponível" in output


def test_provider_registry_selects_three_runtimes_and_supports_safe_rollout_fallback(monkeypatch):
    from aicentralv2.cadu_workspace.agent_v2 import provider
    monkeypatch.setattr(provider, "_shared_configuration", lambda: ("", ""))
    app = Flask(__name__)
    app.config.update(
        CADU_CONVERSATIONS_V2_DIFY_URL="https://legacy-v2.example/v1",
        CADU_CONVERSATIONS_V2_DIFY_KEY="fallback-key",
        CADU_DIFY_FAST_URL="https://fast.example/v1", CADU_DIFY_FAST_KEY="fast-key",
        CADU_DIFY_ANALYST_URL="https://analyst.example/v1", CADU_DIFY_ANALYST_KEY="analyst-key",
        CADU_DIFY_OPERATOR_URL="https://operator.example/v1", CADU_DIFY_OPERATOR_KEY="operator-key",
    )
    with app.app_context():
        assert provider.runtime_for("fast")["id"] == "cadu-fast"
        assert provider.runtime_for("analysis")["url"] == "https://analyst.example/v1"
        assert provider.runtime_for("agentic")["id"] == "cadu-operator"
        app.config["CADU_DIFY_FAST_URL"] = ""
        app.config["CADU_DIFY_FAST_KEY"] = ""
        fallback = provider.runtime_for("fast")
        assert fallback["url"] == "https://legacy-v2.example/v1"
        assert "key" not in fallback
        _, headers = provider.settings("fast")
        assert headers["Authorization"] == "Bearer fallback-key"
        app.config["CADU_DIFY_FAST_URL"] = "https://incomplete.example/v1"
        partial_fallback = provider.runtime_for("fast")
        assert partial_fallback["url"] == "https://legacy-v2.example/v1"
        assert partial_fallback["source"] == "legacy"
        app.config["CADU_CONVERSATIONS_V2_DIFY_URL"] = ""
        app.config["CADU_CONVERSATIONS_V2_DIFY_KEY"] = ""
        with pytest.raises(provider.ProviderUnavailable):
            provider.runtime_for("fast")
        monkeypatch.setattr(provider, "_shared_configuration", lambda: (
            "https://vault-dify.example/v1", "vault-key"
        ))
        shared = provider.runtime_for("fast")
        assert shared["url"] == "https://vault-dify.example/v1"
        assert shared["source"] == "centralx-integration"


def test_provider_preserves_answer_when_dify_errors_after_first_content(monkeypatch):
    from aicentralv2.cadu_workspace.agent_v2 import provider

    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def iter_lines(self, **_):
            return iter([
                'data: {"event":"message","answer":"Resposta útil"}',
                '',
                'data: {"event":"error","message":"upstream failed"}',
                '',
            ])

    monkeypatch.setattr(provider, "settings", lambda *_: ("https://dify.example/v1", {}))
    monkeypatch.setattr(provider.requests, "post", lambda *_, **__: Response())
    app = Flask(__name__)
    with app.app_context():
        events = list(provider.events({"query": "teste"}, "analysis"))

    assert events == [{"event": "message", "answer": "Resposta útil"}]


def test_provider_fails_when_dify_errors_before_any_content(monkeypatch):
    from aicentralv2.cadu_workspace.agent_v2 import provider

    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def iter_lines(self, **_):
            return iter([
                'data: {"event":"error","message":"upstream failed"}',
                '',
            ])

    monkeypatch.setattr(provider, "settings", lambda *_: ("https://dify.example/v1", {}))
    monkeypatch.setattr(provider.requests, "post", lambda *_, **__: Response())
    app = Flask(__name__)
    with app.app_context(), pytest.raises(provider.ProviderUnavailable):
        list(provider.events({"query": "teste"}, "analysis"))
