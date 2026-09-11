#!/usr/bin/env python
"""Libera o provider OpenRouter na central de credenciais."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_openrouter_integration_credential.sql")


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
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid) AS definition
                  FROM pg_constraint
                 WHERE conname = 'system_integration_credentials_provider_check'
                """
            )
            row = cursor.fetchone()
        conn.commit()
    definition = (row or {}).get("definition") or ""
    if "openrouter" not in definition:
        raise RuntimeError("A constraint de integrações não aceitou o OpenRouter.")
    print("OpenRouter liberado na central de credenciais.")


if __name__ == "__main__":
    main()
