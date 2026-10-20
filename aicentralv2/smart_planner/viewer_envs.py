"""Ambientes de mídia do Cadu Studio nos mockups do plano.

O Studio cadastra, em cx_creative_viewer_profiles, como cada veículo se parece: paleta, menu,
fileira do catálogo (Netflix, Disney+, HBO Max, Prime Video), home de notícia (g1, CNN, SBT News)
e o feed das redes (Instagram, Facebook, TikTok, YouTube, LinkedIn). O plano usa esses dados
para a tela do canal ficar parecida com a do veículo. Sem banco, os mockups seguem genéricos.

Os formatos e tamanhos de cada tela vêm do registro de formatos do Studio.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from ..creative_format_registry import entry as format_entry
from .helpers import as_dict, as_list, text

logger = logging.getLogger(__name__)

HEX = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")
CACHE_SECONDS = 600
_CACHE: dict = {"at": 0.0, "envs": {}}

# Canal do plano → ambiente do Studio.
CHANNEL_ENV = {
    "netflix": "netflix", "disney": "disney-plus", "hbo_max": "hbo-max", "prime_video": "prime-video",
    "meta_ads": "instagram", "tiktok": "tiktok", "youtube": "youtube", "linkedin": "linkedin",
    "g1": "g1", "cnn": "cnn-brasil", "sbt": "sbt-news",
}
# Portal do recorte da Rede de portais → ambiente do Studio.
SITE_ENV = {"g1": "g1", "cnn": "cnn-brasil", "cnn brasil": "cnn-brasil", "sbt news": "sbt-news", "sbt": "sbt-news"}

# Formatos de cada tela, pelo registro do Studio; o nome fica em português.
FORMAT_KEYS = {
    "tv": ("video-linear-15",),
    "portal": ("iab-billboard", "iab-medium"),
    "social": ("feed-4x5",),
    "vertical": ("reels-9x16",),
}
FORMAT_KEYS_BY_CHANNEL = {"linkedin": ("feed-1x1",), "youtube": ("youtube-infeed",)}
FORMAT_NAMES = {
    "video-linear-15": "Vídeo 15s", "iab-billboard": "Billboard", "iab-medium": "Retângulo médio",
    "feed-4x5": "Feed 4:5", "feed-1x1": "Feed 1:1", "reels-9x16": "Vertical 9:16", "youtube-infeed": "In-feed 16:9",
}


def _palette(raw: Any) -> dict:
    return {key: text(value) for key, value in as_dict(raw).items() if HEX.match(text(value))}


def _static(value: Any) -> str:
    url = text(value)
    return url if url.startswith("/static/") else ""


def _env(row: dict) -> dict:
    shell = as_dict(row.get("shell_spec"))
    sections = [as_dict(s) for s in as_list(shell.get("sections"))]
    items = [as_dict(i) for s in sections for i in as_list(s.get("items"))]
    hero = as_dict(shell.get("hero"))
    return {
        "slug": text(row.get("slug")),
        "name": text(row.get("name")),
        "kind": text(row.get("viewer_kind")),
        "logo": _static(row.get("logo_asset_ref")),
        "palette": _palette(row.get("palette")),
        "nav": [text(n) for n in as_list(shell.get("nav")) if text(n)][:5],
        "row_title": text(sections[0].get("title")) if sections else "",
        # Fileira do catálogo: a tira de pôsteres do primeiro bloco.
        "catalog": next((_static(i.get("image")) for i in items if _static(i.get("image"))), ""),
        "hero": {"title": text(hero.get("title"))[:90], "eyebrow": text(hero.get("eyebrow")), "image": _static(hero.get("image"))},
        "news": [
            {"title": text(i.get("title"))[:80], "image": _static(i.get("image")), "category": text(i.get("category"))}
            for i in items if text(i.get("title")) and _static(i.get("image"))
        ][:2],
    }


def load(force: bool = False) -> dict:
    """Ambientes ativos do Studio por slug, guardados por dez minutos; falha vira {}."""
    now = time.monotonic()
    if not force and _CACHE["envs"] and now - _CACHE["at"] < CACHE_SECONDS:
        return _CACHE["envs"]
    try:
        from ..db import get_db

        with get_db().cursor() as cursor:
            cursor.execute(
                """
                SELECT slug, name, viewer_kind, logo_asset_ref, palette, shell_spec
                  FROM cx_creative_viewer_profiles
                 WHERE is_active = TRUE
                """
            )
            envs = {text(row["slug"]): _env(dict(row)) for row in cursor.fetchall()}
    except Exception:
        logger.exception("Falha ao ler os ambientes de mídia do Studio")
        return _CACHE["envs"]
    _CACHE.update(at=now, envs=envs)
    return envs


def env_for(channel_id: str, site: str, envs: dict) -> dict:
    envs = as_dict(envs)
    slug = SITE_ENV.get(text(site).lower()) if site else ""
    return as_dict(envs.get(slug or CHANNEL_ENV.get(text(channel_id), "")))


def formats_for(kind: str, channel_id: str) -> list[dict]:
    out = []
    for key in FORMAT_KEYS_BY_CHANNEL.get(text(channel_id)) or FORMAT_KEYS.get(kind, ()):
        item = format_entry(key)
        if item:
            out.append({"key": key, "name": FORMAT_NAMES.get(key, text(item.get("label"))), "size": f"{item['width']}×{item['height']}"})
    return out
