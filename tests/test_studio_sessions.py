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
    studio_usage_summary,
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

    def test_all_scope_groups_project_work_and_only_the_users_free_sessions(self):
        personal = self.repo.create(31, 7, {"studio_type": "create", "title": "Livre"})
        project = self.repo.create(31, 8, {
            "studio_type": "edit", "title": "Campanha", "project_id": "project-1",
        })
        self.repo.create(31, 8, {"studio_type": "create", "title": "Livre de outra pessoa"})
        visible = self.repo.listing(31, 7, include_all=True)
        self.assertEqual({item["id"] for item in visible}, {personal["id"], project["id"]})

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
        self.assertEqual(metrics["estimated_manual_minutes"], 65)
        self.assertEqual(metrics["estimated_minutes_saved"], 55)

    def test_usage_summary_comes_from_charged_root_chain_rows(self):
        class Cursor:
            def __init__(self):
                self.sqls = []
                self.params_list = []

            def execute(self, sql, params):
                self.sql = sql
                self.params = params
                self.sqls.append(sql)
                self.params_list.append(params)

            def fetchone(self):
                if "cadu_credit_packages" in self.sql:
                    return {"name": "Pacote 100", "credits": 100, "price": "800.00"}
                return {"provider_tokens": 1200, "charged_credits": 17200, "internal_cost_usd": "0.172"}

        cursor = Cursor()
        summary = studio_usage_summary(cursor, "root-1", 7)

        self.assertTrue(any("metadata->>'studio_root_session_id'" in sql for sql in cursor.sqls))
        self.assertIn((7, "root-1"), cursor.params_list)
        self.assertEqual(summary, {
            "provider_tokens": 1200,
            "charged_credits": 17200,
            "internal_cost_usd": "0.172000",
            "sale_price_per_credit_brl": "8.000000",
            "sale_package_name": "Pacote 100",
        })

    def test_generated_attempt_counts_once_in_final_metrics(self):
        created = self.repo.create(31, 7, {"studio_type": "create", "title": "Campanha"})
        attempt = {
            "role": "attempt", "asset_url": "/media/generated.png", "source_type": "studio-create",
            "source_id": "node-1", "metadata": {"origin": "generation"},
        }
        first = self.repo.accept(31, 7, created["id"], attempt)
        self.repo.accept(31, 7, created["id"], attempt)
        accepted = self.repo.accept(31, 7, created["id"], {
            "role": "accepted", "asset_id": first["assets"][0]["id"],
        })
        result = self.repo.finalize(31, 7, created["id"], {"active_seconds": 60})
        self.assertEqual(accepted["status"], "ready")
        self.assertEqual(result["finalization"]["generation_count"], 1)

    def test_trocr_attempt_counts_as_one_edit_in_final_metrics(self):
        created = self.repo.create(31, 7, {"studio_type": "edit", "title": "Ajuste"})
        attempt = {
            "role": "attempt", "asset_url": "/media/edited.png", "source_type": "trocr",
            "source_id": "run-1:v2", "metadata": {"origin": "trocr-edit"},
        }
        first = self.repo.accept(31, 7, created["id"], attempt)
        self.repo.accept(31, 7, created["id"], attempt)
        self.repo.accept(31, 7, created["id"], {
            "role": "accepted", "asset_id": first["assets"][0]["id"],
        })
        result = self.repo.finalize(31, 7, created["id"], {"active_seconds": 60})
        self.assertEqual(result["finalization"]["edit_count"], 1)
        self.assertEqual(result["finalization"]["generation_count"], 0)

    def test_final_email_metrics_cover_the_entire_root_chain(self):
        created = self.repo.create(31, 7, {"studio_type": "create", "title": "Campanha"})
        generated = self.repo.accept(31, 7, created["id"], {
            "role": "attempt", "asset_url": "/media/generated.png", "source_id": "generation-1",
            "metadata": {"origin": "generation"},
        })
        self.repo.accept(31, 7, created["id"], {
            "role": "accepted", "asset_id": generated["assets"][0]["id"],
        })
        editing = self.repo.handoff(31, 7, created["id"], {
            "request_id": "edit-1", "studio_type": "edit",
        })
        edited = self.repo.accept(31, 7, editing["id"], {
            "role": "attempt", "asset_url": "/media/edited.png", "source_id": "edit-version-1",
            "metadata": {"origin": "trocr-edit"},
        })
        self.repo.accept(31, 7, editing["id"], {
            "role": "accepted", "asset_id": edited["assets"][-1]["id"],
        })

        result = self.repo.finalize(31, 7, editing["id"], {"active_seconds": 60})

        self.assertEqual(result["finalization"]["generation_count"], 1)
        self.assertEqual(result["finalization"]["edit_count"], 1)
        self.assertEqual(result["finalization"]["handoff_count"], 1)

    def test_discard_is_marked_for_delayed_deletion_and_restore_cancels_it(self):
        self.repo = LocalSessionRepository(self.root, retention_seconds=0)
        created = self.repo.create(31, 7, {"studio_type": "create"})
        attempt = self.repo.accept(31, 7, created["id"], {
            "role": "attempt", "asset_url": "/static/uploads/creative_generated/old.png",
            "source_id": "old-version",
        })
        asset_id = attempt["assets"][0]["id"]
        self.repo.discard(31, 7, created["id"], asset_id)
        with sqlite3.connect(self.repo.path) as db:
            queued = db.execute("SELECT storage_key,status FROM deletions WHERE asset_id=?", (asset_id,)).fetchone()
            self.assertEqual(queued, ("/static/uploads/creative_generated/old.png", "pending"))
        self.repo.discard(31, 7, created["id"], asset_id, restore=True)
        with sqlite3.connect(self.repo.path) as db:
            self.assertEqual(db.execute("SELECT status FROM deletions WHERE asset_id=?", (asset_id,)).fetchone()[0], "cancelled")

    def test_finalize_queues_only_unselected_attempts_for_cleanup(self):
        self.repo = LocalSessionRepository(self.root, retention_seconds=0)
        created = self.repo.create(31, 7, {"studio_type": "create", "title": "Campanha"})
        unused = self.repo.accept(31, 7, created["id"], {
            "role": "attempt", "asset_url": "/static/uploads/creative_generated/unused.png",
            "source_id": "unused", "metadata": {"origin": "generation"},
        })
        previous = self.repo.accept(31, 7, created["id"], {
            "role": "attempt", "asset_url": "/static/uploads/creative_generated/approved.png",
            "source_id": "approved", "metadata": {"origin": "generation"},
        })
        approved_asset = next(asset for asset in previous["assets"] if asset["source_id"] == "approved")
        self.repo.accept(31, 7, created["id"], {"role": "accepted", "asset_id": approved_asset["id"]})
        final = self.repo.accept(31, 7, created["id"], {
            "role": "accepted", "asset_url": "/static/uploads/creative_generated/final.png",
            "source_id": "final",
        })
        self.repo.finalize(31, 7, created["id"], {})
        unused_asset = next(asset for asset in unused["assets"] if asset["source_id"] == "unused")
        with sqlite3.connect(self.repo.path) as db:
            self.assertEqual(db.execute("SELECT status FROM assets WHERE id=?", (unused_asset["id"],)).fetchone()[0], "discarded")
            self.assertEqual(db.execute("SELECT status FROM deletions WHERE asset_id=?", (unused_asset["id"],)).fetchone()[0], "pending")
            self.assertEqual(db.execute("SELECT status FROM assets WHERE id=?", (approved_asset["id"],)).fetchone()[0], "accepted")
            self.assertEqual(db.execute("SELECT status FROM assets WHERE id=?", (final["active_asset_id"],)).fetchone()[0], "final")


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
                project_session = client.post(base, json={
                    "studio_type": "edit", "title": "Projeto", "project_id": "project-1",
                }, headers=headers)
                self.assertEqual(project_session.status_code, 200, project_session.json)
                listing = client.get(f"{base}?client_id=31&scope=all", headers=headers)
                self.assertEqual(listing.status_code, 200, listing.json)
                self.assertEqual(len(listing.json["data"]["items"]), 2)
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


def test_creation_editor_groups_free_and_project_sessions_and_switches_context():
    root = Path(__file__).resolve().parents[1]
    source = (root / "aicentralv2" / "static" / "js" / "mc-studio-create.js").read_text(encoding="utf-8")
    assert "scope:'all'" in source
    assert 'optgroup label="Sessões livres"' in source
    assert 'optgroup label="Projeto ·' in source
    assert "pendingSessionId" in source
    assert "projectSelect.dispatchEvent(new Event('change'" in source
    assert "summary.studio_type !== 'create'" in source
    assert "target.searchParams.set('studio_session_id'" in source
