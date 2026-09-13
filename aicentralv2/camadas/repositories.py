"""Persistência PostgreSQL da Camadas V2."""

from contextlib import contextmanager
from decimal import Decimal

from psycopg.types.json import Json

from .schema import ensure_schema
from .schemas import new_public_id


class CamadasNotFoundError(LookupError):
    pass


class CamadasConflictError(ValueError):
    pass


def _serialize(row):
    if not row:
        return row
    data = dict(row)
    for key, value in list(data.items()):
        if isinstance(value, Decimal):
            data[key] = float(value)
    return data


class CamadasRepository:
    def __init__(self, connection=None):
        self._connection = connection
        self._ready = False

    @property
    def conn(self):
        if self._connection is not None:
            return self._connection
        from .. import db

        return db.get_db()

    def ready(self):
        if not self._ready:
            ensure_schema(self.conn)
            self._ready = True
        return self

    @contextmanager
    def _write(self):
        try:
            with self.conn.cursor() as cursor:
                yield cursor
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def create_creative(self, data):
        public_id = data.get("public_id") or new_public_id("creative")
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_camadas_creatives (
                    public_id, client_id, collection_id, name, status,
                    original_path, original_name, mime_type, sha256,
                    width, height, reading, warnings, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                RETURNING *
                """,
                (
                    public_id,
                    data.get("client_id"),
                    data.get("collection_id"),
                    data.get("name") or "",
                    data.get("status") or "queued",
                    data.get("original_path") or "",
                    data.get("original_name") or "",
                    data.get("mime_type") or "",
                    data.get("sha256") or "",
                    data.get("width") or 0,
                    data.get("height") or 0,
                    Json(data.get("reading") or {}),
                    Json(data.get("warnings") or []),
                    data.get("created_by"),
                ),
            )
            row = cursor.fetchone()
        return _serialize(row)

    def get_creative(self, public_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM cx_camadas_creatives WHERE public_id = %s",
                (public_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CamadasNotFoundError("Criativo não encontrado.")
        return _serialize(row)

    def update_creative(self, public_id, **fields):
        allowed = {
            "status",
            "reading",
            "warnings",
            "name",
            "width",
            "height",
        }
        assignments = []
        values = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in {"reading", "warnings"}:
                assignments.append(f"{key} = %s")
                values.append(Json(value))
            else:
                assignments.append(f"{key} = %s")
                values.append(value)
        if not assignments:
            return self.get_creative(public_id)
        assignments.append("updated_at = NOW()")
        values.append(public_id)
        with self._write() as cursor:
            cursor.execute(
                f"""
                UPDATE cx_camadas_creatives
                   SET {", ".join(assignments)}
                 WHERE public_id = %s
             RETURNING *
                """,
                tuple(values),
            )
            row = cursor.fetchone()
        if not row:
            raise CamadasNotFoundError("Criativo não encontrado.")
        return _serialize(row)

    def create_job(self, creative_id, public_id=None):
        job_id = public_id or new_public_id("job")
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_camadas_jobs (
                    public_id, creative_id, status, stage, progress, message
                ) VALUES (%s, %s, 'queued', 'queued', 0, 'Enviando original')
                RETURNING *
                """,
                (job_id, creative_id),
            )
            row = cursor.fetchone()
        return _serialize(row)

    def get_job(self, public_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT j.*, c.public_id AS creative_public_id
                  FROM cx_camadas_jobs j
                  JOIN cx_camadas_creatives c ON c.id = j.creative_id
                 WHERE j.public_id = %s
                """,
                (public_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CamadasNotFoundError("Job não encontrado.")
        return _serialize(row)

    def latest_job(self, creative_pk):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM cx_camadas_jobs
                 WHERE creative_id = %s
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (creative_pk,),
            )
            row = cursor.fetchone()
        return _serialize(row) if row else None

    def update_job(self, public_id, **fields):
        allowed = {"status", "stage", "progress", "message", "error"}
        assignments = []
        values = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            assignments.append(f"{key} = %s")
            values.append(value)
        if not assignments:
            return self.get_job(public_id)
        assignments.append("updated_at = NOW()")
        values.append(public_id)
        with self._write() as cursor:
            cursor.execute(
                f"""
                UPDATE cx_camadas_jobs
                   SET {", ".join(assignments)}
                 WHERE public_id = %s
             RETURNING *
                """,
                tuple(values),
            )
            row = cursor.fetchone()
        if not row:
            raise CamadasNotFoundError("Job não encontrado.")
        return _serialize(row)

    def replace_elements(self, creative_pk, rows):
        with self._write() as cursor:
            cursor.execute(
                "DELETE FROM cx_camadas_elements WHERE creative_id = %s",
                (creative_pk,),
            )
            saved = []
            for item in rows or []:
                public_id = item.get("public_id") or new_public_id("element")
                cursor.execute(
                    """
                    INSERT INTO cx_camadas_elements (
                        public_id, creative_id, role, label, layer_type,
                        bbox, quality, provenance, visible, locked, z_index,
                        approved, text_content, png_path, mask_path, thumb_path, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    RETURNING *
                    """,
                    (
                        public_id,
                        creative_pk,
                        item.get("role") or "support",
                        item.get("label") or "",
                        item.get("layer_type") or "image",
                        Json(item.get("bbox") or {}),
                        item.get("quality") or "",
                        item.get("provenance") or "html",
                        bool(item.get("visible", True)),
                        bool(item.get("locked", False)),
                        int(item.get("z_index") or 0),
                        bool(item.get("approved", False)),
                        item.get("text_content") or "",
                        item.get("png_path"),
                        item.get("mask_path"),
                        item.get("thumb_path"),
                        Json(item.get("metadata") or {}),
                    ),
                )
                saved.append(_serialize(cursor.fetchone()))
        return saved

    def list_elements(self, creative_pk):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM cx_camadas_elements
                 WHERE creative_id = %s
                 ORDER BY z_index, id
                """,
                (creative_pk,),
            )
            rows = cursor.fetchall()
        return [_serialize(row) for row in rows]

    def get_element(self, public_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT e.*, c.public_id AS creative_public_id
                  FROM cx_camadas_elements e
                  JOIN cx_camadas_creatives c ON c.id = e.creative_id
                 WHERE e.public_id = %s
                """,
                (public_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CamadasNotFoundError("Elemento não encontrado.")
        return _serialize(row)

    def add_element(self, creative_pk, data):
        public_id = data.get("public_id") or new_public_id("element")
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_camadas_elements (
                    public_id, creative_id, role, label, layer_type,
                    bbox, quality, provenance, visible, locked, z_index,
                    approved, text_content, png_path, mask_path, thumb_path, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING *
                """,
                (
                    public_id,
                    creative_pk,
                    data.get("role") or "product",
                    data.get("label") or "",
                    data.get("layer_type") or "image",
                    Json(data.get("bbox") or {}),
                    data.get("quality") or "",
                    data.get("provenance") or "recorte_original",
                    bool(data.get("visible", True)),
                    bool(data.get("locked", False)),
                    int(data.get("z_index") or 0),
                    bool(data.get("approved", False)),
                    data.get("text_content") or "",
                    data.get("png_path"),
                    data.get("mask_path"),
                    data.get("thumb_path"),
                    Json(data.get("metadata") or {}),
                ),
            )
            row = cursor.fetchone()
        return _serialize(row)

    def update_element(self, public_id, **fields):
        allowed = {
            "label",
            "visible",
            "locked",
            "z_index",
            "approved",
            "quality",
            "bbox",
            "png_path",
            "mask_path",
            "metadata",
            "text_content",
        }
        assignments = []
        values = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in {"bbox", "metadata"}:
                assignments.append(f"{key} = %s")
                values.append(Json(value))
            else:
                assignments.append(f"{key} = %s")
                values.append(value)
        if not assignments:
            return self.get_element(public_id)
        assignments.append("updated_at = NOW()")
        values.append(public_id)
        with self._write() as cursor:
            cursor.execute(
                f"""
                UPDATE cx_camadas_elements
                   SET {", ".join(assignments)}
                 WHERE public_id = %s
             RETURNING *
                """,
                tuple(values),
            )
            row = cursor.fetchone()
        if not row:
            raise CamadasNotFoundError("Elemento não encontrado.")
        return _serialize(row)

    def save_mask(self, element_pk, data):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_camadas_masks (element_id, version, mask_path, contours, points)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    element_pk,
                    int(data.get("version") or 1),
                    data.get("mask_path"),
                    Json(data.get("contours") or []),
                    Json(data.get("points") or []),
                ),
            )
            row = cursor.fetchone()
        return _serialize(row)

    def upsert_scene(self, creative_pk, document, version=1):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_camadas_scenes (creative_id, version, document)
                VALUES (%s, %s, %s)
                ON CONFLICT (creative_id) DO UPDATE
                   SET version = EXCLUDED.version,
                       document = EXCLUDED.document,
                       updated_at = NOW()
                RETURNING *
                """,
                (creative_pk, int(version or 1), Json(document or {})),
            )
            row = cursor.fetchone()
        return _serialize(row)

    def get_scene(self, creative_pk):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM cx_camadas_scenes WHERE creative_id = %s",
                (creative_pk,),
            )
            row = cursor.fetchone()
        return _serialize(row) if row else None

    def update_scene_if_version(self, creative_pk, expected_version, document):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_camadas_scenes
                   SET document = %s,
                       version = version + 1,
                       updated_at = NOW()
                 WHERE creative_id = %s
                   AND version = %s
             RETURNING *
                """,
                (Json(document or {}), creative_pk, int(expected_version)),
            )
            row = cursor.fetchone()
        if not row:
            current = self.get_scene(creative_pk)
            if not current:
                raise CamadasNotFoundError("Cena não encontrada.")
            raise CamadasConflictError("A cena mudou. Recarregue e tente de novo.")
        return _serialize(row)

    def list_collections(self, client_id):
        if not client_id:
            return []
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM cx_camadas_collections
                 WHERE client_id = %s
                 ORDER BY created_at DESC
                """,
                (client_id,),
            )
            rows = cursor.fetchall()
        return [_serialize(row) for row in rows]

    def get_collection(self, public_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM cx_camadas_collections WHERE public_id = %s",
                (public_id,),
            )
            row = cursor.fetchone()
        return _serialize(row) if row else None

    def get_collection_by_pk(self, collection_pk):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM cx_camadas_collections WHERE id = %s",
                (collection_pk,),
            )
            row = cursor.fetchone()
        return _serialize(row) if row else None

    def find_collection_by_name(self, client_id, name):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM cx_camadas_collections
                 WHERE client_id = %s AND lower(name) = lower(%s)
                 ORDER BY id
                 LIMIT 1
                """,
                (client_id, str(name or "").strip()),
            )
            row = cursor.fetchone()
        return _serialize(row) if row else None

    def create_collection(self, data):
        public_id = data.get("public_id") or new_public_id("collection")
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_camadas_collections (public_id, client_id, name)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (public_id, data.get("client_id"), str(data.get("name") or "Geral")[:200]),
            )
            row = cursor.fetchone()
        return _serialize(row)

    def create_asset(self, data):
        public_id = data.get("public_id") or new_public_id("asset")
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_camadas_assets (
                    public_id, client_id, collection_id, element_id, creative_id,
                    name, kind, provenance, sha256, asset_path, thumb_path, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING *
                """,
                (
                    public_id,
                    data.get("client_id"),
                    data.get("collection_id"),
                    data.get("element_id"),
                    data.get("creative_id"),
                    str(data.get("name") or "")[:200],
                    data.get("kind") or "graphic",
                    data.get("provenance") or "cutout",
                    data.get("sha256") or "",
                    data.get("asset_path"),
                    data.get("thumb_path"),
                    Json(data.get("metadata") or {}),
                ),
            )
            row = cursor.fetchone()
        return _serialize(row)

    def get_asset(self, public_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM cx_camadas_assets WHERE public_id = %s",
                (public_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CamadasNotFoundError("Ativo não encontrado.")
        return _serialize(row)

    def find_asset_by_sha(self, client_id, sha256):
        if not client_id or not sha256:
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM cx_camadas_assets
                 WHERE client_id = %s AND sha256 = %s
                 ORDER BY id
                 LIMIT 1
                """,
                (client_id, sha256),
            )
            row = cursor.fetchone()
        return _serialize(row) if row else None

    def list_assets(self, client_id, collection_pk=None):
        if not client_id:
            return []
        sql = """
            SELECT a.*, c.public_id AS collection_public_id, c.name AS collection_name
              FROM cx_camadas_assets a
              LEFT JOIN cx_camadas_collections c ON c.id = a.collection_id
             WHERE a.client_id = %s
        """
        values = [client_id]
        if collection_pk:
            sql += " AND a.collection_id = %s"
            values.append(collection_pk)
        sql += " ORDER BY a.created_at DESC, a.id DESC"
        with self.conn.cursor() as cursor:
            cursor.execute(sql, tuple(values))
            rows = cursor.fetchall()
        return [_serialize(row) for row in rows]
