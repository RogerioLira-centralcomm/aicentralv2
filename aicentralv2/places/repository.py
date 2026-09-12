"""Persistência de Places em cx_places e cx_place_inquiries."""

from __future__ import annotations

import logging
from typing import Any, Optional

from psycopg.types.json import Json

from ..db import get_db
from .schema import CITIES, PLACE_TYPES, STATUSES, as_dict, normalize_payload, text

logger = logging.getLogger(__name__)

PLACE_COLS = (
    "id",
    "slug",
    "preview_token",
    "place_type",
    "city",
    "status",
    "title",
    "code",
    "operator",
    "subtitle",
    "payload",
    "published_at",
    "created_by",
    "created_at",
    "updated_at",
)


class PlacesError(RuntimeError):
    pass


class PlaceNotFound(PlacesError):
    pass


class PlaceConflict(PlacesError):
    pass


def _row(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    data = dict(row)
    data["payload"] = normalize_payload(as_dict(data.get("payload")))
    return data


def count_places() -> int:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM cx_places")
        row = cur.fetchone() or {}
    return int(row.get("n") or 0)


def list_places(*, city: str = "", place_type: str = "", status: str = "", q: str = "") -> list[dict]:
    clauses = ["1=1"]
    params: list[Any] = []
    if city in CITIES:
        clauses.append("city = %s")
        params.append(city)
    if place_type in PLACE_TYPES:
        clauses.append("place_type = %s")
        params.append(place_type)
    if status in STATUSES:
        clauses.append("status = %s")
        params.append(status)
    query = text(q)
    if query:
        clauses.append("(title ILIKE %s OR slug ILIKE %s OR COALESCE(code, '') ILIKE %s)")
        like = f"%{query}%"
        params.extend([like, like, like])
    sql = f"""
        SELECT {", ".join(PLACE_COLS)}
          FROM cx_places
         WHERE {" AND ".join(clauses)}
         ORDER BY
           CASE city WHEN 'bh' THEN 1 WHEN 'sp' THEN 2 WHEN 'rj' THEN 3 ELSE 4 END,
           CASE place_type WHEN 'aeroporto' THEN 1 WHEN 'shopping' THEN 2 ELSE 3 END,
           title
    """
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall() or []
    return [_row(item) for item in rows if item]


def list_published() -> list[dict]:
    return list_places(status="published")


def get_by_id(place_id: int) -> dict:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(PLACE_COLS)} FROM cx_places WHERE id = %s LIMIT 1",
            (int(place_id),),
        )
        row = _row(cur.fetchone())
    if not row:
        raise PlaceNotFound("Place não encontrado.")
    return row


def get_by_slug(slug: str) -> Optional[dict]:
    value = text(slug)
    if not value:
        return None
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(PLACE_COLS)} FROM cx_places WHERE slug = %s LIMIT 1",
            (value,),
        )
        return _row(cur.fetchone())


def get_published_by_slug(slug: str) -> dict:
    row = get_by_slug(slug)
    if not row or row.get("status") != "published":
        raise PlaceNotFound("Place público não encontrado.")
    return row


def get_by_preview_token(token: str) -> dict:
    value = text(token)
    if not value:
        raise PlaceNotFound("Prévia inválida.")
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(PLACE_COLS)} FROM cx_places WHERE preview_token = %s LIMIT 1",
            (value,),
        )
        row = _row(cur.fetchone())
    if not row:
        raise PlaceNotFound("Prévia não encontrada.")
    return row


def insert_place(data: dict) -> dict:
    conn = get_db()
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO cx_places (
                    slug, preview_token, place_type, city, status,
                    title, code, operator, subtitle, payload,
                    published_at, created_by
                )
                VALUES (
                    %(slug)s, %(preview_token)s, %(place_type)s, %(city)s, %(status)s,
                    %(title)s, %(code)s, %(operator)s, %(subtitle)s, %(payload)s,
                    %(published_at)s, %(created_by)s
                )
                RETURNING id
                """,
                {
                    "slug": data["slug"],
                    "preview_token": data["preview_token"],
                    "place_type": data["place_type"],
                    "city": data["city"],
                    "status": data["status"],
                    "title": data["title"],
                    "code": data.get("code") or None,
                    "operator": data.get("operator") or None,
                    "subtitle": data.get("subtitle") or None,
                    "payload": Json(normalize_payload(data.get("payload"))),
                    "published_at": data.get("published_at"),
                    "created_by": data.get("created_by"),
                },
            )
            row = cur.fetchone() or {}
        except Exception as exc:
            conn.rollback()
            message = str(exc)
            if "ux_cx_places_slug" in message or "slug" in message.lower():
                raise PlaceConflict("Já existe um place com este slug.") from exc
            raise
    conn.commit()
    return get_by_id(int(row["id"]))


def update_place(place_id: int, data: dict) -> dict:
    conn = get_db()
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                UPDATE cx_places
                   SET slug = %(slug)s,
                       place_type = %(place_type)s,
                       city = %(city)s,
                       status = %(status)s,
                       title = %(title)s,
                       code = %(code)s,
                       operator = %(operator)s,
                       subtitle = %(subtitle)s,
                       payload = %(payload)s,
                       published_at = %(published_at)s,
                       updated_at = now()
                 WHERE id = %(id)s
                """,
                {
                    "id": int(place_id),
                    "slug": data["slug"],
                    "place_type": data["place_type"],
                    "city": data["city"],
                    "status": data["status"],
                    "title": data["title"],
                    "code": data.get("code") or None,
                    "operator": data.get("operator") or None,
                    "subtitle": data.get("subtitle") or None,
                    "payload": Json(normalize_payload(data.get("payload"))),
                    "published_at": data.get("published_at"),
                },
            )
            if cur.rowcount == 0:
                raise PlaceNotFound("Place não encontrado.")
        except PlaceNotFound:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            message = str(exc)
            if "ux_cx_places_slug" in message or "duplicate" in message.lower():
                raise PlaceConflict("Já existe um place com este slug.") from exc
            raise
    conn.commit()
    return get_by_id(place_id)


def upsert_seed(data: dict) -> dict:
    existing = get_by_slug(data["slug"])
    if existing:
        if existing.get("status") != "draft":
            return existing
        merged = dict(existing)
        merged.update(
            {
                "title": data["title"],
                "code": data.get("code"),
                "operator": data.get("operator"),
                "subtitle": data.get("subtitle"),
                "place_type": data["place_type"],
                "city": data["city"],
                "status": data.get("status") or existing.get("status"),
                "payload": data.get("payload"),
                "published_at": existing.get("published_at"),
            }
        )
        return update_place(int(existing["id"]), merged)
    return insert_place(data)


def insert_inquiry(data: dict) -> dict:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cx_place_inquiries (
                place_id, name, company, email, phone, message, source_slug
            )
            VALUES (
                %(place_id)s, %(name)s, %(company)s, %(email)s, %(phone)s, %(message)s, %(source_slug)s
            )
            RETURNING id, place_id, name, company, email, phone, message, source_slug, created_at
            """,
            {
                "place_id": int(data["place_id"]),
                "name": text(data.get("name")),
                "company": text(data.get("company")) or None,
                "email": text(data.get("email")) or None,
                "phone": text(data.get("phone")) or None,
                "message": text(data.get("message")) or None,
                "source_slug": text(data.get("source_slug")),
            },
        )
        row = cur.fetchone() or {}
    conn.commit()
    return dict(row)


def inquiry_payload(raw: Any) -> dict:
    data = as_dict(raw)
    name = text(data.get("name"))
    email = text(data.get("email"))
    phone = text(data.get("phone"))
    if not name:
        raise PlacesError("Informe o nome.")
    if not email and not phone:
        raise PlacesError("Informe e-mail ou WhatsApp.")
    return {
        "name": name,
        "company": text(data.get("company")),
        "email": email,
        "phone": phone,
        "message": text(data.get("message")),
    }
