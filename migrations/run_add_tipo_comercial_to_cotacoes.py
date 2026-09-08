#!/usr/bin/env python
"""Adiciona a categoria comercial única às cotações existentes."""

import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(_path):
        return False


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_tipo_comercial_to_cotacoes.sql")


def main() -> int:
    try:
        conn = psycopg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            dbname=os.getenv("DB_NAME", "aicentral_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            row_factory=dict_row,
        )
    except Exception as exc:
        print(f"[migration] Falha ao conectar no Postgres: {exc}", file=sys.stderr)
        return 2

    try:
        with conn.cursor() as cur:
            cur.execute(SQL_PATH.read_text(encoding="utf-8"))
            cur.execute(
                """
                SELECT column_default, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'cadu_cotacoes'
                  AND column_name = 'tipo_comercial'
                """
            )
            column = cur.fetchone()
        conn.commit()
        if column:
            print(f"[migration] OK — tipo_comercial presente: {column}")
            return 0
        print("[migration] ERRO — tipo_comercial não foi criado.", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
