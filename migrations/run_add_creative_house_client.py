#!/usr/bin/env python
"""Vincula marcas órfãs da modelagem ao cliente CentralComm."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_house_client.sql")


def main():
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
        conn.commit()
        with conn.cursor() as cursor:
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
            names = {row["indexname"] for row in cursor.fetchall()}
        if "uq_cx_clients_crm_client" in names:
            raise RuntimeError("O índice único de crm_client_id ainda existe.")
        if "idx_cx_clients_crm_client" not in names:
            raise RuntimeError("O índice de crm_client_id não foi criado.")
    print("Migração do cliente CentralComm da modelagem executada e validada.")


if __name__ == "__main__":
    main()
