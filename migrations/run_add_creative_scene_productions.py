#!/usr/bin/env python
"""Cria e valida o plano de produção visual por cenas."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_scene_productions.sql")


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
                SELECT to_regclass('public.cx_creative_productions') AS productions,
                       to_regclass('public.cx_creative_scenes') AS scenes
                """
            )
            tables = cursor.fetchone()
            cursor.execute(
                """
                SELECT table_name, column_name
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND column_name = 'scene_id'
                   AND table_name IN (
                       'cx_generation_jobs', 'cx_generated_assets'
                   )
                """
            )
            linked_tables = {row["table_name"] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid) AS definition
                  FROM pg_constraint
                 WHERE conname = 'chk_cx_creative_scene_position'
                   AND conrelid = 'cx_creative_scenes'::regclass
                """
            )
            position_check = cursor.fetchone()

        if not tables["productions"] or not tables["scenes"]:
            raise RuntimeError("Tabelas de produção por cenas não foram criadas.")
        if linked_tables != {"cx_generation_jobs", "cx_generated_assets"}:
            raise RuntimeError("Vínculos scene_id não foram criados.")
        if not position_check or "8" not in (position_check.get("definition") or ""):
            raise RuntimeError("A posição das cenas ainda não aceita lotes de 6 ou 8.")

    print("Migração de produções por cenas executada e validada.")


if __name__ == "__main__":
    main()
