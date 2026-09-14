"""Jobs e ativos. Memória para testes; Postgres em produção."""

from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime, timezone

from psycopg.types.json import Json

from .ids import new_id
from .schema import ensure_schema


def utc_now():
    return datetime.now(timezone.utc)


def public_job(row):
    if not row:
        return {}
    data = dict(row)
    data.pop("provider_polling_url", None)
    return data


class MemoryMediaRepository:
    def __init__(self):
        self.jobs = {}
        self.assets = {}
        self._lock = threading.Lock()

    def ready(self):
        return self

    def create_job(self, payload):
        public_id = payload.get("public_id") or new_id("job")
        row = {
            "id": len(self.jobs) + 1,
            "public_id": public_id,
            "user_id": payload.get("user_id"),
            "client_id": payload.get("client_id"),
            "run_id": payload.get("run_id") or "",
            "source_version_id": payload.get("source_version_id") or "",
            "source_revision": payload.get("source_revision"),
            "plan_json": deepcopy(payload.get("plan_json") or {}),
            "plan_hash": payload.get("plan_hash") or "",
            "quote_json": deepcopy(payload.get("quote_json") or {}),
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "message": "Na fila",
            "stages": [],
            "provider": "openrouter",
            "model": payload.get("model") or "",
            "provider_job_id": "",
            "provider_polling_url": "",
            "seed": payload.get("seed"),
            "locked_at": None,
            "started_at": None,
            "completed_at": None,
            "failed_at": None,
            "error_code": "",
            "error_message": "",
            "attempt": 0,
            "version_payload": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.jobs[public_id] = row
        return deepcopy(row)

    def get_job(self, public_id):
        row = self.jobs.get(str(public_id or ""))
        if not row:
            raise MediaNotFoundError("Job não encontrado.")
        return deepcopy(row)

    def update_job(self, public_id, **fields):
        row = self.jobs.get(str(public_id or ""))
        if not row:
            raise MediaNotFoundError("Job não encontrado.")
        row.update(fields)
        row["updated_at"] = utc_now()
        return deepcopy(row)

    def claim_job(self, public_id):
        with self._lock:
            row = self.jobs.get(str(public_id or ""))
            if not row:
                raise MediaNotFoundError("Job não encontrado.")
            if row.get("locked_at") and row.get("status") not in {"queued", "failed"}:
                return None
            row["locked_at"] = utc_now()
            row["attempt"] = int(row.get("attempt") or 0) + 1
            return deepcopy(row)

    def add_asset(self, payload):
        public_id = payload.get("public_id") or new_id("asset")
        row = {
            "id": len(self.assets) + 1,
            "public_id": public_id,
            "job_id": payload.get("job_id"),
            "kind": payload.get("kind") or "master",
            "mime_type": payload.get("mime_type") or "video/mp4",
            "storage_key": payload.get("storage_key") or "",
            "sha256": payload.get("sha256") or "",
            "size_bytes": payload.get("size_bytes") or 0,
            "width": payload.get("width"),
            "height": payload.get("height"),
            "duration": payload.get("duration"),
            "has_audio": bool(payload.get("has_audio")),
            "provenance": deepcopy(payload.get("provenance") or {}),
            "created_at": utc_now(),
        }
        self.assets[public_id] = row
        return deepcopy(row)

    def get_asset(self, public_id):
        row = self.assets.get(str(public_id or ""))
        if not row:
            raise MediaNotFoundError("Ativo não encontrado.")
        return deepcopy(row)

    def list_assets(self, job_id=None, kind=None):
        rows = []
        for item in self.assets.values():
            if job_id not in (None, "") and item.get("job_id") != job_id:
                continue
            if kind and item.get("kind") != kind:
                continue
            rows.append(deepcopy(item))
        return rows

    def find_latest_job_by_creative(self, creative_id):
        wanted = str(creative_id or "")
        if not wanted:
            return None
        matches = []
        for row in self.jobs.values():
            snap = ((row.get("plan_json") or {}).get("source") or {}).get("snapshot") or {}
            if str(snap.get("creative_id") or "") == wanted:
                matches.append(row)
        if not matches:
            return None
        return deepcopy(max(matches, key=lambda item: item.get("id") or 0))


class MediaNotFoundError(LookupError):
    pass


class MediaRepository:
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

    def create_job(self, payload):
        public_id = payload.get("public_id") or new_id("job")
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_media_jobs (
                    public_id, user_id, client_id, run_id, source_version_id,
                    source_revision, plan_json, plan_hash, quote_json, model, seed
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING *
                """,
                (
                    public_id,
                    payload.get("user_id"),
                    payload.get("client_id"),
                    payload.get("run_id") or "",
                    payload.get("source_version_id") or "",
                    payload.get("source_revision"),
                    Json(payload.get("plan_json") or {}),
                    payload.get("plan_hash") or "",
                    Json(payload.get("quote_json") or {}),
                    payload.get("model") or "",
                    payload.get("seed"),
                ),
            )
            row = dict(cursor.fetchone())
        self.conn.commit()
        return row

    def get_job(self, public_id):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM cx_media_jobs WHERE public_id = %s", (public_id,))
            row = cursor.fetchone()
        if not row:
            raise MediaNotFoundError("Job não encontrado.")
        return dict(row)

    def update_job(self, public_id, **fields):
        if not fields:
            return self.get_job(public_id)
        columns = []
        values = []
        json_keys = {"plan_json", "quote_json", "stages", "version_payload"}
        for key, value in fields.items():
            columns.append(f"{key} = %s")
            values.append(Json(value) if key in json_keys else value)
        values.append(public_id)
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"UPDATE cx_media_jobs SET {', '.join(columns)}, updated_at = NOW() WHERE public_id = %s RETURNING *",
                values,
            )
            row = cursor.fetchone()
        self.conn.commit()
        if not row:
            raise MediaNotFoundError("Job não encontrado.")
        return dict(row)

    def claim_job(self, public_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE cx_media_jobs
                   SET locked_at = NOW(),
                       attempt = attempt + 1,
                       updated_at = NOW()
                 WHERE public_id = %s
                   AND (locked_at IS NULL OR status IN ('queued', 'failed'))
             RETURNING *
                """,
                (public_id,),
            )
            row = cursor.fetchone()
        self.conn.commit()
        return dict(row) if row else None

    def add_asset(self, payload):
        public_id = payload.get("public_id") or new_id("asset")
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_media_assets (
                    public_id, job_id, kind, mime_type, storage_key, sha256,
                    size_bytes, width, height, duration, has_audio, provenance
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING *
                """,
                (
                    public_id,
                    payload.get("job_id"),
                    payload.get("kind") or "master",
                    payload.get("mime_type") or "video/mp4",
                    payload.get("storage_key") or "",
                    payload.get("sha256") or "",
                    payload.get("size_bytes") or 0,
                    payload.get("width"),
                    payload.get("height"),
                    payload.get("duration"),
                    bool(payload.get("has_audio")),
                    Json(payload.get("provenance") or {}),
                ),
            )
            row = dict(cursor.fetchone())
        self.conn.commit()
        return row

    def get_asset(self, public_id):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM cx_media_assets WHERE public_id = %s", (public_id,))
            row = cursor.fetchone()
        if not row:
            raise MediaNotFoundError("Ativo não encontrado.")
        return dict(row)

    def list_assets(self, job_id=None, kind=None):
        clauses = []
        values = []
        if job_id not in (None, ""):
            clauses.append("job_id = %s")
            values.append(job_id)
        if kind:
            clauses.append("kind = %s")
            values.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM cx_media_assets {where} ORDER BY id", tuple(values))
            rows = cursor.fetchall()
        return [dict(item) for item in rows]

    def find_latest_job_by_creative(self, creative_id):
        if not creative_id:
            return None
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM cx_media_jobs
                 WHERE plan_json #>> '{source,snapshot,creative_id}' = %s
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (str(creative_id),),
            )
            row = cursor.fetchone()
        return dict(row) if row else None
