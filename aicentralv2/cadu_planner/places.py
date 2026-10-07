"""Client-facing, read-only projection of published Places."""

from flask import g, has_request_context
from werkzeug.exceptions import BadRequest, NotFound

from ..places import service


def _coordinate(value, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _serialize(row):
    media = row.get("media") or {}
    geo = row.get("geo") or {}
    lat, lng = _coordinate(geo.get("lat"), -90, 90), _coordinate(geo.get("lng"), -180, 180)
    gallery = [item for item in media.get("gallery") or [] if item.get("url")]
    card_image = next((item.get("url") for item in gallery if item.get("kind") == "hero"), "")
    return {
        "id": row["id"], "slug": row["slug"], "name": row["title"],
        "code": row.get("code") or "",
        "operator": row.get("operator") or "",
        "description": row.get("subtitle") or row.get("operator") or "",
        "category": row.get("type_label") or row.get("place_type"),
        "city": row.get("city_label") or row.get("city"),
        "audience": ((row.get("metrics") or {}).get("addressable") or {}).get("label") or "",
        "traffic": ((row.get("metrics") or {}).get("passengers") or {}).get("label") or "",
        "traffic_label": row.get("traffic_label") or "Movimento",
        # The marketplace should show the curated photo library, not a stale
        # generated hero when real photos are available.
        "image_url": card_image or media.get("hero_url") or next((item.get("url") for item in media.get("images") or [] if item.get("url")), ""),
        "gallery": gallery,
        # A place is one media point: its position, not a list of sub-points.
        "lat": lat if lng is not None else None, "lng": lng if lat is not None else None,
        "map_url": f"https://www.google.com/maps?q={lat},{lng}" if lat is not None and lng is not None else "",
        "public_url": row.get("public_url") or "",
    }


def _catalog_records():
    """Serialize the published catalog once per request for cards and facets."""
    cache_key = "planner_place_catalog_records"
    if has_request_context() and hasattr(g, cache_key):
        return getattr(g, cache_key)
    records = [_serialize(service.serialize(item)) for item in service.public_catalog()]
    if has_request_context():
        setattr(g, cache_key, records)
    return records


def catalog(query="", category="", city=""):
    value = str(query or "").strip().lower()
    category_value = str(category or "").strip().lower()
    city_value = str(city or "").strip().lower()
    records = _catalog_records()
    return [row for row in records
            if (not value or value in " ".join(str(row.get(key) or "") for key in ("name", "category", "city")).lower())
            and (not category_value or str(row.get("category") or "").strip().lower() == category_value)
            and (not city_value or str(row.get("city") or "").strip().lower() == city_value)]


def catalog_facets():
    records = catalog()
    return {
        "categories": sorted({str(row.get("category") or "").strip() for row in records if row.get("category")}),
        "cities": sorted({str(row.get("city") or "").strip() for row in records if row.get("city")}),
    }


def detail(slug):
    value = str(slug or "").strip()
    if not value:
        raise BadRequest("Identificador de place inválido.")
    # One row, not the whole serialized catalog: the fiche must stay fast.
    try:
        return _serialize(service.serialize(service.public_place(value)))
    except service.PlaceNotFound:
        raise NotFound("Place indisponível.")
