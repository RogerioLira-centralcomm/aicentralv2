"""Read-only Reports V1 migration and client isolation audit.

Usage: python scripts/audit_reports_v1.py
Exit 0 when required tables exist and no cross-client references are found.
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

TABLES = (
    'cadu_reports_accounts', 'cadu_reports_campaigns',
    'cadu_reports_campaign_daily_metrics', 'cadu_reports_ingest_keys',
    'cadu_reports_user_access', 'cadu_reports_site_tags',
    'cadu_reports_flow_steps', 'cadu_reports_flow_events',
    'cadu_reports_flow_rate_limits', 'cadu_reports_external_conversions',
    'cadu_connect_report_workspaces', 'cadu_reports_link_test_runs',
    'cadu_reports_link_association_history',
)

CHECKS = {
    'MCC em outro cliente': '''SELECT COUNT(*) FROM cadu_reports_accounts a
        JOIN cadu_reports_accounts p ON p.id=a.parent_account_id
        WHERE (a.organization_id,a.client_id) IS DISTINCT FROM
              (p.organization_id,p.client_id)''',
    'Campanha em conta de outro cliente': '''SELECT COUNT(*) FROM cadu_reports_campaigns c
        JOIN cadu_reports_accounts a ON a.id=c.account_id
        WHERE (c.organization_id,c.client_id) IS DISTINCT FROM
              (a.organization_id,a.client_id)''',
    'Métrica em campanha de outro cliente': '''SELECT COUNT(*) FROM cadu_reports_campaign_daily_metrics m
        JOIN cadu_reports_campaigns c ON c.id=m.campaign_id
        WHERE (m.organization_id,m.client_id) IS DISTINCT FROM
              (c.organization_id,c.client_id)''',
    'Relatório em conta de outro cliente': '''SELECT COUNT(*) FROM cadu_connect_report_workspaces w
        JOIN cadu_reports_accounts a ON a.id=w.account_id
        WHERE (w.organization_id,w.client_id) IS DISTINCT FROM
              (a.organization_id,a.client_id)''',
    'Relatório em campanha de outro cliente': '''SELECT COUNT(*) FROM cadu_connect_report_workspaces w
        JOIN cadu_reports_campaigns c ON c.id=w.media_campaign_id
        WHERE (w.organization_id,w.client_id) IS DISTINCT FROM
              (c.organization_id,c.client_id)''',
    'Etapa em tag de outro cliente': '''SELECT COUNT(*) FROM cadu_reports_flow_steps s
        JOIN cadu_reports_site_tags t ON t.id=s.tag_id
        WHERE (s.organization_id,s.client_id) IS DISTINCT FROM
              (t.organization_id,t.client_id)''',
    'Evento em tag de outro cliente': '''SELECT COUNT(*) FROM cadu_reports_flow_events e
        JOIN cadu_reports_site_tags t ON t.id=e.tag_id
        WHERE (e.organization_id,e.client_id) IS DISTINCT FROM
              (t.organization_id,t.client_id)''',
    'Evento em campanha de outro cliente': '''SELECT COUNT(*) FROM cadu_reports_flow_events e
        JOIN cadu_reports_campaigns c ON c.id=e.campaign_id
        WHERE (e.organization_id,e.client_id) IS DISTINCT FROM
              (c.organization_id,c.client_id)''',
    'Conversão CRM em campanha de outro cliente': '''SELECT COUNT(*) FROM cadu_reports_external_conversions x
        JOIN cadu_reports_campaigns c ON c.id=x.campaign_id
        WHERE (x.organization_id,x.client_id) IS DISTINCT FROM
              (c.organization_id,c.client_id)''',
    'Link em campanha de outro cliente': '''SELECT COUNT(*) FROM cadu_reports_link_test_runs r
        JOIN cadu_reports_campaigns c ON c.id=r.media_campaign_id
        WHERE r.client_id IS DISTINCT FROM c.client_id''',
    'Link em relatório de outro cliente': '''SELECT COUNT(*) FROM cadu_reports_link_test_runs r
        JOIN cadu_connect_report_workspaces w ON w.id=r.report_workspace_id
        WHERE r.client_id IS DISTINCT FROM w.client_id''',
    'Histórico em link de outro cliente': '''SELECT COUNT(*) FROM cadu_reports_link_association_history h
        JOIN cadu_reports_link_test_runs r ON r.id=h.run_id
        WHERE h.client_id IS DISTINCT FROM r.client_id''',
}


def main():
    config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'dbname': os.getenv('DB_NAME', 'aicentralv2'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', ''),
        'options': '-c default_transaction_read_only=on',
        'connect_timeout': 7,
    }
    with psycopg.connect(**config) as db, db.cursor() as cursor:
        cursor.execute('SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname=%s', ('public',))
        present = {row[0] for row in cursor.fetchall()}
        missing = sorted(set(TABLES) - present)
        if missing:
            print('Migrações pendentes: ' + ', '.join(missing))
            return 2
        problems = 0
        for label, query in CHECKS.items():
            cursor.execute(query)
            count = cursor.fetchone()[0]
            print(f'{label}: {count}')
            problems += count
        print(f'Total de referências entre clientes: {problems}')
        return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
