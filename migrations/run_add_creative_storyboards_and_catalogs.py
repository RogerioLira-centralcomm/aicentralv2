#!/usr/bin/env python3
"""Aplica e valida storyboards, catálogo CTV e formato Netflix de pausa."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_storyboards_and_catalogs.sql")


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
                SELECT EXISTS (
                    SELECT 1
                      FROM information_schema.columns
                     WHERE table_schema = 'public'
                       AND table_name = 'cx_campaigns'
                       AND column_name = 'creative_brief'
                ) AS has_brief,
                EXISTS (
                    SELECT 1 FROM cx_format_templates
                     WHERE slug = 'netflix-pause-banner'
                       AND media_type = 'image'
                       AND is_active = TRUE
                ) AS has_netflix_format,
                (
                    SELECT COUNT(*) FROM cx_creative_viewer_profiles
                     WHERE slug IN ('netflix', 'disney-plus', 'hbo-max')
                       AND jsonb_array_length(shell_spec->'sections') > 0
                ) AS catalog_count
                """
            )
            result = cursor.fetchone()
    if not result["has_brief"] or not result["has_netflix_format"]:
        raise RuntimeError("Storyboard ou formato Netflix não foi criado.")
    if result["catalog_count"] != 3:
        raise RuntimeError("Os três catálogos CTV não foram configurados.")
    print("Storyboards, formato Netflix e catálogos CTV atualizados.")


if __name__ == "__main__":
    main()
