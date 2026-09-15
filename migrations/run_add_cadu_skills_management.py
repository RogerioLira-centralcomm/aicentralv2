#!/usr/bin/env python3
"""Aplica ranking, gestão e métricas do Cadu Skills."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_cadu_skills_management.sql")


def main():
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""), row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            cursor.execute("SELECT COUNT(*) AS total FROM cadu_skill_definitions WHERE owner_type='centralx' AND is_testable=TRUE")
            total = int(cursor.fetchone()["total"])
        conn.commit()
    if total < 10:
        raise RuntimeError(f"Esperadas 10 skills de teste; encontradas {total}.")
    print(f"Cadu Skills: {total} skills de teste e métricas prontas.")


if __name__ == "__main__":
    main()
