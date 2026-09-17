"""Client-facing, read-only projection of published Places."""

from flask import g, has_request_context
from werkzeug.exceptions import BadRequest, NotFound

from ..places import service


def _serialize(row):
    media = row.get("media") or {}
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
        "investment": ((row.get("investment") or {}).get("label") or ""),
        # The marketplace should show the curated photo library, not a stale
        # generated hero when real photos are available.
        "image_url": card_image or media.get("hero_url") or next((item.get("url") for item in media.get("images") or [] if item.get("url")), ""),
        "gallery": gallery,
        "points": [{"id": item.get("id") or item.get("slug") or item.get("name"), "name": item.get("name"),
                    "kind": item.get("kind"), "audience": item.get("reach") or item.get("audience"),
                    "formats": item.get("formats") or []}
                   for item in (row.get("points") or []) if item.get("name")],
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
    record = next((row for row in catalog() if row["slug"] == value), None)
    if not record:
        raise NotFound("Place indisponível.")
    return record
