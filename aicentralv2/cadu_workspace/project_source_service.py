"""Project attachment ingestion shared by Workspace UI and MCP adapters."""

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4
from hashlib import sha256
import json
import re
from typing import Optional

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from psycopg.types.json import Json
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest, Conflict, NotFound
from werkzeug.utils import secure_filename

from ..cadu_skills.repository import charge_project_rag
from ..db import get_db
from . import project_index_service, project_knowledge, project_sources
from .agent_v2.contracts import RequestContext


UPLOAD_MAX_AGE = 600
ATTACHMENT_EXTENSIONS = project_sources.ALLOWED_EXTENSIONS | {".png", ".jpg", ".jpeg", ".webp", ".gif"}
CATEGORIES = {"brief", "research", "media_plan", "report", "brand_asset", "reference", "contract", "spreadsheet", "other"}


def inspect_file_support(filename: str, mime_type: str = "") -> dict:
    """Describe processing support without reading or accepting file content."""
    safe_name = secure_filename(str(filename or ""))[:220]
    suffix = Path(safe_name).suffix.lower()
    mime_type = str(mime_type or "application/octet-stream")[:160]
    if suffix in project_sources.ALLOWED_EXTENSIONS:
        return {"filename": safe_name, "extension": suffix, "mime_type": mime_type,
                "status": "supported", "can_attach": True, "can_index": True,
                "processing": "text_extraction", "requires_adapter": False}
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


def prepare_upload(context: RequestContext, *, request_id: str, use_as_knowledge: bool,
                   category: Optional[str] = None) -> dict:
    project_id = _project_id(context)
    try:
        request_id = str(UUID(str(request_id)))
    except (TypeError, ValueError) as exc:
        raise BadRequest("Identificador do upload inválido.") from exc
    category = str(category or "").strip().lower() or None
    if category and category not in CATEGORIES:
        raise BadRequest("Categoria de arquivo inválida.")
    token = _serializer().dumps({
        "organization_id": context.organization_id, "client_id": context.client_id,
        "user_id": context.user_id, "project_id": project_id,
        "request_id": request_id,
        "use_as_knowledge": bool(use_as_knowledge),
        "category": category,
    })
    return {
        "upload_token": token,
        "upload_url": "/workspace/mcp/uploads",
        "method": "POST",
        "field": "file",
        "max_bytes": project_sources.MAX_BYTES,
        "use_as_knowledge": bool(use_as_knowledge),
        "purpose": "knowledge_source" if use_as_knowledge else "project_attachment",
        "category": category,
        "expires_in": UPLOAD_MAX_AGE,
        "accepted": sorted(ATTACHMENT_EXTENSIONS if not use_as_knowledge else project_sources.ALLOWED_EXTENSIONS),
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
    name = secure_filename(file_storage.filename or "")[:220]
    suffix = Path(name).suffix.lower()
    if not name or suffix not in ATTACHMENT_EXTENSIONS:
        raise BadRequest("Use imagem, PDF, DOCX, TXT, CSV, Markdown, JSON ou HTML.")
    data = file_storage.stream.read(project_sources.MAX_BYTES + 1)
    if len(data) > project_sources.MAX_BYTES:
        raise BadRequest("Cada anexo pode ter no máximo 15 MB.")
    if not data:
        raise BadRequest("O arquivo está vazio.")
    mime = str(file_storage.mimetype or "application/octet-stream")[:160]
    if suffix == ".pdf" and not data.startswith(b"%PDF-"):
        raise BadRequest("O conteúdo não corresponde a um PDF válido.")
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        try:
            from PIL import Image
            image = Image.open(BytesIO(data))
            image.verify()
            mime = Image.MIME.get(image.format, mime)
        except Exception as exc:
            raise BadRequest("A imagem não pôde ser validada.") from exc
    return {"name": name, "suffix": suffix, "mime": mime, "data": data}


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
    use_as_knowledge = bool(claims["use_as_knowledge"])
    source = project_sources.validate_upload(file_storage) if use_as_knowledge else _attachment(file_storage)
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
                              "sha256": content_hash},
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
                 classification["reason"], Json({"classifier": "deterministic-v1", "content_inspected": use_as_knowledge,
                                                  "sha256": content_hash, "upload_request_id": request_id})))
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
    category = str(category or "other").strip().lower()
    if category not in CATEGORIES:
        raise BadRequest("Categoria de nota inválida.")
    content_hash = sha256(content.encode("utf-8")).hexdigest()
    classification = {"category": category, "status": "manual", "confidence": 1.0,
                      "reason": "Nota estruturada pelo usuário no Conversas."}
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
                        WHERE projeto_id = %s AND id_cliente = %s
                     ORDER BY created_at DESC, id DESC LIMIT %s""", (project_id, context.client_id, limit))
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["use_as_knowledge"] = row.get("purpose") == "knowledge_source"
        if row.get("classification_confidence") is not None:
            row["classification_confidence"] = float(row["classification_confidence"])
    return rows
