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


def mockups_for(view: dict, image: str, limit: int = 2) -> list[dict]:
    """Uma tela por tipo de canal do plano (o de maior peso primeiro), com o criativo dentro."""
    if not text(image):
        return []
    channels = sorted(
        (as_dict(c) for c in as_list(as_dict(view.get("media")).get("channels"))),
        key=lambda c: -(float(c.get("pct") or 0)),
    )
    sites = [as_dict(s) for s in as_list(as_dict(view.get("network_sites")).get("sites"))]
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
        out.append({"kind": kind, "label": label, "logo": logo, "image": text(image), "channel": text(channel.get("label"))})
        if len(out) >= limit:
            break
    if not out:
        out.append({"kind": "portal", "label": "Portal", "logo": "", "image": text(image), "channel": ""})
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
    out = []
    for channel in channels:
        if text(channel.get("group")) in {"ooh", "places", "data"}:
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
            "kind": kind, "label": label, "logo": logo, "image": text(image),
            "channel": text(channel.get("label")), "pct": channel.get("pct"),
            "placement": PLACEMENT.get(kind, ""),
        })
        if len(out) >= limit:
            break
    return out
