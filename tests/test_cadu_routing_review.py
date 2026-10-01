"""Artifact and plugin routing review: right Dify app per artifact, no creative-concept hijack."""
import json

import pytest

from aicentralv2.cadu_workspace.agent_v2.contracts import FLAT_SCHEMA_ARTIFACTS, IntentRoute, execution_mode_for
from aicentralv2.cadu_workspace.agent_v2.router import route_request


def route(artifact_type, complexity="medium", confirm=False):
    return IntentRoute("workspace", "x", complexity, "artifact_first", (), (), artifact_type, confirm)


@pytest.mark.parametrize("artifact_type", ["brief", "meeting_summary", "meeting_agenda"])
def test_flat_schema_artifacts_stay_on_the_analysis_app(artifact_type):
    assert artifact_type in FLAT_SCHEMA_ARTIFACTS
    assert execution_mode_for(route(artifact_type)) == "analysis"


@pytest.mark.parametrize("artifact_type", ["document", "media_plan", "scenario", "research",
                                           "executive_summary", "note", "html", "project_map"])
def test_artifacts_with_html_tables_or_metrics_run_on_the_operator(artifact_type):
    assert execution_mode_for(route(artifact_type)) == "agentic"


def test_requested_fast_mode_never_downgrades_a_rich_artifact():
    assert execution_mode_for(route("document"), "fast") == "agentic"


def test_non_artifact_work_keeps_its_previous_mode():
    assert execution_mode_for(IntentRoute("workspace", "answer", "low", "direct")) == "fast"
    assert execution_mode_for(IntentRoute("workspace", "analyze", "medium", "analysis", (), ("x",))) == "analysis"


@pytest.mark.parametrize("message", [
    "Crie um conceito criativo para a campanha de lançamento",
    "Quero três rotas criativas para o Dia das Mães",
    "Desenvolva a direção criativa do projeto",
    "Preciso de uma plataforma criativa para a marca",
])
def test_creative_strategy_is_not_an_image_request(message):
    assert not route_request(message).action.startswith("studio_")


@pytest.mark.parametrize("message", [
    "Crie uma imagem para o post de lançamento",
    "Gere um criativo para o anúncio",
    "Crie uma arte para o banner",
    "Edite a imagem para ficar mais clara",
])
def test_real_image_requests_still_reach_the_studio(message):
    assert route_request(message).action in {"studio_create_image", "studio_edit_image"}


from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.agent_v2.prompt_assembler import build_payload
from aicentralv2.cadu_workspace.agent_v2.response_policy import policy_for


def payload_for(message, **policy_overrides):
    request = RequestContext(client_id=1, user_id=7, conversation_id="c", surface="conversations", capabilities=("workspace",))
    selected = route_request(message)
    policy = {**policy_for(selected), **policy_overrides}
    return build_payload(message=message, request=request, route=selected, resolved={"current_context": {}},
                         policy=policy, user_label="user-7")["inputs"]


@pytest.mark.parametrize("message", [
    "Prepare a pauta da reunião de alinhamento do lançamento",
    "Monte o plano da campanha de lançamento",
    "Revise a marca no relatório de campanha",
])
def test_entity_depth_instruction_is_not_added_to_ordinary_marketing_tasks(message):
    assert "pergunta sobre uma pessoa, marca ou campanha" not in payload_for(message)["core"]


@pytest.mark.parametrize("message", ["Quem é Ogilvy?", "Fale sobre a campanha Dove Real Beleza", "Qual a história da Nike?"])
def test_entity_depth_instruction_still_applies_to_questions_about_an_entity(message):
    assert "pergunta sobre uma pessoa, marca ou campanha" in payload_for(message)["core"]


def test_response_policy_sent_to_the_model_has_no_duplicated_or_internal_fields():
    inputs = payload_for("qual a verba?", plugin_instruction="x" * 500, artifact_fallback_title="t",
                         artifact_chat_message="m", max_output_tokens=900, max_duration_ms=1)
    sent = json.loads(inputs["response_policy"])
    for key in ("plugin_instruction", "artifact_fallback_title", "artifact_chat_message",
                "max_output_tokens", "max_duration_ms"):
        assert key not in sent
    assert sent["mode"] and "max_answer_chars" in sent


def test_meeting_plugin_artifact_does_not_ask_for_tables_or_images():
    from aicentralv2.cadu_workspace.agent_v2 import executor, plugins
    from aicentralv2.cadu_workspace.agent_v2.context_resolver import ResolvedContext
    plugins.get_plugin = lambda pid: {"id": pid, "name": pid, "maturity": "active", "internal_tools": [],
                                      "manifest": {}, "selectable": True, "version": "1"}
    executor.recent_preferences = lambda *a, **k: []
    executor.resolve_context = lambda route, request, *a, **k: ResolvedContext(values={"current_context": {}}, tool_calls=[])
    request = RequestContext(client_id=1, user_id=7, conversation_id="c", surface="conversations",
                             project_ref="ci:t", capabilities=("workspace",))
    agenda = executor.prepare_execution("/meeting-copilot Prepare a pauta da reunião de amanhã", request)
    assert agenda["route"]["artifact_type"] == "meeting_agenda"
    assert "tabelas para comparações" not in agenda["provider_payload"]["inputs"]["core"]
    document = executor.prepare_execution("Analise o relatório da campanha em anexo", request,
                                          has_report_attachment=True)
    assert document["route"]["artifact_type"] == "document"
    assert document["execution_mode"] == "agentic"
    assert "tabelas para comparações" in document["provider_payload"]["inputs"]["core"]


@pytest.mark.parametrize("message", ["Faça uma imagem do produto", "Faça a imagem do lançamento", "Façam uma ilustração para o post"])
def test_imperative_faca_reaches_the_studio_for_images(message):
    assert route_request(message).action == "studio_create_image"


def test_imperative_faca_reaches_the_studio_for_video():
    assert route_request("Faça um vídeo curto do produto").action.startswith("studio_")
