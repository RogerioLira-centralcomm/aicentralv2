"""Adiciona o timestamp de última alteração às marcas do Workspace."""

import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg


ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / ".env")
    sql_path = Path(__file__).with_name("add_updated_at_to_cx_clients.sql")
    required = [key for key in ("DB_HOST", "DB_NAME", "DB_USER") if not os.getenv(key)]
    if required:
        raise RuntimeError("Configuração ausente: " + ", ".join(required))
    connection = psycopg.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.getenv("DB_PASSWORD", ""),
        port=os.getenv("DB_PORT", "5432"),
        connect_timeout=10,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute(sql_path.read_text())
            cursor.execute("""SELECT is_nullable, column_default
                                FROM information_schema.columns
                               WHERE table_schema = 'public'
                                 AND table_name = 'cx_clients'
                                 AND column_name = 'updated_at'""")
            column = cursor.fetchone()
            if not column or column[0] != "NO":
                raise RuntimeError("A coluna cx_clients.updated_at não foi validada.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    print("Migração aplicada e validada: última alteração das marcas.")


if __name__ == "__main__":
    main()
