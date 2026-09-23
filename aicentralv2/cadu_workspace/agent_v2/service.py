"""Admission, execution and persistence for a complete Conversations V2 turn."""

import json
import re
import unicodedata
from html import unescape
from dataclasses import asdict, replace
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4

from flask import abort, current_app, has_app_context, has_request_context, session, url_for
from psycopg.types.json import Json

from ...db import close_db
from ...cadu_credit_connector import CaduCreditConnector, CreditActor
from ...cadu_family import repository
from ...cadu_tool_billing import InsufficientToolCredits
from ..conversations.guardrails import validate_files
from ..artifacts import create_draft, get_artifact, patch_artifact
from ..artifacts.service import list_artifacts
from . import provider
from .executor import prepare_execution
from .guardrails import normalize_response
from .request_context import resolve
from .contracts import ActiveObject
from . import journal
from .context_builder import (
    ConversationContextBuilder,
    previous_assistant_context,
    selected_context,
    turn_context,
    turn_selected_context,
)
from .conversation_runtime import RuntimeRollout, TurnIdentity
from .memory_checkpoint import schedule as schedule_memory_checkpoint
from ..workspace_action_policy import WORKSPACE_ONLY_ACTIONS, action_link


PROJECT_MAP_MAX_RESOURCES = 120
PROJECT_MAP_MAX_RELATIONS = 200
PROJECT_MAP_GROUP_MAX_HEIGHT = 520


def _event(kind, **values):
    return "data: " + json.dumps({"event": kind, **values}, ensure_ascii=False, default=str) + "\n\n"


def _plain(value):
    folded = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(char for char in folded if not unicodedata.combining(char))))


def _revision_summary(before, after):
    """Describe changed document sections from persisted content, not model claims."""
    def sections(content):
        markup = str((content or {}).get("html") or "")
        headings = list(re.finditer(r"<h[1-3]\b[^>]*>(.*?)</h[1-3]>", markup, re.I | re.S))
        return {
            _plain(unescape(re.sub(r"<[^>]+>", "", match.group(1)))): (
                unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip(),
                unescape(re.sub(r"<[^>]+>", " ", markup[match.end():headings[index + 1].start() if index + 1 < len(headings) else len(markup)]))
            )
            for index, match in enumerate(headings)
        }
    old_sections, new_sections = sections(before), sections(after)
    changed = [(new_sections.get(name) or old_sections[name])[0]
               for name in dict.fromkeys([*old_sections, *new_sections])
               if old_sections.get(name) != new_sections.get(name)]
    if changed:
        return "Seções revisadas: " + ", ".join(changed[:4])[:420]
    keys = [key for key in dict.fromkeys([*(before or {}), *(after or {})])
            if key not in {"title", "_provenance"} and (before or {}).get(key) != (after or {}).get(key)]
    return "Campos revisados: " + ", ".join(keys[:5]) if keys else "Título atualizado"


def _revision_target(message, context, previous_messages):
    """Resolve a named document or section across the conversation and active project."""
    if not re.search(r"\b(?:mud|alter|revis|atualiz|corrig|edit|ajust|melhor|inclu|acrescent|reescrev|refin|apliqu|aplicar|implement|j[aá]\s+est[aá]\s+decid|n[aã]o\s+precisa\s+mais)", message, re.I):
        return context
    section = re.search(r"\b(?:parte|se[cç][aã]o|trecho|bloco|t[oó]pico)\s+[“\"]?([^\n,.;:!?\"”]{5,100})", message, re.I)
    section_name = _plain(re.split(r"\s+(?:isso|que\s+j[aá]|porque|pois)\b", section.group(1), maxsplit=1, flags=re.I)[0]) if section else ""
    request_text = _plain(message)
    active_id = context.active_object.id if context.active_object and context.active_object.type.startswith("artifact:") else ""
    candidates = []
    for item in reversed(previous_messages[-40:]):
        metadata = item.get("metadata") if isinstance(item, dict) else None
        artifact_id = metadata.get("artifact_id") if isinstance(metadata, dict) else None
        if artifact_id and str(artifact_id) not in candidates:
            candidates.append(str(artifact_id))
    if active_id and active_id not in candidates:
        candidates.insert(0, active_id)
    conversation_candidates = set(candidates)
    if context.project_ref and (section_name or re.search(r"\b(?:briefing|documento|plano|relat[oó]rio|apresenta[cç][aã]o)\b", message, re.I)):
        try:
            candidates.extend(str(item["id"]) for item in list_artifacts(context, limit=20)
                              if str(item["id"]) not in candidates)
        except Exception:
            pass
    matches = []
    authorized = []
    for index, artifact_id in enumerate(dict.fromkeys(candidates)):
        try:
            artifact = get_artifact(context, artifact_id)
        except Exception:
            continue
        artifact_project = artifact.get("project_ref")
        if artifact_project:
            if not repository.project_user_can_view(context.client_id, artifact_project, context.user_id):
                continue
        elif int(artifact.get("created_by") or 0) != context.user_id:
            continue
        authorized.append(artifact)
        title = _plain(artifact.get("title"))
        content = _plain(json.dumps(artifact.get("content") or {}, ensure_ascii=False))
        title_named = len(title) >= 8 and title not in {"resultado do trabalho", "documento editavel"} and title in request_text
        section_found = len(section_name) >= 8 and section_name in content
        score = (100 if section_found else 0) + (80 if title_named else 0) + (15 if artifact_id == active_id else 0) - index
        if section_name and not section_found and not title_named:
            continue
        matches.append((score, artifact, section_found, title_named))
    if not matches:
        if section_name:
            return replace(context, active_object=None, selected_context={
                "type": "artifact_missing", "text": f"Não encontrei um arquivo autorizado com a seção: {section_name}",
            })
        fallback = next((item for item in authorized if str(item["id"]) == active_id), None)
        recent = [item for item in authorized if str(item["id"]) in conversation_candidates]
        if not fallback and len(recent) == 1:
            fallback = recent[0]
        if not fallback and len(authorized) == 1:
            fallback = authorized[0]
        named_kind = next((kind for kind in ("briefing", "plano de midia", "relatorio", "apresentacao")
                           if kind in request_text), "")
        if fallback and named_kind and named_kind not in _plain(fallback.get("title")):
            fallback = None
        if fallback:
            return replace(context, project_ref=fallback.get("project_ref"),
                           active_object=ActiveObject(f"artifact:{fallback['type']}", str(fallback["id"])))
        return context
    matches.sort(key=lambda pair: pair[0], reverse=True)
    named_matches = [item for item in matches if item[3]]
    section_matches = [item for item in matches if item[2]]
    ambiguous = named_matches if len(named_matches) > 1 else (
        section_matches if section_name and not named_matches and len(section_matches) > 1 else []
    )
    if ambiguous:
        names = [str(item[1].get("title") or "Documento") for item in ambiguous][:3]
        return replace(context, active_object=None, selected_context={
            "type": "artifact_ambiguity", "text": "Mais de um arquivo corresponde ao pedido: " + "; ".join(names),
        })
    artifact = matches[0][1]
    return replace(context, project_ref=artifact.get("project_ref"),
                   active_object=ActiveObject(f"artifact:{artifact['type']}", str(artifact["id"])))


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


_PROJECT_CONTEXT_DENIAL = re.compile(
    r"\b(?:n[aã]o tenho (?:contexto|acesso|informa[cç][oõ]es)|"
    r"n[aã]o h[aá] (?:contexto|informa[cç][oõ]es)|"
    r"n[aã]o sei (?:nada|o suficiente))\b.{0,120}\bprojeto\b",
    re.IGNORECASE | re.DOTALL,
)


def _repair_project_context_denial(response, run) -> bool:
    """Use saved fields if the provider denies context that Python already read."""
    if run["route"].get("action") != "describe_project" or not _PROJECT_CONTEXT_DENIAL.search(response.answer or ""):
        return False
    evidence = run["resolved_context"].values.get("workspace.search_project_content") or {}
    if not isinstance(evidence, dict) or evidence.get("context_status") != "available":
        return False
    project = evidence.get("project") or {}
    if not isinstance(project, dict):
        return False
    name = " ".join(str(project.get("nome") or "").split())[:180]
    description = " ".join(str(project.get("descricao") or "").split())[:1000]
    instructions = " ".join(str(project.get("instrucoes") or "").split())[:600]
    if not any((name, description, instructions)):
        return False
    parts = [f"O projeto **{name}** está cadastrado no Workspace." if name else "Encontrei o projeto selecionado no Workspace."]
    if description:
        parts.append(f"Descrição salva: {description}")
    if instructions:
        parts.append(f"Instruções salvas: {instructions}")
    inventory = evidence.get("source_inventory") or {}
    if int(inventory.get("needs_index") or 0) > 0:
        parts.append("Há arquivos do projeto que ainda precisam de indexação para uma leitura completa.")
    response.answer = "\n\n".join(parts)
    response.confidence = "medium"
    response.questions = []
    response.actions = []
    response.blocks = []
    return True


def _html_failure_code(response, finish_reason=""):
    if response.artifact_patch:
        return None
    reason = str(finish_reason or "").strip().lower()
    if reason in {"length", "max_tokens", "token_limit", "max_output_tokens"}:
        return "html_generation_truncated"
    return "html_generation_invalid"


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


def _provider_conversation(cur, *, conversation_id, runtime_id, client_id, user_id):
    """Return the scoped provider session for this canonical conversation/runtime."""
    cur.execute("""SELECT provider_conversation_id
                     FROM cadu_agent_provider_sessions
                    WHERE conversation_id=%s AND runtime_id=%s
                      AND client_id=%s AND user_id=%s""",
                (conversation_id, runtime_id, client_id, user_id))
    row = cur.fetchone()
    return str(row.get("provider_conversation_id") or "") if row else ""


def _save_provider_conversation(cur, *, conversation_id, runtime_id,
                                provider_conversation_id, client_id, user_id):
    """Bind Dify continuity to Cadu's canonical, access-scoped conversation."""
    value = str(provider_conversation_id or "").strip()
    if not value:
        return
    cur.execute("""INSERT INTO cadu_agent_provider_sessions
        (conversation_id,client_id,user_id,runtime_id,provider_conversation_id,created_at,updated_at)
        VALUES (%s,%s,%s,%s,%s,NOW(),NOW())
        ON CONFLICT (conversation_id,runtime_id) DO UPDATE SET
            client_id=EXCLUDED.client_id,user_id=EXCLUDED.user_id,
            provider_conversation_id=EXCLUDED.provider_conversation_id,updated_at=NOW()
        WHERE cadu_agent_provider_sessions.client_id=EXCLUDED.client_id
          AND cadu_agent_provider_sessions.user_id=EXCLUDED.user_id""",
                (conversation_id, client_id, user_id, runtime_id, value))


def _resume_provider_conversation(cur, execution, *, conversation_id, runtime_id,
                                  client_id, user_id):
    """Attach the prior Dify session to the next provider payload, if available."""
    value = _provider_conversation(
        cur, conversation_id=conversation_id, runtime_id=runtime_id,
        client_id=client_id, user_id=user_id,
    )
    if value:
        execution["provider_payload"]["conversation_id"] = value
    return value


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
    """Compatibility wrapper for callers predating ConversationContextBuilder."""
    return selected_context(value)


def _previous_assistant_context(message, messages):
    """Compatibility wrapper around the canonical reference resolver."""
    return previous_assistant_context(message, messages)


def _conversation_turn_context(message, messages):
    """Compatibility wrapper around the canonical turn context builder."""
    return turn_context(message, messages)


def _turn_selected_context(turn):
    return turn_selected_context(turn)


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
        query = str(run.get("message") or "").lower()
        person_or_work_query = any(token in query for token in (
            "quem é", "quem foi", "morreu", "biografia", "história", "historia", "carreira", "obra", "artista", "cantor", "autor",
            "marca", "campanha", "campanhas", "case", "trajetória", "trajetoria", "legado", "lançamento", "lancamento",
        ))
        image_limit = 0 if execution_mode == "fast" else 3
        image_items = [source for source in safe_web_sources if source.get("image_url")][:image_limit] if person_or_work_query else []
        if image_items:
            response.blocks = [{
                "type": "images", "title": "Imagens relacionadas",
                "summary": "Imagens encontradas em fontes públicas consultadas.",
                "items": [{"id": f"image-{index}", "title": item["title"], "url": item["image_url"], "source_url": item["url"]}
                          for index, item in enumerate(image_items, 1)],
            }, *response.blocks]
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
    current = _revision_target(message, current, previous_messages)
    requested_mode = data.get("execution_mode") or data.get("depth") or data.get("mode") or ""
    builder = ConversationContextBuilder()
    try:
        built_context = builder.build(
            message=message, messages=previous_messages, request_context=current,
            conversation_id=conversation_id if identity.conversation_supplied else None,
            memory_enabled=rollout.memory_v2,
        )
    except Exception:
        current_app.logger.exception("Memória longa indisponível; conversa=%s", conversation_id)
        built_context = builder.build(
            message=message, messages=previous_messages, request_context=current,
            conversation_id=conversation_id if identity.conversation_supplied else None, memory_enabled=False,
        )
    current = built_context.request_context
    # Memory/context reads are complete. Release their request-scoped
    # connection before web research or any other potentially slow tool.
    close_db()
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
            # Cadu remains the canonical transcript, while the scoped Dify
            # session preserves the provider's native turn-by-turn continuity.
            # Sessions are isolated by runtime because each mode may point to a
            # different Dify application whose conversation IDs are not portable.
            provider_conversation_id = _resume_provider_conversation(
                cur, execution, conversation_id=conversation_id, runtime_id=runtime["id"],
                client_id=current.client_id, user_id=current.user_id,
            )
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
                     Json({"available": call["status"] == "completed",
                           **({"project_evidence": call["project_evidence"]} if call.get("project_evidence") else {})}),
                     call.get("code")))
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
                 "payload_diagnostics": execution.get("payload_diagnostics"),
                 "rollout": rollout.public_metadata()})
    except Exception:
        conn.rollback()
        raise
    return {
        "run_id": run_id, "conversation_id": conversation_id, "message": message,
        "context": current, "runtime": runtime, "context_diagnostics": built_context.diagnostics,
        "provider_conversation_id": provider_conversation_id,
        "rollout": rollout.public_metadata(), **execution,
    }


def stream(run):
    # Admission is complete before the SSE response starts. Do not reserve a
    # PostgreSQL connection while the provider is producing tokens.
    close_db()
    run_started = perf_counter()
    execution_mode = run.get("execution_mode") or "analysis"
    provider_started = None
    first_token_ms = None
    answer_chunks, usage, provider_id, task_id = [], {}, None, None
    streamed_answer = ""
    state, assistant_id = "failed", None
    terminal_message = None
    terminal_error_code = None
    provider_finish_reason = ""
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
        provider_conversation_reused=bool(run.get("provider_conversation_id")),
        context_diagnostics=run.get("context_diagnostics") or {},
        rollout=run.get("rollout") or {},
    )
    target = (getattr(run["resolved_context"], "values", {}) or {}).get("artifacts.get") or {}
    target_summary = (
        {"id": str(target.get("id")), "title": str(target.get("title") or "Documento")[:180]}
        if target.get("id") else None
    )
    _journal(run["run_id"], "route.selected", {"route": run["route"], "policy": run["policy"], "target_artifact": target_summary})
    yield _event("route.selected", route=run["route"], policy=run["policy"], target_artifact=target_summary)
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
            close_db()
        except Exception:
            conn.rollback()
            close_db()
            current_app.logger.exception("Falha ao finalizar proposta de ação %s", run["run_id"])
        payload = {"status": "completed", "conversation_id": run["conversation_id"],
                   "total_duration_ms": round((perf_counter() - run_started) * 1000)}
        _journal(run["run_id"], "run.completed", payload, item_type="activity")
        yield _event("run.completed", **payload)
        return
    try:
        route_action = str(run["route"].get("action") or "")
        workspace_action = None
        if route_action == "choose_artifact":
            selection = run["context"].selected_context or {}
            if selection.get("type") == "artifact_ambiguity":
                titles = [title.strip() for title in str(selection.get("text") or "").partition(":")[2].split(";") if title.strip()][:3]
                if len(titles) != len(set(_plain(title) for title in titles)):
                    answer_chunks.append(json.dumps({
                        "answer": "Encontrei arquivos com o mesmo título. Abra o arquivo certo e peça para aplicar a revisão nele.",
                        "ui": {"blocks": []},
                    }, ensure_ascii=False))
                else:
                    answer_chunks.append(json.dumps({
                        "answer": "Encontrei mais de um arquivo que corresponde ao pedido. Escolha onde devo aplicar a revisão.",
                        "ui": {"blocks": [{"type": "questions", "title": "Escolha o arquivo", "items": [{
                            "id": "artifact-choice", "question": "Em qual arquivo devo aplicar a revisão pedida anteriormente?",
                            "required": True, "allow_custom": True, "options": titles,
                        }]}]},
                    }, ensure_ascii=False))
            else:
                answer_chunks.append(json.dumps({
                    "answer": "Não encontrei a seção indicada nos arquivos disponíveis. Abra o documento que quer revisar ou informe o título dele.",
                    "ui": {"blocks": []},
                }, ensure_ascii=False))
            provider_events = ()
        elif route_action in WORKSPACE_ONLY_ACTIONS:
            workspace_action = action_link(
                route_action, project_ref=run["context"].project_ref,
                brand_ref=run["context"].brand_ref,
            )
            answer_chunks.append(json.dumps({
                "answer": workspace_action["answer"],
                "ui": {"blocks": [workspace_action["block"]]},
            }, ensure_ascii=False))
            provider_events = ()
        else:
            provider_started = perf_counter()
            provider_events = provider.events(run["provider_payload"], execution_mode)
        for item in provider_events:
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
                close_db()
            if item.get("event") in {"message", "agent_message"} and item.get("answer"):
                answer_chunks.append(str(item["answer"]))
                visible_answer = _streamable_answer("".join(answer_chunks))
                if (run["route"].get("action") not in WORKSPACE_ONLY_ACTIONS
                        and run["route"].get("action") != "describe_project"
                        and not run["route"].get("artifact_type")
                        and visible_answer and visible_answer != streamed_answer):
                    streamed_answer = visible_answer
                    yield _event("answer.delta", answer=streamed_answer)
            if item.get("event") == "message_end":
                metadata = item.get("metadata") or {}
                usage = metadata.get("usage") or {}
                provider_finish_reason = str(
                    metadata.get("finish_reason") or metadata.get("stop_reason")
                    or item.get("finish_reason") or item.get("stop_reason") or ""
                ).strip()
                _journal(run["run_id"], "provider.completed", {
                    "finish_reason": provider_finish_reason or "unknown",
                }, item_type="activity")
        if _run_was_cancelled(run["run_id"]):
            state = "cancelled"
        else:
            response = normalize_response("".join(answer_chunks), run["policy"])
            response = _preserve_streamed_answer(response, streamed_answer, run["policy"])
            if _repair_project_context_denial(response, run):
                _journal(run["run_id"], "answer.repaired_project_context_denial", {
                    "project_bound": True,
                    "context_status": "available",
                }, item_type="activity")
            if workspace_action:
                response.answer = workspace_action["answer"]
                response.blocks = [workspace_action["block"]]
                response.actions = []
            response = _enrich_source_blocks(response, run)
            if run["route"].get("action") == "plan_project_tasks" and response.task_proposal:
                proposal = dict(response.task_proposal)
                proposal.pop("initial_list", None)
                existing_tasks = run["resolved_context"].values.get("projects.list_tasks") or {}
                tool_name = ("projects.create_initial_task_list" if not (existing_tasks.get("tasks") or [])
                             else "projects.create_tasks")
                proposed_action = journal.propose_action(
                    run["run_id"], tool_name, proposal,
                    "Criar as tarefas propostas e manter os vínculos com as fontes do projeto.",
                )
                public_action = {**proposed_action, "run_id": run["run_id"]}
                _journal(run["run_id"], "action.proposed", public_action, item_type="action")
                yield _event("action.proposed", action=public_action)
            artifact = None
            # A response patch is only materialized when the route explicitly
            # requested an artifact. General answers must never silently turn
            # into a document just because a provider returned dense text.
            artifact_type = run["route"].get("artifact_type")
            if artifact_type == "html":
                terminal_error_code = _html_failure_code(response, provider_finish_reason)
                if terminal_error_code:
                    _journal(run["run_id"], "artifact.invalid", {
                        "code": terminal_error_code,
                        "finish_reason": provider_finish_reason or "unknown",
                        "type": "html",
                    }, item_type="error")
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
                selected = run["context"].selected_context or {}
                source_message_id = selected.get("source_message_id") if isinstance(selected, dict) else None
                if source_message_id:
                    existing_provenance = artifact_content.get("_provenance")
                    existing_provenance = existing_provenance if isinstance(existing_provenance, dict) else {}
                    artifact_content = {
                        **artifact_content,
                        "_provenance": {
                            **existing_provenance,
                            "conversation_id": str(run["conversation_id"]),
                            "source_message_id": str(source_message_id),
                        },
                    }
                artifact_title = str(artifact_content.get("title") or response.answer)[:120]
                active = run["context"].active_object
                if (active and active.type == f"artifact:{artifact_type}"
                        and str(run["route"].get("action") or "").startswith("update_")):
                    existing_artifact = get_artifact(run["context"], active.id)
                else:
                    existing_artifact = None
                revised_artifact = bool(existing_artifact and existing_artifact.get("type") == artifact_type)
                if revised_artifact:
                    # A revision changes the document body. Keep its identity and
                    # title unless the user explicitly asked to rename it.
                    if not re.search(r"\b(?:renome\w*|mud\w*\s+o\s+t[ií]tulo|alter\w*\s+o\s+t[ií]tulo)\b", run["message"], re.I):
                        artifact_title = existing_artifact["title"]
                    if "title" in artifact_content or "title" in (existing_artifact.get("content") or {}):
                        artifact_content["title"] = artifact_title
                    revised_content = {**(existing_artifact.get("content") or {}), **artifact_content}
                    if (revised_content == (existing_artifact.get("content") or {})
                            and artifact_title == existing_artifact["title"]):
                        response.answer = "Não encontrei uma mudança concreta para salvar neste documento. Diga qual trecho quer ajustar."
                        response.artifact_patch = None
                    else:
                        artifact = patch_artifact(
                            run["context"], active.id, revised_content,
                            expected_version=existing_artifact["current_version"],
                            title=artifact_title,
                            change_summary=_revision_summary(existing_artifact.get("content") or {}, revised_content),
                        )
                elif str(run["route"].get("action") or "").startswith("update_"):
                    response.answer = "Não encontrei o documento certo para revisar. Abra o arquivo ou indique seu título. Nenhuma versão nova foi salva."
                    response.artifact_patch = None
                else:
                    artifact = create_draft(
                        replace(run["context"], project_ref=None)
                        if run["policy"].get("artifact_scope") == "session" else run["context"],
                        artifact_type, artifact_content,
                        title=artifact_title,
                        conversation_id=run["conversation_id"],
                    )
                if artifact:
                    _complete_step(run["run_id"], "artifact", {"artifact_id": str(artifact["id"])})
                    _journal(run["run_id"], "artifact.created", {"artifact_id": str(artifact["id"]),
                             "type": artifact_type}, item_type="artifact")
                    yield _event("artifact.created", artifact=artifact, revised=revised_artifact)
            elif str(run["route"].get("action") or "").startswith("update_") and artifact_type:
                response.answer = "Não consegui aplicar a revisão ao documento. Nenhuma versão nova foi salva."
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
            close_db()
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
                        close_db()
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
                                   terminal_error_code=%s
                               WHERE id = %s""", (state, task_id, first_token_ms, total_duration_ms,
                                  provider_duration_ms, max(0, int(usage.get("prompt_tokens") or 0)),
                                  max(0, int(usage.get("completion_tokens") or 0)),
                                  terminal_error_code, run["run_id"]))
            conn.commit()
            close_db()
        except Exception:
            conn.rollback()
            close_db()
            current_app.logger.exception("Falha ao finalizar run V2 %s", run["run_id"])
        # Provider continuity is a rebuildable projection. Its failure must not
        # roll back the canonical terminal state or leave the conversation busy.
        if provider_id:
            session_conn = repository.get_db()
            try:
                with session_conn.cursor() as cur:
                    _save_provider_conversation(
                        cur, conversation_id=run["conversation_id"],
                        runtime_id=runtime.get("id") or execution_mode,
                        provider_conversation_id=provider_id,
                        client_id=run["context"].client_id, user_id=run["context"].user_id,
                    )
                    cur.execute("""UPDATE cadu_conversations
                                      SET dify_conversation_id=COALESCE(dify_conversation_id,%s)
                                    WHERE id=%s AND id_cliente=%s AND id_contato_cliente=%s""",
                                (provider_id, run["conversation_id"],
                                 run["context"].client_id, run["context"].user_id))
                session_conn.commit()
                close_db()
            except Exception:
                session_conn.rollback()
                close_db()
                current_app.logger.exception(
                    "Falha ao projetar sessão do provedor; conversa=%s runtime=%s",
                    run["conversation_id"], runtime.get("id") or execution_mode,
                )
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
            close_db()
        except Exception:
            conn.rollback()
            close_db()
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
