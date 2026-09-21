"""Apply and validate the normalized evidence storage for brand audits."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name('add_workspace_brand_audit_evidence.sql')
EXPECTED = {
    'cadu_workspace_brand_audit_sources',
    'cadu_workspace_brand_audit_evidence',
    'cadu_workspace_brand_audit_agents',
    'cadu_workspace_brand_audit_assets',
    'cadu_workspace_brand_profile_snapshots',
    'cadu_workspace_brand_campaigns',
}


def run_migration():
    load_dotenv(ROOT / '.env')
    missing = [key for key in ('DB_HOST', 'DB_NAME', 'DB_USER') if not os.getenv(key)]
    if missing:
        raise RuntimeError('Configuração ausente: ' + ', '.join(missing))
    with psycopg.connect(host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
                         password=os.getenv('DB_PASSWORD', ''), port=os.getenv('DB_PORT', '5432'), connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '45s'")
            cursor.execute(SQL_PATH.read_text(encoding='utf-8'))
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = ANY(%s)", (list(EXPECTED),))
            found = {row[0] for row in cursor.fetchall()}
            if found != EXPECTED:
                raise RuntimeError('Schema de evidências incompleto: ' + ', '.join(sorted(EXPECTED - found)))
    print('Migração aplicada e validada: evidências e campanhas de auditoria de marca.')


if __name__ == '__main__':
    run_migration()
