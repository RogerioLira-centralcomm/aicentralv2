#!/usr/bin/env python
"""Executa e valida a migração da biblioteca HTML do Estúdio."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_compose_library.sql")


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
                SELECT
                    to_regclass('public.cx_brand_visual_systems') AS systems,
                    to_regclass('public.cx_compose_templates') AS templates,
                    to_regclass('public.cx_compose_variations') AS variations,
                    to_regclass('public.cx_compose_feedback') AS feedback
                """
            )
            validation = cursor.fetchone()
            cursor.execute(
                """
                SELECT slug FROM cx_compose_templates
                 WHERE slug = ANY(%s)
                """,
                ([
                    "editorial-still-4x5",
                    "editorial-still-1x1",
                    "product-hero-story",
                    "ugc-face-story",
                    "offer-stack-1x1",
                ],),
            )
            found = {row["slug"] for row in cursor.fetchall()}
        if not all(validation.values()):
            raise RuntimeError(f"Validação da migração falhou: {validation}")
        missing = {
            "editorial-still-4x5",
            "editorial-still-1x1",
            "product-hero-story",
            "ugc-face-story",
            "offer-stack-1x1",
        } - found
        if missing:
            raise RuntimeError(
                "Validação da migração falhou: "
                f"templates ausentes {sorted(missing)}."
            )
    print("Migração da biblioteca de compose executada e validada.")


if __name__ == "__main__":
    main()
