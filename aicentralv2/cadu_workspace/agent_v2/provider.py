"""Separate Dify adapter for Conversations V2.

The legacy Dify app and credentials remain untouched.  V2 fails closed until
its own URL and key are configured, which makes parallel rollout reversible.
"""

import json
from urllib.parse import urlparse

import requests
from flask import current_app


class ProviderUnavailable(RuntimeError):
    pass


def settings():
    url = str(current_app.config.get("CADU_CONVERSATIONS_V2_DIFY_URL") or "").rstrip("/")
    key = str(current_app.config.get("CADU_CONVERSATIONS_V2_DIFY_KEY") or "")
    parsed = urlparse(url)
    if not key or parsed.scheme != "https" or not parsed.hostname:
        raise ProviderUnavailable("O runtime Dify V2 ainda não foi configurado.")
    return url, {"Authorization": "Bearer " + key, "Accept": "text/event-stream", "Cache-Control": "no-cache"}


def events(payload):
    url, headers = settings()
    try:
        with requests.post(url + "/chat-messages", json=payload, headers=headers, stream=True,
                           timeout=(10, 90), allow_redirects=False) as response:
            if response.status_code != 200:
                raise ProviderUnavailable("O runtime V2 não conseguiu iniciar a resposta.")
            parts = []
            for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                if line.startswith("data:"):
                    parts.append(line[5:].lstrip())
                elif not line and parts:
                    raw, parts = "\n".join(parts), []
                    if raw == "[DONE]":
                        return
                    value = json.loads(raw)
                    if isinstance(value, dict):
                        yield value
    except (requests.RequestException, ValueError) as exc:
        raise ProviderUnavailable("A conexão com o runtime V2 foi interrompida.") from exc


def stop(task_id: str, user: str) -> None:
    if not task_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in task_id):
        raise ProviderUnavailable("A geração ainda está iniciando. Tente novamente.")
    url, headers = settings()
    try:
        with requests.post(url + "/chat-messages/" + task_id + "/stop", headers=headers,
                           json={"user": user}, timeout=(10, 20), allow_redirects=False) as response:
            if response.status_code != 200:
                raise ProviderUnavailable("Não foi possível interromper a geração.")
    except requests.RequestException as exc:
        raise ProviderUnavailable("Não foi possível interromper a geração.") from exc
