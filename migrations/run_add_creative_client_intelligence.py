#!/usr/bin/env python
"""Executa e valida a inteligência de marca dos clientes criativos."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_client_intelligence.sql")


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
                SELECT column_name, data_type
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'cx_clients'
                   AND column_name = ANY(%s)
                """,
                (["website_url", "brand_profile", "analysis_metadata"],),
            )
            found = {row["column_name"]: row["data_type"] for row in cursor.fetchall()}
        expected = {
            "website_url": "text",
            "brand_profile": "jsonb",
            "analysis_metadata": "jsonb",
        }
        if found != expected:
            raise RuntimeError(f"Validação da inteligência de marca falhou: {found}")
    print("Migração de inteligência de marca executada e validada.")


if __name__ == "__main__":
    main()
