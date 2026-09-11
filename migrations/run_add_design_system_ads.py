#!/usr/bin/env python
"""Garante o índice do Design System Ads e os JSONB da marca e da campanha."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_design_system_ads.sql")


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
                    EXISTS (
                        SELECT 1
                          FROM information_schema.columns
                         WHERE table_schema = 'public'
                           AND table_name = 'cx_clients'
                           AND column_name = 'brand_profile'
                    ) AS has_brand_profile,
                    EXISTS (
                        SELECT 1
                          FROM information_schema.columns
                         WHERE table_schema = 'public'
                           AND table_name = 'cx_campaigns'
                           AND column_name = 'creative_brief'
                    ) AS has_brief,
                    EXISTS (
                        SELECT 1
                          FROM pg_indexes
                         WHERE schemaname = 'public'
                           AND indexname = 'uq_cx_brand_visual_systems_design_system_ads'
                    ) AS has_unique
                """
            )
            result = cursor.fetchone()
    if not result["systems"]:
        raise RuntimeError("cx_brand_visual_systems não existe.")
    if not result["has_brand_profile"]:
        raise RuntimeError("cx_clients.brand_profile não existe.")
    if not result["has_brief"]:
        raise RuntimeError("cx_campaigns.creative_brief não existe.")
    if not result["has_unique"]:
        raise RuntimeError("Índice único do Design System Ads não existe.")
    print("Migração do Design System Ads executada e validada.")


if __name__ == "__main__":
    main()
