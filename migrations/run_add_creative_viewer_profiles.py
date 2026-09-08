#!/usr/bin/env python
"""Executa e valida a migração dos visualizadores de mídia."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_viewer_profiles.sql")


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
                    to_regclass('public.cx_creative_viewer_profiles') AS profiles,
                    EXISTS (
                        SELECT 1 FROM information_schema.columns
                         WHERE table_name = 'cx_format_templates'
                           AND column_name = 'default_viewer_profile_id'
                    ) AS format_link,
                    EXISTS (
                        SELECT 1 FROM information_schema.columns
                         WHERE table_name = 'cx_public_collection_assets'
                           AND column_name = 'viewer_profile_id'
                    ) AS collection_link
                """
            )
            validation = cursor.fetchone()
        if not all(validation.values()):
            raise RuntimeError(f"Validação da migração falhou: {validation}")
    print("Migração dos visualizadores de mídia executada e validada.")


if __name__ == "__main__":
    main()
