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
ORCHESTRATOR_METADATA_PATTERN = re.compile(
    r"(?im)^\s*(?:projeto usado|decis[aã]o proposta|confian[cç]a|pr[oó]ximo passo)\s*:",
)
INLINE_ORCHESTRATOR_PREFIX = re.compile(
    r"^\s*[^|\n]{1,240}\|\s*confian[cç]a\s*:\s*\**\s*"
    r"(?:baixa|m[eé]dia|alta|low|medium|high)\**[.,]?\s*",
    re.IGNORECASE,
)
_LEAKED_DECISION_PATTERN = re.compile(
    r"^\s*Projeto usado:\s*(?P<project>.+?)\.\s*"
    r"Decisão proposta:\s*(?P<decision>.+?)"
    r"(?:\.\s*Confiança:\s*(?P<confidence>[^,.]+)"
    r"(?:,\s*pois\s*(?P<reason>.+?))?)?\.?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def repair_metadata_answer(value):
    """Turn a leaked routing summary into a customer-facing sentence."""
    original = str(value or "").strip()
    text = " ".join(original.split()).strip()

    # Providers sometimes collapse the orchestration report into one
    # paragraph. In that form the line-oriented cleanup below cannot see the
    # labels, so prefer the factual/customer-facing segment when it exists.
    fact_match = re.search(
        r"(?is)(?:^|\s)fato\s*:\s*(.*?)(?=\s+pr[oó]xima\s+a[cç][aã]o\s*:|$)",
        text,
    )
    if fact_match and fact_match.group(1).strip():
        return fact_match.group(1).strip().rstrip(".") + "."

    # Some providers wrap the actual answer in an orchestration report. Keep
    # only the customer-facing response and discard the internal next-action
    # instruction before streaming or persisting it.
    response_match = re.search(r"(?is)(?:^|\s)resposta\s*:\s*(.*?)(?=\s+pr[oó]xima a[cç][aã]o\s*:|$)", text)
    if response_match:
        response = response_match.group(1).strip()
        if response:
            return response
    # A compact orchestration report can contain only the decision and
    # confidence fields (without a separate ``Resposta``/``Fato`` field).
    # In that case the decision is the useful customer-facing answer; never
    # expose the routing report itself.
    compact_match = re.search(
        r"(?is)decis[aã]o proposta\s*:\s*(.*?)(?=\s+confian[cç]a\s*:|\s+pr[oó]xima\s+a[cç][aã]o\s*:|$)",
        text,
    )
    if compact_match and compact_match.group(1).strip():
        decision = compact_match.group(1).strip().rstrip(".")
        return decision[:1].upper() + decision[1:] + "."

    text = re.sub(r"(?is)^\s*(?:projeto usado|decis[aã]o proposta|confian[cç]a|pr[oó]ximo passo)\s*:[^.]*\.\s*", "", text)
    match = _LEAKED_DECISION_PATTERN.match(text)
    if not match:
        return original
    project = match.group("project").strip().rstrip(".")
    decision = re.sub(r"\s*\+\s*", ", ", match.group("decision").strip()).rstrip(".")
    reason = (match.group("reason") or "").strip().rstrip(".")
    if decision.lower().startswith("posicionar "):
        sentence = f"A oportunidade para {project} é {decision}"
    else:
        sentence = f"A direção inicial para {project} é {decision}"
    if reason:
        sentence += ", mas essa é uma hipótese inicial porque " + reason[0].lower() + reason[1:]
    return sentence.rstrip(".") + "."


def _clean_text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _clean_editor_html(value, limit=100000):
    """Keep a small rich-text vocabulary; never persist executable markup."""
    html = str(value or "")
    html = re.sub(r"<!--.*?-->|<\s*(?:script|style|iframe|object|embed|form)\b[^>]*>.*?<\s*/\s*(?:script|style|iframe|object|embed|form)\s*>", "", html,
                  flags=re.IGNORECASE | re.DOTALL)
    allowed = {"p", "br", "strong", "b", "em", "i", "u", "h1", "h2", "h3", "ul", "ol", "li",
               "blockquote", "a", "img", "figure", "figcaption", "hr", "div", "span"}

    def tag(match):
        closing, name, attrs = match.group(1), match.group(2).lower(), match.group(3) or ""
        if name not in allowed:
            return ""
        if closing:
            return f"</{name}>"
        safe_attrs = []
        for attr, quote, raw in re.findall(r"([a-zA-Z:-]+)\s*=\s*(['\"])(.*?)\2", attrs, re.DOTALL):
            attr = attr.lower()
            value = str(raw or "").strip()
            if attr.startswith("on") or attr in {"style", "srcdoc"}:
                continue
            if attr in {"href", "src"} and not (value.startswith("https://") or value.startswith("http://") or value.startswith("data:image/")):
                continue
            if attr in {"href", "src", "alt", "title", "target", "rel"}:
                safe_attrs.append(f' {attr}="{value.replace(chr(34), "&quot;")[:2000]}"')
        return f"<{name}{''.join(safe_attrs)}>"

    return re.sub(r"<\s*(/?)\s*([a-zA-Z0-9]+)([^>]*)>", tag, html)[:limit]


def _clean_actions(values, limit):
    actions = []
    for item in values if isinstance(values, list) else []:
        if not isinstance(item, dict):
            continue
        action_id = _clean_text(item.get("id"), 120)
        label = _clean_text(item.get("label"), 160)
        prompt = _clean_text(item.get("prompt"), 1000)
        if action_id and label:
            actions.append({
                "id": action_id,
                "label": label,
                "prompt": prompt,
                "kind": _clean_text(item.get("kind") or "conversation.prompt", 80),
                "requires_confirmation": _as_bool(item.get("requires_confirmation")),
            })
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
            "url": _resource_url(item.get("url")),
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


def _brand_asset_url(value):
    value = _clean_text(value, 2000)
    if value.startswith('/') and not value.startswith('//'):
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


def _clean_brand_color(value):
    color = str(value or "").strip()
    return color if re.fullmatch(r"#[0-9a-fA-F]{3,8}", color) else ""


def _clean_runtime_html(value, limit=100_000):
    """Keep Tailwind-friendly markup while removing executable HTML attributes."""
    html = str(value or "")
    html = re.sub(r"<!--.*?-->|<\s*(?:script|iframe|object|embed|form|style|base)\b[^>]*>.*?<\s*/\s*(?:script|iframe|object|embed|form|style|base)\s*>", "",
                  html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<\s*script\b[^>]*>.*$", "", html, flags=re.IGNORECASE | re.DOTALL)
    allowed = {"main", "section", "article", "header", "footer", "nav", "div", "span", "p", "br", "strong", "b", "em", "i", "u",
               "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "table", "thead", "tbody", "tfoot", "tr", "th", "td",
               "a", "img", "figure", "figcaption", "hr", "dl", "dt", "dd", "button", "label", "input"}

    def tag(match):
        closing, name, attrs = match.group(1), match.group(2).lower(), match.group(3) or ""
        if name not in allowed:
            return ""
        if closing:
            return f"</{name}>"
        safe_attrs = []
        for attr, quote, raw in re.findall(r"([a-zA-Z:-]+)\s*=\s*(['\"])(.*?)\2", attrs, re.DOTALL):
            attr = attr.lower()
            value = str(raw or "").strip()
            if attr.startswith("on") or attr in {"style", "srcdoc", "formaction"}:
                continue
            if attr in {"href", "src", "action"} and not (value.startswith("https://") or value.startswith("http://") or value.startswith("/") and not value.startswith("//") or value.startswith("data:image/")):
                continue
            if attr in {"class", "id", "role", "alt", "title", "target", "rel", "href", "src", "action", "type", "name", "value", "placeholder", "aria-label"} or attr.startswith("aria-") or attr.startswith("data-"):
                safe_attrs.append(f' {attr}="{value.replace(chr(34), "&quot;")[:2000]}"')
        return f"<{name}{''.join(safe_attrs)}>"

    return re.sub(r"<\s*(/?)\s*([a-zA-Z0-9]+)([^>]*)>", tag, html)[:limit]


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim"}


def _clean_blocks(values):
    """Reduce provider UI suggestions to a small, inert product contract."""
    blocks = []
    allowed = {
        "entity", "summary", "activity", "progress", "source", "sources", "source_group",
        "assumption", "warning", "error", "question", "questions",
        "decision", "checklist", "insights", "metrics", "files", "steps", "images",
    }
    allowed_states = {"pending", "active", "done", "blocked"}
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict) or value.get("type") not in allowed:
            continue
        block_type = value["type"]
        if block_type in {"summary", "activity", "progress", "assumption", "warning", "error"}:
            text = _clean_text(value.get("text") or value.get("summary") or value.get("detail") or value.get("title"), 1200)
            if text:
                blocks.append({
                    "type": block_type,
                    "title": _clean_text(value.get("title"), 180),
                    "summary": _clean_text(value.get("summary"), 500),
                    "text": text,
                    "label": _clean_text(value.get("label"), 180),
                    "status": _clean_text(value.get("status") or value.get("state"), 30),
                })
            if len(blocks) >= 3:
                break
            continue
        items = []
        used_ids = set()
        source_items = value.get("items") if isinstance(value.get("items"), list) else []
        if not source_items and block_type in {"source", "sources"}:
            source_items = [value.get("resource") or value]
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
            if block_type in {"question", "questions"}:
                clean["prompt"] = _clean_text(item.get("prompt") or item.get("question"), 1000)
            elif block_type in {"source", "sources", "source_group"}:
                clean.update({
                    "kind": _clean_text(item.get("kind"), 80),
                    "url": _resource_url(item.get("url")),
                    "favicon": _resource_url(item.get("favicon")),
                    "published_at": _clean_text(item.get("published_at"), 60),
                    "resource_id": _clean_text(item.get("resource_id"), 120),
                })
            elif block_type == "decision":
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
            elif block_type == "images":
                clean.update({
                    "url": _resource_url(item.get("url")),
                    "source_url": _resource_url(item.get("source_url")),
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
        compact_types = {"summary", "activity", "progress", "source", "sources", "source_group", "assumption", "warning", "error"}
        if len(blocks) >= 2 and any(item["type"] not in compact_types for item in blocks):
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
    # Expository bullets are content, not controls. Turning every short list
    # into clickable "insights" fabricated intent and produced follow-up
    # prompts unrelated to the user's actual goal. Interactive blocks must be
    # explicitly returned by the provider; only real decisions keep a safe
    # compatibility fallback here.
    return []


def _decode_provider_value(raw):
    """Decode structured output even when a chatflow serializes it twice."""
    value = raw
    for _ in range(3):
        if isinstance(value, dict):
            for key in ("structured_output", "output", "data"):
                nested = value.get(key)
                if isinstance(nested, dict) and ("text" in nested or "answer" in nested):
                    value = nested
                    break
            return value
        if not isinstance(value, str):
            return value
        text = value.strip().lstrip("\ufeff")
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        elif text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()
        try:
            value = json.loads(text)
            continue
        except (TypeError, ValueError):
            start, end = text.find("{"), text.rfind("}")
            if 0 <= start < end:
                try:
                    value = json.loads(text[start:end + 1])
                    continue
                except (TypeError, ValueError):
                    pass
            return {"answer": text}
    return value


def _clean_patch(value):
    if not isinstance(value, dict):
        return None
    # A provider envelope is protocol, never editable document content. Reject
    # the patch so a legitimate artifact route can rebuild it from the already
    # normalized customer answer instead of persisting JSON in the editor.
    for candidate in (value.get("html"), value.get("summary")):
        if not isinstance(candidate, str):
            continue
        serialized = candidate.strip().lstrip("\ufeff")
        if not (serialized.startswith("{") or serialized.startswith("```")):
            continue
        decoded = _decode_provider_value(candidate)
        if isinstance(decoded, dict) and (
                isinstance(decoded.get("text"), dict) or "ui" in decoded
                or "artifact_patch" in decoded or "answer" in decoded):
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
            "html": (_clean_runtime_html(value.get("html"), 100_000)
                     if value.get("css") or value.get("js") else
                     _clean_editor_html(value.get("html"), 100_000)),
            "css": str(value.get("css") or "")[:30_000],
            "js": str(value.get("js") or "")[:40_000],
            "logo_url": _brand_asset_url(value.get("logo_url")),
            "primary_color": _clean_brand_color(value.get("primary_color")),
            "secondary_color": _clean_brand_color(value.get("secondary_color")),
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


def _single_sentence(value):
    raw = str(value or "")
    if re.search(r"(?m)^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s)", raw):
        return raw.strip()
    text = " ".join(raw.split())
    if not text:
        return text
    # Keep the concise chat contract without silently dropping the rest of a
    # useful answer: join sentence boundaries into one readable sentence.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9])", text)
    if len(parts) == 1:
        return text.strip()
    joined = "; ".join(part.strip().rstrip(".!?") for part in parts if part.strip())
    return (joined + ".").strip()


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
    patch = {
        "title": title,
        "summary": _plain_multiline("\n".join(intro), 2000),
        "fields": fields,
    }
    if policy.get("artifact_type") in {"meeting_summary", "meeting_agenda"} and not fields:
        patch["fields"] = [{"key": "Contexto", "value": _plain_multiline(answer), "state": "inferred"}]
    return patch


def normalize_response(raw, policy: dict) -> AgentResponse:
    value = _decode_provider_value(raw)
    if not isinstance(value, dict):
        raise BadRequest("O provider retornou uma resposta inválida.")
    # V2 contract: provider text and UI state are separate namespaces. Keep
    # the legacy flat shape only as a compatibility fallback for older flows.
    text_payload = value.get("text") if isinstance(value.get("text"), dict) else {}
    ui_payload = value.get("ui") if isinstance(value.get("ui"), dict) else {}
    answer_value = text_payload.get("content") or value.get("answer")
    for _ in range(3):
        if not isinstance(answer_value, str):
            break
        nested = _decode_provider_value(answer_value)
        if not isinstance(nested, dict):
            break
        nested_text = nested.get("text") if isinstance(nested.get("text"), dict) else {}
        candidate = nested_text.get("content") or nested.get("answer")
        if not isinstance(candidate, str) or candidate == answer_value:
            break
        answer_value = candidate
    answer = str(answer_value or "").strip()
    if not answer:
        raise BadRequest("O provider não retornou uma resposta utilizável.")
    repaired_answer = repair_metadata_answer(answer)
    if repaired_answer != answer:
        answer = repaired_answer
    # Some structured-output models prepend a compact decision/confidence
    # summary to the actual Markdown without a line break. It is UI metadata,
    # never part of the customer answer.
    answer = INLINE_ORCHESTRATOR_PREFIX.sub("", answer).strip()
    # Preserve headings when the provider serialized Markdown into one line.
    # The direct-mode compactor detects block Markdown by line boundaries.
    answer = re.sub(r"(?<!\n)\s+(#{2,6}\s+)", r"\n\n\1", answer)
    if INTERNAL_PATTERN.search(answer) or ORCHESTRATOR_METADATA_PATTERN.search(answer):
        raise BadRequest("A resposta continha um diagnóstico interno.")
    # Analysis is intentionally allowed to be multi-paragraph. Collapsing the
    # intermediate mode to one sentence discarded requested essays, research
    # summaries and other substantive answers.
    if policy.get("mode") in {"direct", "decision", "clarification", "artifact_first"}:
        answer = _single_sentence(answer)
    ui = {**value, **ui_payload}
    questions = [str(item).strip()[:500] for item in ui.get("questions", []) if str(item).strip()]
    questions = questions[:max(0, int(policy.get("max_questions", 1)))]
    assumptions = [str(item).strip()[:500] for item in ui.get("assumptions", []) if str(item).strip()][:10]
    citations = _clean_citations(ui.get("citations"))
    actions = _clean_actions(ui.get("actions"), max(0, int(policy.get("max_next_steps", 2))))
    provider_blocks = _clean_blocks(ui.get("blocks"))
    blocks = provider_blocks
    # Failing closed is important here: only the executor may opt into an
    # artifact after the router selected a concrete artifact type.
    can_materialize_artifact = bool(policy.get("allow_artifact", False))
    patch = _clean_patch(value.get("artifact_patch"))
    if not can_materialize_artifact:
        patch = None
    artifact_first = (can_materialize_artifact and policy.get("mode") == "artifact_first"
                      and policy.get("artifact_type") not in {None, "html", "project_map"})
    if artifact_first and not patch:
        patch = _fallback_artifact(answer, policy)
    dense_answer = len(answer) > int(policy.get("max_answer_chars") or 1800) or len(re.findall(r"(?m)^\s*(?:#{1,6}|[-*+]\s|\d+[.)]\s)", answer)) > 3
    if not blocks:
        blocks = _fallback_blocks(answer, policy)
    if artifact_first and dense_answer:
        answer = str(policy.get("artifact_chat_message") or "Organizei o resultado no artefato ao lado para você revisar e editar.")
    elif dense_answer and not blocks and policy.get("mode") != "clarification" and can_materialize_artifact:
        patch = patch or _fallback_artifact(answer, policy)
        answer = "Organizei os detalhes no artefato ao lado para você revisar e editar."
    elif blocks and not provider_blocks:
        # When we derive an interactive component from a list already present
        # in the prose, keep only its introduction to avoid rendering the same
        # choices twice. Provider-authored blocks never replace editorial text.
        answer = _short_intro(answer, "Preparei opções para você continuar abaixo.")
    max_answer_chars = min(40000, max(240, int(policy.get("max_answer_chars") or 1800)))
    if len(answer) > max_answer_chars:
        answer = _short_intro(answer, answer[:max_answer_chars].rstrip())
        if len(answer) > max_answer_chars:
            answer = answer[:max_answer_chars].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    confidence = str(ui.get("confidence") or "medium").lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    # Provider-produced source blocks are presentation data, not evidence. A
    # high-confidence assertion needs a validated citation in the response.
    if confidence == "high" and not citations:
        confidence = "medium"
    return AgentResponse(answer=answer, confidence=confidence, assumptions=assumptions,
                         questions=questions, actions=actions, artifact_patch=patch,
                         citations=citations, blocks=blocks)
