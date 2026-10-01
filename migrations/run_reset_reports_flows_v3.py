"""Limpa todos os dados do Fluxos para a estrutura v3 começar sem legado.

Mantém a Super Tag, os sites, os eventos do site e tudo o que não é do Fluxos.
Por padrão só mostra o que seria apagado. Para apagar de verdade:

    RESET_REPORTS_FLOWS=1 python migrations/run_reset_reports_flows_v3.py --confirm

Nunca entra no deploy automático.
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Ordem de dependência: quem aponta para outra tabela sai antes dela.
FLOW_TABLES = (
    "cadu_reports_flow_events",
    "cadu_reports_flow_events_test",
    "cadu_reports_flow_sessions",
    "cadu_reports_flow_suggestions",
    "cadu_reports_flow_monitor_checks",
    "cadu_reports_flow_probe_runs",
    "cadu_reports_flow_plan_versions",
    "cadu_reports_flow_versions",
    "cadu_reports_flow_grants",
    "cadu_reports_flow_steps",
    "cadu_reports_flow_discovered_pages",
    "cadu_reports_flow_discovery_runs",
    "cadu_reports_flow_rate_limits",
    "cadu_reports_flow_tag_isolation_audit",
    "cadu_reports_flow_registry",
)


def existing(cursor, tables):
    cursor.execute("SELECT t FROM unnest(%s::text[]) AS t WHERE to_regclass('public.' || t) IS NOT NULL", (list(tables),))
    return [row[0] for row in cursor.fetchall()]


def outside_tag_references(cursor):
    """Tables outside the Flows product that point at site tags must keep their tags."""
    cursor.execute("""SELECT DISTINCT cl.relname, a.attname
        FROM pg_constraint c
        JOIN pg_class cl ON cl.oid = c.conrelid
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
        WHERE c.contype = 'f' AND c.confrelid = 'public.cadu_reports_site_tags'::regclass""")
    return [(table, column) for table, column in cursor.fetchall() if table not in FLOW_TABLES]


def main(confirm):
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    ) as conn:
        with conn.cursor() as cursor:
            tables = existing(cursor, FLOW_TABLES)
            keep = outside_tag_references(cursor)
            guard = " AND ".join(f"NOT EXISTS (SELECT 1 FROM {table} r WHERE r.{column} = t.id)" for table, column in keep)
            tag_filter = "t.tag_kind = 'flow'" + (f" AND {guard}" if guard else "")
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                print(f"{table}: {cursor.fetchone()[0]} linha(s)")
            cursor.execute(f"SELECT COUNT(*) FROM cadu_reports_site_tags t WHERE {tag_filter}")
            print(f"cadu_reports_site_tags (tags internas de fluxo sem outro uso): {cursor.fetchone()[0]} linha(s)")
            if keep:
                print("Tags usadas fora do Fluxos são mantidas: " + ", ".join(f"{t}.{c}" for t, c in keep))
            if not confirm:
                print("Nada foi apagado. Use RESET_REPORTS_FLOWS=1 e --confirm para limpar.")
                return
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
            cursor.execute(f"DELETE FROM cadu_reports_site_tags t WHERE {tag_filter}")
            print(f"Tags internas de fluxo apagadas: {cursor.rowcount}")
        conn.commit()
    print("Dados do Fluxos limpos. Super Tag, sites e eventos do site foram mantidos.")


if __name__ == "__main__":
    wants = "--confirm" in sys.argv[1:]
    if wants and os.getenv("RESET_REPORTS_FLOWS") != "1":
        raise SystemExit("Defina RESET_REPORTS_FLOWS=1 junto com --confirm para apagar os dados do Fluxos.")
    main(confirm=wants)
