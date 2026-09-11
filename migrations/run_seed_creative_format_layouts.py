#!/usr/bin/env python
"""Popula especificações técnicas iniciais dos formatos criativos."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BEHAVIORS = {
    "hotspot": {"type": "hotspot", "trigger": "hover_tap", "transition_ms": 220},
    "cartas": {"type": "flip", "trigger": "click", "transition_ms": 420},
    "puxe-descubra": {"type": "reveal", "trigger": "drag_vertical", "transition_ms": 280},
    "arraste-descubra": {"type": "compare", "trigger": "drag_horizontal", "transition_ms": 0},
    "quiz": {"type": "quiz", "trigger": "click", "transition_ms": 180},
    "video-outstream": {"type": "carousel", "trigger": "auto", "transition_ms": 420},
    "netflix-logo-bumper": {"type": "carousel", "trigger": "auto", "transition_ms": 420},
    "netflix-anuncio-simulado": {"type": "carousel", "trigger": "auto", "transition_ms": 420},
    "hbomax-interactive-midroll": {"type": "carousel", "trigger": "auto", "transition_ms": 420},
}


SOCIAL_CHANNELS = {
    "meta_social", "tiktok_social", "linkedin_social", "youtube_social",
}
SOCIAL_DESKTOP = {"linkedin-share", "youtube-infeed"}


def _context(row):
    channel = (row.get("channel") or "").lower()
    if channel in {"netflix", "hbomax", "disneyplus", "primevideo"}:
        return "tv"
    if channel in SOCIAL_CHANNELS:
        return "social"
    if "mobile" in (row.get("slug") or ""):
        return "celular"
    return "portal"


def _placement(row):
    context = _context(row)
    size = row.get("default_size") or ""
    slug = row.get("slug") or ""
    zone = None
    if context == "tv":
        tv_slots = {
            "disney-pause-plus": {"x": 22, "y": 22, "width": 56, "height": 48},
            "disney-branded-slate": {"x": 20, "y": 18, "width": 60, "height": 54},
            "hbomax-pause-ad": {"x": 18, "y": 21, "width": 64, "height": 50},
            "hbomax-interactive-midroll": {"x": 14, "y": 18, "width": 72, "height": 54},
            "netflix-logo-bumper": {"x": 26, "y": 24, "width": 48, "height": 44},
            "netflix-anuncio-simulado": {"x": 16, "y": 19, "width": 68, "height": 52},
            "netflix-pause-banner": {"x": 8, "y": 6, "width": 84, "height": 15},
        }
        slot = tv_slots.get(
            slug,
            {"x": 18, "y": 20, "width": 64, "height": 50},
        )
        viewport = {"width": 1600, "height": 900}
    elif context == "social":
        slot = {"x": 0, "y": 0, "width": 100, "height": 100}
        viewport = (
            {"width": 1280, "height": 800}
            if slug in SOCIAL_DESKTOP
            else {"width": 390, "height": 844}
        )
    elif size == "728x90":
        slot = {"x": 12, "y": 18, "width": 76, "height": 12}
        viewport = {"width": 1280, "height": 800}
        zone = "leaderboard"
    elif size == "300x600":
        slot = {"x": 70, "y": 16, "width": 23, "height": 68}
        viewport = {"width": 1280, "height": 800}
        zone = "rail"
    elif size == "320x50":
        slot = {"x": 5, "y": 82, "width": 90, "height": 12}
        viewport = {"width": 390, "height": 844}
        zone = "sticky"
    else:
        slot = {"x": 65, "y": 20, "width": 28, "height": 38}
        viewport = {"width": 1280, "height": 800}
        zone = "in_feed"
    if slug in {
        "hotspot", "cartas", "puxe-descubra", "arraste-descubra",
        "quiz", "native-infeed",
    }:
        zone = "in_feed"
    spec = {
        "context": context,
        "viewport": viewport,
        "slot": slot,
        "fit": "contain",
        "responsive": "scale",
    }
    if context not in {"tv", "social"} and zone:
        spec["placement_zone"] = zone
    return spec


def main():
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.id, f.slug, f.mechanic, f.default_size, ch.slug AS channel
                  FROM cx_format_templates f
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                 WHERE f.is_active = TRUE
                   AND (
                       COALESCE(f.placement_spec, '{}'::jsonb) = '{}'::jsonb
                       OR COALESCE(f.behavior_spec, '{}'::jsonb) = '{}'::jsonb
                   )
                """
            )
            rows = cursor.fetchall()
            for row in rows:
                behavior = BEHAVIORS.get(
                    row.get("slug"),
                    {"type": "static", "trigger": "none", "transition_ms": 0},
                )
                cursor.execute(
                    """
                    UPDATE cx_format_templates
                       SET placement_spec = CASE
                               WHEN COALESCE(placement_spec, '{}'::jsonb) = '{}'::jsonb
                               THEN %s::jsonb ELSE placement_spec
                           END,
                           behavior_spec = CASE
                               WHEN COALESCE(behavior_spec, '{}'::jsonb) = '{}'::jsonb
                               THEN %s::jsonb ELSE behavior_spec
                           END
                     WHERE id = %s
                    """,
                    (Jsonb(_placement(row)), Jsonb(behavior), row["id"]),
                )
        conn.commit()
        print(f"Especificações técnicas populadas para {len(rows)} formatos.")


if __name__ == "__main__":
    main()

