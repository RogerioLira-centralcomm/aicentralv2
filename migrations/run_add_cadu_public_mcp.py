"""Apply and validate the public Cadu MCP beta schema."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    sql = Path(__file__).with_name("add_cadu_public_mcp.sql").read_text(encoding="utf-8")
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
                    to_regclass('public.cadu_public_mcp_keys') AS keys,
                    to_regclass('public.cadu_public_mcp_usage') AS usage
                """
            )
            validation = cursor.fetchone()
        connection.commit()
    if not all(validation.values()):
        raise RuntimeError(f"Validação do schema público MCP falhou: {validation}")
    print("OK public Cadu MCP schema")


if __name__ == "__main__":
    main()
