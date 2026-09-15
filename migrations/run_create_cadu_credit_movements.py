#!/usr/bin/env python
"""Cria o livro auditável de créditos do Cadu na base compartilhada."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

sql = (Path(__file__).with_name("create_cadu_credit_movements.sql")).read_text(encoding="utf-8")
conn = psycopg.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "aicentral_db"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres"),
)
try:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("Migration cadu_credit_movements executada com sucesso.")
finally:
    conn.close()
