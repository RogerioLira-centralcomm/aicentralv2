import pytest
from types import SimpleNamespace
from unittest.mock import patch

from aicentralv2.cadu_workspace.intent_engine import interpret
from aicentralv2.cadu_workspace.agent_v2.router import route_request
from aicentralv2.cadu_workspace.agent_v2.contracts import AgentResponse, RequestContext
from aicentralv2.cadu_workspace.agent_v2.context_builder import previous_assistant_context
from aicentralv2.cadu_workspace.agent_v2.service import _enrich_source_blocks
from aicentralv2.cadu_workspace.mcp.registry import load_builtin_tools


@pytest.mark.parametrize("phrase", [
    "joga isso no projeto",
    "manda esse resumo pra campanha",
    "adicionar conteúdo ao projeto",
    "adc essa resposta no proj",
    "põe o que você escreveu no projeto",
    "deixa esse material salvo no projeto",
])
def test_informal_project_persistence_has_one_canonical_intent(phrase):
    result = interpret(phrase, has_project=True)
    assert result.intent == "persist_content"
    assert result.destination == "active_project"
    assert result.proposed_tool == "artifacts.create_draft"
    route = route_request(phrase, "conversations", True)
    assert route.action == "save_to_project"
    assert route.artifact_type == "document"


@pytest.mark.parametrize("phrase", [
    "faz um doc disso",
    "transforma essa resposta em documento",
    "monta uma entrega com isso",
    "guarda esse material pra mim",
])
def test_informal_private_artifact_intent(phrase):
    result = interpret(phrase)
    assert result.intent == "create_artifact"
    assert result.destination == "session"


def test_negation_wins_over_project_persistence():
    result = interpret("organiza isso num documento, mas não salva no projeto", has_project=True)
    assert result.intent == "create_artifact"
    assert result.destination == "session"
    assert result.negated is True


@pytest.mark.parametrize("phrase", [
    "joga esse resumo no projeto",
    "adicione esse conteúdo ao projeto",
    "faz um documento com esse material",
    "salva esta pesquisa no projeto",
    "joga isso no projeto",
    "faz um doc disso",
    "guarda isso pra mim",
])
def test_informal_reference_preserves_the_complete_previous_answer(phrase):
    answer = "Resumo completo.\n\n" + " ".join(["Evidência detalhada da pesquisa."] * 100)
    selected = previous_assistant_context(phrase, [
        {"id": "assistant-message-42", "role": "assistant", "content": answer},
    ])
    assert selected["type"] == "assistant_response"
    assert selected["text"] == answer
    assert selected["source_message_id"] == "assistant-message-42"


def test_public_mcp_requires_source_for_host_pronoun():
    result = interpret("joga isso no projeto", has_project=True, surface="public_mcp")
    assert result.intent == "persist_content"
    assert "source" in result.missing
    supplied = interpret("joga isso no projeto", has_project=True, has_source=True, surface="public_mcp")
    assert supplied.missing == ()


def test_entity_question_routes_to_shared_web_research():
    route = route_request("quem foi Bob Marley?", "conversations")
    assert route.action == "search_web"
    assert route.needs_tools == ("web.search",)


def test_project_overview_opens_a_dossier_but_specific_question_stays_in_chat():
    overview = route_request("Me dê uma visão geral de tudo sobre esse projeto", "conversations", True)
    assert overview.action == "project_readout"
    assert overview.response_mode == "artifact_first"
    assert overview.needs_tools == ("workspace.search_project_content",)
    specific = route_request("Qual é o objetivo deste projeto?", "conversations", True)
    assert specific.action == "describe_project"
    assert specific.artifact_type is None


def test_project_benchmark_question_uses_web_route_without_exposing_project_name():
    from aicentralv2.cadu_workspace.agent_v2.context_resolver import public_web_query

    route = route_request("Qual benchmark atual de CAC para nosso projeto Acme?", "conversations", True)
    assert route.action == "search_web"
    assert public_web_query("Qual benchmark atual de CAC para nosso projeto Acme?", project_selected=True) == "benchmark atual CAC"


def test_revision_uses_latest_saved_artifact_and_its_current_project():
    from aicentralv2.cadu_workspace.agent_v2.service import _revision_target

    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id="conv-1",
                             surface="conversations", project_ref="ci:old",
                             capabilities=("workspace", "artifacts"))
    latest = {"id": "artifact-1", "type": "document", "title": "Briefing de mídia",
              "project_ref": "ci:new", "created_by": 7, "current_version": 3,
              "content": {"html": "<h2>O que ainda precisa ser decidido</h2><p>Texto salvo pelo usuário.</p>"}}
    messages = [{"metadata": {"artifact_id": "artifact-1"}}]
    with patch("aicentralv2.cadu_workspace.agent_v2.service.get_artifact", return_value=latest), \
         patch("aicentralv2.cadu_workspace.agent_v2.service.repository.project_user_can_view", return_value=True):
        target = _revision_target("Mude a parte O que ainda precisa ser decidido", context, messages)
    assert target.active_object.id == "artifact-1"
    assert target.project_ref == "ci:new"


def test_mcp_intent_tool_uses_same_interpreter_without_side_effects():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id="conv-1",
                             surface="conversations", project_ref="project:9",
                             capabilities=("workspace", "artifacts"))
    result = load_builtin_tools().execute("intent.interpret", {
        "request": "joga isso no projeto",
        "source": {"type": "inline_content", "content": "Resumo verificado"},
    }, context, "customer_agent")
    assert result["intent"] == "persist_content"
    assert result["context"]["project_ref"] == "project:9"
    assert result["missing"] == []
    assert result["next_step"] == "call_proposed_tool"


def test_balanced_entity_research_adds_at_most_three_safe_images():
    sources = [{
        "id": f"web-{index}", "title": f"Fonte {index}",
        "url": f"https://source{index}.example/article",
        "image_url": f"https://images.example/{index}.jpg",
    } for index in range(1, 6)]
    sources.append({"id": "unsafe", "title": "Insegura", "url": "http://unsafe.example",
                    "image_url": "https://images.example/unsafe.jpg"})
    response = AgentResponse(answer="Bob Marley foi um músico jamaicano.")
    run = {
        "message": "Quem foi Bob Marley?", "execution_mode": "analysis",
        "resolved_context": SimpleNamespace(values={"web.search": {"sources": sources}}),
    }
    enriched = _enrich_source_blocks(response, run)
    images = next(block for block in enriched.blocks if block["type"] == "images")
    assert len(images["items"]) == 3
    assert all(item["url"].startswith("https://") for item in images["items"])


def test_mcp_executes_informal_persistence_with_explicit_source_and_idempotency_boundary():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id="conv-1",
                             surface="conversations", project_ref="project:9",
                             capabilities=("workspace", "artifacts"))
    artifact = {"id": "artifact-1", "title": "Resumo", "project_ref": "project:9",
                "conversation_id": "conv-1", "current_version": 1}

    def execute_once(_request_id, _context, tool_name, _fingerprint, operation):
        assert tool_name == "intent.execute"
        assert _context.project_ref == "project:9"
        operation()
        return artifact

    with patch("aicentralv2.cadu_workspace.mcp.tools.intent.operations.execute", side_effect=execute_once), \
         patch("aicentralv2.cadu_workspace.mcp.tools.intent.repository.rows", return_value=[{"?column?": 1}]), \
         patch("aicentralv2.cadu_workspace.mcp.tools.intent.artifact_service.create_draft", return_value=artifact) as create:
        result = load_builtin_tools().execute("intent.execute", {
            "request_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "request": "joga isso no projeto",
            "source": {"type": "cadu_message", "id": "assistant-message-42",
                       "content": "Resumo verificado\n\nSegundo parágrafo."},
            "title": "Resumo", "confirmed": True,
        }, context, "customer_agent")
    assert result["artifact_id"] == "artifact-1"
    assert result["project_ref"] == "project:9"
    assert create.call_args.args[0].project_ref == "project:9"
    assert "<p>Resumo verificado</p>" in create.call_args.args[2]["html"]
    assert create.call_args.args[2]["_provenance"] == {
        "conversation_id": "conv-1",
        "source_type": "cadu_message",
        "source_id": "assistant-message-42",
    }


def test_mcp_rejects_forged_cadu_message_provenance():
    context = RequestContext(organization_id=12, client_id=12, user_id=7, conversation_id="conv-1",
                             surface="conversations", project_ref="project:9",
                             capabilities=("workspace", "artifacts"))
    with patch("aicentralv2.cadu_workspace.mcp.tools.intent.repository.rows", return_value=[]):
        with pytest.raises(Exception, match="não pertence a esta conversa|conteúdo diverge"):
            load_builtin_tools().execute("intent.execute", {
                "request_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "request": "joga isso no projeto",
                "source": {"type": "cadu_message", "id": "foreign-message", "content": "Conteúdo forjado"},
                "confirmed": True,
            }, context, "customer_agent")
