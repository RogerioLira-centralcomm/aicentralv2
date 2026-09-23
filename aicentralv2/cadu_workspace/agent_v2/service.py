"""Admission, execution and persistence for a complete Conversations V2 turn."""

import json
import re
from dataclasses import asdict, replace
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4

from flask import abort, current_app, has_app_context, has_request_context, session, url_for
from psycopg.types.json import Json

from ...cadu_credit_connector import CaduCreditConnector, CreditActor
from ...cadu_family import repository
from ...cadu_tool_billing import InsufficientToolCredits
from ..conversations.guardrails import normalize_colloquial, validate_files
from ..artifacts import create_draft, get_artifact, patch_artifact
from . import provider
from .executor import prepare_execution
from .guardrails import normalize_response
from .request_context import resolve
from . import journal
from .context_builder import ConversationContextBuilder, selected_context
from .conversation_runtime import RuntimeRollout, TurnIdentity
from .memory_checkpoint import schedule as schedule_memory_checkpoint


PROJECT_MAP_MAX_RESOURCES = 120
PROJECT_MAP_MAX_RELATIONS = 200
PROJECT_MAP_GROUP_MAX_HEIGHT = 520


def _event(kind, **values):
    return "data: " + json.dumps({"event": kind, **values}, ensure_ascii=False, default=str) + "\n\n"


def _preserve_streamed_answer(response, streamed_answer: str, policy: dict):
    """Keep a substantive visible draft stable when final metadata arrives."""
    streamed = str(streamed_answer or "").strip()
    final = str(response.answer or "").strip()
    # A provider can stream its structured contract as text even when the
    # final payload was normalized correctly. Never promote that envelope
    # back into the customer-facing answer.
    if re.match(r'^\s*(?:```(?:json)?\s*)?["\']?\s*[\[{]', streamed, re.IGNORECASE):
        return response
    if response.artifact_patch or len(streamed) < 80:
        return response
    # A final answer that extends the exact visible draft is safe and useful.
    # Any rewrite or shorter synthesis would make already-read text disappear,
    # so retain the last complete draft and merge only the structured metadata.
    if final.startswith(streamed) and len(final) > len(streamed):
        return response
    return replace(response, answer=streamed)


def _decode_partial_json_string(value: str) -> str:
    """Decode the completed portion of a JSON string without exposing its envelope."""
    output, index = [], 0
    escapes = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
               "n": "\n", "r": "\r", "t": "\t"}
    while index < len(value):
        char = value[index]
        if char != "\\":
            output.append(char)
            index += 1
            continue
        if index + 1 >= len(value):
            break
        escaped = value[index + 1]
        if escaped == "u":
            code = value[index + 2:index + 6]
            if len(code) < 4 or not all(item in "0123456789abcdefABCDEF" for item in code):
                break
            output.append(chr(int(code, 16)))
            index += 6
            continue
        output.append(escapes.get(escaped, escaped))
        index += 2
    return "".join(output)


def _streamable_answer(value: str) -> str:
    """Return only user-visible prose from plain or partially streamed JSON output."""
    raw = str(value or "")
    stripped = raw.lstrip()
    if not stripped:
        return ""
    matches = list(re.finditer(r'"(?:answer|content)"\s*:\s*"', raw, re.IGNORECASE))
    if not matches:
        looks_structured = stripped.startswith(("{", "[", '"{', "```json", "```JSON"))
        if looks_structured:
            return ""
        return raw
    start = matches[-1].end()
    escaped = False
    end = len(raw)
    for index in range(start, len(raw)):
        char = raw[index]
        if char == '"' and not escaped:
            end = index
            break
        if char == "\\" and not escaped:
            escaped = True
        else:
            escaped = False
    return _decode_partial_json_string(raw[start:end])


def _journal(run_id, kind, payload=None, *, item_type="activity", duration_ms=None):
    try:
        return journal.record(run_id, kind, payload, item_type=item_type, duration_ms=duration_ms)
    except Exception:
        if has_app_context():
            current_app.logger.exception("Falha ao registrar evento do Turn %s", run_id)
        return {"event": kind, **(payload or {})}


def _complete_step(run_id, kind, output=None, error_code=None):
    try:
        journal.complete_step(run_id, kind, output, error_code)
    except Exception:
        if has_app_context():
            current_app.logger.exception("Falha ao salvar checkpoint %s do Turn %s", kind, run_id)


def _message(value):
    text = " ".join(str(value or "").split())
    if not 1 <= len(text) <= 20000:
        abort(400, description="Informe uma mensagem de até 20.000 caracteres.")
    # Clients published before the structured-question fix could submit the
    # assistant's own question as if it were the user's answer. Stop this
    # before admission, routing, web search or credit consumption.
    if re.fullmatch(r'Sobre\s+[“\"]\s*.+?\s*[”\"]\s*:\s*', text, flags=re.IGNORECASE):
        abort(400, description="Digite sua resposta antes de continuar.")
    return text


def _selected_context(value):
    if not isinstance(value, dict):
        return None
    kind = str(value.get("type") or "selection")[:40]
    raw_text = str(value.get("text") or "").replace("\r\n", "\n").replace("\r", "\n")
    if kind == "assistant_response":
        text = "\n".join(line.rstrip() for line in raw_text.split("\n")).strip()
        limit = 40000
    else:
        text = " ".join(raw_text.split())
        limit = 12000
    if not 3 <= len(text) <= limit:
        return None
    label = str(value.get("label") or "Contexto selecionado")[:80]
    return {"type": kind, "label": label, "text": text}


def _previous_assistant_context(message, messages):
    """Resolve explicit references to the previous answer without model guesswork."""
    if not re.search(
        r"\b(?:[uú]ltima resposta|resposta anterior|texto anterior|conte[uú]do anterior|"
        r"esse texto|este texto|essa resposta|esta resposta|o que voc[eê] (?:escreveu|gerou|respondeu))\b",
        str(message or ""), re.IGNORECASE,
    ):
        return None
    previous = next((item for item in reversed(messages or []) if item.get("role") == "assistant" and str(item.get("content") or "").strip()), None)
    if not previous:
        return None
    return _selected_context({
        "type": "assistant_response",
        "label": "Última resposta do assistente",
        "text": previous.get("content"),
    })


_TURN_URL = re.compile(r"https?://[^\s<>\]\[\"']+", re.IGNORECASE)
_LINK_REFERENCE = re.compile(
    r"\b(?:esse|este|aquele|o)\s+(?:link|site|endere[cç]o|url)|"
    r"\b(?:link|site|url)\s+que\s+(?:eu\s+)?(?:enviei|mandei|passei|adicionei)|"
    r"\bcom\s+base\s+(?:nele|nisso|no\s+link)\b",
    re.IGNORECASE,
)
_SHORT_CONFIRMATION = re.compile(
    r"^\s*(?:sim|pode|pode\s+(?:criar|fazer|gerar|seguir)|fa[cç]a|crie|gere|continue|prossiga|ok)\s*[.!]?\s*$",
    re.IGNORECASE,
)
_FORMAT_CONTINUATION = re.compile(
    r"\b(?:pode\s+ser|fa[cç]a|quero)\s+(?:um|uma|em\s+formato\s+de)?\s*"
    r"(plano|relat[oó]rio|apresenta[cç][aã]o|briefing|documento|texto)\b",
    re.IGNORECASE,
)
_GENERIC_REFERENCE = re.compile(
    r"\b(?:isso|isto|aquilo|nele|nela|deles|delas|esse|essa|este|esta|aquele|aquela)\b|"
    r"\b(?:o|a|esse|essa|aquele|aquela)\s+(?:arquivo|anexo|documento|texto|resposta|imagem|"
    r"plano|relat[oó]rio|apresenta[cç][aã]o|briefing|projeto|marca|campanha|conte[uú]do)\b|"
    r"\b(?:continue|continue\s+da[ií]|prossiga|retome|revise|ajuste|altere|melhore|resuma|"
    r"transforme|reescreva|complete|finalize)\b",
    re.IGNORECASE,
)


def _metadata_response(message):
    metadata = message.get("metadata") if isinstance(message, dict) else None
    if not isinstance(metadata, dict):
        return {}
    response = metadata.get("response")
    return response if isinstance(response, dict) else {}


def _conversation_turn_context(message, messages):
    """Build bounded operational state and resolve references before inference."""
    recent = [item for item in (messages or []) if item.get("role") in {"user", "assistant"}][-12:]
    if not recent:
        return None
    latest_url = ""
    latest_url_message = None
    pending = None
    files = []
    artifact = None
    latest_user_request = ""
    latest_assistant_answer = ""
    inspected_latest_assistant = False
    for item in reversed(recent):
        role = item.get("role")
        content = str(item.get("content") or "")
        if not latest_url:
            match = _TURN_URL.search(content)
            if match:
                latest_url = match.group(0).rstrip(".,;:!?)")
                latest_url_message = item
        if role == "user" and not latest_user_request and content.strip():
            latest_user_request = " ".join(content.split())[:1200]
        if role == "assistant" and not latest_assistant_answer and content.strip():
            latest_assistant_answer = " ".join(content.split())[:1600]
        for file in item.get("files") or []:
            if not isinstance(file, dict):
                continue
            identity = str(file.get("id") or file.get("url") or file.get("name") or "")
            if identity and all(existing.get("identity") != identity for existing in files):
                files.append({
                    "identity": identity,
                    "name": str(file.get("name") or "Arquivo")[:180],
                    "url": str(file.get("url") or "")[:2000],
                })
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        if artifact is None and metadata.get("artifact_id"):
            artifact = {"id": str(metadata["artifact_id"]), "title": str(metadata.get("artifact_title") or "Artefato")[:180]}
        # Only the latest assistant turn can own a pending action. Looking past
        # it would revive stale suggestions after the subject already changed.
        if role == "assistant" and not inspected_latest_assistant:
            inspected_latest_assistant = True
            response = _metadata_response(item)
            for block in reversed(response.get("blocks") or []):
                if not isinstance(block, dict):
                    continue
                for option in reversed(block.get("items") or []):
                    if isinstance(option, dict) and option.get("auto_submit") and option.get("prompt"):
                        pending = {"title": str(option.get("title") or "Continuar"), "prompt": str(option["prompt"])}
                        break
                if pending:
                    break
    normalized_message = normalize_colloquial(message)
    refers_to_link = bool(_LINK_REFERENCE.search(normalized_message))
    generic_reference = bool(_GENERIC_REFERENCE.search(normalized_message))
    confirms = bool(_SHORT_CONFIRMATION.match(normalized_message))
    format_match = _FORMAT_CONTINUATION.search(normalized_message)
    transcript = []
    for item in recent[-6:]:
        content = " ".join(str(item.get("content") or "").split())[:1000]
        if content:
            transcript.append({"role": item.get("role"), "content": content})
    routing_message = ""
    if format_match and latest_url:
        routing_message = (
            f"Abra o link e crie um resumo editável estruturado como {format_match.group(1)}: {latest_url}"
        )
    resolved_reference = "none"
    if routing_message:
        resolved_reference = "format_refinement"
    elif refers_to_link and latest_url:
        resolved_reference = "latest_url"
    elif confirms and pending:
        resolved_reference = "pending_action"
    elif generic_reference:
        resolved_reference = "recent_turn"
    active_entities = {}
    if latest_url:
        active_entities["url"] = latest_url
    if files:
        active_entities["files"] = files[:5]
    if artifact:
        active_entities["artifact"] = artifact
    return {
        "type": "conversation_turn",
        "active_entities": active_entities,
        "resolved_reference": resolved_reference,
        "requires_selected_context": resolved_reference != "none",
        "pending_action": pending,
        "routing_message": routing_message,
        "source_message_id": str((latest_url_message or {}).get("id") or ""),
        "latest_user_request": latest_user_request,
        "latest_assistant_answer": latest_assistant_answer,
        "recent_turns": transcript,
    }


def _turn_selected_context(turn):
    if not turn or not turn.get("requires_selected_context"):
        return None
    return _selected_context({
        "type": "conversation_turn",
        "label": "Continuidade da conversa",
        "text": json.dumps(turn, ensure_ascii=False, separators=(",", ":")),
    })


def _run_was_cancelled(run_id: str) -> bool:
    """Recheck durable state before persisting output from a stopped provider."""
    try:
        rows = repository.rows(
            "SELECT status FROM cadu_family_chat_runs WHERE id = %s AND runtime_version = 'v2'",
            (run_id,),
        )
        return bool(rows and rows[0].get("status") == "cancelled")
    except Exception:
        current_app.logger.exception("Falha ao consultar cancelamento do run V2 %s", run_id)
        return False


def _project_map_content(run: dict, suggested=None) -> dict:
    """Build the spatial artifact from the canonical registry, never from invented model IDs."""
    registry = run["resolved_context"].values.get("projects.list_resources") or {}
    resources = registry.get("resources") if isinstance(registry, dict) else []
    relations = registry.get("relations") if isinstance(registry, dict) else []
    suggested = suggested if isinstance(suggested, dict) else {}
    group_specs = (
        ("context", "Contexto e referências", {"file", "link"}),
        ("planning", "Planos e estratégia", {"artifact", "media_plan"}),
        ("results", "Resultados e análises", {"report", "analysis"}),
        ("creative", "Criação", {"image", "video"}),
    )
    groups = []
    grouped = {key: [] for key, _, _ in group_specs}
    grouped["other"] = []
    type_group = {resource_type: key for key, _, types in group_specs for resource_type in types}
    safe_resources = []
    all_resources = resources if isinstance(resources, list) else []
    project_ref = str(getattr(run.get("context"), "project_ref", "") or "")
    project_id = project_ref[3:] if project_ref.startswith("ci:") else ""
    for item in all_resources[:PROJECT_MAP_MAX_RESOURCES]:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        group_id = type_group.get(str(item.get("resource_type") or ""), "other")
        locator = str(item.get("locator") or "")
        source_system = str(item.get("source_system") or "")[:120]
        source_id = str(item.get("source_id") or "")[:220]
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        provider_name = str(metadata.get("provider") or "")[:80]
        parsed_locator = urlparse(locator) if locator.startswith("https://") else None
        hostname = (parsed_locator.hostname or "").lower() if parsed_locator else ""
        if hostname.endswith("docs.google.com"):
            provider_name = "Google Sheets" if parsed_locator.path.startswith("/spreadsheets/") else "Google Docs"
        elif hostname.endswith("drive.google.com"):
            provider_name = "Google Drive"
        editor_url = f"/workspace/docs/{source_id}" if source_system == "planner_docs" else ""
        download_url = ""
        if source_system == "workspace" and source_id.startswith("file:") and source_id[5:].isdigit() and project_id:
            download_url = f"/workspace/app/projetos/{project_id}/fontes/{source_id[5:]}/download"
        editing_mode = (
            "native" if editor_url else
            "download" if download_url else
            "external" if locator.startswith("https://") else
            "read_only"
        )
        public_locator = locator if locator.startswith(("https://", "/")) else ""
        if source_system == "workspace_images" and source_id.isdigit() and project_id and has_app_context():
            public_locator = url_for("cadu_workspace.project_image", project_id=project_id, image_id=int(source_id))
        record = {
            "id": str(item["id"])[:120],
            "title": str(item.get("title") or "Arquivo")[:220],
            "source_system": source_system,
            "source_id": source_id,
            "type": str(item.get("resource_type") or "file")[:80],
            "mime_type": str(item.get("mime_type") or "")[:160],
            "category": str(item.get("category") or "other")[:120],
            "status": str(item.get("status") or "active")[:80],
            "version": max(1, int(item.get("version") or 1)),
            "group_id": group_id,
            "possible_duplicate": bool(item.get("possible_duplicate")),
            "url": public_locator[:500],
            "editor_url": editor_url,
            "download_url": download_url,
            "editable_copy_url": f"/workspace/api/v2/resources/{str(item['id'])[:120]}/editable-copy" if download_url else "",
            "editing_mode": editing_mode,
            "provider": provider_name,
        }
        grouped[group_id].append(record)
        safe_resources.append(record)
    visible_specs = [(key, title) for key, title, _ in group_specs if grouped[key]]
    if grouped["other"]:
        visible_specs.append(("other", "Outros recursos"))
    y = 48
    for row_start in range(0, len(visible_specs), 2):
        row_specs = visible_specs[row_start:row_start + 2]
        row_heights = []
        for column, (key, title) in enumerate(row_specs):
            height = min(PROJECT_MAP_GROUP_MAX_HEIGHT, 56 + (len(grouped[key]) * 48))
            height = max(112, height)
            row_heights.append(height)
            groups.append({
                "id": key, "title": title, "x": 48 + column * 360, "y": y,
                "width": 310, "height": height,
                "resource_ids": [item["id"] for item in grouped[key]],
            })
        y += max(row_heights, default=112) + 48
    safe_ids = {item["id"] for item in safe_resources}
    safe_relations = []
    for relation in (relations if isinstance(relations, list) else [])[:PROJECT_MAP_MAX_RELATIONS]:
        source = str(relation.get("source_resource_id") or "")
        target = str(relation.get("target_resource_id") or "")
        if source in safe_ids and target in safe_ids:
            safe_relations.append({
                "source": source, "target": target,
                "type": str(relation.get("relation_type") or "related")[:80],
                "confidence": float(relation.get("confidence") or 0),
            })
    total = len(all_resources)
    visible = len(safe_resources)
    return {
        "title": suggested.get("title") or "Mapa do projeto",
        "summary": suggested.get("summary") or (
            f"{visible} de {total} recurso{'s' if total != 1 else ''} organizado{'s' if visible != 1 else ''} pelo Cadu."
            if total > visible else
            f"{total} recurso{'s' if total != 1 else ''} organizado{'s' if total != 1 else ''} pelo Cadu."
        ),
        "layout": {"mode": "spatial", "version": 1, "zoom": 1},
        "groups": groups,
        "resources": safe_resources,
        "relations": safe_relations,
        "summary_counts": registry.get("summary") if isinstance(registry, dict) else {},
        "total_resources": total,
        "visible_resources": visible,
        "truncated": total > visible,
    }


def _enrich_source_blocks(response, run):
    """Resolve project and web source references without trusting provider URLs."""
    registry = run["resolved_context"].values.get("projects.list_resources") or {}
    resources = registry.get("resources") if isinstance(registry, dict) else []
    by_id = {}
    for resource in resources if isinstance(resources, list) else []:
        if not isinstance(resource, dict):
            continue
        for key in ("id", "source_id"):
            if resource.get(key):
                by_id[str(resource[key])] = resource
    for block in response.blocks:
        if block.get("type") not in {"source", "sources", "source_group"}:
            continue
        for item in block.get("items") or []:
            resource = by_id.get(str(item.get("resource_id") or item.get("id")))
            if not resource:
                continue
            item.update({
                "resource_id": str(resource.get("id") or item.get("resource_id") or ""),
                "title": str(resource.get("title") or item.get("title") or "Arquivo")[:220],
                "kind": str(resource.get("resource_type") or item.get("kind") or "Arquivo")[:80],
                "url": str(resource.get("locator") or item.get("url") or "")[:2000],
                "source_system": str(resource.get("source_system") or "")[:80],
            })
    web_result = (
        run["resolved_context"].values.get("web.search")
        or run["resolved_context"].values.get("web.read")
        or {}
    )
    web_sources = web_result.get("sources") if isinstance(web_result, dict) else []
    safe_web_sources = []
    seen_urls = set()
    for source in web_sources if isinstance(web_sources, list) else []:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "").strip()[:2000]
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        safe_web_sources.append({
            "id": str(source.get("id") or f"web-{len(safe_web_sources) + 1}")[:100],
            "title": str(source.get("title") or parsed.hostname or "Fonte")[:220],
            "url": url,
            "excerpt": " ".join(str(source.get("content_excerpt") or source.get("excerpt") or "").split())[:500],
            "content": " ".join(str(source.get("content") or source.get("content_excerpt") or source.get("excerpt") or "").split())[:6000],
            "published_at": str(source.get("published_at") or "")[:60],
            "kind": "web",
            "favicon": str(source.get("favicon") or "")[:2000],
            "image_url": str(source.get("image_url") or "")[:2000],
        })
        if len(safe_web_sources) >= 8:
            break
    if safe_web_sources:
        execution_mode = str(run.get("execution_mode") or "analysis")
        query = str(run.get("payload", {}).get("query") or "").lower()
        person_or_work_query = any(token in query for token in (
            "quem é", "quem foi", "morreu", "biografia", "história", "historia", "carreira", "obra", "artista", "cantor", "autor",
            "marca", "campanha", "campanhas", "case", "trajetória", "trajetoria", "legado", "lançamento", "lancamento",
        ))
        image_limit = 0 if execution_mode == "fast" else 1 if execution_mode == "analysis" else 3
        image_items = [source for source in safe_web_sources if source.get("image_url")][:image_limit] if person_or_work_query else []
        if image_items:
            response.blocks = [*response.blocks, {
                "type": "images", "title": "Imagens relacionadas",
                "summary": "Imagens encontradas em fontes públicas consultadas.",
                "items": [{"id": f"image-{index}", "title": item["title"], "url": item["image_url"], "source_url": item["url"]}
                          for index, item in enumerate(image_items, 1)],
            }, *response.blocks[2:]]
        existing_urls = {
            str(citation.get("url") or "") for citation in response.citations
            if isinstance(citation, dict)
        }
        for source in safe_web_sources:
            if source["url"] in existing_urls:
                continue
            response.citations.append({
                "title": source["title"],
                "url": source["url"],
                "excerpt": source["excerpt"],
            })
            existing_urls.add(source["url"])
        for block in response.blocks:
            if block.get("type") not in {"source", "sources", "source_group"}:
                continue
            for item in block.get("items") or []:
                item_url = str(item.get("url") or "")
                source = next((candidate for candidate in safe_web_sources if candidate["url"] == item_url), None)
                if source:
                    item.update({
                        "id": source["id"], "title": source["title"], "url": source["url"],
                        "kind": "web", "favicon": source["favicon"],
                        "detail": str(item.get("detail") or source["excerpt"] or "")[:700],
                        "content": source["content"],
                    })
        has_web_block = any(
            block.get("type") == "source_group" and any(
                item.get("kind") == "web" and item.get("url") in seen_urls for item in block.get("items") or []
            ) for block in response.blocks
        )
        if not has_web_block:
            response.blocks = [*response.blocks[:2], {
                "type": "source_group",
                "title": "Fontes consultadas",
                "summary": (
                    f"Consultei {len(safe_web_sources)} fonte"
                    f"{'s' if len(safe_web_sources) != 1 else ''} pública"
                    f"{'s' if len(safe_web_sources) != 1 else ''} e li seletivamente os resultados mais relevantes."
                ),
                "items": [{
                    "id": source["id"], "title": source["title"],
                    "detail": source["excerpt"], "content": source["content"], "kind": source["kind"], "url": source["url"], "favicon": source["favicon"],
                } for source in safe_web_sources[:8]],
            }]
    return response


def prepare(data):
    message = _message(data.get("message"))
    identity = TurnIdentity.from_payload(data)
    run_id = identity.run_id
    conversation_id = identity.conversation_id
    current = resolve(conversation_id=conversation_id, request_id=run_id,
                      surface=str(data.get("surface") or "conversations"),
                      active_object=data.get("active_object"),
                      project_ref=data.get("project_ref"), brand_ref=data.get("brand_ref"))
    rollout = RuntimeRollout.current(
        client_id=current.client_id, user_id=current.user_id,
        is_internal=bool(session.get("is_centralcomm")) if has_request_context() else False,
    )
    current = replace(current, selected_context=selected_context(data.get("selected_context")))
    file_ids = validate_files(data.get("files"))
    uploads = repository.rows(
        """SELECT id, provider_id, kind, name FROM cadu_family_chat_uploads
             WHERE id::text = ANY(%s) AND user_id = %s AND client_id = %s""",
        ([str(value) for value in file_ids], current.user_id, current.client_id),
    ) if file_ids else []
    if len(uploads) != len(set(str(value) for value in file_ids)):
        abort(403, description="Um arquivo não pertence a este ambiente ou usuário.")
    try:
        CaduCreditConnector().authorize(
            CreditActor.from_values(current.client_id, current.user_id),
            max(1, int(current_app.config.get("CADU_CHAT_ADMISSION_TOKENS", 8000) or 8000)),
        )
    except InsufficientToolCredits as exc:
        abort(409, description=str(exc))
    previous_messages = (repository.conversation_messages(
        current.user_id, current.client_id, conversation_id
    ) if identity.conversation_supplied else []) or []
    requested_mode = data.get("execution_mode") or data.get("depth") or data.get("mode") or ""
    builder = ConversationContextBuilder()
    try:
        built_context = builder.build(
            message=message, messages=previous_messages, request_context=current,
            conversation_id=conversation_id if identity.conversation_supplied else None,
            memory_enabled=rollout.memory_v2 and rollout.runtime_v2,
        )
    except Exception:
        current_app.logger.exception("Memória longa indisponível; conversa=%s", conversation_id)
        built_context = builder.build(
            message=message, messages=previous_messages, request_context=current,
            conversation_id=conversation_id if identity.conversation_supplied else None, memory_enabled=False,
        )
    current = built_context.request_context
    execution = prepare_execution(message, current, built_context.history, requested_mode,
                                  conversation_state=built_context.state,
                                  routing_message=built_context.routing_message)
    if uploads:
        execution["provider_payload"]["files"] = [
            {"type": row["kind"], "transfer_method": "local_file", "upload_file_id": row["provider_id"]}
            for row in uploads
        ]
    runtime = provider.runtime_for(execution["execution_mode"])
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cadu_family_chat_runs WHERE id = %s", (run_id,))
            if cur.fetchone():
                abort(409, description="Este envio já foi recebido.")
            cur.execute("""SELECT id FROM cadu_conversations
                            WHERE id = %s AND id_contato_cliente = %s AND id_cliente = %s FOR UPDATE""",
                        (conversation_id, current.user_id, current.client_id))
            existing = cur.fetchone()
            if identity.conversation_supplied and not existing:
                abort(404)
            if not existing:
                cur.execute("""INSERT INTO cadu_conversations
                    (id, id_cliente, id_contato_cliente, titulo, status, total_mensagens, projeto_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, 'ativa', 0, %s, NOW(), NOW())""",
                    (conversation_id, current.client_id, current.user_id, message[:120],
                     current.project_ref[3:] if current.project_ref and current.project_ref.startswith("ci:") else None))
                cur.execute("""INSERT INTO cadu_family_conversation_context
                    (conversation_id, user_id, organization_id, client_id, profile, project_ref, brand_ref)
                    VALUES (%s, %s, %s, %s, 'workspace', %s, %s)""",
                    (conversation_id, current.user_id, current.organization_id, current.client_id,
                     current.project_ref, current.brand_ref))
            else:
                # Persist a context repaired from the explicitly selected,
                # authorized turn so reopening the thread cannot regress to a
                # visually active but operationally context-free state.
                cur.execute("""UPDATE cadu_family_conversation_context
                                  SET project_ref=COALESCE(project_ref,%s),
                                      brand_ref=COALESCE(brand_ref,%s)
                                WHERE conversation_id=%s AND user_id=%s
                                  AND organization_id=%s AND client_id=%s""",
                            (current.project_ref, current.brand_ref, conversation_id,
                             current.user_id, current.organization_id, current.client_id))
                if current.project_ref and current.project_ref.startswith("ci:"):
                    cur.execute("""UPDATE cadu_conversations SET projeto_id=COALESCE(projeto_id,%s)
                                    WHERE id=%s AND id_contato_cliente=%s AND id_cliente=%s""",
                                (current.project_ref[3:], conversation_id, current.user_id, current.client_id))
            cur.execute("""SELECT id FROM cadu_family_chat_runs
                            WHERE conversation_id = %s AND status = 'running'""", (conversation_id,))
            if cur.fetchone():
                abort(409, description="Aguarde a resposta atual ou interrompa a geração.")
            # CentralX owns the canonical conversation history and sends a
            # bounded copy in the V2 evidence envelope. Reusing the provider's
            # conversation id would create a second, invisible memory that can
            # retain obsolete prompts and conflict with the persisted thread.
            cur.execute("""INSERT INTO cadu_family_chat_runs
                (id, conversation_id, user_id, client_id, status, runtime_version, execution_mode,
                 runtime_id, provider_config_version, route, request_context, response_policy, context_chars, created_at)
                VALUES (%s, %s, %s, %s, 'running', 'v2', %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (run_id, conversation_id, current.user_id, current.client_id,
                 execution["execution_mode"], runtime["id"], runtime["config_version"],
                 Json(execution["route"]), Json(current.to_dict()), Json(execution["policy"]),
                 len(execution["provider_payload"]["inputs"]["evidence"])))
            cur.execute("""INSERT INTO cadu_conversation_messages
                (id, conversation_id, role, content, files, metadata, created_at)
                VALUES (%s, %s, 'user', %s, %s, %s, NOW())""",
                (str(uuid4()), conversation_id, message,
                 Json([{"id": str(row["id"]), "name": row["name"]} for row in uploads]),
                 Json({"runtime": "v2", "selected_context": execution.get("selected_context")})))
            for call in execution["resolved_context"].tool_calls:
                cur.execute("""INSERT INTO cadu_agent_tool_calls
                    (id, run_id, tool_name, status, input_redacted, output_summary, error_code,
                     created_at, finished_at)
                    VALUES (%s, %s, %s, %s, '{}'::jsonb, %s, %s, NOW(), NOW())""",
                    (str(uuid4()), run_id, call["name"],
                     "completed" if call["status"] == "completed" else "failed",
                     Json({"available": call["status"] == "completed"}), call.get("code")))
                cur.execute("""UPDATE cadu_agent_tool_calls SET duration_ms=%s
                                WHERE run_id=%s AND tool_name=%s""",
                            (call.get("duration_ms"), run_id, call["name"]))
        conn.commit()
        journal.persist_plan(run_id, execution["plan"], execution["resolved_context"].tool_calls)
        _journal(run_id, "run.admitted", {"execution_mode": execution["execution_mode"],
                 "runtime_id": runtime["id"], "provider_config_version": runtime["config_version"],
                 "route": execution["route"], "budget": execution["budget"],
                 "selected_context": bool(execution.get("selected_context")),
                 "context_diagnostics": built_context.diagnostics,
                 "rollout": rollout.public_metadata()})
    except Exception:
        conn.rollback()
        raise
    return {
        "run_id": run_id, "conversation_id": conversation_id, "message": message,
        "context": current, "runtime": runtime, "context_diagnostics": built_context.diagnostics,
        "rollout": rollout.public_metadata(), **execution,
    }


def stream(run):
    run_started = perf_counter()
    execution_mode = run.get("execution_mode") or "analysis"
    provider_started = None
    first_token_ms = None
    answer_chunks, usage, provider_id, task_id = [], {}, None, None
    streamed_answer = ""
    state, assistant_id = "failed", None
    terminal_message = None
    terminal_error_code = None
    runtime = run.get("runtime") or {}
    _journal(run["run_id"], "run.started", {"conversation_id": run["conversation_id"],
             "execution_mode": execution_mode})
    yield _event(
        "run.started", run_id=run["run_id"], conversation_id=run["conversation_id"],
        execution_mode=execution_mode, resolved_context={
            "project_ref": run["context"].project_ref,
            "brand_ref": run["context"].brand_ref,
        }, runtime_id=runtime.get("id", ""),
        provider_config_version=runtime.get("config_version", ""),
        context_diagnostics=run.get("context_diagnostics") or {},
        rollout=run.get("rollout") or {},
    )
    _journal(run["run_id"], "route.selected", {"route": run["route"], "policy": run["policy"]})
    yield _event("route.selected", route=run["route"], policy=run["policy"])
    waiting_actions = journal.waiting_actions(
        run["run_id"], run["context"].client_id, run["context"].user_id,
    )
    for action in waiting_actions:
        public_action = {**action, "run_id": run["run_id"]}
        _journal(run["run_id"], "action.proposed", public_action, item_type="action")
        yield _event("action.proposed", action=public_action)
    for call in run["resolved_context"].tool_calls:
        _journal(run["run_id"], "tool.completed" if call["status"] == "completed" else "tool.unavailable",
                 call, item_type="activity", duration_ms=call.get("duration_ms"))
        yield _event("tool.completed" if call["status"] == "completed" else "tool.unavailable", **call)
    # These are bounded mutations whose server-authored approval proposal is
    # the complete response. Calling the provider afterwards can fabricate a
    # success message before the user has approved and executed the action.
    proposal_only_actions = {"projects.create_link_reference", "workspace.update_project_context"}
    if any(action.get("name") in proposal_only_actions for action in waiting_actions):
        conn = repository.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""UPDATE cadu_family_chat_runs
                               SET status='completed', finished_at=NOW(), total_duration_ms=%s,
                                   provider_duration_ms=0, input_tokens=0, output_tokens=0
                             WHERE id=%s AND status='running'""",
                            (round((perf_counter() - run_started) * 1000), run["run_id"]))
            conn.commit()
        except Exception:
            conn.rollback()
            current_app.logger.exception("Falha ao finalizar proposta de ação %s", run["run_id"])
        payload = {"status": "completed", "conversation_id": run["conversation_id"],
                   "total_duration_ms": round((perf_counter() - run_started) * 1000)}
        _journal(run["run_id"], "run.completed", payload, item_type="activity")
        yield _event("run.completed", **payload)
        return
    try:
        provider_started = perf_counter()
        for item in provider.events(run["provider_payload"], execution_mode):
            if first_token_ms is None and (item.get("answer") or item.get("event") in {"message", "agent_message"}):
                first_token_ms = round((perf_counter() - run_started) * 1000)
                _journal(run["run_id"], "provider.first_token", {"first_token_ms": first_token_ms},
                         duration_ms=first_token_ms)
                yield _event("provider.first_token", first_token_ms=first_token_ms)
            provider_id = item.get("conversation_id") or provider_id
            next_task_id = item.get("task_id")
            if next_task_id and next_task_id != task_id:
                task_id = next_task_id
                conn = repository.get_db()
                with conn.cursor() as cur:
                    cur.execute("UPDATE cadu_family_chat_runs SET task_id = %s WHERE id = %s AND status = 'running'",
                                (task_id, run["run_id"]))
                conn.commit()
            if item.get("event") in {"message", "agent_message"} and item.get("answer"):
                answer_chunks.append(str(item["answer"]))
                visible_answer = _streamable_answer("".join(answer_chunks))
                if not run["route"].get("artifact_type") and visible_answer and visible_answer != streamed_answer:
                    streamed_answer = visible_answer
                    yield _event("answer.delta", answer=streamed_answer)
            if item.get("event") == "message_end":
                usage = (item.get("metadata") or {}).get("usage") or {}
        if _run_was_cancelled(run["run_id"]):
            state = "cancelled"
        else:
            response = normalize_response("".join(answer_chunks), run["policy"])
            response = _preserve_streamed_answer(response, streamed_answer, run["policy"])
            response = _enrich_source_blocks(response, run)
            artifact = None
            # A response patch is only materialized when the route explicitly
            # requested an artifact. General answers must never silently turn
            # into a document just because a provider returned dense text.
            artifact_type = run["route"].get("artifact_type")
            project_map_registry = run["resolved_context"].values.get("projects.list_resources") or {}
            project_map_resources = (
                project_map_registry.get("resources")
                if isinstance(project_map_registry, dict) else []
            )
            can_build_project_map = artifact_type != "project_map" or bool(project_map_resources)
            if artifact_type and can_build_project_map and (response.artifact_patch or artifact_type == "project_map"):
                artifact_content = response.artifact_patch or {}
                if artifact_type == "project_map":
                    artifact_content = _project_map_content(run, response.artifact_patch)
                artifact_title = str(artifact_content.get("title") or response.answer)[:120]
                active = run["context"].active_object
                if (active and active.type == f"artifact:{artifact_type}"
                        and str(run["route"].get("action") or "").startswith("update_")):
                    existing_artifact = get_artifact(run["context"], active.id)
                else:
                    existing_artifact = None
                if existing_artifact and existing_artifact.get("type") == artifact_type:
                    artifact = patch_artifact(
                        run["context"], active.id,
                        {**(existing_artifact.get("content") or {}), **artifact_content},
                        expected_version=existing_artifact["current_version"],
                        title=artifact_title,
                        change_summary="Revisão pelo Cadu",
                    )
                else:
                    artifact = create_draft(
                        replace(run["context"], project_ref=None)
                        if run["policy"].get("artifact_scope") == "session" else run["context"],
                        artifact_type, artifact_content,
                        title=artifact_title,
                        conversation_id=run["conversation_id"],
                    )
                _complete_step(run["run_id"], "artifact", {"artifact_id": str(artifact["id"])})
                _journal(run["run_id"], "artifact.created", {"artifact_id": str(artifact["id"]),
                         "type": artifact_type}, item_type="artifact")
                yield _event("artifact.created", artifact=artifact)
            _complete_step(run["run_id"], "generate", {"answer_chars": len(response.answer)})
            _journal(run["run_id"], "answer.completed", {"response": asdict(response)}, item_type="message")
            yield _event("answer.completed", response=asdict(response))
            state = "completed"
            conn = repository.get_db()
            with conn.cursor() as cur:
                assistant_id = str(uuid4())
                cur.execute("""INSERT INTO cadu_conversation_messages
                    (id, conversation_id, role, content, tokens_entrada, tokens_saida, metadata, created_at)
                    VALUES (%s, %s, 'assistant', %s, %s, %s, %s, NOW())""",
                    (assistant_id, run["conversation_id"], response.answer,
                     max(0, int(usage.get("prompt_tokens") or 0)),
                     max(0, int(usage.get("completion_tokens") or 0)),
                     Json({"runtime": "v2", "response": asdict(response),
                           "artifact_id": str(artifact["id"]) if artifact else None})))
                cur.execute("""UPDATE cadu_conversations
                    SET total_mensagens = (SELECT COUNT(*) FROM cadu_conversation_messages WHERE conversation_id = %s),
                        total_tokens_entrada = COALESCE(total_tokens_entrada, 0) + %s,
                        total_tokens_saida = COALESCE(total_tokens_saida, 0) + %s, updated_at = NOW()
                    WHERE id = %s""",
                    (run["conversation_id"], max(0, int(usage.get("prompt_tokens") or 0)),
                     max(0, int(usage.get("completion_tokens") or 0)), run["conversation_id"]))
            conn.commit()
            if usage:
                try:
                    charge = CaduCreditConnector().charge_provider(
                        actor=CreditActor.from_values(run["context"].client_id, run["context"].user_id),
                        idempotency_key="chat-v2:" + run["run_id"], app="Cadu Chat", stage="conversa-v2",
                        provider_result={"usage": usage, "model": run["runtime"]["id"]},
                        metadata={"conversation_id": run["conversation_id"], "runtime_id": run["runtime"]["id"],
                                  "provider_conversation_id": provider_id or ""},
                    )
                    if charge:
                        conn = repository.get_db()
                        with conn.cursor() as cur:
                            cur.execute("""UPDATE cadu_family_chat_runs SET charged_credits=%s,
                                           estimated_cost_usd=%s WHERE id=%s""",
                                        (int(charge.get("tokens_cobrados") or charge.get("charged_tokens") or 0),
                                         charge.get("custo_interno") or charge.get("internal_cost_usd") or 0, run["run_id"]))
                        conn.commit()
                except Exception:
                    # The answer is already durable. Billing reconciliation uses
                    # the idempotency key and must not corrupt the customer turn.
                    current_app.logger.exception("Falha de cobrança no run V2 %s", run["run_id"])
    except provider.ProviderUnavailable:
        if _run_was_cancelled(run["run_id"]):
            state = "cancelled"
        else:
            current_app.logger.exception("Runtime Cadu indisponível; run=%s", run["run_id"])
            terminal_error_code = "provider_unavailable"
            _complete_step(run["run_id"], "generate", error_code=terminal_error_code)
            terminal_message = "O agente desta conversa está temporariamente indisponível. Tente novamente em instantes."
    except Exception:
        if _run_was_cancelled(run["run_id"]):
            state = "cancelled"
        else:
            current_app.logger.exception("Falha no runtime Cadu Conversations V2; run=%s", run["run_id"])
            terminal_error_code = "provider_failed"
            _complete_step(run["run_id"], "generate", error_code=terminal_error_code)
            terminal_message = "A execução foi interrompida. Tente novamente."
    finally:
        total_duration_ms = round((perf_counter() - run_started) * 1000)
        provider_duration_ms = round((perf_counter() - provider_started) * 1000) if provider_started else None
        conn = repository.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""UPDATE cadu_family_chat_runs
                               SET status = CASE WHEN status = 'cancelled' THEN status ELSE %s END,
                                   task_id = COALESCE(%s, task_id), finished_at = NOW(),
                                   first_token_ms=%s, total_duration_ms=%s, provider_duration_ms=%s,
                                   input_tokens=%s, output_tokens=%s,
                                   terminal_error_code=CASE WHEN %s='failed' THEN %s ELSE NULL END
                               WHERE id = %s""", (state, task_id, first_token_ms, total_duration_ms,
                                  provider_duration_ms, max(0, int(usage.get("prompt_tokens") or 0)),
                                  max(0, int(usage.get("completion_tokens") or 0)), state,
                                  terminal_error_code or "provider_failed", run["run_id"]))
            conn.commit()
        except Exception:
            conn.rollback()
            current_app.logger.exception("Falha ao finalizar run V2 %s", run["run_id"])
    # A cancelled provider may still deliver a late chunk after the stop was
    # recorded. Never turn that stale text into conversation history. Failed
    # runs may retain an already-visible partial answer with an explicit state.
    if state == "failed" and streamed_answer.strip() and not assistant_id:
        try:
            assistant_id = str(uuid4())
            conn = repository.get_db()
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO cadu_conversation_messages
                    (id, conversation_id, role, content, tokens_entrada, tokens_saida, metadata, created_at)
                    VALUES (%s, %s, 'assistant', %s, %s, %s, %s, NOW())""",
                    (assistant_id, run["conversation_id"], streamed_answer,
                     max(0, int(usage.get("prompt_tokens") or 0)),
                     max(0, int(usage.get("completion_tokens") or 0)),
                     Json({"runtime": "v2", "terminal_state": state, "partial": True})))
                cur.execute("""UPDATE cadu_conversations
                    SET total_mensagens = (SELECT COUNT(*) FROM cadu_conversation_messages WHERE conversation_id = %s),
                        updated_at = NOW() WHERE id = %s""",
                    (run["conversation_id"], run["conversation_id"]))
            conn.commit()
        except Exception:
            conn.rollback()
            assistant_id = None
            current_app.logger.exception("Falha ao persistir resposta parcial; run=%s", run["run_id"])
    terminal_event = "run.completed" if state == "completed" else "run.cancelled" if state == "cancelled" else "run.failed"
    terminal_payload = {
        "status": state,
        "message_terminal_state": state,
        "conversation_id": run["conversation_id"],
        "message_id": assistant_id,
        "total_duration_ms": round((perf_counter() - run_started) * 1000),
    }
    if terminal_message:
        terminal_payload["message"] = terminal_message
        terminal_payload["code"] = terminal_error_code or "provider_failed"
    _journal(run["run_id"], terminal_event, terminal_payload,
             item_type="error" if state == "failed" else "activity")
    # Persist only a lightweight queue row before yielding the terminal event.
    # The projection itself runs in a supervised worker; enqueueing first means
    # a client disconnect immediately after completion cannot lose the job.
    if state == "completed" and assistant_id and (run.get("rollout") or {}).get("memory_v2", True):
        try:
            schedule_memory_checkpoint(
                conversation_id=run["conversation_id"], organization_id=run["context"].organization_id,
                client_id=run["context"].client_id, user_id=run["context"].user_id,
            )
        except Exception:
            current_app.logger.exception("Não foi possível agendar checkpoint de memória; conversa=%s",
                                         run["conversation_id"])
    yield _event(terminal_event, **terminal_payload)
