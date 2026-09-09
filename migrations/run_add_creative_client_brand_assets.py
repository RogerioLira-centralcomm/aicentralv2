#!/usr/bin/env python
"""Cria e valida os ativos visuais dos perfis criativos."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_client_brand_assets.sql")


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
                   AND table_name = 'cx_client_brand_assets'
                """
            )
            found = {row["column_name"] for row in cursor.fetchall()}
        expected = {
            "id", "client_id", "role", "source_kind", "source_url",
            "page_url", "asset_path", "mime_type", "width", "height",
            "sha256", "score", "status", "is_primary", "metadata",
        }
        if not expected.issubset(found):
            raise RuntimeError(
                "Validação dos ativos visuais falhou: "
                + ", ".join(sorted(expected - found))
            )
    print("Migração de ativos visuais executada e validada.")


if __name__ == "__main__":
    main()
