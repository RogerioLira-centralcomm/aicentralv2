#!/usr/bin/env python3
"""Check or apply the additive external-link dock constraint.

Without --apply this performs only a read-only schema check. The configured
database may be remote, so applying is always an explicit choice.
"""
import argparse
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name('add_cadu_workspace_external_dock_shortcuts.sql')
CONSTRAINT = 'cadu_workspace_dock_shortcuts_shortcut_type_check'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply the migration to the configured database')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    missing = [key for key in ('DB_HOST', 'DB_NAME', 'DB_USER') if not os.getenv(key)]
    if missing:
        raise RuntimeError('Configuração ausente: ' + ', '.join(missing))
    with psycopg.connect(
        host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'], password=os.getenv('DB_PASSWORD', ''),
        port=os.getenv('DB_PORT', '5432'), connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '45s'")
            cursor.execute('SET LOCAL search_path TO public')
            cursor.execute("SELECT to_regclass('public.cadu_workspace_dock_shortcuts')")
            if not cursor.fetchone()[0]:
                raise RuntimeError('Tabela da dock ausente; aplique primeiro a migração base do Workspace.')
            if args.apply:
                cursor.execute(SQL_PATH.read_text(encoding='utf-8'))
            cursor.execute("""SELECT pg_get_constraintdef(oid) FROM pg_constraint
                               WHERE conrelid = 'public.cadu_workspace_dock_shortcuts'::regclass
                                 AND conname = %s""", (CONSTRAINT,))
            result = cursor.fetchone()
            ready = bool(result and "'external'" in result[0])
            if args.apply and not ready:
                raise RuntimeError('A constraint não passou a aceitar atalhos externos.')
    print('Dock externa pronta.' if ready else 'Migração da dock externa pendente. Execute com --apply no ambiente autorizado.')


if __name__ == '__main__':
    main()
