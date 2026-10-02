from unittest.mock import Mock, patch

import pytest

from aicentralv2.services import typesafe_service


@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.get_configuration", return_value={"default_model": "jev-latest"})
@patch("aicentralv2.services.typesafe_service.requests.post")
def test_system_one_sends_the_documented_http_contract(post, _configuration, _api_key):
    response = Mock(status_code=200)
    response.json.return_value = {
        "model": "jev-1.13.0",
        "answers": {"official": {"type": "noul", "noul": 0.97}},
        "usage": {"input_tokens": 80, "output_tokens": 8},
    }
    post.return_value = response
    state = {"brand": "Acme", "website": "https://acme.example"}
    questions = {
        "official": {
            "type": "noul",
            "instructions": "Is this the official website for the brand in `brand`?",
            "criteria": {"true": "First-party site", "false": "Unrelated site"},
        },
    }

    result = typesafe_service.system_one(state, questions, timeout=12)

    assert result["answers"]["official"]["noul"] == 0.97
    post.assert_called_once_with(
        "https://api.typesafe.ai/v1/systemone",
        headers={
            "Authorization": "Bearer secret",
            "Content-Type": "application/json",
        },
        json={"state": state, "model": "jev-latest", "questions": questions},
        timeout=12,
    )


@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.requests.post")
def test_system_one_rejects_a_response_without_typed_answers(post, _api_key):
    response = Mock(status_code=200)
    response.json.return_value = {"model": "jev-1.13.0", "usage": {}}
    post.return_value = response

    with pytest.raises(typesafe_service.TypeSafeError, match="respostas tipadas"):
        typesafe_service.system_one("state", {"official": {"type": "noul", "instructions": "Is it?"}})


@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.requests.post")
def test_system_one_reports_provider_rate_limit_without_fallback_payload(post, _api_key):
    post.return_value = Mock(status_code=429)

    with pytest.raises(typesafe_service.TypeSafeError, match="limitou as chamadas"):
        typesafe_service.system_one("state", {"official": {"type": "noul", "instructions": "Is it?"}})


QUESTION = {"official": {"type": "noul", "instructions": "Is it?"}}
GOOD_BODY = {
    "model": "jev-1.13.0",
    "answers": {"official": {"type": "noul", "noul": 0.9}},
    "usage": {"input_tokens": 5, "output_tokens": 1},
}


def _response(status, body=None):
    response = Mock(status_code=status, headers={})
    response.json.return_value = body
    return response


@patch("aicentralv2.services.typesafe_service.time.sleep")
@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.requests.post")
def test_system_one_retries_transient_gateway_errors(post, _api_key, sleep):
    post.side_effect = [_response(503), _response(200, GOOD_BODY)]

    assert typesafe_service.system_one("state", QUESTION)["model"] == "jev-1.13.0"
    assert post.call_count == 2
    sleep.assert_called_once()


@patch("aicentralv2.services.typesafe_service.time.sleep")
@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.requests.post")
def test_system_one_retries_timeouts_then_reports_connection_failure(post, _api_key, _sleep):
    post.side_effect = typesafe_service.requests.Timeout("slow")

    with pytest.raises(typesafe_service.TypeSafeError, match="conectar"):
        typesafe_service.system_one("state", QUESTION, attempts=2)
    assert post.call_count == 2


@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.requests.post")
def test_system_one_does_not_retry_rejected_credentials(post, _api_key):
    post.return_value = _response(401)

    with pytest.raises(typesafe_service.TypeSafeError, match="credencial"):
        typesafe_service.system_one("state", QUESTION)
    assert post.call_count == 1


@pytest.mark.parametrize("answer", [
    {"type": "noul"},
    {"type": "score", "score": 0.5},
    {"type": "noul", "noul": True},
    {"type": "noul", "noul": "high"},
])
@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.requests.post")
def test_system_one_rejects_answers_that_do_not_match_the_question_type(post, _api_key, answer):
    body = {**GOOD_BODY, "answers": {"official": answer}}
    post.return_value = _response(200, body)

    with pytest.raises(typesafe_service.TypeSafeError, match="formato inválido"):
        typesafe_service.system_one("state", QUESTION)


@pytest.mark.parametrize("questions, state", [
    ({}, "state"),
    ({"q": {"type": "other", "instructions": "x"}}, "state"),
    ({"q": {"type": "noul"}}, "state"),
    (QUESTION, {"value": float("nan")}),
    (QUESTION, 42),
])
@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.requests.post")
def test_system_one_rejects_invalid_input_before_calling_the_api(post, _api_key, questions, state):
    with pytest.raises(typesafe_service.TypeSafeError):
        typesafe_service.system_one(state, questions)
    post.assert_not_called()


@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.get_configuration", return_value={"default_model": "jev-custom"})
@patch("aicentralv2.services.typesafe_service.requests.post")
def test_system_one_uses_the_configured_model(post, _configuration, _api_key):
    post.return_value = _response(200, GOOD_BODY)

    typesafe_service.system_one("state", QUESTION)

    assert post.call_args.kwargs["json"]["model"] == "jev-custom"


@patch("aicentralv2.services.typesafe_service.resolve_typesafe_api_key", return_value="secret")
@patch("aicentralv2.services.typesafe_service.get_configuration", return_value={})
def test_timeouts_that_use_up_the_deadline_raise_a_typesafe_error(_configuration, _api_key):
    import requests

    clock = [0.0]

    def slow_post(*_args, **_kwargs):
        clock[0] += 31  # each timeout burns half of the 60 s deadline
        raise requests.Timeout("slow")

    with patch.object(typesafe_service.time, "monotonic", lambda: clock[0]), \
            patch.object(typesafe_service.time, "sleep", lambda _seconds: None), \
            patch.object(typesafe_service.requests, "post", slow_post):
        with pytest.raises(typesafe_service.TypeSafeError, match="Não foi possível conectar"):
            typesafe_service.system_one({"a": 1}, {"q": {"type": "noul", "instructions": "x"}})


def test_retry_waits_never_go_past_the_deadline():
    with patch.object(typesafe_service.time, "monotonic", lambda: 59.0):
        assert typesafe_service._bounded_delay(4.0, deadline=60.0) == 1.0
        assert typesafe_service._bounded_delay(4.0, deadline=58.0) == 0.0


@pytest.mark.parametrize("value", [1.5, -0.1, float("nan"), float("inf"), True])
def test_a_noul_outside_zero_to_one_or_not_finite_is_rejected(value):
    assert typesafe_service._valid_answer({"type": "noul", "noul": value}, "noul") is False


def test_valid_noul_score_and_choice_answers_are_accepted():
    assert typesafe_service._valid_answer({"type": "noul", "noul": 0.97}, "noul")
    assert typesafe_service._valid_answer({"type": "score", "score": 7}, "score")
    assert typesafe_service._valid_answer({"type": "choice", "choice": "a"}, "choice")
    assert not typesafe_service._valid_answer({"type": "score", "score": float("nan")}, "score")
