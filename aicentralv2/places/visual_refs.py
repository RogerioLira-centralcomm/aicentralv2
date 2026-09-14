"""Busca fotos reais do lugar no Firecrawl antes de gerar a imagem."""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlparse

import requests

from .schema import CITY_LABELS, as_dict, text

logger = logging.getLogger(__name__)

SKIP_HOSTS = (
    "lookaside.instagram.com",
    "instagram.com",
    "facebook.com",
    "fbcdn.net",
    "pbs.twimg.com",
)

AIRPORT_ALIASES = {
    "CNF": "Tancredo Neves BH Airport",
    "CGH": "Congonhas",
    "SDU": "Santos Dumont",
    "GIG": "Galeão Tom Jobim",
}

PREFERRED = (
    "bh-airport",
    "bhairport",
    "archdaily",
    "aeroin",
    "panrotas",
    "infraero",
    "anac.gov",
    "rio-galeao",
    "gru.com.br",
)


def visual_query(place: dict, *, kind: str = "hero", point: dict | None = None) -> str:
    title = text(place.get("title"))
    city = text(place.get("city_label")) or CITY_LABELS.get(text(place.get("city")), "") or text(place.get("city"))
    code = text(place.get("code")).upper()
    place_type = text(place.get("place_type"))
    kind = (kind or "hero").lower()
    point = as_dict(point)
    name = text(point.get("name"))
    point_kind = text(point.get("kind"))
    alias = AIRPORT_ALIASES.get(code, "")
    if kind in ("hero", "og"):
        if place_type == "shopping":
            return f"{title} {city} shopping fachada exterior foto".strip()
        if place_type == "evento":
            return f"{title} {city} recinto fachada exterior foto".strip()
        return f"{title} {code} {alias} {city} terminal fachada exterior foto".strip()
    if kind == "map":
        if place_type == "aeroporto":
            return f"{title} {code} {city} vista aérea terminal foto".strip()
        return f"{title} {city} vista aérea foto".strip()
    if point_kind in ("terminal", "embarque", "premium"):
        return f"{title} {alias or code} {name or 'saguão'} interior check-in foto".strip()
    if point_kind == "mobilidade":
        return f"{title} {alias or code} estacionamento curbside foto".strip()
    return f"{title} {name} {city} foto".strip()


def search_visual_refs(
    place: dict,
    *,
    kind: str = "hero",
    point: dict | None = None,
    limit: int = 4,
) -> list[dict]:
    query = visual_query(place, kind=kind, point=point)
    key = (os.getenv("FIRECRAWL_API_KEY") or "").strip()
    if not key or not query:
        return []
    try:
        response = requests.post(
            _search_url(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "query": query,
                "sources": ["images"],
                "limit": max(4, min(int(limit) * 2, 10)),
                "ignoreInvalidURLs": True,
            },
            timeout=25,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("Busca visual do place falhou: %s", exc)
        return []
    data = body.get("data") if isinstance(body, dict) else {}
    rows = (data or {}).get("images") or (data or {}).get("web") or []
    refs = []
    seen = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        url = text(item.get("imageUrl") or item.get("image_url") or item.get("url"))
        if not usable_image_url(url) or url in seen:
            continue
        seen.add(url)
        refs.append(
            {
                "url": url,
                "title": text(item.get("title")),
                "page_url": text(item.get("sourceUrl") or item.get("source_url") or item.get("url")),
                "query": query,
            }
        )
    refs.sort(key=_score, reverse=True)
    return refs[:limit]


def reference_urls(refs: list[dict]) -> list[str]:
    return [text(item.get("url")) for item in refs if usable_image_url(text(item.get("url")))][:2]


def usable_image_url(url: str) -> bool:
    if url.startswith("data:image/"):
        return True
    if not url.startswith(("https://", "http://")):
        return False
    host = urlparse(url).netloc.lower()
    return not any(skip in host for skip in SKIP_HOSTS)


def _score(item: dict[str, Any]) -> int:
    blob = " ".join(
        text(item.get(key)).lower() for key in ("url", "page_url", "title")
    )
    score = 0
    for token in PREFERRED:
        if token in blob:
            score += 40
    if "fachada" in blob or "terminal" in blob:
        score += 10
    if "saguão" in blob or "check-in" in blob or "checkin" in blob:
        score += 8
    return score


def _search_url() -> str:
    endpoint = (os.getenv("FIRECRAWL_API_URL") or "https://api.firecrawl.dev/v2/search").strip()
    if endpoint.endswith("/scrape"):
        return endpoint.rsplit("/scrape", 1)[0] + "/search"
    if endpoint.endswith("/v1") or endpoint.endswith("/v2"):
        return endpoint + "/search"
    if not endpoint.endswith("/search"):
        return endpoint.rstrip("/") + "/v2/search"
    return endpoint
