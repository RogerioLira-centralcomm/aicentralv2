"""Importação de URL: fetch + extração do texto principal."""

import ipaddress
import socket
from urllib.parse import urlparse

from ..crm_v3_web_scout import _firecrawl_scrape
from .prompts import SUMMARIZE_URL_SYSTEM, wrap_untrusted


def validate_public_url(raw):
    value = str(raw or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Informe uma URL http ou https válida.")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("A URL precisa ser pública.")
    try:
        addresses = {
            item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443)
        }
    except socket.gaierror as exc:
        raise ValueError("Não foi possível resolver o endereço da página.") from exc
    for raw_address in addresses:
        address = ipaddress.ip_address(raw_address)
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ValueError("A URL precisa apontar para um endereço público.")
    return value


def extract_page(url):
    safe_url = validate_public_url(url)
    data = _firecrawl_scrape(safe_url, formats=["markdown"], timeout_s=40)
    metadata = data.get("metadata") or {}
    markdown = str(data.get("markdown") or data.get("content") or "").strip()
    if not markdown:
        raise ValueError("Não foi possível extrair o conteúdo principal da página.")
    title = (
        metadata.get("title")
        or metadata.get("ogTitle")
        or metadata.get("og:title")
        or safe_url
    )
    return {
        "url": safe_url,
        "titulo": str(title)[:300],
        "texto": markdown[:12000],
    }


def summarize_page(providers, page):
    result = providers.text.complete(
        [
            {"role": "system", "content": SUMMARIZE_URL_SYSTEM},
            {
                "role": "user",
                "content": wrap_untrusted(page.get("url"), page.get("texto")),
            },
        ],
        max_tokens=700,
        temperature=0.2,
    )
    return result
