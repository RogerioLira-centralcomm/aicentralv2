#!/usr/bin/env python3
"""Enable the internal and external Google login credential records."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name("add_google_login_credentials.sql")
load_dotenv(ROOT / ".env")


def main():
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""), row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            cursor.execute("SELECT provider FROM system_integration_credentials WHERE provider IN ('google_login_cadu','google_login_centralx')")
            found = {row["provider"] for row in cursor.fetchall()}
        conn.commit()
    if found != {"google_login_cadu", "google_login_centralx"}:
        raise RuntimeError("Credenciais de login Google não foram preparadas.")
    print("Google Login pronto para receber as duas credenciais OAuth.")


if __name__ == "__main__":
    main()
