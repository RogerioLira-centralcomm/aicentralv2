"""Validate provider output before it becomes product state or visible text."""

import json
import re

from werkzeug.exceptions import BadRequest

from .contracts import AgentResponse


INTERNAL_PATTERN = re.compile(
    r"\b(api[_ -]?key|bearer token|stack trace|traceback|dify unavailable|http 5\d\d|system prompt)\b",
    re.IGNORECASE,
)


def normalize_response(raw, policy: dict) -> AgentResponse:
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        elif text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()
        try:
            value = json.loads(text)
        except (TypeError, ValueError):
            value = {"answer": text}
    elif isinstance(raw, dict):
        value = raw
    else:
        raise BadRequest("O provider retornou uma resposta inválida.")
    answer = str(value.get("answer") or "").strip()
    if not answer:
        raise BadRequest("O provider não retornou uma resposta utilizável.")
    if INTERNAL_PATTERN.search(answer):
        raise BadRequest("A resposta continha um diagnóstico interno.")
    questions = [str(item).strip()[:500] for item in value.get("questions", []) if str(item).strip()]
    questions = questions[:max(0, int(policy.get("max_questions", 1)))]
    assumptions = [str(item).strip()[:500] for item in value.get("assumptions", []) if str(item).strip()][:10]
    citations = [item for item in value.get("citations", []) if isinstance(item, dict)][:20]
    actions = [item for item in value.get("actions", []) if isinstance(item, dict)][:5]
    patch = value.get("artifact_patch") if isinstance(value.get("artifact_patch"), dict) else None
    if not policy.get("artifact_in_chat", False) and len(answer) > 12000:
        answer = answer[:12000].rstrip() + "…"
    confidence = str(value.get("confidence") or "medium").lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    return AgentResponse(answer=answer, confidence=confidence, assumptions=assumptions,
                         questions=questions, actions=actions, artifact_patch=patch, citations=citations)
