"""Imagens do place e dos pontos via OpenRouter, modelo por aeroporto."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import unicodedata

from flask import current_app, has_app_context

from ..services.openrouter_service import generate_image, resolve_image_model
from .schema import as_dict, as_list, text
from .visual_refs import (
    collect_visual_refs,
    materialize_reference_urls,
    reference_urls,
    selected_gallery_refs,
)

GROUNDING = (
    " Use the approved reference photos as the source image: preserve their architecture, "
    "camera angle, composition, materials, surroundings and overall color temperature. "
    "Apply only restrained editorial enhancement (exposure, contrast, clarity and light cleanup). "
    "Do not invent, remove or relocate buildings, people, signs, roads or landscape elements; "
    "do not turn the place into a generic mega-hub or a stylized rendering."
)

logger = logging.getLogger(__name__)

# Confins e SDU ficam no GPT Image 2; Congonhas no Nano Banana Pro 1K;
# Galeão no Seedream 5 Lite 2K. PLACES_IMAGE_MODEL sobrescreve o mapa.
IMAGE_SPECS = {
    "CNF": ("openai/gpt-image-2", "2K"),
    "SDU": ("openai/gpt-image-2", "2K"),
    "CGH": ("google/gemini-3-pro-image", "1K"),
    "GIG": ("bytedance-seed/seedream-5-0-lite", "2K"),
}


def resolve_place_image_spec(place: dict) -> tuple[str, str]:
    code = text(place.get("code")).upper()
    default_model, default_res = IMAGE_SPECS.get(code, ("openai/gpt-image-2", "2K"))
    if os.getenv("PLACES_IMAGE_FORCE") == "1":
        return (
            os.getenv("PLACES_IMAGE_MODEL") or default_model,
            os.getenv("PLACES_IMAGE_RESOLUTION") or default_res,
        )
    return default_model, default_res


class ImageError(RuntimeError):
    pass


def point_keys(point: dict) -> set[str]:
    name = text(point.get("name"))
    pid = text(point.get("id"))
    keys = {name, pid, _slug(name), _slug(pid)}
    return {item.lower() for item in keys if item}


def point_matches(point: dict, wanted: str) -> bool:
    needle = text(wanted)
    if not needle:
        return True
    keys = point_keys(point)
    return needle.lower() in keys or _slug(needle) in keys


def next_image_target(place: dict, *, points_only: bool = False) -> dict | None:
    media = as_dict(place.get("media"))
    if not points_only:
        if not text(media.get("hero_url")):
            return {"kind": "hero", "point_id": "", "label": "Hero"}
        if not text(media.get("map_url")):
            return {"kind": "map", "point_id": "", "label": "Mapa"}
    for raw in as_list(place.get("points")):
        point = as_dict(raw)
        name = text(point.get("name"))
        if not name or text(point.get("image_url")):
            continue
        pid = text(point.get("id")) or _slug(name)
        return {"kind": "point", "point_id": pid, "label": name}
    return None


def image_queue(place: dict) -> list[dict]:
    jobs = []
    media = as_dict(place.get("media"))
    if not text(media.get("hero_url")):
        jobs.append({"kind": "hero", "point_id": "", "label": "Hero"})
    if not text(media.get("map_url")):
        jobs.append({"kind": "map", "point_id": "", "label": "Mapa"})
    for raw in as_list(place.get("points")):
        point = as_dict(raw)
        name = text(point.get("name"))
        if not name or text(point.get("image_url")):
            continue
        jobs.append({"kind": "point", "point_id": text(point.get("id")) or _slug(name), "label": name})
    return jobs


def resolve_generation_refs(
    place: dict,
    *,
    kind: str = "hero",
    point: dict | None = None,
    refs: list[dict] | None = None,
) -> list[dict]:
    if refs:
        return list(refs)
    picked = selected_gallery_refs(place, kind=kind, point=point)
    if picked:
        return picked
    return collect_visual_refs(place, kind=kind, point=point)


def generate_place_images(place: dict, *, kind: str = "hero", refs: list[dict] | None = None) -> dict:
    title = text(place.get("title")) or "place"
    city = text(place.get("city_label") or place.get("city"))
    code = text(place.get("code"))
    slug = _slug(place.get("slug") or title)
    kind = (kind or "hero").lower()
    neighborhoods = ", ".join(
        text(item) for item in as_list((as_dict(place.get("catchment")).get("neighborhoods"))) if text(item)
    )
    urls = {}
    usages = []
    if kind in ("hero", "both", "all"):
        refs = resolve_generation_refs(place, kind="hero", refs=refs)
        url, usage = _render(
            _hero_prompt(title, city, code),
            f"{slug}-hero",
            "16:9",
            place,
            refs=refs,
        )
        urls["hero_url"] = url
        usages.append({"step": "image-hero", "label": "Hero", "usage": usage})
        _attach_refs(urls, "hero", refs)
    if kind in ("og", "both", "all"):
        refs = resolve_generation_refs(place, kind="og", refs=refs if kind == "og" else None)
        url, usage = _render(
            (
                f"Premium share photo of {title} {code} in {city}, Brazil. "
                "Atmospheric real place, no text, no logos, no UI, 16:9."
            ),
            f"{slug}-og",
            "16:9",
            place,
            refs=refs,
        )
        urls["og_url"] = url
        usages.append({"step": "image-og", "label": "Cartão", "usage": usage})
        _attach_refs(urls, "og", refs)
    if kind in ("map", "all"):
        refs = resolve_generation_refs(place, kind="map", refs=refs if kind == "map" else None)
        url, usage = _render(
            (
                f"Photoreal oblique aerial map of {title} {code} in {city}, Brazil. "
                f"Recognizable terminal, roads and catchment neighborhoods {neighborhoods or city}. "
                "Documentary cartographic photography, true geography, no labels, no logos, no UI, 16:9."
            ),
            f"{slug}-map",
            "16:9",
            place,
            refs=refs,
        )
        urls["map_url"] = url
        usages.append({"step": "image-map", "label": "Mapa", "usage": usage})
        _attach_refs(urls, "map", refs)
    urls["usages"] = usages
    return urls


def generate_point_images(place: dict, *, point_id: str = "", refs: list[dict] | None = None) -> list[dict]:
    title = text(place.get("title")) or "place"
    city = text(place.get("city_label") or place.get("city"))
    slug = _slug(place.get("slug") or title)
    wanted = text(point_id)
    incoming_refs = refs
    generated = []
    for index, raw in enumerate(as_list(place.get("points"))):
        point = as_dict(raw)
        name = text(point.get("name"))
        if not name:
            continue
        pid = text(point.get("id")) or _slug(name)
        if wanted and not point_matches(point, wanted):
            continue
        kind = text(point.get("kind")) or "marco"
        prompt = _point_prompt(title, city, name, kind, point.get("note"))
        point_refs = resolve_generation_refs(place, kind="point", point=point, refs=incoming_refs)
        try:
            url, usage = _render(prompt, f"{slug}-{_slug(pid or name)}-pt", "4:3", place, refs=point_refs)
            generated.append(
                {
                    "id": pid,
                    "name": name,
                    "kind": kind,
                    "lat": point.get("lat"),
                    "lng": point.get("lng"),
                    "source": point.get("source"),
                    "note": point.get("note"),
                    "image_url": url,
                    "usage": usage,
                    "index": index,
                    "gallery": point_refs,
                }
            )
        except ImageError as exc:
            generated.append(
                {
                    "id": pid,
                    "name": name,
                    "kind": kind,
                    "error": str(exc),
                    "index": index,
                }
            )
        if wanted:
            break
    if wanted and not any(item.get("image_url") for item in generated):
        raise ImageError(generated[0].get("error") if generated else "Ponto não encontrado para gerar a imagem.")
    return generated


def _hero_prompt(title: str, city: str, code: str) -> str:
    specifics = {
        "CNF": (
            "Tancredo Neves / BH Airport Confins by Bacco: long horizontal white terminal, "
            "flat straight roof, two concrete control towers, glass curtain wall, elevated "
            "curbside and parking deck in cerrado hills at dusk. "
            "Forbidden: wavy parametric Hadid roof, Beijing Daxing, undulating canopy, generic mega-hub."
        ),
        "CGH": (
            "Congonhas urban airport in the middle of São Paulo: compact terminal, "
            "Avenida Washington Luís in front, one runway squeezed into Campo Belo rooftops. "
            "Forbidden: coastal airport, dual long runways in countryside."
        ),
        "SDU": (
            "Santos Dumont on Guanabara Bay: historic art-deco original terminal plus later "
            "glass additions, two parallel runways on the landfill, Centro of Rio behind. "
            "Forbidden: a single fantasy runway, Sugarloaf as the main subject, generic glass cathedral."
        ),
        "GIG": (
            "Galeão / Tom Jobim International on Ilha do Governador: large T2 glass terminal, "
            "two long runways (10/28 and 15/33) beside Guanabara Bay, access via Avenida "
            "Vinte de Janeiro. Forbidden: Santos Dumont downtown, a single short runway, "
            "Congonhas squeezed into city blocks."
        ),
        "DMM": (
            "Diamond Mall in Lourdes / Savassi, Belo Horizonte: compact Multiplan urban mall, "
            "stone and glass street facade on a city block, trees and traffic, dusk. "
            "Forbidden: geodesic glass dome, crystal polygon, generic luxury atrium, airport."
        ),
        "IGT": (
            "Iguatemi São Paulo on Faria Lima: low luxury mall with landscaped garden, "
            "white canopies, jacarandas and the Faria Lima towers behind, golden hour. "
            "Forbidden: generic marble hotel drop-off, a single glass box, airport."
        ),
        "IBI": (
            "Ibirapuera Park, São Paulo: Niemeyer's white Oca dome and the long concrete "
            "marquee by the lake, towers of Vila Mariana behind, late afternoon. "
            "Forbidden: a generic city park, tropical beach, invented sculpture."
        ),
        "EXP": (
            "Expominas in Gameleira, Belo Horizonte: white barrel-vault exhibition halls, "
            "wide empty forecourt, hills of the west region behind, overcast day. "
            "Forbidden: airport hangar, stadium, generic convention center in Dubai."
        ),
    }
    extra = specifics.get(code.upper(), "Architecture and setting as they really are.")
    return (
        f"Photoreal dusk exterior of {title} {code} in {city}, Brazil. {extra} "
        "Wide real place, people as they are, no text, no logos, no UI, cinematic, 16:9."
    )


def _point_prompt(title: str, city: str, name: str, kind: str, note) -> str:
    note = text(note)
    extra = f" {note}." if note else ""
    named = _named_scene(title, city, name)
    if named:
        body = named
    else:
        scenes = {
            "terminal": (
                f"Photoreal interior check-in hall of {title} airport, {city}, Brazil. "
                "Real materials, lighting and passengers as they are. Not a generic European hub."
            ),
            "bairro": (
                f"Photoreal street-level view of {name} near {title}, {city}, Brazil. "
                "How the neighborhood actually looks on the ground, facades, sidewalk, daylight. "
                "No runway, no aerial, no airplane wing."
            ),
            "pessoas": (
                f"Photoreal street scene of people in {name} near {title}, {city}, Brazil. "
                "Everyday circulation, not a posed stock photo."
            ),
            "densidade": (
                f"Photoreal urban fabric of {name} near {title}, {city}, Brazil. "
                "Buildings, streets and real density from eye level. No aerial of the airport."
            ),
            "marco": (
                f"Photoreal view of the landmark {name} near {title}, {city}, Brazil. "
                "How it looks in place, not a postcard collage."
            ),
            "mobilidade": (
                f"Photoreal access and mobility around {name} at {title}, {city}, Brazil. "
                "Roads, drop-off or transit as they really are."
            ),
            "embarque": (
                f"Photoreal departures hall at {title} airport, {city}, Brazil. "
                "Check-in to gate, queues and boarding as they really are."
            ),
            "premium": (
                f"Photoreal international area at {title} airport, {city}, Brazil. "
                "Immigration desks or duty-free approach, fewer people, real materials. "
                "Not a luxury hotel lobby."
            ),
            "halo": (
                f"Photoreal street-level view of {name} near {title}, {city}, Brazil. "
                "Neighborhood, shops and sidewalk. Forbidden: airport aerial, runway, airplane wing."
            ),
        }
        body = scenes.get(kind, scenes["marco"])
    return (
        f"{body}{extra} Documentary photography, no text, no logos, no UI, no maps overlay, 4:3."
    )


def _named_scene(title: str, city: str, name: str) -> str:
    key = _slug(name)
    scenes = {
        "washington-luis": (
            f"Photoreal street-level view of Avenida Washington Luís in front of Congonhas Airport, "
            f"{city}, Brazil. Taxi drop-off, buses, wet asphalt, the airport terminal facade across "
            "the avenue. Eye level from the sidewalk. Forbidden: boarding gate, jet bridge, runway interior."
        ),
        "moema": (
            f"Photoreal street-level view of Moema, São Paulo, Brazil, near Congonhas. "
            "Tree-lined sidewalk, mid-rise residential towers, shops and a corner bakery, daylight. "
            "Forbidden: airport runway, airplane wing, aerial of Congonhas."
        ),
        "campo-belo": (
            f"Photoreal street-level view of Campo Belo, São Paulo, Brazil, next to Congonhas. "
            "Low-rise houses, quiet residential street, parked cars, daylight. "
            "Forbidden: runway aerial, airplane wing."
        ),
        "centro": (
            f"Photoreal street-level view of Centro, Rio de Janeiro, near Santos Dumont. "
            "Avenida Rio Branco or Cinelândia, historic facades, office workers, daylight. "
            "Forbidden: aerial of the airport, runway into the bay, single-runway fantasy."
        ),
        "gloria": (
            f"Photoreal street-level view of Glória, Rio de Janeiro, Brazil. "
            "Hotels, Aterro do Flamengo trees, orla and city traffic. The bay may appear in the "
            "background. Forbidden: invented single-runway airport as the subject."
        ),
        "mg-010": (
            f"Photoreal highway MG-010 through cerrado hills north of Confins, Minas Gerais, Brazil. "
            "Asphalt, trucks, dry vegetation. Forbidden: airport terminal, aerial of runways."
        ),
        "vlt": (
            f"Photoreal VLT Carioca tram stop next to Santos Dumont, Rio de Janeiro, Brazil. "
            "Yellow-and-white tram, taxis, the bay and city hill behind, street level."
        ),
        "vinte-de-janeiro": (
            f"Photoreal street-level view of Avenida Vinte de Janeiro, the access road to "
            f"Galeão Airport on Ilha do Governador, {city}, Brazil. Cars, buses, tropical "
            "vegetation, airport signs in the distance. Forbidden: runway aerial, terminal hall."
        ),
        "jardim-guanabara": (
            f"Photoreal street-level view of Jardim Guanabara, Ilha do Governador, Rio de Janeiro. "
            "Residential streets, mid-rise buildings, trees, neighborhood shops, daylight. "
            "Forbidden: airport runway, airplane wing, aerial of Galeão."
        ),
        "portuguesa": (
            f"Photoreal street-level view of Portuguesa, Ilha do Governador, Rio de Janeiro. "
            "Local commerce, sidewalks, everyday traffic. Forbidden: airport aerial, runway."
        ),
    }
    return scenes.get(key, "")


def _attach_refs(urls: dict, kind: str, refs: list[dict]) -> None:
    packed = []
    gallery = []
    for item in refs:
        url = text(item.get("url") or item.get("source_url"))
        if not url:
            continue
        packed.append(
            {
                "kind": kind,
                "url": url,
                "title": text(item.get("title")),
                "query": text(item.get("query")),
            }
        )
        row = dict(item)
        row["kind"] = kind
        gallery.append(row)
    if packed:
        urls.setdefault("visual_refs", []).extend(packed)
        urls.setdefault("gallery", []).extend(gallery)


def _render(
    prompt: str,
    stem: str,
    aspect_ratio: str,
    place: dict | None = None,
    refs: list[dict] | None = None,
) -> tuple[str, dict]:
    model, resolution = resolve_place_image_spec(place or {})
    images = materialize_reference_urls(reference_urls(refs or []))
    if images:
        prompt = f"{prompt}{GROUNDING}"
    try:
        result = generate_image(
            prompt,
            aspect_ratio=aspect_ratio,
            quality="high",
            output_format="png",
            resolution=resolution,
            model=model or resolve_image_model(),
            input_references=images or None,
        )
    except Exception as exc:
        raise ImageError("Não foi possível gerar a imagem do place.") from exc
    encoded = result.get("b64_json")
    if not encoded:
        raise ImageError("A geração não devolveu imagem.")
    raw = base64.b64decode(encoded)
    digest = hashlib.sha1(raw).hexdigest()[:8]
    filename = f"{stem}-{digest}.png"
    path = os.path.join(_art_dir(), filename)
    with open(path, "wb") as handle:
        handle.write(raw)
    logger.info("Imagem de place gravada: %s", filename)
    return f"/static/images/places/generated/{filename}", result.get("usage") or {}


def _art_dir() -> str:
    if has_app_context() and current_app.static_folder:
        root = current_app.static_folder
    else:
        root = os.path.join(os.path.dirname(__file__), "..", "static")
    dest = os.path.abspath(os.path.join(root, "images", "places", "generated"))
    os.makedirs(dest, exist_ok=True)
    return dest


def _slug(value: str) -> str:
    folded = unicodedata.normalize("NFKD", text(value).lower())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return (slug or "place")[:40]
