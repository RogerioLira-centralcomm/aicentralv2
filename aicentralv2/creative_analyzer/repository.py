"""Histórico unificado do Creative Analyzer.

A fonte PHP é somente leitura. Novas análises pertencem às tabelas do Studio.
"""

from __future__ import annotations

import json
from datetime import date, datetime


LEGACY_COLUMNS = (
    "id",
    "uuid",
    "user_id",
    "client_id",
    "arquivo_nome",
    "arquivo_tipo",
    "arquivo_formato",
    "thumbnail_base64",
    "imagem_path",
    "score_geral",
    "analise_completa",
    "created_at",
)


def _json_object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _iso(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value or "")


def _score(row, analysis):
    stored = row.get("score_geral")
    if stored is not None:
        return stored
    for key in ("score", "scores"):
        candidate = analysis.get(key)
        if isinstance(candidate, dict) and candidate.get("geral") is not None:
            return candidate["geral"]
    return None


def _thumbnail(value):
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith(("data:image/", "http://", "https://", "/")):
        return text
    return f"data:image/jpeg;base64,{text}"


def legacy_item(row, legacy_origin):
    """Normaliza versões conhecidas sem alterar o JSON histórico."""
    analysis = _json_object(row.get("analise_completa"))
    mime = str(row.get("arquivo_tipo") or "").lower()
    filename = str(row.get("arquivo_nome") or "Criativo")
    extension = str(row.get("arquivo_formato") or "").lower()
    is_video = mime.startswith("video/") or extension in {"mp4", "mov", "webm", "avi"}
    uuid = str(row.get("uuid") or "")
    item_id = uuid or str(row.get("id") or "")
    classification = analysis.get("classificacao") if isinstance(analysis.get("classificacao"), dict) else {}
    origin = str(legacy_origin or "https://cadu.centralcomm.media").rstrip("/")
    return {
        "id": f"legacy:{item_id}",
        "source": "legacy",
        "source_id": row.get("id"),
        "source_uuid": uuid or None,
        "name": filename,
        "media_type": "video" if is_video else "image",
        "mime_type": row.get("arquivo_tipo") or None,
        "format": row.get("arquivo_formato") or None,
        "thumbnail": _thumbnail(row.get("thumbnail_base64")),
        "score": _score(row, analysis),
        "creative_type": classification.get("tipo"),
        "funnel": classification.get("funil"),
        "status": "complete",
        "created_at": _iso(row.get("created_at")),
        "result_url": f"{origin}/creative-analyzer/{uuid}" if uuid else f"{origin}/creative-analyzer?carregar={row.get('id')}",
        "opens_legacy": True,
    }


def studio_item(row):
    payload = _json_object(row.get("result_json"))
    score = payload.get("score") if isinstance(payload.get("score"), dict) else {}
    public_id = str(row.get("public_id") or "")
    return {
        "id": f"studio:{public_id}",
        "source": "studio",
        "source_id": row.get("id"),
        "source_uuid": public_id,
        "name": row.get("original_name") or "Criativo",
        "media_type": row.get("media_type") or "image",
        "mime_type": row.get("mime_type") or None,
        "format": row.get("format") or None,
        "thumbnail": row.get("thumbnail_url") or None,
        "score": row.get("score_geral") if row.get("score_geral") is not None else score.get("geral"),
        "creative_type": row.get("creative_type") or None,
        "funnel": row.get("funnel") or None,
        "status": row.get("status") or "queued",
        "created_at": _iso(row.get("created_at")),
        "result_url": f"/analyzer/{public_id}",
        "opens_legacy": False,
    }


def merge_history(legacy_rows, studio_rows, legacy_origin, limit, offset):
    rows = [legacy_item(row, legacy_origin) for row in legacy_rows]
    rows.extend(studio_item(row) for row in studio_rows)
    rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    page = rows[offset : offset + limit + 1]
    return page[:limit], offset + limit if len(page) > limit else None


class AnalyzerRepository:
    def __init__(self, connection=None, legacy_origin=None):
        self._connection = connection
        self.legacy_origin = legacy_origin

    @property
    def connection(self):
        if self._connection is not None:
            return self._connection
        from .. import db

        return db.get_db()

    def _columns(self, table):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_schema = 'public' AND table_name = %s
                """,
                (table,),
            )
            return {row["column_name"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()}

    def _legacy(self, user_id, client_id, fetch_limit):
        columns = self._columns("cadu_analises_criativos")
        if not columns:
            return []
        selected = [name if name in columns else f"NULL AS {name}" for name in LEGACY_COLUMNS]
        where = []
        params = []
        if "client_id" in columns:
            where.append("client_id = %s")
            params.append(client_id)
        elif "user_id" in columns:
            where.append("user_id = %s")
            params.append(user_id)
        else:
            return []
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {', '.join(selected)} FROM public.cadu_analises_criativos "
                f"WHERE {' AND '.join(where)} ORDER BY created_at DESC NULLS LAST LIMIT %s",
                tuple(params + [fetch_limit]),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _studio(self, user_id, client_id, fetch_limit):
        if not self._columns("studio_creative_analyses"):
            return []
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, public_id, original_name, media_type, mime_type,
                       format, thumbnail_url, score_geral, creative_type,
                       funnel, status, result_json, created_at
                  FROM public.studio_creative_analyses
                 WHERE client_id = %s
                 ORDER BY created_at DESC
                 LIMIT %s
                """,
                (client_id, fetch_limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_history(self, user_id, client_id, limit=24, offset=0):
        fetch_limit = offset + limit + 1
        return merge_history(
            self._legacy(user_id, client_id, fetch_limit),
            self._studio(user_id, client_id, fetch_limit),
            self.legacy_origin,
            limit,
            offset,
        )
