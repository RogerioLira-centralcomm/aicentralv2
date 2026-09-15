"""Persiste audiência, demografia estimada e top 15 em todos os Places.

Uso: python -m migrations.enrich_cx_places_audience
"""

from __future__ import annotations

from psycopg.types.json import Json

from aicentralv2 import create_app
from aicentralv2.db import get_db
from aicentralv2.places.audience import enrich_point_inventory, enrich_public_payload
from aicentralv2.places.schema import CITY_LABELS, normalize_payload


def run() -> int:
    app = create_app()
    with app.app_context():
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT id, slug, place_type, city, payload FROM cx_places ORDER BY id")
            rows = cur.fetchall() or []
            for row in rows:
                payload = enrich_point_inventory(
                    normalize_payload(row.get("payload")),
                    place_type=row.get("place_type") or "evento",
                    city=row.get("city") or "sp",
                    overwrite=True,
                )
                payload = enrich_public_payload(
                    payload,
                    place_type=row.get("place_type") or "evento",
                    slug=row.get("slug") or "",
                    city_label=CITY_LABELS.get(row.get("city") or "", ""),
                )
                cur.execute(
                    "UPDATE cx_places SET payload=%s, updated_at=now() WHERE id=%s",
                    (Json(normalize_payload(payload)), row["id"]),
                )
        conn.commit()
    return len(rows)


if __name__ == "__main__":
    print(f"{run()} Places enriquecidos com top 10 de apps e portais por ponto.")
