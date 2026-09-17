"""Hybrid, attributable retrieval for private Workspace project sources.

The old ``cadu_ci_chunks`` rows only looked like vectors: their embedding
columns were empty and every lookup was lexical.  This module is the single
place where a source becomes retrieval material, so ingestion, reindexing and
chat cannot silently diverge again.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

import requests

from ..services.openrouter_service import resolve_openai_api_key


EMBEDDING_URL = "https://api.openai.com/v1/embeddings"
EMBEDDING_MODEL = os.getenv("WORKSPACE_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("WORKSPACE_EMBEDDING_DIMENSIONS", "1536"))
CHUNK_TARGET = int(os.getenv("WORKSPACE_RAG_CHUNK_TARGET", "1800"))
CHUNK_OVERLAP = int(os.getenv("WORKSPACE_RAG_CHUNK_OVERLAP", "220"))


class KnowledgeIndexError(RuntimeError):
    """The source remains intact; only its retrieval material was not created."""


@dataclass(frozen=True)
class Chunk:
    order: int
    content: str
    content_hash: str
    section: str
    tokens: int
    embedding: list[float]


def _estimate_tokens(value: str) -> int:
    # Until a provider returns exact usage this is only a pre-flight estimate;
    # callers persist the returned embedding usage when it is available.
    return max(1, round(len(value) / 4))


def split(content: str, target: int = CHUNK_TARGET, overlap: int = CHUNK_OVERLAP) -> list[tuple[str, str]]:
    """Split on headings and paragraphs, retaining a short semantic bridge."""
    text = str(content or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    size = 0
    section = ""
    bridge = ""
    for paragraph in paragraphs:
        if re.match(r"^(?:#{1,6}\s+|[A-ZÀ-Ý][^\n]{0,100}:$)", paragraph):
            section = re.sub(r"^#+\s*", "", paragraph).rstrip(":").strip()[:180]
        parts = [paragraph[i:i + target] for i in range(0, len(paragraph), target)] or [paragraph]
        for part in parts:
            proposed = size + len(part) + (2 if current else 0)
            if current and proposed > target:
                value = "\n\n".join(current).strip()
                chunks.append((value, section))
                bridge = value[-overlap:].strip() if overlap else ""
                current = [bridge, part] if bridge else [part]
                size = sum(len(item) for item in current) + 2
            else:
                current.append(part)
                size = proposed
    if current:
        chunks.append(("\n\n".join(current).strip(), section))
    return [(value, section) for value, section in chunks if len(value) >= 20]


def _embed(texts: list[str]) -> tuple[list[list[float]], int, str]:
    key = resolve_openai_api_key()
    if not key:
        raise KnowledgeIndexError("OpenAI não está configurada para indexar fontes do projeto.")
    try:
        response = requests.post(
            EMBEDDING_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": EMBEDDING_MODEL, "input": texts, "dimensions": EMBEDDING_DIMENSIONS},
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        values = [item.get("embedding") for item in sorted(payload.get("data") or [], key=lambda item: item.get("index", 0))]
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise KnowledgeIndexError("Não foi possível gerar os embeddings desta fonte. Tente novamente.") from exc
    if len(values) != len(texts) or any(not isinstance(item, list) or len(item) != EMBEDDING_DIMENSIONS for item in values):
        raise KnowledgeIndexError("O provedor retornou embeddings em formato incompatível.")
    usage = payload.get("usage") or {}
    tokens = int(usage.get("total_tokens") or sum(_estimate_tokens(item) for item in texts))
    return values, max(1, tokens), str(payload.get("model") or EMBEDDING_MODEL)


def index(content: str) -> tuple[list[Chunk], int, str]:
    pieces = split(content)
    if not pieces:
        raise KnowledgeIndexError("A fonte não contém texto suficiente para indexação semântica.")
    vectors, tokens, model = _embed([value for value, _section in pieces])
    records = [Chunk(
        order=order,
        content=value,
        content_hash=hashlib.sha256(value.encode("utf-8")).hexdigest(),
        section=section,
        tokens=_estimate_tokens(value),
        embedding=vector,
    ) for order, ((value, section), vector) in enumerate(zip(pieces, vectors))]
    return records, tokens, model


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8g}" for value in values) + "]"


def query_embedding(query: str) -> list[float]:
    values, _tokens, _model = _embed([" ".join(str(query or "").split())[:1200]])
    return values[0]
