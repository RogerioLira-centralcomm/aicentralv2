#!/usr/bin/env python
"""Grava o GPT Image 2 na credencial OpenRouter da central de integrações."""

import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_openrouter_gpt_image_2.sql")


def _encrypted_api_key():
    fernet_key = (os.getenv("INTEGRATION_CREDENTIALS_KEY") or "").strip()
    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
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
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            if encrypted:
                cursor.execute(
                    """
                    UPDATE system_integration_credentials
                       SET encrypted_secret = COALESCE(encrypted_secret, %s),
                           updated_at = NOW()
                     WHERE provider = 'openrouter'
                       AND (encrypted_secret IS NULL OR encrypted_secret = '')
                    """,
                    (encrypted,),
                )
            cursor.execute(
                """
                SELECT public_config->>'image_model' AS image_model,
                       (encrypted_secret IS NOT NULL AND encrypted_secret <> '') AS has_secret
                  FROM system_integration_credentials
                 WHERE provider = 'openrouter'
                """
            )
            row = cursor.fetchone() or {}
        conn.commit()
    if row.get("image_model") != "openai/gpt-image-2":
        raise RuntimeError("A credencial OpenRouter não recebeu o GPT Image 2.")
    secret_state = "com chave" if row.get("has_secret") else "sem chave (use Integrações ou o .env)"
    print(f"OpenRouter GPT Image 2 gravado na central de credenciais ({secret_state}).")


if __name__ == "__main__":
    main()
