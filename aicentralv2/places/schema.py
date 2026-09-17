"""Normalização do payload de um place."""

from __future__ import annotations

from typing import Any

from .brand import TYPE_PIN_COLORS, zone_color

PLACE_TYPES = ("aeroporto", "shopping", "evento")
CITIES = ("bh", "sp", "rj")
STATUSES = ("draft", "published", "archived", "mapping")
SOURCE_STATUSES = ("official", "estimate", "to_validate")
ZONE_TYPES = ("CORE", "DEPARTURES", "PREMIUM", "MOBILITY", "HALO")
POINT_KINDS = (
    "bairro",
    "densidade",
    "pessoas",
    "marco",
    "mobilidade",
    "terminal",
    "embarque",
    "premium",
    "halo",
)
POINT_LABELS = {
    "bairro": "Bairro",
    "densidade": "Densidade",
    "pessoas": "Pessoas",
    "marco": "Marco",
    "mobilidade": "Mobilidade",
    "terminal": "Terminal",
    "embarque": "Embarque",
    "premium": "Premium",
    "halo": "Halo",
}
POINT_SCOPES = ("internal", "external")
SCOPE_LABELS = {"internal": "No sítio", "external": "Halo"}
INTERNAL_KINDS = ("terminal", "embarque", "premium", "mobilidade", "marco", "pessoas")
EXTERNAL_KINDS = ("halo", "bairro", "densidade")
POINT_RADIUS = {
    "terminal": 300,
    "embarque": 250,
    "premium": 200,
    "mobilidade": 350,
    "halo": 1000,
    "bairro": 800,
    "densidade": 900,
    "pessoas": 700,
    "marco": 400,
}

CITY_LABELS = {"bh": "Belo Horizonte", "sp": "São Paulo", "rj": "Rio de Janeiro"}
TYPE_LABELS = {"aeroporto": "Aeroporto", "shopping": "Shopping", "evento": "Parques e eventos"}
TRAFFIC_LABELS = {
    "aeroporto": "No avião, 2025",
    "shopping": "No shopping, 2025",
    "evento": "No lugar, 2025",
}
INDEX_COLUMNS = (
    {"id": "aeroporto", "title": "Aeroportos", "types": ("aeroporto",)},
    {"id": "shopping", "title": "Shoppings", "types": ("shopping",)},
    {"id": "evento", "title": "Parques e eventos", "types": ("evento",)},
)
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
ENRICH_FORMATS = (
    "Display no app",
    "Vídeo no saguão",
    "Vídeo vertical",
    "Portais",
    "7 e 15 dias",
)
INVENTORY_MAX_ITEMS = 15


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return ""
    return str(value).strip()


def hex_color(value: Any, fallback: str = "#167A3A") -> str:
    candidate = text(value)
    if len(candidate) == 7 and candidate[0] == "#" and all(char in "0123456789abcdefABCDEF" for char in candidate[1:]):
        return candidate
    return fallback


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


def normalize_inventory_item(item: Any) -> dict:
    if isinstance(item, (list, tuple)) and item:
        return normalize_inventory_item({"name": item[0], "why": item[1] if len(item) > 1 else ""})
    if not isinstance(item, dict):
        name = text(item)
        return {"name": name, "why": "", "confidence": "estimate"} if name else {}
    data = as_dict(item)
    name = text(data.get("name") or data.get("title"))
    if not name:
        return {}
    return {
        "name": name,
        "why": text(data.get("why") or data.get("note") or data.get("body")),
        "confidence": normalize_source_status(data.get("confidence") or data.get("source_status"), "estimate"),
    }


def normalize_inventory_items(value: Any, *, limit: int = INVENTORY_MAX_ITEMS) -> list:
    items = []
    seen = set()
    for raw in as_list(value):
        item = normalize_inventory_item(raw)
        key = text(item.get("name")).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) >= limit:
            break
    return items


def normalize_inventory(value: Any) -> dict:
    data = as_dict(value)
    return {
        "lead": text(data.get("lead")),
        "reviewed_at": text(data.get("reviewed_at")),
        "model": text(data.get("model")),
        "notes": text(data.get("notes")),
    }


def normalize_channel_ranking(value: Any) -> list[dict]:
    rows = []
    seen = set()
    for raw in as_list(value):
        data = as_dict(raw)
        name = text(data.get("name") or data.get("title"))
        key = name.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "rank": len(rows) + 1,
                "name": name,
                "kind": text(data.get("kind")) or "app/site",
                "why": text(data.get("why") or data.get("note")),
                "confidence": normalize_source_status(data.get("confidence"), "estimate"),
                "short": text(data.get("short"))[:3],
                "color": hex_color(data.get("color")),
                "url": text(data.get("url")) if text(data.get("url")).startswith("https://") else "",
                "icon": text(data.get("icon")) if text(data.get("icon")).startswith("images/") else "",
            }
        )
        if len(rows) >= 15:
            break
    return rows


def normalize_demographics(value: Any) -> dict:
    data = as_dict(value)
    return {key: text(data.get(key)) for key in ("age", "gender", "income", "origin")}


def normalize_audience_plan(value: Any) -> dict:
    data = as_dict(value)
    steps = []
    for raw in as_list(data.get("steps"))[:4]:
        row = as_dict(raw)
        if text(row.get("title")):
            steps.append({"title": text(row.get("title")), "body": text(row.get("body"))})
    return {
        "window": text(data.get("window")),
        "title": text(data.get("title")),
        "steps": steps,
        "reuse_note": text(data.get("reuse_note")),
    }


def infer_point_scope(kind: str, value: Any = None) -> str:
    raw = text(value).lower()
    if raw in POINT_SCOPES:
        return raw
    if kind in EXTERNAL_KINDS:
        return "external"
    if kind in INTERNAL_KINDS:
        return "internal"
    return "internal"


def sort_place_points(points: list) -> list:
    internals = [item for item in points if text(item.get("scope")) != "external"]
    externals = [item for item in points if text(item.get("scope")) == "external"]
    return internals + externals


def normalize_point(item: Any) -> dict:
    data = as_dict(item)
    kind = normalize_choice(data.get("kind"), POINT_KINDS, "marco")
    scope = infer_point_scope(kind, data.get("scope"))
    radius_m = _float(data.get("radius_m"))
    radius_m = int(radius_m) if radius_m else POINT_RADIUS.get(kind, 400)
    return {
        "id": text(data.get("id")),
        "name": text(data.get("name")),
        "kind": kind,
        "kind_label": POINT_LABELS.get(kind, "Marco"),
        "scope": scope,
        "scope_label": SCOPE_LABELS[scope],
        "lat": _float(data.get("lat")),
        "lng": _float(data.get("lng")),
        "radius_m": radius_m,
        "radius_label": text(data.get("radius_label")) or f"{radius_m} m",
        "reach": text(data.get("reach")),
        "reach_status": normalize_source_status(data.get("reach_status"), "estimate"),
        "formats": [text(x) for x in as_list(data.get("formats")) if text(x)],
        "audiences": [text(x) for x in as_list(data.get("audiences")) if text(x)],
        "apps": normalize_inventory_items(data.get("apps")),
        "portals": normalize_inventory_items(data.get("portals")),
        "commercial": text(data.get("commercial")),
        "defense": text(data.get("defense") or data.get("commercial")),
        "investment": text(data.get("investment")),
        "color": text(data.get("color")) or zone_color(
            {"terminal": "CORE", "embarque": "DEPARTURES", "premium": "PREMIUM", "mobilidade": "MOBILITY", "halo": "HALO"}.get(kind, "CORE")
        ),
        "source": text(data.get("source")),
        "note": text(data.get("note")),
        "image_url": text(data.get("image_url")),
        "inside": [text(x) for x in as_list(data.get("inside")) if text(x)],
        "target_audience": [text(x) for x in as_list(data.get("target_audience")) if text(x)],
    }


def normalize_weekly_movement(value: Any) -> dict:
    data = as_dict(value)
    values = []
    for raw in as_list(data.get("values"))[:7]:
        number = _float(raw)
        values.append(max(0, min(100, round(number))) if number is not None else None)
    values.extend([None] * (7 - len(values)))
    return {
        "values": values,
        "source": text(data.get("source")),
        "source_status": normalize_source_status(data.get("source_status"), "to_validate"),
        "note": text(data.get("note")),
    }


def normalize_planning(value: Any) -> dict:
    data = as_dict(value)
    return {
        "objective": text(data.get("objective")),
        "channels": [text(item) for item in as_list(data.get("channels")) if text(item)],
        "models": [text(item) for item in as_list(data.get("models")) if text(item)],
        "source_status": normalize_source_status(data.get("source_status"), "to_validate"),
        "note": text(data.get("note")),
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


def normalize_media(value: Any) -> dict:
    data = as_dict(value)
    images = []
    for raw in as_list(data.get("images")):
        item = as_dict(raw)
        url = text(item.get("url") or item.get("image_url"))
        if not url:
            continue
        images.append(
            {
                "id": text(item.get("id")),
                "role": text(item.get("role")) or "point",
                "url": url,
            }
        )
    visual_refs = []
    for raw in as_list(data.get("visual_refs")):
        item = as_dict(raw)
        url = text(item.get("url"))
        if not url:
            continue
        visual_refs.append(
            {
                "kind": text(item.get("kind")) or "hero",
                "url": url,
                "title": text(item.get("title")),
                "query": text(item.get("query")),
            }
        )
    gallery = []
    seen = set()
    for raw in as_list(data.get("gallery")):
        item = as_dict(raw)
        url = text(item.get("url") or item.get("source_url"))
        if not url:
            continue
        gid = text(item.get("id")) or url
        if gid in seen:
            continue
        seen.add(gid)
        gallery.append(
            {
                "id": gid,
                "kind": text(item.get("kind")) or "hero",
                "point_id": text(item.get("point_id")),
                "url": url,
                "source_url": text(item.get("source_url")) or url,
                "page_url": text(item.get("page_url")),
                "title": text(item.get("title")),
                "query": text(item.get("query")),
                "selected": bool(item.get("selected")),
                "review_status": text(item.get("review_status")) or "pending",
                "review_note": text(item.get("review_note")),
            }
        )
    return {
        "hero_url": text(data.get("hero_url")),
        "map_url": text(data.get("map_url")),
        "og_url": text(data.get("og_url")),
        "video_url": text(data.get("video_url")),
        "image_model": text(data.get("image_model")),
        "image_resolution": text(data.get("image_resolution")),
        "images": images,
        "visual_refs": visual_refs,
        "gallery": gallery,
    }


def normalize_pipeline(value: Any) -> dict:
    data = as_dict(value)
    models = as_dict(data.get("models"))
    return {
        "steps": [text(item) for item in as_list(data.get("steps")) if text(item)],
        "models": {text(key): text(value) for key, value in models.items() if text(key) and text(value)},
        "warnings": [text(item) for item in as_list(data.get("warnings")) if text(item)],
        "unlocated": [text(item) for item in as_list(data.get("unlocated")) if text(item)],
    }


def normalize_offer(value: Any) -> dict:
    data = as_dict(value)
    lines = []
    for raw in as_list(data.get("lines") or data.get("items")):
        row = as_dict(raw)
        title = text(row.get("title"))
        body = text(row.get("body"))
        if title:
            lines.append({"title": title, "body": body})
    return {"lead": text(data.get("lead")), "lines": lines}


def normalize_defense(value: Any, *, fallback: str = "") -> dict:
    data = as_dict(value)
    lead = text(data.get("lead"))
    body = text(data.get("body") or data.get("text"))
    if not lead:
        lead = fallback
    return {"lead": lead, "body": body}


def infer_place_investment(addressable_value: Any) -> dict:
    value = addressable_value if isinstance(addressable_value, (int, float)) and not isinstance(addressable_value, bool) else 0
    if value >= 250_000:
        label, mid = "R$ 55–95 mil", 75_000
    elif value >= 150_000:
        label, mid = "R$ 40–70 mil", 55_000
    elif value >= 80_000:
        label, mid = "R$ 28–48 mil", 38_000
    elif value >= 40_000:
        label, mid = "R$ 18–32 mil", 25_000
    else:
        label, mid = "R$ 12–22 mil", 17_000
    return metric_stat(
        mid,
        label,
        source="Ordem de grandeza para o recorte no celular, 4 semanas",
        source_status="to_validate",
        note="Não é cotação. Serve para a defesa de venda do ponto.",
    )


def infer_point_investment(kind: str, place_label: str = "") -> str:
    if kind in ("halo", "bairro"):
        return "R$ 10–18 mil"
    if kind in ("pessoas", "mobilidade", "embarque"):
        return "R$ 14–26 mil"
    if kind == "premium":
        return "R$ 18–32 mil"
    return text(place_label) or "R$ 18–32 mil"


def usage_cost_usd(usage: Any) -> float:
    data = as_dict(usage)
    for key in ("cost", "total_cost", "cost_usd", "usd"):
        value = data.get(key)
        try:
            if value is not None:
                return max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return 0.0


def format_usd(value: Any) -> str:
    amount = _float(value) or 0.0
    if amount <= 0:
        return "—"
    formatted = f"{amount:,.2f}"
    return "US$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def normalize_cost_entry(item: Any) -> dict:
    data = as_dict(item)
    return {
        "step": text(data.get("step")),
        "model": text(data.get("model")),
        "usd": usage_cost_usd(data) or (_float(data.get("usd")) or 0.0),
        "at": text(data.get("at")),
        "label": text(data.get("label")),
    }


def normalize_costs(value: Any) -> dict:
    data = as_dict(value)
    entries = [
        item
        for item in (normalize_cost_entry(raw) for raw in as_list(data.get("entries")))
        if item["step"]
    ]
    total = round(sum(item["usd"] for item in entries), 4)
    return {"entries": entries, "total_usd": total, "label": format_usd(total)}


DEFAULT_METHODOLOGY_BODY = (
    "Passageiros da ANAC não são o que a campanha compra. "
    "O número do ponto é quem dá para alcançar neste raio, no celular, em 4 semanas. "
    "Os raios não se somam."
)


def normalize_payload(value: Any) -> dict:
    data = as_dict(value)
    metrics = as_dict(data.get("metrics"))
    media = as_dict(data.get("media"))
    methodology = as_dict(data.get("methodology"))
    offer = normalize_offer(data.get("offer"))
    addressable = normalize_metric(metrics.get("addressable"))
    raw_investment = as_dict(data.get("investment") or metrics.get("investment"))
    investment = normalize_metric(raw_investment) if text(raw_investment.get("label")) or raw_investment.get("value") is not None else infer_place_investment(addressable.get("value"))
    points = sort_place_points(
        [item for item in (normalize_point(raw) for raw in as_list(data.get("points"))) if item["name"]]
    )
    for point in points:
        if not text(point.get("investment")):
            point["investment"] = infer_point_investment(point.get("kind"), investment.get("label"))
        if not text(point.get("defense")):
            point["defense"] = text(point.get("commercial"))
    return {
        "metrics": {
            "passengers": normalize_metric(metrics.get("passengers")),
            "four_weeks": normalize_metric(metrics.get("four_weeks")),
            "addressable": addressable,
            "impacted": normalize_metric(metrics.get("impacted") or metrics.get("four_weeks")),
        },
        "geo": normalize_geo(data.get("geo")),
        "points": points,
        "research": normalize_research(data.get("research")),
        "catchment": normalize_catchment(data.get("catchment")),
        "zones": [normalize_zone(item) for item in as_list(data.get("zones"))],
        "audiences": [normalize_audience(item) for item in as_list(data.get("audiences")) if normalize_audience(item)["title"]],
        "target_audience": [text(x) for x in as_list(data.get("target_audience")) if text(x)],
        "income": normalize_metric(data.get("income")),
        "weekly_movement": normalize_weekly_movement(data.get("weekly_movement")),
        "planning": normalize_planning(data.get("planning")),
        "media": normalize_media(media),
        "pipeline": normalize_pipeline(data.get("pipeline")),
        "offer": offer,
        "defense": normalize_defense(data.get("defense")),
        "investment": investment,
        "inventory": normalize_inventory(data.get("inventory")),
        "channel_ranking": normalize_channel_ranking(data.get("channel_ranking")),
        "demographics": normalize_demographics(data.get("demographics")),
        "audience_plan": normalize_audience_plan(data.get("audience_plan")),
        "costs": normalize_costs(data.get("costs")),
        "methodology": {
            "title": text(methodology.get("title")) or "Como o número é feito",
            "body": text(methodology.get("body")) or DEFAULT_METHODOLOGY_BODY,
            "steps": [text(x) for x in as_list(methodology.get("steps")) if text(x)],
            "trust": text(methodology.get("trust")),
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
    place_type = normalize_choice(row.get("place_type"), PLACE_TYPES, "aeroporto")
    city = normalize_choice(row.get("city"), CITIES, "bh")
    from .audience import enrich_public_payload

    payload = normalize_payload(
        enrich_public_payload(
            payload,
            place_type=place_type,
            slug=slug,
            city_label=CITY_LABELS.get(city, ""),
        )
    )
    return {
        "id": row.get("id"),
        "slug": slug,
        "place_type": place_type,
        "city": city,
        "status": normalize_choice(row.get("status"), STATUSES, "draft"),
        "title": text(row.get("title")),
        "code": text(row.get("code")),
        "operator": text(row.get("operator")),
        "subtitle": text(row.get("subtitle")),
        "city_label": CITY_LABELS.get(city, ""),
        "type_label": TYPE_LABELS.get(place_type, ""),
        "status_label": STATUS_LABELS.get(normalize_choice(row.get("status"), STATUSES, "draft"), ""),
        "traffic_label": TRAFFIC_LABELS.get(place_type, TRAFFIC_LABELS["aeroporto"]),
        **payload,
    }


def directory_card(item: dict) -> dict:
    media = as_dict(item.get("media"))
    metrics = as_dict(item.get("metrics"))
    addressable = as_dict(metrics.get("addressable"))
    passengers = as_dict(metrics.get("passengers"))
    geo = as_dict(item.get("geo"))
    place_type = normalize_choice(item.get("place_type"), PLACE_TYPES, "aeroporto")
    slug = text(item.get("slug"))
    return {
        "slug": slug,
        "title": text(item.get("title")),
        "code": text(item.get("code")),
        "subtitle": text(item.get("subtitle")),
        "place_type": place_type,
        "type_label": TYPE_LABELS.get(place_type, ""),
        "traffic_label": TRAFFIC_LABELS.get(place_type, TRAFFIC_LABELS["aeroporto"]),
        "city": normalize_choice(item.get("city"), CITIES, "bh"),
        "city_label": text(item.get("city_label")) or CITY_LABELS.get(normalize_choice(item.get("city"), CITIES, "bh"), ""),
        "hero_url": text(media.get("hero_url")),
        "reach": text(addressable.get("label")),
        "passengers": text(passengers.get("label")),
        "lat": geo.get("lat"),
        "lng": geo.get("lng"),
        "color": TYPE_PIN_COLORS.get(place_type, TYPE_PIN_COLORS["aeroporto"]),
        "href": f"/places/p/{slug}" if slug else "",
    }


def featured_card(cards: list) -> dict:
    rows = [as_dict(item) for item in cards if text(as_dict(item).get("slug"))]
    for slug in ("confins",):
        for item in rows:
            if text(item.get("slug")) == slug:
                return item
    for item in rows:
        if text(item.get("hero_url")):
            return item
    return rows[0] if rows else {}


def match_directory(card: dict, q: str = "", tipo: str = "") -> bool:
    item = as_dict(card)
    wanted = text(tipo).lower()
    if wanted and text(item.get("place_type")) != wanted:
        return False
    needle = text(q).lower().strip()
    if not needle:
        return True
    blob = " ".join(
        text(item.get(key))
        for key in ("title", "code", "city_label", "type_label", "slug", "subtitle")
    ).lower()
    return needle in blob


def group_directory(items: list) -> list[dict]:
    cards = [directory_card(item) for item in items if text(item.get("slug"))]
    return [
        {
            "id": column["id"],
            "title": column["title"],
            "places": [card for card in cards if card["place_type"] in column["types"]],
        }
        for column in INDEX_COLUMNS
    ]


def type_column_title(place_type: str) -> str:
    wanted = normalize_choice(place_type, PLACE_TYPES, "aeroporto")
    for column in INDEX_COLUMNS:
        if wanted in column["types"]:
            return column["title"]
    return TYPE_LABELS.get(wanted, "")


def maps_directions_url(geo: dict) -> str:
    point = as_dict(geo)
    lat = point.get("lat")
    lng = point.get("lng")
    if lat is None or lng is None:
        return ""
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"


def place_photos(place: dict, *, limit: int | None = None) -> list[dict]:
    item = as_dict(place)
    media = as_dict(item.get("media"))
    seen = set()
    photos = []
    for raw in as_list(media.get("gallery")):
        row = as_dict(raw)
        url = text(row.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        photos.append(
            {
                "url": url,
                "title": text(row.get("title")) or text(row.get("kind")) or text(item.get("title")),
            }
        )
        if limit is not None and len(photos) >= limit:
            return photos
    for point in as_list(item.get("points")):
        row = as_dict(point)
        url = text(row.get("image_url"))
        if not url or url in seen:
            continue
        seen.add(url)
        photos.append({"url": url, "title": text(row.get("name")) or text(item.get("title"))})
        if limit is not None and len(photos) >= limit:
            break
    return photos


def related_cards(groups: list, place: dict, *, limit: int = 3) -> list[dict]:
    current = as_dict(place)
    slug = text(current.get("slug"))
    city = text(current.get("city"))
    place_type = text(current.get("place_type"))
    cards = []
    for column in groups or []:
        for item in as_list(as_dict(column).get("places")):
            card = as_dict(item)
            if not text(card.get("slug")) or text(card.get("slug")) == slug:
                continue
            cards.append(card)
    cards.sort(
        key=lambda card: (
            0 if text(card.get("city")) == city else 1,
            0 if text(card.get("place_type")) == place_type else 1,
            text(card.get("title")),
        )
    )
    return cards[:limit]
