"""Chamada OpenRouter compartilhada pelos agentes."""

from __future__ import annotations

import json
import re

from ..creative_modeling_generation import _json_content
from ..services.openrouter_service import chat_completion
from .models import AGENT_MODELS, assert_openrouter_gpt


def call_agent_llm(agent_name, system, user, *, images=None, text_callable=None, temperature=0.15):
    model = assert_openrouter_gpt(AGENT_MODELS[agent_name])
    content = user
    if images:
        blocks = [{"type": "text", "text": user}]
        for url in images:
            if url:
                blocks.append({"type": "image_url", "image_url": {"url": url}})
        content = blocks
    runner = text_callable or chat_completion
    response = runner(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        model=model,
        max_tokens=1800,
        temperature=temperature,
    )
    raw = response["message"].get("content") if isinstance(response, dict) else response
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raw = json.dumps(raw, ensure_ascii=False)
    try:
        return _json_content(raw)
    except Exception:
        clean = re.sub(r"^```(?:json)?\s*", "", str(raw).strip(), flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean)
        return json.loads(clean)
