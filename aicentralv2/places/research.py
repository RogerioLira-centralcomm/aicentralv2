"""Busca de lugares, pesquisa de região e revisão do payload."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

from ..services.openrouter_service import OpenRouterError, chat_completion
from .schema import CITIES, POINT_KINDS, as_dict, as_list, normalize_payload, text

logger = logging.getLogger(__name__)

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "CentralX-Places/1.0 (comercial@centralcomm.media)"
RESEARCH_MODEL = os.getenv("PLACES_RESEARCH_MODEL") or os.getenv(
    "TRAINING_RESEARCH_MODEL", "perplexity/sonar-pro"
)
REVIEW_MODEL = os.getenv("PLACES_REVIEW_MODEL") or os.getenv(
    "PLACES_FINALIZE_MODEL", "openai/gpt-5-mini"
)
FINALIZE_MODEL = os.getenv("PLACES_FINALIZE_MODEL", "openai/gpt-5-mini")


class ResearchError(RuntimeError):
    pass


def _city_from_address(address: dict) -> str:
    blob = " ".join(
        text(address.get(key))
        for key in ("state", "city", "municipality", "town", "display_name")
    ).lower()
    if "rio de janeiro" in blob or "rio de janeiro" in text(address.get("state")).lower():
        if "são paulo" not in blob:
            return "rj"
    if "minas" in blob or "belo horizonte" in blob:
        return "bh"
    if "são paulo" in blob or "sao paulo" in blob:
        return "sp"
    return ""


def search_places(query: str, *, limit: int = 6) -> list[dict]:
    q = text(query)
    if len(q) < 2:
        raise ResearchError("Informe pelo menos duas letras para buscar o lugar.")
    try:
        response = requests.get(
            NOMINATIM,
            params={
                "q": q,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": max(1, min(int(limit), 8)),
                "countrycodes": "br",
            },
            headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR"},
            timeout=12,
        )
        response.raise_for_status()
        rows = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ResearchError("Não foi possível buscar o lugar agora.") from exc
    found = []
    for item in rows if isinstance(rows, list) else []:
        lat = item.get("lat")
        lng = item.get("lon")
        try:
            lat_n = float(lat)
            lng_n = float(lng)
        except (TypeError, ValueError):
            continue
        address = item.get("address") if isinstance(item.get("address"), dict) else {}
        city = _city_from_address({**address, "display_name": item.get("display_name")})
        found.append(
            {
                "title": text(item.get("name") or item.get("display_name")),
                "label": text(item.get("display_name")),
                "lat": lat_n,
                "lng": lng_n,
                "kind": text(item.get("type") or item.get("class")),
                "city": city if city in CITIES else "",
                "osm_id": item.get("osm_id"),
            }
        )
    return found


def geocode_one(query: str, *, near: dict | None = None) -> dict | None:
    q = text(query)
    if near and near.get("lat") is not None and near.get("lng") is not None:
        q = f"{q} {near.get('lat')},{near.get('lng')}"
    try:
        rows = search_places(q, limit=1)
    except ResearchError:
        return None
    return rows[0] if rows else None


def research_region(place: dict) -> dict:
    title = text(place.get("title"))
    city = text(place.get("city_label") or place.get("city"))
    code = text(place.get("code"))
    if not title:
        raise ResearchError("Salve o place com um nome antes de pesquisar a região.")
    geo = as_dict(place.get("geo"))
    messages = [
        {
            "role": "system",
            "content": (
                "Você pesquisa a bacia de um place comercial no Brasil. "
                "Foco: densidade, bairros, pessoas que moram na região e pontos principais. "
                "Não invente estatística. Se o número não tiver fonte, marque to_validate. "
                "Responda só JSON válido."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Place: {title} {code} — {city}. "
                f"Geo: {geo.get('lat')}, {geo.get('lng')}.\n"
                "Devolva JSON com: "
                "population_label, population_value, population_source, population_status, "
                "density_label, density_source, density_status, "
                "impacted_label, neighborhoods (lista), profile, notes, "
                "sources (lista de {title, url}), "
                "points (lista de {name, kind, note}) onde kind é "
                "bairro|densidade|pessoas|marco|mobilidade|terminal|halo."
            ),
        },
    ]
    try:
        response = chat_completion(
            messages,
            model=RESEARCH_MODEL,
            max_tokens=1600,
            temperature=0.15,
            timeout=90,
            response_format={"type": "json_object"},
        )
    except OpenRouterError as exc:
        raise ResearchError(str(exc) or "A pesquisa não respondeu.") from exc
    data = _json_content((response.get("message") or {}).get("content"))
    return {
        "model": response.get("model") or RESEARCH_MODEL,
        "usage": response.get("usage") or {},
        "catchment": {
            "population": {
                "label": text(data.get("population_label")),
                "value": data.get("population_value"),
                "source": text(data.get("population_source")),
                "source_status": text(data.get("population_status")) or "to_validate",
                "note": "População residente da bacia. Não é presença no terminal.",
            },
            "density": {
                "label": text(data.get("density_label")),
                "source": text(data.get("density_source")),
                "source_status": text(data.get("density_status")) or "to_validate",
                "note": "Densidade da bacia, não do sítio.",
            },
            "impacted": {
                "label": text(data.get("impacted_label")),
                "source_status": "estimate",
                "note": "Halo. Não some ao terminal.",
            },
            "neighborhoods": [text(x) for x in as_list(data.get("neighborhoods")) if text(x)],
            "profile": text(data.get("profile")),
        },
        "research": {
            "query": f"{title} {city} densidade bairros pessoas",
            "notes": text(data.get("notes")),
            "sources": as_list(data.get("sources")),
        },
        "suggested_points": [
            item
            for item in as_list(data.get("points"))
            if isinstance(item, dict) and text(item.get("name"))
        ],
    }


def review_place(place: dict) -> dict:
    return finalize_import(place, research=as_dict(place.get("research")))


def finalize_import(place: dict, *, research: dict | None = None) -> dict:
    """Fecha a importação com a família GPT-5: ficha, linha de venda e pontos."""
    payload = normalize_payload(place)
    research = as_dict(research or payload.get("research"))
    title = text(place.get("title"))
    city = text(place.get("city_label") or place.get("city"))
    code = text(place.get("code"))
    messages = [
        {
            "role": "system",
            "content": (
                "Você finaliza a ficha comercial de um place para venda de mídia. "
                "Quem lê o link público é agência ou cliente final que vai comprar. "
                "Números sem fonte viram to_validate. Estimativa de 4 semanas é anual÷13. "
                "Não some zonas. Halo não é presença no terminal. "
                "Densidade, bairros e pessoas são o núcleo. "
                "Não invente estatística. Responda só JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Place: {title} {code} — {city}.\n"
                "Devolva JSON com: "
                "subtitle (uma frase de venda para quem vai comprar presença aqui), "
                "catchment (mesmo formato, corrigido), "
                "points (lista de {name, kind, note} — terminal, bairros da bacia e marcos reais), "
                "review (texto curto do que fechou), "
                "changes (lista de frases).\n\n"
                f"catchment={json.dumps(payload.get('catchment'), ensure_ascii=False)}\n"
                f"research={json.dumps({'notes': research.get('notes'), 'sources': research.get('sources')}, ensure_ascii=False)}"
            ),
        },
    ]
    try:
        response = chat_completion(
            messages,
            model=FINALIZE_MODEL,
            max_tokens=1400,
            temperature=0.1,
            timeout=90,
            response_format={"type": "json_object"},
        )
    except OpenRouterError as exc:
        raise ResearchError(str(exc) or "A finalização não respondeu.") from exc
    data = _json_content((response.get("message") or {}).get("content"))
    points = [
        item
        for item in as_list(data.get("points"))
        if isinstance(item, dict) and text(item.get("name"))
    ]
    return {
        "model": response.get("model") or FINALIZE_MODEL,
        "usage": response.get("usage") or {},
        "subtitle": text(data.get("subtitle")),
        "catchment": as_dict(data.get("catchment")) or payload.get("catchment"),
        "points": points,
        "review": text(data.get("review")),
        "changes": [text(x) for x in as_list(data.get("changes")) if text(x)],
    }


def suggest_points(place: dict, raw_points: list | None = None) -> list[dict]:
    catchment = as_dict(place.get("catchment"))
    names = [text(x) for x in as_list(catchment.get("neighborhoods")) if text(x)]
    extras = []
    for item in raw_points or []:
        if isinstance(item, dict) and text(item.get("name")):
            extras.append(item)
        elif text(item):
            extras.append({"name": text(item), "kind": "marco"})
    geo = as_dict(place.get("geo"))
    title = text(place.get("title"))
    city = text(place.get("city_label") or place.get("city"))
    seeds = extras or [{"name": name, "kind": "bairro"} for name in names]
    if title and not any(text(item.get("name")).lower() == title.lower() for item in seeds):
        seeds.insert(0, {"name": title, "kind": "terminal", "note": "Sítio principal"})
    points = []
    seen = set()
    for item in seeds:
        name = text(item.get("name"))
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        kind = text(item.get("kind")).lower()
        if kind not in POINT_KINDS:
            kind = "bairro" if name in names else "marco"
        located = geocode_one(f"{name} {title} {city}".strip(), near=geo)
        if not located:
            continue
        points.append(
            {
                "id": re.sub(r"[^a-z0-9]+", "-", key).strip("-")[:32] or f"pt-{len(points)+1}",
                "name": name,
                "kind": kind,
                "lat": located["lat"],
                "lng": located["lng"],
                "source": "Nominatim + pesquisa da região",
                "note": text(item.get("note")),
            }
        )
    return points


def _json_content(raw: Any) -> dict:
    blob = raw
    if isinstance(raw, list):
        blob = "\n".join(text(part.get("text") if isinstance(part, dict) else part) for part in raw)
    text_blob = text(blob)
    if not text_blob:
        return {}
    match = re.search(r"\{.*\}", text_blob, re.S)
    if match:
        text_blob = match.group(0)
    try:
        data = json.loads(text_blob)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
