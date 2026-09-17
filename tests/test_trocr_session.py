"""Sessão do Trocr: histórico, still autenticado e CSRF. Sem Ads/Camadas."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Blueprint, Flask

from aicentralv2.creative_format_lab.service import FormatLabService
from aicentralv2.creative_format_lab.swap_session import TrocrStore, published_still_url
from aicentralv2.creative_format_lab.video_script import build_video_script
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
        empty = lab.save_swap_history(
            {
                "client_id": 10,
                "reset": True,
                "revision": dropped["revision"],
                "versions": [],
            },
            user_id=7,
        )
        self.assertEqual(empty["versions"], [])
        self.assertGreaterEqual(len(empty.get("runs") or []), 1)
        previous = next((item for item in empty["runs"] if item.get("version_count")), None)
        self.assertIsNotNone(previous)
        reopened = lab.load_swap_history({"client_id": 10, "run_id": previous["run_id"]}, user_id=7)
        self.assertEqual([item["id"] for item in reopened["versions"]], ["v1", "v2"])

    def test_nova_troca_nao_apaga_run_anterior(self):
        class _MemStorage:
            def __init__(self):
                self.sessions = {}

            def save_trocr_still(self, encoded, output_format="png"):
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
                "revision": 0,
                "versions": [{"id": "v1", "name": "Original", "origin": "original", "image": png}],
            },
            user_id=7,
        )
        second = lab.save_swap_history(
            {
                "client_id": 10,
                "new_run": True,
                "reset": True,
                "revision": first["revision"],
                "versions": [],
            },
            user_id=7,
        )
        self.assertEqual(second["versions"], [])
        self.assertNotEqual(second["run_id"], first["run_id"])
        self.assertTrue(any(item["run_id"] == first["run_id"] for item in second["runs"]))

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

    def test_still_path_aceita_extensao_irma(self):
        with tempfile.TemporaryDirectory() as folder:
            name = "c86b3398268e48b9bcecadde5cb9ebfd.png"
            path = Path(folder) / name
            path.write_bytes(TINY_PNG)

            class _Storage:
                def load_trocr_still(self, filename):
                    return path if filename == name else None

                def load_generated_still(self, filename):
                    return None

            store = TrocrStore(Mock(storage=_Storage()), FakeRepository())
            self.assertEqual(store.still_path("c86b3398268e48b9bcecadde5cb9ebfd.jpg"), path)

    def test_biblioteca_achata_stills_e_filtra_video(self):
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

        modeling = CreativeModelingService(FakeRepository(), FakeGenerator(), storage=_MemStorage())
        lab = FormatLabService(modeling)
        png = "data:image/png;base64," + TINY_PNG.hex()
        first = lab.save_swap_history(
            {
                "client_id": 10,
                "revision": 0,
                "versions": [{"id": "v1", "name": "Original", "origin": "original", "image": png}],
            },
            user_id=7,
        )
        lab.save_swap_history(
            {
                "client_id": 10,
                "run_id": first["run_id"],
                "revision": first["revision"],
                "versions": [
                    {"id": "v1", "name": "Original", "origin": "original", "image": first["versions"][0]["image_url"]},
                    {
                        "id": "v2",
                        "name": "Animação",
                        "origin": "animate",
                        "media": "video",
                        "video_url": "/parametros/api/media/assets/asset_clip/content",
                    },
                ],
            },
            user_id=7,
        )
        stills = lab.load_swap_library({"client_id": 10, "media": "still"}, user_id=7)
        clips = lab.load_swap_library({"client_id": 10, "media": "video"}, user_id=7)
        self.assertEqual(len(stills["items"]), 1)
        self.assertEqual(stills["items"][0]["version_id"], "v1")
        self.assertEqual(len(clips["items"]), 1)
        self.assertEqual(clips["items"][0]["video_url"], "/parametros/api/media/assets/asset_clip/content")
        only_still = lab.load_swap_history({"client_id": 10, "run_id": first["run_id"], "media": "still"}, user_id=7)
        self.assertTrue(all(item.get("media") != "video" for item in only_still["versions"]))
        dropped = lab.save_swap_history(
            {
                "client_id": 10,
                "run_id": first["run_id"],
                "revision": only_still["revision"],
                "versions": [
                    {"id": "v1", "name": "Original", "origin": "original", "image": first["versions"][0]["image_url"]},
                ],
            },
            user_id=7,
        )
        self.assertTrue(any(item.get("media") == "video" for item in dropped["versions"]))
        from aicentralv2.creative_format_lab.video_script import build_video_script

        store = lab._trocr_store()
        with self.assertRaises(ValueError) as one:
            build_video_script(store, {"client_id": 10, "scene_ids": [stills["items"][0]["id"]]}, user_id=7)
        self.assertIn("2 a 30", str(one.exception))
        extra = lab.add_swap_library_still({"client_id": 10, "image": png, "name": "Cena 2"}, user_id=7)
        for ident, headline in ((stills["items"][0]["id"], "Oferta"), (extra["id"], "CTA")):
            item, _run = store.find_still({"client_id": 10}, ident, user_id=7)
            item["ocr"] = {"headline": headline, "cta": "Vai"}
        scripted = build_video_script(
            store,
            {"client_id": 10, "scene_ids": [stills["items"][0]["id"], extra["id"]], "duration": 8},
            user_id=7,
        )
        self.assertEqual(len(scripted["script"]["beats"]), 2)
        self.assertEqual(scripted["scenes"][0]["id"], stills["items"][0]["id"])
        self.assertEqual(scripted["scenes"][0]["headline"], "Oferta")

    def test_roteiro_rele_ocr_invalido_e_grava_na_peca(self):
        class _MemStorage:
            def __init__(self):
                self.sessions = {}

            def save_trocr_still(self, encoded, output_format="png"):
                return f"/parametros/api/format-lab/swap/still/{'a' * 32}.png"

            def save_trocr_session(self, key, data):
                self.sessions[key] = data

            def load_trocr_session(self, key):
                return self.sessions.get(key)

        modeling = CreativeModelingService(FakeRepository(), FakeGenerator(), storage=_MemStorage())
        lab = FormatLabService(modeling)
        png = "data:image/png;base64," + TINY_PNG.hex()
        first = lab.add_swap_library_still({"client_id": 10, "image": png, "name": "Cena 1", "new_piece": True}, user_id=7)
        second = lab.add_swap_library_still({"client_id": 10, "image": png, "name": "Cena 2", "new_piece": True}, user_id=7)
        store = lab._trocr_store()
        for ident in (first["id"], second["id"]):
            item, _run = store.find_still({"client_id": 10}, ident, user_id=7)
            item["ocr"] = {"status": "invalid", "error": "A leitura veio inválida.", "headline": ""}
            item["image_url"] = png
        reads = []

        def fake_text(messages, **_kwargs):
            blob = str(messages)
            if "Você escreve o roteiro" in blob:
                return {
                    "message": {
                        "content": (
                            '{"beats":['
                            f'{{"id":"{first["id"]}","purpose":"hook","visual":"500 MEGA","motion":"Zoom","hold":"Preço","spoken":""}},'
                            f'{{"id":"{second["id"]}","purpose":"end","visual":"500 MEGA","motion":"Hold","hold":"CTA","spoken":""}}'
                            "]}"
                        )
                    }
                }
            reads.append(1)
            return {"message": {"content": '{"headline":"500 MEGA","cta":"Monte o seu","price":"R$ 99"}'}}

        scripted = build_video_script(
            store,
            {"client_id": 10, "scene_ids": [first["id"], second["id"]], "duration": 8},
            user_id=7,
            text_callable=fake_text,
        )
        self.assertEqual(len(reads), 2)
        self.assertEqual(scripted["scenes"][0]["headline"], "500 MEGA")
        self.assertEqual(scripted["scenes"][0]["cta"], "Monte o seu")
        self.assertEqual(scripted["script"]["beats"][0]["visual"], "500 MEGA")
        self.assertEqual(scripted["warnings"], [])
        saved, _run = store.find_still({"client_id": 10}, first["id"], user_id=7)
        self.assertEqual(saved["ocr"]["headline"], "500 MEGA")
        self.assertEqual(saved["ocr"]["cta"], "Monte o seu")

        again = build_video_script(
            store,
            {"client_id": 10, "scene_ids": [first["id"], second["id"]], "duration": 8},
            user_id=7,
        )
        self.assertEqual(again["scenes"][0]["headline"], "500 MEGA")

        with self.assertRaises(ValueError) as failed:
            build_video_script(
                store,
                {"client_id": 10, "scene_ids": [first["id"], second["id"]], "force_ocr": True},
                user_id=7,
                text_callable=lambda *_a, **_k: {"message": {"content": "isso não é json"}},
            )
        self.assertIn("inválida", str(failed.exception).lower())

    def test_historico_mantem_video_sem_poster(self):
        class _MemStorage:
            def __init__(self):
                self.sessions = {}

            def save_trocr_session(self, key, data):
                self.sessions[key] = data

            def load_trocr_session(self, key):
                return self.sessions.get(key)

        modeling = CreativeModelingService(FakeRepository(), FakeGenerator(), storage=_MemStorage())
        lab = FormatLabService(modeling)
        saved = lab.save_swap_history(
            {
                "client_id": 10,
                "revision": 0,
                "versions": [{
                    "id": "v2",
                    "name": "Animação",
                    "origin": "animate",
                    "media": "video",
                    "video_url": "/parametros/api/media/assets/asset_clip/content",
                }],
            },
            user_id=7,
        )
        self.assertEqual(saved["versions"][0]["media"], "video")
        self.assertEqual(
            saved["versions"][0]["video_url"],
            "/parametros/api/media/assets/asset_clip/content",
        )

    def test_biblioteca_remove_tim_e_still_404(self):
        alive_name = "a" * 32 + ".png"
        dead_name = "d" * 32 + ".png"
        with tempfile.TemporaryDirectory() as folder:
            alive = Path(folder) / alive_name
            alive.write_bytes(TINY_PNG)

            class _Storage:
                def __init__(self):
                    self.sessions = {}

                def save_trocr_session(self, key, data):
                    self.sessions[key] = data

                def load_trocr_session(self, key):
                    return self.sessions.get(key)

                def load_trocr_still(self, filename):
                    return alive if filename == alive_name else None

                def load_generated_still(self, filename):
                    return None

            repo = FakeRepository()
            repo.get_client = lambda client_id: {
                "id": client_id,
                "name": "TIM" if int(client_id) == 32 else "Outra marca",
            }
            modeling = CreativeModelingService(repo, FakeGenerator(), storage=_Storage())
            lab = FormatLabService(modeling)
            store = lab._trocr_store()
            packed = {
                "schema": "runs-v1",
                "active_run_id": "r-keep",
                "runs": [
                    {
                        "run_id": "r-keep",
                        "client_id": 10,
                        "title": "Original · 16:9",
                        "versions": [{
                            "id": "v1",
                            "name": "Original",
                            "origin": "original",
                            "image_url": f"/parametros/api/format-lab/swap/still/{alive_name}",
                            "thumb_url": f"/parametros/api/format-lab/swap/still/{alive_name}",
                        }],
                    },
                    {
                        "run_id": "r-tim",
                        "client_id": 10,
                        "title": "TIM Black · 16:9",
                        "versions": [{
                            "id": "v1",
                            "name": "TIM Black",
                            "origin": "original",
                            "ocr": {"headline": "TIM Black", "logo_text": "TIM"},
                            "image_url": f"/parametros/api/format-lab/swap/still/{alive_name}",
                            "thumb_url": f"/parametros/api/format-lab/swap/still/{alive_name}",
                        }],
                    },
                    {
                        "run_id": "r-dead",
                        "client_id": 10,
                        "title": "Peça sumida · 16:9",
                        "versions": [{
                            "id": "v1",
                            "name": "Original",
                            "origin": "original",
                            "image_url": f"/parametros/api/format-lab/swap/still/{dead_name}",
                            "thumb_url": f"/parametros/api/format-lab/swap/still/{dead_name}",
                        }],
                    },
                    {
                        "run_id": "r-foreign",
                        "client_id": 32,
                        "title": "De outra marca · 16:9",
                        "versions": [{
                            "id": "v1",
                            "name": "Original",
                            "origin": "original",
                            "image_url": f"/parametros/api/format-lab/swap/still/{alive_name}",
                            "thumb_url": f"/parametros/api/format-lab/swap/still/{alive_name}",
                        }],
                    },
                ],
            }
            store.write("client-10", packed, 10)
            store.write("client-32", {
                "schema": "runs-v1",
                "active_run_id": "r-tim32",
                "runs": [{
                    "run_id": "r-tim32",
                    "client_id": 32,
                    "title": "TIM Black · 16:9",
                    "versions": [{
                        "id": "v1",
                        "name": "TIM Black",
                        "origin": "original",
                        "ocr": {"headline": "TIM Black", "logo_text": "TIM"},
                        "image_url": f"/parametros/api/format-lab/swap/still/{alive_name}",
                        "thumb_url": f"/parametros/api/format-lab/swap/still/{alive_name}",
                    }],
                }],
            }, 32)
            items = lab.load_swap_library({"client_id": 10, "media": "still"}, user_id=7)
            ids = {item["run_id"] for item in items["items"]}
            self.assertEqual(ids, {"r-keep", "r-dead"})
            dead = next(item for item in items["items"] if item["run_id"] == "r-dead")
            self.assertTrue(dead["broken"])
            purged = lab.remove_swap_library_items(
                {"client_id": 10, "broken": True, "media": "still"},
                user_id=7,
            )
            self.assertEqual(purged["removed"], 1)
            self.assertEqual({item["run_id"] for item in purged["items"]}, {"r-keep"})
            gone = lab.remove_swap_library_items(
                {"client_id": 10, "id": "r-keep:v1", "media": "still"},
                user_id=7,
            )
            self.assertEqual(gone["removed"], 1)
            self.assertEqual(gone["items"], [])
            tim = lab.load_swap_library({"client_id": 32, "media": "still"}, user_id=7)
            self.assertEqual([item["run_id"] for item in tim["items"]], ["r-tim32"])

    def test_persist_still_normaliza_url_absoluta(self):
        store = TrocrStore(Mock(storage=Mock()), FakeRepository())
        url = "https://ai.centralcomm.media/parametros/api/format-lab/swap/still/c86b3398268e48b9bcecadde5cb9ebfd.jpg"
        self.assertEqual(
            store.persist_still(url),
            "/parametros/api/format-lab/swap/still/c86b3398268e48b9bcecadde5cb9ebfd.jpg",
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

    def test_still_autenticado_vira_data_url_para_ocr(self):
        with tempfile.TemporaryDirectory() as folder:
            name = "c" * 32 + ".png"
            path = Path(folder) / name
            path.write_bytes(TINY_PNG)

            class _Storage:
                def load_trocr_still(self, filename):
                    return path if filename == name else None

            captured = {}

            def fake_text(messages, **_kwargs):
                captured["url"] = messages[1]["content"][1]["image_url"]["url"]
                return {"message": {"content": '{"headline":"500 MEGA","cta":"Vai"}'}}

            generator = type("G", (), {"text_callable": staticmethod(fake_text)})()
            modeling = CreativeModelingService(FakeRepository(), generator, storage=_Storage())
            lab = FormatLabService(modeling)
            result = lab.read_swap({"reference": f"/parametros/api/format-lab/swap/still/{name}"})
            self.assertTrue(captured["url"].startswith("data:image/png;base64,"))
            self.assertEqual(result["headline"], "500 MEGA")
            self.assertEqual(result["status"], "completed")


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

    def test_post_do_historico_aceita_token_da_pagina_anterior(self):
        """An editor already open must remain usable after a CSRF token migration."""
        with self.client.session_transaction() as session:
            session.pop("trocr_csrf_token", None)
            session["studio_csrf_token"] = "studio-test-csrf"
        service = Mock()
        service.save_format_lab_swap_history.return_value = {"versions": [], "revision": 1}
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            saved = self.client.post(
                "/parametros/api/format-lab/swap/history",
                json={"client_id": 10, "versions": []},
                headers={"X-Trocr-CSRF-Token": "studio-test-csrf"},
            )
        self.assertEqual(saved.status_code, 200)
        service.save_format_lab_swap_history.assert_called_once()


class TrocrVideoProjectTest(unittest.TestCase):
    def _lab(self):
        class _MemStorage:
            def __init__(self):
                self.sessions = {}

            def save_trocr_still(self, encoded, output_format="png"):
                return f"/parametros/api/format-lab/swap/still/{'a' * 32}.png"

            def save_trocr_session(self, key, data):
                self.sessions[key] = data

            def load_trocr_session(self, key):
                return self.sessions.get(key)

        modeling = CreativeModelingService(FakeRepository(), FakeGenerator(), storage=_MemStorage())
        return FormatLabService(modeling)

    def test_video_project_persiste_e_sobrevive_ao_scrub(self):
        lab = self._lab()
        png = "data:image/png;base64," + TINY_PNG.hex()
        first = lab.add_swap_library_still(
            {"client_id": 10, "image": png, "name": "Cena 1", "new_piece": True},
            user_id=7,
        )
        second = lab.add_swap_library_still(
            {"client_id": 10, "image": png, "name": "Cena 2", "new_piece": True},
            user_id=7,
        )
        saved = lab.save_video_project(
            {
                "client_id": 10,
                "project": {
                    "name": "Pré 24",
                    "duration": 15,
                    "quality": "production",
                    "aspect_ratio": "9:16",
                    "scene_ids": [first["id"], second["id"]],
                    "script": {"beats": [{"id": first["id"], "purpose": "hook", "visual": "A", "motion": "m", "hold": "h", "spoken": "oi"}]},
                    "audio": {"mode": "voiceover", "script": "oi tudo bem aqui", "voice": "female", "pace": "fast"},
                    "motion": {"preset": "camera", "intensity": "moderate", "note": "zoom"},
                },
            },
            user_id=7,
        )
        self.assertEqual(saved["project"]["name"], "Pré 24")
        self.assertEqual(saved["project"]["duration"], 15)
        self.assertEqual(saved["project"]["audio"]["mode"], "voiceover")
        loaded = lab.load_video_project({"client_id": 10}, user_id=7)
        self.assertEqual(loaded["project"]["scene_ids"], [first["id"], second["id"]])
        self.assertEqual(loaded["project"]["motion"]["preset"], "camera")
        # Apagar peça não pode apagar o projeto da mesa.
        lab.remove_swap_library_items({"client_id": 10, "id": second["id"], "media": "still"}, user_id=7)
        again = lab.load_video_project({"client_id": 10}, user_id=7)
        self.assertEqual(again["project"]["name"], "Pré 24")
        self.assertEqual(again["project"]["audio"]["voice"], "female")

    def test_library_video_devolve_script_e_quality(self):
        lab = self._lab()
        png = "data:image/png;base64," + TINY_PNG.hex()
        first = lab.save_swap_history(
            {
                "client_id": 10,
                "active_id": "v1",
                "base_id": "v1",
                "revision": 0,
                "versions": [{"id": "v1", "name": "Original", "origin": "original", "image": png}],
            },
            user_id=7,
        )
        store = lab._trocr_store()
        store.persist_animate(
            {"client_id": 10, "run_id": first["run_id"], "base_id": "v1"},
            {
                "video_url": "/parametros/api/media/assets/asset_clip/content",
                "poster_url": "/parametros/api/media/assets/asset_poster/content",
                "image_url": "/parametros/api/media/assets/asset_poster/content",
                "job_id": "anim_restore",
                "duration": 8,
                "quality": "draft",
                "has_audio": True,
                "voiceover_script": "Recarregue trinta reais agora mesmo.",
                "storyboard_ids": ["v1", "v2"],
                "script": {"beats": [{"id": "v1", "purpose": "hook", "visual": "A", "motion": "m", "hold": "h", "spoken": ""}]},
            },
            user_id=7,
        )
        clips = lab.load_swap_library({"client_id": 10, "media": "video"}, user_id=7)
        self.assertEqual(len(clips["items"]), 1)
        clip = clips["items"][0]
        self.assertEqual(clip["quality"], "draft")
        self.assertTrue(clip["has_audio"])
        self.assertEqual(clip["voiceover_script"], "Recarregue trinta reais agora mesmo.")
        self.assertEqual(clip["script"]["beats"][0]["id"], "v1")
        self.assertEqual(clip["storyboard_ids"], ["v1", "v2"])


if __name__ == "__main__":
    unittest.main()
