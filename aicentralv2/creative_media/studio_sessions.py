"""Durable Studio sessions shared by creation, Trocr and format adaptation."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager

from psycopg.types.json import Json


SESSION_TYPES = frozenset({"create", "edit", "adapt"})
SESSION_STATUSES = frozenset({
    "draft", "active", "ready", "finalizing", "finalized", "archived", "failed", "cancelled",
})
MUTABLE_STATUSES = frozenset({"draft", "active", "ready", "failed"})
ASSET_KINDS = frozenset({"reference", "image", "video", "document"})
ASSET_ROLES = frozenset({"reference", "base", "attempt", "accepted", "final", "discard"})
TRANSITIONS = {
    "draft": {"active", "ready", "cancelled", "archived"},
    "active": {"ready", "failed", "cancelled", "archived"},
    "ready": {"active", "finalizing", "failed", "cancelled", "archived"},
    "finalizing": {"finalized", "ready", "failed"},
    "finalized": {"archived"},
    "failed": {"active", "ready", "cancelled", "archived"},
    "cancelled": {"archived"},
    "archived": set(),
}
DISCARD_RETENTION_SECONDS = max(0, int(os.getenv("STUDIO_DISCARD_RETENTION_SECONDS", "604800")))
DELETABLE_PREFIXES = ("/static/uploads/creative_generated/", "/static/uploads/creative_references/")


class SessionConflict(ValueError):
    pass


def new_id():
    return str(uuid.uuid4())


def clean_text(value, limit):
    return str(value or "").strip()[:limit]


def require_type(value):
    value = clean_text(value, 24).lower()
    if value not in SESSION_TYPES:
        raise ValueError("Tipo de sessão inválido.")
    return value


def require_status(value):
    value = clean_text(value, 24).lower()
    if value not in SESSION_STATUSES:
        raise ValueError("Status de sessão inválido.")
    return value


def check_transition(current, target):
    if target == current:
        return
    if target not in TRANSITIONS.get(current, set()):
        raise ValueError(f"Não é possível mudar a sessão de {current} para {target}.")


def estimate_metrics(events, active_seconds=0):
    counts = {"generation": 0, "edit": 0, "format": 0, "handoff": 0}
    for event in events or []:
        kind = str(event.get("event_type") or "")
        if kind == "generation_completed":
            counts["generation"] += 1
        elif kind == "edit_completed":
            counts["edit"] += 1
        elif kind == "format_created":
            counts["format"] += 1
        elif kind == "handoff_created":
            counts["handoff"] += 1
    manual = (45 if counts["generation"] else 0) + counts["edit"] * 12 + counts["format"] * 8
    active_minutes = max(0, int(active_seconds or 0)) // 60
    counts["estimated_minutes_saved"] = max(0, manual - active_minutes)
    counts["active_seconds"] = max(0, int(active_seconds or 0))
    return counts


def public_session(row, assets=None, finalization=None):
    data = dict(row or {})
    for key in ("metadata",):
        if isinstance(data.get(key), str):
            try:
                data[key] = json.loads(data[key])
            except json.JSONDecodeError:
                data[key] = {}
    data["assets"] = assets or []
    data["finalization"] = finalization
    data["read_only"] = data.get("status") in {"finalized", "archived", "cancelled"}
    return data


class LocalSessionRepository:
    """SQLite fallback used by local development and isolated tests."""

    def __init__(self, root, retention_seconds=None):
        self.path = root / "studio-sessions.sqlite3"
        self.retention_seconds = DISCARD_RETENTION_SECONDS if retention_seconds is None else max(0, int(retention_seconds))
        root.mkdir(parents=True, exist_ok=True)
        self.ensure()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def ensure(self):
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY, client_id INTEGER NOT NULL, owner_user_id INTEGER NOT NULL,
                    project_id TEXT, kind TEXT NOT NULL, source_type TEXT NOT NULL, source_id TEXT NOT NULL,
                    title TEXT NOT NULL, asset_url TEXT NOT NULL, storage_key TEXT NOT NULL,
                    status TEXT NOT NULL, metadata TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS assets_source ON assets(client_id, source_type, source_id)
                    WHERE source_id <> '';
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, root_session_id TEXT NOT NULL, parent_session_id TEXT,
                    project_id TEXT, client_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                    studio_type TEXT NOT NULL, status TEXT NOT NULL, title TEXT NOT NULL,
                    revision INTEGER NOT NULL, active_asset_id TEXT, base_asset_id TEXT,
                    original_prompt TEXT NOT NULL, optimized_prompt TEXT NOT NULL,
                    prompt_language TEXT NOT NULL, prompt_version TEXT NOT NULL, metadata TEXT NOT NULL,
                    started_at REAL NOT NULL, finalized_at REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS session_assets (
                    session_id TEXT NOT NULL, asset_id TEXT NOT NULL, role TEXT NOT NULL,
                    position INTEGER NOT NULL, created_at REAL NOT NULL,
                    PRIMARY KEY(session_id, asset_id, role)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, event_type TEXT NOT NULL,
                    request_id TEXT, payload TEXT NOT NULL, created_at REAL NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS events_request ON events(session_id, request_id, event_type)
                    WHERE request_id IS NOT NULL AND request_id <> '';
                CREATE TABLE IF NOT EXISTS finalizations (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE, root_session_id TEXT NOT NULL,
                    final_asset_id TEXT NOT NULL, snapshot TEXT NOT NULL, generation_count INTEGER NOT NULL,
                    edit_count INTEGER NOT NULL, format_count INTEGER NOT NULL, handoff_count INTEGER NOT NULL,
                    active_seconds INTEGER NOT NULL, estimated_minutes_saved INTEGER NOT NULL, created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    id TEXT PRIMARY KEY, root_session_id TEXT NOT NULL, finalization_id TEXT NOT NULL,
                    recipient_email TEXT NOT NULL, recipient_name TEXT NOT NULL, kind TEXT NOT NULL,
                    status TEXT NOT NULL, attempts INTEGER NOT NULL, provider_message_id TEXT NOT NULL,
                    payload TEXT NOT NULL, last_error TEXT NOT NULL, available_at REAL NOT NULL,
                    sent_at REAL, created_at REAL NOT NULL,
                    UNIQUE(root_session_id, kind)
                );
                CREATE TABLE IF NOT EXISTS deletions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id TEXT NOT NULL UNIQUE,
                    storage_key TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL,
                    available_at REAL NOT NULL, deleted_at REAL, last_error TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)

    def create(self, client_id, user_id, payload):
        now = time.time()
        ident = new_id()
        root_id = clean_text(payload.get("root_session_id"), 64) or ident
        parent_id = clean_text(payload.get("parent_session_id"), 64) or None
        project_id = clean_text(payload.get("project_id"), 64) or None
        kind = require_type(payload.get("studio_type") or "create")
        title = clean_text(payload.get("title"), 160) or "Novo trabalho"
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        with self.connection() as db:
            if root_id != ident:
                parent = db.execute(
                    "SELECT root_session_id FROM sessions WHERE id=? AND client_id=?",
                    (parent_id or root_id, int(client_id)),
                ).fetchone()
                if not parent:
                    raise ValueError("Sessão de origem não encontrada.")
                root_id = parent["root_session_id"]
            db.execute("""
                INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (ident, root_id, parent_id, project_id, int(client_id), int(user_id), kind, "draft", title, 1,
                  None, None, clean_text(payload.get("original_prompt"), 12000),
                  clean_text(payload.get("optimized_prompt"), 20000),
                  clean_text(payload.get("prompt_language"), 16) or "pt-BR",
                  clean_text(payload.get("prompt_version"), 40), json.dumps(metadata, ensure_ascii=False),
                  now, None, now, now))
            self._event(db, ident, "session_started", payload={"studio_type": kind})
        return self.read(client_id, user_id, ident)

    def listing(self, client_id, user_id, project_id=None, status=None, limit=100):
        clauses = ["client_id=?"]
        values = [int(client_id)]
        if project_id:
            clauses.append("project_id=?")
            values.append(str(project_id))
        else:
            clauses.extend(["project_id IS NULL", "user_id=?"])
            values.append(int(user_id))
        if status:
            clauses.append("status=?")
            values.append(require_status(status))
        values.append(max(1, min(int(limit), 200)))
        with self.connection() as db:
            rows = db.execute(
                f"SELECT * FROM sessions WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?", values,
            ).fetchall()
        return [public_session(row) for row in rows]

    def read(self, client_id, user_id, ident):
        with self.connection() as db:
            row = self._owned(db, client_id, user_id, ident)
            assets = [dict(item) for item in db.execute("""
                SELECT a.*, sa.role, sa.position FROM session_assets sa
                JOIN assets a ON a.id=sa.asset_id WHERE sa.session_id=?
                ORDER BY sa.position, sa.created_at
            """, (ident,)).fetchall()]
            final = db.execute("SELECT * FROM finalizations WHERE session_id=?", (ident,)).fetchone()
        return public_session(row, assets, dict(final) if final else None)

    def save(self, client_id, user_id, ident, payload):
        with self.connection() as db:
            row = self._owned(db, client_id, user_id, ident)
            if row["status"] not in MUTABLE_STATUSES:
                raise ValueError("Esta sessão está concluída. Use Continuar editando para criar uma nova sessão.")
            expected = int(payload.get("expected_revision") or 0)
            if expected != row["revision"]:
                raise SessionConflict("A sessão foi alterada em outra aba. Sua edição local foi preservada.")
            target = require_status(payload.get("status") or row["status"])
            check_transition(row["status"], target)
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else json.loads(row["metadata"])
            values = (
                clean_text(payload.get("title", row["title"]), 160) or row["title"], target,
                clean_text(payload.get("original_prompt", row["original_prompt"]), 12000),
                clean_text(payload.get("optimized_prompt", row["optimized_prompt"]), 20000),
                clean_text(payload.get("prompt_language", row["prompt_language"]), 16) or "pt-BR",
                clean_text(payload.get("prompt_version", row["prompt_version"]), 40),
                json.dumps(metadata, ensure_ascii=False), time.time(), ident, row["revision"],
            )
            changed = db.execute("""
                UPDATE sessions SET title=?, status=?, original_prompt=?, optimized_prompt=?, prompt_language=?,
                    prompt_version=?, metadata=?, revision=revision+1, updated_at=? WHERE id=? AND revision=?
            """, values)
            if changed.rowcount != 1:
                raise SessionConflict("A sessão foi alterada em outra aba. Sua edição local foi preservada.")
            self._event(db, ident, "saved", payload={"revision": row["revision"] + 1})
        return self.read(client_id, user_id, ident)

    def accept(self, client_id, user_id, ident, payload):
        role = clean_text(payload.get("role"), 24) or "accepted"
        if role not in {"reference", "base", "attempt", "accepted"}:
            raise ValueError("Papel do ativo inválido.")
        with self.connection() as db:
            session = self._owned(db, client_id, user_id, ident)
            if session["status"] not in MUTABLE_STATUSES:
                raise ValueError("Esta sessão não aceita novas versões.")
            asset = self._ensure_asset(db, client_id, user_id, session["project_id"], payload)
            now = time.time()
            db.execute("INSERT OR IGNORE INTO session_assets VALUES (?,?,?,?,?)", (ident, asset, role, int(payload.get("position") or 0), now))
            if role in {"accepted", "base"}:
                db.execute("UPDATE assets SET status='accepted', updated_at=? WHERE id=?", (now, asset))
                db.execute("UPDATE deletions SET status='cancelled', last_error='' WHERE asset_id=? AND status IN ('pending','failed')", (asset,))
                db.execute("UPDATE sessions SET active_asset_id=?, base_asset_id=?, status='ready', revision=revision+1, updated_at=? WHERE id=?",
                           (asset, asset, now, ident))
                self._event(db, ident, "asset_accepted" if role == "accepted" else "base_changed", payload={"asset_id": asset})
            else:
                db.execute("UPDATE sessions SET status=CASE WHEN status='draft' THEN 'active' ELSE status END, revision=revision+1, updated_at=? WHERE id=?", (now, ident))
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            if role == "attempt" and metadata.get("origin") == "generation":
                self._event(db, ident, "generation_completed", clean_text(payload.get("source_id"), 180) or asset,
                            {"asset_id": asset})
        return self.read(client_id, user_id, ident)

    def handoff(self, client_id, user_id, ident, payload):
        request_id = clean_text(payload.get("request_id"), 160)
        with self.connection() as db:
            source = self._owned(db, client_id, user_id, ident)
            if not source["base_asset_id"]:
                raise ValueError("Escolha uma peça como base antes de abrir outro editor.")
            if request_id:
                event = db.execute("SELECT payload FROM events WHERE session_id=? AND request_id=? AND event_type='handoff_created'", (ident, request_id)).fetchone()
                if event:
                    child_id = json.loads(event["payload"])["child_session_id"]
                    return self.read(client_id, user_id, child_id)
            child_id = self._create_child(db, source, user_id, require_type(payload.get("studio_type") or "edit"), clean_text(payload.get("title"), 160))
            self._event(db, ident, "handoff_created", request_id, {"child_session_id": child_id})
        return self.read(client_id, user_id, child_id)

    def continue_session(self, client_id, user_id, ident, payload):
        with self.connection() as db:
            source = self._owned(db, client_id, user_id, ident)
            if source["status"] != "finalized":
                raise ValueError("Finalize o trabalho antes de criar uma continuação.")
            child_id = self._create_child(db, source, user_id, require_type(payload.get("studio_type") or source["studio_type"]), clean_text(payload.get("title"), 160))
            self._event(db, child_id, "continued_from_final", payload={"parent_session_id": ident})
        return self.read(client_id, user_id, child_id)

    def discard(self, client_id, user_id, ident, asset_id, restore=False):
        with self.connection() as db:
            session = self._owned(db, client_id, user_id, ident)
            if session["status"] not in MUTABLE_STATUSES:
                raise ValueError("Esta sessão não aceita alterações no descarte.")
            linked = db.execute("SELECT 1 FROM session_assets WHERE session_id=? AND asset_id=?", (ident, asset_id)).fetchone()
            if not linked:
                raise ValueError("Ativo não encontrado nesta sessão.")
            now = time.time()
            if restore:
                db.execute("DELETE FROM session_assets WHERE session_id=? AND asset_id=? AND role='discard'", (ident, asset_id))
                db.execute("UPDATE assets SET status='working', updated_at=? WHERE id=? AND status='discarded'", (now, asset_id))
                db.execute("UPDATE deletions SET status='cancelled', last_error='' WHERE asset_id=? AND status IN ('pending','failed')", (asset_id,))
            else:
                if asset_id in {session["active_asset_id"], session["base_asset_id"]}:
                    raise ValueError("A peça ativa não pode ser descartada.")
                db.execute("INSERT OR IGNORE INTO session_assets VALUES (?,?,?,?,?)", (ident, asset_id, "discard", 0, now))
                db.execute("UPDATE assets SET status='discarded', updated_at=? WHERE id=?", (now, asset_id))
                asset = db.execute("SELECT storage_key FROM assets WHERE id=?", (asset_id,)).fetchone()
                storage_key = str(asset["storage_key"] or "") if asset else ""
                if storage_key.startswith(DELETABLE_PREFIXES):
                    db.execute("""
                        INSERT INTO deletions(asset_id,storage_key,status,attempts,available_at,deleted_at,last_error,created_at)
                        VALUES (?,?,'pending',0,?,NULL,'',?)
                        ON CONFLICT(asset_id) DO UPDATE SET storage_key=excluded.storage_key,status='pending',
                            available_at=excluded.available_at,deleted_at=NULL,last_error=''
                    """, (asset_id, storage_key, now + self.retention_seconds, now))
            self._event(db, ident, "asset_restored" if restore else "trash_marked", payload={"asset_id": asset_id})
        return self.read(client_id, user_id, ident)

    def finalize(self, client_id, user_id, ident, payload):
        with self.connection() as db:
            session = self._owned(db, client_id, user_id, ident)
            existing = db.execute("SELECT * FROM finalizations WHERE session_id=?", (ident,)).fetchone()
            if existing:
                return {"session": self.read(client_id, user_id, ident), "finalization": dict(existing), "replayed": True}
            if session["status"] not in {"ready", "active"} or not session["active_asset_id"]:
                raise ValueError("Escolha a peça final antes de concluir o trabalho.")
            if payload.get("pending_jobs"):
                raise ValueError("Aguarde as gerações em andamento antes de finalizar.")
            events = [dict(row) for row in db.execute("SELECT event_type FROM events WHERE session_id=?", (ident,)).fetchall()]
            metrics = estimate_metrics(events, payload.get("active_seconds"))
            asset = db.execute("SELECT * FROM assets WHERE id=?", (session["active_asset_id"],)).fetchone()
            final_id = new_id()
            now = time.time()
            asset_snapshot = {key: asset[key] for key in ("id", "kind", "title", "asset_url", "storage_key")}
            snapshot = {"session_id": ident, "root_session_id": session["root_session_id"], "asset": asset_snapshot,
                        "title": session["title"], "credits": max(0, int(payload.get("credits") or 0))}
            db.execute("""
                INSERT INTO finalizations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (final_id, ident, session["root_session_id"], session["active_asset_id"], json.dumps(snapshot, ensure_ascii=False),
                  metrics["generation"], metrics["edit"], metrics["format"], metrics["handoff"], metrics["active_seconds"],
                  metrics["estimated_minutes_saved"], now))
            db.execute("UPDATE assets SET status='final', updated_at=? WHERE id=?", (now, session["active_asset_id"]))
            db.execute("INSERT OR IGNORE INTO session_assets VALUES (?,?,?,?,?)", (ident, session["active_asset_id"], "final", 0, now))
            db.execute("UPDATE sessions SET status='finalized', finalized_at=?, revision=revision+1, updated_at=? WHERE id=?", (now, now, ident))
            self._event(db, ident, "finalized", payload={"finalization_id": final_id, **metrics})
            email = clean_text(payload.get("recipient_email"), 320).lower()
            if email:
                db.execute("INSERT OR IGNORE INTO outbox VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    new_id(), session["root_session_id"], final_id, email, clean_text(payload.get("recipient_name"), 160),
                    "first_finalization", "pending", 0, "", json.dumps(snapshot, ensure_ascii=False), "", now, None, now,
                ))
                self._event(db, ident, "email_queued", payload={"recipient": email})
            final = db.execute("SELECT * FROM finalizations WHERE id=?", (final_id,)).fetchone()
        return {"session": self.read(client_id, user_id, ident), "finalization": dict(final), "replayed": False}

    def _owned(self, db, client_id, user_id, ident):
        row = db.execute("""
            SELECT * FROM sessions WHERE id=? AND client_id=?
              AND (project_id IS NOT NULL OR user_id=?)
        """, (ident, int(client_id), int(user_id))).fetchone()
        if not row:
            raise ValueError("Sessão não encontrada neste Studio.")
        return row

    def _event(self, db, session_id, event_type, request_id=None, payload=None):
        db.execute("INSERT OR IGNORE INTO events(session_id,event_type,request_id,payload,created_at) VALUES (?,?,?,?,?)",
                   (session_id, event_type, request_id or None, json.dumps(payload or {}, ensure_ascii=False), time.time()))

    def _ensure_asset(self, db, client_id, user_id, project_id, payload):
        asset_id = clean_text(payload.get("asset_id"), 64)
        if asset_id:
            row = db.execute("SELECT id FROM assets WHERE id=? AND client_id=?", (asset_id, int(client_id))).fetchone()
            if not row:
                raise ValueError("Ativo não encontrado neste Studio.")
            return asset_id
        url = clean_text(payload.get("asset_url") or payload.get("image_url"), 4000)
        if not url:
            raise ValueError("Escolha uma imagem ou vídeo para a sessão.")
        source_type = clean_text(payload.get("source_type"), 48) or "studio"
        source_id = clean_text(payload.get("source_id"), 180)
        if source_id:
            row = db.execute("SELECT id FROM assets WHERE client_id=? AND source_type=? AND source_id=?", (int(client_id), source_type, source_id)).fetchone()
            if row:
                return row["id"]
        asset_id = new_id()
        now = time.time()
        kind = clean_text(payload.get("kind"), 24) or "image"
        if kind not in ASSET_KINDS:
            raise ValueError("Tipo de ativo inválido.")
        storage_key = clean_text(payload.get("storage_key"), 2000)
        if not storage_key and url.startswith(DELETABLE_PREFIXES):
            storage_key = url
        db.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            asset_id, int(client_id), int(user_id), project_id, kind, source_type, source_id,
            clean_text(payload.get("title"), 160) or "Ativo do Studio", url,
            storage_key, "working",
            json.dumps(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}, ensure_ascii=False), now, now,
        ))
        return asset_id

    def _create_child(self, db, source, user_id, studio_type, title):
        ident = new_id()
        now = time.time()
        db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            ident, source["root_session_id"], source["id"], source["project_id"], source["client_id"], int(user_id),
            studio_type, "active", title or f"Continuação de {source['title']}", 1,
            source["active_asset_id"], source["base_asset_id"] or source["active_asset_id"], source["original_prompt"],
            source["optimized_prompt"], source["prompt_language"], source["prompt_version"], source["metadata"],
            now, None, now, now,
        ))
        if source["active_asset_id"]:
            db.execute("INSERT OR IGNORE INTO session_assets VALUES (?,?,?,?,?)", (ident, source["active_asset_id"], "base", 0, now))
        self._event(db, ident, "session_started", payload={"parent_session_id": source["id"], "studio_type": studio_type})
        return ident


class PostgresSessionRepository:
    """Canonical PostgreSQL repository used in production."""

    def __init__(self, connection):
        self.connection = connection

    def create(self, client_id, user_id, payload):
        ident = new_id()
        parent_id = clean_text(payload.get("parent_session_id"), 64) or None
        root_id = ident
        project_id = clean_text(payload.get("project_id"), 64) or None
        studio_type = require_type(payload.get("studio_type") or "create")
        with self.connection.cursor() as cursor:
            if parent_id:
                cursor.execute("SELECT root_session_id::text AS root_session_id FROM cx_studio_sessions WHERE id=%s AND client_id=%s", (parent_id, int(client_id)))
                parent = cursor.fetchone()
                if not parent:
                    raise ValueError("Sessão de origem não encontrada.")
                root_id = parent["root_session_id"]
            cursor.execute("""
                INSERT INTO cx_studio_sessions
                    (id,root_session_id,parent_session_id,project_id,client_id,user_id,studio_type,title,
                     original_prompt,optimized_prompt,prompt_language,prompt_version,metadata)
                VALUES (%s,%s,%s,NULLIF(%s,'')::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (ident, root_id, parent_id, project_id or "", int(client_id), int(user_id), studio_type,
                  clean_text(payload.get("title"), 160) or "Novo trabalho",
                  clean_text(payload.get("original_prompt"), 12000), clean_text(payload.get("optimized_prompt"), 20000),
                  clean_text(payload.get("prompt_language"), 16) or "pt-BR", clean_text(payload.get("prompt_version"), 40),
                  Json(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {})))
            self._event(cursor, ident, "session_started", payload={"studio_type": studio_type})
        self.connection.commit()
        return self.read(client_id, user_id, ident)

    def listing(self, client_id, user_id, project_id=None, status=None, limit=100):
        values = [int(client_id)]
        where = ["client_id=%s"]
        if project_id:
            where.append("project_id=%s")
            values.append(project_id)
        else:
            where.extend(["project_id IS NULL", "user_id=%s"])
            values.append(int(user_id))
        if status:
            where.append("status=%s")
            values.append(require_status(status))
        values.append(max(1, min(int(limit), 200)))
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT *, id::text AS id, root_session_id::text AS root_session_id, parent_session_id::text AS parent_session_id, project_id::text AS project_id, active_asset_id::text AS active_asset_id, base_asset_id::text AS base_asset_id FROM cx_studio_sessions WHERE {' AND '.join(where)} ORDER BY updated_at DESC LIMIT %s", values)
            return [public_session(row) for row in cursor.fetchall()]

    def read(self, client_id, user_id, ident):
        with self.connection.cursor() as cursor:
            row = self._owned(cursor, client_id, user_id, ident)
            cursor.execute("""
                SELECT a.*, a.id::text AS id, a.project_id::text AS project_id, sa.role, sa.position
                  FROM cx_studio_session_assets sa JOIN cx_studio_assets a ON a.id=sa.asset_id
                 WHERE sa.session_id=%s ORDER BY sa.position, sa.created_at
            """, (ident,))
            assets = [dict(item) for item in cursor.fetchall()]
            cursor.execute("SELECT *, id::text AS id, final_asset_id::text AS final_asset_id FROM cx_studio_finalizations WHERE session_id=%s", (ident,))
            final = cursor.fetchone()
        return public_session(row, assets, dict(final) if final else None)

    def save(self, client_id, user_id, ident, payload):
        with self.connection.cursor() as cursor:
            row = self._owned(cursor, client_id, user_id, ident)
            if row["status"] not in MUTABLE_STATUSES:
                raise ValueError("Esta sessão está concluída. Use Continuar editando para criar uma nova sessão.")
            expected = int(payload.get("expected_revision") or 0)
            if expected != row["revision"]:
                raise SessionConflict("A sessão foi alterada em outra aba. Sua edição local foi preservada.")
            target = require_status(payload.get("status") or row["status"])
            check_transition(row["status"], target)
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else row["metadata"]
            cursor.execute("""
                UPDATE cx_studio_sessions SET title=%s,status=%s,original_prompt=%s,optimized_prompt=%s,
                    prompt_language=%s,prompt_version=%s,metadata=%s,revision=revision+1,updated_at=NOW()
                 WHERE id=%s AND client_id=%s AND revision=%s RETURNING revision
            """, (clean_text(payload.get("title", row["title"]), 160) or row["title"], target,
                  clean_text(payload.get("original_prompt", row["original_prompt"]), 12000),
                  clean_text(payload.get("optimized_prompt", row["optimized_prompt"]), 20000),
                  clean_text(payload.get("prompt_language", row["prompt_language"]), 16) or "pt-BR",
                  clean_text(payload.get("prompt_version", row["prompt_version"]), 40), Json(metadata), ident, int(client_id), expected))
            saved = cursor.fetchone()
            if not saved:
                raise SessionConflict("A sessão foi alterada em outra aba. Sua edição local foi preservada.")
            self._event(cursor, ident, "saved", payload={"revision": saved["revision"]})
        self.connection.commit()
        return self.read(client_id, user_id, ident)

    def accept(self, client_id, user_id, ident, payload):
        role = clean_text(payload.get("role"), 24) or "accepted"
        if role not in {"reference", "base", "attempt", "accepted"}:
            raise ValueError("Papel do ativo inválido.")
        with self.connection.cursor() as cursor:
            session = self._owned(cursor, client_id, user_id, ident)
            if session["status"] not in MUTABLE_STATUSES:
                raise ValueError("Esta sessão não aceita novas versões.")
            asset_id = self._ensure_asset(cursor, client_id, user_id, session.get("project_id"), payload)
            cursor.execute("""
                INSERT INTO cx_studio_session_assets(session_id,asset_id,role,position)
                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING
            """, (ident, asset_id, role, int(payload.get("position") or 0)))
            if role in {"accepted", "base"}:
                cursor.execute("UPDATE cx_studio_assets SET status='accepted',updated_at=NOW() WHERE id=%s", (asset_id,))
                cursor.execute("UPDATE cx_studio_asset_deletions SET status='cancelled',last_error='' WHERE asset_id=%s AND status IN ('pending','failed')", (asset_id,))
                cursor.execute("UPDATE cx_studio_sessions SET active_asset_id=%s,base_asset_id=%s,status='ready',revision=revision+1,updated_at=NOW() WHERE id=%s", (asset_id, asset_id, ident))
                self._event(cursor, ident, "asset_accepted" if role == "accepted" else "base_changed", payload={"asset_id": asset_id})
            else:
                cursor.execute("UPDATE cx_studio_sessions SET status=CASE WHEN status='draft' THEN 'active' ELSE status END,revision=revision+1,updated_at=NOW() WHERE id=%s", (ident,))
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            if role == "attempt" and metadata.get("origin") == "generation":
                self._event(cursor, ident, "generation_completed", clean_text(payload.get("source_id"), 180) or asset_id,
                            {"asset_id": asset_id})
        self.connection.commit()
        return self.read(client_id, user_id, ident)

    def handoff(self, client_id, user_id, ident, payload):
        return self._derive(client_id, user_id, ident, payload, require_final=False, event_type="handoff_created")

    def continue_session(self, client_id, user_id, ident, payload):
        return self._derive(client_id, user_id, ident, payload, require_final=True, event_type="continued_from_final")

    def discard(self, client_id, user_id, ident, asset_id, restore=False):
        with self.connection.cursor() as cursor:
            session = self._owned(cursor, client_id, user_id, ident)
            if session["status"] not in MUTABLE_STATUSES:
                raise ValueError("Esta sessão não aceita alterações no descarte.")
            cursor.execute("SELECT 1 FROM cx_studio_session_assets WHERE session_id=%s AND asset_id=%s", (ident, asset_id))
            if not cursor.fetchone():
                raise ValueError("Ativo não encontrado nesta sessão.")
            if restore:
                cursor.execute("DELETE FROM cx_studio_session_assets WHERE session_id=%s AND asset_id=%s AND role='discard'", (ident, asset_id))
                cursor.execute("UPDATE cx_studio_assets SET status='working',updated_at=NOW() WHERE id=%s AND status='discarded'", (asset_id,))
                cursor.execute("UPDATE cx_studio_asset_deletions SET status='cancelled',last_error='' WHERE asset_id=%s AND status IN ('pending','failed')", (asset_id,))
            else:
                if asset_id in {session.get("active_asset_id"), session.get("base_asset_id")}:
                    raise ValueError("A peça ativa não pode ser descartada.")
                cursor.execute("INSERT INTO cx_studio_session_assets(session_id,asset_id,role) VALUES (%s,%s,'discard') ON CONFLICT DO NOTHING", (ident, asset_id))
                cursor.execute("UPDATE cx_studio_assets SET status='discarded',updated_at=NOW() WHERE id=%s", (asset_id,))
                cursor.execute("SELECT storage_key FROM cx_studio_assets WHERE id=%s", (asset_id,))
                asset = cursor.fetchone()
                storage_key = str((asset or {}).get("storage_key") or "")
                if storage_key.startswith(DELETABLE_PREFIXES):
                    cursor.execute("""
                        INSERT INTO cx_studio_asset_deletions(asset_id,storage_key,available_at)
                        VALUES (%s,%s,NOW()+(%s * INTERVAL '1 second'))
                        ON CONFLICT (asset_id) DO UPDATE SET storage_key=EXCLUDED.storage_key,status='pending',
                            available_at=EXCLUDED.available_at,deleted_at=NULL,last_error=''
                    """, (asset_id, storage_key, DISCARD_RETENTION_SECONDS))
            self._event(cursor, ident, "asset_restored" if restore else "trash_marked", payload={"asset_id": asset_id})
        self.connection.commit()
        return self.read(client_id, user_id, ident)

    def finalize(self, client_id, user_id, ident, payload):
        with self.connection.cursor() as cursor:
            session = self._owned(cursor, client_id, user_id, ident)
            cursor.execute("SELECT *,id::text AS id FROM cx_studio_finalizations WHERE session_id=%s", (ident,))
            existing = cursor.fetchone()
            if existing:
                return {"session": self.read(client_id, user_id, ident), "finalization": dict(existing), "replayed": True}
            if session["status"] not in {"ready", "active"} or not session.get("active_asset_id"):
                raise ValueError("Escolha a peça final antes de concluir o trabalho.")
            if payload.get("pending_jobs"):
                raise ValueError("Aguarde as gerações em andamento antes de finalizar.")
            cursor.execute("SELECT event_type FROM cx_studio_session_events WHERE session_id=%s", (ident,))
            metrics = estimate_metrics(cursor.fetchall(), payload.get("active_seconds"))
            cursor.execute("SELECT *,id::text AS id FROM cx_studio_assets WHERE id=%s", (session["active_asset_id"],))
            asset = dict(cursor.fetchone())
            final_id = new_id()
            asset_snapshot = {key: asset.get(key) for key in ("id", "kind", "title", "asset_url", "storage_key")}
            snapshot = {"session_id": ident, "root_session_id": session["root_session_id"], "asset": asset_snapshot,
                        "title": session["title"], "credits": max(0, int(payload.get("credits") or 0))}
            cursor.execute("""
                INSERT INTO cx_studio_finalizations
                    (id,session_id,root_session_id,final_asset_id,snapshot,generation_count,edit_count,
                     format_count,handoff_count,active_seconds,estimated_minutes_saved)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (final_id, ident, session["root_session_id"], session["active_asset_id"], Json(snapshot),
                  metrics["generation"], metrics["edit"], metrics["format"], metrics["handoff"],
                  metrics["active_seconds"], metrics["estimated_minutes_saved"]))
            cursor.execute("UPDATE cx_studio_assets SET status='final',updated_at=NOW() WHERE id=%s", (session["active_asset_id"],))
            cursor.execute("INSERT INTO cx_studio_session_assets(session_id,asset_id,role) VALUES (%s,%s,'final') ON CONFLICT DO NOTHING", (ident, session["active_asset_id"]))
            cursor.execute("UPDATE cx_studio_sessions SET status='finalized',finalized_at=NOW(),revision=revision+1,updated_at=NOW() WHERE id=%s", (ident,))
            self._event(cursor, ident, "finalized", payload={"finalization_id": final_id, **metrics})
            email = clean_text(payload.get("recipient_email"), 320).lower()
            if email:
                cursor.execute("""
                    INSERT INTO cx_studio_delivery_outbox
                        (id,root_session_id,finalization_id,recipient_email,recipient_name,payload)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (root_session_id,kind) DO NOTHING
                """, (new_id(), session["root_session_id"], final_id, email, clean_text(payload.get("recipient_name"), 160), Json(snapshot)))
                self._event(cursor, ident, "email_queued", payload={"recipient": email})
        self.connection.commit()
        return {"session": self.read(client_id, user_id, ident), "finalization": {"id": final_id, **metrics}, "replayed": False}

    def _derive(self, client_id, user_id, ident, payload, require_final, event_type):
        request_id = clean_text(payload.get("request_id"), 160)
        with self.connection.cursor() as cursor:
            source = self._owned(cursor, client_id, user_id, ident)
            if require_final and source["status"] != "finalized":
                raise ValueError("Finalize o trabalho antes de criar uma continuação.")
            if not source.get("base_asset_id"):
                raise ValueError("Escolha uma peça como base antes de abrir outro editor.")
            if request_id:
                cursor.execute("SELECT payload FROM cx_studio_session_events WHERE session_id=%s AND request_id=%s AND event_type=%s", (ident, request_id, event_type))
                existing = cursor.fetchone()
                if existing:
                    return self.read(client_id, user_id, existing["payload"]["child_session_id"])
            child_id = new_id()
            studio_type = require_type(payload.get("studio_type") or (source["studio_type"] if require_final else "edit"))
            cursor.execute("""
                INSERT INTO cx_studio_sessions
                    (id,root_session_id,parent_session_id,project_id,client_id,user_id,studio_type,status,title,
                     active_asset_id,base_asset_id,original_prompt,optimized_prompt,prompt_language,prompt_version,metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'active',%s,%s,%s,%s,%s,%s,%s,%s)
            """, (child_id, source["root_session_id"], ident, source.get("project_id"), int(client_id), int(user_id), studio_type,
                  clean_text(payload.get("title"), 160) or f"Continuação de {source['title']}", source.get("active_asset_id"),
                  source.get("base_asset_id") or source.get("active_asset_id"), source["original_prompt"], source["optimized_prompt"],
                  source["prompt_language"], source["prompt_version"], Json(source.get("metadata") or {})))
            cursor.execute("INSERT INTO cx_studio_session_assets(session_id,asset_id,role) VALUES (%s,%s,'base') ON CONFLICT DO NOTHING", (child_id, source.get("base_asset_id") or source.get("active_asset_id")))
            self._event(cursor, ident if event_type == "handoff_created" else child_id, event_type, request_id, {"child_session_id": child_id, "parent_session_id": ident})
            self._event(cursor, child_id, "session_started", payload={"parent_session_id": ident, "studio_type": studio_type})
        self.connection.commit()
        return self.read(client_id, user_id, child_id)

    def _owned(self, cursor, client_id, user_id, ident):
        cursor.execute("""
            SELECT *,id::text AS id,root_session_id::text AS root_session_id,parent_session_id::text AS parent_session_id,
                   project_id::text AS project_id,active_asset_id::text AS active_asset_id,base_asset_id::text AS base_asset_id
              FROM cx_studio_sessions WHERE id=%s AND client_id=%s AND (project_id IS NOT NULL OR user_id=%s)
        """, (ident, int(client_id), int(user_id)))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Sessão não encontrada neste Studio.")
        return dict(row)

    def _event(self, cursor, session_id, event_type, request_id=None, payload=None):
        cursor.execute("""
            INSERT INTO cx_studio_session_events(session_id,event_type,request_id,payload)
            VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING
        """, (session_id, event_type, request_id or None, Json(payload or {})))

    def _ensure_asset(self, cursor, client_id, user_id, project_id, payload):
        asset_id = clean_text(payload.get("asset_id"), 64)
        if asset_id:
            cursor.execute("SELECT id::text AS id FROM cx_studio_assets WHERE id=%s AND client_id=%s AND deleted_at IS NULL", (asset_id, int(client_id)))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Ativo não encontrado neste Studio.")
            return row["id"]
        url = clean_text(payload.get("asset_url") or payload.get("image_url"), 4000)
        if not url:
            raise ValueError("Escolha uma imagem ou vídeo para a sessão.")
        source_type = clean_text(payload.get("source_type"), 48) or "studio"
        source_id = clean_text(payload.get("source_id"), 180)
        if source_id:
            cursor.execute("SELECT id::text AS id FROM cx_studio_assets WHERE client_id=%s AND source_type=%s AND source_id=%s AND deleted_at IS NULL", (int(client_id), source_type, source_id))
            row = cursor.fetchone()
            if row:
                return row["id"]
        kind = clean_text(payload.get("kind"), 24) or "image"
        if kind not in ASSET_KINDS:
            raise ValueError("Tipo de ativo inválido.")
        asset_id = new_id()
        storage_key = clean_text(payload.get("storage_key"), 2000)
        if not storage_key and url.startswith(DELETABLE_PREFIXES):
            storage_key = url
        cursor.execute("""
            INSERT INTO cx_studio_assets
                (id,client_id,owner_user_id,project_id,kind,source_type,source_id,title,asset_url,storage_key,metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (asset_id, int(client_id), int(user_id), project_id, kind, source_type, source_id,
              clean_text(payload.get("title"), 160) or "Ativo do Studio", url, storage_key,
              Json(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {})))
        return asset_id
