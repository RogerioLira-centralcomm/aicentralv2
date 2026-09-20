"""Tenant-safe web discovery and selective source reading for Cadu agents.

Search is deliberately separate from project retrieval.  The agent receives a
small, cleaned evidence packet with source URLs and selected page content; it
does not receive provider diagnostics, credentials or raw HTML.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

import requests

from ..cadu_credit_connector import CaduCreditConnector, CreditActor
from ..cadu_tool_billing import InsufficientToolCredits
from ..services.integration_credentials import resolve_firecrawl_api_key


logger = logging.getLogger(__name__)
MAX_QUERY = 400
MAX_SOURCES = 8
MAX_HYDRATED_SOURCES = 3


class WebSearchUnavailable(RuntimeError):
    """Raised when the optional external search cannot produce evidence."""


def _clean_text(value, limit: int) -> str:
    text = str(value or "")
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_`~]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _host(value: str) -> str:
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        return ""
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return parsed.hostname.lower()[:180]


def _safe_url(value: str) -> str:
    value = str(value or "").strip()
    return value[:2000] if _host(value) else ""


def _endpoint() -> str:
    configured = str(os.getenv("FIRECRAWL_API_URL") or "").strip().rstrip("/")
    if not configured:
        return "https://api.firecrawl.dev/v2/search"
    if configured.endswith("/scrape"):
        return configured.rsplit("/scrape", 1)[0] + "/search"
    if configured.endswith("/v1") or configured.endswith("/v2"):
        return configured + "/search"
    return configured if configured.endswith("/search") else configured + "/v2/search"


def _search(query: str, *, limit: int, include_domains: list[str],
            exclude_domains: list[str], recency: str) -> list[dict]:
    key = resolve_firecrawl_api_key()
    if not key:
        raise WebSearchUnavailable("A pesquisa online não está configurada nesta conta.")
    payload = {
        "query": query,
        "limit": limit,
        "sources": ["web"],
        "country": "BR",
        "safe": True,
        "highlights": True,
        "ignoreInvalidURLs": True,
        "timeout": 45_000,
    }
    if include_domains:
        payload["includeDomains"] = include_domains
    elif exclude_domains:
        payload["excludeDomains"] = exclude_domains
    if recency:
        payload["tbs"] = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}[recency]
    try:
        response = requests.post(
            _endpoint(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=55,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise WebSearchUnavailable("A pesquisa online não respondeu nesta tentativa.") from exc
    data = body.get("data") if isinstance(body, dict) else {}
    data = data if isinstance(data, dict) else {}
    rows = data.get("web") or data.get("results") or []
    sources = []
    for index, item in enumerate(rows[:limit], start=1):
        if not isinstance(item, dict):
            continue
        url = _safe_url(item.get("url") or item.get("sourceURL"))
        title = _clean_text(item.get("title") or item.get("metadata", {}).get("title"), 220)
        description = _clean_text(item.get("description") or item.get("snippet"), 900)
        if not url or not (title or description):
            continue
        sources.append({
            "id": f"web-{index}",
            "title": title or _host(url),
            "url": url,
            "domain": _host(url),
            "excerpt": description,
            "published_at": _clean_text(item.get("date") or item.get("publishedDate"), 60),
            "source_type": _clean_text(item.get("category") or "web", 40),
            "rank": index,
        })
    return sources


def _read_source(url: str) -> str:
    """Read only the main markdown content of one selected result."""
    try:
        from ..crm_v3_web_scout import _firecrawl_scrape
        data = _firecrawl_scrape(url, formats=["markdown"], timeout_s=35, only_main_content=True)
    except Exception:
        logger.info("Fonte web não pôde ser lida: %s", url, exc_info=True)
        return ""
    if not isinstance(data, dict):
        return ""
    content = data.get("markdown") or data.get("content") or ""
    return _clean_text(content, 4200) if len(str(content or "").strip()) >= 80 else ""


def _domains(values) -> list[str]:
    result = []
    for value in values if isinstance(values, list) else []:
        raw = str(value or "").strip().lower()
        if not raw:
            continue
        raw = raw.removeprefix("https://").removeprefix("http://").split("/", 1)[0]
        if re.fullmatch(r"[a-z0-9.-]+", raw) and "." in raw:
            result.append(raw[:180])
        if len(result) >= 10:
            break
    return list(dict.fromkeys(result))


def search(context, arguments: dict) -> dict:
    """Search current public sources and hydrate only the strongest results."""
    query = " ".join(str(arguments.get("query") or "").split())[:MAX_QUERY]
    if len(query) < 3:
        raise ValueError("Informe o que deve ser pesquisado na internet.")
    limit = min(MAX_SOURCES, max(3, int(arguments.get("limit") or 6)))
    include_domains = _domains(arguments.get("include_domains"))
    exclude_domains = _domains(arguments.get("exclude_domains"))
    if include_domains and exclude_domains:
        raise ValueError("Escolha domínios para incluir ou excluir, não os dois.")
    recency = str(arguments.get("recency") or "").strip().lower()
    if recency not in {"", "day", "week", "month", "year"}:
        raise ValueError("Recência inválida.")
    include_content = arguments.get("include_content", True) is not False
    hydrate_limit = min(MAX_HYDRATED_SOURCES, limit) if include_content else 0
    actor = CreditActor.from_values(context.client_id, context.user_id)
    credits = CaduCreditConnector()
    try:
        credits.authorize_firecrawl(actor, "search", results=limit)
        if hydrate_limit:
            credits.authorize_firecrawl(actor, "scrape", pages=hydrate_limit)
    except InsufficientToolCredits as exc:
        raise ValueError("Não há saldo suficiente para pesquisar na internet agora.") from exc
    request_id = str(arguments.get("request_id") or getattr(context, "request_id", "") or uuid4())[:120]
    sources = _search(query, limit=limit, include_domains=include_domains,
                      exclude_domains=exclude_domains, recency=recency)
    hydrated = 0
    for source in sources[:hydrate_limit]:
        content = _read_source(source["url"])
        if content:
            source["content"] = content
            hydrated += 1
    try:
        credits.charge_firecrawl(
            actor=actor, idempotency_key=f"web-search:{request_id}:search",
            operation="search", results=limit, app="Cadu Pesquisa", stage="web_search",
            metadata={"conversation_id": str(context.conversation_id or ""), "query_length": len(query)},
        )
        if hydrated:
            credits.charge_firecrawl(
                actor=actor, idempotency_key=f"web-search:{request_id}:scrape",
                operation="scrape", pages=hydrated, app="Cadu Pesquisa", stage="web_source_reading",
                metadata={"conversation_id": str(context.conversation_id or ""), "sources_read": hydrated},
            )
    except Exception:
        # Search evidence remains useful even if the ledger needs reconciliation;
        # the failure is logged and never exposed as provider detail.
        logger.exception("Falha ao registrar cobrança da pesquisa web")
    return {
        "query": query,
        "sources": sources,
        "source_count": len(sources),
        "sources_read": hydrated,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "search_mode": "firecrawl_discovery_with_selected_source_reading",
        "evidence_policy": "Use as fontes para responder ao pedido atual; diferencie fato, interpretação e lacuna.",
    }
