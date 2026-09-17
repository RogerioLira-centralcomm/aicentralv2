"""Client-facing, read-only projection of published Places."""

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


def catalog(query=""):
    value = str(query or "").strip().lower()
    records = [_serialize(service.serialize(item)) for item in service.public_catalog()]
    if not value:
        return records
    return [row for row in records if value in " ".join(str(row.get(key) or "") for key in ("name", "category", "city")).lower()]


def detail(slug):
    value = str(slug or "").strip()
    if not value:
        raise BadRequest("Identificador de place inválido.")
    record = next((row for row in catalog() if row["slug"] == value), None)
    if not record:
        raise NotFound("Place indisponível.")
    return record
