#!/usr/bin/env python3
"""Cria os índices das leituras por projeto do Workspace (aditivo, idempotente).

NÃO está em migrations/ORDER.txt: só entra no deploy quando alguém registrar a linha
`migrations/run_add_workspace_query_indexes.py`. CREATE INDEX comum bloqueia escritas na tabela
enquanto roda; com as tabelas deste porte é uma questão de segundos, por isso o lock_timeout curto.
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name('add_workspace_query_indexes.sql')


def main():
    load_dotenv(ROOT / '.env')
    required = [key for key in ('DB_HOST', 'DB_NAME', 'DB_USER') if not os.getenv(key)]
    if required:
        raise RuntimeError('Configuração ausente: ' + ', '.join(required))
    with psycopg.connect(host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
                         password=os.getenv('DB_PASSWORD', ''), port=os.getenv('DB_PORT', '5432'), connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute(SQL_PATH.read_text(encoding='utf-8'))
    print('Índices de leitura por projeto do Workspace garantidos.')


if __name__ == '__main__':
    main()
