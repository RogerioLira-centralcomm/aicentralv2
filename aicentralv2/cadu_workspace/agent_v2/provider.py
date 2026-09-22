"""Dify adapter for Conversations V2 with a reversible runtime rollout."""

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


def _shared_configuration():
    """Use the CentralX credential vault as the operational fallback."""
    from ...services.integration_credentials import resolve_dify_configuration

    url, key = resolve_dify_configuration()
    return str(url or "").rstrip("/"), str(key or "")


def _chat_configuration():
    """Prefer the dedicated Cadu Chat credential stored in CentralX."""
    from ...services.integration_credentials import resolve_cadu_chat_dify_configuration

    url, key = resolve_cadu_chat_dify_configuration()
    return str(url or "").rstrip("/"), str(key or "")


def _configuration(execution_mode="analysis") -> dict:
    mode = execution_mode if execution_mode in RUNTIMES else "analysis"
    runtime_id, url_key, secret_key = RUNTIMES[mode]
    specific_url = str(current_app.config.get(url_key) or "").rstrip("/")
    specific_key = str(current_app.config.get(secret_key) or "")
    chat_url, chat_key = _chat_configuration()
    specific_complete = bool(specific_url) and bool(specific_key)
    specific_partial = bool(specific_url) != bool(specific_key)
    chat_complete = bool(chat_url) and bool(chat_key)
    shared_url, shared_key = ("", "")
    if not specific_complete and not chat_complete:
        shared_url, shared_key = _shared_configuration()
    shared_complete = bool(shared_url) and bool(shared_key)
    if specific_partial and not chat_complete and not shared_complete:
        raise ProviderUnavailable(f"A configuração do runtime {runtime_id} está incompleta.")
    if specific_partial:
        current_app.logger.warning(
            "Configuração parcial do runtime %s; usando a configuração de reserva do Dify.",
            runtime_id,
        )
    if specific_complete:
        url, key, source = specific_url, specific_key, "mode-specific"
    elif chat_complete:
        url, key, source = chat_url, chat_key, "cadu-chat-integration"
    else:
        url, key, source = shared_url, shared_key, "centralx-integration"
    parsed = urlparse(url)
    if not key or parsed.scheme != "https" or not parsed.hostname:
        raise ProviderUnavailable(f"O runtime {runtime_id} ainda não foi configurado.")
    return {"id": runtime_id, "mode": mode, "url": url, "key": key, "source": source,
            "transport": "chat-messages", "config_version": "2026-09-21.1"}


def runtime_for(execution_mode="analysis") -> dict:
    runtime = _configuration(execution_mode)
    return {key: value for key, value in runtime.items() if key != "key"}


def settings(execution_mode="analysis"):
    runtime = _configuration(execution_mode)
    return runtime["url"], {"Authorization": "Bearer " + runtime["key"],
                            "Accept": "text/event-stream", "Cache-Control": "no-cache"}


def upload_file(file, user: str, execution_mode="analysis") -> str:
    runtime = _configuration(execution_mode)
    try:
        file.stream.seek(0)
        with requests.post(
            runtime["url"] + "/files/upload",
            headers={"Authorization": "Bearer " + runtime["key"]},
            data={"user": user},
            files={"file": (file.filename, file.stream, file.content_type)},
            timeout=(10, 90),
            allow_redirects=False,
        ) as response:
            if response.status_code not in {200, 201}:
                raise ProviderUnavailable("O runtime V2 não aceitou o arquivo.")
            value = response.json()
            if not isinstance(value, dict) or not value.get("id"):
                raise ProviderUnavailable("O runtime V2 não confirmou o arquivo.")
            return str(value["id"])
    except (requests.RequestException, ValueError) as exc:
        raise ProviderUnavailable("Não foi possível enviar o arquivo ao runtime V2.") from exc


def events(payload, execution_mode="analysis"):
    url, headers = settings(execution_mode)
    read_timeout = {"fast": 30, "analysis": 120, "agentic": 240}.get(execution_mode, 120)
    received_answer = False
    try:
        with requests.post(url + "/chat-messages", json=payload, headers=headers, stream=True,
                           timeout=(10, read_timeout), allow_redirects=False) as response:
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
                        if value.get("event") == "error":
                            if received_answer:
                                current_app.logger.warning(
                                    "Runtime V2 encerrou o stream após iniciar a resposta; preservando conteúdo recebido."
                                )
                                return
                            raise ProviderUnavailable("O runtime V2 retornou um erro durante a resposta.")
                        if value.get("event") in {"message", "agent_message"} and value.get("answer"):
                            received_answer = True
                        yield value
    except (requests.RequestException, ValueError) as exc:
        if received_answer:
            current_app.logger.warning(
                "Conexão com o runtime V2 terminou após iniciar a resposta; preservando conteúdo recebido: %s",
                type(exc).__name__,
            )
            return
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
