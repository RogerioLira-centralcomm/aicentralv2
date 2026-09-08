#!/usr/bin/env python
"""Executa e valida a migração do estúdio de formatos criativos."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_format_studio.sql")


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
                SELECT
                    to_regclass('public.cx_format_modeling_jobs') AS jobs,
                    EXISTS (
                        SELECT 1 FROM information_schema.columns
                         WHERE table_schema = 'public'
                           AND table_name = 'cx_format_templates'
                           AND column_name = 'placement_spec'
                    ) AS placement,
                    EXISTS (
                        SELECT 1 FROM information_schema.columns
                         WHERE table_schema = 'public'
                           AND table_name = 'cx_format_templates'
                           AND column_name = 'behavior_spec'
                    ) AS behavior
                """
            )
            validation = cursor.fetchone()
        if not all(validation.values()):
            raise RuntimeError(f"Validação da migração falhou: {validation}")
    print("Migração do estúdio de formatos executada e validada.")


if __name__ == "__main__":
    main()
