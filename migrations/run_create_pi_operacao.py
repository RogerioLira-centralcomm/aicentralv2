#!/usr/bin/env python
"""Executa migrations/create_pi_operacao.sql e valida coluna/tabelas."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

sql_path = Path(__file__).resolve().parent / 'create_pi_operacao.sql'
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
            """
            SELECT column_name, data_type
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'cadu_pi_campanha'
               AND column_name = 'id_responsavel_operacao'
            """
        )
        coluna = cur.fetchone()
        cur.execute(
            """
            SELECT table_name
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name = 'cadu_pi_operacao_etapa'
            """
        )
        tabela_etapa = cur.fetchone()

    print('Migration executada com sucesso.')
    print('cadu_pi_campanha.id_responsavel_operacao:', coluna)
    print('cadu_pi_operacao_etapa:', tabela_etapa)

    if not coluna or not tabela_etapa:
        raise SystemExit('Validacao falhou: coluna ou tabela nao encontrada.')
finally:
    conn.close()
