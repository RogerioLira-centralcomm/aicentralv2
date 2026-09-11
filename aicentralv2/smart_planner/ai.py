"""Chamadas OpenRouter para o Smart Planner."""

from __future__ import annotations

import os
from typing import Any

from ..services.openrouter_service import OpenRouterError, chat_completion
from .cost import record as record_cost
from .helpers import extract_json, text


def chat_text(
    system: str,
    user: str,
    *,
    max_tokens: int = 4000,
    temperature: float = 0.2,
    timeout: int = 90,
) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    result = chat_completion(
        messages,
        model=os.getenv("SMART_PLANNER_MODEL") or os.getenv("AGENT_OPENROUTER_MODEL"),
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    record_cost(result.get("usage"), kind="chat", model=text(result.get("model")))
    message = result.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return text(content)


def chat_json(
    system: str,
    user: str,
    *,
    max_tokens: int = 4000,
    temperature: float = 0.1,
) -> Any:
    raw = chat_text(system, user, max_tokens=max_tokens, temperature=temperature)
    parsed = extract_json(raw)
    if parsed is None:
        raise OpenRouterError("A IA não devolveu JSON válido.")
    return parsed
