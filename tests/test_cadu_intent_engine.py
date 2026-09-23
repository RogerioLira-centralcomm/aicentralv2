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
