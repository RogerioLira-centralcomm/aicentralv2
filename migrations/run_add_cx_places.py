#!/usr/bin/env python
"""Cria cx_places e cx_place_inquiries e faz seed dos 3 aeroportos."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Json

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
SQL_PATH = Path(__file__).with_name("add_cx_places.sql")
sys.path.insert(0, str(ROOT))

from aicentralv2.places.catalog import SEED_PLACES  # noqa: E402
from aicentralv2.places.share import make_preview_token  # noqa: E402


def connect():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    )


def seed_airports(cursor):
    now = datetime.now(timezone.utc)
    for item in SEED_PLACES:
        cursor.execute("SELECT id, status, preview_token FROM cx_places WHERE slug = %s", (item["slug"],))
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """
                UPDATE cx_places
                   SET title = %s,
                       code = %s,
                       operator = %s,
                       subtitle = %s,
                       place_type = %s,
                       city = %s,
                       payload = %s,
                       updated_at = now()
                 WHERE id = %s
                """,
                (
                    item["title"],
                    item.get("code"),
                    item.get("operator"),
                    item.get("subtitle"),
                    item["place_type"],
                    item["city"],
                    Json(item["payload"]),
                    existing["id"],
                ),
            )
            continue
        cursor.execute(
            """
            INSERT INTO cx_places (
                slug, preview_token, place_type, city, status,
                title, code, operator, subtitle, payload, published_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                item["slug"],
                make_preview_token(),
                item["place_type"],
                item["city"],
                item["status"],
                item["title"],
                item.get("code"),
                item.get("operator"),
                item.get("subtitle"),
                Json(item["payload"]),
                now if item.get("status") == "published" else None,
            ),
        )


def main():
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(SQL_PATH.read_text(encoding="utf-8"))
            seed_airports(cursor)
        conn.commit()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    to_regclass('public.cx_places') AS places,
                    to_regclass('public.cx_place_inquiries') AS inquiries,
                    (SELECT COUNT(*) FROM cx_places WHERE place_type = 'aeroporto') AS airports,
                    (SELECT payload->'metrics'->'passengers'->>'label'
                       FROM cx_places WHERE slug = 'santos-dumont') AS sdu_passengers,
                    (SELECT payload->'catchment'->'population'->>'label'
                       FROM cx_places WHERE slug = 'confins') AS cnf_pop,
                    (SELECT payload->'catchment'->'population'->>'label'
                       FROM cx_places WHERE slug = 'congonhas') AS cgh_pop,
                    (SELECT payload->'catchment'->'population'->>'label'
                       FROM cx_places WHERE slug = 'santos-dumont') AS sdu_pop
                """
            )
            result = cursor.fetchone() or {}
    if not result.get("places"):
        raise RuntimeError("cx_places não existe.")
    if not result.get("inquiries"):
        raise RuntimeError("cx_place_inquiries não existe.")
    if int(result.get("airports") or 0) < 3:
        raise RuntimeError("Seed dos aeroportos incompleto.")
    if result.get("sdu_passengers") != "6,2 mi":
        raise RuntimeError("Santos Dumont ainda sem o número ANAC 2025.")
    if result.get("cnf_pop") != "212 mil":
        raise RuntimeError("Confins ainda sem a bacia IBGE 2022.")
    if result.get("cgh_pop") != "153 mil":
        raise RuntimeError("Congonhas ainda sem a bacia dos distritos Campo Belo e Moema.")
    if result.get("sdu_pop") != "96 mil":
        raise RuntimeError("Santos Dumont ainda sem a bacia IPP 2022.")
    print("Migração de Places executada e validada.")


if __name__ == "__main__":
    main()
