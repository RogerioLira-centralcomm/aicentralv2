"""DDL de mídia. Também vive em migrations/add_creative_media.sql."""

from pathlib import Path

_SCHEMA_READY = False
SCHEMA_SQL = (Path(__file__).resolve().parents[2] / "migrations" / "add_creative_media.sql").read_text(
    encoding="utf-8"
)


def ensure_schema(conn):
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    statements = [item.strip() for item in SCHEMA_SQL.split(";") if item.strip()]
    with conn.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
    conn.commit()
    _SCHEMA_READY = True
