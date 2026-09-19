"""Validate provider output before it becomes product state or visible text."""

import json
import re
from urllib.parse import urlsplit
from uuid import UUID

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


def _resource_url(value):
    value = _clean_text(value, 2000)
    if value.startswith('/workspace/'):
        return value
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password else ''
    except ValueError:
        return ''


def _clean_uuid(value):
    try:
        return str(UUID(str(value or "")))
    except (TypeError, ValueError, AttributeError):
        return ""


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim"}


def _clean_blocks(values):
    """Reduce provider UI suggestions to a small, inert product contract."""
    blocks = []
    allowed = {"decision", "checklist", "insights", "metrics", "files", "steps"}
    allowed_states = {"pending", "active", "done", "blocked"}
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict) or value.get("type") not in allowed:
            continue
        block_type = value["type"]
        items = []
        used_ids = set()
        source_items = value.get("items") if isinstance(value.get("items"), list) else []
        for index, item in enumerate(source_items):
            if not isinstance(item, dict):
                continue
            title = _clean_text(item.get("title") or item.get("label"), 180)
            if not title:
                continue
            item_id = _clean_text(item.get("id"), 100) or f"item-{index + 1}"
            if item_id in used_ids:
                item_id = f"item-{index + 1}"
            while item_id in used_ids:
                item_id = f"{item_id}-next"
            used_ids.add(item_id)
            clean = {
                "id": item_id,
                "title": title,
                "detail": _clean_text(item.get("detail") or item.get("description"), 500),
            }
            if block_type == "decision":
                clean.update({
                    "recommended": _as_bool(item.get("recommended")),
                    "prompt": _clean_text(item.get("prompt"), 1000),
                })
            elif block_type in {"checklist", "steps"}:
                state = _clean_text(item.get("state"), 30).lower()
                clean.update({
                    "state": state if state in allowed_states else "pending",
                    "prompt": _clean_text(item.get("prompt"), 1000),
                })
            elif block_type in {"insights", "metrics"}:
                clean["prompt"] = _clean_text(item.get("prompt"), 1000)
                if block_type == "metrics":
                    clean.update({
                        "value": _clean_text(item.get("value"), 100),
                        "url": _resource_url(item.get("url")),
                    })
            elif block_type == "files":
                clean.update({
                    "kind": _clean_text(item.get("kind"), 80) or "Arquivo",
                    "url": _resource_url(item.get("url")),
                    "artifact_id": _clean_uuid(item.get("artifact_id")),
                    "editor_url": _resource_url(item.get("editor_url")),
                    "editable_copy_url": _resource_url(item.get("editable_copy_url")),
                    "download_url": _resource_url(item.get("download_url")),
                })
            items.append(clean)
            if len(items) >= 5:
                break
        if items:
            blocks.append({
                "type": block_type,
                "title": _clean_text(value.get("title"), 180),
                "summary": _clean_text(value.get("summary"), 500),
                "items": items,
            })
        if len(blocks) >= 2:
            break
    return blocks


def _list_items(answer):
    items = []
    for raw_line in str(answer or "").replace("\r\n", "\n").split("\n"):
        match = re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$", raw_line)
        if not match:
            continue
        text = re.sub(r"[*_`]", "", match.group(1)).strip()
        if not text:
            continue
        title, separator, detail = text.partition(":")
        if not separator:
            title, separator, detail = text.partition(" — ")
        items.append({
            "id": f"item-{len(items) + 1}",
            "title": _clean_text(title, 180),
            "detail": _clean_text(detail, 500) if separator else "",
        })
    return items


def _short_intro(answer, fallback):
    intro = []
    for raw_line in str(answer or "").replace("\r\n", "\n").split("\n"):
        if re.match(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)", raw_line):
            if intro:
                break
            continue
        clean = _clean_text(re.sub(r"[*_`]", "", raw_line), 320)
        if clean:
            intro.append(clean)
        if len(" ".join(intro)) >= 220:
            break
    return _clean_text(" ".join(intro), 280) or fallback


def _fallback_blocks(answer, policy):
    items = _list_items(answer)
    mode = policy.get("mode")
    if mode == "decision" and 2 <= len(items) <= 5:
        for item in items:
            item.update({"recommended": False, "prompt": f"Use a opção “{item['title']}” e continue o trabalho."})
        return [{"type": "decision", "title": "Escolha uma direção", "summary": "", "items": items}]
    if mode in {"direct", "analysis"} and 2 <= len(items) <= 5:
        for item in items:
            item["prompt"] = f"Aprofunde este ponto: {item['title']}."
        return [{"type": "insights", "title": "Pontos principais", "summary": "", "items": items}]
    return []


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


def _plain_multiline(value, limit=4000):
    lines = []
    for raw_line in str(value or "").replace("\r\n", "\n").split("\n"):
        line = re.sub(r"\*\*([^*]+)\*\*|__([^_]+)__", lambda match: match.group(1) or match.group(2), raw_line)
        line = re.sub(r"^\s*[-*+]\s+", "• ", line)
        line = re.sub(r"^\s*#{1,6}\s*", "", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)[:limit].rstrip()


def _fallback_artifact(answer, policy):
    title = _clean_text(policy.get("artifact_fallback_title") or "Resultado do trabalho", 300)
    sections, heading, body, intro = [], "", [], []
    for line in str(answer or "").replace("\r\n", "\n").split("\n"):
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if match:
            if heading:
                sections.append((heading, "\n".join(body)))
            elif body:
                intro.extend(body)
            heading, body = match.group(1), []
        else:
            body.append(line)
    if heading:
        sections.append((heading, "\n".join(body)))
    else:
        intro.extend(body)
    fields = [{"key": _clean_text(key, 160), "value": _plain_multiline(value), "state": "inferred"}
              for key, value in sections[:20] if _clean_text(key, 160)]
    return {
        "title": title,
        "summary": _plain_multiline("\n".join(intro), 2000),
        "fields": fields,
    }


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
    blocks = _clean_blocks(value.get("blocks"))
    patch = _clean_patch(value.get("artifact_patch"))
    artifact_first = policy.get("mode") == "artifact_first" and policy.get("artifact_type") not in {None, "html", "project_map"}
    if artifact_first and not patch:
        patch = _fallback_artifact(answer, policy)
    dense_answer = len(answer) > int(policy.get("max_answer_chars") or 1800) or len(re.findall(r"(?m)^\s*(?:#{1,6}|[-*+]\s|\d+[.)]\s)", answer)) > 3
    if not blocks:
        blocks = _fallback_blocks(answer, policy)
    if artifact_first and dense_answer:
        answer = str(policy.get("artifact_chat_message") or "Organizei o resultado no artefato ao lado para você revisar e editar.")
    elif dense_answer and not blocks and policy.get("mode") != "clarification":
        patch = patch or _fallback_artifact(answer, policy)
        answer = "Organizei os detalhes no artefato ao lado para você revisar e editar."
    elif blocks:
        answer = _short_intro(answer, "Preparei o resultado para você continuar abaixo.")
    max_answer_chars = min(12000, max(240, int(policy.get("max_answer_chars") or 1800)))
    if len(answer) > max_answer_chars:
        answer = _short_intro(answer, answer[:max_answer_chars].rstrip())
        if len(answer) > max_answer_chars:
            answer = answer[:max_answer_chars].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    confidence = str(value.get("confidence") or "medium").lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    return AgentResponse(answer=answer, confidence=confidence, assumptions=assumptions,
                         questions=questions, actions=actions, artifact_patch=patch,
                         citations=citations, blocks=blocks)
