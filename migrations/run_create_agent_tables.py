#!/usr/bin/env python
"""Executa migrations/create_agent_tables.sql e valida as tabelas do Agente CentralX."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

sql_path = Path(__file__).resolve().parent / 'create_agent_tables.sql'
sql = sql_path.read_text(encoding='utf-8')

EXPECTED_TABLES = (
    'agent_conversations',
    'agent_messages',
    'agent_tool_calls',
)

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
            """
            SELECT table_name
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name = ANY(%s)
             ORDER BY table_name
            """,
            (list(EXPECTED_TABLES),),
        )
        found = [row['table_name'] for row in (cur.fetchall() or [])]

    print('Migration executada com sucesso.')
    for table in EXPECTED_TABLES:
        print(f'  {table}:', 'OK' if table in found else 'FALTANDO')

    missing = [t for t in EXPECTED_TABLES if t not in found]
    if missing:
        raise SystemExit(f'Validacao falhou: tabelas ausentes: {", ".join(missing)}')
finally:
    conn.close()
