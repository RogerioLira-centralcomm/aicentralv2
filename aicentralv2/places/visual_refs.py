"""Fotos reais do lugar: Firecrawl busca, raspa o site oficial e a galeria guarda a cópia."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from flask import current_app, has_app_context

from .schema import CITY_LABELS, as_dict, as_list, infer_point_scope, text

logger = logging.getLogger(__name__)

SKIP_HOSTS = (
    "lookaside.instagram.com",
    "instagram.com",
    "facebook.com",
    "fbcdn.net",
    "pbs.twimg.com",
    "gettyimages.com",
    "media.gettyimages.com",
    "alamy.com",
    "shutterstock.com",
)

AIRPORT_ALIASES = {
    "CNF": "Tancredo Neves BH Airport",
    "CGH": "Congonhas",
    "SDU": "Santos Dumont",
    "GIG": "Galeão Tom Jobim",
}

OFFICIAL_PAGES = {
    "CNF": ("https://www.bh-airport.com.br/",),
    "CGH": ("https://www.aeroportodecongonhas.net/",),
    "SDU": ("https://www4.infraero.gov.br/aeroportos/aeroporto-do-rio-de-janeiro-santos-dumont/",),
    "GIG": ("https://www.riogaleao.com/",),
    "DMM": ("https://www.diamondmall.com.br/",),
    "IGT": ("https://iguatemi.com.br/saopaulo",),
    "IBI": ("https://parqueibirapuera.org/",),
    "EXP": ("https://www.expominas.com.br/",),
    "BHS": ("https://www.bhshopping.com.br/",),
    "PSV": ("https://www.patiosavassi.com/",),
    "MNS": ("https://www.minasshopping.com.br/",),
    "DRY": ("https://www.shoppingdelrey.com.br/",),
    "MCB": ("https://www.mercadocentral.com.br/",),
    "SMB": ("https://www.shoppingmorumbi.com.br/",),
    "JKI": ("https://iguatemi.com.br/jk",),
    "ELD": ("https://www.shoppingeldorado.com.br/",),
    "VLB": ("https://www.parquevillalobos.sp.gov.br/",),
    "MSP": ("https://www.mercadomunicipal.com.br/",),
    "BRS": ("https://www.barrashopping.com.br/",),
    "RSL": ("https://www.riosul.com.br/",),
    "LBN": ("https://www.shopleblon.com.br/",),
    "MAR": ("https://www.maracana.com/",),
    "PLG": ("https://eavparquelage.rj.gov.br/",),
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
    "riogaleao",
    "gru.com.br",
    "diamondmall",
    "iguatemi",
    "parqueibirapuera",
    "expominas",
    "bhshopping",
    "patiosavassi",
    "minasshopping",
    "shoppingdelrey",
    "mercadocentral",
    "shoppingmorumbi",
    "shoppingeldorado",
    "barrashopping",
    "riosul",
    "shopleblon",
    "maracana",
    "eavparquelage",
    "parquevillalobos",
    "mercadomunicipal",
)

MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")
BARE_IMAGE = re.compile(r"https?://[^\s\"')]+\.(?:jpe?g|png|webp)(?:\?[^\s\"')]*)?", re.I)


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
    scope = infer_point_scope(point_kind, point.get("scope")) if point else "internal"
    if kind in ("hero", "og"):
        if place_type == "shopping":
            extra = " Faria Lima Jardim Paulistano" if code == "IGT" else ""
            return f"{title} {city}{extra} shopping fachada exterior foto".strip()
        if place_type == "evento":
            return f"{title} {city} recinto fachada exterior foto".strip()
        return f"{title} {code} {alias} {city} terminal fachada exterior foto".strip()
    if kind == "map":
        if place_type == "aeroporto":
            return f"{title} {code} {city} vista aérea terminal foto".strip()
        return f"{title} {city} vista aérea foto".strip()
    name_l = (name or "").lower()
    if scope == "external" or "washington" in name_l:
        return f"{title} {name} {city} bairro rua foto".strip()
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
    key = _api_key()
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
            _ref(
                url,
                kind=kind,
                point=point,
                title=text(item.get("title")),
                page_url=text(item.get("sourceUrl") or item.get("source_url") or item.get("url")),
                query=query,
            )
        )
    refs.sort(key=_score, reverse=True)
    return refs[:limit]


def scrape_page_images(url: str, *, kind: str = "hero", point: dict | None = None, query: str = "") -> list[dict]:
    key = _api_key()
    page = text(url)
    if not key or not page.startswith(("https://", "http://")):
        return []
    try:
        response = requests.post(
            _scrape_url(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"url": page, "formats": ["markdown", "links"], "onlyMainContent": True},
            timeout=35,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("Scrape visual do place falhou: %s", exc)
        return []
    data = body.get("data") if isinstance(body, dict) else body
    if not isinstance(data, dict):
        return []
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    markdown = text(data.get("markdown"))
    found = []
    og = text(metadata.get("ogImage") or metadata.get("og:image") or metadata.get("image"))
    if og:
        found.append(urljoin(page, og))
    found.extend(MARKDOWN_IMAGE.findall(markdown))
    found.extend(BARE_IMAGE.findall(markdown))
    for link in as_list(data.get("links")):
        href = text(link if not isinstance(link, dict) else link.get("url") or link.get("href"))
        if href.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            found.append(urljoin(page, href))
    refs = []
    seen = set()
    for raw in found:
        image = text(raw)
        if image.startswith("/"):
            image = urljoin(page, image)
        if not usable_image_url(image) or image in seen:
            continue
        seen.add(image)
        refs.append(_ref(image, kind=kind, point=point, title=text(metadata.get("title")), page_url=page, query=query))
    refs.sort(key=_score, reverse=True)
    return refs[:6]


def collect_visual_refs(
    place: dict,
    *,
    kind: str = "hero",
    point: dict | None = None,
    limit: int = 6,
) -> list[dict]:
    query = visual_query(place, kind=kind, point=point)
    found = []
    found.extend(search_visual_refs(place, kind=kind, point=point, limit=limit))
    for page in official_pages(place)[:2]:
        found.extend(scrape_page_images(page, kind=kind, point=point, query=query))
    merged = merge_gallery([], found)
    localized = [localize_ref(item, place) for item in merged]
    localized.sort(key=_score, reverse=True)
    return localized[:limit]


def official_pages(place: dict) -> list[str]:
    code = text(place.get("code")).upper()
    pages = [text(item) for item in OFFICIAL_PAGES.get(code, ()) if text(item)]
    research = as_dict(place.get("research"))
    for item in as_list(research.get("sources")):
        url = text(item.get("url") if isinstance(item, dict) else "")
        if url.startswith(("https://", "http://")):
            pages.append(url)
    seen = set()
    unique = []
    for url in pages:
        if url in seen:
            continue
        seen.add(url)
        unique.append(url)
    return unique


def selected_gallery_refs(place: dict, *, kind: str = "hero", point: dict | None = None) -> list[dict]:
    point = as_dict(point)
    point_id = text(point.get("id") or point.get("name"))
    kind = (kind or "hero").lower()
    media = as_dict(place.get("media"))
    selected = []
    fallback = []
    for item in as_list(media.get("gallery")):
        row = as_dict(item)
        if text(row.get("kind")) != kind:
            continue
        if kind == "point" and point_id and text(row.get("point_id")) not in ("", point_id):
            continue
        if row.get("selected") and text(row.get("review_status")) == "approved":
            selected.append(row)
        elif text(row.get("review_status")) == "approved":
            fallback.append(row)
    picked = selected or fallback[:2]
    return [item for item in picked if usable_image_url(text(item.get("url") or item.get("source_url")))][:2]


def gallery_items_by_ids(place: dict, ids) -> list[dict]:
    if isinstance(ids, str) and text(ids):
        wanted = {text(ids)}
    else:
        wanted = {text(item) for item in as_list(ids) if text(item)}
    if not wanted:
        return []
    media = as_dict(place.get("media"))
    return [as_dict(item) for item in as_list(media.get("gallery")) if text(as_dict(item).get("id")) in wanted]


def merge_gallery(existing, incoming) -> list[dict]:
    rows = []
    seen = set()
    for raw in list(as_list(incoming)) + list(as_list(existing)):
        item = as_dict(raw)
        url = text(item.get("source_url") or item.get("url"))
        gid = text(item.get("id")) or _ref_id(url)
        if not url or gid in seen:
            continue
        seen.add(gid)
        item["id"] = gid
        item["source_url"] = url
        item["url"] = text(item.get("url")) or url
        rows.append(item)
    return rows


def select_gallery(gallery, item_id: str) -> list[dict]:
    wanted = text(item_id)
    chosen = next((as_dict(item) for item in as_list(gallery) if text(as_dict(item).get("id")) == wanted), {})
    kind = text(chosen.get("kind")) or "hero"
    point_id = text(chosen.get("point_id"))
    updated = []
    for raw in as_list(gallery):
        item = dict(as_dict(raw))
        same = text(item.get("kind")) == kind and text(item.get("point_id")) == point_id
        item["selected"] = same and text(item.get("id")) == wanted
        updated.append(item)
    return updated


def localize_ref(item: dict, place: dict) -> dict:
    row = dict(as_dict(item))
    source = text(row.get("source_url") or row.get("url"))
    row["id"] = text(row.get("id")) or _ref_id(source)
    row["source_url"] = source
    local = text(row.get("url"))
    if local.startswith("/static/images/places/"):
        return row
    stored = store_gallery_image(source, place, kind=text(row.get("kind")) or "hero")
    if stored:
        row["url"] = stored
    else:
        row["url"] = source
    return row


def store_gallery_image(source_url: str, place: dict, *, kind: str = "hero") -> str:
    url = text(source_url)
    if not url.startswith(("https://", "http://")):
        return ""
    try:
        response = requests.get(
            url,
            timeout=25,
            headers={"User-Agent": "CentralX-Places/1.0"},
            stream=True,
        )
        response.raise_for_status()
        raw = response.content[: 8 * 1024 * 1024]
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("Cópia da foto real falhou: %s", exc)
        return ""
    if len(raw) < 800 or raw[:1] in (b"<", b"{"):
        return ""
    mime = (response.headers.get("content-type") or "").split(";", 1)[0].lower()
    ext = "png" if "png" in mime or raw.startswith(b"\x89PNG") else "jpg"
    slug = text(place.get("slug") or place.get("code") or "place").lower() or "place"
    digest = hashlib.sha1(raw).hexdigest()[:8]
    filename = f"{slug}-{kind}-{digest}.{ext}"
    dest = os.path.join(_gallery_dir(), filename)
    if not os.path.exists(dest):
        with open(dest, "wb") as handle:
            handle.write(raw)
    return f"/static/images/places/gallery/{filename}"


def materialize_reference_urls(urls: list[str]) -> list[str]:
    ready = []
    for url in urls:
        value = text(url)
        if value.startswith("data:image/"):
            ready.append(value)
        elif value.startswith("/static/"):
            data = _data_url(_static_path(value))
            if data:
                ready.append(data)
        elif usable_image_url(value):
            ready.append(value)
        if len(ready) == 2:
            break
    return ready


def reference_urls(refs: list[dict]) -> list[str]:
    urls = []
    for item in refs:
        local = text(item.get("url"))
        remote = text(item.get("source_url"))
        pick = local if usable_image_url(local) else remote
        if usable_image_url(pick) and pick not in urls:
            urls.append(pick)
    return urls[:2]


def usable_image_url(url: str) -> bool:
    if url.startswith("data:image/"):
        return True
    if url.startswith("/static/images/places/"):
        return True
    if not url.startswith(("https://", "http://")):
        return False
    host = urlparse(url).netloc.lower()
    return not any(skip in host for skip in SKIP_HOSTS)


def _ref(url: str, *, kind: str, point: dict | None, title: str, page_url: str, query: str) -> dict:
    point = as_dict(point)
    return {
        "id": _ref_id(url),
        "kind": (kind or "hero").lower(),
        "point_id": text(point.get("id") or point.get("name")),
        "url": url,
        "source_url": url,
        "page_url": page_url,
        "title": title,
        "query": query,
        "selected": False,
    }


def _ref_id(url: str) -> str:
    return hashlib.sha1(text(url).encode("utf-8")).hexdigest()[:12]


def _score(item: dict[str, Any]) -> int:
    blob = " ".join(text(item.get(key)).lower() for key in ("url", "source_url", "page_url", "title"))
    score = 0
    for token in PREFERRED:
        if token in blob:
            score += 40
    if "fachada" in blob or "terminal" in blob:
        score += 10
    if "saguão" in blob or "check-in" in blob or "checkin" in blob:
        score += 8
    if "jk iguatemi" in blob or "jk-iguatemi" in blob:
        score -= 80
    if item.get("selected"):
        score += 80
    if text(item.get("url")).startswith("/static/"):
        score += 5
    return score


def _api_key() -> str:
    try:
        from aicentralv2.services.integration_credentials import resolve_firecrawl_api_key

        return resolve_firecrawl_api_key()
    except Exception:
        return (os.getenv("FIRECRAWL_API_KEY") or "").strip()


def _search_url() -> str:
    return _endpoint("search")


def _scrape_url() -> str:
    return _endpoint("scrape")


def _endpoint(name: str) -> str:
    endpoint = (os.getenv("FIRECRAWL_API_URL") or "https://api.firecrawl.dev/v2/search").strip()
    if endpoint.endswith("/scrape") or endpoint.endswith("/search"):
        return endpoint.rsplit("/", 1)[0] + f"/{name}"
    if endpoint.endswith("/v1") or endpoint.endswith("/v2"):
        return endpoint + f"/{name}"
    if f"/{name}" not in endpoint:
        return endpoint.rstrip("/") + f"/v2/{name}"
    return endpoint


def _gallery_dir() -> str:
    dest = os.path.abspath(os.path.join(_static_root(), "images", "places", "gallery"))
    os.makedirs(dest, exist_ok=True)
    return dest


def _static_root() -> str:
    if has_app_context() and current_app.static_folder:
        return current_app.static_folder
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))


def _static_path(url: str) -> str:
    relative = text(url).split("/static/", 1)[-1]
    return os.path.abspath(os.path.join(_static_root(), relative))


def _data_url(path: str) -> str:
    if not path or not os.path.isfile(path):
        return ""
    with open(path, "rb") as handle:
        raw = handle.read()
    mime = "image/png" if raw.startswith(b"\x89PNG") else "image/jpeg"
    import base64

    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
