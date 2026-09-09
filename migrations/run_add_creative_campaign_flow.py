#!/usr/bin/env python
"""Executa e valida a integração CRM do fluxo de campanhas criativas."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_campaign_flow.sql")


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
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'cx_clients'
                   AND column_name = 'crm_client_id'
                """
            )
            linked = cursor.fetchone()
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid) AS definition
                  FROM pg_constraint
                 WHERE conname = 'chk_cx_generation_job_type'
                   AND conrelid = 'cx_generation_jobs'::regclass
                """
            )
            job_constraint = cursor.fetchone()
        if not linked:
            raise RuntimeError("Coluna cx_clients.crm_client_id não foi criada.")
        definition = (job_constraint or {}).get("definition", "")
        if "display_motion_payload" not in definition:
            raise RuntimeError("Contrato de job criativo não foi atualizado.")
    print("Migração do fluxo de campanhas criativas executada e validada.")


if __name__ == "__main__":
    main()
