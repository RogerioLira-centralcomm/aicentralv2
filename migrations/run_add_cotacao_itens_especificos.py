#!/usr/bin/env python
"""Cria e valida os itens de montagem das cotações não-Mídia."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_cotacao_itens_especificos.sql")


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
                "SELECT to_regclass('public.cadu_cotacao_itens_especificos') AS tabela"
            )
            validation = cursor.fetchone()
        if not validation or not validation["tabela"]:
            raise RuntimeError("Tabela de itens específicos não foi criada.")
    print("Montagem tipada de cotações criada e validada.")


if __name__ == "__main__":
    main()
