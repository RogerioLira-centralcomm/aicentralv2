#!/usr/bin/env python3
"""Apply and validate the durable Workspace brand-audit queue migration."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name('add_workspace_brand_audit_jobs.sql')
EXPECTED = {
    'job_id', 'client_id', 'brand_id', 'payload', 'status', 'attempts',
    'created_at', 'claimed_at', 'heartbeat_at', 'finished_at',
}


def main():
    load_dotenv(ROOT / '.env')
    missing = [key for key in ('DB_HOST', 'DB_NAME', 'DB_USER') if not os.getenv(key)]
    if missing:
        raise RuntimeError('Configuração ausente: ' + ', '.join(missing))
    with psycopg.connect(
        host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'], password=os.getenv('DB_PASSWORD', ''),
        port=os.getenv('DB_PORT', '5432'), connect_timeout=10,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute("SET LOCAL statement_timeout = '45s'")
            cur.execute('SET LOCAL search_path TO public')
            cur.execute(SQL_PATH.read_text(encoding='utf-8'))
            cur.execute('''SELECT column_name FROM information_schema.columns
                           WHERE table_schema = 'public' AND table_name = %s''',
                        ('cadu_workspace_brand_audit_jobs',))
            found = {row[0] for row in cur.fetchall()}
            if not EXPECTED.issubset(found):
                raise RuntimeError('Schema incompleto: cadu_workspace_brand_audit_jobs')
            cur.execute("SELECT to_regclass('public.cadu_workspace_brand_audit_jobs_pending')")
            if cur.fetchone()[0] is None:
                raise RuntimeError('Índice da fila de auditoria ausente.')
    print('Migração aplicada e validada: fila durável de auditoria de marca.')


if __name__ == '__main__':
    main()
