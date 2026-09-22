"""Durable Studio delivery and mark-and-sweep cleanup workers."""
from __future__ import annotations

import json
from urllib.parse import quote, urljoin

from flask import current_app


def _mapping(value):
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def absolute_studio_url(value, base_url):
    value = str(value or "").strip()
    if value.startswith(("https://", "http://")):
        return value
    return urljoin(str(base_url or "").rstrip("/") + "/", value.lstrip("/")) if value else ""


class PostgresStudioMaintenance:
    def __init__(self, connection, *, email_sender=None, asset_delete=None, base_url=""):
        self.connection = connection
        self.email_sender = email_sender or self._send_email
        self.asset_delete = asset_delete or self._delete_asset
        self.base_url = str(base_url or current_app.config.get("STUDIO_URL") or "").rstrip("/")

    def drain(self, limit=10):
        counts = {"emails": 0, "assets": 0, "failed": 0}
        for _ in range(max(1, min(int(limit or 1), 100))):
            row = self._claim_email()
            if not row:
                break
            try:
                result = self.email_sender(self._email_payload(row)) or {}
                if result.get("success") is False:
                    raise RuntimeError(str(result.get("error") or "O provedor recusou o e-mail."))
                self._finish_email(row["id"], result.get("messageId") or ("disabled" if result.get("skipped") else ""))
                counts["emails"] += 1
            except Exception as error:
                self._fail_email(row["id"], row["attempts"], error)
                counts["failed"] += 1
        for _ in range(max(1, min(int(limit or 1), 100))):
            row = self._claim_deletion()
            if not row:
                break
            try:
                if not self._safe_to_delete(row["asset_id"]):
                    self._cancel_deletion(row["id"], "Ativo voltou a ser usado por uma sessão ou projeto.")
                    continue
                self.asset_delete(row["storage_key"])
                self._finish_deletion(row["id"], row["asset_id"])
                counts["assets"] += 1
            except Exception as error:
                self._fail_deletion(row["id"], row["attempts"], error)
                counts["failed"] += 1
        return counts

    def _claim_email(self):
        with self.connection.cursor() as cursor:
            cursor.execute("""
                WITH candidate AS (
                    SELECT id FROM cx_studio_delivery_outbox
                     WHERE attempts < 6 AND available_at <= NOW()
                       AND (status IN ('pending','failed') OR (status='processing' AND updated_at < NOW()-INTERVAL '15 minutes'))
                     ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
                )
                UPDATE cx_studio_delivery_outbox o SET status='processing',attempts=attempts+1,updated_at=NOW()
                  FROM candidate WHERE o.id=candidate.id
                RETURNING o.*,o.id::text AS id,o.finalization_id::text AS finalization_id
            """)
            row = cursor.fetchone()
        self.connection.commit()
        return dict(row) if row else None

    def _email_payload(self, row):
        snapshot = _mapping(row.get("payload"))
        if row.get("kind") == "session_saved":
            return {
                "kind": "session_saved", "recipient_email": row.get("recipient_email") or "",
                "recipient_name": row.get("recipient_name") or "", "title": snapshot.get("title") or "Mesa de edição salva",
                "stage_image_url": absolute_studio_url(snapshot.get("stage_image_url"), self.base_url),
                "session_url": absolute_studio_url(snapshot.get("session_url"), self.base_url),
                "edits": snapshot.get("edits", 0), "estimated_credits": snapshot.get("estimated_credits", 0),
                "estimated_minutes": snapshot.get("estimated_minutes", 0), "review_points": snapshot.get("review_points") or [],
            }
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT f.generation_count,f.edit_count,f.format_count,f.handoff_count,f.active_seconds,
                       f.estimated_minutes_saved,a.asset_url,s.id::text AS session_id,s.title
                  FROM cx_studio_finalizations f
                  JOIN cx_studio_assets a ON a.id=f.final_asset_id
                  JOIN cx_studio_sessions s ON s.id=f.session_id
                 WHERE f.id=%s
            """, (row["finalization_id"],))
            detail = dict(cursor.fetchone() or {})
        asset = _mapping(snapshot.get("asset"))
        usage = _mapping(snapshot.get("usage"))
        specifications = _mapping(snapshot.get("specifications"))
        detail.update({
            "charged_credits": usage.get("charged_credits", snapshot.get("credits", 0)),
            "provider_tokens": usage.get("provider_tokens", 0),
            "internal_cost_usd": usage.get("internal_cost_usd", 0),
            "sale_price_per_credit_brl": usage.get("sale_price_per_credit_brl", 0),
            "sale_package_name": usage.get("sale_package_name", ""),
            "format": specifications.get("format", ""),
            "width": specifications.get("width", ""),
            "height": specifications.get("height", ""),
            "quality": specifications.get("quality", ""),
            "extension": specifications.get("extension", ""),
            "project_name": specifications.get("project_name", ""),
        })
        return {
            "recipient_email": row.get("recipient_email") or "",
            "recipient_name": row.get("recipient_name") or "",
            "title": detail.get("title") or snapshot.get("title") or "Trabalho do Studio",
            "asset_url": absolute_studio_url(detail.get("asset_url") or asset.get("asset_url"), self.base_url),
            "public_url": absolute_studio_url(detail.get("asset_url") or asset.get("asset_url"), self.base_url),
            "studio_url": absolute_studio_url("/criar", self.base_url),
            "session_url": absolute_studio_url(
                f"/criar?studio_session_id={quote(str(detail.get('session_id') or ''), safe='')}",
                self.base_url,
            ),
            "metrics": detail,
        }

    def _finish_email(self, ident, message_id):
        self._execute("UPDATE cx_studio_delivery_outbox SET status='sent',provider_message_id=%s,sent_at=NOW(),last_error='',updated_at=NOW() WHERE id=%s", (str(message_id or "")[:180], ident))

    def _fail_email(self, ident, attempts, error):
        delay = min(3600, 30 * (2 ** max(0, int(attempts or 1) - 1)))
        self._execute("UPDATE cx_studio_delivery_outbox SET status='failed',last_error=%s,available_at=NOW()+(%s*INTERVAL '1 second'),updated_at=NOW() WHERE id=%s", (str(error)[:2000], delay, ident))

    def _claim_deletion(self):
        with self.connection.cursor() as cursor:
            cursor.execute("""
                WITH candidate AS (
                    SELECT id FROM cx_studio_asset_deletions
                     WHERE attempts < 6 AND available_at <= NOW()
                       AND (status IN ('pending','failed') OR (status='processing' AND updated_at < NOW()-INTERVAL '15 minutes'))
                     ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1
                )
                UPDATE cx_studio_asset_deletions d SET status='processing',attempts=attempts+1,updated_at=NOW()
                  FROM candidate WHERE d.id=candidate.id
                RETURNING d.*,d.asset_id::text AS asset_id
            """)
            row = cursor.fetchone()
        self.connection.commit()
        return dict(row) if row else None

    def _safe_to_delete(self, asset_id):
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT a.status='discarded'
                   AND NOT EXISTS (
                       SELECT 1 FROM cx_studio_session_assets sa
                       JOIN cx_studio_sessions s ON s.id=sa.session_id
                       WHERE sa.asset_id=a.id
                         AND sa.role IN ('reference','base','accepted','final')
                         AND s.status NOT IN ('archived','cancelled')
                   )
                   AND NOT EXISTS (SELECT 1 FROM cx_studio_finalizations f WHERE f.final_asset_id=a.id)
                   AND NOT EXISTS (SELECT 1 FROM cx_studio_project_items p WHERE p.asset_url=a.asset_url)
                  AS safe
                  FROM cx_studio_assets a WHERE a.id=%s AND a.deleted_at IS NULL
            """, (asset_id,))
            row = cursor.fetchone()
        return bool(row and row.get("safe"))

    def _finish_deletion(self, ident, asset_id):
        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE cx_studio_assets SET status='deleted',deleted_at=NOW(),updated_at=NOW() WHERE id=%s", (asset_id,))
            cursor.execute("UPDATE cx_studio_asset_deletions SET status='deleted',deleted_at=NOW(),last_error='',updated_at=NOW() WHERE id=%s", (ident,))
        self.connection.commit()

    def _cancel_deletion(self, ident, reason):
        self._execute("UPDATE cx_studio_asset_deletions SET status='cancelled',last_error=%s,updated_at=NOW() WHERE id=%s", (str(reason)[:2000], ident))

    def _fail_deletion(self, ident, attempts, error):
        delay = min(86400, 300 * (2 ** max(0, int(attempts or 1) - 1)))
        self._execute("UPDATE cx_studio_asset_deletions SET status='failed',last_error=%s,available_at=NOW()+(%s*INTERVAL '1 second'),updated_at=NOW() WHERE id=%s", (str(error)[:2000], delay, ident))

    def _execute(self, sql, params):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
        self.connection.commit()

    @staticmethod
    def _send_email(payload):
        from ..services.cadu_product_emails import send_studio_session_saved, send_studio_work_completed
        if payload.pop("kind", "") == "session_saved":
            return send_studio_session_saved(**payload)
        return send_studio_work_completed(**payload)

    @staticmethod
    def _delete_asset(storage_key):
        from ..creative_modeling_storage import ClientLogoStorage
        return ClientLogoStorage().delete(storage_key)


def drain_studio_maintenance(connection, *, limit=10, email_sender=None, asset_delete=None, base_url=""):
    return PostgresStudioMaintenance(
        connection, email_sender=email_sender, asset_delete=asset_delete, base_url=base_url,
    ).drain(limit=limit)
