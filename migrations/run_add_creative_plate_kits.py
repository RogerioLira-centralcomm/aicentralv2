#!/usr/bin/env python
"""Cria a tabela de kits IAB base por marca."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_plate_kits.sql")


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
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'cx_plate_kits'
                """
            )
            columns = {row["column_name"] for row in cursor.fetchall()}
    required = {
        "id",
        "client_id",
        "name",
        "product",
        "copy",
        "product_assets",
        "plates",
        "bindings",
        "passes",
        "created_at",
    }
    missing = required - columns
    if missing:
        raise RuntimeError(f"cx_plate_kits incompleta: {sorted(missing)}")
    print("Migração de cx_plate_kits executada e validada.")


if __name__ == "__main__":
    main()
