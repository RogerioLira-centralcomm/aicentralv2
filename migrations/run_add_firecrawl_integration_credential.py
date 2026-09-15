#!/usr/bin/env python
"""Libera o Firecrawl na central de credenciais e grava a chave do .env."""

import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_firecrawl_integration_credential.sql")


def _encrypted_api_key():
    fernet_key = (os.getenv("INTEGRATION_CREDENTIALS_KEY") or "").strip()
    api_key = (os.getenv("FIRECRAWL_API_KEY") or "").strip()
    if not fernet_key or not api_key:
        return None
    from cryptography.fernet import Fernet

    payload = json.dumps({"api_key": api_key}, ensure_ascii=False, sort_keys=True)
    return Fernet(fernet_key.encode()).encrypt(payload.encode()).decode()


def main():
    encrypted = _encrypted_api_key()
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cursor:
            # Esta migration é executada em todo deploy. Em bancos que já
            # receberam providers adicionados depois do Firecrawl, reaplicar o
            # SQL antigo reduziria a lista aceita pelo CHECK e falharia ao
            # validar registros existentes. Só altere a constraint se o
            # provider ainda não estiver liberado.
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid) AS definition
                  FROM pg_constraint
                 WHERE conname = 'system_integration_credentials_provider_check'
                """
            )
            current = ((cursor.fetchone() or {}).get("definition") or "")
            if "firecrawl" not in current:
                cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            if encrypted:
                cursor.execute(
                    """
                    UPDATE system_integration_credentials
                       SET encrypted_secret = COALESCE(
                               NULLIF(encrypted_secret, ''),
                               %s
                           ),
                           updated_at = NOW()
                     WHERE provider = 'firecrawl'
                    """,
                    (encrypted,),
                )
            cursor.execute(
                """
                SELECT pg_get_constraintdef(oid) AS definition
                  FROM pg_constraint
                 WHERE conname = 'system_integration_credentials_provider_check'
                """
            )
            constraint = cursor.fetchone() or {}
            cursor.execute(
                """
                SELECT (encrypted_secret IS NOT NULL AND encrypted_secret <> '') AS has_secret
                  FROM system_integration_credentials
                 WHERE provider = 'firecrawl'
                """
            )
            row = cursor.fetchone() or {}
        conn.commit()
    definition = (constraint.get("definition") or "")
    if "firecrawl" not in definition:
        raise RuntimeError("A constraint de integrações não aceitou o Firecrawl.")
    secret_state = (
        "com chave no banco"
        if row.get("has_secret")
        else "sem chave (use Integrações ou o .env)"
    )
    print(f"Firecrawl liberado na central de credenciais ({secret_state}).")


if __name__ == "__main__":
    main()
