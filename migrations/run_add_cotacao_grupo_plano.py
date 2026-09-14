#!/usr/bin/env python
"""Adiciona família de versões (grupo_plano_id + eh_principal) às cotações."""

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
SQL_PATH = Path(__file__).with_name("add_cotacao_grupo_plano.sql")


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
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'cadu_cotacoes'
                  AND column_name IN ('grupo_plano_id', 'eh_principal')
                ORDER BY column_name
                """
            )
            columns = [row["column_name"] for row in cur.fetchall()]
        conn.commit()
        if columns == ["eh_principal", "grupo_plano_id"]:
            print("[migration] OK — grupo_plano_id e eh_principal presentes")
            return 0
        print(f"[migration] ERRO — colunas incompletas: {columns}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
