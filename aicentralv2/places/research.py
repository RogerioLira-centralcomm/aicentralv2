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
    try:
        rows = search_places(text(query), limit=5)
    except ResearchError:
        return None
    if not rows:
        return None
    if near is None or near.get("lat") is None or near.get("lng") is None:
        return rows[0]
    return min(rows, key=lambda item: _geo_distance(near, item))


def _geo_distance(origin: dict, item: dict) -> float:
    try:
        d_lat = float(item.get("lat")) - float(origin.get("lat"))
        d_lng = float(item.get("lng")) - float(origin.get("lng"))
    except (TypeError, ValueError):
        return float("inf")
    return d_lat * d_lat + d_lng * d_lng


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
                "bairro|densidade|pessoas|marco|mobilidade|terminal|embarque|premium|halo. "
                "Se for aeroporto: bacia é o recorte residencial (ilha, distritos ou municípios do corredor), "
                "não só o bairro do sítio. Inclua terminal, embarque, internacional se houver fonte, "
                "acesso/mobilidade e halo de bairro. Sem pista, sem base militar, sem acidente geográfico."
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
        )
    except OpenRouterError as exc:
        raise ResearchError(str(exc) or "A pesquisa não respondeu.") from exc
    data = _json_content((response.get("message") or {}).get("content"))
    profile = data.get("profile")
    if isinstance(profile, dict):
        profile = text(profile.get("urban_context") or profile.get("profile") or profile.get("summary"))
    else:
        profile = text(profile)
    notes = data.get("notes")
    if isinstance(notes, list):
        notes = " ".join(text(item) for item in notes if text(item))
    else:
        notes = text(notes)
    neighborhoods = []
    for item in as_list(data.get("neighborhoods")):
        if isinstance(item, dict):
            name = text(item.get("name") or item.get("title"))
        else:
            name = text(item)
        if name:
            neighborhoods.append(name)
    sources = []
    for item in as_list(data.get("sources")):
        if isinstance(item, dict) and (text(item.get("title")) or text(item.get("url"))):
            sources.append({"title": text(item.get("title")), "url": text(item.get("url"))})
        elif text(item):
            sources.append({"title": text(item), "url": ""})
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
            "neighborhoods": neighborhoods,
            "profile": profile,
        },
        "research": {
            "query": f"{title} {city} densidade bairros pessoas",
            "notes": notes,
            "sources": sources,
        },
        "suggested_points": [
            item
            for item in as_list(data.get("points"))
            if isinstance(item, dict) and text(item.get("name"))
        ],
    }


def refine_generated_fiche(place: dict, *, draft: dict | None = None) -> dict:
    """Refina pesquisa + finalize: ficha comercial, sem inventar número oficial."""
    payload = normalize_payload(place)
    draft = as_dict(draft)
    locked = {
        "title": text(place.get("title")),
        "code": text(place.get("code")),
        "city": text(place.get("city_label") or place.get("city")),
        "place_type": text(place.get("place_type") or "aeroporto"),
        "operator": text(place.get("operator")),
        "metrics": payload.get("metrics"),
        "catchment": payload.get("catchment"),
        "draft_subtitle": text(place.get("subtitle") or draft.get("subtitle")),
        "draft_points": draft.get("points") or payload.get("points") or [],
        "draft_review": text(draft.get("review") or as_dict(payload.get("research")).get("review")),
        "research_notes": text(as_dict(payload.get("research")).get("notes")),
        "research_sources": as_dict(payload.get("research")).get("sources") or [],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "Você refina a ficha gerada de um place da CentralComm. "
                "Quem lê compra o raio no celular, não outdoor nem proposta. "
                "Frase curta, voz ativa, português do Brasil. "
                "Proibido: geofence, proposta, HTML5, push, banner, interstitial, "
                "out-of-home, OOH, exposição estratégica, posicionamento de mídia, "
                "viajante nacional, executivos, segmento premium, base militar, pista, baía como ponto. "
                "Aeroporto precisa de: terminal, embarque, internacional se o lugar tiver voo para fora, "
                "mobilidade (pátio ou acesso) e halo de bairro com nome real. "
                "Públicos começam com Quem. Formatos só: Display no app, Vídeo no saguão, "
                "Vídeo vertical, Portais, 7 e 15 dias. "
                "Não invente número oficial. Não some raios. Halo não é o terminal. "
                "Responda só JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "Devolva JSON: subtitle, operator, catchment_profile, "
                "neighborhoods (lista curta de nomes reais), "
                "offer_lead, offer_lines (3 {title,body}), methodology_body, "
                "audiences (6 pares {title,body}), "
                "points (lista de {name, kind, note, commercial} — kind: "
                "terminal|embarque|premium|mobilidade|halo).\n\n"
                f"travado={json.dumps(locked, ensure_ascii=False)}"
            ),
        },
    ]
    try:
        response = chat_completion(
            messages,
            model=FINALIZE_MODEL,
            max_tokens=4000,
            temperature=0.2,
            timeout=90,
            response_format={"type": "json_object"},
        )
    except OpenRouterError as exc:
        raise ResearchError(str(exc) or "O refine da ficha não respondeu.") from exc
    data = _json_content((response.get("message") or {}).get("content"))
    points = [
        item
        for item in as_list(data.get("points"))
        if isinstance(item, dict) and text(item.get("name"))
    ]
    audiences = []
    for item in as_list(data.get("audiences")):
        if isinstance(item, dict) and text(item.get("title")):
            audiences.append([text(item.get("title")), text(item.get("body"))])
        elif isinstance(item, list) and len(item) >= 2:
            audiences.append([text(item[0]), text(item[1])])
    return {
        "model": response.get("model") or FINALIZE_MODEL,
        "usage": response.get("usage") or {},
        "subtitle": text(data.get("subtitle")),
        "operator": text(data.get("operator")),
        "catchment_profile": text(data.get("catchment_profile")),
        "neighborhoods": [text(x) for x in as_list(data.get("neighborhoods")) if text(x)][:6],
        "offer": {
            "lead": text(data.get("offer_lead")),
            "lines": [
                {"title": text(item.get("title")), "body": text(item.get("body"))}
                for item in as_list(data.get("offer_lines"))
                if isinstance(item, dict) and text(item.get("title"))
            ][:3],
        },
        "methodology_body": text(data.get("methodology_body")),
        "audiences": audiences[:6],
        "points": points,
    }


def polish_one_page(place: dict) -> dict:
    """Reescreve a one-page sem mexer em número oficial, raio ou alcance."""
    payload = normalize_payload(place)
    title = text(place.get("title"))
    city = text(place.get("city_label") or place.get("city"))
    code = text(place.get("code"))
    locked = {
        "title": title,
        "code": code,
        "city": city,
        "passengers": as_dict(as_dict(payload.get("metrics")).get("passengers")).get("label"),
        "addressable": as_dict(as_dict(payload.get("metrics")).get("addressable")).get("label"),
        "catchment_population": as_dict(as_dict(payload.get("catchment")).get("population")).get("label"),
        "points": [
            {
                "id": text(item.get("id")),
                "name": text(item.get("name")),
                "kind": text(item.get("kind")),
                "radius": text(item.get("radius_label")),
                "reach": text(item.get("reach")),
                "reach_status": text(item.get("reach_status")),
                "commercial": text(item.get("commercial")),
                "formats": item.get("formats") or [],
                "audiences": item.get("audiences") or [],
            }
            for item in as_list(payload.get("points"))
        ],
        "draft": {
            "subtitle": text(place.get("subtitle")),
            "offer": payload.get("offer"),
            "catchment_profile": text(as_dict(payload.get("catchment")).get("profile")),
            "methodology_body": text(as_dict(payload.get("methodology")).get("body")),
        },
    }
    messages = [
        {
            "role": "system",
            "content": (
                "Você é o redator da CentralComm. Melhora o rascunho da one-page. "
                "Quem lê compra o raio no celular. Frase curta, voz ativa, português do Brasil. "
                "Proibido: geofence, proposta, HTML5, push, banner, interstitial, ativa campanha, "
                "presença móvel, viajante nacional, executivos, segmento premium. "
                "Formatos só do tipo: Display no app, Vídeo no saguão, Vídeo vertical, Portais, 7 e 15 dias. "
                "Públicos começam com Quem. Não invente número. Não some raios. "
                "O rascunho já é bom — deixe mais concreto e local. Responda só JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "Devolva JSON: subtitle, offer_lead, offer_lines (3 {title,body}), "
                "points ({id, commercial, formats, audiences}), catchment_profile, methodology_body.\n\n"
                f"travado={json.dumps(locked, ensure_ascii=False)}"
            ),
        },
    ]
    try:
        response = chat_completion(
            messages,
            model=FINALIZE_MODEL,
            max_tokens=4000,
            temperature=0.2,
            timeout=90,
            response_format={"type": "json_object"},
        )
    except OpenRouterError as exc:
        raise ResearchError(str(exc) or "A polidez da one-page não respondeu.") from exc
    data = _json_content((response.get("message") or {}).get("content"))
    points = []
    for item in as_list(data.get("points")):
        if not isinstance(item, dict) or not text(item.get("id")):
            continue
        points.append(
            {
                "id": text(item.get("id")),
                "commercial": text(item.get("commercial")),
                "formats": [text(x) for x in as_list(item.get("formats")) if text(x)][:3],
                "audiences": [text(x) for x in as_list(item.get("audiences")) if text(x)][:2],
            }
        )
    return {
        "model": response.get("model") or FINALIZE_MODEL,
        "usage": response.get("usage") or {},
        "subtitle": text(data.get("subtitle")),
        "offer": {
            "lead": text(data.get("offer_lead")),
            "lines": [
                {"title": text(item.get("title")), "body": text(item.get("body"))}
                for item in as_list(data.get("offer_lines"))
                if isinstance(item, dict) and text(item.get("title"))
            ][:3],
        },
        "points": points,
        "catchment_profile": text(data.get("catchment_profile")),
        "methodology_body": text(data.get("methodology_body")),
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
            max_tokens=4000,
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
        row = {
            "id": re.sub(r"[^a-z0-9]+", "-", key).strip("-")[:32] or f"pt-{len(points)+1}",
            "name": name,
            "kind": kind,
            "note": text(item.get("note")),
        }
        if located:
            row["lat"] = located["lat"]
            row["lng"] = located["lng"]
            row["source"] = "Nominatim + pesquisa da região"
        points.append(row)
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
