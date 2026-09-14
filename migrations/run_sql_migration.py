"""Executa uma migration SQL do diretório ``migrations`` de forma idempotente.

Uso: python migrations/run_sql_migration.py arquivo.sql
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations"
load_dotenv(ROOT / ".env")


def main(filename: str) -> None:
    path = (MIGRATIONS_DIR / filename).resolve()
    if path.parent != MIGRATIONS_DIR.resolve() or path.suffix != ".sql" or not path.is_file():
        raise ValueError(f"Migration SQL inválida: {filename}")

    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(path.read_text(encoding="utf-8"))
        conn.commit()
    print(f"Migration executada: {path.name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python migrations/run_sql_migration.py arquivo.sql")
    main(sys.argv[1])
