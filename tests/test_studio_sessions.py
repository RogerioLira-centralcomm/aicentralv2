import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Blueprint, Flask, jsonify, request

from aicentralv2.creative_media.studio_sessions import (
    LocalSessionRepository,
    SessionConflict,
    estimate_metrics,
)


class StudioSessionRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = LocalSessionRepository(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_free_session_is_private_and_save_uses_revision(self):
        created = self.repo.create(31, 7, {"studio_type": "create", "title": "Capa"})
        self.assertEqual(created["status"], "draft")
        self.assertEqual(len(self.repo.listing(31, 7)), 1)
        self.assertEqual(self.repo.listing(31, 8), [])
        saved = self.repo.save(31, 7, created["id"], {
            "expected_revision": 1,
            "status": "active",
            "original_prompt": "Corrija somente a hora",
            "optimized_prompt": "Correct only the time",
        })
        self.assertEqual(saved["revision"], 2)
        self.assertEqual(saved["original_prompt"], "Corrija somente a hora")
        with self.assertRaises(SessionConflict):
            self.repo.save(31, 7, created["id"], {"expected_revision": 1, "title": "Perdido"})

    def test_accepted_asset_is_the_base_and_handoff_is_idempotent(self):
        created = self.repo.create(31, 7, {"studio_type": "create", "title": "Capa"})
        ready = self.repo.accept(31, 7, created["id"], {
            "role": "accepted", "kind": "image", "source_type": "generation",
            "source_id": "request-1", "asset_url": "/media/final.png", "title": "Versão aprovada",
        })
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["active_asset_id"], ready["base_asset_id"])
        payload = {"request_id": "handoff-1", "studio_type": "edit"}
        first = self.repo.handoff(31, 7, created["id"], payload)
        second = self.repo.handoff(31, 7, created["id"], payload)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["parent_session_id"], created["id"])
        self.assertEqual(first["base_asset_id"], ready["base_asset_id"])

    def test_finalize_once_and_continue_without_second_email(self):
        created = self.repo.create(31, 7, {"studio_type": "edit", "title": "Ajuste final"})
        ready = self.repo.accept(31, 7, created["id"], {
            "role": "accepted", "kind": "image", "source_id": "edit-1",
            "asset_url": "/media/final.png",
        })
        first = self.repo.finalize(31, 7, created["id"], {
            "recipient_email": "user@example.com", "recipient_name": "Usuário", "active_seconds": 180,
        })
        replay = self.repo.finalize(31, 7, created["id"], {"recipient_email": "user@example.com"})
        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        self.assertTrue(first["session"]["read_only"])
        continued = self.repo.continue_session(31, 7, created["id"], {"studio_type": "edit"})
        self.assertEqual(continued["root_session_id"], created["id"])
        self.assertEqual(continued["status"], "active")
        with sqlite3.connect(self.repo.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 1)

    def test_active_asset_cannot_be_discarded(self):
        created = self.repo.create(31, 7, {"studio_type": "create"})
        ready = self.repo.accept(31, 7, created["id"], {
            "role": "accepted", "asset_url": "/media/final.png", "source_id": "final",
        })
        with self.assertRaisesRegex(ValueError, "ativa"):
            self.repo.discard(31, 7, created["id"], ready["active_asset_id"])

    def test_metrics_ignore_failures(self):
        metrics = estimate_metrics([
            {"event_type": "generation_completed"},
            {"event_type": "generation_failed"},
            {"event_type": "edit_completed"},
            {"event_type": "format_created"},
        ], active_seconds=600)
        self.assertEqual(metrics["generation"], 1)
        self.assertEqual(metrics["edit"], 1)
        self.assertEqual(metrics["format"], 1)
        self.assertEqual(metrics["estimated_minutes_saved"], 55)


class StudioSessionRouteTest(unittest.TestCase):
    def test_route_scope_csrf_conflict_and_authenticated_email(self):
        from aicentralv2.creative_media.studio import register_studio_routes

        with tempfile.TemporaryDirectory() as directory:
            app = Flask(__name__, instance_path=directory)
            app.secret_key = "test-only"
            app.config.update(TESTING=True, MEDIA_ROOT=directory)
            bp = Blueprint("studio_session_test", __name__)
            register_studio_routes(bp)
            app.register_blueprint(bp)
            client = app.test_client()
            base = "/api/format-lab/studio/sessions"
            self.assertEqual(client.get(base).status_code, 401)
            with client.session_transaction() as sess:
                sess.update(user_id=7, user_type="admin", cliente_id=31, user_email="real@example.com",
                            user_name="Pessoa", studio_csrf_token="token")

            def execute(fn):
                try:
                    return fn()
                except ValueError as error:
                    return jsonify(success=False, error=str(error)), 400

            http = (execute, lambda: request.get_json(), lambda data: jsonify(success=True, data=data), None)
            headers = {"X-Trocr-CSRF-Token": "token"}
            with patch("aicentralv2.creative_media.studio._http", return_value=http):
                self.assertEqual(client.post(base, json={"studio_type": "create"}).status_code, 403)
                created = client.post(base, json={"studio_type": "create", "title": "Peça"}, headers=headers)
                self.assertEqual(created.status_code, 200, created.json)
                ident = created.json["data"]["id"]
                saved = client.patch(f"{base}/{ident}", json={"expected_revision": 1, "status": "active"}, headers=headers)
                self.assertEqual(saved.status_code, 200, saved.json)
                conflict = client.patch(f"{base}/{ident}", json={"expected_revision": 1, "title": "Outra"}, headers=headers)
                self.assertEqual(conflict.status_code, 409, conflict.json)
                accepted = client.post(f"{base}/{ident}/accept", json={"asset_url": "/piece.png", "role": "accepted"}, headers=headers)
                self.assertEqual(accepted.status_code, 200, accepted.json)
                final = client.post(f"{base}/{ident}/finalize", json={"recipient_email": "attacker@example.com"}, headers=headers)
                self.assertEqual(final.status_code, 200, final.json)

            root = next(Path(directory).glob("creative_media/studio/*"))
            with sqlite3.connect(root / "studio-sessions.sqlite3") as db:
                self.assertEqual(db.execute("SELECT recipient_email FROM outbox").fetchone()[0], "real@example.com")


def test_session_schema_is_in_fresh_and_rollout_migrations():
    root = Path(__file__).resolve().parents[1]
    fresh = (root / "migrations" / "add_creative_media.sql").read_text(encoding="utf-8")
    rollout = (root / "migrations" / "add_studio_sessions.sql").read_text(encoding="utf-8")
    for table in (
        "cx_studio_assets", "cx_studio_sessions", "cx_studio_session_assets",
        "cx_studio_session_events", "cx_studio_finalizations", "cx_studio_delivery_outbox",
        "cx_studio_asset_deletions",
    ):
        assert table in fresh
        assert table in rollout
