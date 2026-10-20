"""Mockups dos canais nos slides: o criativo do plano dentro da tela onde ele vai aparecer.

Três telas, no estilo do visualizador de criativos do Workspace: TV (CTV e streaming), portal
(a Rede de portais e os sites de notícia, com leaderboard e retângulo médio) e celular (redes
sociais). As telas são desenhadas em CSS no próprio slide; não dependem de banco nem de imagem
externa. A logo do canal ou do maior portal do recorte entra na tela.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .catalog import CHANNEL_CATALOG, CHANNEL_LOGOS
from .helpers import as_dict, as_list, text

KIND_BY_GROUP = {"ctv": "tv", "video": "tv", "social": "social", "apps": "app", "audio": "audio"}
# Canais cuja tela não segue o grupo: vídeo vertical e app de mobilidade com mapa.
KIND_BY_CHANNEL = {"tiktok": "vertical", "kwai": "vertical", "twitch": "tv", "waze": "app"}

# Como o criativo entra em cada tela: o que o cliente precisa saber da adaptação.
PLACEMENT = {
    "tv": "Vídeo em tela cheia, entre conteúdos do streaming.",
    "portal": "Leaderboard e retângulo médio, ao lado da notícia.",
    "social": "Post patrocinado no feed, em formato 4:5.",
    "vertical": "Vídeo vertical 9:16 em tela cheia.",
    "app": "Banner no app durante a corrida ou o pedido.",
    "audio": "Spot de áudio com banner de apoio no player.",
}

# Logos de portais que já temos no projeto, pelo nome do site no catálogo de portais.
SITE_LOGOS = {
    "g1": CHANNEL_LOGOS.get("g1", ""),
    "uol": CHANNEL_LOGOS.get("uol", ""),
    "r7": CHANNEL_LOGOS.get("r7", ""),
    "cnn brasil": CHANNEL_LOGOS.get("cnn", ""),
    "cnn": CHANNEL_LOGOS.get("cnn", ""),
    "infomoney": CHANNEL_LOGOS.get("infomoney", ""),
    "ge": CHANNEL_LOGOS.get("ge-globo-esporte", ""),
    "techtudo": CHANNEL_LOGOS.get("techtudo", ""),
    "tudogostoso": CHANNEL_LOGOS.get("tudogostoso", ""),
    "tudo gostoso": CHANNEL_LOGOS.get("tudogostoso", ""),
    "sbt": CHANNEL_LOGOS.get("sbt", ""),
    "sbt news": "/static/images/creative-viewers/sbt-news.svg",
}


def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", text(value).lower())
    return re.sub(r"\s+", " ", "".join(ch for ch in raw if not unicodedata.combining(ch))).strip()


def site_logo(name: Any) -> str:
    key = _fold(name)
    return SITE_LOGOS.get(key) or SITE_LOGOS.get(key.replace(".com", "").replace(".br", "").strip()) or ""


def channel_logo(channel: dict) -> str:
    channel = as_dict(channel)
    return text(channel.get("logo")) or CHANNEL_LOGOS.get(text(channel.get("id")), "")


def kind_for(channel: dict) -> str:
    channel = as_dict(channel)
    if text(channel.get("id")) in KIND_BY_CHANNEL:
        return KIND_BY_CHANNEL[text(channel.get("id"))]
    group = text(channel.get("group")) or text(as_dict(CHANNEL_CATALOG.get(text(channel.get("id")))).get("group"))
    return KIND_BY_GROUP.get(group, "portal")


# Grupos que não têm tela com o criativo (OOH, lugares e dados ficam fora dos mockups).
NO_SCREEN_GROUPS = {"ooh", "places", "data"}

# Variações da arte principal e as telas que as usam: a vertical vai para stories e vídeo
# vertical; a quadrada, para o feed, o retângulo médio do portal e a capa do player de áudio.
VARIANT_RATIOS = {"vertical": "2:3", "square": "1:1"}
VARIANT_KINDS = {"vertical": {"vertical", "social"}, "square": {"social", "portal", "audio"}}
# Em cada tela, a variação que melhor ocupa o espaço; sem ela, entra a arte principal.
IMAGE_BY_KIND = {"vertical": "vertical", "social": "square", "audio": "square"}


def variants_needed(channels: Any) -> list[str]:
    """Quais variações o plano usa, pelos canais com tela."""
    kinds = {
        kind_for(channel)
        for channel in (as_dict(c) if isinstance(c, dict) else {"id": text(c)} for c in as_list(channels))
        if text(channel.get("id") or channel.get("label"))
        and (text(channel.get("group")) or text(as_dict(CHANNEL_CATALOG.get(text(channel.get("id")))).get("group"))) not in NO_SCREEN_GROUPS
    }
    return [name for name, uses in VARIANT_KINDS.items() if kinds & uses]


def _images(kind: str, image: str, variants: dict) -> dict:
    variants = as_dict(variants)
    best = text(variants.get(IMAGE_BY_KIND.get(kind, ""))) or text(image)
    return {"image": best, "square": text(variants.get("square")) or text(image)}


def mockups_for(view: dict, image: str, limit: int = 2) -> list[dict]:
    """Uma tela por tipo de canal do plano (o de maior peso primeiro), com o criativo dentro."""
    if not text(image):
        return []
    channels = sorted(
        (as_dict(c) for c in as_list(as_dict(view.get("media")).get("channels"))),
        key=lambda c: -(float(c.get("pct") or 0)),
    )
    sites = [as_dict(s) for s in as_list(as_dict(view.get("network_sites")).get("sites"))]
    variants = as_dict(as_dict(view.get("hero")).get("creative_variants"))
    out: list[dict] = []
    seen: set[str] = set()
    for channel in channels:
        if text(channel.get("group")) in {"ooh", "places", "audio", "data"}:
            continue
        kind = kind_for(channel)
        if kind in {"app", "vertical"}:
            # A capa e o slide do criativo usam telas largas; app e vertical ficam no slide dos canais.
            kind = "social"
        if kind in seen:
            continue
        seen.add(kind)
        label, logo = text(channel.get("label")), channel_logo(channel)
        if kind == "portal":
            # Na Rede de portais, a tela mostra o maior portal do recorte que tenha logo.
            for site in sites:
                found = site_logo(site.get("name"))
                if found:
                    label, logo = text(site.get("name")), found
                    break
        out.append({"kind": kind, "label": label, "logo": logo, **_images(kind, image, variants), "channel": text(channel.get("label"))})
        if len(out) >= limit:
            break
    if not out:
        out.append({"kind": "portal", "label": "Portal", "logo": "", **_images("portal", image, variants), "channel": ""})
    return out


def showcase_for(view: dict, image: str, limit: int = 4) -> list[dict]:
    """Uma tela por canal do plano (até quatro), cada uma no layout do canal, com o criativo dentro."""
    if not text(image):
        return []
    channels = sorted(
        (as_dict(c) for c in as_list(as_dict(view.get("media")).get("channels"))),
        key=lambda c: -(float(c.get("pct") or 0)),
    )
    sites = [as_dict(s) for s in as_list(as_dict(view.get("network_sites")).get("sites"))]
    variants = as_dict(as_dict(view.get("hero")).get("creative_variants"))
    out = []
    for channel in channels:
        if text(channel.get("group")) in NO_SCREEN_GROUPS:
            continue
        kind = kind_for(channel)
        label, logo = text(channel.get("label")), channel_logo(channel)
        if kind == "portal":
            for site in sites:
                found = site_logo(site.get("name"))
                if found:
                    label, logo = text(site.get("name")), found
                    break
        out.append({
            "kind": kind, "label": label, "logo": logo, **_images(kind, image, variants),
            "channel": text(channel.get("label")), "pct": channel.get("pct"),
            "placement": PLACEMENT.get(kind, ""),
        })
        if len(out) >= limit:
            break
    return out
