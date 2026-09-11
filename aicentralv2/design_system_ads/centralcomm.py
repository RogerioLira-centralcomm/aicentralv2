"""Preset CentralComm Ads — nasce do tema Tailwind da casa."""

from __future__ import annotations

from .schema import DesignSystemAds

CENTRALCOMM_SLUG = "centralcomm"
CENTRALCOMM_LOGO = "/static/images/cc_logo.png"
CENTRALCOMM_NAMES = {"centralcomm", "central comm", "centralcomm ads"}

# Cores do tema [data-theme="centralcomm"] em design-system.css.
CENTRALCOMM_TOKENS = {
    "paper": "#FFFFFF",
    "ink": "#1E4D4F",
    "accent": "#1E4D4F",
    "muted": "#3D4451",
    "cta_ink": "#FFFFFF",
    "highlight": "#F3B71B",
    "logo": CENTRALCOMM_LOGO,
    "font-display": "Inter",
    "font-body": "Inter",
    "type-headline": "72px",
    "type-support": "28px",
    "type-cta": "22px",
    "type-legal": "14px",
    "cta-radius": "0.25rem",
    "safe": "6%",
}


def is_centralcomm_client(client=None):
    if client is None:
        return False
    if isinstance(client, str):
        return client.strip().lower() in CENTRALCOMM_NAMES | {CENTRALCOMM_SLUG}
    if not isinstance(client, dict):
        return False
    name = str(client.get("name") or "").strip().lower()
    slug = str(client.get("id") or client.get("slug") or "").strip().lower()
    return name in CENTRALCOMM_NAMES or slug == CENTRALCOMM_SLUG


def centralcomm_preset(*, client_id=None, status="draft"):
    return DesignSystemAds.model_validate(
        {
            "id": "dsa-centralcomm",
            "scope": "brand",
            "name": "CentralComm Ads",
            "source": "tailwind-centralcomm",
            "status": status,
            "version": 1,
            "client_id": client_id or CENTRALCOMM_SLUG,
            "logo_url": CENTRALCOMM_LOGO,
            "tokens": dict(CENTRALCOMM_TOKENS),
            "dna": {
                "name": "CentralComm",
                "personality": ["clara", "técnica", "de mídia", "acessível"],
                "must": [
                    "teal da casa no ink e no CTA",
                    "ouro só como highlight",
                    "Inter",
                    "copy curta",
                ],
                "avoid": ["verde #9CCF31", "pílula", "cream/terracotta", "resize cego"],
            },
            "archetype": "brand",
            "ad_copy": {
                "headline": "A peça na tinta certa",
                "support": "O anúncio herda o tema Tailwind da CentralComm.",
                "cta": "Ver o sistema",
                "legal": "CentralComm Ads · Design System Ads",
            },
        }
    )
