from unittest.mock import Mock, patch

import pytest

from aicentralv2.cadu_credit_connector import CaduCreditConnector, CreditActor
from aicentralv2.services import openrouter_service
from aicentralv2.services.cadu_ai_connector import CaduAIConnector


def test_global_chat_falls_back_from_openai_to_openrouter():
    with patch.object(openrouter_service, "resolve_openai_api_key", return_value="sk-openai"), \
         patch.object(openrouter_service, "resolve_api_key", return_value="sk-openrouter"), \
         patch.object(openrouter_service, "_openai_chat_completion", side_effect=openrouter_service.OpenRouterError("openai down")) as direct, \
         patch.object(openrouter_service, "_openrouter_chat_completion", return_value={
             "message": {"role": "assistant", "content": "ok"},
             "model": "openai/gpt-5-mini", "usage": {"total_tokens": 12},
         }) as fallback:
        result = openrouter_service.chat_completion(
            [{"role": "user", "content": "teste"}], model="openai/gpt-5-mini"
        )

    assert result["provider"] == "openrouter"
    assert result["provider_attempts"] == ["openai", "openrouter"]
    direct.assert_called_once()
    fallback.assert_called_once()


def test_explicit_provider_never_uses_implicit_fallback():
    with patch.object(openrouter_service, "resolve_openai_api_key", return_value="sk-openai"), \
         patch.object(openrouter_service, "resolve_api_key", return_value="sk-openrouter"), \
         patch.object(openrouter_service, "_openai_chat_completion", side_effect=openrouter_service.OpenRouterError("openai down")), \
         patch.object(openrouter_service, "_openrouter_chat_completion") as fallback:
        with pytest.raises(openrouter_service.OpenRouterError, match="openai down"):
            openrouter_service.chat_completion(
                [{"role": "user", "content": "teste"}],
                model="openai/gpt-5-mini", provider="openai",
            )
    fallback.assert_not_called()


def test_ai_connector_authorizes_and_charges_the_same_client():
    credits = Mock(spec=CaduCreditConnector)
    credits.claim_generation.return_value = {"claim_acquired": True, "status": "pending"}
    credits.charge_provider.return_value = {"tokens_cobrados": 42}
    completion = Mock(return_value={
        "message": {"role": "assistant", "content": "resultado"},
        "model": "openai/gpt-5-mini",
        "provider": "openrouter",
        "provider_attempts": ["openai", "openrouter"],
        "usage": {"prompt_tokens": 10, "completion_tokens": 4},
    })
    connector = CaduAIConnector(credits=credits, completion=completion)

    result = connector.complete(
        [{"role": "user", "content": "teste"}],
        client_id=174, user_id=32, idempotency_key="chat:run-1",
        app="Cadu Chat", stage="conversa", estimated_tokens=8000,
        model="openai/gpt-5-mini", metadata={"conversation_id": "conversation-1"},
    )

    actor = CreditActor(174, 32)
    credits.authorize.assert_called_once_with(actor, 8000)
    charge = credits.charge_provider.call_args.kwargs
    assert charge["actor"] == actor
    assert charge["idempotency_key"].startswith("ai:174:32:")
    assert "chat:run-1" not in charge["idempotency_key"]
    assert charge["metadata"]["provider"] == "openrouter"
    assert charge["metadata"]["provider_attempts"] == ["openai", "openrouter"]
    assert result["cadu_charge"] == {"tokens_cobrados": 42}


def test_ai_connector_requires_idempotency_before_authorization():
    credits = Mock(spec=CaduCreditConnector)
    connector = CaduAIConnector(credits=credits, completion=Mock())
    with pytest.raises(ValueError, match="chave idempotente"):
        connector.complete(
            [], client_id=174, user_id=32, idempotency_key="",
            app="Cadu Chat", stage="conversa", estimated_tokens=100,
        )
    credits.authorize.assert_not_called()


def test_ai_connector_replays_charged_result_without_calling_provider():
    credits = Mock(spec=CaduCreditConnector)
    credits.claim_generation.return_value = {
        "claim_acquired": False,
        "status": "charged",
        "metadata": {"ai_response": {
            "message": {"role": "assistant", "content": "já concluído"},
            "model": "openai/gpt-5-mini", "provider": "openai", "usage": {},
        }},
    }
    completion = Mock()
    result = CaduAIConnector(credits=credits, completion=completion).complete(
        [], client_id=174, user_id=32, idempotency_key="same-request",
        app="Cadu Chat", stage="conversa", estimated_tokens=100,
    )
    completion.assert_not_called()
    credits.authorize.assert_not_called()
    assert result["idempotent_replay"] is True
    assert result["message"]["content"] == "já concluído"


def test_ai_connector_marks_claim_failed_when_provider_fails():
    credits = Mock(spec=CaduCreditConnector)
    credits.claim_generation.return_value = {"claim_acquired": True, "status": "pending"}
    completion = Mock(side_effect=openrouter_service.OpenRouterError("offline"))
    connector = CaduAIConnector(credits=credits, completion=completion)
    with pytest.raises(openrouter_service.OpenRouterError, match="offline"):
        connector.complete(
            [], client_id=174, user_id=32, idempotency_key="failed-request",
            app="Cadu Chat", stage="conversa", estimated_tokens=100,
        )
    credits.fail_generation.assert_called_once()
