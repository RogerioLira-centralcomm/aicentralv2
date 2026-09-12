"""Imagens do place e dos pontos via GPT Image 2."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re

from flask import current_app, has_app_context

from ..services.openrouter_service import generate_image, resolve_image_model
from .schema import as_dict, as_list, text

logger = logging.getLogger(__name__)


class ImageError(RuntimeError):
    pass


def generate_place_images(place: dict, *, kind: str = "both") -> dict:
    title = text(place.get("title")) or "place"
    city = text(place.get("city_label") or place.get("city"))
    code = text(place.get("code"))
    slug = _slug(place.get("slug") or title)
    kind = (kind or "both").lower()
    neighborhoods = ", ".join(
        text(item) for item in as_list((as_dict(place.get("catchment")).get("neighborhoods"))) if text(item)
    )
    urls = {}
    if kind in ("hero", "both", "all"):
        urls["hero_url"] = _render(
            (
                f"Photoreal dusk exterior of {title} {code} in {city}, Brazil. "
                "Wide real place, people and architecture as they are, no text, no logos, no UI, cinematic, 16:9."
            ),
            f"{slug}-hero",
            "16:9",
        )
    if kind in ("og", "both", "all"):
        urls["og_url"] = _render(
            (
                f"Premium share photo of {title} {code} in {city}, Brazil. "
                "Atmospheric real place, no text, no logos, no UI, 16:9."
            ),
            f"{slug}-og",
            "16:9",
        )
    if kind in ("map", "all"):
        urls["map_url"] = _render(
            (
                f"Photoreal oblique aerial map of {title} {code} in {city}, Brazil. "
                f"Recognizable terminal, roads and catchment neighborhoods {neighborhoods or city}. "
                "Documentary cartographic photography, true geography, no labels, no logos, no UI, 16:9."
            ),
            f"{slug}-map",
            "16:9",
        )
    return urls


def generate_point_images(place: dict, *, point_id: str = "") -> list[dict]:
    title = text(place.get("title")) or "place"
    city = text(place.get("city_label") or place.get("city"))
    slug = _slug(place.get("slug") or title)
    wanted = text(point_id)
    generated = []
    for index, raw in enumerate(as_list(place.get("points"))):
        point = as_dict(raw)
        name = text(point.get("name"))
        if not name:
            continue
        pid = text(point.get("id")) or _slug(name)
        if wanted and wanted not in (pid, name):
            continue
        kind = text(point.get("kind")) or "marco"
        prompt = _point_prompt(title, city, name, kind, point.get("note"))
        url = _render(prompt, f"{slug}-{_slug(pid or name)}-pt", "4:3")
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
                "index": index,
            }
        )
        if wanted:
            break
    if wanted and not generated:
        raise ImageError("Ponto não encontrado para gerar a imagem.")
    return generated


def _point_prompt(title: str, city: str, name: str, kind: str, note) -> str:
    note = text(note)
    extra = f" {note}." if note else ""
    scenes = {
        "terminal": (
            f"Photoreal interior of {name} at {title}, {city}, Brazil. "
            "Check-in hall, real materials, lighting and passengers as they are."
        ),
        "bairro": (
            f"Photoreal street-level view of {name} near {title}, {city}, Brazil. "
            "How the neighborhood actually looks on the ground, facades, sidewalk, daylight."
        ),
        "pessoas": (
            f"Photoreal street scene of people in {name} near {title}, {city}, Brazil. "
            "Everyday circulation, not a posed stock photo."
        ),
        "densidade": (
            f"Photoreal urban fabric of {name} near {title}, {city}, Brazil. "
            "Buildings, streets and real density from eye level."
        ),
        "marco": (
            f"Photoreal view of the landmark {name} near {title}, {city}, Brazil. "
            "How it looks in place, not a postcard collage."
        ),
        "mobilidade": (
            f"Photoreal access and mobility around {name} at {title}, {city}, Brazil. "
            "Roads, drop-off or transit as they really are."
        ),
        "halo": (
            f"Photoreal surrounding area of {name} near {title}, {city}, Brazil. "
            "The halo around the place, not the terminal interior."
        ),
    }
    body = scenes.get(kind, scenes["marco"])
    return (
        f"{body}{extra} Documentary photography, no text, no logos, no UI, no maps overlay, 4:3."
    )


def _render(prompt: str, stem: str, aspect_ratio: str) -> str:
    try:
        result = generate_image(
            prompt,
            aspect_ratio=aspect_ratio,
            quality="high",
            output_format="png",
            resolution="2K",
            model=os.getenv("PLACES_IMAGE_MODEL") or resolve_image_model(),
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
    return f"/static/images/places/generated/{filename}"


def _art_dir() -> str:
    if has_app_context() and current_app.static_folder:
        root = current_app.static_folder
    else:
        root = os.path.join(os.path.dirname(__file__), "..", "static")
    dest = os.path.abspath(os.path.join(root, "images", "places", "generated"))
    os.makedirs(dest, exist_ok=True)
    return dest


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text(value).lower()).strip("-")
    return (slug or "place")[:40]
