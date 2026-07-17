#!/usr/bin/env python
"""Executa migrations/add_pi_status_cancelado.sql e valida os registros."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

sql_path = Path(__file__).resolve().parent / 'add_pi_status_cancelado.sql'
sql = sql_path.read_text(encoding='utf-8')

conn = psycopg.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', 5432)),
    dbname=os.getenv('DB_NAME', 'aicentral_db'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', 'postgres'),
    row_factory=dict_row,
)
try:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, descricao FROM cadu_pi_aux_status WHERE descricao = %s",
            ('Cancelado',),
        )
        pi_status = cur.fetchone()
        cur.execute(
            "SELECT key, display FROM cadu_pi_sub_status WHERE display = %s",
            ('Cancelado',),
        )
        pi_sub = cur.fetchone()
        cur.execute(
            "SELECT id, descricao FROM cadu_pi_camp_status WHERE descricao = %s",
            ('Cancelada',),
        )
        camp = cur.fetchone()

    print('Migration executada com sucesso.')
    print('cadu_pi_aux_status:', pi_status)
    print('cadu_pi_sub_status:', pi_sub)
    print('cadu_pi_camp_status:', camp)

    if not pi_status or not pi_sub or not camp:
        raise SystemExit('Validacao falhou: algum status nao foi encontrado.')
finally:
    conn.close()
