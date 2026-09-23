"""Project attachment ingestion shared by Workspace UI and MCP adapters."""

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4
from hashlib import sha256
import json
import re
from typing import Optional
from urllib.parse import urlparse

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from psycopg.types.json import Json
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest, Conflict, NotFound
from werkzeug.utils import secure_filename

from ..cadu_skills.repository import charge_project_rag
from ..db import get_db
from . import project_index_service, project_knowledge, project_sources
from .meeting_reference import parse_meeting_invite
from .agent_v2.contracts import RequestContext


UPLOAD_MAX_AGE = 600
OFFICE_ATTACHMENT_EXTENSIONS = {
    ".doc", ".odt", ".rtf", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp",
}
ATTACHMENT_EXTENSIONS = (
    project_sources.ALLOWED_EXTENSIONS
    | project_sources.IMAGE_EXTENSIONS
    | project_sources.CREATIVE_EXTENSIONS
    | project_sources.ARCHIVE_EXTENSIONS
    | OFFICE_ATTACHMENT_EXTENSIONS
)
CATEGORIES = {"brief", "research", "media_plan", "report", "brand_asset", "reference", "contract", "spreadsheet", "other"}
EXTERNAL_RESOURCE_KINDS = {
    "web_page", "document", "spreadsheet", "presentation", "design", "image",
    "video", "audio", "folder", "board", "campaign", "dashboard", "calendar_event",
    "meeting", "workspace_item", "ads_resource", "social_or_ads", "internal_resource",
    "drive_file", "event", "other",
}


def inspect_file_support(filename: str, mime_type: str = "") -> dict:
    """Describe processing support without reading or accepting file content."""
    safe_name = secure_filename(str(filename or ""))[:220]
    suffix = Path(safe_name).suffix.lower()
    mime_type = str(mime_type or "application/octet-stream")[:160]
    if suffix in project_sources.ALLOWED_EXTENSIONS:
        return {"filename": safe_name, "extension": suffix, "mime_type": mime_type,
                "status": "supported", "can_attach": True, "can_index": True,
                "processing": "text_extraction", "requires_adapter": False}
    if suffix in project_sources.IMAGE_EXTENSIONS:
        return {"filename": safe_name, "extension": suffix, "mime_type": mime_type,
                "status": "supported", "can_attach": True, "can_index": True,
                "processing": "ocr", "requires_adapter": False}
    # InDesign packages can be preserved and organized, but not parsed.
    if suffix == '.indd':
        return {"filename": safe_name, "extension": suffix, "mime_type": mime_type,
                "status": "attachment_only", "can_attach": True, "can_index": False,
                "processing": "metadata_only", "requires_adapter": True,
                "reason": "O arquivo é preservado no projeto; ainda não há adapter de leitura."}
    if suffix in ATTACHMENT_EXTENSIONS:
        return {"filename": safe_name, "extension": suffix, "mime_type": mime_type,
                "status": "attachment_only", "can_attach": True, "can_index": False,
                "processing": "metadata_only", "requires_adapter": True}
    families = {
        ".xls": "spreadsheet", ".xlsx": "spreadsheet", ".ods": "spreadsheet",
        ".ppt": "presentation", ".pptx": "presentation", ".odp": "presentation",
        ".mp4": "video", ".mov": "video", ".webm": "video",
        ".mp3": "audio", ".wav": "audio", ".m4a": "audio",
        ".zip": "archive", ".rar": "archive", ".7z": "archive",
    }
    return {"filename": safe_name, "extension": suffix, "mime_type": mime_type,
            "status": "needs_adapter" if suffix in families else "unsupported",
            "can_attach": False, "can_index": False, "processing": "none",
            "format_family": families.get(suffix, "unknown"), "requires_adapter": True,
            "reason": "O formato ainda não possui um adapter seguro no upload MCP."}


def classify_intake(*, filename: str = "", mime_type: str = "", url: str = "", text: str = "",
                    requested_purpose: str = "") -> dict:
    """Classify a proposed Chat input before any file, URL or text is persisted.

    This is deliberately deterministic and read-only. Rich extraction, OCR and
    transcription are later jobs; the first decision must be fast, explainable
    and safe about indexing.
    """
    requested_purpose = str(requested_purpose or "").strip().lower()
    if requested_purpose not in {"", "conversation", "knowledge_source", "project_attachment", "artifact"}:
        raise BadRequest("Finalidade de entrada inválida.")
    normalized_url = str(url or "").strip()
    normalized_text = str(text or "").strip()
    if normalized_url:
        if not re.match(r"^https?://[^\s/$.?#][^\s]*$", normalized_url, re.IGNORECASE):
            raise BadRequest("Informe uma URL http ou https válida.")
        descriptor = describe_link(normalized_url)
        return {
            "input_type": "link", "purpose": requested_purpose or "project_attachment",
            "category": "reference", "index_recommended": False,
            "processing": "reference_only", "requires_confirmation": False,
            "reason": "Links são salvos somente como referência. Leitura, extração e indexação são ações posteriores e explícitas.",
            "link": descriptor,
        }
    if filename:
        support = inspect_file_support(filename, mime_type)
        source = {"name": support["filename"], "suffix": support.get("extension"), "mime": support.get("mime_type")}
        classification = _classify(source, None)
        can_index = bool(support.get("can_index"))
        purpose = requested_purpose or ("knowledge_source" if can_index and classification["category"] in {"brief", "research", "report", "media_plan"} else "project_attachment")
        return {
            "input_type": "file", "purpose": purpose, "category": classification["category"],
            "classification": classification, "index_recommended": bool(purpose == "knowledge_source" and can_index),
            "processing": support.get("processing"), "support": support,
            "requires_confirmation": purpose == "knowledge_source",
        }
    if normalized_text:
        meeting = parse_meeting_invite(normalized_text)
        if meeting:
            descriptor = describe_link(meeting["url"], meeting["title"])
            return {
                "input_type": "link", "purpose": requested_purpose or "project_attachment",
                "category": "reference", "index_recommended": False,
                "processing": "structured_reference", "requires_confirmation": True,
                "reason": "Convite de reunião reconhecido; os dados serão preservados como metadados sem abrir o link.",
                "link": descriptor, "meeting": meeting,
            }
        haystack = normalized_text[:5000].casefold()
        artifact_type = "meeting_summary" if any(token in haystack for token in ("reunião", "reuniao", "ata", "decisões", "decisoes")) else "meeting_agenda" if any(token in haystack for token in ("pauta", "agenda")) else "note"
        return {
            "input_type": "text", "purpose": requested_purpose or "artifact", "category": "reference",
            "artifact_type": artifact_type, "index_recommended": False,
            "processing": "structured_artifact", "requires_confirmation": False,
            "reason": "Texto do chat deve começar como artifact editável; salvar como fonte é uma decisão separada.",
        }
    raise BadRequest("Informe um arquivo, link ou texto para classificar.")


_LINK_PROVIDERS = {
    "meet.google.com": ("google_meet", "Google Meet", "meeting", "authenticated"),
    "calendar.google.com": ("google_calendar", "Google Calendar", "calendar_event", "unknown"),
    "drive.google.com": ("google_drive", "Google Drive", "drive_file", "unknown"),
    "docs.google.com": ("google_drive", "Google Drive", "drive_file", "unknown"),
    "lookerstudio.google.com": ("looker_studio", "Looker Studio", "dashboard", "authenticated"),
    "analytics.google.com": ("google_analytics", "Google Analytics", "dashboard", "authenticated"),
    "ads.google.com": ("google_ads", "Google Ads", "ads_resource", "authenticated"),
    "canva.com": ("canva", "Canva", "design", "unknown"),
    "figma.com": ("figma", "Figma", "design", "unknown"),
    "dropbox.com": ("dropbox", "Dropbox", "drive_file", "unknown"),
    "box.com": ("box", "Box", "drive_file", "unknown"),
    "sharepoint.com": ("sharepoint", "SharePoint", "document", "authenticated"),
    "onedrive.live.com": ("onedrive", "OneDrive", "drive_file", "unknown"),
    "app.slack.com": ("slack", "Slack", "workspace_item", "authenticated"),
    "teams.microsoft.com": ("microsoft_teams", "Microsoft Teams", "meeting", "authenticated"),
    "teams.live.com": ("microsoft_teams", "Microsoft Teams", "meeting", "authenticated"),
    "zoom.us": ("zoom", "Zoom", "meeting", "authenticated"),
    "monday.com": ("monday", "Monday.com", "board", "authenticated"),
    "app.asana.com": ("asana", "Asana", "workspace_item", "authenticated"),
    "airtable.com": ("airtable", "Airtable", "spreadsheet", "authenticated"),
    "sympla.com.br": ("sympla", "Sympla", "event", "public"),
    "sympla.com": ("sympla", "Sympla", "event", "public"),
    "clickup.com": ("clickup", "ClickUp", "workspace_item", "authenticated"),
    "trello.com": ("trello", "Trello", "board", "unknown"),
    "notion.so": ("notion", "Notion", "document", "unknown"),
    "notion.site": ("notion", "Notion", "document", "public"),
    "miro.com": ("miro", "Miro", "board", "unknown"),
    "mural.co": ("mural", "Mural", "board", "unknown"),
    "youtube.com": ("youtube", "YouTube", "video", "public"),
    "youtu.be": ("youtube", "YouTube", "video", "public"),
    "facebook.com": ("meta", "Meta", "social_or_ads", "unknown"),
    "business.facebook.com": ("meta_ads", "Meta Ads", "ads_resource", "authenticated"),
    "adsmanager.facebook.com": ("meta_ads", "Meta Ads", "ads_resource", "authenticated"),
    "tiktok.com": ("tiktok", "TikTok", "social_or_ads", "unknown"),
    "ads.tiktok.com": ("tiktok_ads", "TikTok Ads", "ads_resource", "authenticated"),
    "linkedin.com": ("linkedin", "LinkedIn", "social_or_ads", "unknown"),
}


def describe_link(value: str, title: str = "") -> dict:
    """Classify a URL conservatively without fetching or guessing access.

    URL shape can identify a provider and likely resource type, but it cannot
    prove that a shared document is public. That distinction is intentionally
    left as ``unknown`` until an extractor or authenticated connector checks it.
    """
    raw = str(value or "").strip()
    if raw and "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise BadRequest("Use um link HTTPS válido, sem usuário, senha ou credenciais na URL.")
    matched = next((data for domain, data in sorted(_LINK_PROVIDERS.items(), key=lambda item: len(item[0]), reverse=True)
                    if host == domain or host.endswith(f".{domain}")), None)
    provider, suggested, resource_kind, access_type = matched or (
        "generic", host.removeprefix("www."), "web_page", "unknown",
    )
    internal = parsed.path.startswith("/workspace/") and host in {
        "workspace.centralcomm.media", "localhost", "127.0.0.1",
    }
    if internal:
        provider, resource_kind, access_type = "cadu", "internal_resource", "authenticated"
    embed_type = "youtube" if provider == "youtube" else "none"
    return {
        "url": parsed._replace(fragment="").geturl(),
        "provider": provider,
        "title": str(title or "").strip()[:180] or suggested,
        "resource_kind": resource_kind,
        "access_type": access_type,
        "embed_type": embed_type,
        "connector_recommended": access_type == "authenticated" or provider in {
            "google_drive", "google_calendar", "google_meet", "trello", "notion", "miro", "mural",
        },
    }


def _link_metadata(value: str, title: str = "") -> dict:
    """Normalize a URL without fetching it or accepting credential-bearing URLs."""
    return describe_link(value, title)


def create_link_reference(context: RequestContext, *, url: str, title: str = "",
                          resource_kind: str = "", platform: str = "", external_id: str = "",
                          description: str = "", tags: Optional[list[str]] = None,
                          meeting: Optional[dict] = None) -> dict:
    """Save a project URL as a reference and schedule registry reconciliation.

    Deliberately does not download, parse, or index the remote page. Those are
    explicit future jobs so a pasted link never changes the knowledge base by
    surprise.
    """
    project_id = _project_id(context)
    link = _link_metadata(url, title)
    explicit_kind = str(resource_kind or "").strip().lower()
    if explicit_kind and explicit_kind not in EXTERNAL_RESOURCE_KINDS:
        raise BadRequest("Tipo de recurso externo inválido.")
    link["resource_kind"] = explicit_kind or link["resource_kind"]
    platform = str(platform or "").strip()[:120]
    external_id = str(external_id or "").strip()[:512]
    description = str(description or "").strip()[:4000]
    if tags is not None and not isinstance(tags, list):
        raise BadRequest("As etiquetas do recurso devem ser enviadas como uma lista.")
    normalized_tags = list(dict.fromkeys(
        str(item or "").strip()[:64] for item in (tags or []) if str(item or "").strip()
    ))[:20]
    meeting = dict(meeting or {}) if isinstance(meeting, dict) else {}
    connection = get_db()
    link_id = None
    created = False
    try:
        with connection.cursor() as cursor:
            # The table predates this service and does not guarantee a unique
            # (client, project, url) key. Serialize that natural key so two
            # different MCP request IDs cannot insert the same reference.
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                           (f"cadu-project-link:{context.client_id}:{project_id}:{link['url']}",))
            cursor.execute("""SELECT id::text AS id, titulo FROM cadu_ci_projeto_links
                               WHERE id_cliente=%s AND projeto_id=%s AND url=%s
                               ORDER BY created_at ASC LIMIT 1""",
                           (context.client_id, project_id, link["url"]))
            existing = cursor.fetchone()
            if existing:
                link_id = str(existing["id"])
                link["title"] = existing.get("titulo") or link["title"]
            else:
                link_id = str(uuid4())
                cursor.execute(
                    """INSERT INTO cadu_ci_projeto_links
                       (id, projeto_id, id_cliente, criado_por, provider, url, titulo, position)
                       VALUES (%s, %s, %s, %s, %s, %s, %s,
                               COALESCE((SELECT MAX(position) + 1 FROM cadu_ci_projeto_links
                                         WHERE projeto_id = %s AND id_cliente = %s), 0))""",
                    (link_id, project_id, context.client_id, context.user_id, link["provider"],
                     link["url"], link["title"], project_id, context.client_id),
                )
                created = True
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    try:
        from . import project_resource_service
        project_resource_service.notify_change(
            context.client_id, context.project_ref, "created" if created else "linked",
            source_system="workspace", source_id=f"link:{link_id}", actor_id=context.user_id,
        )
        registry_sync = "queued"
    except Exception:
        current_app.logger.exception("Falha ao enfileirar reconciliação do link %s", link_id)
        registry_sync = "pending"
    return {"link_id": link_id, "url": link["url"], "title": link["title"],
            "provider": link["provider"], "resource_kind": link["resource_kind"],
            "access_type": link["access_type"], "embed_type": link["embed_type"],
            "connector_recommended": link["connector_recommended"], "created": created,
            "platform": platform or link["provider"], "external_id": external_id or None,
            "description": description or None, "tags": normalized_tags, "meeting": meeting or None,
            "purpose": "project_attachment", "indexing": "not_requested",
            "access": "not_checked", "content": "not_read",
            "registry_sync": registry_sync}


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="cadu-mcp-project-upload-v1")


def _project_id(context: RequestContext) -> str:
    if not context.project_ref or not context.project_ref.startswith("ci:"):
        raise BadRequest("Selecione um projeto nativo do Cadu para anexar arquivos.")
    project_id = context.project_ref[3:]
    with get_db().cursor() as cur:
        cur.execute("SELECT id, status FROM cadu_ci_projetos WHERE id = %s AND id_cliente = %s", (project_id, context.client_id))
        row = cur.fetchone()
    if not row:
        raise NotFound("Projeto indisponível.")
    if row["status"] == "arquivado":
        raise Conflict("Reative o projeto antes de anexar arquivos.")
    return str(row["id"])


def prepare_upload(context: RequestContext, *, request_id: str, use_as_knowledge: Optional[bool] = None,
                   category: Optional[str] = None, description: str = "") -> dict:
    project_id = _project_id(context)
    try:
        request_id = str(UUID(str(request_id)))
    except (TypeError, ValueError) as exc:
        raise BadRequest("Identificador do upload inválido.") from exc
    category = str(category or "").strip().lower() or None
    if category and category not in CATEGORIES:
        raise BadRequest("Categoria de arquivo inválida.")
    description = str(description or "").strip()[:4000]
    token = _serializer().dumps({
        "organization_id": context.organization_id, "client_id": context.client_id,
        "user_id": context.user_id, "project_id": project_id,
        "request_id": request_id,
        "use_as_knowledge": use_as_knowledge,
        "category": category,
        "description": description,
    })
    return {
        "upload_token": token,
        "upload_url": "/workspace/mcp/uploads",
        "project_ref": context.project_ref,
        "method": "POST",
        "field": "file",
        "max_bytes": project_sources.MAX_BYTES,
        "use_as_knowledge": use_as_knowledge,
        "purpose": "automatic" if use_as_knowledge is None else "knowledge_source" if use_as_knowledge else "project_attachment",
        "category": category,
        "expires_in": UPLOAD_MAX_AGE,
        "accepted": sorted(ATTACHMENT_EXTENSIONS if use_as_knowledge is not True else project_sources.ALLOWED_EXTENSIONS | project_sources.IMAGE_EXTENSIONS),
    }


def _upload_claims(context: RequestContext, token: str) -> dict:
    try:
        value = _serializer().loads(str(token or ""), max_age=UPLOAD_MAX_AGE)
    except SignatureExpired as exc:
        raise BadRequest("A autorização de upload expirou. Solicite uma nova.") from exc
    except BadSignature as exc:
        raise BadRequest("Autorização de upload inválida.") from exc
    expected = (context.organization_id, context.client_id, context.user_id)
    received = (value.get("organization_id"), value.get("client_id"), value.get("user_id")) if isinstance(value, dict) else ()
    if received != expected:
        raise BadRequest("A autorização de upload não pertence a este contexto.")
    return value


def _storage_root() -> str:
    return str(current_app.config.get("WORKSPACE_SOURCE_STORAGE_DIR") or current_app.instance_path)


def _attachment(file_storage) -> dict:
    source = project_sources.inspect_upload(file_storage, require_text=False)
    return source


def _classify(source: dict, requested: Optional[str], text: str = "") -> dict:
    if requested in CATEGORIES:
        return {"category": requested, "status": "manual", "confidence": 1.0,
                "reason": "Categoria informada pelo usuário."}
    haystack = f"{source.get('name', '')} {text[:4000]}".casefold()
    rules = (
        ("media_plan", ("plano de mídia", "plano de midia", "media plan")),
        ("brief", ("briefing", "brief ")),
        ("report", ("relatório", "relatorio", "report", "dashboard")),
        ("research", ("pesquisa", "research", "estudo de mercado")),
        ("contract", ("contrato", "contract", "proposta comercial")),
        ("brand_asset", ("logo", "marca", "brandbook", "brand book", "manual de marca")),
    )
    for category, signals in rules:
        matched = next((signal for signal in signals if signal in haystack), None)
        if matched:
            return {"category": category, "status": "classified", "confidence": 0.82,
                    "reason": f"Sinal identificado: {matched}."}
    if source.get("suffix") in {".csv", ".xlsx", ".xls"}:
        return {"category": "spreadsheet", "status": "classified", "confidence": 0.95,
                "reason": "Formato de planilha."}
    if source.get("suffix") in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return {"category": "reference", "status": "classified", "confidence": 0.7,
                "reason": "Arquivo visual classificado como referência."}
    return {"category": "other", "status": "needs_review", "confidence": 0.25,
            "reason": "Não há sinais suficientes para uma categoria específica."}


def _schedule_resource_reconciliation(context: RequestContext, source_id: int) -> str:
    """Queue registry reconciliation and repair immediately only if queueing failed."""
    from . import project_resource_service

    try:
        project_resource_service.notify_change(
            context.client_id, context.project_ref, "created", source_system="workspace",
            source_id=f"file:{source_id}", actor_id=context.user_id,
        )
        return "queued"
    except Exception:
        current_app.logger.exception("Falha ao enfileirar organização do recurso %s", source_id)
        try:
            project_resource_service.reconcile(context.client_id, context.project_ref, context.user_id)
            return "reconciled"
        except Exception:
            current_app.logger.exception("Reconciliação imediata indisponível para o recurso %s", source_id)
            return "pending"


def save_upload(context: RequestContext, token: str, file_storage) -> dict:
    claims = _upload_claims(context, token)
    project_id = _project_id(context)
    if project_id != str(claims["project_id"]):
        raise BadRequest("O projeto selecionado mudou. Solicite uma nova autorização de upload.")
    requested_knowledge = claims.get("use_as_knowledge")
    source = project_sources.validate_upload(file_storage) if requested_knowledge is True else _attachment(file_storage)
    description = str(claims.get("description") or "").strip()[:4000]
    if description:
        extracted_can_index = bool(source.get("can_index"))
        source["text"] = (f"Descrição fornecida pelo agente: {description}\n\n"
                          f"Texto extraído do arquivo: {source.get('text') or ''}").strip()
        source["can_index"] = extracted_can_index or len(description) >= 20
    use_as_knowledge = bool(source.get("can_index")) if requested_knowledge is None else bool(requested_knowledge)
    try:
        request_id = str(UUID(str(claims.get("request_id"))))
    except (TypeError, ValueError) as exc:
        raise BadRequest("A autorização de upload não possui identificador válido.") from exc
    content_hash = sha256(source["data"]).hexdigest()
    connection = get_db()
    target = None
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                        (f"cadu-project-upload:{context.client_id}:{context.user_id}:{request_id}",))
            cur.execute("""SELECT id,nome_arquivo AS name,mime AS mime_type,tamanho AS size,purpose,category,
                                  classification_status,classification_confidence,classification_reason,tokens
                             FROM cadu_ci_projeto_arquivos
                            WHERE id_cliente=%s AND projeto_id=%s AND criado_por=%s
                              AND classification_metadata->>'upload_request_id'=%s
                            ORDER BY id DESC LIMIT 1""",
                        (context.client_id, project_id, context.user_id, request_id))
            existing = cur.fetchone()
        if existing:
            connection.commit()
            return {"source_id": int(existing["id"]), "project_ref": context.project_ref,
                    "name": existing["name"], "mime_type": existing["mime_type"],
                    "size": int(existing.get("size") or 0),
                    "use_as_knowledge": existing.get("purpose") == "knowledge_source",
                    "purpose": existing.get("purpose"), "category": existing.get("category"),
                    "classification": {"status": existing.get("classification_status"),
                                       "confidence": float(existing.get("classification_confidence") or 0),
                                       "reason": existing.get("classification_reason")},
                    "status": "indexed" if existing.get("purpose") == "knowledge_source" else "attached",
                    "charged_credits": int(existing.get("tokens") or 0), "idempotent_replay": True}
        target = project_sources.private_path(
            _storage_root(), context.client_id, project_id, source["suffix"], uuid4().hex,
        )
        target.write_bytes(source["data"])
        storage_path = target.relative_to(Path(_storage_root())).as_posix()
        chunks, charged_tokens, extracted_text = [], 0, None
        if use_as_knowledge:
            extracted_text = source["text"]
            chunks, embedding_tokens, embedding_model = project_knowledge.index(extracted_text)
        classification = _classify(source, claims.get("category"), extracted_text or "")
        purpose = "knowledge_source" if use_as_knowledge else "project_attachment"
        with connection.cursor() as cur:
            if use_as_knowledge:
                charged_tokens = charge_project_rag(
                    cur, client_id=context.client_id, user_id=context.user_id, project_id=project_id,
                    tokens=embedding_tokens, stage="indexacao",
                    idempotency_key="mcp-project-rag-index:" + request_id,
                )
                source_id = project_index_service.persist_indexed_source(
                    cur, project_id=project_id, client_id=context.client_id,
                    user_id=context.user_id, name=source["name"], mime=source["mime"],
                    size=len(source["data"]), storage_path=storage_path,
                    source="mcp_upload", content=extracted_text,
                    chunks=chunks, embedding_model=embedding_model,
                    charged_tokens=charged_tokens,
                    classification=classification,
                    metadata={"classifier": "deterministic-v1", "upload_request_id": request_id,
                              "sha256": content_hash, "agent_description": description},
                )
            else:
                cur.execute("""INSERT INTO cadu_ci_projeto_arquivos
                (projeto_id, id_cliente, criado_por, nome_arquivo, mime, tamanho, storage_path,
                 extracted_text, doc_form, indexing_status, word_count, tokens, purpose, category,
                 classification_status, classification_confidence, classification_reason,
                 classification_metadata, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()) RETURNING id""",
                (project_id, context.client_id, context.user_id, source["name"], source["mime"],
                 len(source["data"]), storage_path, extracted_text,
                 "text_model",
                 "completed" if use_as_knowledge else "paused",
                 len(re.findall(r"\b\w+\b", extracted_text or "", flags=re.UNICODE)), charged_tokens,
                 purpose, classification["category"], classification["status"], classification["confidence"],
                 classification["reason"], Json({"classifier": "deterministic-v1", "content_inspected": bool(source.get("text")),
                                                  "processing": source.get("processing") or "metadata_only",
                                                  "can_index": bool(source.get("can_index")),
                                                  "sha256": content_hash, "upload_request_id": request_id,
                                                  "agent_description": description})))
                source_id = int(cur.fetchone()["id"])
                cur.execute("""UPDATE cadu_ci_projetos SET total_arquivos = COALESCE(total_arquivos, 0) + 1,
                                  updated_at = NOW() WHERE id = %s AND id_cliente = %s""",
                            (project_id, context.client_id))
        connection.commit()
    except Exception:
        connection.rollback()
        if target is not None:
            target.unlink(missing_ok=True)
        raise
    registry_sync = _schedule_resource_reconciliation(context, source_id)
    return {"source_id": source_id, "project_ref": context.project_ref, "name": source["name"],
            "mime_type": source["mime"], "size": len(source["data"]),
            "use_as_knowledge": use_as_knowledge,
            "purpose": purpose, "category": classification["category"],
            "classification": classification,
            "processing": source.get("processing") or "metadata_only",
            "can_index": bool(source.get("can_index")),
            "status": "indexed" if use_as_knowledge else "attached", "charged_credits": charged_tokens,
            "registry_sync": registry_sync}


def create_note(context: RequestContext, *, title: str, content: str, category: Optional[str] = None) -> dict:
    """Persist a chat-authored note through the same index and registry pipeline as uploads."""
    project_id = _project_id(context)
    title = " ".join(str(title or "").split())[:180]
    content = str(content or "").strip()[:50000]
    if len(title) < 2:
        raise BadRequest("Dê um título para identificar esta nota.")
    if len(content) < 20:
        raise BadRequest("A nota precisa ter ao menos 20 caracteres de contexto.")
    category = str(category or "").strip().lower()
    if category and category not in CATEGORIES:
        raise BadRequest("Categoria de nota inválida.")
    content_hash = sha256(content.encode("utf-8")).hexdigest()
    classification = _classify({"name": title, "suffix": ".md"}, category or None, content)
    category = classification["category"]
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            # Keep a same-content retry or a second request from becoming a new
            # knowledge source. The lock spans embedding generation below so two
            # simultaneous turns cannot both pass the lookup.
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                           (f"cadu-project-note:{context.client_id}:{project_id}:{content_hash}",))
            cursor.execute("""SELECT id,nome_arquivo AS name,tokens,category
                              FROM cadu_ci_projeto_arquivos
                             WHERE id_cliente=%s AND projeto_id=%s
                               AND purpose='knowledge_source'
                               AND classification_metadata->>'sha256'=%s
                               AND classification_metadata->>'classifier'='user-note-v1'
                             ORDER BY id DESC LIMIT 1""",
                           (context.client_id, project_id, content_hash))
            existing = cursor.fetchone()
            if existing:
                connection.commit()
                registry_sync = _schedule_resource_reconciliation(context, int(existing["id"]))
                return {"source_id": int(existing["id"]), "project_ref": context.project_ref,
                        "name": existing["name"], "purpose": "knowledge_source",
                        "category": existing.get("category") or category, "status": "indexed",
                        "chunks": None, "charged_credits": 0, "idempotent_replay": True,
                        "registry_sync": registry_sync}

            chunks, embedding_tokens, embedding_model = project_knowledge.index(content)
            if not chunks:
                raise BadRequest("A nota não contém texto que possa ser indexado.")
            charged_tokens = charge_project_rag(
                cursor, client_id=context.client_id, user_id=context.user_id, project_id=project_id,
                tokens=embedding_tokens, stage="indexacao",
                idempotency_key=f"mcp-project-note:{context.client_id}:{project_id}:{content_hash}",
            )
            source_id = project_index_service.persist_indexed_source(
                cursor, project_id=project_id, client_id=context.client_id, user_id=context.user_id,
                name=title, mime="text/markdown", size=len(content.encode("utf-8")),
                storage_path=f"workspace://project-notes/{uuid4()}", source="mcp_note", content=content,
                chunks=chunks, embedding_model=embedding_model, charged_tokens=charged_tokens,
                classification=classification,
                metadata={"classifier": "user-note-v1", "sha256": content_hash, "created_via": "conversations"},
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    registry_sync = _schedule_resource_reconciliation(context, source_id)
    return {"source_id": source_id, "project_ref": context.project_ref, "name": title,
            "purpose": "knowledge_source", "category": category, "status": "indexed",
            "chunks": len(chunks), "charged_credits": charged_tokens, "registry_sync": registry_sync}


def list_sources(context: RequestContext, *, limit=50) -> list[dict]:
    project_id = _project_id(context)
    limit = min(100, max(1, int(limit or 50)))
    with get_db().cursor() as cur:
        cur.execute("""SELECT id, nome_arquivo AS name, mime AS mime_type, tamanho AS size,
                              indexing_status, word_count, tokens, purpose, category,
                              classification_status, classification_confidence, classification_reason,
                              created_at, updated_at
                         FROM cadu_ci_projeto_arquivos
                        WHERE projeto_id = %s AND id_cliente = %s AND indexing_status <> 'superseded'
                     ORDER BY created_at DESC, id DESC LIMIT %s""", (project_id, context.client_id, limit))
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["use_as_knowledge"] = row.get("purpose") == "knowledge_source"
        if row.get("classification_confidence") is not None:
            row["classification_confidence"] = float(row["classification_confidence"])
    return rows
