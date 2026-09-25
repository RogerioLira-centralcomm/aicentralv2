"""Small server-side client for TypeSafe System One evaluations."""

import requests
import time

from .integration_credentials import get_configuration, resolve_typesafe_api_key


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

    try:
        config = get_configuration("typesafe")
    except Exception:
        config = {}
    request_model = str(
        model or config.get("default_model") or "jev-latest"
    ).strip()
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
        retry_after = response.headers.get('Retry-After', '')
        try:
            delay = min(4.0, max(0.0, float(retry_after)))
        except ValueError:
            delay = min(4.0, 2 ** attempt)
        time.sleep(delay)

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
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise TypeSafeError("A resposta TypeSafe não contém respostas tipadas.")
    return result
