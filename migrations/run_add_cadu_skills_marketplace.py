#!/usr/bin/env python3
"""Aplica e verifica a fundação relacional do Cadu Skills."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_cadu_skills_marketplace.sql")
TABLES = (
    "cadu_skill_definitions", "cadu_skill_versions", "cadu_skill_customizations",
    "cadu_skill_shares", "cadu_skill_runs", "cadu_credit_ledger",
)


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
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name = ANY(%s)",
                (list(TABLES),),
            )
            found = {row["table_name"] for row in cursor.fetchall()}
        conn.commit()
    missing = set(TABLES) - found
    if missing:
        raise RuntimeError(f"Tabelas não criadas: {', '.join(sorted(missing))}")
    print(f"Cadu Skills pronto: {len(found)} tabelas verificadas.")


if __name__ == "__main__":
    main()
