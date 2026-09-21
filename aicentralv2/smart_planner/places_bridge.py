"""Places publicados no motor de briefing do Smart Planner — só leitura."""

from __future__ import annotations

import re
from typing import Any

from .catalog import CHANNEL_CATALOG, INTERATIVOS_FORMATS, PORTAL_CHANNELS
from .helpers import as_dict, as_list, text


PLACE_ALIASES = {
    "confins": (
        "confins", "cnf", "bh airport", "aeroporto de confins",
        "aeroporto internacional de belo horizonte",
    ),
    "congonhas": ("congonhas", "cgh", "aeroporto de congonhas"),
    "santos-dumont": ("santos dumont", "sdu", "aeroporto santos dumont"),
    "galeao": ("galeão", "galeao", "gig", "aeroporto do galeão"),
    "diamond-mall": ("diamond mall", "diamond"),
    "iguatemi-sao-paulo": ("iguatemi são paulo", "iguatemi sao paulo", "iguatemi"),
    "ibirapuera": ("ibirapuera", "parque ibirapuera"),
    "expominas": ("expominas",),
}


def _item_name(raw: Any) -> str:
    if isinstance(raw, dict):
        return text(raw.get("name") or raw.get("label") or raw.get("id"))
    return text(raw)


def _names(items: Any) -> list[str]:
    out = []
    seen = set()
    for item in as_list(items):
        name = _item_name(item)
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def _aliases_for(place: dict) -> list[str]:
    slug = text(place.get("slug")).lower()
    names = [slug, text(place.get("title")).lower(), text(place.get("code")).lower()]
    names.extend(PLACE_ALIASES.get(slug, ()))
    out = []
    seen = set()
    for name in names:
        value = text(name).lower()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _compact_point(point: dict) -> dict:
    data = as_dict(point)
    return {
        "id": text(data.get("id")),
        "name": text(data.get("name")),
        "kind": text(data.get("kind")),
        "kind_label": text(data.get("kind_label") or data.get("name")),
        "radius_m": data.get("radius_m"),
        "radius_label": text(data.get("radius_label")),
        "reach": text(data.get("reach")),
        "apps": _names(data.get("apps")),
        "portals": _names(data.get("portals")),
        "formats": [text(item) for item in as_list(data.get("formats")) if text(item)],
        "commercial": text(data.get("commercial")),
    }


def _investment_minimum(value: Any) -> int:
    """Return the floor of a published Brazilian investment range, in BRL."""
    raw = text(value).lower().replace(".", "")
    match = re.search(r"(\d+(?:,\d+)?)\s*(mil|k)?", raw)
    if not match:
        return 0
    number = float(match.group(1).replace(",", "."))
    return int(number * (1000 if match.group(2) in {"mil", "k"} else 1))


def _compact_place(row: dict) -> dict:
    data = as_dict(row)
    metrics = as_dict(data.get("metrics"))
    addressable = as_dict(metrics.get("addressable"))
    four_weeks = as_dict(metrics.get("four_weeks"))
    investment = as_dict(data.get("investment"))
    points = [_compact_point(item) for item in as_list(data.get("points")) if text(as_dict(item).get("id"))]
    return {
        "slug": text(data.get("slug")),
        "title": text(data.get("title")),
        "code": text(data.get("code")),
        "place_type": text(data.get("place_type")),
        "type_label": text(data.get("type_label")),
        "city": text(data.get("city")),
        "city_label": text(data.get("city_label")),
        "aliases": _aliases_for(data),
        "points": points,
        "metrics": {
            "addressable": text(addressable.get("label")),
            "four_weeks": text(four_weeks.get("label")),
        },
        "investment_label": text(investment.get("label")),
        "investment_min_brl": _investment_minimum(investment.get("label") or investment.get("value")),
    }


def places_minimum(raw: Any, catalog: list[dict] | None = None) -> dict:
    """Commercial floor for unique selected Places; points never double the floor."""
    selected = resolve_places(raw, catalog)
    index = catalog_by_slug(catalog)
    items = []
    for item in selected:
        place = index.get(text(item.get("slug"))) or {}
        minimum = int(place.get("investment_min_brl") or 0)
        if minimum:
            items.append({"slug": item["slug"], "title": place.get("title") or item["slug"], "minimum_brl": minimum})
    return {"minimum_brl": sum(item["minimum_brl"] for item in items), "items": items, "missing": [item["slug"] for item in selected if not int((index.get(text(item.get("slug"))) or {}).get("investment_min_brl") or 0)]}


def _seed_catalog() -> list[dict]:
    try:
        from ..places.catalog import SEED_PLACES
        from ..places.schema import public_view
    except Exception:
        return []
    out = []
    for item in SEED_PLACES:
        if text(item.get("status")) != "published":
            continue
        out.append(_compact_place(public_view(item)))
    return [item for item in out if item.get("slug")]


def planner_place_catalog() -> list[dict]:
    rows = []
    try:
        from ..places.service import public_catalog
        rows = [_compact_place(item) for item in public_catalog() or []]
    except Exception:
        rows = []
    rows = [item for item in rows if item.get("slug")]
    return rows or _seed_catalog()


def catalog_by_slug(catalog: list[dict] | None = None) -> dict[str, dict]:
    return {text(item.get("slug")): item for item in (catalog or planner_place_catalog()) if text(item.get("slug"))}


def catalog_prompt_lines(catalog: list[dict] | None = None) -> str:
    lines = []
    for place in catalog or planner_place_catalog():
        points = []
        for point in as_list(place.get("points")):
            apps = ", ".join(as_list(point.get("apps"))) or "sem app listado"
            points.append(
                f"{text(point.get('id'))} ({text(point.get('name'))}, {text(point.get('radius_label'))}, apps: {apps})"
            )
        lines.append(
            f"- {text(place.get('slug'))} = {text(place.get('title'))}"
            + (f" ({text(place.get('code'))})" if place.get("code") else "")
            + (f" · pontos: {'; '.join(points)}" if points else "")
        )
    return "\n".join(lines) or "- (nenhum place publicado)"


def _match_point(place: dict, raw_id: str) -> dict:
    wanted = text(raw_id).lower()
    if not wanted:
        return {}
    for point in as_list(place.get("points")):
        if text(point.get("id")).lower() == wanted:
            return as_dict(point)
        if text(point.get("kind")).lower() == wanted:
            return as_dict(point)
        if text(point.get("name")).lower() == wanted:
            return as_dict(point)
    return {}


def _filter_apps(wanted: Any, points: list[dict]) -> list[str]:
    allowed = {}
    for point in points:
        for name in as_list(point.get("apps")):
            allowed[text(name).lower()] = text(name)
    out = []
    for name in _names(wanted):
        key = name.lower()
        if key in allowed and allowed[key] not in out:
            out.append(allowed[key])
    return out


def resolve_places(raw: Any, catalog: list[dict] | None = None) -> list[dict]:
    index = catalog_by_slug(catalog)
    out = []
    seen = set()
    for item in as_list(raw):
        data = as_dict(item) if isinstance(item, dict) else {"slug": item}
        slug = text(data.get("slug")).lower()
        place = index.get(slug)
        if not place or slug in seen:
            continue
        wanted_points = [text(value) for value in as_list(data.get("point_ids") or data.get("points")) if text(value)]
        points = []
        for raw_id in wanted_points:
            point = _match_point(place, raw_id)
            if point and text(point.get("id")) not in {text(row.get("id")) for row in points}:
                points.append(point)
        if not points:
            points = [as_dict(row) for row in as_list(place.get("points"))[:1] if as_dict(row).get("id")]
        apps = _filter_apps(data.get("apps"), points)
        out.append({
            "slug": text(place.get("slug")),
            "title": text(place.get("title")),
            "point_ids": [text(row.get("id")) for row in points],
            "apps": apps,
        })
        seen.add(slug)
    return out


def suggest_places_from_material(material: str, catalog: list[dict] | None = None) -> list[dict]:
    hay = text(material).lower()
    if not hay:
        return []
    found = []
    for place in catalog or planner_place_catalog():
        aliases = as_list(place.get("aliases")) or _aliases_for(place)
        if any(_mentions_alias(hay, alias) for alias in aliases):
            found.append({"slug": text(place.get("slug")), "point_ids": [], "apps": []})
    resolved = resolve_places(found, catalog)
    index = catalog_by_slug(catalog)
    for item in resolved:
        place = index.get(text(item.get("slug"))) or {}
        wanted = set(as_list(item.get("point_ids")))
        points = [
            as_dict(point) for point in as_list(place.get("points"))
            if not wanted or text(as_dict(point).get("id")) in wanted
        ]
        item["apps"] = sorted(set(name for point in points for name in _names(point.get("apps"))))
        item["sites"] = sorted(set(name for point in points for name in _names(point.get("portals"))))
    return resolved


def _mentions_alias(material: str, alias: str) -> bool:
    value = text(alias).strip().lower()
    if not value:
        return False
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])", material, re.I))


def snapshot_places(raw: Any, catalog: list[dict] | None = None) -> list[dict]:
    index = catalog_by_slug(catalog)
    resolved = resolve_places(raw, catalog)
    out = []
    for item in resolved:
        place = index.get(text(item.get("slug")))
        if not place:
            continue
        wanted = set(as_list(item.get("point_ids")))
        points = []
        for point in as_list(place.get("points")):
            if wanted and text(point.get("id")) not in wanted:
                continue
            row = dict(point)
            if item.get("apps"):
                allowed = {name.lower() for name in as_list(item.get("apps"))}
                row["apps"] = [name for name in as_list(point.get("apps")) if text(name).lower() in allowed]
            points.append(row)
        out.append({
            "slug": text(place.get("slug")),
            "title": text(place.get("title")),
            "type": text(place.get("place_type")),
            "type_label": text(place.get("type_label")),
            "city": text(place.get("city")),
            "city_label": text(place.get("city_label")),
            "points": points,
            "metrics": as_dict(place.get("metrics")),
        })
    return out


def normalize_interativos(raw: Any, canais: Any) -> dict:
    keys = {text(key) for key in as_list(canais) if text(key)}
    allowed = {item["id"] for item in INTERATIVOS_FORMATS}
    formats = []
    data = as_dict(raw) if not isinstance(raw, list) else {"formats": raw}
    for item in as_list(data.get("formats")):
        key = text(item).lower().replace("í", "i")
        if key in allowed and key not in formats:
            formats.append(key)
    if not keys.intersection(PORTAL_CHANNELS):
        return {"formats": []}
    return {"formats": formats}


def apply_places_to_campos(
    campos: dict,
    catalog: list[dict] | None = None,
    material: str = "",
    *,
    lock_channel: bool = False,
) -> dict:
    out = dict(campos or {})
    resolved = resolve_places(out.get("places"), catalog)
    if material:
        # The extractor may see the full catalog in its prompt. Re-resolve only
        # explicit venue mentions so it cannot select catalog points or apps
        # that the user never chose.
        resolved = suggest_places_from_material(material, catalog)
    out["places"] = resolved
    canais = [text(key) for key in as_list(out.get("canais")) if text(key) in CHANNEL_CATALOG]
    if resolved and "places" not in canais:
        canais.append("places")
    if not resolved and not lock_channel:
        canais = [key for key in canais if key != "places"]
    interativos = normalize_interativos(out.get("interativos"), canais)
    if "interativos" in canais and not any(key in PORTAL_CHANNELS for key in canais):
        canais = [key for key in canais if key != "interativos"]
        interativos = {"formats": []}
    if interativos.get("formats") and "interativos" not in canais and any(key in PORTAL_CHANNELS for key in canais):
        canais.append("interativos")
    out["interativos"] = interativos
    out["canais"] = canais
    return out


def places_prompt_block(places: list[dict] | None) -> str:
    rows = as_list(places)
    if not rows:
        return ""
    lines = [
        "PLACES CONFIRMADOS — use só estes ambientes. Apresente audiência de forma consolidada. Apps e sites observados no catálogo podem ser usados como contexto de audiência digital, nunca como promessa de compra ou inventário. Não liste pontos, raios, preços ou fornecedores.",
    ]
    for place in rows:
        title = text(place.get("title") or place.get("slug"))
        metrics = as_dict(place.get("metrics"))
        audience = text(metrics.get("addressable")) or "A definir"
        period = text(metrics.get("four_weeks")) or "A definir"
        apps = []
        sites = []
        for point in as_list(place.get("points")):
            apps.extend(text(item) for item in as_list(as_dict(point).get("apps")) if text(item))
            sites.extend(text(item) for item in as_list(as_dict(point).get("portals")) if text(item))
        digital = sorted(set(apps + sites))
        digital_note = f" · ambientes digitais observados: {', '.join(digital[:4])}" if digital else ""
        lines.append(f"- {title} · audiência consolidada: {audience} · média em 4 semanas: {period}{digital_note}")
    return "\n".join(lines)
