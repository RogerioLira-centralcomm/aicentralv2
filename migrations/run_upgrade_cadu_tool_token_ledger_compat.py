#!/usr/bin/env python3
"""Compatibiliza as tabelas produtivas de créditos CADU com o ledger atual."""
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from dotenv import load_dotenv


def main():
    sql = Path(__file__).with_name("upgrade_cadu_tool_token_ledger_compat.sql").read_text(encoding="utf-8")
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    conn = psycopg.connect(
        host=os.getenv('DATABASE_HOST') or os.getenv('DB_HOST'),
        port=os.getenv('DATABASE_PORT') or os.getenv('DB_PORT'),
        dbname=os.getenv('DATABASE_NAME') or os.getenv('DB_NAME'),
        user=os.getenv('DATABASE_USER') or os.getenv('DB_USER'),
        password=os.getenv('DATABASE_PASSWORD') or os.getenv('DB_PASSWORD'),
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()
        print("OK: compatibilidade do ledger CADU aplicada")
    except Exception:
        conn.rollback()
        raise


if __name__ == "__main__":
    main()
