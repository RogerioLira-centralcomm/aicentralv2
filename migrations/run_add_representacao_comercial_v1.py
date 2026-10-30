#!/usr/bin/env python
"""Schema da trilha Representação Comercial v1."""

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
SQL_PATH = Path(__file__).with_name("add_representacao_comercial_v1.sql")


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
        print(f"[migration] Falha ao conectar: {exc}", file=sys.stderr)
        return 2

    try:
        with conn.cursor() as cur:
            cur.execute(SQL_PATH.read_text(encoding="utf-8"))
            cur.execute(
                "SELECT to_regclass('public.cadu_pi_representacao_relatorio') AS t"
            )
            ok = cur.fetchone()
        conn.commit()
        if ok and ok.get("t"):
            print("[migration] OK — representacao_comercial v1")
            return 0
        print("[migration] ERRO — tabelas não criadas.", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
