"""Apply and validate the public Cadu MCP tool-module schema."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    missing = [key for key in ("DB_HOST", "DB_NAME", "DB_USER") if not os.getenv(key)]
    if missing:
        raise RuntimeError("Configuração ausente: " + ", ".join(missing))
    sql = Path(__file__).with_name("add_cadu_public_mcp_modules.sql").read_text(encoding="utf-8")
    with psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
        connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            cursor.execute("SET LOCAL search_path TO public")
            cursor.execute(sql)
            cursor.execute("""SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND ((table_name='cadu_public_mcp_keys' AND column_name='modules')
                    OR (table_name='cadu_oauth_grants' AND column_name='modules'))""")
            columns = {(row["table_name"], row["column_name"]) for row in cursor.fetchall()}
        connection.commit()
    expected = {("cadu_public_mcp_keys", "modules"), ("cadu_oauth_grants", "modules")}
    if columns != expected:
        raise RuntimeError(f"Validação dos módulos MCP falhou: {columns}")
    print("OK public Cadu MCP modules schema")


if __name__ == "__main__":
    main()
