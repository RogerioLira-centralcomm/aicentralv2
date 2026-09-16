#!/usr/bin/env python
"""Libera o Dify no cofre de credenciais sem copiar ou exibir segredos."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_dify_integration_credential.sql")


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
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid) AS definition
                  FROM pg_constraint
                 WHERE conname = 'system_integration_credentials_provider_check'
                """
            )
            current = ((cursor.fetchone() or {}).get("definition") or "")
            if "dify" not in current:
                cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            cursor.execute(
                """
                SELECT encrypted_secret IS NOT NULL AND encrypted_secret <> '' AS has_secret
                  FROM system_integration_credentials
                 WHERE provider = 'dify'
                """
            )
            row = cursor.fetchone() or {}
        conn.commit()
    state = "com chave no banco" if row.get("has_secret") else "sem chave (configure em Integrações ou no .env)"
    print(f"Dify liberado na central de credenciais ({state}).")


if __name__ == "__main__":
    main()
