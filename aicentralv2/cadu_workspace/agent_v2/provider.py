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


RUNTIMES = {
    "fast": ("cadu-fast", "CADU_DIFY_FAST_URL", "CADU_DIFY_FAST_KEY"),
    "analysis": ("cadu-analyst", "CADU_DIFY_ANALYST_URL", "CADU_DIFY_ANALYST_KEY"),
    "agentic": ("cadu-operator", "CADU_DIFY_OPERATOR_URL", "CADU_DIFY_OPERATOR_KEY"),
}


def _configuration(execution_mode="analysis") -> dict:
    mode = execution_mode if execution_mode in RUNTIMES else "analysis"
    runtime_id, url_key, secret_key = RUNTIMES[mode]
    specific_url = str(current_app.config.get(url_key) or "").rstrip("/")
    specific_key = str(current_app.config.get(secret_key) or "")
    if bool(specific_url) != bool(specific_key):
        raise ProviderUnavailable(f"A configuração do runtime {runtime_id} está incompleta.")
    url = specific_url or str(current_app.config.get("CADU_CONVERSATIONS_V2_DIFY_URL") or "").rstrip("/")
    key = specific_key or str(current_app.config.get("CADU_CONVERSATIONS_V2_DIFY_KEY") or "")
    parsed = urlparse(url)
    if not key or parsed.scheme != "https" or not parsed.hostname:
        raise ProviderUnavailable(f"O runtime {runtime_id} ainda não foi configurado.")
    return {"id": runtime_id, "mode": mode, "url": url, "key": key,
            "transport": "chat-messages", "config_version": "2026-09-19"}


def runtime_for(execution_mode="analysis") -> dict:
    runtime = _configuration(execution_mode)
    return {key: value for key, value in runtime.items() if key != "key"}


def settings(execution_mode="analysis"):
    runtime = _configuration(execution_mode)
    return runtime["url"], {"Authorization": "Bearer " + runtime["key"],
                            "Accept": "text/event-stream", "Cache-Control": "no-cache"}


def events(payload, execution_mode="analysis"):
    url, headers = settings(execution_mode)
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


def stop(task_id: str, user: str, execution_mode="analysis") -> None:
    if not task_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in task_id):
        raise ProviderUnavailable("A geração ainda está iniciando. Tente novamente.")
    url, headers = settings(execution_mode)
    try:
        with requests.post(url + "/chat-messages/" + task_id + "/stop", headers=headers,
                           json={"user": user}, timeout=(10, 20), allow_redirects=False) as response:
            if response.status_code != 200:
                raise ProviderUnavailable("Não foi possível interromper a geração.")
    except requests.RequestException as exc:
        raise ProviderUnavailable("Não foi possível interromper a geração.") from exc
