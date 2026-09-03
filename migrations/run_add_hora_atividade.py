#!/usr/bin/env python
"""Executa a migration que adiciona `hora_atividade TIME` em sales_atividades.

Uso:
    python migrations/run_add_hora_atividade.py

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

SQL_PATH = Path(__file__).resolve().parent / "add_hora_atividade_to_sales_atividades.sql"
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
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'sales_atividades'
                  AND column_name = 'hora_atividade'
                """
            )
            row = cur.fetchone()
        if row:
            print(f"[migration] OK — hora_atividade presente: {row}")
            return 0
        print("[migration] ERRO — coluna hora_atividade ainda não existe após o ALTER.",
              file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
