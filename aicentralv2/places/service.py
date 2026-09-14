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
from .images import (
    ImageError,
    generate_place_images,
    generate_point_images,
    image_queue,
    next_image_target,
    resolve_place_image_spec,
)
from .visual_refs import collect_visual_refs, gallery_items_by_ids, merge_gallery, select_gallery
from .pipeline import assemble_fiche, fiche_output, image_pack, locate_points, pipeline_record
from .research import (
    ResearchError,
    enrich_points,
    finalize_import,
    polish_one_page,
    refine_generated_fiche,
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
    as_dict,
    as_list,
    empty_payload,
    format_usd,
    normalize_choice,
    normalize_costs,
    normalize_payload,
    public_view,
    text,
    usage_cost_usd,
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


def _desk_stats(view: dict) -> dict:
    points = [item for item in (view.get("points") or []) if item.get("name")]
    media = as_dict(view.get("media"))
    photos = sum(1 for item in points if item.get("image_url"))
    if media.get("hero_url"):
        photos += 1
    if media.get("map_url"):
        photos += 1
    costs = normalize_costs(view.get("costs"))
    return {
        "points_count": len(points),
        "photos_count": photos,
        "photos_total": len(points) + 2,
        "ai_cost_usd": costs.get("total_usd") or 0,
        "ai_cost_label": costs.get("label") or format_usd(costs.get("total_usd")),
        "image_queue": image_queue(view),
    }


def _record_cost(payload: dict, *, step: str, model: str = "", usage=None, usd=None, label: str = "") -> dict:
    costs = normalize_costs(payload.get("costs"))
    amount = usd if usd is not None else usage_cost_usd(usage)
    if not step or float(amount or 0) <= 0:
        payload["costs"] = costs
        return payload
    costs["entries"].append(
        {
            "step": step,
            "model": text(model),
            "usd": float(amount or 0),
            "at": datetime.now(timezone.utc).isoformat(),
            "label": label or step,
        }
    )
    payload["costs"] = normalize_costs(costs)
    return payload


def _keep_previous(previous: dict, payload: dict) -> dict:
    if not (payload.get("metrics") or {}).get("passengers", {}).get("value") and (
        previous.get("metrics") or {}
    ).get("passengers", {}).get("value"):
        payload["metrics"] = previous["metrics"]
    if not (payload.get("offer") or {}).get("lead") and (previous.get("offer") or {}).get("lead"):
        payload["offer"] = previous["offer"]
    if not (payload.get("audiences") or []) and previous.get("audiences"):
        payload["audiences"] = previous["audiences"]
    if not (payload.get("research") or {}).get("notes") and previous.get("research"):
        payload["research"] = previous["research"]
    if not (payload.get("pipeline") or {}).get("steps") and previous.get("pipeline"):
        payload["pipeline"] = previous["pipeline"]
    if not (payload.get("costs") or {}).get("entries") and previous.get("costs"):
        payload["costs"] = previous["costs"]
    if not (payload.get("inventory") or {}).get("lead") and (previous.get("inventory") or {}).get("lead"):
        payload["inventory"] = previous["inventory"]
    prev_body = text((previous.get("methodology") or {}).get("body"))
    incoming_body = text((payload.get("methodology") or {}).get("body"))
    default_body = text((empty_payload().get("methodology") or {}).get("body"))
    if prev_body and incoming_body in ("", default_body) and prev_body != default_body:
        payload["methodology"] = previous["methodology"]
    return payload


def serialize(row: dict) -> dict:
    view = public_view(row)
    view.update(_share(row))
    view["source_labels"] = SOURCE_LABELS
    view["fiche"] = fiche_output(view)
    view["images"] = image_pack(view)
    view.update(_desk_stats(view))
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
        "fiche": fiche_output({"title": "", "code": "", **empty_payload()}),
        "images": image_pack({}),
        "costs": normalize_costs({}),
        "image_queue": [],
        "points_count": 0,
        "photos_count": 0,
        "photos_total": 2,
        "ai_cost_usd": 0,
        "ai_cost_label": "—",
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
        payload = _keep_previous(previous, payload)
        media = dict(previous.get("media") or {})
        media.update({key: value for key, value in (payload.get("media") or {}).items() if value})
        payload["media"] = media
        payload["points"] = _merge_points(payload.get("points") or [], previous.get("points") or [])
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
    _record_cost(
        payload,
        step="research",
        model=text(result.get("model")),
        usage=result.get("usage"),
        label="Pesquisa da bacia",
    )
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
    _record_cost(
        payload,
        step="review",
        model=text(result.get("model")),
        usage=result.get("usage"),
        label="Revisão da ficha",
    )
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
    finalized = finalize_import(place, research=place.get("research"))
    refined = refine_generated_fiche(place, draft=finalized)
    assembled = assemble_fiche(place, researched=researched, finalized=finalized, refined=refined)
    located, missing_rows = locate_points(assembled.get("points") or [], place)
    if not located and not missing_rows:
        try:
            located, missing_rows = locate_points(suggest_points(place, assembled.get("points") or []), place)
        except ResearchError:
            missing_rows = list(assembled.get("points") or [])
    unlocated = [text(item.get("name")) for item in missing_rows if text(item.get("name"))]
    payload = normalize_payload(place)
    if assembled.get("catchment"):
        payload["catchment"] = assembled["catchment"]
    if assembled.get("offer") and assembled["offer"].get("lead"):
        payload["offer"] = assembled["offer"]
    if assembled.get("audiences"):
        payload["audiences"] = assembled["audiences"]
    if assembled.get("methodology_body"):
        methodology = dict(payload.get("methodology") or {})
        methodology["title"] = methodology.get("title") or "Como o número é feito"
        methodology["body"] = assembled["methodology_body"]
        payload["methodology"] = methodology
    research = dict(payload.get("research") or {})
    research["review"] = finalized.get("review") or ""
    research["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    payload["research"] = research
    payload["points"] = _merge_points(located + missing_rows, payload.get("points") or [])
    warnings = list(assembled.get("warnings") or [])
    _record_cost(payload, step="finalize", model=text(finalized.get("model")), usage=finalized.get("usage"), label="Fechar ficha")
    _record_cost(payload, step="refine", model=text(refined.get("model")), usage=refined.get("usage"), label="Refinar ficha")
    if unlocated:
        warnings.append("Sem coordenada: " + ", ".join(unlocated) + ".")
    model, resolution = resolve_place_image_spec(place)
    media = dict(payload.get("media") or {})
    media["image_model"] = model
    media["image_resolution"] = resolution
    payload["media"] = media
    payload["pipeline"] = pipeline_record(
        steps=["research", "finalize", "refine", "geocode"],
        models={**as_dict(assembled.get("models")), "image": model},
        warnings=warnings,
        unlocated=unlocated,
    )
    record = dict(place)
    if assembled.get("subtitle"):
        record["subtitle"] = assembled["subtitle"]
    if assembled.get("operator"):
        record["operator"] = assembled["operator"]
    record["payload"] = payload
    update_place(place_id, record)
    place = serialize(get_by_id(place_id))
    try:
        polished = polish_one_page(place)
    except ResearchError:
        polished = {}
    if polished:
        payload = normalize_payload(place)
        if polished.get("subtitle"):
            record["subtitle"] = polished["subtitle"]
        if polished.get("offer") and polished["offer"].get("lead"):
            payload["offer"] = polished["offer"]
        if polished.get("catchment_profile"):
            catchment = dict(payload.get("catchment") or {})
            catchment["profile"] = polished["catchment_profile"]
            payload["catchment"] = catchment
        if polished.get("methodology_body"):
            methodology = dict(payload.get("methodology") or {})
            methodology["body"] = polished["methodology_body"]
            payload["methodology"] = methodology
        by_id = {text(item.get("id")): item for item in polished.get("points") or []}
        merged = []
        for item in payload.get("points") or []:
            extra = by_id.get(text(item.get("id"))) or {}
            row = dict(item)
            if extra.get("commercial"):
                row["commercial"] = extra["commercial"]
            if extra.get("formats"):
                row["formats"] = extra["formats"]
            if extra.get("audiences"):
                row["audiences"] = extra["audiences"]
            merged.append(row)
        payload["points"] = merged
        steps = list((payload.get("pipeline") or {}).get("steps") or [])
        if "polish" not in steps:
            steps.append("polish")
        pipeline = dict(payload.get("pipeline") or {})
        pipeline["steps"] = steps
        models = dict(pipeline.get("models") or {})
        models["polish"] = text(polished.get("model"))
        pipeline["models"] = models
        payload["pipeline"] = pipeline
        _record_cost(payload, step="polish", model=text(polished.get("model")), usage=polished.get("usage"), label="Polir one-page")
        record["payload"] = payload
        update_place(place_id, record)
    saved = serialize(get_by_id(place_id))
    saved["review_changes"] = finalized.get("changes") or []
    saved["import_model"] = finalized.get("model") or refined.get("model") or ""
    saved["pipeline"] = saved.get("pipeline") or payload.get("pipeline")
    return saved


def apply_suggested_points(place_id: int, raw_points: list | None = None) -> dict:
    place = serialize(get_by_id(place_id))
    suggested = suggest_points(place, raw_points)
    payload = normalize_payload(place)
    payload["points"] = _merge_points(suggested, payload.get("points") or [])
    record = dict(place)
    record["payload"] = payload
    return serialize(update_place(place_id, record))


def collect_place_gallery(place_id: int, *, kind: str = "hero", point_id: str = "") -> dict:
    place = serialize(get_by_id(place_id))
    payload = normalize_payload(place)
    point = next(
        (
            item
            for item in payload.get("points") or []
            if text(item.get("id")) == text(point_id) or text(item.get("name")) == text(point_id)
        ),
        None,
    ) if point_id else None
    incoming = collect_visual_refs(place, kind=kind or "hero", point=point)
    if incoming and not any(item.get("selected") for item in incoming):
        incoming[0]["selected"] = True
    media = dict(payload.get("media") or {})
    media["gallery"] = merge_gallery(media.get("gallery"), incoming)
    if incoming:
        kinds = {text(item.get("kind")) for item in incoming}
        previous = [item for item in as_list(media.get("visual_refs")) if text(item.get("kind")) not in kinds]
        media["visual_refs"] = previous + [
            {"kind": text(item.get("kind")), "url": text(item.get("url")), "title": text(item.get("title")), "query": text(item.get("query"))}
            for item in incoming
            if text(item.get("url"))
        ]
    payload["media"] = media
    record = dict(place)
    record["payload"] = payload
    return serialize(update_place(place_id, record))


def select_place_gallery(place_id: int, item_id: str) -> dict:
    place = serialize(get_by_id(place_id))
    payload = normalize_payload(place)
    media = dict(payload.get("media") or {})
    media["gallery"] = select_gallery(media.get("gallery"), item_id)
    payload["media"] = media
    record = dict(place)
    record["payload"] = payload
    return serialize(update_place(place_id, record))


def apply_images(place_id: int, *, kind: str = "next", point_id: str = "", reference_ids=None) -> dict:
    place = serialize(get_by_id(place_id))
    payload = normalize_payload(place)
    kind = (kind or "next").lower()
    chosen = gallery_items_by_ids(place, reference_ids)
    target_label = ""
    if kind in ("next", "points") and not (kind == "point" and point_id):
        target = next_image_target(place, points_only=(kind == "points"))
        if not target:
            saved = serialize(get_by_id(place_id))
            saved["images"] = image_pack(saved)
            saved["image_job"] = None
            saved["image_remaining"] = 0
            return saved
        kind = target["kind"]
        point_id = target.get("point_id") or ""
        target_label = target.get("label") or ""
    errors = []
    generated_media = {}
    generated = []
    usages = []
    if kind not in ("points", "point"):
        try:
            generated_media = generate_place_images(place, kind=kind, refs=chosen or None)
            usages.extend(generated_media.pop("usages", []) or [])
        except ImageError as exc:
            errors.append(str(exc))
    if kind in ("point", "all", "both"):
        generated = generate_point_images(place, point_id=point_id if kind == "point" else "", refs=chosen or None)
        errors.extend(text(item.get("error")) for item in generated if item.get("error"))
        by_id = {text(item.get("id")): item for item in generated if item.get("image_url")}
        by_name = {text(item.get("name")).lower(): item for item in generated if item.get("image_url")}
        merged = []
        for item in payload.get("points") or []:
            match = by_id.get(text(item.get("id"))) or by_name.get(text(item.get("name")).lower())
            if match and match.get("image_url"):
                item = dict(item)
                item["image_url"] = match["image_url"]
                if match.get("usage"):
                    usages.append(
                        {
                            "step": "image-point",
                            "label": text(item.get("name")),
                            "usage": match.get("usage"),
                            "model": resolve_place_image_spec(place)[0],
                        }
                    )
            merged.append(item)
        payload["points"] = merged
        place["points"] = merged
        if not target_label and generated:
            target_label = text(generated[0].get("name"))
    media = dict(payload.get("media") or {})
    incoming_refs = generated_media.pop("visual_refs", None) or []
    incoming_gallery = generated_media.pop("gallery", None) or []
    if kind in ("point", "all", "both"):
        for item in generated if kind in ("point", "all", "both") else []:
            incoming_gallery.extend(as_list(item.get("gallery")))
    media.update({key: value for key, value in generated_media.items() if value and key != "usages"})
    if incoming_refs:
        kinds = {text(item.get("kind")) for item in incoming_refs}
        previous = [
            item for item in as_list(media.get("visual_refs")) if text(item.get("kind")) not in kinds
        ]
        media["visual_refs"] = previous + incoming_refs
    if incoming_gallery:
        media["gallery"] = merge_gallery(media.get("gallery"), incoming_gallery)
    model, resolution = resolve_place_image_spec(place)
    media["image_model"] = model
    media["image_resolution"] = resolution
    pack = image_pack(place, generated=generated_media, errors=errors)
    media["images"] = (
        ([{"id": "hero", "role": "hero", "url": pack["hero_url"]}] if pack.get("hero_url") else [])
        + [{"id": item["id"], "role": "point", "url": item["url"]} for item in pack.get("points") or []]
    )
    payload["media"] = media
    pipeline = dict(payload.get("pipeline") or {})
    steps = list(pipeline.get("steps") or [])
    if "images" not in steps:
        steps.append("images")
    pipeline["steps"] = steps
    models = dict(pipeline.get("models") or {})
    models["image"] = model
    pipeline["models"] = models
    if errors:
        pipeline["warnings"] = list(pipeline.get("warnings") or []) + errors
    payload["pipeline"] = pipeline
    for item in usages:
        _record_cost(
            payload,
            step=text(item.get("step")) or "image",
            model=text(item.get("model")) or model,
            usage=item.get("usage"),
            label=text(item.get("label")) or target_label or "Imagem",
        )
    record = dict(place)
    record["payload"] = payload
    saved = serialize(update_place(place_id, record))
    saved["images"] = image_pack(saved, generated=generated_media, errors=errors)
    saved["image_job"] = {"kind": kind, "point_id": point_id, "label": target_label}
    saved["image_remaining"] = len(image_queue(saved))
    return saved


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
        row = dict(item)
        for key in ("image_url", "note", "commercial", "reach", "formats", "audiences", "apps", "portals"):
            if old.get(key) and not row.get(key):
                row[key] = old[key]
        merged.append(row)
    return merged


def merge_enrich_points(points: list, extras: list) -> list:
    by_id = {text(item.get("id")): item for item in extras or [] if text(item.get("id"))}
    by_name = {
        text(item.get("name")).lower(): item
        for item in extras or []
        if text(item.get("name"))
    }
    merged = []
    for item in points or []:
        extra = by_id.get(text(item.get("id"))) or by_name.get(text(item.get("name")).lower()) or {}
        row = dict(item)
        if extra.get("apps"):
            row["apps"] = extra["apps"]
        if extra.get("portals"):
            row["portals"] = extra["portals"]
        if extra.get("formats"):
            row["formats"] = extra["formats"]
        merged.append(row)
    return merged


def apply_enrich(place_id: int) -> dict:
    row = get_by_id(place_id)
    place = serialize(row)
    result = enrich_points(place)
    if not result.get("points") and not result.get("lead"):
        raise ResearchError("A pesquisa não devolveu apps nem portais. Tente de novo.")
    payload = normalize_payload(place)
    previous_inventory = dict(payload.get("inventory") or {})
    if result.get("points"):
        payload["points"] = merge_enrich_points(payload.get("points") or [], result.get("points") or [])
    payload["inventory"] = {
        "lead": result.get("lead") or previous_inventory.get("lead") or "",
        "notes": result.get("notes") or previous_inventory.get("notes") or "",
        "model": text(result.get("model")) or previous_inventory.get("model") or "",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    pipeline = dict(payload.get("pipeline") or {})
    steps = list(pipeline.get("steps") or [])
    if "enrich" not in steps:
        steps.append("enrich")
    pipeline["steps"] = steps
    models = dict(pipeline.get("models") or {})
    models["enrich"] = text(result.get("model"))
    pipeline["models"] = models
    payload["pipeline"] = pipeline
    _record_cost(
        payload,
        step="enrich",
        model=text(result.get("model")),
        usage=result.get("usage"),
        label="Enriquecer pontos",
    )
    record = dict(row)
    record["payload"] = payload
    return serialize(update_place(place_id, record))


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
