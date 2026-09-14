"""Cria a tabela de revisões imutáveis das variantes de formato."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main():
    sql = (ROOT / "migrations" / "add_format_variant_revisions.sql").read_text(
        encoding="utf-8"
    )
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()
    print("Tabela cx_format_variant_revisions pronta.")


if __name__ == "__main__":
    main()
