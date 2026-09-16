#!/usr/bin/env python3
"""Aplica a tabela de alertas de saldo do ledger Cadu."""
import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
load_dotenv(root / ".env")
sql = Path(__file__).with_name("add_cadu_credit_alerts.sql")
with psycopg.connect(host=os.environ["DB_HOST"], port=os.getenv("DB_PORT", "5432"), dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"], password=os.getenv("DB_PASSWORD", "")) as conn:
    with conn.cursor() as cur:
        cur.execute(sql.read_text())
    conn.commit()
print("Alertas de créditos prontos.")
