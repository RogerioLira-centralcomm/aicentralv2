"""Client-facing, read-only projection of published Places."""

from werkzeug.exceptions import BadRequest, NotFound

from ..places import service


def _serialize(row):
    return {
        "id": row["id"], "slug": row["slug"], "name": row["title"],
        "description": row.get("subtitle") or row.get("operator") or "",
        "category": row.get("type_label") or row.get("place_type"),
        "city": row.get("city_label") or row.get("city"),
        "audience": ((row.get("metrics") or {}).get("addressable") or {}).get("label") or "",
        "points": [{"id": item.get("id") or item.get("slug") or item.get("name"), "name": item.get("name"),
                    "kind": item.get("kind"), "audience": item.get("reach") or item.get("audience")}
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
