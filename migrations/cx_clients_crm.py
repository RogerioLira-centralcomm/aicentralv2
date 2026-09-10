"""Índice de crm_client_id: INTEGER compartilhado, sem unicidade."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def connect():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    )


def tabela_cx_clients_existe(cursor):
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name = 'cx_clients'
        ) AS existe
        """
    )
    return bool(cursor.fetchone()["existe"])


def liberar_crm_client_id(cursor):
    """Tira unicidade de crm_client_id. Várias marcas podem usar o mesmo cliente."""
    if not tabela_cx_clients_existe(cursor):
        return
    cursor.execute(
        "ALTER TABLE cx_clients DROP CONSTRAINT IF EXISTS uq_cx_clients_crm_client"
    )
    cursor.execute("DROP INDEX IF EXISTS uq_cx_clients_crm_client")
    if tipo_crm_client_id(cursor) is None:
        return
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cx_clients_crm_client
            ON cx_clients(crm_client_id)
            WHERE crm_client_id IS NOT NULL
        """
    )


def indices_crm_client(cursor):
    if not tabela_cx_clients_existe(cursor):
        return set()
    cursor.execute(
        """
        SELECT indexname
          FROM pg_indexes
         WHERE tablename = 'cx_clients'
           AND indexname IN (
               'uq_cx_clients_crm_client',
               'idx_cx_clients_crm_client'
           )
        """
    )
    return {row["indexname"] for row in cursor.fetchall()}


def tipo_crm_client_id(cursor):
    cursor.execute(
        """
        SELECT data_type
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'cx_clients'
           AND column_name = 'crm_client_id'
        """
    )
    row = cursor.fetchone()
    return row["data_type"] if row else None


def validar_crm_client_id(cursor, exigir_tabela=True):
    if not tabela_cx_clients_existe(cursor):
        if exigir_tabela:
            raise RuntimeError("Tabela cx_clients não existe.")
        return
    tipo = tipo_crm_client_id(cursor)
    if tipo is None:
        if exigir_tabela:
            raise RuntimeError("Coluna cx_clients.crm_client_id não existe.")
        return
    if tipo != "integer":
        raise RuntimeError(
            f"cx_clients.crm_client_id deveria ser integer, veio {tipo!r}."
        )
    nomes = indices_crm_client(cursor)
    if "uq_cx_clients_crm_client" in nomes:
        raise RuntimeError("O índice único de crm_client_id ainda existe.")
    if "idx_cx_clients_crm_client" not in nomes:
        raise RuntimeError("O índice de busca de crm_client_id não foi criado.")
