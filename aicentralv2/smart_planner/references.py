"""Captura de referências do passo 1 — URL, arquivo e busca online."""

from __future__ import annotations

import base64
import os
from urllib.parse import urlparse

import requests

from .ai import chat_text, chat_vision
from .helpers import text
from .materials import extract_pdf, scrape_url


def reference_block(kind: str, label: str, body: str) -> str:
    heading = {
        "url": "Referência — página",
        "file": "Referência — arquivo",
        "image": "Referência — imagem",
        "search": "Referência — dados online",
    }.get(kind, "Referência")
    body = (body or "").strip()
    return f"\n\n## {heading}: {label}\n{body}\n"


def capture_url(url: str) -> dict:
    raw = scrape_url(url)
    label = urlparse(url).netloc or url
    digest = _digest(raw, kind="url", label=label)
    return {
        "kind": "url",
        "label": label,
        "url": url,
        "text": raw,
        "digest": digest,
        "bloco": reference_block("url", label, digest),
    }


def capture_file(path: str, original: str) -> dict:
    ext = (original.rsplit(".", 1)[-1] if "." in original else "").lower()
    if ext == "pdf":
        raw = extract_pdf(path)
        kind = "file"
    elif ext in {"png", "jpg", "jpeg", "webp"}:
        raw = _read_image(path, ext)
        kind = "image"
    else:
        raise ValueError("Envie um PDF ou uma imagem (PNG, JPG ou WEBP).")
    digest = _digest(raw, kind=kind, label=original)
    return {
        "kind": kind,
        "label": original,
        "name": original,
        "text": raw,
        "digest": digest,
        "bloco": reference_block(kind, original, digest),
    }


def capture_search(query: str, briefing: str = "") -> dict:
    query = (query or "").strip()
    if len(query) < 3:
        raise ValueError("Escreva o que devemos pesquisar.")
    raw = search_web(query, briefing)
    digest = _digest(raw, kind="search", label=query)
    return {
        "kind": "search",
        "label": query,
        "text": raw,
        "digest": digest,
        "bloco": reference_block("search", query, digest),
    }


def search_web(query: str, briefing: str = "") -> str:
    key = (os.getenv("FIRECRAWL_API_KEY") or "").strip()
    if key:
        found = _firecrawl_search(query, key)
        if found:
            return found
    hint = (briefing or "").strip()[:800]
    prompt = (
        f"Pesquise dados atuais sobre: {query}\n"
        "Devolva um resumo factual em português, com fontes nomeadas quando souber.\n"
        "Não invente número de verba, KPI ou audiência."
    )
    if hint:
        prompt += "\n\nContexto do briefing:\n" + hint
    raw = chat_text(
        "Você resume dados públicos de mercado para um planejamento de mídia.",
        prompt,
        role="digest",
        max_tokens=1800,
    )
    if len(raw) < 40:
        raise ValueError("A busca não devolveu conteúdo suficiente.")
    return raw


def _firecrawl_search(query: str, key: str) -> str:
    endpoint = (os.getenv("FIRECRAWL_API_URL") or "https://api.firecrawl.dev/v2/search").strip()
    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"query": query, "limit": 5, "ignoreInvalidURLs": True},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return ""
    data = payload.get("data") or payload
    rows = data.get("web") or data.get("results") or []
    parts = []
    for item in rows[:5]:
        if not isinstance(item, dict):
            continue
        title = text(item.get("title"))
        snippet = text(item.get("description") or item.get("snippet") or item.get("markdown"))
        url = text(item.get("url"))
        if title or snippet:
            parts.append(" — ".join(part for part in (title, snippet, url) if part))
    return "\n\n".join(parts)


def _read_image(path: str, ext: str) -> str:
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}[ext]
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return chat_vision(
        "Leia esta imagem de briefing ou material de campanha. "
        "Transcreva texto visível e descreva o que importa para um plano de mídia. "
        "Não invente verba, KPI ou marca que não apareça.",
        f"data:{mime};base64,{encoded}",
    )


def _digest(raw: str, *, kind: str, label: str) -> str:
    raw = (raw or "").strip()
    if len(raw) < 80:
        return raw
    digest = chat_text(
        "Você resume referências para um briefing de mídia. "
        "Fidelidade ao material. Sem inventar número.",
        f"Resuma em até 180 palavras, em português, esta referência ({kind}: {label}):\n\n{raw[:12000]}",
        role="digest",
    )
    return digest or raw[:900]