"""Captura e revisão de referências do passo 1 — URL, arquivo e busca."""

from __future__ import annotations

import base64
import logging
import os
import re
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

SEARCH_FOCUS = {
    "briefing": {
        "label": "completar o briefing",
        "instruction": "identifique lacunas, contexto e fatos públicos que ajudem a sustentar o briefing",
        "papel": "campanha",
    },
    "marca": {
        "label": "entender a marca",
        "instruction": "priorize posicionamento, produtos, público, presença e movimentos recentes da marca",
        "papel": "marca",
    },
    "cliente": {
        "label": "conhecer o cliente",
        "instruction": "priorize atuação, praças, prioridades de negócio e oportunidades de comunicação do anunciante",
        "papel": "marca",
    },
    "agencia": {
        "label": "conhecer a agência",
        "instruction": "priorize especialidades, portfólio, clientes atendidos e trabalhos recentes da agência",
        "papel": "marca",
    },
    "campanhas": {
        "label": "explorar campanhas",
        "instruction": "priorize campanhas recentes, mensagens, canais utilizados e movimentos dos concorrentes",
        "papel": "campanha",
    },
    "mercado": {
        "label": "ler o mercado",
        "instruction": "priorize tendências, comportamento, dados públicos e mudanças na categoria",
        "papel": "mercado",
    },
}


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
    if kind == "image" and _looks_like_ooh_inventory(raw):
        captured = capture_ooh_inventory(raw, original)
        return {**captured, "name": original}
    return _captured(kind, original, raw, name=original)


def capture_ooh_inventory(raw: str, label: str = "Pontos de OOH informados") -> dict:
    """Capture points explicitly supplied by the executive without inventing inventory data."""
    raw = (raw or "").strip()
    if len(raw) < 8:
        raise ValueError("Cole ao menos um ponto de OOH.")
    normalized = re.sub(r"\r\n?", "\n", raw)
    blocks = [re.sub(r"\s+", " ", block).strip() for block in re.split(r"\n\s*\n+", normalized) if block.strip()]
    if len(blocks) == 1:
        blocks = [part.strip() for part in re.split(
            r"(?=(?:Banca\s+Est[aá]tica|Front\s+Light|Outdoor|Painel(?:\s+Digital)?|Mobili[aá]rio)\s*[-:])",
            blocks[0], flags=re.I,
        ) if part.strip()]
    points = []
    for index, block in enumerate(blocks[:100], start=1):
        name, _, _ = block.partition("-")
        points.append({"id": f"ooh-{index}", "name": name.strip() or f"Ponto OOH {index}", "detail": block})
    notes = "Inventário OOH informado pelo executivo:\n" + "\n".join(
        f"{index}. {point['detail']}" for index, point in enumerate(points, start=1)
    )
    return normalize_reference({
        "kind": "inventory", "label": label.strip() or "Pontos de OOH informados",
        "notas": notes, "papel": "inventario",
        "fatos": {"inventario_ooh": {"source": "referencia_do_briefing", "points": points}},
    })


def _looks_like_ooh_inventory(raw: str) -> bool:
    text_lower = text(raw).lower()
    kinds = re.findall(r"\b(?:banca\s+est[aá]tica|front\s+light|outdoor|painel(?:\s+digital)?|mobili[aá]rio)\b", text_lower)
    return len(kinds) >= 2 or ("banca estática" in text_lower and "av." in text_lower)


def capture_search(query: str, briefing: str = "", scope: str = "mercado") -> dict:
    query = (query or "").strip()
    if len(query) < 3:
        raise ValueError("Escreva o que devemos pesquisar.")
    scope = scope if scope in SEARCH_FOCUS else "briefing"
    raw = search_web(query, briefing, scope)
    source_mode = "model" if raw.startswith("Fonte: conhecimento do modelo") else "web"
    return _captured("search", query, raw, scope=scope, source_mode=source_mode)


def discover_campaigns(query: str, briefing: str = "") -> dict:
    """Return current Firecrawl search candidates for the campaign-research modal."""
    from ..services.integration_credentials import resolve_firecrawl_api_key

    query = (query or "").strip()
    if len(query) < 3:
        raise ValueError("Informe a marca, campanha ou categoria a pesquisar.")
    key = resolve_firecrawl_api_key()
    if not key:
        captured = capture_search(query, briefing, "campanhas")
        return {"query": query, "items": [{"title": captured["label"], "snippet": captured["notas"], "url": "", "image_url": "", "source_mode": captured["source_mode"]}]}
    hits = _firecrawl_search(f"{query}. Foco: {SEARCH_FOCUS['campanhas']['instruction']}", key)
    return {
        "query": query,
        "items": [{
            "title": text(item.get("title")) or "Fonte de campanha",
            "snippet": text(item.get("snippet")),
            "url": text(item.get("url")),
            "image_url": text(item.get("image_url") or item.get("image") or item.get("imageUrl")),
            "source_mode": "web",
        } for item in hits],
    }


def search_web(query: str, briefing: str = "", scope: str = "mercado") -> str:
    from ..services.integration_credentials import resolve_firecrawl_api_key

    focus = SEARCH_FOCUS.get(scope, SEARCH_FOCUS["briefing"])
    search_query = f"{query}. Foco: {focus['instruction']}"
    hint = strip_markdown((briefing or "").strip())[:500]
    if hint:
        search_query += f". Contexto do briefing: {hint}"
    key = resolve_firecrawl_api_key()
    if key:
        hits = _firecrawl_search(search_query, key)
        pages = _scrape_search_hits(hits)
        if pages:
            return pages
        listing = _format_search_hits(hits)
        if listing:
            return listing
    hint = strip_markdown((briefing or "").strip())[:800]
    prompt = (
        f"Pesquise dados atuais sobre: {query}\n"
        f"Objetivo da descoberta: {focus['instruction']}.\n"
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


def review_reference(raw: str, *, kind: str, label: str, scope: str = "mercado") -> dict:
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
        papel = SEARCH_FOCUS.get(scope, SEARCH_FOCUS["briefing"])["papel"]
    return {"notas": notas, "fatos": fatos, "papel": papel}


def _captured(kind: str, label: str, raw: str, **extra) -> dict:
    reviewed = review_reference(raw, kind=kind, label=label, scope=text(extra.get("scope")))
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
            hits.append({"title": title, "snippet": snippet, "url": url, "image_url": text(item.get("imageUrl") or item.get("image_url") or item.get("image"))})
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
