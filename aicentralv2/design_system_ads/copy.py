"""Linha de anúncio da marca — nunca copy sobre o laboratório."""

from __future__ import annotations

import re

COPY_KEYS = ("headline", "support", "cta", "legal")
META_COPY = re.compile(
    r"design system|tinta certa|herda o tema|tailwind|ver o sistema",
    re.I,
)
STOCK_COPY = re.compile(
    r"no primeiro olhar|o que .+ promete, no tamanho do anúncio|saiba mais",
    re.I,
)


def is_centralcomm_name(name):
    return str(name or "").strip().lower() in {
        "centralcomm",
        "central comm",
        "centralcomm ads",
        "central comm ads",
    }


def is_meta_copy(copy):
    blob = " ".join(str((copy or {}).get(key) or "") for key in COPY_KEYS)
    return bool(META_COPY.search(blob))


def is_stock_copy(copy):
    if is_centralcomm_name((copy or {}).get("legal")):
        return False
    blob = " ".join(str((copy or {}).get(key) or "") for key in COPY_KEYS)
    return bool(STOCK_COPY.search(blob) or META_COPY.search(blob))


def brand_ad_copy(name="", *, centralcomm=False):
    short = str(name or "").replace(" Ads", "").strip() or "A marca"
    if META_COPY.search(short):
        short = "A marca"
    if centralcomm or is_centralcomm_name(short) or is_centralcomm_name(name):
        return {
            "headline": "A campanha chega inteira",
            "support": "Do cliente à tela, sem perder cor nem prazo.",
            "cta": "Começar agora",
            "legal": "CentralComm",
        }
    return {
        "headline": short,
        "support": "",
        "cta": "Ver mais",
        "legal": short,
    }


COPY_LIMITS = {
    "compact": {"headline": 32, "support": 0, "cta": 14, "legal": 22},
    "standard": {"headline": 42, "support": 56, "cta": 16, "legal": 36},
    "rich": {"headline": 56, "support": 80, "cta": 18, "legal": 48},
}


def fit_ad_copy(copy, density="rich", name=""):
    """Corta a linha no tamanho do IAB. Compacto não leva apoio."""
    cleaned = clean_ad_copy(copy, name)
    limits = COPY_LIMITS.get(str(density or "rich"), COPY_LIMITS["rich"])
    fitted = {}
    for key in COPY_KEYS:
        limit = int(limits.get(key) or 0)
        if limit <= 0:
            fitted[key] = ""
            continue
        fitted[key] = str(cleaned.get(key) or "")[:limit]
    return fitted


def clean_ad_copy(copy, name="", *, centralcomm=False):
    fallback = brand_ad_copy(name, centralcomm=centralcomm)
    if not isinstance(copy, dict) or is_meta_copy(copy):
        return dict(fallback)
    cleaned = dict(fallback)
    for key in COPY_KEYS:
        value = str(copy.get(key) or "").strip()
        if value and not META_COPY.search(value) and not STOCK_COPY.search(value):
            cleaned[key] = value[:180]
    return cleaned
