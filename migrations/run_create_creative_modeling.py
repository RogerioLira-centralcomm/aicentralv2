#!/usr/bin/env python
"""Executa e valida a migration de Modelagem de Criativos."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cx_clients_crm import connect, liberar_crm_client_id, validar_crm_client_id


SQL_PATH = Path(__file__).with_name("create_creative_modeling.sql")


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

        expected = {
            "cx_format_categories",
            "cx_channels",
            "cx_format_templates",
            "cx_clients",
            "cx_campaigns",
            "cx_campaign_variations",
            "cx_variation_steps",
            "cx_generation_jobs",
            "cx_generation_references",
            "cx_generated_assets",
            "cx_format_references",
            "cx_video_input_assets",
            "cx_generation_cost_ledger",
            "cx_public_creative_collections",
            "cx_public_collection_assets",
        }
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                  FROM information_schema.tables
                 WHERE table_schema = 'public'
                   AND table_name = ANY(%s)
                """,
                (sorted(expected),),
            )
            found = {row["table_name"] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT column_name, data_type
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'cx_format_templates'
                   AND column_name IN ('layers', 'required_fields', 'use_cases_by_market')
                """
            )
            json_columns = {
                row["column_name"]
                for row in cursor.fetchall()
                if row["data_type"] == "jsonb"
            }
            validar_crm_client_id(cursor)

        missing = expected - found
        expected_json = {"layers", "required_fields", "use_cases_by_market"}
        if missing or json_columns != expected_json:
            raise RuntimeError(
                f"Validação falhou: tabelas ausentes={sorted(missing)}, "
                f"JSONB encontrados={sorted(json_columns)}"
            )
        print("Migration de Modelagem de Criativos executada e validada.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
