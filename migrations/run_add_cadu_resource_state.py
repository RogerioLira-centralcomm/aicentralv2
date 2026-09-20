#!/usr/bin/env python
"""Apply and validate canonical Cadu resource processing state."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    sql = Path(__file__).with_name("add_cadu_resource_state.sql").read_text(encoding="utf-8")
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
                """SELECT column_name FROM information_schema.columns
                     WHERE table_schema='public' AND table_name='cadu_project_resources'
                       AND column_name = ANY(%s)""",
                (["permission_snapshot", "capability_snapshot", "index_status", "ocr_status", "embedding_status", "deleted_at"],),
            )
            columns = {row["column_name"] for row in cursor.fetchall()}
        connection.commit()
    expected = {"permission_snapshot", "capability_snapshot", "index_status", "ocr_status", "embedding_status", "deleted_at"}
    if columns != expected:
        raise RuntimeError(f"Validação do estado dos recursos falhou: {sorted(columns)}")
    print("OK Cadu resource state schema")


if __name__ == "__main__":
    main()
