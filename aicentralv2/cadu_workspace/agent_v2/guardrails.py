"""Validate provider output before it becomes product state or visible text."""

import json
import re

from werkzeug.exceptions import BadRequest

from .contracts import AgentResponse


INTERNAL_PATTERN = re.compile(
    r"\b(api[_ -]?key|bearer token|stack trace|traceback|dify unavailable|http 5\d\d|system prompt)\b",
    re.IGNORECASE,
)


def _clean_text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _clean_actions(values, limit):
    actions = []
    for item in values if isinstance(values, list) else []:
        if not isinstance(item, dict):
            continue
        action_id = _clean_text(item.get("id"), 120)
        label = _clean_text(item.get("label"), 160)
        prompt = _clean_text(item.get("prompt"), 1000)
        if action_id and label:
            actions.append({"id": action_id, "label": label, "prompt": prompt})
        if len(actions) >= limit:
            break
    return actions


def _clean_citations(values):
    citations = []
    for item in values if isinstance(values, list) else []:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), 300)
        if not title:
            continue
        citations.append({
            "title": title,
            "url": _clean_text(item.get("url"), 2000),
            "excerpt": _clean_text(item.get("excerpt"), 1000),
        })
        if len(citations) >= 20:
            break
    return citations


def _clean_patch(value):
    if not isinstance(value, dict):
        return None
    fields = []
    allowed_states = {"confirmed", "inferred", "assumed", "missing", "conflicting"}
    for item in value.get("fields", []) if isinstance(value.get("fields"), list) else []:
        if not isinstance(item, dict):
            continue
        key = _clean_text(item.get("key"), 160)
        state = _clean_text(item.get("state"), 40).lower()
        if key:
            fields.append({
                "key": key,
                "value": _clean_text(item.get("value"), 4000),
                "state": state if state in allowed_states else "inferred",
            })
        if len(fields) >= 100:
            break
    patch = {
        "title": _clean_text(value.get("title"), 300),
        "summary": _clean_text(value.get("summary"), 2000),
        "fields": fields,
    }
    if any(key in value for key in ("html", "css", "js")):
        patch.update({
            "fields": [],
            "html": str(value.get("html") or "")[:100_000],
            "css": str(value.get("css") or "")[:30_000],
            "js": str(value.get("js") or "")[:40_000],
        })
    return patch


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
    citations = _clean_citations(value.get("citations"))
    actions = _clean_actions(value.get("actions"), max(0, int(policy.get("max_next_steps", 2))))
    patch = _clean_patch(value.get("artifact_patch"))
    max_answer_chars = min(12000, max(1000, int(policy.get("max_output_tokens") or 3000) * 4))
    if len(answer) > max_answer_chars:
        answer = answer[:max_answer_chars].rstrip() + "…"
    confidence = str(value.get("confidence") or "medium").lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    return AgentResponse(answer=answer, confidence=confidence, assumptions=assumptions,
                         questions=questions, actions=actions, artifact_patch=patch, citations=citations)
