"""Integração PostgreSQL real: duas conexões, path JSONB e vizinho."""

from __future__ import annotations

import os
import unittest
import uuid
from pathlib import Path

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Json

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _dsn_kwargs():
    url = os.getenv("CX_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        return {"conninfo": url, "row_factory": dict_row, "connect_timeout": 3}
    return {
        "dbname": os.getenv("DB_NAME", "aicentral_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "row_factory": dict_row,
        "connect_timeout": 3,
    }


def _connect():
    import psycopg

    return psycopg.connect(**_dsn_kwargs())


def _postgres_available():
    try:
        conn = _connect()
        conn.close()
        return True
    except Exception:
        return False


def _has_cx_clients(conn):
    with conn.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.cx_clients') AS name")
        row = cursor.fetchone()
    return bool(row and row.get("name"))


@unittest.skipUnless(_postgres_available(), "PostgreSQL de integração ausente")
class DesignSystemAdsPostgresJsonbTest(unittest.TestCase):
    def test_duas_conexoes_vizinho_e_ads_sobrevivem(self):
        from aicentralv2.creative_modeling_repository import (
            CreativeModelingRepository,
            jsonb_merge_neighbors_sql,
            jsonb_set_ads_sql,
        )

        marker = f"dsa-probe-{uuid.uuid4().hex[:12]}"
        seed = {
            "brand_summary": "antes",
            "trocr": {"step": "old"},
            "design_system_ads": {
                "framework": "design-system-ads",
                "revision": 1,
                "tokens": {"ink": "#111111"},
            },
        }
        neighbor = {
            "brand_summary": marker,
            "trocr": {"step": "new"},
            "design_system_ads": {
                "revision": 0,
                "stale": True,
                "tokens": {"ink": "#000000"},
            },
        }
        ads = {
            "framework": "design-system-ads",
            "revision": 2,
            "tokens": {"ink": "#082C9C"},
        }

        conn_a = _connect()
        conn_b = _connect()
        self.addCleanup(conn_a.close)
        self.addCleanup(conn_b.close)

        if _has_cx_clients(conn_a):
            repo_a = CreativeModelingRepository(conn_a)
            repo_b = CreativeModelingRepository(conn_b)
            with conn_a.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO cx_clients (name, brand_profile)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (marker, Json(seed)),
                )
                client_id = cursor.fetchone()["id"]
                conn_a.commit()

            def cleanup():
                with conn_a.cursor() as cursor:
                    cursor.execute("DELETE FROM cx_clients WHERE id = %s", (client_id,))
                    conn_a.commit()

            self.addCleanup(cleanup)
            repo_a.update_client_brand_profile(client_id, neighbor)
            repo_b.update_client_brand_profile_cas(
                client_id, {"design_system_ads": ads}, 1
            )
            with conn_a.cursor() as cursor:
                cursor.execute(
                    "SELECT brand_profile FROM cx_clients WHERE id = %s",
                    (client_id,),
                )
                profile = cursor.fetchone()["brand_profile"]
        else:
            table = "cx_dsa_jsonb_probe"
            with conn_a.cursor() as cursor:
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id SERIAL PRIMARY KEY,
                        brand_profile JSONB NOT NULL DEFAULT '{{}}'::jsonb
                    )
                    """
                )
                cursor.execute(
                    f"INSERT INTO {table} (brand_profile) VALUES (%s) RETURNING id",
                    (Json(seed),),
                )
                row_id = cursor.fetchone()["id"]
                conn_a.commit()

            def cleanup_probe():
                with conn_a.cursor() as cursor:
                    cursor.execute(f"DELETE FROM {table} WHERE id = %s", (row_id,))
                    conn_a.commit()

            self.addCleanup(cleanup_probe)
            with conn_a.cursor() as cursor:
                cursor.execute(
                    jsonb_merge_neighbors_sql("brand_profile", table),
                    (Json(neighbor), row_id),
                )
                conn_a.commit()
            with conn_b.cursor() as cursor:
                cursor.execute(
                    jsonb_set_ads_sql("brand_profile", table),
                    (Json(ads), row_id, 1),
                )
                self.assertTrue(cursor.fetchone())
                conn_b.commit()
            with conn_a.cursor() as cursor:
                cursor.execute(
                    f"SELECT brand_profile FROM {table} WHERE id = %s", (row_id,)
                )
                profile = cursor.fetchone()["brand_profile"]

        self.assertEqual(profile["brand_summary"], marker)
        self.assertEqual(profile["trocr"]["step"], "new")
        self.assertEqual(profile["design_system_ads"]["revision"], 2)
        self.assertEqual(profile["design_system_ads"]["tokens"]["ink"], "#082C9C")
        self.assertNotIn("stale", profile["design_system_ads"])
        if _has_cx_clients(conn_a):
            with conn_a.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT design_system_ads_revision
                      FROM cx_clients
                     WHERE id = %s
                    """,
                    (client_id,),
                )
                self.assertEqual(cursor.fetchone()["design_system_ads_revision"], 2)
