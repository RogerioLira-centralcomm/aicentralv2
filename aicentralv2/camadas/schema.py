"""DDL da Camadas V2. Também vive em migrations/add_camadas_v2.sql."""

from pathlib import Path

_SCHEMA_READY = False
_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
SCHEMA_SQL = (_MIGRATIONS / "add_camadas_v2.sql").read_text(encoding="utf-8")
WORKSPACE_SQL = (_MIGRATIONS / "add_camadas_v2_workspace.sql").read_text(encoding="utf-8")


def ensure_schema(conn):
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    blob = f"{SCHEMA_SQL};\n{WORKSPACE_SQL}"
    statements = [item.strip() for item in blob.split(";") if item.strip()]
    with conn.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
    conn.commit()
    _SCHEMA_READY = True
