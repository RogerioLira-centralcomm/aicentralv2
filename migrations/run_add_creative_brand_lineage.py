#!/usr/bin/env python
"""Habilita criativos reais como evidência da linguagem de marca."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_brand_lineage.sql")


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
                SELECT pg_get_constraintdef(oid) AS definition
                  FROM pg_constraint
                 WHERE conname = 'chk_cx_client_brand_asset_role'
                """
            )
            row = cursor.fetchone()
        if not row or "'creative'" not in row["definition"]:
            raise RuntimeError("O papel creative não foi habilitado.")
    print("Migração da linha criativa executada e validada.")


if __name__ == "__main__":
    main()
