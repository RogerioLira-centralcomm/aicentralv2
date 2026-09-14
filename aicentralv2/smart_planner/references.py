"""Captura e revisão de referências do passo 1 — URL, arquivo e busca."""

from __future__ import annotations

import base64
import logging
import os
from urllib.parse import urlparse

import requests

from .ai import chat_json, chat_text, chat_vision
from .catalog import FIELD_SCHEMA
from .helpers import as_dict, strip_markdown, text
from .materials import (
    REFERENCE_PAPEL,
    extract_pdf,
    normalize_reference,
    scrape_url,
)

logger = logging.getLogger(__name__)

REVIEW_SYSTEM = """Você revisa material de apoio para um briefing de mídia no CentralX.
Descarte menu, cookie, rodapé, CTA de site e qualquer markdown.
Organize só o que importa em prosa limpa, em português.
Não invente verba, KPI, cliente, prazo ou marca que o material não afirma.
Responda apenas com JSON válido."""


def reference_block(kind: str, label: str, body: str) -> str:
    heading = {
        "url": "página",
        "file": "arquivo",
        "image": "imagem",
        "search": "dados online",
    }.get(kind, "referência")
    return (body or "").strip() or f"Apoio da {heading} {label}".strip()


def capture_url(url: str) -> dict:
    raw = scrape_url(url)
    label = urlparse(url).netloc or url
    return _captured("url", label, raw, url=url)


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
    return _captured(kind, original, raw, name=original)


def capture_search(query: str, briefing: str = "") -> dict:
    query = (query or "").strip()
    if len(query) < 3:
        raise ValueError("Escreva o que devemos pesquisar.")
    raw = search_web(query, briefing)
    return _captured("search", query, raw)


def search_web(query: str, briefing: str = "") -> str:
    from ..services.integration_credentials import resolve_firecrawl_api_key

    key = resolve_firecrawl_api_key()
    if key:
        hits = _firecrawl_search(query, key)
        pages = _scrape_search_hits(hits)
        if pages:
            return pages
        listing = _format_search_hits(hits)
        if listing:
            return listing
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
    return "Fonte: conhecimento do modelo, não é página capturada.\n\n" + raw


def review_reference(raw: str, *, kind: str, label: str) -> dict:
    raw = (raw or "").strip()
    fallback_papel = REFERENCE_PAPEL.get(kind, "marca")
    if len(raw) < 80:
        return {
            "notas": strip_markdown(raw),
            "fatos": {},
            "papel": fallback_papel,
        }
    schema = ", ".join(FIELD_SCHEMA)
    try:
        parsed = as_dict(chat_json(
            REVIEW_SYSTEM,
            (
                f"Tipo: {kind}\nRótulo: {label}\n"
                f"Campos úteis se o material afirmar: {schema}\n\n"
                "Devolva JSON:\n"
                '{"notas":"parágrafos sem markdown: o que é, oferta, público implícito, '
                'praça, prova, restrições",'
                '"fatos":{"campo":"valor só se o material afirmar"},'
                '"papel":"marca|campanha|mercado|visual"}\n\n'
                "Material:\n" + raw[:20000]
            ),
            role="review",
        ))
    except Exception:
        logger.exception("Falha ao revisar referência %s", label)
        parsed = {}
    notas = strip_markdown(text(parsed.get("notas")) or raw[:2000])
    fatos = parsed.get("fatos") if isinstance(parsed.get("fatos"), dict) else {}
    papel = text(parsed.get("papel")).lower()
    if papel not in {"marca", "campanha", "mercado", "visual"}:
        papel = fallback_papel
    if kind == "search":
        papel = "mercado"
    return {"notas": notas, "fatos": fatos, "papel": papel}


def _captured(kind: str, label: str, raw: str, **extra) -> dict:
    reviewed = review_reference(raw, kind=kind, label=label)
    payload = {
        "kind": kind,
        "label": label,
        "text": raw,
        "digest": reviewed["notas"],
        "notas": reviewed["notas"],
        "fatos": reviewed["fatos"],
        "papel": reviewed["papel"],
        "bloco": reviewed["notas"],
        **extra,
    }
    return normalize_reference(payload) | payload


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


def _firecrawl_search(query: str, key: str) -> list[dict]:
    endpoint = (os.getenv("FIRECRAWL_API_URL") or "https://api.firecrawl.dev/v2/search").strip()
    if endpoint.endswith("/scrape"):
        endpoint = endpoint.rsplit("/scrape", 1)[0] + "/search"
    elif endpoint.endswith("/v1") or endpoint.endswith("/v2"):
        endpoint = endpoint + "/search"
    elif not endpoint.endswith("/search"):
        endpoint = endpoint.rstrip("/") + "/v2/search"
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
        return []
    data = payload.get("data") or payload
    rows = data.get("web") or data.get("results") or []
    hits = []
    for item in rows[:5]:
        if not isinstance(item, dict):
            continue
        title = text(item.get("title"))
        snippet = text(item.get("description") or item.get("snippet") or item.get("markdown"))
        url = text(item.get("url"))
        if title or snippet or url:
            hits.append({"title": title, "snippet": snippet, "url": url})
    return hits


def _format_search_hits(hits: list[dict]) -> str:
    parts = []
    for item in hits:
        line = " — ".join(part for part in (item.get("title"), item.get("snippet"), item.get("url")) if part)
        if line:
            parts.append(line)
    return "\n\n".join(parts)


def _scrape_search_hits(hits: list[dict], limit: int = 2) -> str:
    parts = []
    for item in hits[:limit]:
        url = text(item.get("url"))
        title = text(item.get("title"))
        snippet = text(item.get("snippet"))
        page = ""
        if url:
            try:
                page = scrape_url(url)
            except Exception:
                logger.exception("Falha ao abrir resultado da busca %s", url)
                page = ""
        body = page or snippet
        if not body:
            continue
        head = " — ".join(part for part in (title, url) if part)
        parts.append(f"{head}\n{body[:12000]}" if head else body[:12000])
    return "\n\n".join(parts)
