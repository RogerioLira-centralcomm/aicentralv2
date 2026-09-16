import io
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase, mock

from flask import Blueprint, Flask
from werkzeug.datastructures import FileStorage

from aicentralv2.creative_analyzer.processor import normalize_result
from aicentralv2.creative_analyzer.repository import legacy_item, merge_history
from aicentralv2.creative_analyzer.routes import register_api_routes, register_product_routes
from aicentralv2.creative_analyzer.service import AnalyzerService
from aicentralv2.creative_analyzer.storage import AnalyzerStorage
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

    def test_migration_is_additive(self):
        sql = (ROOT / "migrations" / "add_studio_creative_analyzer.sql").read_text()
        self.assertIn("CREATE TABLE IF NOT EXISTS", sql)
        self.assertNotIn("DROP TABLE", sql.upper())
        self.assertNotIn("DELETE FROM", sql.upper())
