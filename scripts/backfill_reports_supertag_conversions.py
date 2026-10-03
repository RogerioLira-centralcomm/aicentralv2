"""Create the derived Super Tag conversions for events received before the conversion rules existed.

Run only on request. Dry run by default (prints what would be created); ``--apply`` writes.

    .venv/bin/python scripts/backfill_reports_supertag_conversions.py --site <public_id> --days 30
    .venv/bin/python scripts/backfill_reports_supertag_conversions.py --site <public_id> --days 30 --apply

Uses the same rules as the collector (aicentralv2.cadu_connect.reports_supertag_leads): the saved
``config.conversion_rules`` or, when there are none, the default thank-you page rules. Derived ids are
``uuid5(site, source_event_id)``, so running it twice never duplicates; a thank-you page already converted in a
session is skipped, and so is a conversion with the same name (or a trackConversion on the same page) in the same
session within 5 minutes, exactly as the collector does. Pending leads of those sessions are confirmed as well.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aicentralv2.cadu_connect.reports_supertag_leads import (  # noqa: E402
    CONFIRM_SKEW, CONFIRM_WINDOW, DEDUPE_WINDOW, dedupe_conversions, derive_conversions)


def _stored_conversions(rows):
    return [{'session_id': str(r['session_id']), 'event_name': r['event_name'], 'page_path': r['page_path'],
             'occurred_at': r['occurred_at'], 'derived_from': json.loads(r['event_data'] or '{}').get('derived_from')}
            for r in rows if r['event_kind'] == 'conversion']


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--site', required=True, help='public_id da instalação (data-cadu-site)')
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--apply', action='store_true', help='grava; sem esta opção só simula')
    args = parser.parse_args()
    if not 1 <= args.days <= 400:
        parser.error('--days vai de 1 a 400')
    connection = psycopg.connect(
        dbname=os.getenv('DB_NAME', 'aicentral_db'), user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres'), host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'), row_factory=dict_row)
    try:
        with connection.cursor() as cursor:
            cursor.execute('''SELECT id,client_id,config FROM cadu_reports_supertag_sites
                WHERE public_id=%s AND revoked_at IS NULL''', (args.site,))
            site = cursor.fetchone()
            if not site:
                raise SystemExit('Instalação não encontrada.')
            site['id'] = str(site['id'])
            cursor.execute('''SELECT event_id,site_id,client_id,visitor_id,session_id,event_kind,event_name,page_path,
                    referrer_host,attribution::text AS attribution,event_data::text AS event_data,viewport_width,
                    viewport_height,occurred_at,expires_at
                FROM cadu_reports_supertag_events
                WHERE site_id=%s AND expires_at>NOW() AND occurred_at>=NOW()-(%s * INTERVAL '1 day')
                    AND event_kind IN ('page_view','form_submit','custom_event','conversion')
                ORDER BY occurred_at,id''', (site['id'], args.days))
            rows = cursor.fetchall()
            prepared = [(str(r['event_id']), site['id'], r['client_id'], r['visitor_id'], str(r['session_id']),
                         r['event_kind'], r['event_name'], r['page_path'], r['referrer_host'], r['attribution'],
                         r['event_data'], r['viewport_width'], r['viewport_height'], r['occurred_at']) for r in rows]
            expires = {str(r['event_id']): r['expires_at'] for r in rows}
            already = {(str(r['session_id']), r['page_path']) for r in rows if r['event_kind'] == 'conversion'
                       and json.loads(r['event_data'] or '{}').get('derived_from', 'page_view') == 'page_view'}
            source = [item for item in prepared if item[5] != 'conversion']
            stored_ids = {item[0] for item in prepared}
            derived = [item for item in derive_conversions(site, source + [item for item in prepared if item[5] == 'conversion'], already)
                       if item[0] not in stored_ids]
            derived, dropped = dedupe_conversions(derived, _stored_conversions(rows))
            print(f'{len(rows)} eventos lidos; {len(derived)} conversões derivadas a criar '
                  f'({len(dropped)} ignoradas: mesma conversão na sessão em até 5 min).')
            for item in derived[:20]:
                print(f'  {item[13]:%Y-%m-%d %H:%M}  {item[6]:<22} {item[7]}')
            if not args.apply:
                print('Simulação: nada foi gravado. Use --apply para gravar.')
                return
            # Same lock as the collector (sorted sessions): a batch arriving now waits, and the stored conversions are
            # read again under the lock before writing.
            for session_id in sorted({str(item[4]) for item in derived}):
                cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s),hashtext(%s))', (site['id'], f'session:{session_id}'))
            if derived:
                cursor.execute('''SELECT event_id,session_id,event_name,page_path,occurred_at,
                        event_data->>'derived_from' AS derived_from
                    FROM cadu_reports_supertag_events
                    WHERE site_id=%s AND session_id = ANY(%s::uuid[]) AND event_kind='conversion'
                        AND occurred_at BETWEEN %s AND %s''',
                    (site['id'], sorted({str(item[4]) for item in derived}),
                     min(item[13] for item in derived) - DEDUPE_WINDOW, max(item[13] for item in derived) + DEDUPE_WINDOW))
                derived, _late = dedupe_conversions(derived, cursor.fetchall())
            created = 0
            for item in derived:
                source_id = json.loads(item[10])['source_event_id']
                cursor.execute('''INSERT INTO cadu_reports_supertag_events
                    (event_id,site_id,client_id,visitor_id,session_id,event_kind,event_name,page_path,referrer_host,
                     attribution,event_data,viewport_width,viewport_height,occurred_at,expires_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s)
                    ON CONFLICT (site_id,event_id) DO NOTHING''', (*item, expires[source_id]))
                created += cursor.rowcount
            cursor.execute("SELECT to_regclass('public.cadu_reports_supertag_leads') IS NOT NULL AS ready")
            if cursor.fetchone()['ready']:
                for item in derived:
                    cursor.execute('''UPDATE cadu_reports_supertag_leads SET confirmed_at=%s,confirmation='rule'
                        WHERE site_id=%s AND session_id=%s AND confirmed_at IS NULL
                            AND submitted_at BETWEEN %s AND %s''',
                        (item[13], site['id'], item[4], item[13] - CONFIRM_WINDOW, item[13] + CONFIRM_SKEW))
        connection.commit()
        print(f'{created} conversões gravadas.')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
