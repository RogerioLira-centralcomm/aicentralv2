#!/usr/bin/env python3
"""Apply the one-time 100k Cadu Token launch allowance safely."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name("add_cadu_launch_credit.sql")


def main():
    load_dotenv(ROOT / ".env")
    missing = [key for key in ("DB_HOST", "DB_NAME", "DB_USER") if not os.getenv(key)]
    if missing:
        raise RuntimeError("Configuração ausente: " + ", ".join(missing))
    with psycopg.connect(
        host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
        password=os.getenv("DB_PASSWORD", ""), port=os.getenv("DB_PORT", "5432"), connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '45s'")
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            cursor.execute("""SELECT COUNT(*) FROM cadu_credit_entitlements
                               WHERE entitlement_key = 'cadu_launch_100k' AND status = 'granted'""")
            granted = cursor.fetchone()[0]
            cursor.execute("""SELECT COUNT(*) FROM cadu_credit_entitlements
                               WHERE entitlement_key = 'cadu_launch_100k' AND status = 'excluded_test'""")
            excluded = cursor.fetchone()[0]
    print(f"Benefício Cadu aplicado: {granted} concessões; {excluded} exceção de teste.")


if __name__ == "__main__":
    main()
