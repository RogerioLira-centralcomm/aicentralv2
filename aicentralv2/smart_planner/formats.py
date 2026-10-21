"""Formatos por canal e rede de portais.

Canal é o ambiente de compra (Rede de portais e sites, Meta, YouTube, Netflix...). Formato é o
que se veicula nele: display IAB, vídeo, native, rich media e interativos. Interativos não são canal:
são tipos de formato, com custo agregado na proposta. A Rede de portais e sites reúne os portais do
catálogo (mais de mil); G1, UOL, CNN e os demais são sites da rede, não canais separados.

O catálogo de formatos é o do Cadu (``cadu_formatos``). Se o banco não responder, um conjunto mínimo
embutido mantém o planejamento funcionando.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from .catalog import CHANNEL_CATALOG, PORTAL_CHANNELS
from .helpers import as_dict, as_list, text

logger = logging.getLogger(__name__)

NETWORK_CHANNEL = "dv360"  # Rede de portais e sites

# Canal do Smart Planner -> plataformas do catálogo de formatos (cadu_formatos.plataforma_slug).
CHANNEL_FORMAT_PLATFORMS = {
    "dv360": ("programatica_iab", "interativos"),
    "amazon_ads": ("programatica_iab",),
    "google_ads": ("google_ads",),
    "youtube": ("google_ads",),
    "meta_ads": ("meta_ads",),
    "tiktok": ("tiktok_ads",),
    "linkedin": ("linkedin_ads",),
    "spotify": ("spotify_ads",),
    "netflix": ("netflix",),
    "prime_video": ("prime_video",),
}

# Tipos que carregam custo agregado: o formato é produzido e vendido à parte da mídia.
AGGREGATED_TYPES = {"display_interativo", "rich-media", "rich media", "interactive"}

# Ids antigos dos formatos interativos -> slug do catálogo.
LEGACY_FORMAT_ALIASES = {
    "hotspot": "interativo-hotspots-shop-the-look",
    "cartas": "interativo-cards",
    "quiz": "interativo-quiz",
    "cube": "cube",
    "scratch": "scratch",
    "360": "viewer-360",
    "countdown": "countdown",
    "video": "video-interactive",
}

# Plano sem banco: o essencial da rede de portais (IAB) e dos interativos mais usados.
_STATIC = (
    ("medium-rectangle-300x250", "Medium Rectangle (300x250)", "display", "300x250 pixels", False, "programatica_iab"),
    ("leaderboard-728x90", "Leaderboard (728x90)", "display", "728x90 pixels", False, "programatica_iab"),
    ("billboard-970x250", "Billboard (970x250)", "display", "970x250 pixels", False, "programatica_iab"),
    ("half-page-300x600", "Half Page (300x600)", "display", "300x600 pixels", False, "programatica_iab"),
    ("smartphone-banner-320x50", "Smartphone Banner (320x50)", "display", "320x50 pixels", False, "programatica_iab"),
    ("native-in-feed", "Native In-Feed", "native", "Imagem 1200x627", False, "programatica_iab"),
    ("pre-roll-vast", "Pre-Roll (VAST)", "video", "1920x1080 (16:9)", False, "programatica_iab"),
    ("outstream-video", "Outstream Video", "video", "1920x1080 (16:9)", False, "programatica_iab"),
    ("interativo-hotspots-shop-the-look", "Hotspots (Shop the Look)", "display_interativo", "IAB desktop e mobile", True, "interativos"),
    ("interativo-cards", "Cards", "display_interativo", "IAB desktop e mobile", True, "interativos"),
    ("interativo-quiz", "Quiz", "display_interativo", "IAB desktop e mobile", True, "interativos"),
    ("cube", "Cube", "display_interativo", "IAB desktop e mobile", True, "interativos"),
    ("scratch", "Scratch", "rich-media", "IAB desktop e mobile", True, "interativos"),
    ("viewer-360", "360° Viewer", "rich-media", "IAB desktop e mobile", True, "interativos"),
    ("countdown", "Countdown Timer", "rich-media", "IAB desktop e mobile", True, "interativos"),
    ("video-interactive", "Video Interactive", "rich-media", "IAB desktop e mobile", True, "interativos"),
)

_CACHE: dict = {"at": 0.0, "rows": None}
_TTL = 600


def _static_rows() -> list[dict]:
    return [
        {"id": slug, "name": name, "type": kind, "dimensions": dims, "interactive": interactive, "platform": platform}
        for slug, name, kind, dims, interactive, platform in _STATIC
    ]


def _load() -> list[dict]:
    try:
        from ..cadu_family import repository

        rows = repository.rows(
            """SELECT slug, nome, tipo, dimensoes, is_interativo, plataforma_slug, duracao,
                      descricao, categoria_criativa, dados_extras
                 FROM cadu_formatos WHERE is_active IS TRUE ORDER BY ordem NULLS LAST, nome"""
        )
    except Exception:
        logger.warning("Catálogo de formatos indisponível; usando o conjunto mínimo.", exc_info=True)
        return _static_rows()
    out = []
    for row in rows or []:
        slug = text(row.get("slug"))
        if not slug:
            continue
        out.append({
            "id": slug,
            "name": text(row.get("nome")),
            "type": text(row.get("tipo")),
            "dimensions": text(row.get("dimensoes")),
            "interactive": bool(row.get("is_interativo")),
            "platform": text(row.get("plataforma_slug")),
            "duration": text(row.get("duracao")),
            **_showcase(row),
        })
    return out or _static_rows()


def _showcase(row: dict) -> dict:
    """Descrição, categoria criativa, imagem e peça de teste: o que a vitrine de interativos do Planner mostra."""
    from ..cadu_family.repository import _current_creative_url

    extras = row.get("dados_extras") or {}
    if isinstance(extras, str):
        try:
            extras = json.loads(extras)
        except ValueError:
            extras = {}
    extras = extras if isinstance(extras, dict) else {}
    segment = row.get("categoria_criativa") or extras.get("segmento") or ""
    if isinstance(segment, list):
        segment = segment[0] if segment else ""
    creative = next((extras.get(key) for key in ("creative_url", "preview_url", "link", "url") if extras.get(key)), "")
    return {
        "description": text(row.get("descricao")),
        "category": text(segment)[:100],
        "image_url": _current_creative_url(extras.get("imagem_referencia", "")),
        "creative_url": _current_creative_url(creative),
    }


def catalog() -> list[dict]:
    """Formatos ativos do catálogo, com cache curto para não consultar o banco a cada tela."""
    now = time.monotonic()
    if _CACHE["rows"] is None or now - _CACHE["at"] > _TTL:
        _CACHE["rows"] = _load()
        _CACHE["at"] = now
    return _CACHE["rows"]


def reset_cache() -> None:
    _CACHE["rows"], _CACHE["at"] = None, 0.0


def decorate(row: dict) -> dict:
    kind = text(row.get("type")).lower()
    return {**row, "aggregated_cost": bool(row.get("interactive")) or kind in AGGREGATED_TYPES}


# Plataformas que já têm canal próprio no Smart Planner.
_MAPPED_PLATFORMS = {platform for platforms in CHANNEL_FORMAT_PLATFORMS.values() for platform in platforms}


def formats_for_channel(channel_id: str) -> list[dict]:
    """Formatos que o canal veicula. A rede de portais leva também os interativos de plataforma sem
    canal próprio (rich media sem plataforma, por exemplo): interativo roda em portal."""
    channel_id = text(channel_id)
    platforms = CHANNEL_FORMAT_PLATFORMS.get(channel_id, ())
    network = channel_id == NETWORK_CHANNEL
    return [
        decorate(row) for row in catalog()
        if row.get("platform") in platforms
        or (network and row.get("interactive") and row.get("platform") not in _MAPPED_PLATFORMS)
    ]


def by_id(slug: str) -> dict:
    wanted = text(slug)
    return next((decorate(row) for row in catalog() if row["id"] == wanted), {})


def _fold(value: Any) -> str:
    import re
    import unicodedata

    plain = unicodedata.normalize("NFKD", text(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", plain)).strip()


def resolve_id(value: Any, allowed: set[str] | None = None) -> str:
    """Slug do catálogo para um valor vindo do briefing, da tela ou de plano antigo.

    Aceita o slug, o id antigo (hotspot, cartas), o nome exato e, por último, um nome parcial que
    aponte para um único formato ("Hotspots" -> "Hotspots (Shop the Look)").
    """
    raw = text(value).lower()
    if not raw:
        return ""
    rows = [row for row in catalog() if allowed is None or row["id"] in allowed]
    ids = {row["id"] for row in rows}
    slug = LEGACY_FORMAT_ALIASES.get(raw, raw)
    if slug in ids:
        return slug
    folded = _fold(raw)
    exact = [row["id"] for row in rows if _fold(row.get("name")) == folded or _fold(row["id"]) == folded]
    if exact:
        return exact[0]
    loose = [row["id"] for row in rows if len(folded) >= 4 and (folded in _fold(row.get("name")) or _fold(row.get("name")) in folded)]
    return loose[0] if len(loose) == 1 else ""


def particulars(row: dict) -> dict:
    """O que o plano conta de um interativo escolhido: mecânica, categoria e a peça de teste."""
    if not row.get("interactive"):
        return {}
    return {key: value for key, value in (
        ("interativo", True),
        ("categoria", text(row.get("category"))),
        ("descricao", text(row.get("description"))[:600]),
        ("demo", text(row.get("creative_url"))),
    ) if value}


def interactive_details(formats_by_channel: Any) -> list[dict]:
    """Interativos escolhidos no plano, sem repetir, com os detalhes do catálogo.

    Planos gerados antes de a página guardar os detalhes trazem só o nome: o catálogo completa.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for items in as_dict(formats_by_channel).values():
        for item in as_list(items):
            item = as_dict(item)
            slug = text(item.get("id")) or resolve_id(item.get("nome"))
            row = by_id(slug) if slug else {}
            if not (item.get("interativo") or row.get("interactive")):
                continue
            key = slug or text(item.get("nome"))
            if not key or key in seen:
                continue
            seen.add(key)
            extra = particulars(row) if row else {}
            out.append({
                "nome": text(item.get("nome")) or text(row.get("name")),
                "dimensoes": text(item.get("dimensoes")) or text(row.get("dimensions")),
                "categoria": text(item.get("categoria")) or extra.get("categoria", ""),
                "descricao": text(item.get("descricao")) or extra.get("descricao", ""),
                "demo": text(item.get("demo")) or extra.get("demo", ""),
            })
    return out


def channel_allows(channel_id: str, slug: str) -> bool:
    return any(row["id"] == slug for row in formats_for_channel(channel_id))


def display_name(slug: str) -> str:
    row = by_id(slug)
    return text(row.get("name")) or slug


def aggregated_names(slugs) -> list[str]:
    """Nomes dos formatos com custo agregado, sem repetir e na ordem recebida."""
    names: list[str] = []
    for slug in as_list(slugs):
        row = by_id(text(slug))
        if row.get("aggregated_cost") and row["name"] not in names:
            names.append(row["name"])
    return names


def migrate_campanha(campanha: Any) -> dict:
    """Leva planos antigos ao modelo atual: Interativos e portais soltos deixam de ser canais.

    - G1, UOL, R7, CNN e demais portais, e o canal Interativos, viram a Rede de portais e sites;
    - os pesos e valores deles somam no canal da rede;
    - os formatos interativos antigos passam a formatos do catálogo, nas táticas e no canal;
    - os portais retirados ficam como sites preferidos.
    Idempotente: um plano já migrado volta igual.
    """
    data = dict(as_dict(campanha))
    legacy = set(PORTAL_CHANNELS) | {"interativos"}
    canais = [text(key) for key in as_list(data.get("canais")) if text(key)]
    found = [key for key in canais if key in legacy]
    old_interativos = as_dict(data.get("interativos"))
    if not found and not as_list(old_interativos.get("formats")) and "interativos" not in data:
        return data

    def merge_ids(items):
        out: list[str] = []
        for key in items:
            key = NETWORK_CHANNEL if key in legacy else key
            if key not in out:
                out.append(key)
        return out

    if found and NETWORK_CHANNEL not in canais:
        position = min(canais.index(key) for key in found)
        canais[position] = NETWORK_CHANNEL
    data["canais"] = merge_ids(canais)

    mix = dict(as_dict(data.get("mix")))
    if as_list(mix.get("weights")):
        merged: dict[str, float] = {}
        order: list[str] = []
        for item in as_list(mix.get("weights")):
            row = as_dict(item)
            key = NETWORK_CHANNEL if text(row.get("id")) in legacy else text(row.get("id"))
            if key not in merged:
                order.append(key)
            merged[key] = merged.get(key, 0.0) + float(row.get("pct") or 0)
        mix["weights"] = [
            {"id": key, "label": text((CHANNEL_CATALOG.get(key) or {}).get("label")) or key,
             "group": text((CHANNEL_CATALOG.get(key) or {}).get("group")), "pct": round(merged[key], 2) if merged[key] % 1 else int(merged[key])}
            for key in order
        ]
        data["mix"] = mix
    split = as_dict(data.get("canais_verba"))
    if split:
        money: dict[str, int] = {}
        for key, value in split.items():
            target = NETWORK_CHANNEL if text(key) in legacy else text(key)
            money[target] = money.get(target, 0) + int(value or 0)
        data["canais_verba"] = money

    formats = [resolve_id(item) for item in as_list(old_interativos.get("formats"))]
    formats = [slug for slug in dict.fromkeys(formats) if slug]
    by_channel = {key: [text(s) for s in as_list(value)] for key, value in as_dict(data.get("formatos")).items()}
    if formats:
        by_channel[NETWORK_CHANNEL] = list(dict.fromkeys(by_channel.get(NETWORK_CHANNEL, []) + formats))
    if by_channel:
        data["formatos"] = by_channel

    taticas = []
    for item in as_list(data.get("taticas")):
        row = dict(as_dict(item))
        row["canais"] = merge_ids([text(key) for key in as_list(row.get("canais"))])
        row["formatos"] = list(dict.fromkeys(
            "dco" if text(f).lower() == "dco" else (resolve_id(f) or text(f)) for f in as_list(row.get("formatos"))
        ))
        taticas.append(row)
    if taticas:
        data["taticas"] = taticas

    sites = [text((CHANNEL_CATALOG.get(key) or {}).get("label")) for key in found if key in PORTAL_CHANNELS]
    portais = dict(as_dict(data.get("portais")))
    if sites:
        portais["sites_preferidos"] = list(dict.fromkeys(as_list(portais.get("sites_preferidos")) + sites))
        data["portais"] = portais
    data.pop("interativos", None)
    return data
