"""Pesquisa de canais (Perplexity via OpenRouter) e logos (Firecrawl)."""

import logging
import re

from ..crm_v3_web_scout import _firecrawl_scrape
from .agenda import CHANNELS


logger = logging.getLogger(__name__)

CHANNEL_QUERY = (
    "Para o canal de mídia {name} no Brasil e no mundo em 2025-2026, traga: "
    "1) números de usuários/alcance mais recentes com fonte e data; "
    "2) estrutura típica de audiência e segmentação para anunciantes; "
    "3) UM case real de campanha (marca, objetivo, formato, resultado numérico se houver); "
    "4) uma defesa curta de por que o canal interessa ao anunciante final. "
    "Não invente estatística. Se não houver dado confiável, diga pendente. "
    "Responda em português do Brasil, em no máximo 12 frases."
)


def research_channel(providers, channel):
    query = CHANNEL_QUERY.format(name=channel["name"])
    result = providers.research.search(query, context=channel["name"])
    return {
        "key": channel["key"],
        "name": channel["name"],
        "site": channel["site"],
        "resumo": (result.get("content") or "").strip(),
        "model": result.get("model"),
        "usage": result.get("usage") or {},
        "cost_usd": result.get("cost_usd") or 0,
    }


def fetch_logo_url(channel):
    data = _firecrawl_scrape(channel["site"], formats=["branding"], timeout_s=35)
    branding = data.get("branding") or {}
    images = branding.get("images") or {}
    meta = data.get("metadata") or {}
    logo = (
        branding.get("logo")
        or images.get("logo")
        or images.get("ogImage")
        or meta.get("ogImage")
        or meta.get("favicon")
        or ""
    )
    logo = str(logo or "").strip()
    if logo.startswith("//"):
        logo = "https:" + logo
    if not logo.startswith(("http://", "https://")):
        raise ValueError(f"Logo de {channel['name']} não encontrado.")
    return logo


def render_channel_html(channel, resumo, logo_url=None):
    logo = ""
    if logo_url:
        logo = (
            f'<figure class="ts-inline-image ts-canal-logo">'
            f'<img src="{logo_url}" alt="Logo {channel["name"]}"></figure>'
        )
    body = _plain_to_html(resumo) if resumo else (
        "<p>Pesquisa sem retorno confiável. Marcar como pendente.</p>"
    )
    return (
        f'<section class="ts-canal" data-canal="{channel["key"]}" id="canal-{channel["key"]}">'
        f'<!-- CANAL:{channel["key"]} -->'
        f"{logo}<h2>{channel['name']}</h2>"
        f"{body}"
        f'<!-- /CANAL:{channel["key"]} -->'
        "</section>"
    )


def replace_channel_block(html, channel_key, block):
    pattern = re.compile(
        rf'(?:<section class="ts-canal"[^>]*>)?<!-- CANAL:{re.escape(channel_key)} -->'
        rf".*?"
        rf"<!-- /CANAL:{re.escape(channel_key)} -->(?:</section>)?",
        re.DOTALL,
    )
    if pattern.search(html or ""):
        return pattern.sub(block, html, count=1)
    return (html or "") + block


def _plain_to_html(text):
    chunks = [item.strip() for item in re.split(r"\n\s*\n", text or "") if item.strip()]
    if not chunks:
        return ""
    return "".join(f"<p>{_escape(item).replace(chr(10), '<br>')}</p>" for item in chunks)


def _escape(value):
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
