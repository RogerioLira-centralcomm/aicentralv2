#!/usr/bin/env python
"""Executa migrations/create_pi_financeiro.sql e valida tabelas."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

sql_path = Path(__file__).resolve().parent / "create_pi_financeiro.sql"
sql = sql_path.read_text(encoding="utf-8")

conn = psycopg.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "aicentral_db"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "postgres"),
    row_factory=dict_row,
)
try:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name IN (
                   'cadu_pi_financeiro',
                   'cadu_pi_resultado_fechamento',
                   'cadu_pi_resultado_campanha'
               )
             ORDER BY table_name
            """
        )
        tabelas = [row["table_name"] for row in cur.fetchall()]

    print("Migration executada com sucesso.")
    print("tabelas:", tabelas)
    if len(tabelas) != 3:
        raise SystemExit("Validacao falhou: tabelas financeiras ausentes.")
finally:
    conn.close()
