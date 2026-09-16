#!/usr/bin/env python3
"""Apply and validate Connect report storage atomically on the configured DB."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name('add_connect_report_workspace.sql')
EXPECTED = {
    'cadu_connect_report_workspaces': {
        'id', 'organization_id', 'client_id', 'project_ref', 'campaign_name',
        'campaign_key', 'document', 'revision', 'created_by', 'updated_by',
        'created_at', 'updated_at',
    },
    'cadu_connect_report_workspace_versions': {
        'report_id', 'revision', 'document', 'note', 'created_by', 'created_at',
    },
}


def main():
    load_dotenv(ROOT / '.env')
    # Require explicit configuration: do not accidentally migrate a default DB.
    missing = [key for key in ('DB_HOST', 'DB_NAME', 'DB_USER') if not os.getenv(key)]
    if missing:
        raise RuntimeError('Configuração ausente: ' + ', '.join(missing))
    with psycopg.connect(host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'],
                         user=os.environ['DB_USER'], password=os.getenv('DB_PASSWORD', ''),
                         port=os.getenv('DB_PORT', '5432'), connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            cursor.execute('SET LOCAL search_path TO public')
            cursor.execute(SQL_PATH.read_text(encoding='utf-8'))
            for table, expected in EXPECTED.items():
                cursor.execute('''SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s''', (table,))
                found = {row[0] for row in cursor.fetchall()}
                if not expected.issubset(found):
                    raise RuntimeError('Schema incompleto: ' + table)
                cursor.execute('''SELECT contype FROM pg_constraint
                    WHERE conrelid=to_regclass(%s)''', ('public.' + table,))
                kinds = {row[0] for row in cursor.fetchall()}
                needed = {'p', 'u', 'c'} if table.endswith('workspaces') else {'p', 'f'}
                if not needed.issubset(kinds):
                    raise RuntimeError('Constraints incompletas: ' + table)
            cursor.execute("SELECT to_regclass('public.idx_connect_report_workspace_client')")
            if cursor.fetchone()[0] is None:
                raise RuntimeError('Índice de biblioteca ausente.')
    print(f'Migration aplicada e validada: {len(EXPECTED)} tabelas, constraints e índice. Sem dados de teste inseridos.')


if __name__ == '__main__':
    main()
