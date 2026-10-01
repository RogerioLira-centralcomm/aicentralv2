"""Apps with the flat structured-output schema get a matching contract; the legacy app is untouched."""
import copy
import json

import pytest
from flask import Flask

from aicentralv2.cadu_workspace.agent_v2 import provider
from aicentralv2.cadu_workspace.agent_v2.contracts import RequestContext
from aicentralv2.cadu_workspace.agent_v2.guardrails import normalize_response
from aicentralv2.cadu_workspace.agent_v2.prompt_assembler import (
    CORE, FLAT_OUTPUT_CONTRACT, adapt_output_format, build_payload,
)
from aicentralv2.cadu_workspace.agent_v2.response_policy import policy_for
from aicentralv2.cadu_workspace.agent_v2.router import route_request


def make_payload():
    request = RequestContext(client_id=12, user_id=7, conversation_id="c", surface="conversations",
                             project_ref="ci:1", capabilities=("workspace",))
    route = route_request("qual a verba?", has_project=True)
    return build_payload(message="qual a verba?", request=request, route=route, resolved={"current_context": {}},
                         policy=policy_for(route), user_label="user-7")


def test_nested_runtime_payload_is_left_exactly_as_before():
    payload = make_payload()
    before = copy.deepcopy(payload)
    assert adapt_output_format(payload, "nested") == before
    assert adapt_output_format(payload, None) == before


def test_flat_runtime_gets_answer_contract_and_core_without_nested_names():
    payload = adapt_output_format(make_payload(), "flat")
    inputs = payload["inputs"]
    assert json.loads(inputs["output_contract"]) == FLAT_OUTPUT_CONTRACT
    assert "text.content" not in inputs["core"] and "ui.questions" not in inputs["core"]
    assert "`answer` é a resposta visível" in inputs["core"]
    assert "artifact_patch` vazio" in inputs["core"]
    assert inputs["skill_context"] == inputs["core"]
    assert "text.content" in CORE, "the shared CORE constant must stay unchanged for nested runtimes"


def test_flat_schema_keys_match_the_dify_structured_output():
    assert set(FLAT_OUTPUT_CONTRACT) == {"answer", "questions", "actions", "assumptions", "citations",
                                         "confidence", "artifact_patch"}
    assert set(FLAT_OUTPUT_CONTRACT["artifact_patch"]) == {"title", "summary", "fields"}


def test_backend_reads_the_flat_envelope_and_ignores_the_empty_artifact():
    policy = {"mode": "direct", "max_questions": 1, "max_next_steps": 2, "max_answer_chars": 3000,
              "allow_artifact": False, "artifact_type": None}
    flat = {"answer": "A verba aprovada é R$ 50 mil para Google Ads.", "questions": [], "actions": [],
            "assumptions": [], "citations": [], "confidence": "high",
            "artifact_patch": {"title": "", "summary": "", "fields": []}}
    response = normalize_response(json.dumps(flat), policy)
    assert response.answer.startswith("A verba aprovada") and response.artifact_patch is None


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config.update(CADU_DIFY_FAST_URL="https://dify.example/v1", CADU_DIFY_FAST_KEY="k")
    return app


def test_output_format_follows_the_credential_source(app, monkeypatch):
    monkeypatch.delenv("CADU_DIFY_OUTPUT_FORMAT", raising=False)
    monkeypatch.setattr(provider, "_chat_configuration", lambda: ("https://legacy.example/v1", "legacy"))
    with app.app_context():
        assert provider._configuration("fast")["output_format"] == "flat"      # mode-specific variables
        assert provider._configuration("analysis")["output_format"] == "nested"  # fallback credential
        assert provider._configuration("agentic")["output_format"] == "nested"


def test_operator_with_its_own_credentials_still_gets_the_rich_nested_contract(app, monkeypatch):
    monkeypatch.delenv("CADU_DIFY_OUTPUT_FORMAT", raising=False)
    monkeypatch.setattr(provider, "_chat_configuration", lambda: ("https://legacy.example/v1", "legacy"))
    app.config.update(CADU_DIFY_OPERATOR_URL="https://dify.example/v1", CADU_DIFY_OPERATOR_KEY="k")
    with app.app_context():
        config = provider._configuration("agentic")
        assert config["source"] == "mode-specific" and config["output_format"] == "nested"
    app.config["CADU_DIFY_OPERATOR_OUTPUT_FORMAT"] = "flat"
    with app.app_context():
        assert provider._configuration("agentic")["output_format"] == "flat"


def test_output_format_can_be_forced(app, monkeypatch):
    monkeypatch.setattr(provider, "_chat_configuration", lambda: ("https://legacy.example/v1", "legacy"))
    monkeypatch.setenv("CADU_DIFY_OUTPUT_FORMAT", "nested")
    with app.app_context():
        assert provider._configuration("fast")["output_format"] == "nested"
    monkeypatch.setenv("CADU_DIFY_OUTPUT_FORMAT", "flat")
    with app.app_context():
        assert provider._configuration("analysis")["output_format"] == "flat"


def _artifact_policy(artifact_type="meeting_agenda"):
    return {"mode": "artifact_first", "artifact_type": artifact_type, "allow_artifact": True,
            "max_answer_chars": 8000, "max_questions": 1, "max_next_steps": 2,
            "artifact_chat_message": "Organizei o resultado em uma versão editável."}


EMPTY_PATCH = {"title": "", "summary": "", "fields": []}


def _envelope(answer, patch):
    return json.dumps({"answer": answer, "questions": [], "actions": [], "assumptions": [], "citations": [],
                       "confidence": "medium", "artifact_patch": patch}, ensure_ascii=False)


def test_empty_patch_from_the_flat_schema_means_no_artifact():
    response = normalize_response(_envelope("Pauta: status, verba e próximos passos. " * 5, EMPTY_PATCH), _artifact_policy())
    assert not response.artifact_patch or response.artifact_patch.get("fields")
    # the artifact-first fallback may build one from the answer, but never an empty record
    if response.artifact_patch:
        assert any(str(f.get("value") or "").strip() for f in response.artifact_patch["fields"]) \
            or str(response.artifact_patch.get("html") or "").strip()


def test_filled_patch_is_kept_untouched():
    patch = {"title": "Pauta", "summary": "Alinhamento", "fields": [
        {"key": "Objetivo", "value": "Alinhar o lançamento", "state": "confirmed"}]}
    response = normalize_response(_envelope("Preparei a pauta.", patch), _artifact_policy())
    assert response.answer == "Preparei a pauta."
    assert response.artifact_patch["title"] == "Pauta" and response.artifact_patch["fields"][0]["key"] == "Objetivo"


def test_missing_state_field_counts_as_content():
    patch = {"title": "Ata", "summary": "", "fields": [{"key": "Decisões", "value": "", "state": "missing"}]}
    assert normalize_response(_envelope("Ata parcial.", patch), _artifact_policy("meeting_summary")).artifact_patch


def test_empty_html_patch_still_fails_closed_with_the_visual_message():
    response = normalize_response(_envelope("Pronto.", {"title": "", "summary": "", "fields": []}), _artifact_policy("html"))
    assert response.artifact_patch is None and "conteúdo visual" in response.answer
