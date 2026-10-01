"""Hybrid retrieval over chat conversations, shared by everyone who can view a project."""
from __future__ import annotations

import hashlib
import json
import re

import click
from flask import current_app
from flask.cli import with_appcontext

from ..cadu_family import repository
from ..db import close_db
from . import project_knowledge

INDEX_VERSION = "conversation-chunks-v1"
SEGMENT_MESSAGES = 6
USER_CHARS = 1500
ASSISTANT_CHARS = 700
EMBED_BATCH = 64


def available() -> bool:
    rows = repository.rows("SELECT to_regclass('public.cadu_conversation_chunks') IS NOT NULL AS available", ())
    return bool(rows and rows[0].get("available"))


def _clean(value: str, limit: int) -> str:
    text = re.sub(r"<think\b[^>]*>.*?(?:</think\s*>|$)", "", str(value or ""), flags=re.I | re.S)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def segments(messages: list[dict]) -> list[dict]:
    """Group a transcript into fixed windows so only the newest window changes per turn."""
    grouped: dict[int, list[dict]] = {}
    for message in messages:
        sequence = int(message.get("conversation_sequence") or 0)
        if sequence <= 0 or message.get("role") not in {"user", "assistant"}:
            continue
        grouped.setdefault((sequence - 1) // SEGMENT_MESSAGES, []).append(message)
    result = []
    for index in sorted(grouped):
        lines, ids = [], []
        for message in grouped[index]:
            is_user = message["role"] == "user"
            text = _clean(message.get("content"), USER_CHARS if is_user else ASSISTANT_CHARS)
            if not text:
                continue
            author = str(message.get("author_name") or "").strip()
            label = (f"Usuário ({author})" if author else "Usuário") if is_user else "Assistente"
            lines.append(f"{label}: {text}")
            ids.append(str(message["id"]))
        if not lines:
            continue
        content = "\n".join(lines)
        result.append({
            "segment_index": index,
            "first_sequence": int(grouped[index][0]["conversation_sequence"]),
            "last_sequence": int(grouped[index][-1]["conversation_sequence"]),
            "message_ids": ids,
            "content": content,
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "last_message_at": grouped[index][-1].get("created_at"),
        })
    return result


def index_conversation(conversation_id: str) -> int:
    """Create or refresh the excerpts of one conversation; returns how many changed."""
    conversation = repository.rows("""SELECT conversation.id_cliente AS client_id, author.nome_completo AS author_name
          FROM cadu_conversations conversation
     LEFT JOIN tbl_contato_cliente author ON author.id_contato_cliente=conversation.id_contato_cliente
         WHERE conversation.id=%s""", (conversation_id,))
    if not conversation:
        return 0
    client_id = int(conversation[0]["client_id"])
    author_name = str(conversation[0].get("author_name") or "").split(" ")[0]
    messages = repository.rows("""SELECT id, role, content, conversation_sequence, created_at
          FROM cadu_conversation_messages
         WHERE conversation_id=%s AND role IN ('user','assistant') AND conversation_sequence IS NOT NULL
         ORDER BY conversation_sequence""", (conversation_id,))
    for message in messages:
        message["author_name"] = author_name
    existing = {int(row["segment_index"]): row["content_hash"].strip() for row in repository.rows(
        """SELECT segment_index, content_hash FROM cadu_conversation_chunks
            WHERE conversation_id=%s AND embedding IS NOT NULL""", (conversation_id,))}
    changed = [item for item in segments(messages) if existing.get(item["segment_index"]) != item["content_hash"]]
    if not changed:
        return 0
    vectors, model = [], project_knowledge.EMBEDDING_MODEL
    for start in range(0, len(changed), EMBED_BATCH):
        batch_vectors, _tokens, model = project_knowledge._embed(
            [item["content"] for item in changed[start:start + EMBED_BATCH]])
        vectors.extend(batch_vectors)
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            for item, vector in zip(changed, vectors):
                cur.execute("""INSERT INTO cadu_conversation_chunks
                    (conversation_id, client_id, segment_index, first_sequence, last_sequence, message_ids,
                     content, content_hash, search_vector, embedding, embedding_model, last_message_at,
                     index_version, indexed_at)
                    VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,to_tsvector('portuguese',%s),%s::vector,%s,%s,%s,NOW())
                    ON CONFLICT (conversation_id, segment_index) DO UPDATE SET
                        client_id=EXCLUDED.client_id, first_sequence=EXCLUDED.first_sequence,
                        last_sequence=EXCLUDED.last_sequence, message_ids=EXCLUDED.message_ids,
                        content=EXCLUDED.content, content_hash=EXCLUDED.content_hash,
                        search_vector=EXCLUDED.search_vector, embedding=EXCLUDED.embedding,
                        embedding_model=EXCLUDED.embedding_model, last_message_at=EXCLUDED.last_message_at,
                        index_version=EXCLUDED.index_version, indexed_at=NOW()""",
                            (conversation_id, client_id, item["segment_index"], item["first_sequence"],
                             item["last_sequence"], json.dumps(item["message_ids"]), item["content"],
                             item["content_hash"], item["content"], project_knowledge.vector_literal(vector),
                             model, item["last_message_at"], INDEX_VERSION))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(changed)


def search_project(*, client_id: int, project_ref: str, query: str, exclude_conversation_id: str | None,
                   limit: int = 6) -> list[dict]:
    """Hybrid search over every conversation bound to the project, by any member."""
    terms = " ".join(str(query or "").split())[:400]
    if not terms:
        return []
    scope = """FROM cadu_conversation_chunks chunk
          JOIN cadu_family_conversation_context binding ON binding.conversation_id=chunk.conversation_id
         WHERE chunk.client_id=%s AND binding.client_id=%s AND binding.project_ref=%s
           AND chunk.conversation_id<>COALESCE(%s,'')"""
    scope_params = (client_id, client_id, project_ref, exclude_conversation_id)
    lexical_query = _or_terms(terms)
    try:
        vector = project_knowledge.vector_literal(project_knowledge.query_embedding(terms))
        semantic = f"""SELECT chunk.id, 1 - (chunk.embedding <=> %s::vector) AS score {scope}
               AND chunk.embedding IS NOT NULL ORDER BY chunk.embedding <=> %s::vector LIMIT 12"""
        semantic_params = (vector, *scope_params, vector)
    except project_knowledge.KnowledgeIndexError:
        semantic = f"SELECT chunk.id, 0::double precision AS score {scope} AND FALSE"
        semantic_params = scope_params
    rows = repository.rows(f"""WITH lexical AS (
            SELECT chunk.id, ts_rank_cd(chunk.search_vector, websearch_to_tsquery('portuguese', %s)) AS score {scope}
               AND chunk.search_vector @@ websearch_to_tsquery('portuguese', %s)
             ORDER BY score DESC LIMIT 12
        ), semantic AS ({semantic}), ranked AS (
            SELECT id, SUM(1.0 / (60 + rank)) AS score FROM (
                SELECT id, row_number() OVER (ORDER BY score DESC) AS rank FROM lexical
                UNION ALL SELECT id, row_number() OVER (ORDER BY score DESC) AS rank FROM semantic
            ) candidates GROUP BY id
        ) SELECT chunk.id AS chunk_id, chunk.conversation_id, chunk.content, chunk.message_ids,
                 chunk.last_message_at, conversation.titulo AS conversation_title, ranked.score
            FROM ranked JOIN cadu_conversation_chunks chunk ON chunk.id=ranked.id
            JOIN cadu_conversations conversation ON conversation.id=chunk.conversation_id
           ORDER BY ranked.score DESC LIMIT %s""",
        (lexical_query, *scope_params, lexical_query, *semantic_params, limit))
    return [{
        "result_type": "conversation_excerpt", "evidence_level": "conversation_excerpt",
        "conversation_chunk_id": str(row["chunk_id"]),
        "conversation_id": str(row["conversation_id"]),
        "message_id": str((row.get("message_ids") or [""])[0]),
        "title": str(row.get("conversation_title") or "Conversa anterior")[:160],
        "description": str(row.get("content") or ""),
        "created_at": str(row.get("last_message_at") or ""),
        "score": float(row.get("score") or 0),
    } for row in rows]


def _or_terms(terms: str) -> str:
    """websearch syntax with OR, so a long question still matches partially."""
    words = [word for word in re.findall(r"[^\W_]{3,}", terms, re.UNICODE)][:12]
    return " OR ".join(words) or terms


def project_has_chunks(client_id: int, project_ref: str) -> bool:
    rows = repository.rows("""SELECT EXISTS (SELECT 1 FROM cadu_conversation_chunks chunk
          JOIN cadu_family_conversation_context binding ON binding.conversation_id=chunk.conversation_id
         WHERE chunk.client_id=%s AND binding.client_id=%s AND binding.project_ref=%s) AS present""",
                           (client_id, client_id, project_ref))
    return bool(rows and rows[0].get("present"))


@click.command("conversation-index-backfill")
@click.option("--client-id", type=int, default=None, help="Limita a um cliente.")
@click.option("--limit", type=int, default=0, help="Número máximo de conversas (0 = todas).")
@with_appcontext
def backfill_command(client_id, limit):
    """Index existing conversations; safe to rerun (only changed excerpts are embedded)."""
    rows = repository.rows("""SELECT conversation.id FROM cadu_conversations conversation
         WHERE (%s::int IS NULL OR conversation.id_cliente=%s)
           AND EXISTS (SELECT 1 FROM cadu_conversation_messages message
                        WHERE message.conversation_id=conversation.id AND message.conversation_sequence IS NOT NULL)
         ORDER BY conversation.id""", (client_id, client_id))
    if limit:
        rows = rows[:limit]
    changed = failed = 0
    for row in rows:
        try:
            changed += index_conversation(str(row["id"]))
        except Exception:
            failed += 1
            current_app.logger.exception("Falha ao indexar conversa %s", row["id"])
            close_db()
    click.echo(f"Conversas: {len(rows)}; trechos atualizados: {changed}; falhas: {failed}.")
