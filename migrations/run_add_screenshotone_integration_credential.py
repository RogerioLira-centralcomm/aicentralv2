#!/usr/bin/env python
"""Libera a ScreenshotOne no cofre de credenciais do CentralX."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from integration_provider_check_lib import ensure_provider_in_check


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_screenshotone_integration_credential.sql")


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
            ensure_provider_in_check(cursor, "screenshotone")
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            cursor.execute(
                """
                SELECT encrypted_secret IS NOT NULL AND encrypted_secret <> '' AS has_secret
                  FROM system_integration_credentials
                 WHERE provider = 'screenshotone'
                """
            )
            row = cursor.fetchone() or {}
        conn.commit()
    state = "com chave protegida" if row.get("has_secret") else "sem chave"
    print(f"ScreenshotOne liberada na central de credenciais ({state}).")


if __name__ == "__main__":
    main()
