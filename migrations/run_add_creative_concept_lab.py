#!/usr/bin/env python
"""Cria e valida as tabelas da Mesa de conceito 15s."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_creative_concept_lab.sql")
REQUIRED_TABLES = (
    "cx_concept_sessions",
    "cx_concept_scenes",
    "cx_concept_layers",
    "cx_concept_passes",
    "cx_concept_references",
)


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
                SELECT table_name
                  FROM information_schema.tables
                 WHERE table_schema = 'public'
                   AND table_name = ANY(%s)
                """,
                (list(REQUIRED_TABLES),),
            )
            tables = {row["table_name"] for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'cx_generation_jobs'
                   AND column_name = 'concept_session_id'
                """
            )
            job_link = cursor.fetchone()
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid) AS definition
                  FROM pg_constraint
                 WHERE conname = 'chk_cx_concept_session_scene_count'
                   AND conrelid = 'cx_concept_sessions'::regclass
                """
            )
            scene_check = cursor.fetchone()

        missing = set(REQUIRED_TABLES) - tables
        if missing:
            raise RuntimeError(f"Tabelas da Mesa de conceito ausentes: {sorted(missing)}")
        if not job_link:
            raise RuntimeError("cx_generation_jobs.concept_session_id não foi criado.")
        if not scene_check or "4" not in (scene_check.get("definition") or ""):
            raise RuntimeError("scene_count da sessão de conceito ainda não aceita 4 ou 5.")

    print("Migração da Mesa de conceito 15s executada e validada.")


if __name__ == "__main__":
    main()
