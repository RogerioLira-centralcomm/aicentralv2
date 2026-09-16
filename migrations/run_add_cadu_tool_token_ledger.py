#!/usr/bin/env python3
"""Aplica e valida o ledger de créditos/tokens das ferramentas Cadu."""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name("add_cadu_tool_token_ledger.sql")
EXPECTED = {
    "cadu_credits_extras": {
        "id", "id_cliente", "tokens_amount", "tokens_used", "purchased_at",
        "expires_at", "status", "created_at",
    },
    "cadu_tools_token_usage": {
        "id", "idempotency_key", "id_cliente", "id_contato_cliente",
        "ferramenta", "etapa", "modelo", "tokens_entrada", "tokens_saida",
        "total_tokens", "tokens_cobrados", "custo_interno",
        "custo_adicional", "moeda", "metadata", "status", "charged_at",
        "created_at",
    },
}


def main():
    load_dotenv(ROOT / ".env")
    missing = [key for key in ("DB_HOST", "DB_NAME", "DB_USER") if not os.getenv(key)]
    if missing:
        raise RuntimeError("Configuração ausente: " + ", ".join(missing))

    with psycopg.connect(
        host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"], password=os.getenv("DB_PASSWORD", ""),
        port=os.getenv("DB_PORT", "5432"), connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            cursor.execute("SET LOCAL search_path TO public")
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            for table, expected in EXPECTED.items():
                cursor.execute(
                    """SELECT column_name FROM information_schema.columns
                         WHERE table_schema = 'public' AND table_name = %s""",
                    (table,),
                )
                found = {row[0] for row in cursor.fetchall()}
                if not expected.issubset(found):
                    raise RuntimeError("Schema incompleto: " + table)

            cursor.execute(
                "SELECT to_regclass('public.idx_cadu_tools_token_usage_client_created')"
            )
            if cursor.fetchone()[0] is None:
                raise RuntimeError("Índice de consumo por cliente ausente.")

    print("Ledger Cadu aplicado e validado. Nenhum crédito ou consumo foi criado.")


if __name__ == "__main__":
    main()
