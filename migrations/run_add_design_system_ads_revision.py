#!/usr/bin/env python
"""Gera a coluna design_system_ads_revision em marca e campanha."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_design_system_ads_revision.sql")


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
                    EXISTS (
                        SELECT 1
                          FROM information_schema.columns
                         WHERE table_schema = 'public'
                           AND table_name = 'cx_clients'
                           AND column_name = 'design_system_ads_revision'
                    ) AS client_col,
                    EXISTS (
                        SELECT 1
                          FROM information_schema.columns
                         WHERE table_schema = 'public'
                           AND table_name = 'cx_campaigns'
                           AND column_name = 'design_system_ads_revision'
                    ) AS campaign_col
                """
            )
            result = cursor.fetchone()
    if not result["client_col"]:
        raise RuntimeError("cx_clients.design_system_ads_revision não existe.")
    if not result["campaign_col"]:
        raise RuntimeError("cx_campaigns.design_system_ads_revision não existe.")
    print("Coluna de revisão do Design System Ads gerada e validada.")


if __name__ == "__main__":
    main()
