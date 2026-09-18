#!/usr/bin/env python3
"""Cria e valida sessões, finalizações e filas duráveis do Cadu Studio."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_studio_sessions.sql")


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
            cursor.execute("""
                SELECT to_regclass('public.cx_studio_assets') AS assets,
                       to_regclass('public.cx_studio_sessions') AS sessions,
                       to_regclass('public.cx_studio_finalizations') AS finalizations,
                       to_regclass('public.cx_studio_delivery_outbox') AS outbox,
                       to_regclass('public.cx_studio_asset_deletions') AS deletions
            """)
            validation = cursor.fetchone()
        if not all(validation.values()):
            raise RuntimeError(f"Validação da migração falhou: {validation}")
    print("Cadu Studio: sessões, finalizações e filas prontas.")


if __name__ == "__main__":
    main()
