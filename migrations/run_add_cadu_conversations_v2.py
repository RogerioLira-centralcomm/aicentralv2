#!/usr/bin/env python3
"""Apply and validate the additive Conversations V2 storage."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name("add_cadu_conversations_v2.sql")
EXPECTED = {
    "cadu_workspace_artifacts": {"id", "organization_id", "client_id", "project_ref", "conversation_id", "type", "title", "status", "current_version", "created_by"},
    "cadu_workspace_artifact_versions": {"id", "artifact_id", "version", "content", "change_summary", "created_by"},
    "cadu_agent_tool_calls": {"id", "run_id", "tool_name", "status", "input_redacted", "output_summary", "duration_ms", "error_code"},
    "cadu_family_chat_runs": {"runtime_version", "route", "request_context", "response_policy", "context_chars", "first_token_ms", "total_duration_ms"},
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
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            for table, expected in EXPECTED.items():
                cursor.execute("""SELECT column_name FROM information_schema.columns
                                   WHERE table_schema = 'public' AND table_name = %s""", (table,))
                found = {row[0] for row in cursor.fetchall()}
                if not expected.issubset(found):
                    raise RuntimeError("Schema V2 incompleto: " + table)
    print("Conversations V2: artefatos, versões, auditoria de tools e telemetria instalados. A flag não foi ativada.")


if __name__ == "__main__":
    main()
