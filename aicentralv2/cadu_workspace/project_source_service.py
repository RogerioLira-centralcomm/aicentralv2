"""Project attachment ingestion shared by Workspace UI and MCP adapters."""

from io import BytesIO
from pathlib import Path
from uuid import uuid4
import json
import re

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from psycopg.types.json import Json
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest, Conflict, NotFound
from werkzeug.utils import secure_filename

from ..cadu_skills.repository import charge_project_rag
from ..db import get_db
from . import project_knowledge, project_sources
from .agent_v2.contracts import RequestContext


UPLOAD_MAX_AGE = 600
ATTACHMENT_EXTENSIONS = project_sources.ALLOWED_EXTENSIONS | {".png", ".jpg", ".jpeg", ".webp", ".gif"}


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


def prepare_upload(context: RequestContext, *, use_as_knowledge: bool) -> dict:
    project_id = _project_id(context)
    token = _serializer().dumps({
        "organization_id": context.organization_id, "client_id": context.client_id,
        "user_id": context.user_id, "project_id": project_id,
        "use_as_knowledge": bool(use_as_knowledge),
    })
    return {
        "upload_token": token,
        "upload_url": "/workspace/mcp/uploads",
        "method": "POST",
        "field": "file",
        "max_bytes": project_sources.MAX_BYTES,
        "use_as_knowledge": bool(use_as_knowledge),
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


def save_upload(context: RequestContext, token: str, file_storage) -> dict:
    claims = _upload_claims(context, token)
    project_id = _project_id(context)
    if project_id != str(claims["project_id"]):
        raise BadRequest("O projeto selecionado mudou. Solicite uma nova autorização de upload.")
    use_as_knowledge = bool(claims["use_as_knowledge"])
    source = project_sources.validate_upload(file_storage) if use_as_knowledge else _attachment(file_storage)
    target = project_sources.private_path(_storage_root(), context.client_id, project_id, source["suffix"], uuid4().hex)
    target.write_bytes(source["data"])
    storage_path = target.relative_to(Path(_storage_root())).as_posix()
    connection = get_db()
    try:
        chunks, charged_tokens, extracted_text = [], 0, None
        if use_as_knowledge:
            extracted_text = source["text"]
            chunks, embedding_tokens, embedding_model = project_knowledge.index(extracted_text)
        with connection.cursor() as cur:
            if use_as_knowledge:
                charged_tokens = charge_project_rag(
                    cur, client_id=context.client_id, user_id=context.user_id, project_id=project_id,
                    tokens=embedding_tokens, stage="indexacao",
                    idempotency_key="mcp-project-rag-index:" + uuid4().hex,
                )
            cur.execute("""INSERT INTO cadu_ci_projeto_arquivos
                (projeto_id, id_cliente, criado_por, nome_arquivo, mime, tamanho, storage_path,
                 extracted_text, doc_form, indexing_status, word_count, tokens, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()) RETURNING id""",
                (project_id, context.client_id, context.user_id, source["name"], source["mime"],
                 len(source["data"]), storage_path, extracted_text,
                 "text_model",
                 "completed" if use_as_knowledge else "paused",
                 len(re.findall(r"\b\w+\b", extracted_text or "", flags=re.UNICODE)), charged_tokens))
            source_id = int(cur.fetchone()["id"])
            for chunk in chunks:
                cur.execute("""INSERT INTO cadu_ci_chunks
                    (projeto_id, id_cliente, arquivo_id, ordem, titulo, conteudo, search_vector,
                     metadata, embedding, embedding_model, content_hash, tokens, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, to_tsvector('portuguese', %s), %s, %s::vector,
                            %s, %s, %s, NOW())""",
                    (project_id, context.client_id, source_id, chunk.order, source["name"], chunk.content,
                     chunk.content, Json({"source": "mcp_upload", "arquivo_id": source_id, "section": chunk.section}),
                     project_knowledge.vector_literal(chunk.embedding), embedding_model,
                     chunk.content_hash, chunk.tokens))
            cur.execute("""UPDATE cadu_ci_projetos SET total_arquivos = COALESCE(total_arquivos, 0) + 1,
                              updated_at = NOW() WHERE id = %s AND id_cliente = %s""",
                        (project_id, context.client_id))
        connection.commit()
    except Exception:
        connection.rollback()
        target.unlink(missing_ok=True)
        raise
    return {"source_id": source_id, "project_ref": context.project_ref, "name": source["name"],
            "mime_type": source["mime"], "size": len(source["data"]),
            "use_as_knowledge": use_as_knowledge,
            "status": "indexed" if use_as_knowledge else "attached", "charged_credits": charged_tokens}


def list_sources(context: RequestContext, *, limit=50) -> list[dict]:
    project_id = _project_id(context)
    limit = min(100, max(1, int(limit or 50)))
    with get_db().cursor() as cur:
        cur.execute("""SELECT id, nome_arquivo AS name, mime AS mime_type, tamanho AS size,
                              indexing_status, word_count, tokens, created_at, updated_at
                         FROM cadu_ci_projeto_arquivos
                        WHERE projeto_id = %s AND id_cliente = %s
                     ORDER BY created_at DESC, id DESC LIMIT %s""", (project_id, context.client_id, limit))
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["use_as_knowledge"] = row.get("indexing_status") == "completed"
    return rows
