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


PRESET_NO_CLIENT = "no_client"
PRESET_HOUSE_CLIENT = "house_client"
PRESET_OTHER_CLIENT = "other_client"
PRESET_INVALID_CLIENT = "invalid_client"
PRESET_LOAD_ERROR = "load_error"
PRESET_UNAUTHORIZED = "unauthorized"

# Labs / specimen sem marca: só o slug canônico, nunca id vazio ou erro.
HOUSE_CONTEXT_ID = CENTRALCOMM_SLUG


def is_centralcomm_client(client=None):
    if client is None:
        return False
    if isinstance(client, str):
        return client.strip().lower() in CENTRALCOMM_NAMES
    if not isinstance(client, dict):
        return False
    name = str(client.get("name") or "").strip().lower()
    slug = str(client.get("slug") or "").strip().lower()
    return name in CENTRALCOMM_NAMES or slug in CENTRALCOMM_NAMES


def is_house_context_id(client_id):
    return str(client_id or "").strip().lower() == HOUSE_CONTEXT_ID


def resolve_preset_context(
    *,
    client_id=None,
    client=None,
    not_found=False,
    load_error=False,
    unauthorized=False,
):
    if unauthorized:
        return PRESET_UNAUTHORIZED
    if load_error:
        return PRESET_LOAD_ERROR
    if not_found:
        return PRESET_INVALID_CLIENT
    if client is not None:
        if is_centralcomm_client(client):
            return PRESET_HOUSE_CLIENT
        return PRESET_OTHER_CLIENT
    if is_house_context_id(client_id):
        return PRESET_NO_CLIENT
    if client_id not in (None, ""):
        return PRESET_OTHER_CLIENT
    return PRESET_UNAUTHORIZED


def may_apply_house_preset(context):
    return context in {PRESET_NO_CLIENT, PRESET_HOUSE_CLIENT}


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
                "headline": "A campanha chega inteira",
                "support": "Do cliente à tela, sem perder cor nem prazo.",
                "cta": "Começar agora",
                "legal": "CentralComm",
            },
        }
    )
