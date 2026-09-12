"""Regras de criação, publicação e seed dos Places."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask import session

from .catalog import SEED_PLACES
from .repository import (
    PlaceNotFound,
    count_places,
    get_by_id,
    get_by_preview_token,
    get_by_slug,
    get_published_by_slug,
    insert_inquiry,
    insert_place,
    inquiry_payload,
    list_places,
    list_published,
    update_place,
    upsert_seed,
)
from .images import ImageError, generate_place_images, generate_point_images
from .research import (
    ResearchError,
    finalize_import,
    research_region,
    review_place,
    search_places,
    suggest_points,
)
from .schema import (
    CITIES,
    CITY_LABELS,
    PLACE_TYPES,
    POINT_KINDS,
    POINT_LABELS,
    SOURCE_LABELS,
    STATUS_LABELS,
    STATUSES,
    TYPE_LABELS,
    empty_payload,
    normalize_choice,
    normalize_payload,
    public_view,
    text,
)
from .share import make_preview_token, preview_url, public_url, qr_svg, slugify


def _user_id():
    try:
        value = session.get("user_id")
    except Exception:
        return None
    return int(value) if value not in (None, "") else None


def ensure_seed() -> int:
    created = 0
    for item in SEED_PLACES:
        existing = get_by_slug(item["slug"])
        row = {
            **item,
            "preview_token": (existing or {}).get("preview_token") or make_preview_token(),
            "published_at": datetime.now(timezone.utc) if item.get("status") == "published" else None,
            "created_by": _user_id(),
        }
        before = count_places()
        upsert_seed(row)
        if not existing and count_places() > before:
            created += 1
    return created


def _share(row: dict) -> dict:
    slug = text(row.get("slug"))
    token = text(row.get("preview_token"))
    status = row.get("status")
    url = public_url(slug) if status == "published" else preview_url(token)
    return {
        "public_url": public_url(slug) if status == "published" else "",
        "preview_url": preview_url(token),
        "share_url": url,
        "qr_svg": qr_svg(url) if url else "",
    }


def serialize(row: dict) -> dict:
    view = public_view(row)
    view.update(_share(row))
    view["source_labels"] = SOURCE_LABELS
    return view


def list_desk(*, city: str = "", place_type: str = "", status: str = "", q: str = "") -> dict:
    ensure_seed()
    rows = [serialize(item) for item in list_places(city=city, place_type=place_type, status=status, q=q)]
    airports = [item for item in rows if item["place_type"] == "aeroporto"]
    mapping = [item for item in rows if item["place_type"] != "aeroporto" or item["status"] == "mapping"]
    return {
        "rows": rows,
        "airports": airports,
        "mapping": mapping,
        "filters": {"city": city, "place_type": place_type, "status": status, "q": q},
        "cities": [{"id": key, "label": CITY_LABELS[key]} for key in CITIES],
        "types": [{"id": key, "label": TYPE_LABELS[key]} for key in PLACE_TYPES],
        "statuses": [{"id": key, "label": STATUS_LABELS[key]} for key in STATUSES],
        "empty_hint": (
            "SP e RJ têm mais pontos a mapear — shoppings e áreas de evento entram como rascunho."
        ),
    }


def form_context(row: dict | None = None) -> dict:
    place = serialize(row) if row else {
        "id": None,
        "slug": "",
        "place_type": "aeroporto",
        "city": "bh",
        "status": "draft",
        "title": "",
        "code": "",
        "operator": "",
        "subtitle": "",
        **empty_payload(),
        "public_url": "",
        "preview_url": "",
        "share_url": "",
        "qr_svg": "",
        "city_label": CITY_LABELS["bh"],
        "type_label": TYPE_LABELS["aeroporto"],
        "status_label": STATUS_LABELS["draft"],
        "source_labels": SOURCE_LABELS,
        "point_kinds": [{"id": key, "label": POINT_LABELS[key]} for key in POINT_KINDS],
    }
    return {
        "place": place,
        "cities": [{"id": key, "label": CITY_LABELS[key]} for key in CITIES],
        "types": [{"id": key, "label": TYPE_LABELS[key]} for key in PLACE_TYPES],
        "statuses": [{"id": key, "label": STATUS_LABELS[key]} for key in STATUSES],
        "source_labels": SOURCE_LABELS,
        "point_kinds": [{"id": key, "label": POINT_LABELS[key]} for key in POINT_KINDS],
    }


def _payload_from_input(raw: Any) -> dict:
    data = raw if isinstance(raw, dict) else {}
    return normalize_payload(data)


def save_place(raw: Any, *, place_id: int | None = None) -> dict:
    data = raw if isinstance(raw, dict) else {}
    title = text(data.get("title"))
    if not title:
        raise ValueError("Informe o nome do place.")
    slug = slugify(data.get("slug") or title)
    existing = get_by_slug(slug)
    if existing and int(existing["id"]) != int(place_id or 0):
        raise ValueError("Já existe um place com este slug.")
    status = normalize_choice(data.get("status"), STATUSES, "draft")
    payload_preview = normalize_payload(data.get("payload"))
    if status == "published":
        geo = payload_preview.get("geo") or {}
        has_map = geo.get("lat") is not None and (
            payload_preview.get("points") or payload_preview.get("zones")
        )
        if not has_map:
            status = "mapping" if data.get("place_type") != "aeroporto" else "draft"
    if normalize_choice(data.get("place_type"), PLACE_TYPES, "aeroporto") != "aeroporto" and status == "published":
        if not payload_preview.get("zones") and not payload_preview.get("points"):
            status = "mapping"
    current = get_by_id(place_id) if place_id else None
    published_at = current.get("published_at") if current else None
    if status == "published" and not published_at:
        published_at = datetime.now(timezone.utc)
    if status != "published":
        published_at = published_at if status == "archived" else None
    payload = _payload_from_input(data.get("payload"))
    if current:
        previous = normalize_payload(current.get("payload"))
        if not payload.get("zones") and previous.get("zones"):
            payload["zones"] = previous["zones"]
        else:
            previous_zones = {
                item.get("id"): item
                for item in previous.get("zones") or []
                if item.get("id")
            }
            merged_zones = []
            for zone in payload.get("zones") or []:
                old = previous_zones.get(zone.get("id")) or {}
                if old:
                    zone["formats"] = zone.get("formats") or old.get("formats") or []
                    zone["audiences"] = zone.get("audiences") or old.get("audiences") or []
                    zone["commercial"] = zone.get("commercial") or old.get("commercial") or ""
                    zone["color"] = zone.get("color") or old.get("color") or ""
                    zone["geometry"] = zone.get("geometry") or old.get("geometry") or {}
                merged_zones.append(zone)
            payload["zones"] = merged_zones
        if not payload.get("audiences") and previous.get("audiences"):
            payload["audiences"] = previous["audiences"]
        if not (payload.get("research") or {}).get("notes") and previous.get("research"):
            payload["research"] = previous["research"]
        media = dict(previous.get("media") or {})
        media.update({key: value for key, value in (payload.get("media") or {}).items() if value})
        payload["media"] = media
        payload["points"] = _merge_points(payload.get("points") or [], previous.get("points") or [])
        if not payload.get("methodology"):
            payload["methodology"] = previous.get("methodology")
    record = {
        "slug": slug,
        "preview_token": (current or {}).get("preview_token") or make_preview_token(),
        "place_type": normalize_choice(data.get("place_type"), PLACE_TYPES, "aeroporto"),
        "city": normalize_choice(data.get("city"), CITIES, "bh"),
        "status": status,
        "title": title,
        "code": text(data.get("code")).upper(),
        "operator": text(data.get("operator")),
        "subtitle": text(data.get("subtitle")),
        "payload": payload,
        "published_at": published_at,
        "created_by": _user_id(),
    }
    if place_id:
        return serialize(update_place(place_id, record))
    return serialize(insert_place(record))


def publish_place(place_id: int) -> dict:
    row = get_by_id(place_id)
    payload = normalize_payload(row.get("payload"))
    geo = payload.get("geo") or {}
    if geo.get("lat") is None or not (payload.get("points") or payload.get("zones")):
        raise ValueError("Publique depois de ter o mapa e pelo menos um ponto ou zona.")
    row["status"] = "published"
    row["published_at"] = datetime.now(timezone.utc)
    return serialize(update_place(place_id, row))


def apply_research(place_id: int) -> dict:
    place = serialize(get_by_id(place_id))
    result = research_region(place)
    payload = normalize_payload(place)
    payload["catchment"] = result["catchment"]
    payload["research"] = {
        **result["research"],
        "reviewed_at": "",
        "review": "",
    }
    record = dict(place)
    record["payload"] = payload
    saved = update_place(place_id, record)
    return {**serialize(saved), "suggested_points": result.get("suggested_points") or []}


def apply_review(place_id: int) -> dict:
    place = serialize(get_by_id(place_id))
    result = review_place(place)
    payload = normalize_payload(place)
    if result.get("catchment"):
        payload["catchment"] = result["catchment"]
    research = dict(payload.get("research") or {})
    research["review"] = result.get("review") or ""
    research["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    payload["research"] = research
    record = dict(place)
    if result.get("subtitle"):
        record["subtitle"] = result["subtitle"]
    record["payload"] = payload
    saved = serialize(update_place(place_id, record))
    saved["review_changes"] = result.get("changes") or []
    return saved


def apply_import(place_id: int) -> dict:
    researched = apply_research(place_id)
    place = serialize(get_by_id(place_id))
    result = finalize_import(place, research=place.get("research"))
    payload = normalize_payload(place)
    if result.get("catchment"):
        payload["catchment"] = result["catchment"]
    research = dict(payload.get("research") or {})
    research["review"] = result.get("review") or ""
    research["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    payload["research"] = research
    record = dict(place)
    if result.get("subtitle"):
        record["subtitle"] = result["subtitle"]
    record["payload"] = payload
    update_place(place_id, record)
    suggested = result.get("points") or researched.get("suggested_points") or []
    saved = apply_suggested_points(place_id, suggested)
    saved["review_changes"] = result.get("changes") or []
    saved["import_model"] = result.get("model") or ""
    return saved


def apply_suggested_points(place_id: int, raw_points: list | None = None) -> dict:
    place = serialize(get_by_id(place_id))
    suggested = suggest_points(place, raw_points)
    payload = normalize_payload(place)
    payload["points"] = _merge_points(suggested, payload.get("points") or [])
    record = dict(place)
    record["payload"] = payload
    return serialize(update_place(place_id, record))


def apply_images(place_id: int, *, kind: str = "both", point_id: str = "") -> dict:
    place = serialize(get_by_id(place_id))
    payload = normalize_payload(place)
    kind = (kind or "both").lower()
    if kind in ("points", "point", "all"):
        generated = generate_point_images(place, point_id=point_id if kind == "point" else "")
        by_id = {text(item.get("id")): item for item in generated}
        by_name = {text(item.get("name")).lower(): item for item in generated}
        merged = []
        for item in payload.get("points") or []:
            match = by_id.get(text(item.get("id"))) or by_name.get(text(item.get("name")).lower())
            if match and match.get("image_url"):
                item = dict(item)
                item["image_url"] = match["image_url"]
            merged.append(item)
        payload["points"] = merged
    if kind not in ("points", "point"):
        media = dict(payload.get("media") or {})
        media.update(generate_place_images(place, kind=kind))
        payload["media"] = media
    record = dict(place)
    record["payload"] = payload
    return serialize(update_place(place_id, record))


def _merge_points(incoming: list, previous: list) -> list:
    old_by_name = {text(item.get("name")).lower(): item for item in previous if text(item.get("name"))}
    old_by_id = {text(item.get("id")): item for item in previous if text(item.get("id"))}
    merged = []
    seen = set()
    for item in list(incoming or []) + list(previous or []):
        name = text(item.get("name")).lower()
        key = text(item.get("id")) or name
        if not name or key in seen:
            continue
        seen.add(key)
        old = old_by_id.get(text(item.get("id"))) or old_by_name.get(name) or {}
        if old.get("image_url") and not item.get("image_url"):
            item = dict(item)
            item["image_url"] = old["image_url"]
        if old.get("note") and not item.get("note"):
            item = dict(item)
            item["note"] = old["note"]
        merged.append(item)
    return merged


def unpublish_place(place_id: int) -> dict:
    row = get_by_id(place_id)
    row["status"] = "draft"
    return serialize(update_place(place_id, row))


def _seed_public(slug: str = "") -> list[dict]:
    rows = []
    for index, item in enumerate(SEED_PLACES, start=1):
        if slug and item["slug"] != slug:
            continue
        rows.append(
            serialize(
                dict(
                    item,
                    id=index,
                    preview_token=f"seed-{item['slug']}",
                    status="published",
                )
            )
        )
    return rows


def public_catalog() -> list[dict]:
    try:
        ensure_seed()
        return [serialize(item) for item in list_published()]
    except Exception:
        return _seed_public()


def public_place(slug: str) -> dict:
    try:
        ensure_seed()
        return serialize(get_published_by_slug(slug))
    except PlaceNotFound:
        fallback = _seed_public(slug)
        if fallback:
            return fallback[0]
        raise
    except Exception:
        fallback = _seed_public(slug)
        if fallback:
            return fallback[0]
        raise


def preview_place(token: str) -> dict:
    return serialize(get_by_preview_token(token))


def create_inquiry(slug: str, raw: Any) -> dict:
    row = get_published_by_slug(slug)
    payload = inquiry_payload(raw)
    payload["place_id"] = row["id"]
    payload["source_slug"] = row["slug"]
    return insert_inquiry(payload)
