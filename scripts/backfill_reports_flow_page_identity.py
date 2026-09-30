"""Fill additive page identity in bounded, repeatable batches after M2 migration."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg
from aicentralv2.db import get_db_config
from aicentralv2.cadu_connect.reports_page_paths import normalize_page_path


def backfill(batch_size=1000):
    total = 0
    with psycopg.connect(**get_db_config()) as conn:
        while True:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT id,path_prefix
                    FROM cadu_reports_flow_discovered_pages
                    WHERE normalized_path IS NULL OR locale IS NULL
                    ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED''', (batch_size,))
                rows = cursor.fetchall()
                if not rows:
                    break
                for row in rows:
                    normalized = normalize_page_path(row['path_prefix'])
                    cursor.execute('''UPDATE cadu_reports_flow_discovered_pages
                        SET locale=%s,normalized_path=%s
                        WHERE id=%s AND (normalized_path IS NULL OR locale IS NULL)''',
                        (normalized['locale'], normalized['path'], row['id']))
            conn.commit()
            total += len(rows)
    return total


if __name__ == '__main__':
    print(f'{backfill()} páginas atualizadas')
