#!/usr/bin/env python3
"""Enable the internal and external Google login credential records."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = Path(__file__).with_name("add_google_login_credentials.sql")
load_dotenv(ROOT / ".env")


def main():
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""), row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cursor:
            # Deploys may run this after providers added by later migrations.
            # Never replace a broader CHECK with this migration's older list.
            cursor.execute(
                """SELECT pg_get_constraintdef(oid) AS definition
                     FROM pg_constraint
                    WHERE conname = 'system_integration_credentials_provider_check'"""
            )
            definition = ((cursor.fetchone() or {}).get("definition") or "")
            if "google_login_cadu" not in definition or "google_login_centralx" not in definition:
                cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            else:
                cursor.execute(
                    """INSERT INTO system_integration_credentials (provider, public_config, status)
                        VALUES
                          ('google_login_cadu', %s::jsonb, 'active'),
                          ('google_login_centralx', %s::jsonb, 'active')
                        ON CONFLICT (provider) DO NOTHING""",
                    (
                        '{"redirect_uri":"https://auth.centralcomm.media/auth/google/callback"}',
                        '{"redirect_uri":"https://auth.centralcomm.media/auth/google/callback","allowed_domain":"centralcomm.media"}',
                    ),
                )
            cursor.execute("SELECT provider FROM system_integration_credentials WHERE provider IN ('google_login_cadu','google_login_centralx')")
            found = {row["provider"] for row in cursor.fetchall()}
        conn.commit()
    if found != {"google_login_cadu", "google_login_centralx"}:
        raise RuntimeError("Credenciais de login Google não foram preparadas.")
    print("Google Login pronto para receber as duas credenciais OAuth.")


if __name__ == "__main__":
    main()
