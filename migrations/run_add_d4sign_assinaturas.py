#!/usr/bin/env python
"""Libera o provider D4Sign e cria as tabelas da mesa de assinaturas."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from integration_provider_check_lib import ensure_provider_in_check, provider_in_check_constraint


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_d4sign_assinaturas.sql")


def main():
    sql = SQL_PATH.read_text(encoding="utf-8")
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cursor:
            ensure_provider_in_check(cursor, "d4sign")
            cursor.execute(sql)
            if not provider_in_check_constraint(cursor, "d4sign"):
                raise RuntimeError("A constraint de integrações não aceitou o D4Sign.")
            cursor.execute(
                """
                SELECT to_regclass('public.cx_documento') AS documento,
                       to_regclass('public.cx_documento_signatario') AS signatario,
                       to_regclass('public.cx_documento_evento') AS evento
                """
            )
            tables = cursor.fetchone()
        conn.commit()

    if not all((tables or {}).get(name) for name in ("documento", "signatario", "evento")):
        raise RuntimeError("As tabelas da mesa de assinaturas não foram criadas.")
    print("D4Sign e mesa de assinaturas prontos no banco.")


if __name__ == "__main__":
    main()
