"""Client-facing, read-only projection of published Places."""

import re
import time

from werkzeug.exceptions import BadRequest, NotFound

from ..places import service
from ..places.schema import shown_label
from ..places.thumbs import thumb_url


def _coordinate(value, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


# Each number with the unit written after it: '641 mil–1,07 mi', '190–280 mil'.
_REACH_PART = re.compile(r"(\d+(?:[.,]\d+)?)\s*(milh\w*|mil|mi\b)?")


def _scale(unit):
    """'milhão/milhões' and 'mi' are millions; 'mil' is thousands."""
    return 1_000 if unit == "mil" else (1_000_000 if unit else 1)


def _compact(people):
    people = round(people, -3) if people >= 10_000 else round(people, -1)
    if people >= 1_000_000:
        return f"{people / 1_000_000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " mi"
    if people >= 10_000:
        return f"{people / 1_000:.0f} mil"
    # Small places read better as whole numbers: '500–1.000', not '500–1 mil'.
    return f"{people:,.0f}".replace(",", ".")


def weekly_reach(label):
    """'190–280 mil' over four weeks → '48–70 mil' a week. A label without a number ('A validar') gives ''."""
    parts = _REACH_PART.findall(str(label or "").lower())[:2]
    if not parts:
        return ""
    # A bound without its own unit borrows the next one: '190–280 mil'.
    units = [unit or next((later for _, later in parts[index:] if later), "") for index, (_, unit) in enumerate(parts)]
    people = [float(number.replace(",", ".")) * _scale(unit) / 4 for (number, _), unit in zip(parts, units)]
    low, high = _compact(people[0]), _compact(people[-1])
    if low == high:
        return low
    # '48 mil–70 mil' reads as '48–70 mil' when both ends share the unit.
    low_number, _, low_unit = low.partition(" ")
    high_unit = high.partition(" ")[2]
    return f"{low_number}–{high}" if low_unit == high_unit else f"{low}–{high}"


def _points(row):
    """Each cut of the place with what reaches it in a week and the apps people use there."""
    result = []
    for point in row.get("points") or []:
        if not point.get("name"):
            continue
        result.append({
            "name": point["name"],
            "scope": point.get("scope_label") or "",
            "weekly": weekly_reach(point.get("reach")),
            "apps": [item.get("name") for item in point.get("apps") or [] if item.get("name")],
        })
    return result


def _serialize(row, full=False):
    """A card for the shelf; ``full`` adds what only the fiche shows (photos, people, channels)."""
    media = row.get("media") or {}
    geo = row.get("geo") or {}
    metrics = row.get("metrics") or {}
    lat, lng = _coordinate(geo.get("lat"), -90, 90), _coordinate(geo.get("lng"), -180, 180)
    gallery = [item for item in media.get("gallery") or [] if item.get("url")]
    card_image = next((item.get("url") for item in gallery if item.get("kind") == "hero"), "")
    # The marketplace should show the curated photo library, not a stale
    # generated hero when real photos are available.
    image = card_image or media.get("hero_url") or next((item.get("url") for item in media.get("images") or [] if item.get("url")), "")
    record = {
        "id": row["id"], "slug": row["slug"], "name": row["title"],
        "code": row.get("code") or "",
        "operator": row.get("operator") or "",
        "description": row.get("subtitle") or row.get("operator") or "",
        "category": row.get("type_label") or row.get("place_type"),
        "city": row.get("city_label") or row.get("city"),
        "audience": shown_label((metrics.get("addressable") or {}).get("label")),
        "traffic": shown_label((metrics.get("passengers") or {}).get("label")),
        "traffic_label": row.get("traffic_label") or "Movimento",
        # Originals reach 6,500 px / 3 MB: the card gets a 640 px copy, the fiche a 1,600 px one.
        "image_url": thumb_url(image, 1600 if full else 640),
        # A place is one media point: its position, not a list of sub-points.
        "lat": lat if lng is not None else None, "lng": lng if lat is not None else None,
        "map_url": f"https://www.google.com/maps?q={lat},{lng}" if lat is not None and lng is not None else "",
        "public_url": row.get("public_url") or "",
    }
    if not full:
        return record
    weekly = row.get("weekly_movement") or {}
    return {
        **record,
        "gallery": [{**item, "url": thumb_url(item["url"], 1600)} for item in gallery],
        # Where each number comes from: official, estimate or to validate.
        "audience_origin": (metrics.get("addressable") or {}).get("source_status") or "",
        "traffic_origin": (metrics.get("passengers") or {}).get("source_status") or "",
        "weekly_movement": [value if isinstance(value, (int, float)) else None for value in weekly.get("values") or []][:7],
        "weekly_origin": weekly.get("source_status") or "",
        "target_audience": [str(item) for item in row.get("target_audience") or [] if item],
        "demographics": {key: str(value) for key, value in (row.get("demographics") or {}).items() if value},
        "channel_ranking": [{"name": item.get("name") or "", "why": item.get("why") or "", "logo": item.get("icon") or ""}
                            for item in (row.get("channel_ranking") or [])[:6] if item.get("name")],
        "points": _points(row),
    }


_CACHE_SECONDS = 60
_cache = {"at": 0.0, "records": None}


def _catalog_records():
    """The published catalog as shelf cards, kept for a minute: places change rarely and building
    them is the slowest part of the page."""
    now = time.monotonic()
    if _cache["records"] is not None and now - _cache["at"] < _CACHE_SECONDS:
        return _cache["records"]
    # public_catalog already serializes; serializing twice lost the audience, traffic and position.
    records = [_serialize(item) for item in service.public_catalog(qr=False)]
    _cache.update(at=now, records=records)
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
        return _serialize(service.public_place(value), full=True)
    except service.PlaceNotFound:
        raise NotFound("Place indisponível.")
