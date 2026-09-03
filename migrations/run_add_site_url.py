#!/usr/bin/env python
"""Executa a migration que adiciona `site_url VARCHAR(255)` em tbl_cliente.

Uso:
    python migrations/run_add_site_url.py

Lê credenciais de `.env` (mesmo padrão do resto do projeto). Idempotente:
o SQL faz o ALTER apenas quando a coluna não existe.
"""
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

try:
    from dotenv import load_dotenv  # opcional
except ImportError:  # pragma: no cover
    def load_dotenv(_path):
        return False

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SQL_PATH = Path(__file__).resolve().parent / "add_site_url_to_tbl_cliente.sql"
sql = SQL_PATH.read_text(encoding="utf-8")


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
            cur.execute(sql)
        conn.commit()

        # Verifica que a coluna passou a existir.
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'tbl_cliente'
                  AND column_name = 'site_url'
                """
            )
            row = cur.fetchone()
        if row:
            print(f"[migration] OK — site_url presente: {row}")
            return 0
        print("[migration] ERRO — coluna site_url ainda não existe após o ALTER.",
              file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
