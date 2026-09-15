#!/usr/bin/env python3
"""Consolida cada Place em um único ponto comercial, sem descartar a memória do sítio.

Renda e curva semanal não são inferidas: ficam explicitamente como pendentes de fonte.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Json

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def connect():
    return psycopg.connect(
        host=os.environ["DB_HOST"], port=os.getenv("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], row_factory=dict_row,
    )


def one_point(payload: dict) -> dict:
    points = list(payload.get("points") or [])
    if not points:
        return payload
    # Mantém integralmente os recortes antigos para auditoria ou restauração.
    # A migração é idempotente: uma nova execução não troca esse backup.
    payload.setdefault("legacy_points", points)
    primary_index = next((index for index, item in enumerate(points) if item.get("scope") == "internal"), 0)
    primary = dict(points[primary_index])
    primary["scope"] = "internal"
    primary["scope_label"] = "No sítio"
    # As subdivisões viram conteúdo do único ponto vendido; não são inventário separado.
    primary["inside"] = [
        item.get("name") for index, item in enumerate(points)
        if index != primary_index and item.get("scope") == "internal" and item.get("name")
    ]
    audience = []
    for item in list(primary.get("audiences") or []) + [row.get("title") for row in payload.get("audiences") or []]:
        if item and item not in audience:
            audience.append(item)
    primary["target_audience"] = audience[:4]
    primary["formats"] = list(dict.fromkeys(
        value for item in points for value in (item.get("formats") or []) if value
    ))
    payload["points"] = [primary]
    payload["target_audience"] = audience[:4]
    payload.setdefault("income", {"label": "", "source_status": "to_validate", "note": "Aguardando fonte de renda para o recorte."})
    payload.setdefault("weekly_movement", {"values": [None] * 7, "source_status": "to_validate", "note": "Aguardando dado de mobilidade por dia da semana."})
    media = payload.setdefault("media", {})
    for image in media.get("gallery") or []:
        image["point_id"] = primary.get("id", "")
    return payload


def main():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, slug, payload FROM cx_places ORDER BY id")
        rows = cur.fetchall()
        for row in rows:
            payload = one_point(dict(row["payload"] or {}))
            cur.execute("UPDATE cx_places SET payload = %s, updated_at = now() WHERE id = %s", (Json(payload), row["id"]))
        cur.execute("SELECT count(*) AS places, sum(jsonb_array_length(payload->'points')) AS points FROM cx_places")
        result = cur.fetchone()
    print(f"{result['places']} places; {result['points']} pontos comerciais.")


if __name__ == "__main__":
    main()
