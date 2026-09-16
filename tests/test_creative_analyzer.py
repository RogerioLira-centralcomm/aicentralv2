import io
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase, mock

from flask import Blueprint, Flask
from werkzeug.datastructures import FileStorage

from aicentralv2.creative_analyzer.processor import VideoCreativeAnalyzer, normalize_result
from aicentralv2.creative_analyzer.repository import legacy_item, merge_history, share_token_hash
from aicentralv2.creative_analyzer.routes import register_api_routes, register_product_routes
from aicentralv2.creative_analyzer.service import AnalyzerService
from aicentralv2.creative_analyzer.storage import AnalyzerStorage, four_frame_seconds
from aicentralv2.product_domains import product_url


ROOT = Path(__file__).resolve().parents[1]


class CreativeAnalyzerRepositoryTest(TestCase):
    def test_legacy_item_preserves_old_url_and_normalizes_old_scores(self):
        item = legacy_item(
            {
                "id": 19,
                "uuid": "6d71570e-959c-49de-b829-8ad201a71464",
                "arquivo_nome": "filme.mp4",
                "arquivo_tipo": "video/mp4",
                "analise_completa": '{"scores":{"geral":73},"classificacao":{"funil":"awareness"}}',
                "created_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
            },
            "https://cadu.centralcomm.media/",
        )
        self.assertEqual(item["source"], "legacy")
        self.assertEqual(item["media_type"], "video")
        self.assertEqual(item["score"], 73)
        self.assertEqual(item["funnel"], "awareness")
        self.assertEqual(
            item["result_url"],
            "https://cadu.centralcomm.media/creative-analyzer/6d71570e-959c-49de-b829-8ad201a71464",
        )
        self.assertTrue(item["opens_legacy"])

    def test_history_merges_sources_before_pagination(self):
        legacy = [{"id": 1, "arquivo_nome": "antigo.png", "created_at": "2026-01-01T00:00:00"}]
        studio = [{"id": 2, "public_id": "new", "original_name": "novo.png", "created_at": "2026-02-01T00:00:00"}]
        items, next_offset = merge_history(legacy, studio, "https://cadu.example", 1, 0)
        self.assertEqual(items[0]["source"], "studio")
        self.assertEqual(next_offset, 1)

    def test_result_normalization_clamps_provider_scores(self):
        result = normalize_result(
            {"texts": {"all": ["Oferta"]}, "attention_sequence": [{"order": 1, "element": "Oferta"}]},
            {
                "score": {"geral": 140, "clareza": -2},
                "attention_analysis": {"attention_score": 61, "visual_hierarchy": {}},
                "channels": {"instagram_feed": {"score": 14}},
            },
        )
        self.assertEqual(result["score"]["geral"], 100)
        self.assertEqual(result["score"]["clareza"], 0)
        self.assertEqual(result["channels"]["instagram_feed"]["score"], 10)
        self.assertEqual(result["attention_analysis"]["visual_hierarchy"]["sequence"][0]["element"], "Oferta")

    def test_public_share_stores_only_a_one_way_token_digest(self):
        token = "Pp6r9vnYHgX0kcdrGg5eZV5x90WT6bT0JxJv2G0g-RY"
        digest = share_token_hash(token)
        self.assertNotEqual(digest, token)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, share_token_hash(token))


class CreativeAnalyzerImageTest(TestCase):
    @staticmethod
    def image_upload():
        from PIL import Image

        stream = io.BytesIO()
        Image.new("RGB", (120, 80), "#245f55").save(stream, format="PNG")
        stream.seek(0)
        return FileStorage(stream=stream, filename="peca.png", content_type="image/png")

    def test_private_storage_checks_pixels_and_creates_thumbnail(self):
        with tempfile.TemporaryDirectory() as folder:
            stored = AnalyzerStorage(folder).save_image("safe-id", self.image_upload())
            self.assertEqual(stored["mime_type"], "image/png")
            self.assertEqual((stored["width"], stored["height"]), (120, 80))
            self.assertTrue(Path(stored["source_key"]).is_file())
            self.assertTrue(Path(stored["thumbnail_key"]).is_file())

    def test_service_persists_result_without_php(self):
        class Repository:
            def __init__(self):
                self.events = []

            def create_analysis(self, payload):
                self.events.append(("create", payload))
                return {"id": 3, **payload}

            def add_asset(self, analysis_id, payload):
                self.events.append(("asset", payload["kind"]))

            def start_run(self, *args):
                return 8

            def complete_analysis(self, public_id, result):
                self.events.append(("complete", result["score"]["geral"]))
                return {"public_id": public_id, "status": "complete", "result_json": result}

            def finish_run(self, *args, **kwargs):
                self.events.append(("run", args[1]))

            def fail_analysis(self, *args):
                raise AssertionError("não deveria falhar")

        analyzer = mock.Mock()
        analyzer.analyze.return_value = {
            "schema_version": "1.0", "classification": {}, "score": {"geral": 82},
            "technical": {"usage": {}},
        }
        repository = Repository()
        with tempfile.TemporaryDirectory() as folder:
            result = AnalyzerService(repository, AnalyzerStorage(folder), analyzer).analyze_image(
                self.image_upload(), user_id=7, client_id=174, context="Campanha"
            )
        self.assertEqual(result["status"], "complete")
        self.assertIn(("asset", "source"), repository.events)
        self.assertIn(("asset", "thumbnail"), repository.events)
        self.assertIn(("complete", 82), repository.events)

    def test_video_uses_exactly_four_backend_frames(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("FFmpeg indisponível")
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "input.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=#245f55:s=320x180:r=12",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "1.2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
                ],
                check=True, capture_output=True, timeout=30,
            )
            with source.open("rb") as handle:
                upload = FileStorage(stream=handle, filename="filme.mp4", content_type="video/mp4")
                saved = AnalyzerStorage(Path(folder) / "storage").save_video("video-id", upload)
            self.assertEqual(len(saved["frames"]), 4)
            self.assertTrue(saved["has_audio"])
            seconds = [frame["second"] for frame in saved["frames"]]
            self.assertEqual(len(four_frame_seconds(1.2)), 4)
            self.assertEqual(seconds, sorted(seconds))
            self.assertTrue(all(0 <= second <= saved["duration"] for second in seconds))
            self.assertTrue(all(Path(frame["storage_key"]).is_file() for frame in saved["frames"]))

    def test_video_processor_sends_four_frames_in_each_pass(self):
        calls = []

        def provider(messages, **kwargs):
            images = [part for part in messages[1]["content"] if part.get("type") == "image_url"]
            calls.append(len(images))
            if len(calls) == 1:
                content = {"texts": {}, "attention_sequence": [], "narrative": {}}
            else:
                content = {"score": {"geral": 70}, "video_metrics": {"hook_strength": 64}}
            return {"message": {"content": json.dumps(content)}, "model": "test-model", "usage": {}}

        frames = [{"position": index, "second": float(index), "data_url": "data:image/jpeg;base64,AA=="} for index in range(4)]
        result = VideoCreativeAnalyzer(provider).analyze(frames, technical={"has_audio": True})
        self.assertEqual(calls, [4, 4])
        self.assertEqual(result["video_metrics"]["hook_strength"], 64)
        self.assertEqual(result["technical"]["architecture"], "video_four_frames_two_pass")
        self.assertEqual(len(result["technical"]["frame_seconds"]), 4)


class CreativeAnalyzerRoutesTest(TestCase):
    def setUp(self):
        self.app = Flask(
            __name__,
            template_folder=str(ROOT / "aicentralv2" / "templates"),
            static_folder=str(ROOT / "aicentralv2" / "static"),
        )
        self.app.config.update(
            SECRET_KEY="test",
            TESTING=True,
            STUDIO_URL="https://studio.centralcomm.media",
            CADU_URL="https://cadu.centralcomm.media",
        )
        self.app.add_url_rule("/login", "login", lambda: "login")
        self.app.context_processor(lambda: {"product_url": product_url, "studio_url": lambda endpoint, **values: "/"})
        api = Blueprint("studio", __name__, url_prefix="/studio")
        product = Blueprint("studio_product", __name__)
        register_api_routes(api)
        register_product_routes(product)
        self.app.register_blueprint(api)
        self.app.register_blueprint(product)
        self.client = self.app.test_client()

    def login(self):
        with self.client.session_transaction(headers={"Host": "studio.centralcomm.media"}) as session:
            session.update(user_id=7, cliente_id=174, user_name="Apolo", trocr_csrf_token="csrf")

    def test_page_requires_login_and_enters_studio_navigation(self):
        self.assertEqual(self.client.get("/analyzer", headers={"Host": "studio.centralcomm.media"}).status_code, 302)
        self.login()
        response = self.client.get("/analyzer", headers={"Host": "studio.centralcomm.media"})
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Creative Analyzer", html)
        self.assertIn('data-mc-page="analyzer"', html)

    def test_history_is_scoped_to_studio_client(self):
        self.login()
        with mock.patch("aicentralv2.creative_analyzer.routes._repository") as repository:
            repository.return_value.list_history.return_value = ([{"source": "legacy"}], None)
            response = self.client.get(
                "/studio/api/analyzer/history?client_id=999",
                headers={"Host": "studio.centralcomm.media"},
            )
        self.assertEqual(response.status_code, 200)
        repository.return_value.list_history.assert_called_once_with(7, 174, limit=24, offset=0)

    def test_projects_are_loaded_only_from_the_studio_client(self):
        self.login()
        with mock.patch("aicentralv2.creative_analyzer.routes._repository") as repository:
            repository.return_value.list_projects.return_value = [
                {"ref": "ci:project-1", "name": "Lançamento", "color": "#123456"}
            ]
            response = self.client.get(
                "/studio/api/analyzer/projects?client_id=999",
                headers={"Host": "studio.centralcomm.media"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"][0]["name"], "Lançamento")
        repository.return_value.list_projects.assert_called_once_with(174)

    def test_operational_status_exposes_only_scoped_aggregates(self):
        self.login()
        metrics = {"analyses_30d": 8, "complete_30d": 7, "failed_30d": 1, "average_duration_ms": 4200}
        with mock.patch("aicentralv2.creative_analyzer.routes._repository") as repository:
            repository.return_value.observability.return_value = metrics
            response = self.client.get(
                "/studio/api/analyzer/status?client_id=999",
                headers={"Host": "studio.centralcomm.media"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["metrics"], metrics)
        self.assertEqual(response.get_json()["legacy_mode"], "read_only")
        repository.return_value.observability.assert_called_once_with(174)

    def test_write_flag_pauses_new_processing_but_not_reads(self):
        self.login()
        self.app.config["CREATIVE_ANALYZER_WRITES_ENABLED"] = False
        with mock.patch("aicentralv2.creative_analyzer.routes.AnalyzerService") as service:
            response = self.client.post(
                "/studio/api/analyzer/analyses",
                data={"file": (io.BytesIO(b"not-used"), "piece.png")},
                headers={"Host": "studio.centralcomm.media", "X-Trocr-CSRF-Token": "csrf"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("histórico continua disponível", response.get_json()["error"])
        service.assert_not_called()

    def test_image_upload_requires_csrf(self):
        self.login()
        response = self.client.post(
            "/studio/api/analyzer/analyses",
            data={"file": (io.BytesIO(b"not-used"), "piece.png")},
            headers={"Host": "studio.centralcomm.media"},
        )
        self.assertEqual(response.status_code, 403)

    def test_image_upload_calls_native_service(self):
        self.login()
        completed = {
            "public_id": "6d71570e-959c-49de-b829-8ad201a71464",
            "original_name": "piece.png",
            "status": "complete",
            "result_json": {"score": {"geral": 80}},
        }
        with mock.patch("aicentralv2.creative_analyzer.routes.AnalyzerService") as service:
            service.return_value.analyze_image.return_value = completed
            response = self.client.post(
                "/studio/api/analyzer/analyses",
                data={"file": (io.BytesIO(b"not-used"), "piece.png"), "context": "Lançamento"},
                headers={"Host": "studio.centralcomm.media", "X-Trocr-CSRF-Token": "csrf"},
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["analysis"]["status"], "complete")
        service.return_value.analyze_image.assert_called_once()

    def test_upload_rejects_project_from_another_organization(self):
        self.login()
        with mock.patch("aicentralv2.creative_analyzer.routes._repository") as repository, \
             mock.patch("aicentralv2.creative_analyzer.routes.AnalyzerService") as service:
            repository.return_value.project_exists.return_value = False
            response = self.client.post(
                "/studio/api/analyzer/analyses",
                data={"file": (io.BytesIO(b"not-used"), "piece.png"), "project_ref": "ci:foreign"},
                headers={"Host": "studio.centralcomm.media", "X-Trocr-CSRF-Token": "csrf"},
            )
        self.assertEqual(response.status_code, 400)
        repository.return_value.project_exists.assert_called_once_with("ci:foreign", 174)
        service.assert_not_called()

    def test_upload_persists_studio_brand_and_valid_project_refs(self):
        self.login()
        completed = {
            "public_id": "6d71570e-959c-49de-b829-8ad201a71464",
            "original_name": "piece.png", "status": "complete", "result_json": {},
        }
        with mock.patch("aicentralv2.creative_analyzer.routes._repository") as repository, \
             mock.patch("aicentralv2.creative_analyzer.routes.AnalyzerService") as service:
            repository.return_value.project_exists.return_value = True
            service.return_value.analyze_image.return_value = completed
            response = self.client.post(
                "/studio/api/analyzer/analyses",
                data={"file": (io.BytesIO(b"not-used"), "piece.png"), "project_ref": "ci:project-1"},
                headers={"Host": "studio.centralcomm.media", "X-Trocr-CSRF-Token": "csrf"},
            )
        self.assertEqual(response.status_code, 201)
        kwargs = service.return_value.analyze_image.call_args.kwargs
        self.assertEqual(kwargs["client_id"], 174)
        self.assertEqual(kwargs["brand_ref"], "studio:174")
        self.assertEqual(kwargs["project_ref"], "ci:project-1")

    def test_video_upload_selects_backend_video_pipeline(self):
        self.login()
        completed = {
            "public_id": "6d71570e-959c-49de-b829-8ad201a71464",
            "original_name": "film.mp4", "media_type": "video", "status": "complete", "result_json": {},
        }
        with mock.patch("aicentralv2.creative_analyzer.routes.AnalyzerService") as service:
            service.return_value.analyze_video.return_value = completed
            response = self.client.post(
                "/studio/api/analyzer/analyses",
                data={"file": (io.BytesIO(b"not-used"), "film.mp4")},
                headers={"Host": "studio.centralcomm.media", "X-Trocr-CSRF-Token": "csrf"},
            )
        self.assertEqual(response.status_code, 201)
        service.return_value.analyze_video.assert_called_once()
        service.return_value.analyze_image.assert_not_called()

    def test_share_requires_csrf_and_uses_studio_client(self):
        self.login()
        analysis_id = "6d71570e-959c-49de-b829-8ad201a71464"
        path = f"/studio/api/analyzer/analyses/{analysis_id}/share"
        self.assertEqual(
            self.client.post(path, headers={"Host": "studio.centralcomm.media"}).status_code,
            403,
        )
        with mock.patch("aicentralv2.creative_analyzer.routes._repository") as repository:
            repository.return_value.create_share.return_value = {"token": "a" * 43}
            response = self.client.post(
                path,
                headers={"Host": "studio.centralcomm.media", "X-Trocr-CSRF-Token": "csrf"},
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["url"], f"https://studio.centralcomm.media/analyzer/public/{'a' * 43}")
        repository.return_value.create_share.assert_called_once_with(analysis_id, 174, 7)

    def test_public_report_is_anonymous_but_token_gated_and_not_indexed(self):
        token = "b" * 43
        row = {
            "public_id": "6d71570e-959c-49de-b829-8ad201a71464",
            "original_name": "filme.mp4",
            "media_type": "video",
            "result_json": {"score": {"geral": 84}},
        }
        with mock.patch("aicentralv2.creative_analyzer.routes._repository") as repository:
            repository.return_value.public_analysis.return_value = row
            response = self.client.get(
                f"/analyzer/public/{token}", headers={"Host": "studio.centralcomm.media"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("noindex,nofollow", response.get_data(as_text=True))
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")
        repository.return_value.public_analysis.assert_called_once_with(token)

    def test_share_can_be_revoked_for_the_studio_client(self):
        self.login()
        analysis_id = "6d71570e-959c-49de-b829-8ad201a71464"
        with mock.patch("aicentralv2.creative_analyzer.routes._repository") as repository:
            repository.return_value.revoke_share.return_value = True
            response = self.client.delete(
                f"/studio/api/analyzer/analyses/{analysis_id}/share",
                headers={"Host": "studio.centralcomm.media", "X-Trocr-CSRF-Token": "csrf"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"revoked": True})
        repository.return_value.revoke_share.assert_called_once_with(analysis_id, 174)

    def test_public_report_rejects_malformed_token_before_database(self):
        with mock.patch("aicentralv2.creative_analyzer.routes._repository") as repository:
            response = self.client.get(
                "/analyzer/public/curto", headers={"Host": "studio.centralcomm.media"}
            )
        self.assertEqual(response.status_code, 404)
        repository.assert_not_called()

    def test_migration_is_additive(self):
        sql = (ROOT / "migrations" / "add_studio_creative_analyzer.sql").read_text()
        self.assertIn("CREATE TABLE IF NOT EXISTS", sql)
        self.assertNotIn("DROP TABLE", sql.upper())
        self.assertNotIn("DELETE FROM", sql.upper())
