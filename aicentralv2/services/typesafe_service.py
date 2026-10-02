"""Small server-side client for TypeSafe System One evaluations."""

import json
import logging
import math
import time

import requests

from .integration_credentials import (
    _typesafe_retry_delay,
    get_configuration,
    resolve_typesafe_api_key,
)


logger = logging.getLogger(__name__)

API_URL = "https://api.typesafe.ai/v1/systemone"
RETRYABLE_STATUS = (429, 502, 503, 504, 529)
MAX_ATTEMPTS = 3
TOTAL_DEADLINE_SECONDS = 60


class TypeSafeError(RuntimeError):
    """A safe-to-log TypeSafe API failure without credentials or raw payloads."""


def system_one(state, questions, *, model=None, timeout=30, attempts=3):
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
        logger.warning("TypeSafe configuration unavailable; using the default model", exc_info=True)
        config = {}
    if not isinstance(config, dict):
        config = {}
    request_model = str(
        model or config.get("default_model") or "jev-latest"
    ).strip()
    if not request_model or len(request_model) > 120:
        raise TypeSafeError("O modelo TypeSafe configurado é inválido.")
    max_attempts = max(1, min(MAX_ATTEMPTS, attempts))
    deadline = time.monotonic() + TOTAL_DEADLINE_SECONDS
    # Stays None when every attempt failed before a response (timeouts that used up the deadline).
    response = None
    for attempt in range(max_attempts):
        remaining = deadline - time.monotonic()
        if attempt and remaining <= 0:
            break
        try:
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"state": state, "model": request_model, "questions": questions},
                timeout=max(1, min(timeout, remaining)),
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            logger.warning("TypeSafe request failed (%s) on attempt %d", type(exc).__name__, attempt + 1)
            if attempt == max_attempts - 1:
                raise TypeSafeError("Não foi possível conectar à API TypeSafe.") from exc
            time.sleep(_bounded_delay(_typesafe_retry_delay(None, attempt), deadline))
            continue
        except requests.RequestException as exc:
            raise TypeSafeError("Não foi possível conectar à API TypeSafe.") from exc
        if response.status_code not in RETRYABLE_STATUS or attempt == max_attempts - 1:
            break
        logger.warning("TypeSafe returned HTTP %d on attempt %d; retrying", response.status_code, attempt + 1)
        time.sleep(_bounded_delay(_typesafe_retry_delay(response.headers.get("Retry-After"), attempt), deadline))

    if response is None:
        raise TypeSafeError("Não foi possível conectar à API TypeSafe.")
    if response.status_code in (401, 403):
        raise TypeSafeError("A API TypeSafe não aceitou a credencial configurada.")
    if response.status_code == 429:
        raise TypeSafeError("A API TypeSafe limitou as chamadas. Tente novamente mais tarde.")
    if response.status_code == 529:
        raise TypeSafeError("A API TypeSafe está temporariamente sobrecarregada.")
    if response.status_code in (502, 503, 504):
        raise TypeSafeError("A API TypeSafe está temporariamente indisponível.")
    if response.status_code >= 400:
        logger.warning("TypeSafe rejected the evaluation with HTTP %d", response.status_code)
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
    if any(not _valid_answer(result["answers"][question_id], question["type"])
           for question_id, question in questions.items()):
        raise TypeSafeError("A resposta TypeSafe tem avaliações com formato inválido.")
    logger.info("TypeSafe evaluation ok: model=%s input_tokens=%d output_tokens=%d",
                result["model"], usage["input_tokens"], usage["output_tokens"])
    return result


def _bounded_delay(delay, deadline):
    """Never sleep past the total deadline."""
    return max(0.0, min(delay, deadline - time.monotonic()))


def _valid_answer(answer, expected_type):
    if not isinstance(answer, dict) or answer.get("type") != expected_type:
        return False
    value = answer.get(expected_type)
    if expected_type == "choice":
        return isinstance(value, str) and bool(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    # A noul is a probability: the same 0..1 range the integration health check enforces.
    return 0 <= value <= 1 if expected_type == "noul" else True
