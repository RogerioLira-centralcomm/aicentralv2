"""Auditoria SOMENTE LEITURA dos .sql que o deploy não executa e que ainda estão como 'auditar'.

Uso (no servidor): venv/bin/python migrations/audit_unlisted.py

Cobre as categorias 'auditar' e 'revisar-antes'. Para cada arquivo informa se o ledger (deploy_sql_migrations) o conhece e se as tabelas/colunas que ele
cria já existem. Só executa SELECT. Resultado:
  APLICADA        o ledger registra o arquivo
  JA-EXISTE       tudo que o arquivo cria já existe no banco (aplicada fora do ledger)
  PARCIAL         parte dos objetos existe: revisar antes de rodar
  AUSENTE         nada do que o arquivo cria existe: candidata a entrar no ORDER.txt
  SEM-OBJETOS     só altera dados/constraints; conferir à mão
"""

import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "migrations" / "NOT_IN_DEPLOY.txt"
CREATE_TABLE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?([a-z_0-9]+)", re.I)
ADD_COLUMN = re.compile(
    r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?(?:public\.)?([a-z_0-9]+)\s+add\s+column\s+(?:if\s+not\s+exists\s+)?([a-z_0-9]+)", re.I)


def pending_files():
    rows = [line.split(" | ") for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    return [row[0] for row in rows if len(row) >= 2 and row[1] in ("auditar", "revisar-antes")]


def objects(sql):
    tables = set(CREATE_TABLE.findall(sql))
    columns = {(table, column) for table, column in ADD_COLUMN.findall(sql) if table not in tables}
    return tables, columns


def main():
    load_dotenv(ROOT / ".env")
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""), connect_timeout=10, options="-c default_transaction_read_only=on",
    ) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT to_regclass('public.deploy_sql_migrations')")
        ledger = set()
        if cursor.fetchone()[0]:
            cursor.execute("SELECT filename FROM deploy_sql_migrations")
            ledger = {row[0] for row in cursor.fetchall()}
        for name in pending_files():
            sql = (ROOT / "migrations" / name).read_text(encoding="utf-8")
            tables, columns = objects(sql)
            found = total = 0
            for table in tables:
                cursor.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                found += cursor.fetchone()[0] is not None
                total += 1
            for table, column in columns:
                cursor.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s", (table, column))
                found += cursor.fetchone() is not None
                total += 1
            if name in ledger:
                status = "APLICADA"
            elif not total:
                status = "SEM-OBJETOS"
            elif found == total:
                status = "JA-EXISTE"
            elif found == 0:
                status = "AUSENTE"
            else:
                status = "PARCIAL"
            print(f"{status:12} {name} ({found}/{total} objetos)")


if __name__ == "__main__":
    sys.exit(main())
