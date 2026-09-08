#!/usr/bin/env python
"""Cria e valida a central segura de credenciais de integrações."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_system_integration_credentials.sql")


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
                "SELECT to_regclass('public.system_integration_credentials') AS table_name"
            )
            validation = cursor.fetchone()
        if not validation or not validation["table_name"]:
            raise RuntimeError("A tabela de credenciais não foi criada.")
    print("Central de credenciais de integrações criada e validada.")


if __name__ == "__main__":
    main()
