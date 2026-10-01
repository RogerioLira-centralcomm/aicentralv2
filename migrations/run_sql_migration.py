"""Executa uma migration SQL do diretório ``migrations`` de forma idempotente.

Uso: python migrations/run_sql_migration.py arquivo.sql
"""

import hashlib
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations"
load_dotenv(ROOT / ".env")


LEDGER_DDL = """CREATE TABLE IF NOT EXISTS deploy_sql_migrations (
    filename TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)"""


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
            sql = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            cursor.execute(LEDGER_DDL)
            if os.getenv("FORCE_SQL_MIGRATIONS") != "1":
                cursor.execute("SELECT sha256 FROM deploy_sql_migrations WHERE filename = %s", (path.name,))
                row = cursor.fetchone()
                if row and row[0] == digest:
                    conn.commit()
                    print(f"Migration já aplicada: {path.name}")
                    return
            cursor.execute(sql)
            cursor.execute(
                """INSERT INTO deploy_sql_migrations (filename, sha256) VALUES (%s, %s)
                   ON CONFLICT (filename) DO UPDATE SET sha256 = EXCLUDED.sha256, applied_at = now()""",
                (path.name, digest),
            )
        conn.commit()
    print(f"Migration executada: {path.name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python migrations/run_sql_migration.py arquivo.sql")
    main(sys.argv[1])
