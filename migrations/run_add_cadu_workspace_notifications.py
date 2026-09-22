#!/usr/bin/env python3
"""Apply and validate the durable Workspace notification inbox."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = Path(__file__).with_name('add_cadu_workspace_notifications.sql')
EXPECTED = {
    'id', 'organization_id', 'client_id', 'user_id', 'project_ref', 'brand_ref',
    'conversation_id', 'run_id', 'long_job_id', 'source_id', 'notification_type',
    'status', 'title', 'detail', 'action_payload', 'created_at', 'updated_at',
    'read_at', 'resolved_at', 'archived_at',
}


def main():
    load_dotenv(ROOT / '.env')
    missing = [key for key in ('DB_HOST', 'DB_NAME', 'DB_USER') if not os.getenv(key)]
    if missing:
        raise RuntimeError('Configuração ausente: ' + ', '.join(missing))
    with psycopg.connect(host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'],
                         user=os.environ['DB_USER'], password=os.getenv('DB_PASSWORD', ''),
                         port=os.getenv('DB_PORT', '5432'), connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '45s'")
            cursor.execute("SET LOCAL search_path TO public")
            cursor.execute(MIGRATION.read_text(encoding='utf-8'))
            cursor.execute("""SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='cadu_workspace_notifications'""")
            found = {row[0] for row in cursor.fetchall()}
            if not EXPECTED.issubset(found):
                raise RuntimeError('Schema de notificações incompleto.')
            cursor.execute("""SELECT 1 FROM pg_trigger
                WHERE tgname='trg_cadu_notify_long_job_change' AND NOT tgisinternal""")
            if not cursor.fetchone():
                raise RuntimeError('Trigger de tarefas longas não foi instalado.')
    print('Central de notificações aplicada e conectada às tarefas longas.')


if __name__ == '__main__':
    main()
