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
