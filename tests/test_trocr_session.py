"""Sessão do Trocr: histórico, still autenticado e CSRF. Sem Ads/Camadas."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Blueprint, Flask

from aicentralv2.creative_format_lab.service import FormatLabService
from aicentralv2.creative_format_lab.swap_session import TrocrStore, published_still_url
from aicentralv2.creative_modeling_repository import CreativeConflictError, CreativeNotFoundError
from aicentralv2.creative_modeling_routes import register_creative_modeling_routes
from aicentralv2.creative_modeling_service import CreativeModelingService
from tests.test_creative_format_lab import TINY_PNG
from tests.test_modelagem_criativos import FakeGenerator, FakeRepository


class TrocrSessionStoreTest(unittest.TestCase):
    def test_historico_trava_original_cas_e_still_privado(self):
        class _MemStorage:
            def __init__(self):
                self.n = 0
                self.sessions = {}

            def save_trocr_still(self, encoded, output_format="png"):
                self.n += 1
                return f"/parametros/api/format-lab/swap/still/{'a' * 32}.png"

            def save_trocr_session(self, key, data):
                self.sessions[key] = data

            def load_trocr_session(self, key):
                return self.sessions.get(key)

        repository = FakeRepository()
        modeling = CreativeModelingService(repository, FakeGenerator(), storage=_MemStorage())
        lab = FormatLabService(modeling)
        png = "data:image/png;base64," + TINY_PNG.hex()
        first = lab.save_swap_history(
            {
                "client_id": 10,
                "active_id": "v1",
                "base_id": "v1",
                "revision": 0,
                "versions": [
                    {"id": "v1", "name": "Original", "origin": "original", "image": png},
                ],
            },
            user_id=7,
        )
        self.assertEqual(first["revision"], 1)
        self.assertTrue(first["versions"][0]["image_url"].startswith("/parametros/api/format-lab/swap/still/"))
        original = first["versions"][0]["image_url"]
        dropped = lab.save_swap_history(
            {
                "client_id": 10,
                "active_id": "v2",
                "base_id": "v1",
                "revision": 1,
                "versions": [
                    {
                        "id": "v2",
                        "name": "Tipo na foto",
                        "origin": "typeset",
                        "parent_id": "v1",
                        "image": png,
                    },
                ],
            },
            user_id=7,
        )
        self.assertEqual([item["id"] for item in dropped["versions"]], ["v1", "v2"])
        self.assertEqual(dropped["versions"][0]["origin"], "original")
        self.assertEqual(dropped["versions"][0]["image_url"], original)
        self.assertEqual(dropped["versions"][1]["parent_id"], "v1")
        with self.assertRaises(CreativeConflictError) as raised:
            lab.save_swap_history(
                {
                    "client_id": 10,
                    "revision": 1,
                    "versions": [dropped["versions"][0]],
                },
                user_id=7,
            )
        self.assertIn("histórico mudou", str(raised.exception).lower())

    def test_still_legado_hex_vira_rota_autenticada(self):
        name = "a" * 32 + ".png"
        public = f"/static/uploads/creative_generated/{name}"
        self.assertEqual(
            published_still_url(public),
            f"/parametros/api/format-lab/swap/still/{name}",
        )
        self.assertTrue(
            published_still_url("/static/uploads/creative_generated/trocr1.png").startswith(
                "/static/uploads/"
            )
        )

    def test_still_path_cai_no_legado_gerado(self):
        with tempfile.TemporaryDirectory() as folder:
            name = "b" * 32 + ".png"
            path = Path(folder) / name
            path.write_bytes(TINY_PNG)

            class _Storage:
                def load_trocr_still(self, filename):
                    return None

                def load_generated_still(self, filename):
                    return path if filename == name else None

            store = TrocrStore(Mock(storage=_Storage()), FakeRepository())
            self.assertEqual(store.still_path(name), path)
            with self.assertRaises(CreativeNotFoundError):
                store.still_path("missing.png")


class TrocrSessionRoutesTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SECRET_KEY="trocr-session-test")
        bp = Blueprint("parametros_trocr_session", __name__, url_prefix="/parametros")
        register_creative_modeling_routes(bp)
        app.register_blueprint(bp)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
            session["trocr_csrf_token"] = "trocr-test-csrf"

    def test_post_do_historico_exige_csrf(self):
        service = Mock()
        service.load_format_lab_swap_history.return_value = {"versions": [], "revision": 0}
        service.save_format_lab_swap_history.return_value = {"versions": [], "revision": 1}
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            blocked = self.client.post(
                "/parametros/api/format-lab/swap/history",
                json={"client_id": 10, "versions": []},
            )
            saved = self.client.post(
                "/parametros/api/format-lab/swap/history",
                json={"client_id": 10, "versions": []},
                headers={"X-Trocr-CSRF-Token": "trocr-test-csrf"},
            )
            listed = self.client.get("/parametros/api/format-lab/swap/history?client_id=10")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(listed.status_code, 200)
        service.save_format_lab_swap_history.assert_called_once()


if __name__ == "__main__":
    unittest.main()
