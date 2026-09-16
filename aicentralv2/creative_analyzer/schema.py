"""DDL aditivo do Creative Analyzer."""

from pathlib import Path

_READY = False
SCHEMA_SQL = (
    Path(__file__).resolve().parents[2] / "migrations" / "add_studio_creative_analyzer.sql"
).read_text(encoding="utf-8")


def ensure_schema(connection):
    global _READY
    if _READY:
        return
    with connection.cursor() as cursor:
        cursor.execute(SCHEMA_SQL)
    connection.commit()
    _READY = True
