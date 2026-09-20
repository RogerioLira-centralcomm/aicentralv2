"""Tenant-safe web discovery and selective source reading for Cadu agents.

Search is deliberately separate from project retrieval.  The agent receives a
small, cleaned evidence packet with source URLs and selected page content; it
does not receive provider diagnostics, credentials or raw HTML.
"""

from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit
from uuid import uuid4

import requests

from ..cadu_credit_connector import CaduCreditConnector, CreditActor
from ..cadu_tool_billing import InsufficientToolCredits
from ..services.integration_credentials import resolve_firecrawl_api_key


logger = logging.getLogger(__name__)
MAX_QUERY = 400
MAX_SOURCES = 12
MAX_HYDRATED_SOURCES = 5
MAX_CONTENT_CHARS = 6000
MAX_CONTENT_BLOCKS = 18

SEARCH_DEPTHS = {
    "fast": {"limit": 4, "hydrate": 1},
    "analysis": {"limit": 7, "hydrate": 3},
    "agentic": {"limit": 10, "hydrate": 5},
}

_NOISE_TAGS = {"script", "style", "noscript", "template", "svg", "canvas", "nav", "footer", "header", "aside", "form"}
_CONTENT_TAGS = {"p", "li", "blockquote", "pre", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6"}
_NOISE_MARKERS = re.compile(
    r"(?:^|[-_ ])(?:ad|ads|advert|advertisement|banner|breadcrumb|cookie|footer|header|menu|nav|newsletter|popup|sidebar|social|subscribe)(?:$|[-_ ])",
    re.IGNORECASE,
)
_NOISE_COPY = re.compile(
    r"^(?:menu|navigation|home|início|entrar|login|assine|assinar|subscribe|advertisement|publicidade|todos os direitos reservados|all rights reserved)$",
    re.IGNORECASE,
)


class WebSearchUnavailable(RuntimeError):
    """Raised when the optional external search cannot produce evidence."""


class _ReadableHTMLParser(HTMLParser):
    """Keep article-like text while dropping page chrome and embedded code."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.current_tag = ""
        self.current = []
        self.blocks = []

    @staticmethod
    def _is_noise(attrs) -> bool:
        values = " ".join(str(value or "") for name, value in attrs if name in {"id", "class", "role", "aria-label"})
        return bool(_NOISE_MARKERS.search(values))

    def _flush(self):
        text = _clean_text(" ".join(self.current), 1200)
        self.current = []
        if not text or _is_noise_copy(text):
            return
        kind = "heading" if self.current_tag in {"h1", "h2", "h3", "h4", "h5", "h6"} else "paragraph"
        self.blocks.append({"kind": kind, "text": text})

    def handle_starttag(self, tag, attrs):
        tag = str(tag or "").lower()
        if self.skip_depth:
            self.skip_depth += 1
            return
        if tag in _NOISE_TAGS or self._is_noise(attrs):
            self._flush()
            self.skip_depth = 1
            return
        if tag in _CONTENT_TAGS:
            self._flush()
            self.current_tag = tag
        elif tag == "br":
            self.current.append(" ")

    def handle_endtag(self, tag):
        if self.skip_depth:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if str(tag or "").lower() in _CONTENT_TAGS:
            self._flush()
            self.current_tag = ""

    def handle_data(self, data):
        if not self.skip_depth and str(data or "").strip():
            self.current.append(str(data))


def _is_noise_copy(value: str) -> bool:
    text = " ".join(str(value or "").split())
    return bool(_NOISE_COPY.fullmatch(text)) or len(text) < 3


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


def _safe_favicon(value, page_url: str) -> str:
    candidate = _safe_url(value)
    if candidate:
        return candidate
    host = _host(page_url)
    return f"https://{host}/favicon.ico" if host else ""


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
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        title = _clean_text(item.get("title") or metadata.get("title"), 220)
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
            "favicon": _safe_favicon(item.get("favicon") or item.get("faviconUrl") or metadata.get("favicon"), url),
            "rank": index,
        })
    return sources


def _markdown_blocks(value) -> list[dict]:
    blocks = []
    for raw in str(value or "").replace("\r\n", "\n").split("\n"):
        line = _clean_text(unescape(raw), 1200)
        if not line or line.startswith("```") or _is_noise_copy(line):
            continue
        if re.search(r"(?:cookie|accept all|subscribe|advertisement|publicidade|all rights reserved)", line, re.IGNORECASE) and len(line) < 160:
            continue
        kind = "heading" if re.match(r"^#{1,6}\s", raw.strip()) else "paragraph"
        blocks.append({"kind": kind, "text": line})
    return blocks


def _review_blocks(blocks) -> list[dict]:
    """Apply a deterministic quality gate after extraction and before the LLM."""
    reviewed = []
    seen = set()
    for block in blocks if isinstance(blocks, list) else []:
        text = _clean_text((block or {}).get("text"), 1200) if isinstance(block, dict) else ""
        key = text.casefold()
        if not text or _is_noise_copy(text) or key in seen:
            continue
        if len(text) < 18 and (block.get("kind") if isinstance(block, dict) else "") != "heading":
            continue
        seen.add(key)
        reviewed.append({"kind": "heading" if block.get("kind") == "heading" else "paragraph", "text": text})
        if len(reviewed) >= MAX_CONTENT_BLOCKS:
            break
    return reviewed


def _read_source(url: str) -> dict:
    """Read one page, then keep only clean article-like text for the agent."""
    try:
        from ..crm_v3_web_scout import _firecrawl_scrape
        data = _firecrawl_scrape(url, formats=["markdown", "html"], timeout_s=35, only_main_content=True)
    except Exception:
        logger.info("Fonte web não pôde ser lida: %s", url, exc_info=True)
        return {}
    if not isinstance(data, dict):
        return {}
    blocks = []
    html = data.get("html") or ""
    if html:
        parser = _ReadableHTMLParser()
        try:
            parser.feed(str(html))
            blocks = parser.blocks
        except Exception:
            logger.info("HTML da fonte não pôde ser limpo: %s", url, exc_info=True)
    if not blocks:
        blocks = _markdown_blocks(data.get("markdown") or data.get("content") or "")
    blocks = _review_blocks(blocks)
    content = "\n\n".join(block["text"] for block in blocks)
    content = _clean_text(content, MAX_CONTENT_CHARS)
    if len(content) < 80:
        return {}
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    return {
        "content": content,
        "content_blocks": blocks,
        "content_excerpt": content[:520],
        "page_title": _clean_text(metadata.get("title") or data.get("title"), 220),
        "favicon": _safe_favicon(metadata.get("favicon") or data.get("favicon"), url),
        "published_at": _clean_text(
            metadata.get("publishedTime") or metadata.get("publishedDate") or data.get("published_at"), 60
        ),
        "cleaning": "firecrawl_main_content_plus_python_html_cleanup",
        "quality_gate": "passed",
    }


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
    depth = str(arguments.get("depth") or "analysis").strip().lower()
    if depth not in SEARCH_DEPTHS:
        raise ValueError("Profundidade inválida. Use fast, analysis ou agentic.")
    depth_config = SEARCH_DEPTHS[depth]
    limit = min(MAX_SOURCES, max(3, int(arguments.get("limit") or depth_config["limit"])))
    include_domains = _domains(arguments.get("include_domains"))
    exclude_domains = _domains(arguments.get("exclude_domains"))
    if include_domains and exclude_domains:
        raise ValueError("Escolha domínios para incluir ou excluir, não os dois.")
    recency = str(arguments.get("recency") or "").strip().lower()
    if recency not in {"", "day", "week", "month", "year"}:
        raise ValueError("Recência inválida.")
    include_content = arguments.get("include_content", True) is not False
    hydrate_limit = min(MAX_HYDRATED_SOURCES, limit, depth_config["hydrate"]) if include_content else 0
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
    selected = sources[:hydrate_limit]
    # Source reads are independent. Parallelizing them keeps the deep mode useful
    # without making the first response wait for a serial chain of page loads.
    with ThreadPoolExecutor(max_workers=min(4, len(selected) or 1)) as executor:
        extracted_sources = list(executor.map(lambda item: _read_source(item["url"]), selected))
    for source, extracted in zip(selected, extracted_sources):
        if extracted:
            source.update(extracted)
            source["title"] = extracted.get("page_title") or source["title"]
            source["excerpt"] = extracted.get("content_excerpt") or source["excerpt"]
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
        "result_type": "search",
        "query": query,
        "sources": sources,
        "source_count": len(sources),
        "sources_read": hydrated,
        "research_depth": depth,
        "sites_requested": limit,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "search_mode": "firecrawl_discovery_with_selected_source_reading",
        "evidence_policy": "Use as fontes para responder ao pedido atual; diferencie fato, interpretação e lacuna.",
        "review_stage": "python_cleanup_quality_gate_before_agent_synthesis",
    }


def read(context, arguments: dict) -> dict:
    """Read exactly one user-provided URL through the same clean evidence pipeline."""
    url = _safe_url(arguments.get("url"))
    if not url:
        raise ValueError("Informe um link HTTPS válido para analisar.")
    actor = CreditActor.from_values(context.client_id, context.user_id)
    credits = CaduCreditConnector()
    try:
        credits.authorize_firecrawl(actor, "scrape", pages=1)
    except InsufficientToolCredits as exc:
        raise ValueError("Não há saldo suficiente para ler este link agora.") from exc
    extracted = _read_source(url)
    if not extracted:
        raise WebSearchUnavailable("Não consegui extrair conteúdo legível deste link.")
    request_id = str(arguments.get("request_id") or getattr(context, "request_id", "") or uuid4())[:120]
    source = {
        "id": "web-direct-1",
        "title": extracted.get("page_title") or _host(url),
        "url": url,
        "domain": _host(url),
        "excerpt": extracted.get("content_excerpt") or "",
        "source_type": "direct_url",
        "rank": 1,
        **extracted,
    }
    try:
        credits.charge_firecrawl(
            actor=actor, idempotency_key=f"web-read:{request_id}:scrape",
            operation="scrape", pages=1, app="Cadu Pesquisa", stage="web_direct_read",
            metadata={"conversation_id": str(context.conversation_id or ""), "url_host": _host(url)},
        )
    except Exception:
        logger.exception("Falha ao registrar cobrança da leitura direta")
    return {
        "result_type": "direct_read",
        "query": url,
        "sources": [source],
        "source_count": 1,
        "sources_read": 1,
        "searched_at": datetime.now(timezone.utc).isoformat(),
        "search_mode": "firecrawl_direct_page_with_selected_source_reading",
        "evidence_policy": "Use somente o conteúdo limpo deste link; diferencie fato, interpretação e lacuna.",
        "review_stage": "python_cleanup_quality_gate_before_agent_synthesis",
    }
