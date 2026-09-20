#!/usr/bin/env python3
"""Restore CENTRALCOMM's permanent Pro plan and internal test-credit lot."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name("restore_centralcomm_test_credits.sql")


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
            cursor.execute(
                """SELECT p.plan_definition_name, p.tokens_monthly_limit,
                          l.tokens_amount - l.tokens_used AS available
                     FROM cadu_credit_entitlements e
                     JOIN cadu_credits_extras l ON l.id = e.credit_lot_id
                     JOIN (SELECT cp.id_cliente, pd.plan_name AS plan_definition_name,
                                  cp.tokens_monthly_limit
                             FROM cadu_client_plans cp
                             JOIN cadu_plan_definitions pd ON pd.id = cp.id_plan_definition
                            WHERE cp.id_cliente = 174) p ON p.id_cliente = e.id_cliente
                    WHERE e.id_cliente = 174
                      AND e.entitlement_key = 'centralcomm_internal_test_2m'"""
            )
            plan_name, monthly_limit, available = cursor.fetchone()
    print(f"CENTRALCOMM restaurada: plano {plan_name}; limite {monthly_limit}; saldo {available}.")


if __name__ == "__main__":
    main()
