"""Tema visual da página única — fundo e densidade por tipo de mercado."""

from __future__ import annotations

from .helpers import as_dict, text

MARKET_THEMES = {
    "food": {
        "id": "food",
        "label": "Alimentação",
        "aliases": ("grill", "restaurante", "steak", "food", "churrasco", "montana"),
        "ink": "#1A1210",
        "paper": "#F6EDE3",
        "accent": "#B4532A",
        "fog": "#6B5346",
        "rule": "#D4C4B0",
        "bg_url": "/static/images/smart_planner/bg-montana-food.png",
        "bg_prompt": (
            "Atmospheric steakhouse ember and charcoal wash, no text, no logos, "
            "low contrast background for a paper leave-behind."
        ),
        "density_caption": "Peso do mix — premissa do pitch",
        "density": (
            {"label": "CTV", "value": 50},
            {"label": "Marketplace", "value": 30},
            {"label": "Retarget", "value": 20},
        ),
    },
    "travel": {
        "id": "travel",
        "label": "Viagem",
        "aliases": ("airport", "aeroporto", "confins", "viagem", "passagem", "turismo"),
        "ink": "#0E2433",
        "paper": "#EEF3F6",
        "accent": "#2A6F8F",
        "fog": "#5A7382",
        "rule": "#C5D2DA",
        "bg_url": "/static/images/smart_planner/bg-bh-travel.png",
        "bg_prompt": (
            "Cool airport dawn wash, concrete and glass-blue haze, no text, no logos, "
            "low contrast background for a paper leave-behind."
        ),
        "density_caption": "Peso do mix — premissa do pitch",
        "density": (
            {"label": "Portal", "value": 46},
            {"label": "App", "value": 32},
            {"label": "Retarget", "value": 22},
        ),
    },
    "finance": {
        "id": "finance",
        "label": "Serviços financeiros",
        "aliases": ("banco", "crédito", "credito", "bdmg", "fintech", "conta"),
        "ink": "#0C2428",
        "paper": "#EEF4F2",
        "accent": "#1F6B63",
        "fog": "#5A716C",
        "rule": "#C3D4CF",
        "bg_url": "/static/images/smart_planner/bg-bdmg-finance.png",
        "bg_prompt": (
            "Institutional teal stationery wash, soft ledger fog, no text, no logos, "
            "low contrast background for a paper leave-behind."
        ),
        "density_caption": "Peso do mix — premissa do pitch",
        "density": (
            {"label": "Serasa", "value": 44},
            {"label": "Redes", "value": 36},
            {"label": "Interativo", "value": 20},
        ),
    },
    "agro": {
        "id": "agro",
        "label": "Agro e indústria",
        "aliases": ("máquina", "maquina", "agro", "construção", "construcao", "loja"),
        "ink": "#1C2214",
        "paper": "#F3EFE4",
        "accent": "#8A6A22",
        "fog": "#6A6554",
        "rule": "#D2C8B0",
        "bg_url": "/static/images/smart_planner/bg-minas-agro.png",
        "bg_prompt": (
            "Dry Minas field dusk wash, ochre earth and olive haze, no text, no logos, "
            "low contrast background for a paper leave-behind."
        ),
        "density_caption": "Peso do mix — premissa do pitch",
        "density": (
            {"label": "Serasa", "value": 42},
            {"label": "Geolocal", "value": 34},
            {"label": "Loja", "value": 24},
        ),
    },
}

PITCH_THEMES = {
    "montana-grill": "food",
    "bh-airport": "travel",
    "bdmg": "finance",
    "minas-maquinas": "agro",
}


def theme_record(theme_id: str) -> dict:
    key = text(theme_id).lower() or "finance"
    source = MARKET_THEMES.get(key) or MARKET_THEMES["finance"]
    return {
        "id": source["id"],
        "label": source["label"],
        "ink": source["ink"],
        "paper": source["paper"],
        "accent": source["accent"],
        "fog": source["fog"],
        "rule": source["rule"],
        "bg_url": source["bg_url"],
        "bg_prompt": source["bg_prompt"],
        "density_caption": source["density_caption"],
        "density": [dict(item) for item in source["density"]],
    }


def resolve_market_id(client: str = "", agency: str = "", briefing: str = "", pitch: dict | None = None) -> str:
    if pitch:
        explicit = text(pitch.get("market_id")).lower()
        if explicit in MARKET_THEMES:
            return explicit
        pitch_id = text(pitch.get("id")).lower()
        if pitch_id in PITCH_THEMES:
            return PITCH_THEMES[pitch_id]
    hay = " ".join(part.lower() for part in (client, agency, briefing) if part)
    for theme_id, theme in MARKET_THEMES.items():
        if any(alias in hay for alias in theme["aliases"]):
            return theme_id
    return "finance"


def compose_theme(client: str = "", agency: str = "", briefing: str = "", pitch: dict | None = None) -> dict:
    theme = theme_record(resolve_market_id(client, agency, briefing, pitch))
    if pitch:
        creative = as_dict(pitch.get("creative"))
        exclusive = text(creative.get("bg_url") or pitch.get("bg_url"))
        if exclusive:
            theme["bg_url"] = exclusive
        density = pitch.get("density")
        if density:
            theme["density"] = [dict(item) for item in density if as_dict(item)]
        if text(pitch.get("density_caption")):
            theme["density_caption"] = text(pitch.get("density_caption"))
    return theme


def hero_party(branding: dict) -> dict:
    client = as_dict((branding or {}).get("client"))
    agency = as_dict((branding or {}).get("agency"))
    if text(client.get("name")) or text(client.get("logo_url")):
        return {
            "id": client.get("id"),
            "name": text(client.get("name")),
            "logo_url": text(client.get("logo_url")),
            "source": "client",
        }
    if text(agency.get("name")) or text(agency.get("logo_url")):
        return {
            "id": agency.get("id"),
            "name": text(agency.get("name")),
            "logo_url": text(agency.get("logo_url")),
            "source": "agency",
        }
    return {"id": None, "name": "", "logo_url": "", "source": None}
