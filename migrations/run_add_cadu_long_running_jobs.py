#!/usr/bin/env python3
"""Apply and validate the durable Cadu long-job runtime."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = Path(__file__).with_name("add_cadu_long_running_jobs.sql")
EXPECTED = {
    "cadu_agent_long_jobs": {"id", "conversation_id", "status", "token_budget", "tokens_used", "checkpoint", "lease_expires_at"},
    "cadu_agent_long_job_units": {"id", "job_id", "position", "kind", "status", "attempts", "lease_expires_at"},
    "cadu_agent_long_job_sources": {"id", "job_id", "canonical_url", "status", "content_hash"},
    "cadu_agent_long_job_fragments": {"id", "job_id", "ordinal", "kind", "content", "content_hash"},
    "cadu_agent_long_job_calls": {"id", "job_id", "call_type", "status", "idempotency_key", "input_tokens", "output_tokens"},
}


def main():
    load_dotenv(ROOT / ".env")
    missing = [key for key in ("DB_HOST", "DB_NAME", "DB_USER") if not os.getenv(key)]
    if missing:
        raise RuntimeError("Configuração ausente: " + ", ".join(missing))
    with psycopg.connect(
        host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
        password=os.getenv("DB_PASSWORD", ""), port=os.getenv("DB_PORT", "5432"), connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '45s'")
            cursor.execute("SET LOCAL search_path TO public")
            cursor.execute(MIGRATION.read_text(encoding="utf-8"))
            for table, expected in EXPECTED.items():
                cursor.execute("""SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s""", (table,))
                found = {row[0] for row in cursor.fetchall()}
                if not expected.issubset(found):
                    raise RuntimeError(f"Schema incompleto: {table}")
            cursor.execute("""SELECT indexname FROM pg_indexes WHERE schemaname='public'
                AND indexname IN ('idx_cadu_long_jobs_queue','idx_cadu_long_units_next','idx_cadu_long_fragments_job')""")
            if len(cursor.fetchall()) != 3:
                raise RuntimeError("Índices operacionais do trabalho longo estão incompletos.")
    print("Runtime de trabalhos longos aplicado: fila, etapas, fontes, fragmentos e chamadas.")


if __name__ == "__main__":
    main()

