"""Preview or prune old raw Reports events. Use --apply from a scheduled job."""
import argparse
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def main():
    parser = argparse.ArgumentParser(description='Retenção de eventos brutos do Cadu Reports')
    parser.add_argument('--flow-days', type=int, default=180)
    parser.add_argument('--crm-days', type=int, default=400)
    parser.add_argument('--apply', action='store_true', help='Executa a exclusão; sem esta opção apenas conta')
    args = parser.parse_args()
    if not 30 <= args.flow_days <= 3650 or not 30 <= args.crm_days <= 3650:
        parser.error('Os períodos precisam estar entre 30 e 3650 dias.')
    tables = (
        ('cadu_reports_flow_events', args.flow_days),
        ('cadu_reports_external_conversions', args.crm_days),
    )
    with psycopg.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '5432')),
        dbname=os.getenv('DB_NAME', 'aicentralv2'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
    ) as conn:
        for table, days in tables:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE occurred_at < NOW() - (%s * INTERVAL '1 day')", (days,))
                count = cursor.fetchone()[0]
            print(f'{table}: {count} registros com mais de {days} dias')
            if not args.apply:
                continue
            removed = 0
            while True:
                with conn.cursor() as cursor:
                    cursor.execute(f'''DELETE FROM {table} WHERE id IN (
                        SELECT id FROM {table} WHERE occurred_at < NOW() - (%s * INTERVAL '1 day')
                        ORDER BY occurred_at LIMIT 10000
                    )''', (days,))
                    batch = cursor.rowcount
                conn.commit()
                removed += batch
                if batch < 10000:
                    break
            print(f'{table}: {removed} registros removidos')


if __name__ == '__main__':
    main()
