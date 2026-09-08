#!/usr/bin/env python
"""Popula especificações técnicas iniciais dos formatos criativos."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Json


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BEHAVIORS = {
    "hotspot": {"type": "hotspot", "trigger": "hover_tap", "transition_ms": 220},
    "cartas": {"type": "flip", "trigger": "click", "transition_ms": 420},
    "puxe-descubra": {"type": "reveal", "trigger": "drag_vertical", "transition_ms": 280},
    "arraste-descubra": {"type": "compare", "trigger": "drag_horizontal", "transition_ms": 0},
    "quiz": {"type": "quiz", "trigger": "click", "transition_ms": 180},
    "video-outstream": {"type": "video", "trigger": "view", "transition_ms": 0},
}


def _context(row):
    channel = (row.get("channel") or "").lower()
    if channel in {"netflix", "hbomax", "disneyplus"}:
        return "tv"
    if "mobile" in (row.get("slug") or ""):
        return "celular"
    return "portal"


def _placement(row):
    context = _context(row)
    size = row.get("default_size") or ""
    if context == "tv":
        slot = {"x": 6, "y": 7, "width": 88, "height": 86}
        viewport = {"width": 1600, "height": 900}
    elif size == "728x90":
        slot = {"x": 12, "y": 18, "width": 76, "height": 12}
        viewport = {"width": 1280, "height": 800}
    elif size == "300x600":
        slot = {"x": 70, "y": 16, "width": 23, "height": 68}
        viewport = {"width": 1280, "height": 800}
    elif size == "320x50":
        slot = {"x": 5, "y": 82, "width": 90, "height": 12}
        viewport = {"width": 390, "height": 844}
    else:
        slot = {"x": 65, "y": 20, "width": 28, "height": 38}
        viewport = {"width": 1280, "height": 800}
    return {
        "context": context,
        "viewport": viewport,
        "slot": slot,
        "fit": "contain",
        "responsive": "scale",
    }


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
                    row.get("mechanic"),
                    {"type": "static", "trigger": "none", "transition_ms": 0},
                )
                cursor.execute(
                    """
                    UPDATE cx_format_templates
                       SET placement_spec = CASE
                               WHEN COALESCE(placement_spec, '{}'::jsonb) = '{}'::jsonb
                               THEN %s ELSE placement_spec
                           END,
                           behavior_spec = CASE
                               WHEN COALESCE(behavior_spec, '{}'::jsonb) = '{}'::jsonb
                               THEN %s ELSE behavior_spec
                           END
                     WHERE id = %s
                    """,
                    (Json(_placement(row)), Json(behavior), row["id"]),
                )
        conn.commit()
        print(f"Especificações técnicas populadas para {len(rows)} formatos.")


if __name__ == "__main__":
    main()

