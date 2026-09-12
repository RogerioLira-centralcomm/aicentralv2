"""Tokens da one-page pública CentralComm. Não misturar com o ERP."""

from __future__ import annotations

LOGO_PATH = "/static/images/cc_logo.png"

PUBLIC_TOKENS = {
    "teal": "#1E4D4F",
    "teal_deep": "#122F30",
    "gold": "#F3B71B",
    "lime": "#9CCF31",
    "ink": "#F4F1E8",
    "muted": "rgba(244, 241, 232, 0.62)",
    "canvas": "#0C1A1B",
    "panel": "#132426",
    "logo": LOGO_PATH,
    "font_display": "Fraunces",
    "font_body": "Inter",
}

ZONE_COLORS = {
    "CORE": "#F3B71B",
    "DEPARTURES": "#9CCF31",
    "PREMIUM": "#5BB8C4",
    "MOBILITY": "#2A6D70",
    "HALO": "#E8C15A",
}


def zone_color(zone_type: str, fallback: str = "") -> str:
    return ZONE_COLORS.get((zone_type or "").upper(), fallback or ZONE_COLORS["CORE"])
