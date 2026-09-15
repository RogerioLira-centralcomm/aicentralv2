#!/usr/bin/env python3
"""Apply and verify the shared Cadu SSO ticket table."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name("add_cadu_sso_tickets.sql")
load_dotenv(ROOT / ".env")


def main():
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            cursor.execute("SELECT to_regclass('public.cadu_sso_tickets')")
            if cursor.fetchone()[0] != "cadu_sso_tickets":
                raise RuntimeError("Tabela cadu_sso_tickets não foi criada.")
        conn.commit()
    print("Cadu SSO pronto: tabela de tickets verificada.")


if __name__ == "__main__":
    main()
