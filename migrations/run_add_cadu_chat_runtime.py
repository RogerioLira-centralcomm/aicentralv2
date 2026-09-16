#!/usr/bin/env python3
"""Apply and validate the additive Cadu conversation runtime migrations.

This runner requires an explicitly configured database and applies no feature
flags. It is safe to run again because every table, index and column creation
in the migration chain is idempotent.
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    'add_cadu_family.sql',
    'add_cadu_chat_request_hash.sql',
    'add_cadu_chat_jobs.sql',
    'add_cadu_family_skills_profile.sql',
)
EXPECTED_COLUMNS = {
    'cadu_family_conversation_context': {'conversation_id', 'profile', 'project_ref', 'brand_ref'},
    'cadu_family_chat_runs': {'id', 'conversation_id', 'status', 'request_hash'},
    'cadu_family_chat_jobs': {'run_id', 'payload', 'claimed_at', 'finished_at'},
    'cadu_family_chat_events': {'id', 'run_id', 'event', 'created_at'},
}


def main():
    load_dotenv(ROOT / '.env')
    missing = [key for key in ('DB_HOST', 'DB_NAME', 'DB_USER') if not os.getenv(key)]
    if missing:
        raise RuntimeError('Configuração ausente: ' + ', '.join(missing))

    migrations_dir = Path(__file__).resolve().parent
    with psycopg.connect(
        host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'], password=os.getenv('DB_PASSWORD', ''),
        port=os.getenv('DB_PORT', '5432'), connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '45s'")
            cursor.execute('SET LOCAL search_path TO public')
            for filename in MIGRATIONS:
                cursor.execute((migrations_dir / filename).read_text(encoding='utf-8'))

            for table, expected in EXPECTED_COLUMNS.items():
                cursor.execute(
                    """SELECT column_name FROM information_schema.columns
                         WHERE table_schema = 'public' AND table_name = %s""",
                    (table,),
                )
                found = {row[0] for row in cursor.fetchall()}
                if not expected.issubset(found):
                    raise RuntimeError(f'Schema incompleto: {table}')

            cursor.execute(
                """SELECT pg_get_constraintdef(oid)
                     FROM pg_constraint
                    WHERE conrelid = 'public.cadu_family_conversation_context'::regclass
                      AND conname = 'cadu_family_conversation_context_profile_check'"""
            )
            constraint = cursor.fetchone()
            if not constraint or 'skills' not in constraint[0]:
                raise RuntimeError('Constraint de perfis não inclui Skills.')

    print(
        'Migrações Cadu aplicadas e validadas: contexto, recuperação, fila, '
        'eventos e perfil Skills. Nenhuma flag foi ativada.'
    )


if __name__ == '__main__':
    main()
