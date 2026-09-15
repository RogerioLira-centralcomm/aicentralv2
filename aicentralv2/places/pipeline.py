"""Monta a ficha e o pacote de imagens depois da pesquisa."""

from __future__ import annotations

import math
import re
import unicodedata

from .images import resolve_place_image_spec
from .research import geocode_one
from .schema import POINT_KINDS, POINT_RADIUS, as_dict, as_list, text


FORBIDDEN_TERMS = (
    "base aérea",
    "base aerea",
    "pista",
    "runway",
    "baía de",
    "baia de",
)
NAME_FIXES = {
    "avenida vinte e oito de setembro": "Vinte de Janeiro",
    "av. vinte e oito de setembro": "Vinte de Janeiro",
    "av vinte e oito de setembro": "Vinte de Janeiro",
}


def fold(value: str) -> str:
    raw = unicodedata.normalize("NFKD", text(value).lower())
    return "".join(ch for ch in raw if not unicodedata.combining(ch))


def point_id(name: str, prefix: str = "") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")[:32] or "ponto"
    head = re.sub(r"[^a-z0-9]+", "-", fold(prefix)).strip("-")[:8]
    return f"{head}-{slug}" if head and not slug.startswith(head) else slug


def forbidden_point(name: str, note: str = "") -> bool:
    blob = f"{fold(name)} {fold(note)}"
    return any(term in blob for term in FORBIDDEN_TERMS)


def fix_point_name(name: str) -> str:
    key = fold(name)
    for needle, replacement in NAME_FIXES.items():
        if needle in key:
            return replacement
    return text(name).split("—")[0].split(" - ")[0].strip() or text(name)


def geocode_queries(name: str, title: str, city: str) -> list[str]:
    short = fix_point_name(name)
    queries = [f"{short} {city}".strip(), f"{short} {title} {city}".strip()]
    seen = set()
    ordered = []
    for query in queries:
        key = fold(query)
        if key and key not in seen:
            seen.add(key)
            ordered.append(query)
    return ordered


def assemble_fiche(place: dict, *, researched=None, finalized=None, refined=None) -> dict:
    researched = as_dict(researched)
    finalized = as_dict(finalized)
    refined = as_dict(refined)
    catchment = dict(as_dict(place.get("catchment")))
    researched_catchment = as_dict(researched.get("catchment"))
    if researched_catchment:
        catchment = {**catchment, **{key: value for key, value in researched_catchment.items() if value}}
    finalized_catchment = as_dict(finalized.get("catchment"))
    if finalized_catchment:
        catchment = {**catchment, **{key: value for key, value in finalized_catchment.items() if value}}
    if refined.get("catchment_profile"):
        catchment["profile"] = refined["catchment_profile"]
    if refined.get("neighborhoods"):
        catchment["neighborhoods"] = refined["neighborhoods"]
    warnings = []
    raw_points = refined.get("points") or finalized.get("points") or researched.get("suggested_points") or []
    points = []
    prefix = text(place.get("code"))
    for raw in as_list(raw_points):
        item = as_dict(raw)
        name = fix_point_name(item.get("name"))
        if not name:
            continue
        if forbidden_point(name, item.get("note")):
            warnings.append(f"Ponto fora da zona comercial: {name}.")
            continue
        if name != text(item.get("name")):
            warnings.append(f"Nome corrigido para {name}.")
        kind = text(item.get("kind")).lower()
        if kind not in POINT_KINDS:
            kind = "halo"
        radius_m = POINT_RADIUS.get(kind, 400)
        points.append(
            {
                "id": text(item.get("id")) or point_id(name, prefix),
                "name": name,
                "kind": kind,
                "note": text(item.get("note")),
                "commercial": text(item.get("commercial")),
                "formats": [text(x) for x in as_list(item.get("formats")) if text(x)][:3],
                "audiences": [text(x) for x in as_list(item.get("audiences")) if text(x)][:2],
                "radius_m": radius_m,
                "radius_label": f"{radius_m} m" if radius_m < 1000 else f"{radius_m / 1000:.1f} km".replace(".0", ""),
            }
        )
    # O catálogo comercial vende um lugar por vez. Subdivisões encontradas
    # na pesquisa são contexto do único ponto, nunca itens de cobrança.
    if points:
        primary = dict(points[0])
        primary["inside"] = [item["name"] for item in points[1:] if item.get("name")]
        points = [primary]
    return {
        "subtitle": text(refined.get("subtitle") or finalized.get("subtitle") or place.get("subtitle")),
        "operator": text(refined.get("operator") or place.get("operator")),
        "offer": as_dict(refined.get("offer")) or as_dict(place.get("offer")),
        "catchment": catchment,
        "audiences": refined.get("audiences") or place.get("audiences") or [],
        "methodology_body": text(refined.get("methodology_body") or as_dict(place.get("methodology")).get("body")),
        "points": points,
        "warnings": warnings,
        "models": {
            "research": text(researched.get("model")),
            "finalize": text(finalized.get("model")),
            "refine": text(refined.get("model")),
        },
    }


def locate_points(points: list, place: dict, *, geocode=None) -> tuple[list, list]:
    locator = geocode or geocode_one
    geo = as_dict(place.get("geo"))
    title = text(place.get("title"))
    city = text(place.get("city_label") or place.get("city"))
    located = []
    missing = []
    for item in points:
        row = dict(item)
        if row.get("lat") is not None and row.get("lng") is not None:
            located.append(row)
            continue
        hit = None
        for query in geocode_queries(row.get("name"), title, city):
            hit = locator(query, near=geo)
            if hit:
                break
        if not hit:
            missing.append(row)
            continue
        row["lat"] = hit.get("lat")
        row["lng"] = hit.get("lng")
        row["source"] = text(row.get("source")) or "Nominatim + refine"
        located.append(row)
    return located, missing


def image_pack(place: dict, *, generated=None, errors=None) -> dict:
    model, resolution = resolve_place_image_spec(place)
    media = as_dict(place.get("media"))
    generated = as_dict(generated)
    points = []
    for item in as_list(place.get("points")):
        url = text(item.get("image_url"))
        if url:
            points.append({"id": text(item.get("id")), "name": text(item.get("name")), "url": url})
    return {
        "spec": {"model": model, "resolution": resolution},
        "hero_url": text(generated.get("hero_url") or media.get("hero_url")),
        "map_url": text(generated.get("map_url") or media.get("map_url")),
        "og_url": text(generated.get("og_url") or media.get("og_url")),
        "points": points,
        "errors": [text(item) for item in as_list(errors) if text(item)],
    }


def fiche_output(place: dict) -> dict:
    media = as_dict(place.get("media"))
    return {
        "identity": {
            "title": text(place.get("title")),
            "code": text(place.get("code")),
            "city": text(place.get("city_label") or place.get("city")),
            "operator": text(place.get("operator")),
            "subtitle": text(place.get("subtitle")),
        },
        "metrics": as_dict(place.get("metrics")),
        "catchment": as_dict(place.get("catchment")),
        "offer": as_dict(place.get("offer")),
        "points": [
            {
                "id": text(item.get("id")),
                "name": text(item.get("name")),
                "kind": text(item.get("kind")),
                "radius": text(item.get("radius_label")),
                "reach": text(item.get("reach")),
                "lat": item.get("lat"),
                "lng": item.get("lng"),
                "image_url": text(item.get("image_url")),
                "commercial": text(item.get("commercial")),
                "formats": item.get("formats") or [],
                "apps": item.get("apps") or [],
                "portals": item.get("portals") or [],
            }
            for item in as_list(place.get("points"))
        ],
        "inventory": as_dict(place.get("inventory")),
        "images": image_pack(place),
        "methodology": as_dict(place.get("methodology")),
        "pipeline": as_dict(place.get("pipeline")),
    }


def pipeline_record(*, steps, models=None, warnings=None, unlocated=None) -> dict:
    return {
        "steps": [text(item) for item in as_list(steps) if text(item)],
        "models": {text(key): text(value) for key, value in as_dict(models).items() if text(key)},
        "warnings": [text(item) for item in as_list(warnings) if text(item)],
        "unlocated": [text(item) for item in as_list(unlocated) if text(item)],
    }


def _distance_km(lat1, lng1, lat2, lng2) -> float:
    try:
        phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
        d_phi = phi2 - phi1
        d_lambda = math.radians(float(lng2) - float(lng1))
    except (TypeError, ValueError):
        return float("inf")
    hav = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(hav), math.sqrt(max(0, 1 - hav)))


def closest_hit(rows: list, near: dict | None) -> dict | None:
    if not rows:
        return None
    if not near or near.get("lat") is None or near.get("lng") is None:
        return rows[0]
    return min(
        rows,
        key=lambda item: _distance_km(near.get("lat"), near.get("lng"), item.get("lat"), item.get("lng")),
    )
