#!/usr/bin/env python3
"""Apply and validate per-field Workspace brand reliability metadata."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name('add_workspace_brand_field_reliability.sql')


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
            checks = {
                'cadu_workspace_brand_identity_fields': {
                    'field_category', 'reason_code', 'confidence_components',
                    'evidence_ids', 'pipeline_version', 'score_version',
                },
                'cadu_workspace_brand_profile_snapshots': {
                    'pipeline_version', 'score_version', 'evidence_hash',
                },
                'cadu_workspace_brand_audit_sources': {
                    'canonical_url', 'authority', 'status',
                },
            }
            for table, expected in checks.items():
                cur.execute('''SELECT column_name FROM information_schema.columns
                               WHERE table_schema = 'public' AND table_name = %s''', (table,))
                found = {row[0] for row in cur.fetchall()}
                if not expected.issubset(found):
                    raise RuntimeError(f'Schema incompleto: {table}')
    print('Migração aplicada e validada: confiabilidade de marca por campo.')


if __name__ == '__main__':
    main()
