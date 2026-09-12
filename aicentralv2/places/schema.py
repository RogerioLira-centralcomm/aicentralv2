"""Normalização do payload de um place."""

from __future__ import annotations

from typing import Any

from .brand import zone_color

PLACE_TYPES = ("aeroporto", "shopping", "evento")
CITIES = ("bh", "sp", "rj")
STATUSES = ("draft", "published", "archived", "mapping")
SOURCE_STATUSES = ("official", "estimate", "to_validate")
ZONE_TYPES = ("CORE", "DEPARTURES", "PREMIUM", "MOBILITY", "HALO")
POINT_KINDS = ("bairro", "densidade", "pessoas", "marco", "mobilidade", "terminal", "halo")
POINT_LABELS = {
    "bairro": "Bairro",
    "densidade": "Densidade",
    "pessoas": "Pessoas",
    "marco": "Marco",
    "mobilidade": "Mobilidade",
    "terminal": "Terminal",
    "halo": "Halo",
}

CITY_LABELS = {"bh": "Belo Horizonte", "sp": "São Paulo", "rj": "Rio de Janeiro"}
TYPE_LABELS = {"aeroporto": "Aeroporto", "shopping": "Shopping", "evento": "Área de evento"}
STATUS_LABELS = {
    "draft": "Rascunho",
    "published": "Publicado",
    "archived": "Arquivado",
    "mapping": "A mapear",
}
SOURCE_LABELS = {
    "official": "Dado oficial",
    "estimate": "Estimativa",
    "to_validate": "A validar",
}


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return ""
    return str(value).strip()


def as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def normalize_choice(value: Any, options: tuple[str, ...], default: str) -> str:
    raw = text(value).lower()
    return raw if raw in options else default


def normalize_source_status(value: Any, default: str = "estimate") -> str:
    raw = text(value).lower()
    return raw if raw in SOURCE_STATUSES else default


def metric_stat(
    value: Any = None,
    label: str = "",
    *,
    year: Any = None,
    source: str = "",
    source_status: str = "estimate",
    note: str = "",
) -> dict:
    number = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = value
    elif text(value).replace(".", "", 1).isdigit():
        number = int(float(value))
    return {
        "value": number,
        "label": text(label),
        "year": int(year) if str(year or "").isdigit() else None,
        "source": text(source),
        "source_status": normalize_source_status(source_status),
        "note": text(note),
    }


def normalize_metric(value: Any) -> dict:
    data = as_dict(value)
    return metric_stat(
        data.get("value"),
        data.get("label") or "",
        year=data.get("year"),
        source=data.get("source") or "",
        source_status=data.get("source_status") or "estimate",
        note=data.get("note") or "",
    )


def normalize_audience(item: Any) -> dict:
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return {"title": text(item[0]), "body": text(item[1])}
    data = as_dict(item)
    return {"title": text(data.get("title") or data.get("name")), "body": text(data.get("body") or data.get("description"))}


def normalize_zone(item: Any) -> dict:
    data = as_dict(item)
    zone_type = text(data.get("type")).upper()
    if zone_type not in ZONE_TYPES:
        zone_type = "CORE"
    return {
        "id": text(data.get("id")),
        "type": zone_type,
        "name": text(data.get("name")),
        "color": text(data.get("color")) or zone_color(zone_type),
        "radius": text(data.get("radius")),
        "reach": text(data.get("reach")),
        "reach_status": normalize_source_status(data.get("reach_status"), "estimate"),
        "description": text(data.get("description")),
        "formats": [text(x) for x in as_list(data.get("formats")) if text(x)],
        "audiences": [text(x) for x in as_list(data.get("audiences")) if text(x)],
        "commercial": text(data.get("commercial")),
        "polygon": text(data.get("polygon")),
        "geometry": normalize_geometry(data.get("geometry")),
    }


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = text(value).replace(",", ".")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def normalize_geo(value: Any) -> dict:
    data = as_dict(value)
    lat = _float(data.get("lat"))
    lng = _float(data.get("lng"))
    zoom = _float(data.get("zoom"))
    return {
        "lat": lat,
        "lng": lng,
        "zoom": int(zoom) if zoom else (15 if lat is not None and lng is not None else None),
    }


def normalize_geometry(value: Any) -> dict:
    data = as_dict(value)
    if text(data.get("type")).lower() != "polygon":
        return {}
    rings = as_list(data.get("coordinates"))
    cleaned = []
    for ring in rings:
        points = []
        for pair in as_list(ring):
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            lng = _float(pair[0])
            lat = _float(pair[1])
            if lat is None or lng is None:
                continue
            points.append([lng, lat])
        if len(points) >= 3:
            cleaned.append(points)
    if not cleaned:
        return {}
    return {"type": "Polygon", "coordinates": cleaned}


def normalize_point(item: Any) -> dict:
    data = as_dict(item)
    kind = normalize_choice(data.get("kind"), POINT_KINDS, "marco")
    return {
        "id": text(data.get("id")),
        "name": text(data.get("name")),
        "kind": kind,
        "kind_label": POINT_LABELS.get(kind, "Marco"),
        "lat": _float(data.get("lat")),
        "lng": _float(data.get("lng")),
        "source": text(data.get("source")),
        "note": text(data.get("note")),
        "image_url": text(data.get("image_url")),
    }


def normalize_research(value: Any) -> dict:
    data = as_dict(value)
    sources = []
    for item in as_list(data.get("sources")):
        if isinstance(item, dict):
            title = text(item.get("title") or item.get("name"))
            url = text(item.get("url"))
            if title or url:
                sources.append({"title": title, "url": url})
        elif text(item):
            sources.append({"title": text(item), "url": ""})
    return {
        "query": text(data.get("query")),
        "notes": text(data.get("notes")),
        "sources": sources,
        "reviewed_at": text(data.get("reviewed_at")),
        "review": text(data.get("review")),
    }


def normalize_catchment(value: Any) -> dict:
    data = as_dict(value)
    return {
        "population": normalize_metric(data.get("population")),
        "density": normalize_metric(data.get("density")),
        "impacted": normalize_metric(data.get("impacted")),
        "neighborhoods": [text(x) for x in as_list(data.get("neighborhoods")) if text(x)],
        "profile": text(data.get("profile")),
    }


def normalize_payload(value: Any) -> dict:
    data = as_dict(value)
    metrics = as_dict(data.get("metrics"))
    media = as_dict(data.get("media"))
    methodology = as_dict(data.get("methodology"))
    return {
        "metrics": {
            "passengers": normalize_metric(metrics.get("passengers")),
            "four_weeks": normalize_metric(metrics.get("four_weeks")),
            "impacted": normalize_metric(metrics.get("impacted") or metrics.get("four_weeks")),
        },
        "geo": normalize_geo(data.get("geo")),
        "points": [item for item in (normalize_point(raw) for raw in as_list(data.get("points"))) if item["name"] and item["lat"] is not None],
        "research": normalize_research(data.get("research")),
        "catchment": normalize_catchment(data.get("catchment")),
        "zones": [normalize_zone(item) for item in as_list(data.get("zones"))],
        "audiences": [normalize_audience(item) for item in as_list(data.get("audiences")) if normalize_audience(item)["title"]],
        "media": {
            "hero_url": text(media.get("hero_url")),
            "map_url": text(media.get("map_url")),
            "og_url": text(media.get("og_url")),
        },
        "methodology": {
            "title": text(methodology.get("title")) or "Não vendemos um círculo no mapa.",
            "body": text(methodology.get("body"))
            or (
                "As zonas são contextos funcionais. Passageiros físicos, devices observados, "
                "devices elegíveis e usuários impactados são métricas diferentes. "
                "Não some os alcances das zonas."
            ),
            "steps": [text(x) for x in as_list(methodology.get("steps"))]
            or ["Presença física", "Device observado", "Audience match", "Impacto real"],
            "trust": text(methodology.get("trust"))
            or (
                "Terminal, circulação e acessos tratados como áreas funcionais. "
                "O polígono final de mídia deve ser calibrado na plataforma de location data."
            ),
        },
    }


def sum_zone_reaches(_zones: list) -> None:
    """Proibido: alcances de zona não se somam. Mantido para o teste documentar a regra."""
    raise ValueError("Não some os alcances das zonas. Uma pessoa pode atravessar várias áreas.")


def empty_payload() -> dict:
    return normalize_payload({})


def public_view(row: dict) -> dict:
    payload = normalize_payload(row.get("payload"))
    slug = text(row.get("slug"))
    return {
        "id": row.get("id"),
        "slug": slug,
        "place_type": normalize_choice(row.get("place_type"), PLACE_TYPES, "aeroporto"),
        "city": normalize_choice(row.get("city"), CITIES, "bh"),
        "status": normalize_choice(row.get("status"), STATUSES, "draft"),
        "title": text(row.get("title")),
        "code": text(row.get("code")),
        "operator": text(row.get("operator")),
        "subtitle": text(row.get("subtitle")),
        "city_label": CITY_LABELS.get(normalize_choice(row.get("city"), CITIES, "bh"), ""),
        "type_label": TYPE_LABELS.get(normalize_choice(row.get("place_type"), PLACE_TYPES, "aeroporto"), ""),
        "status_label": STATUS_LABELS.get(normalize_choice(row.get("status"), STATUSES, "draft"), ""),
        **payload,
    }
