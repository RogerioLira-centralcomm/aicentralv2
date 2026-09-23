"""Apply and validate the OAuth 2.1 schema for the public Cadu MCP."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    sql = Path(__file__).with_name("add_cadu_public_mcp_oauth.sql").read_text(encoding="utf-8")
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            cursor.execute(
                """SELECT
                    to_regclass('public.cadu_oauth_clients') AS clients,
                    to_regclass('public.cadu_oauth_grants') AS grants,
                    to_regclass('public.cadu_oauth_authorization_codes') AS codes,
                    to_regclass('public.cadu_oauth_access_tokens') AS access_tokens,
                    to_regclass('public.cadu_oauth_refresh_tokens') AS refresh_tokens"""
            )
            validation = cursor.fetchone()
            cursor.execute(
                """SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='cadu_public_mcp_usage'
                      AND column_name IN ('credential_type','credential_id')"""
            )
            usage_columns = {row["column_name"] for row in cursor.fetchall()}
        connection.commit()
    if not all(validation.values()):
        raise RuntimeError(f"Validação do schema OAuth do MCP falhou: {validation}")
    if usage_columns != {"credential_type", "credential_id"}:
        raise RuntimeError(f"Colunas de auditoria OAuth ausentes: {usage_columns}")
    print("OK public Cadu MCP OAuth schema")


if __name__ == "__main__":
    main()
