#!/usr/bin/env python
"""Executa e valida o schema de Google Calendar/Meet por usuário."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_google_calendar_meet.sql")


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
                    to_regclass('public.user_google_connections') AS connections,
                    to_regclass('public.crm_activity_meetings') AS meetings,
                    to_regclass('public.crm_activity_meeting_attendees') AS attendees
                """
            )
            validation = cursor.fetchone()
        if not all(validation.values()):
            raise RuntimeError(f"Validação da migração Google falhou: {validation}")
    print("Migração Google Calendar/Meet executada e validada.")


if __name__ == "__main__":
    main()
