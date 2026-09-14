"""Tokens da one-page pública — os mesmos do site centralcomm.media."""

from __future__ import annotations

LOGO_PATH = "/static/images/cc_logo.png"

PUBLIC_TOKENS = {
    "teal": "#1E4D4F",
    "black": "#080808",
    "lime": "#4AFF6B",
    "lime_on_light": "#167A3A",
    "gold": "#F5A623",
    "canvas": "#F7F8FA",
    "ink": "#141414",
    "logo": LOGO_PATH,
    "font_display": "Nunito",
    "font_body": "Nunito Sans",
}

ZONE_COLORS = {
    "CORE": "#167A3A",
    "DEPARTURES": "#F5A623",
    "PREMIUM": "#1E4D4F",
    "MOBILITY": "#2A6D70",
    "HALO": "#C48A1A",
}
TYPE_PIN_COLORS = {
    "aeroporto": "#167A3A",
    "shopping": "#F5A623",
    "evento": "#1E4D4F",
}


def zone_color(zone_type: str, fallback: str = "") -> str:
    return ZONE_COLORS.get((zone_type or "").upper(), fallback or ZONE_COLORS["CORE"])
