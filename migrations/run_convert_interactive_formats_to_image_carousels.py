#!/usr/bin/env python3
"""Converte formatos interativos e de vídeo em carrosséis de imagens."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name(
    "convert_interactive_formats_to_image_carousels.sql"
)
PORTAL_SLUGS = (
    "hotspot", "cartas", "puxe-descubra", "arraste-descubra",
    "quiz", "native-infeed", "video-outstream",
)
CAROUSEL_SLUGS = (
    "video-outstream", "netflix-logo-bumper",
    "netflix-anuncio-simulado", "hbomax-interactive-midroll",
)


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
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
        conn.commit()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FILTER (
                           WHERE f.slug = ANY(%s)
                             AND ch.slug = 'portal_generico'
                             AND vp.slug = 'g1'
                             AND f.placement_spec->>'context' = 'portal'
                       ) AS portal_count,
                       COUNT(*) FILTER (
                           WHERE f.slug = ANY(%s)
                             AND f.media_type = 'image'
                             AND f.engine = 'gpt_image_2'
                             AND f.behavior_spec->>'type' = 'carousel'
                       ) AS carousel_count
                  FROM cx_format_templates f
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                  LEFT JOIN cx_creative_viewer_profiles vp
                    ON vp.id = f.default_viewer_profile_id
                 WHERE f.slug = ANY(%s)
                """,
                (
                    list(PORTAL_SLUGS),
                    list(CAROUSEL_SLUGS),
                    list(set(PORTAL_SLUGS + CAROUSEL_SLUGS)),
                ),
            )
            result = cursor.fetchone()
    if result["portal_count"] != len(PORTAL_SLUGS):
        raise RuntimeError("Nem todos os formatos interativos usam portal e G1.")
    if result["carousel_count"] != len(CAROUSEL_SLUGS):
        raise RuntimeError("Os antigos formatos de vídeo não viraram carrosséis.")
    print("Formatos interativos e carrosséis de imagens atualizados.")


if __name__ == "__main__":
    main()
