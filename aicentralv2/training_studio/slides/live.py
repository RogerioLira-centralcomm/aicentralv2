"""Deck 16:9 a partir das páginas de palco do editor."""

import re
from html import unescape


PAGE_RE = re.compile(
    r"<article\b([^>]*\bts-page\b[^>]*)>(.*?)</article>",
    re.I | re.S,
)


def pages_from_html(html):
    pages = []
    for match in PAGE_RE.finditer(html or ""):
        attrs = match.group(1) or ""
        body = match.group(2) or ""
        pages.append(
            {
                "layout": _attr(attrs, "data-layout") or "copy",
                "surface": _attr(attrs, "data-surface") or "roteiro",
                "title": _first(body, ("h2", "h3", "h1")) or "Página",
                "lede": _first(body, ("p",)),
                "lines": _lines(body),
                "image": _img(body),
                "metrics": _metrics(body),
            }
        )
    return pages


def slides_payload(html, sessao=None):
    sessao = dict(sessao or {})
    sessao["conteudo_html"] = html if html is not None else sessao.get("conteudo_html")
    return list(deck_from_html(sessao).get("slides") or [])


def deck_from_sessao(sessao):
    sessao = sessao or {}
    stored = sessao.get("palco_json")
    if isinstance(stored, list) and stored:
        return {
            "slug": sessao.get("slug") or "",
            "titulo": sessao.get("titulo") or "Sessão",
            "horario": _horario(sessao),
            "facilitadores": list(sessao.get("facilitadores") or []),
            "tipo": sessao.get("tipo") or "fonte",
            "slides": stored,
            "live": True,
        }
    return deck_from_html(sessao)


def deck_from_html(sessao):
    sessao = sessao or {}
    pages = pages_from_html(sessao.get("conteudo_html") or "")
    slides_only = [item for item in pages if item.get("surface") == "slide"]
    chosen = slides_only or pages
    slides = [_page_to_slide(item, sessao) for item in chosen]
    if not slides:
        slides = [
            {
                "layout": "statement",
                "kicker": "Palco",
                "title": sessao.get("titulo") or "Sessão",
                "lede": "Ainda não há página de palco. Gere no Studio.",
                "note": "Separe roteiro e palco antes de projetar.",
            }
        ]
    return {
        "slug": sessao.get("slug") or "",
        "titulo": sessao.get("titulo") or "Sessão",
        "horario": _horario(sessao),
        "facilitadores": list(sessao.get("facilitadores") or []),
        "tipo": sessao.get("tipo") or "fonte",
        "slides": slides,
        "live": True,
    }


def _page_to_slide(page, sessao):
    kicker = "Palco" if page.get("surface") == "slide" else "Roteiro"
    if page.get("metrics"):
        return {
            "layout": "metrics",
            "kicker": kicker,
            "title": page["title"],
            "metrics": page["metrics"],
            "note": "",
        }
    if page.get("image"):
        return {
            "layout": "visual",
            "kicker": kicker,
            "title": page["title"],
            "lede": page.get("lede") or "",
            "image": page["image"],
            "lines": page.get("lines") or [],
            "note": "",
        }
    if page.get("layout") == "title":
        return {
            "layout": "title",
            "kicker": sessao.get("titulo") or kicker,
            "title": page["title"],
            "lede": page.get("lede") or "",
            "meta": " · ".join(sessao.get("facilitadores") or []) or "",
            "note": "",
        }
    return {
        "layout": "statement",
        "kicker": kicker,
        "title": page["title"],
        "lede": page.get("lede") or " ".join((page.get("lines") or [])[:2]),
        "note": "",
    }


def _attr(attrs, name):
    match = re.search(rf"""{name}=["']([^"']+)["']""", attrs or "", flags=re.I)
    return match.group(1) if match else ""


def _first(html, tags):
    for tag in tags:
        match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", html or "", flags=re.I | re.S)
        if match:
            text = _plain(match.group(1))
            if text:
                return text
    return ""


def _lines(html):
    copy = re.search(r'class="[^"]*ts-page-copy[^"]*"[^>]*>(.*?)</div>', html or "", flags=re.I | re.S)
    source = copy.group(1) if copy else html
    lines = []
    for match in re.finditer(r"<li\b[^>]*>(.*?)</li>|<p\b[^>]*>(.*?)</p>", source or "", flags=re.I | re.S):
        text = _plain(match.group(1) or match.group(2) or "")
        if text:
            lines.append(text)
    return lines[:8]


def _img(html):
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html or "", flags=re.I)
    return match.group(1) if match else ""


def _metrics(html):
    metrics = []
    for match in re.finditer(
        r'class="[^"]*ts-metric[^"]*"[^>]*>.*?'
        r'class="[^"]*ts-metric-value[^"]*"[^>]*>(.*?)</p>.*?'
        r'class="[^"]*ts-metric-label[^"]*"[^>]*>(.*?)</p>',
        html or "",
        flags=re.I | re.S,
    ):
        metrics.append(
            {
                "value": _plain(match.group(1)),
                "label": _plain(match.group(2)),
                "note": "",
            }
        )
    return metrics[:4]


def _plain(html):
    text = re.sub(r"<[^>]+>", " ", html or "")
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _horario(sessao):
    start = sessao.get("horario_inicio") or ""
    end = sessao.get("horario_fim") or ""
    if start and end:
        return f"{start}–{end}"
    return "Fonte"
