"""Shared persistence helpers for project knowledge sources."""
from __future__ import annotations

from hashlib import sha256
import json
import re
from pathlib import Path
from typing import Iterable

from flask import current_app

from ..cadu_skills.repository import charge_project_rag
from ..db import get_db
from . import project_knowledge
from . import project_sources


def indexed_content(content: str):
    """Prepare chunks once, using the canonical knowledge pipeline."""
    return project_knowledge.index(str(content or ""))


def _word_count(content: str) -> int:
    return len(re.findall(r"\b\w+\b", str(content or ""), flags=re.UNICODE))


def persist_indexed_source(
    cursor, *,
    project_id: str,
    client_id: int,
    user_id: int | None,
    name: str,
    mime: str,
    size: int,
    storage_path: str,
    source: str,
    content: str,
    chunks: Iterable,
    embedding_model: str,
    charged_tokens: int,
    classification: dict | None = None,
    metadata: dict | None = None,
    source_status: str = "completed",
) -> int:
    """Persist a knowledge source and its chunks in one transaction."""
    classification = classification or {
        "category": "other",
        "status": "needs_review",
        "confidence": 0.25,
        "reason": "Aguardando classificação contextual.",
    }
    source_metadata = dict(metadata or {})
    source_sha256 = source_metadata.pop("sha256", None)
    file_metadata = {
        "classifier": "workspace-v1",
        "content_inspected": True,
        **source_metadata,
        "sha256": sha256(str(content).encode("utf-8")).hexdigest(),
    }
    if source_sha256:
        file_metadata["source_sha256"] = str(source_sha256)
    cursor.execute(
        """INSERT INTO cadu_ci_projeto_arquivos
               (projeto_id, id_cliente, criado_por, nome_arquivo, mime, tamanho,
                storage_path, extracted_text, doc_form, indexing_status, word_count, tokens,
                purpose, category, classification_status, classification_confidence,
                classification_reason, classification_metadata, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'text_model', %s, %s, %s,
                'knowledge_source', %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
         RETURNING id""",
        (
            project_id, client_id, user_id, name, mime, size, storage_path,
            content, source_status, _word_count(content), charged_tokens,
            classification.get("category") or "other",
            classification.get("status") or "needs_review",
            float(classification.get("confidence") or 0),
            classification.get("reason") or "",
            json.dumps(file_metadata, ensure_ascii=False),
        ),
    )
    file_id = int(cursor.fetchone()["id"])
    resource_id = project_resource_id(client_id, f"ci:{project_id}", file_id)
    for chunk in chunks:
        chunk_metadata = {
            "source": source,
            "arquivo_id": file_id,
            "resource_id": resource_id,
            "section": chunk.section,
        }
        cursor.execute(
            """INSERT INTO cadu_ci_chunks
                   (projeto_id, id_cliente, arquivo_id, ordem, titulo, conteudo,
                    search_vector, metadata, embedding, embedding_model, content_hash, tokens, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, to_tsvector('portuguese', %s),
                        %s::jsonb, %s::vector, %s, %s, %s, NOW())""",
            (
                project_id, client_id, file_id, chunk.order, name, chunk.content,
                chunk.content, json.dumps(chunk_metadata, ensure_ascii=False),
                project_knowledge.vector_literal(chunk.embedding), embedding_model,
                chunk.content_hash, chunk.tokens,
            ),
        )
    cursor.execute(
        """UPDATE cadu_ci_projetos
              SET total_arquivos = COALESCE(total_arquivos, 0) + 1, updated_at = NOW()
            WHERE id = %s AND id_cliente = %s""",
        (project_id, client_id),
    )
    return file_id


def persist_pending_source(
    cursor, *,
    project_id: str,
    client_id: int,
    user_id: int | None,
    name: str,
    mime: str,
    size: int,
    storage_path: str,
    content: str,
    classification: dict | None = None,
    metadata: dict | None = None,
) -> int:
    """Register a source before embedding so a worker can finish it later."""
    classification = classification or {
        "category": "other",
        "status": "needs_review",
        "confidence": 0.25,
        "reason": "Aguardando classificação contextual.",
    }
    source_metadata = dict(metadata or {})
    source_sha256 = source_metadata.pop("sha256", None)
    file_metadata = {
        "classifier": "workspace-v1",
        "content_inspected": True,
        **source_metadata,
        "sha256": sha256(str(content).encode("utf-8")).hexdigest(),
    }
    if source_sha256:
        file_metadata["source_sha256"] = str(source_sha256)
    cursor.execute(
        """INSERT INTO cadu_ci_projeto_arquivos
               (projeto_id, id_cliente, criado_por, nome_arquivo, mime, tamanho,
                storage_path, extracted_text, doc_form, indexing_status, word_count, tokens,
                purpose, category, classification_status, classification_confidence,
                classification_reason, classification_metadata, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'text_model', 'queued', 0, 0,
                'knowledge_source', %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
         RETURNING id""",
        (project_id, client_id, user_id, name, mime, size, storage_path, content,
         classification.get("category") or "other",
         classification.get("status") or "needs_review",
         float(classification.get("confidence") or 0), classification.get("reason") or "",
         json.dumps(file_metadata, ensure_ascii=False)),
    )
    file_id = int(cursor.fetchone()["id"])
    cursor.execute(
        """UPDATE cadu_ci_projetos
              SET total_arquivos=COALESCE(total_arquivos, 0) + 1, updated_at=NOW()
            WHERE id=%s AND id_cliente=%s""",
        (project_id, client_id),
    )
    return file_id


def persist_attachment_source(
    cursor, *, project_id: str, client_id: int, user_id: int | None,
    name: str, mime: str, size: int, storage_path: str,
    extracted_text: str = '', classification: dict | None = None,
    metadata: dict | None = None,
) -> int:
    """Preserve a file before the user decides whether it enters the index."""
    classification = classification or {
        'category': 'other', 'status': 'needs_review', 'confidence': 0.25,
        'reason': 'Aguardando validação do usuário.',
    }
    file_metadata = dict(metadata or {})
    file_metadata.setdefault('classifier', 'workspace-triage-v1')
    file_metadata['content_inspected'] = bool(extracted_text)
    file_metadata['sha256'] = file_metadata.get('sha256') or sha256(
        str(extracted_text).encode('utf-8')
    ).hexdigest()
    cursor.execute(
        """INSERT INTO cadu_ci_projeto_arquivos
               (projeto_id, id_cliente, criado_por, nome_arquivo, mime, tamanho,
                storage_path, extracted_text, doc_form, indexing_status, word_count, tokens,
                purpose, category, classification_status, classification_confidence,
                classification_reason, classification_metadata, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'attachment', 'paused', %s, 0,
                'project_attachment', %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
         RETURNING id""",
        (project_id, client_id, user_id, name, mime, size, storage_path,
         extracted_text or None, _word_count(extracted_text),
         classification.get('category') or 'other',
         classification.get('status') or 'needs_review',
         float(classification.get('confidence') or 0),
         classification.get('reason') or 'Aguardando validação do usuário.',
         json.dumps(file_metadata, ensure_ascii=False)),
    )
    file_id = int(cursor.fetchone()['id'])
    cursor.execute(
        """UPDATE cadu_ci_projetos
              SET total_arquivos = COALESCE(total_arquivos, 0) + 1, updated_at = NOW()
            WHERE id = %s AND id_cliente = %s""",
        (project_id, client_id),
    )
    return file_id


def project_resource_id(client_id: int, project_ref: str, source_id: str) -> str:
    """Return the registry ID used for a source before reconciliation."""
    from .project_resource_service import resource_id_for_source
    return resource_id_for_source(client_id, project_ref, "workspace", f"file:{source_id}")


def _source_content(source: dict) -> str:
    storage_path = str(source.get("storage_path") or "")
    if storage_path.startswith(("workspace://project-notes/", "workspace-url:")):
        content = str(source.get("extracted_text") or "")
        if content:
            return content
        raise ValueError("A fonte não possui texto preservado para reindexação.")
    if not storage_path.startswith("workspace_project_sources/"):
        raise ValueError("A fonte não pertence ao armazenamento atual do Workspace.")
    root = Path(str(current_app.config.get("WORKSPACE_SOURCE_STORAGE_DIR") or current_app.instance_path))
    path = project_sources.resolve_private_path(str(root), storage_path)
    if not path.is_file():
        raise FileNotFoundError("O arquivo original da fonte não está disponível.")
    try:
        return project_sources.reextract(
            source.get("nome_arquivo") or path.name,
            path.read_bytes(),
            source.get("mime") or "",
        )["text"]
    except Exception:
        # OCR/adapter output captured during triage is still a valid source of
        # truth for a confirmed creative asset, even if the worker lacks the
        # same optional OCR binary at reindex time.
        preserved = str(source.get("extracted_text") or "").strip()
        if len(preserved) >= 20:
            return preserved
        raise


def reindex_source(client_id: int, project_id: str, source_id: int, user_id: int) -> dict:
    """Rebuild one source atomically; unchanged content is rejected before charging."""
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, nome_arquivo, mime, tamanho, storage_path, extracted_text,
                          classification_metadata->>'sha256' AS content_hash, indexing_status
                     FROM cadu_ci_projeto_arquivos
                    WHERE id=%s AND projeto_id=%s AND id_cliente=%s""",
                (source_id, project_id, client_id),
            )
            source = cursor.fetchone()
            if not source:
                raise ValueError("Fonte indisponível para reindexação.")
            content = _source_content(source)
            content_hash = sha256(content.encode("utf-8")).hexdigest()
            cursor.execute("""SELECT COUNT(*) AS chunk_count FROM cadu_ci_chunks
                               WHERE arquivo_id=%s AND projeto_id=%s AND id_cliente=%s""",
                           (source_id, project_id, client_id))
            chunk_count = int((cursor.fetchone() or {}).get("chunk_count") or 0)
            if source.get("content_hash") == content_hash and source.get("indexing_status") == "completed" and chunk_count:
                connection.commit()
                return {"source_id": int(source_id), "status": "unchanged", "charged_tokens": 0}
            chunks, embedding_tokens, embedding_model = indexed_content(content)
            charged_tokens = charge_project_rag(
                cursor, client_id=client_id, user_id=user_id, project_id=project_id,
                tokens=embedding_tokens, stage="reindexacao",
                idempotency_key=f"workspace-rag-reindex:{source_id}:{content_hash}",
            )
            cursor.execute(
                "DELETE FROM cadu_ci_chunks WHERE arquivo_id=%s AND projeto_id=%s AND id_cliente=%s",
                (source_id, project_id, client_id),
            )
            resource_id = project_resource_id(client_id, f"ci:{project_id}", source_id)
            for chunk in chunks:
                cursor.execute(
                    """INSERT INTO cadu_ci_chunks
                           (projeto_id, id_cliente, arquivo_id, ordem, titulo, conteudo,
                            search_vector, metadata, embedding, embedding_model, content_hash, tokens, created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,to_tsvector('portuguese', %s),%s::jsonb,%s::vector,%s,%s,%s,NOW())""",
                    (project_id, client_id, source_id, chunk.order, source["nome_arquivo"], chunk.content,
                     chunk.content, json.dumps({"source": "workspace_reindexed", "arquivo_id": source_id,
                                                "resource_id": resource_id, "section": chunk.section}),
                     project_knowledge.vector_literal(chunk.embedding), embedding_model,
                     chunk.content_hash, chunk.tokens),
                )
            cursor.execute(
                """UPDATE cadu_ci_projeto_arquivos
                      SET extracted_text=%s, indexing_status='completed', erro_msg=NULL,
                          word_count=%s, tokens=%s, updated_at=NOW(),
                          classification_metadata=jsonb_set(COALESCE(classification_metadata,'{}'::jsonb),
                            '{sha256}', to_jsonb(%s::text), true)
                    WHERE id=%s AND projeto_id=%s AND id_cliente=%s""",
                (content, _word_count(content), charged_tokens, content_hash, source_id, project_id, client_id),
            )
        connection.commit()
        return {"source_id": int(source_id), "status": "completed", "charged_tokens": charged_tokens,
                "content_hash": content_hash, "chunks": len(chunks)}
    except Exception:
        connection.rollback()
        raise
