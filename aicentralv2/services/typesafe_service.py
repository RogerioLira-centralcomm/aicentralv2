"""Small server-side client for TypeSafe System One evaluations."""

import json
import time

import requests

from .integration_credentials import (
    _typesafe_retry_delay,
    get_configuration,
    resolve_typesafe_api_key,
)


API_URL = "https://api.typesafe.ai/v1/systemone"


class TypeSafeError(RuntimeError):
    """A safe-to-log TypeSafe API failure without credentials or raw payloads."""


def system_one(state, questions, *, model=None, timeout=30):
    """Evaluate typed questions against application state and return the API body.

    Keep the question set narrow and include every answer needed from the same
    state in one call. The TypeSafe key is resolved from the encrypted admin
    integration first, with the server environment as fallback.
    """
    api_key = resolve_typesafe_api_key()
    if not api_key:
        raise TypeSafeError("A integração TypeSafe não está configurada.")
    if not isinstance(questions, dict) or not questions:
        raise TypeSafeError("Informe ao menos uma pergunta TypeSafe.")
    if not isinstance(state, (str, dict, list)):
        raise TypeSafeError("O contexto da avaliação TypeSafe tem formato inválido.")
    try:
        json.dumps({"state": state, "questions": questions}, allow_nan=False)
    except (TypeError, ValueError):
        raise TypeSafeError("O contexto da avaliação TypeSafe contém dados inválidos.") from None
    if any(not isinstance(question_id, str) or not question_id or
           not isinstance(question, dict) or question.get("type") not in ("noul", "choice", "score")
           or "instructions" not in question
           for question_id, question in questions.items()):
        raise TypeSafeError("As perguntas TypeSafe têm formato inválido.")

    try:
        config = get_configuration("typesafe")
    except Exception:
        config = {}
    if not isinstance(config, dict):
        config = {}
    request_model = str(
        model or config.get("default_model") or "jev-latest"
    ).strip()
    if not request_model or len(request_model) > 120:
        raise TypeSafeError("O modelo TypeSafe configurado é inválido.")
    for attempt in range(3):
        try:
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"state": state, "model": request_model, "questions": questions},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise TypeSafeError("Não foi possível conectar à API TypeSafe.") from exc
        if response.status_code not in (429, 529) or attempt == 2:
            break
        time.sleep(_typesafe_retry_delay(response.headers.get("Retry-After"), attempt))

    if response.status_code in (401, 403):
        raise TypeSafeError("A API TypeSafe não aceitou a credencial configurada.")
    if response.status_code == 429:
        raise TypeSafeError("A API TypeSafe limitou as chamadas. Tente novamente mais tarde.")
    if response.status_code == 529:
        raise TypeSafeError("A API TypeSafe está temporariamente sobrecarregada.")
    if response.status_code >= 400:
        raise TypeSafeError(f"A API TypeSafe retornou HTTP {response.status_code}.")
    try:
        result = response.json()
    except ValueError as exc:
        raise TypeSafeError("A API TypeSafe retornou uma resposta inválida.") from exc
    usage = result.get("usage") if isinstance(result, dict) else None
    if (not isinstance(result, dict) or not isinstance(result.get("model"), str)
            or not isinstance(result.get("answers"), dict) or not isinstance(usage, dict)
            or any(isinstance(usage.get(key), bool) or not isinstance(usage.get(key), int)
                   or usage[key] < 0 for key in ("input_tokens", "output_tokens"))):
        raise TypeSafeError("A resposta TypeSafe não contém respostas tipadas.")
    if any(question_id not in result["answers"] for question_id in questions):
        raise TypeSafeError("A resposta TypeSafe não contém todas as avaliações solicitadas.")
    return result
