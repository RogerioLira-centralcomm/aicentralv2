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
               "blockquote", "a", "img", "figure", "figcaption", "hr", "div", "span",
               "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption"}

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
            if attr in {"href", "src", "alt", "title", "target", "rel"} or (name == "th" and attr == "scope" and value in {"col", "row"}):
                safe_attrs.append(f' {attr}="{value.replace(chr(34), "&quot;")}"')
        return f"<{name}{''.join(safe_attrs)}>"

    cleaned = re.sub(r"<\s*(/?)\s*([a-zA-Z0-9]+)([^>]*)>", tag, html)
    return cleaned if limit is None else cleaned[:limit]


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


def _clean_task_proposal(value):
    if not isinstance(value, dict):
        return None
    tasks = []
    for item in value.get("tasks") if isinstance(value.get("tasks"), list) else []:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), 180)
        evidence = _clean_text(item.get("evidence"), 2000)
        if len(title) < 2 or not evidence:
            continue
        refs = []
        for ref in item.get("resource_refs") if isinstance(item.get("resource_refs"), list) else []:
            cleaned = _clean_uuid(ref)
            if cleaned and cleaned not in refs:
                refs.append(cleaned)
        tasks.append({
            "title": title, "description": _clean_text(item.get("description"), 4000),
            "priority": str(item.get("priority") or "normal") if str(item.get("priority") or "normal") in {"low", "normal", "high"} else "normal",
            "status": "todo", "resource_refs": refs[:20],
            "evidence": evidence,
        })
        if len(tasks) >= 50:
            break
    if not tasks:
        return None
    context_summary = _clean_text(value.get("context_summary"), 4000)
    if len(context_summary) < 10:
        return None
    return {"tasks": tasks, "context_summary": context_summary,
            "user_instruction": _clean_text(value.get("user_instruction"), 4000),
            "initial_list": _as_bool(value.get("initial_list"))}


def _clean_citations(values):
    citations = []
    for item in values if isinstance(values, list) else []:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), 300)
        if not title:
            continue
        citation = {
            "title": title,
            "url": _resource_url(item.get("url")),
            "excerpt": _clean_text(item.get("excerpt"), 1000),
        }
        if item.get("id") or item.get("source_id"):
            citation["id"] = _clean_text(item.get("id") or item.get("source_id"), 100)
        citations.append(citation)
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
                safe_attrs.append(f' {attr}="{value.replace(chr(34), "&quot;")}"')
        return f"<{name}{''.join(safe_attrs)}>"

    cleaned = re.sub(r"<\s*(/?)\s*([a-zA-Z0-9]+)([^>]*)>", tag, html)
    return cleaned if limit is None else cleaned[:limit]


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
            title = _clean_text(item.get("title") or item.get("label") or item.get("question"), 180)
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
                clean.update({
                    "question": _clean_text(item.get("question") or item.get("title") or item.get("label"), 500),
                    "prompt": _clean_text(item.get("prompt"), 1000),
                    "required": _as_bool(item.get("required")),
                    "allow_custom": _as_bool(item.get("allow_custom")),
                    "custom_placeholder": _clean_text(item.get("custom_placeholder"), 180),
                })
                options = []
                for option_index, option in enumerate(item.get("options") if isinstance(item.get("options"), list) else []):
                    if isinstance(option, str):
                        label = _clean_text(option, 180)
                        option_value = label
                        option_id = f"option-{option_index + 1}"
                    elif isinstance(option, dict):
                        label = _clean_text(option.get("label") or option.get("title") or option.get("value"), 180)
                        option_value = _clean_text(option.get("value") or label, 300)
                        option_id = _clean_text(option.get("id"), 100) or f"option-{option_index + 1}"
                    else:
                        continue
                    if label and option_value:
                        options.append({"id": option_id, "label": label, "value": option_value})
                    if len(options) >= 6:
                        break
                if options:
                    clean["options"] = options
                elif clean["question"]:
                    # Open questions always need an answerable control even if
                    # the provider omitted allow_custom from its payload.
                    clean["allow_custom"] = True
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


def _provider_envelope_text(value):
    """Extract user-facing prose from a serialized response envelope."""
    decoded = _decode_provider_value(value)
    for _ in range(4):
        if not isinstance(decoded, dict):
            return None
        text_payload = decoded.get("text") if isinstance(decoded.get("text"), dict) else {}
        candidate = text_payload.get("content") or decoded.get("answer") or decoded.get("content")
        if isinstance(candidate, str) and candidate.strip():
            serialized_candidate = candidate.strip()
            if serialized_candidate.startswith(("{", "[", "```")):
                nested = _decode_provider_value(serialized_candidate)
                if isinstance(nested, dict) and any(key in nested for key in ("text", "answer", "artifact_patch")):
                    decoded = nested
                    continue
            return candidate.strip()
        patch = decoded.get("artifact_patch")
        if isinstance(patch, dict):
            candidate = patch.get("html") or patch.get("summary")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None
    return None


def _clean_patch(value, artifact_type=None):
    if not isinstance(value, dict):
        return None
    # A provider envelope is protocol, never editable document content. Reject
    # the patch so a legitimate artifact route can rebuild it from the already
    # normalized customer answer instead of persisting JSON in the editor.
    recovered_html = recovered_css = recovered_js = recovered_text = None
    for candidate in (value.get("html"), value.get("summary")):
        if not isinstance(candidate, (str, dict)):
            continue
        serialized = candidate.strip().lstrip("\ufeff") if isinstance(candidate, str) else ""
        if isinstance(candidate, str) and not (serialized.startswith("{") or serialized.startswith("```")):
            continue
        decoded = _decode_provider_value(candidate)
        if isinstance(decoded, dict) and (
                isinstance(decoded.get("text"), dict) or "ui" in decoded
                or "artifact_patch" in decoded or "answer" in decoded):
            envelope_text = _provider_envelope_text(decoded)
            if artifact_type == "html":
                nested_patch = decoded.get("artifact_patch") if isinstance(decoded.get("artifact_patch"), dict) else {}
                possible = nested_patch.get("html")
                if not possible and candidate is value.get("summary"):
                    possible = envelope_text
                if isinstance(possible, str) and possible.strip():
                    recovered_html = possible
                    recovered_css = str(nested_patch.get("css") or "")
                    recovered_js = str(nested_patch.get("js") or "")
                    break
            if envelope_text:
                recovered_text = envelope_text
                continue
            return None
    if recovered_text and artifact_type != "html":
        value = {**value, "html": ""}
    summary_text = _provider_envelope_text(value.get("summary"))
    summary_text = summary_text or str(value.get("summary") or "").strip()
    if recovered_text and recovered_text not in summary_text:
        summary_text = "\n\n".join(filter(None, (summary_text, recovered_text)))
    fields = []
    allowed_states = {"confirmed", "inferred", "assumed", "missing", "conflicting"}
    for item in value.get("fields", []) if isinstance(value.get("fields"), list) else []:
        if not isinstance(item, dict):
            continue
        key = _clean_text(item.get("key"), 160)
        state = _clean_text(item.get("state"), 40).lower()
        if key:
            field = {
                "key": key,
                "value": str(_provider_envelope_text(item.get("value")) or item.get("value") or "").strip(),
                "state": state if state in allowed_states else "inferred",
            }
            if isinstance(item.get("source_ids"), list):
                field["source_ids"] = [_clean_text(source_id, 100) for source_id in item["source_ids"][:8]
                                       if isinstance(source_id, str) and source_id.strip()]
            fields.append(field)
    patch = {
        "title": _clean_text(value.get("title"), 300),
        "summary": summary_text,
        "fields": fields,
    }
    if artifact_type in {"brief", "note", "executive_summary", "media_plan", "scenario", "research"}:
        metrics = value.get("metrics")
        if isinstance(metrics, dict):
            patch["metrics"] = {_clean_text(key, 80): _clean_text(item, 160)
                                for key, item in list(metrics.items())[:20]
                                if str(key).strip() and item is not None and not isinstance(item, (dict, list))}
        tables = []
        for table in value.get("tables", []) if isinstance(value.get("tables"), list) else []:
            if not isinstance(table, dict):
                continue
            columns = [_clean_text(column, 100) for column in (table.get("columns") if isinstance(table.get("columns"), list) else [])[:12]
                       if isinstance(column, str)]
            rows = [[_clean_text(cell, 500) for cell in row[:12]]
                    for row in (table.get("rows") if isinstance(table.get("rows"), list) else [])[:100] if isinstance(row, list)]
            if columns and rows:
                tables.append({"title": _clean_text(table.get("title"), 160),
                               "columns": columns, "rows": rows})
            if len(tables) >= 8:
                break
        if tables:
            patch["tables"] = tables
        citations = _clean_citations(value.get("citations"))
        if citations:
            patch["citations"] = citations
        images = []
        for item in value.get("images", []) if isinstance(value.get("images"), list) else []:
            image = item if isinstance(item, dict) else {"url": item}
            url = _resource_url(image.get("url"))
            if url:
                images.append({"url": url, "alt": _clean_text(image.get("alt"), 180),
                               "caption": _clean_text(image.get("caption"), 300)})
            if len(images) >= 10:
                break
        if images:
            patch["images"] = images
        if artifact_type == "executive_summary" and isinstance(value.get("highlights"), list):
            patch["highlights"] = [_clean_text(item, 400) for item in value["highlights"][:12]
                                   if isinstance(item, str) and item.strip()]
        if artifact_type == "scenario" and isinstance(value.get("options"), list):
            patch["options"] = [
                {"title": _clean_text(item.get("title"), 160),
                 "summary": _clean_text(item.get("summary"), 1200),
                 "metrics": {_clean_text(key, 80): _clean_text(metric, 160)
                             for key, metric in list((item.get("metrics") or {}).items())[:12]
                             if not isinstance(metric, (dict, list))}}
                for item in value["options"][:6]
                if isinstance(item, dict) and isinstance(item.get("metrics") or {}, dict)
            ]
    if recovered_html:
        lowered = recovered_html.lstrip().lower()
        if lowered.startswith(("<!doctype", "<html")) and "</html>" in lowered:
            styles = re.findall(r"<style\b[^>]*>(.*?)</style\s*>", recovered_html, flags=re.I | re.S)
            scripts = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", recovered_html, flags=re.I | re.S)
            body = re.search(r"<body\b[^>]*>(.*?)</body\s*>", recovered_html, flags=re.I | re.S)
            if body:
                recovered_html = re.sub(
                    r"<(?:script|style)\b[^>]*>.*?</(?:script|style)\s*>", "", body.group(1),
                    flags=re.I | re.S,
                ).strip()
                recovered_css = "\n".join(filter(None, [recovered_css.strip(), *styles])).strip()
                recovered_js = "\n".join(filter(None, [recovered_js.strip(), *scripts])).strip()
        value = {**value, "html": recovered_html, "css": recovered_css or "", "js": recovered_js or "", "summary": ""}
        patch["summary"] = ""
    if any(key in value for key in ("html", "css", "js")):
        patch.update({
            "fields": [],
            "html": (_clean_runtime_html(value.get("html"), None)
                     if artifact_type == "html" or value.get("css") or value.get("js") else
                     _clean_editor_html(value.get("html"), None)),
            "css": str(value.get("css") or ""),
            "js": str(value.get("js") or ""),
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
    # Preserve the provider's natural paragraph and sentence structure in every
    # mode. Server-owned character/question budgets below still bound the
    # response without flattening clarifications or artifact summaries.
    ui = {**value, **ui_payload}
    questions = [str(item).strip()[:500] for item in ui.get("questions", []) if str(item).strip()]
    questions = questions[:max(0, int(policy.get("max_questions", 1)))]
    assumptions = [str(item).strip()[:500] for item in ui.get("assumptions", []) if str(item).strip()][:10]
    citations = _clean_citations(ui.get("citations"))
    actions = _clean_actions(ui.get("actions"), max(0, int(policy.get("max_next_steps", 2))))
    provider_blocks = _clean_blocks(ui.get("blocks"))
    question_budget = max(0, int(policy.get("max_questions", 1)))
    blocks = []
    for block in provider_blocks:
        if block.get("type") in {"question", "questions"}:
            if question_budget <= 0:
                continue
            items = block.get("items") or []
            kept = items[:question_budget]
            question_budget -= len(kept)
            if not kept:
                continue
            block = {**block, "items": kept}
        blocks.append(block)
    # Failing closed is important here: only the executor may opt into an
    # artifact after the router selected a concrete artifact type.
    can_materialize_artifact = bool(policy.get("allow_artifact", False))
    artifact_type = policy.get("artifact_type")
    patch = _clean_patch(value.get("artifact_patch"), artifact_type=artifact_type)
    invalid_html_patch = False
    if not can_materialize_artifact:
        patch = None
    elif artifact_type == "html" and (not patch or not str(patch.get("html") or "").strip()):
        # A title-only patch creates a valid artifact record with an empty
        # document, which the browser can only present as a blank white page.
        patch = None
        invalid_html_patch = True
    if invalid_html_patch:
        answer = "Não consegui gerar o conteúdo visual desta página. Tente novamente para eu reconstruir o dashboard."
    artifact_first = (can_materialize_artifact and not policy.get("require_artifact_patch")
                      and policy.get("mode") == "artifact_first"
                      and policy.get("artifact_type") not in {None, "html", "project_map"})
    if artifact_first and not patch:
        patch = _fallback_artifact(answer, policy)
    dense_answer = len(answer) > int(policy.get("max_answer_chars") or 1800) or len(re.findall(r"(?m)^\s*(?:#{1,6}|[-*+]\s|\d+[.)]\s)", answer)) > 3
    if not blocks:
        blocks = _fallback_blocks(answer, policy)
    if artifact_first and dense_answer:
        answer = str(policy.get("artifact_chat_message") or "Organizei o resultado em uma versão editável para você revisar.")
    elif dense_answer and not blocks and policy.get("mode") != "clarification" and can_materialize_artifact and not policy.get("require_artifact_patch"):
        patch = patch or _fallback_artifact(answer, policy)
        answer = "Organizei os detalhes em uma versão editável para você revisar."
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
    task_proposal = _clean_task_proposal(value.get("task_proposal")) if policy.get("allow_task_proposal") else None
    return AgentResponse(answer=answer, confidence=confidence, assumptions=assumptions,
                         questions=questions, actions=actions, artifact_patch=patch,
                         citations=citations, blocks=blocks, task_proposal=task_proposal)
