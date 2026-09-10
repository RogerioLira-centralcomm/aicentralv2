#!/usr/bin/env python
"""Executa e valida a integração CRM do fluxo de campanhas criativas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cx_clients_crm import connect, liberar_crm_client_id, validar_crm_client_id


SQL_PATH = Path(__file__).with_name("add_creative_campaign_flow.sql")


def main():
    conn = connect()
    try:
        with conn.cursor() as cursor:
            liberar_crm_client_id(cursor)
        conn.commit()

        with conn.cursor() as cursor:
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            liberar_crm_client_id(cursor)
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
            validar_crm_client_id(cursor)

        if not linked:
            raise RuntimeError("Coluna cx_clients.crm_client_id não foi criada.")
        definition = (job_constraint or {}).get("definition", "")
        if "display_motion_payload" not in definition:
            raise RuntimeError("Contrato de job criativo não foi atualizado.")
        print("Migração do fluxo de campanhas criativas executada e validada.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
