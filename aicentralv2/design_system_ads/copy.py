"""Linha de anúncio da marca — nunca copy sobre o laboratório."""

from __future__ import annotations

import re

COPY_KEYS = ("headline", "support", "cta", "legal")
META_COPY = re.compile(
    r"design system|tinta certa|herda o tema|tailwind|ver o sistema",
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
        "headline": f"{short} no primeiro olhar",
        "support": f"O que {short} promete, no tamanho do anúncio.",
        "cta": "Saiba mais",
        "legal": short,
    }


def clean_ad_copy(copy, name="", *, centralcomm=False):
    fallback = brand_ad_copy(name, centralcomm=centralcomm)
    if not isinstance(copy, dict) or is_meta_copy(copy):
        return dict(fallback)
    cleaned = dict(fallback)
    for key in COPY_KEYS:
        value = str(copy.get(key) or "").strip()
        if value and not META_COPY.search(value):
            cleaned[key] = value[:180]
    return cleaned
