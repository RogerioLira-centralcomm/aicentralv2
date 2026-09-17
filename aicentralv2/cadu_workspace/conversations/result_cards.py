"""Safe, typed result cards projected from approved Cadu tool results.

The provider may describe or execute a tool, but it never supplies executable
browser code, arbitrary internal routes, or an authorization decision.  This
module reduces known tool outputs to the small chat contract consumed by the
Workspace renderer.
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit


TOOL_TYPES = {
    "market_research": "research",
    "market_news": "research",
    "web_research": "research",
    "search_audiencias": "audience",
    "audience_search": "audience",
    "link_test": "link",
    "screenshot_url": "link",
    "pdf_process": "document",
    "document_extract": "document",
}


def _object(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or len(value) > 100_000:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _text(value, limit=500):
    return str(value or "").strip()[:limit]


def _https_url(value):
    value = _text(value, 4000)
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return ""
        parsed.port
        return value
    except ValueError:
        return ""


def _tool_name(event):
    data = _object(event.get("data"))
    return _text(
        event.get("tool") or event.get("tool_name") or data.get("tool") or data.get("tool_name"),
        100,
    ).lower()


def _result(event):
    data = _object(event.get("data"))
    for value in (
        event.get("tool_output"), event.get("output"), event.get("result"),
        data.get("tool_output"), data.get("output"), data.get("result"), data.get("outputs"),
    ):
        parsed = _object(value)
        if parsed:
            return parsed
    return {}


def _action(action_id, label, *, url="", prompt="", style="secondary"):
    action = {"id": action_id, "label": label, "style": style}
    if url:
        action["url"] = url
    if prompt:
        action["prompt"] = prompt
    return action


def _research(payload):
    sources = []
    for item in (payload.get("sources") or payload.get("results") or [])[:6]:
        item = _object(item)
        title = _text(item.get("title") or item.get("name"), 160)
        url = _https_url(item.get("url") or item.get("source_url"))
        excerpt = _text(item.get("excerpt") or item.get("summary") or item.get("content"), 360)
        if title or excerpt:
            sources.append({"title": title or "Fonte pesquisada", "excerpt": excerpt, "url": url})
    summary = _text(payload.get("summary") or payload.get("answer") or payload.get("text"), 700)
    if not summary and not sources:
        return None
    actions = [_action("continue_research", "Aprofundar pesquisa", prompt="Aprofunde esta pesquisa com impacto, riscos e recomendações para o projeto.", style="primary")]
    return {
        "type": "research", "title": _text(payload.get("title"), 160) or "Pesquisa para o projeto",
        "summary": summary, "items": sources, "actions": actions,
    }


def _audience(payload):
    records = []
    for item in (payload.get("audiences") or payload.get("records") or payload.get("results") or [])[:10]:
        item = _object(item)
        name = _text(item.get("name") or item.get("nome"), 160)
        detail = _text(item.get("description") or item.get("descricao") or item.get("category"), 280)
        metrics = []
        for label, key in (("Alcance", "reach"), ("CPM", "cpm"), ("Plataforma", "platform")):
            value = _text(item.get(key) or item.get({"reach": "alcance", "platform": "plataforma"}.get(key, "")), 80)
            if value:
                metrics.append({"label": label, "value": value})
        if name:
            records.append({"title": name, "excerpt": detail, "metrics": metrics})
    if not records:
        return None
    return {
        "type": "audience", "title": _text(payload.get("title"), 160) or "Audiências encontradas",
        "summary": _text(payload.get("summary"), 500), "items": records,
        "actions": [_action("compare_audiences", "Comparar audiências", prompt="Compare as audiências encontradas por aderência, alcance, custo e papel no funil.", style="primary")],
    }


def _link(payload):
    url = _https_url(payload.get("url") or payload.get("tested_url") or payload.get("screenshot_url"))
    score = _text(payload.get("score") or payload.get("status"), 40)
    issues = [_text(value, 220) for value in (payload.get("issues") or payload.get("errors") or [])[:4] if _text(value, 220)]
    image = _https_url(payload.get("image_url") or payload.get("screenshot") or payload.get("preview_url"))
    if not any((url, score, issues, image)):
        return None
    actions = []
    if url:
        actions.append(_action("open_link", "Abrir link", url=url, style="secondary"))
    actions.append(_action("analyze_link", "Analisar resultado", prompt="Analise este resultado e indique os ajustes prioritários.", style="primary"))
    return {
        "type": "link", "title": _text(payload.get("title"), 160) or "Verificação de link",
        "summary": _text(payload.get("summary"), 500), "status": score,
        "items": [{"title": "Pontos a revisar", "excerpt": issue} for issue in issues],
        "media": [{"kind": "image", "url": image, "alt": "Prévia capturada"}] if image else [],
        "actions": actions,
    }


def _document(payload):
    title = _text(payload.get("title") or payload.get("name") or payload.get("filename"), 160)
    excerpt = _text(payload.get("summary") or payload.get("excerpt") or payload.get("text"), 900)
    pages = _text(payload.get("pages") or payload.get("page_count"), 30)
    if not title and not excerpt:
        return None
    metrics = [{"label": "Páginas", "value": pages}] if pages else []
    return {
        "type": "document", "title": title or "Documento processado", "summary": excerpt,
        "items": [{"title": "Conteúdo identificado", "excerpt": excerpt, "metrics": metrics}] if excerpt else [],
        "actions": [
            _action("use_document", "Usar neste trabalho", prompt="Use os pontos principais deste documento como contexto para a próxima resposta.", style="primary"),
            _action("create_brief", "Criar briefing", prompt="Transforme este documento em um briefing estruturado.", style="secondary"),
        ],
    }


def project(event, profile=None, client_id=None, actor_id=None):
    """Return one safe customer-facing result card, or ``None``.

    Context parameters are intentionally accepted for the future persistent
    action gateway.  This projection never uses provider-provided identifiers
    to access customer data.
    """
    del profile, client_id, actor_id
    if not isinstance(event, dict):
        return None
    kind = TOOL_TYPES.get(_tool_name(event))
    payload = _result(event)
    if not kind or not payload:
        return None
    card = {"research": _research, "audience": _audience, "link": _link, "document": _document}[kind](payload)
    return {"event": "result", "result": card} if card else None
