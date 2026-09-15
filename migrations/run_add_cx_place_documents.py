#!/usr/bin/env python
"""Aplica e valida a estrutura de documentos comerciais de Places."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def connect():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""), row_factory=dict_row,
    )


def main():
    sql = Path(__file__).with_name("add_cx_place_documents.sql").read_text(encoding="utf-8")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("""
                SELECT to_regclass('public.cx_place_documents') AS documents,
                       to_regclass('public.cx_place_document_exports') AS exports
            """)
            result = cur.fetchone() or {}
            if not result.get("documents") or not result.get("exports"):
                raise RuntimeError("Tabelas de documentos de Places não foram criadas.")
            cur.execute("""
                SELECT 1 FROM pg_indexes
                 WHERE schemaname = 'public' AND indexname = 'idx_cx_place_documents_place_status'
            """)
            if not cur.fetchone():
                raise RuntimeError("Índice de histórico de documentos não foi criado.")
        conn.commit()
    print("Migração de documentos de Places executada e validada.")


if __name__ == "__main__":
    main()
