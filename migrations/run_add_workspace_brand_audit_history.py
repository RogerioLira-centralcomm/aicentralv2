#!/usr/bin/env python3
"""Apply the additive brand-audit history migration."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name('add_workspace_brand_audit_history.sql')


def main():
    load_dotenv(ROOT / '.env')
    required = [key for key in ('DB_HOST', 'DB_NAME', 'DB_USER') if not os.getenv(key)]
    if required:
        raise RuntimeError('Configuração ausente: ' + ', '.join(required))
    with psycopg.connect(host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
                         password=os.getenv('DB_PASSWORD', ''), port=os.getenv('DB_PORT', '5432'), connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute('SET LOCAL lock_timeout = \'5s\'')
            cur.execute(SQL_PATH.read_text(encoding='utf-8'))
            cur.execute("SELECT to_regclass('public.cadu_workspace_brand_audit_runs')")
            if cur.fetchone()[0] is None:
                raise RuntimeError('Tabela de histórico de auditoria ausente.')
    print('Migração aplicada e validada: histórico de auditorias de marca.')


if __name__ == '__main__':
    main()
