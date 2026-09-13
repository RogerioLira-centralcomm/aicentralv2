"""Chamadas OpenRouter para o Smart Planner — família GPT-5 por papel."""

from __future__ import annotations

from typing import Any

from ..services.openrouter_service import OpenRouterError, chat_completion
from .cost import record as record_cost
from .helpers import extract_json, text
from .models import resolve_role


def chat_text(
    system: str,
    user: str,
    *,
    role: str = "draft",
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_k: int | None = None,
    timeout: int = 90,
) -> str:
    spec = resolve_role(role)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    result = chat_completion(
        messages,
        model=spec["model"],
        timeout=timeout,
        max_tokens=max_tokens or spec["max_tokens"],
        temperature=spec["temperature"] if temperature is None else temperature,
        top_k=spec["top_k"] if top_k is None else top_k,
    )
    record_cost(result.get("usage"), kind=role, model=text(result.get("model")) or spec["model"])
    message = result.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return text(content)


def chat_vision(system: str, image_url: str, *, max_tokens: int = 1800) -> str:
    spec = resolve_role("vision")
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Leia o material da imagem."},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        },
    ]
    result = chat_completion(
        messages,
        model=spec["model"],
        timeout=90,
        max_tokens=max_tokens or spec["max_tokens"],
        temperature=spec["temperature"],
        top_k=spec["top_k"],
    )
    record_cost(result.get("usage"), kind="vision", model=text(result.get("model")) or spec["model"])
    message = result.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    out = text(content)
    if len(out) < 40:
        raise OpenRouterError("Não extraímos texto suficiente desta imagem.")
    return out


def chat_json(
    system: str,
    user: str,
    *,
    role: str = "extract",
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> Any:
    raw = chat_text(
        system,
        user,
        role=role,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    parsed = extract_json(raw)
    if parsed is None:
        raise OpenRouterError("A IA não devolveu JSON válido.")
    return parsed
