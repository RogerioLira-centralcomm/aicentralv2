"""Camadas V2 — persistência, OCR completo e contratos HTTP."""

from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Blueprint, Flask
from werkzeug.datastructures import FileStorage

ROOT = Path(__file__).resolve().parents[1]
PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4+\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeRepository:
    def __init__(self):
        self.creatives = {}
        self.jobs = {}
        self.elements = {}
        self.scenes = {}
        self.collections = {}
        self.assets = {}
        self.generations = []
        self._pk = 1

    def ready(self):
        return self

    def create_creative(self, data):
        self._pk += 1
        row = {
            "id": self._pk,
            "warnings": [],
            "reading": {},
            **data,
        }
        self.creatives[row["public_id"]] = row
        return dict(row)

    def find_creative_by_sha(self, client_id, sha256):
        matches = [
            row for row in self.creatives.values()
            if row.get("sha256") == sha256 and (not client_id or row.get("client_id") == client_id)
        ]
        return dict(matches[-1]) if matches else None

    def get_creative(self, public_id):
        row = self.creatives.get(public_id)
        if not row:
            from aicentralv2.camadas.repositories import CamadasNotFoundError

            raise CamadasNotFoundError("Criativo não encontrado.")
        return dict(row)

    def update_creative(self, public_id, **fields):
        row = self.get_creative(public_id)
        row.update(fields)
        self.creatives[public_id] = row
        return dict(row)

    def create_job(self, creative_id, public_id=None):
        from aicentralv2.camadas.schemas import new_public_id

        job_id = public_id or new_public_id("job")
        row = {
            "id": self._pk + 10,
            "public_id": job_id,
            "creative_id": creative_id,
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "message": "Enviando original",
            "error": "",
            "creative_public_id": next(
                key for key, item in self.creatives.items() if item["id"] == creative_id
            ),
        }
        self.jobs[job_id] = row
        return dict(row)

    def get_job(self, public_id):
        row = self.jobs.get(public_id)
        if not row:
            from aicentralv2.camadas.repositories import CamadasNotFoundError

            raise CamadasNotFoundError("Job não encontrado.")
        return dict(row)

    def update_job(self, public_id, **fields):
        row = self.get_job(public_id)
        row.update(fields)
        self.jobs[public_id] = row
        return dict(row)

    def replace_elements(self, creative_pk, rows):
        from aicentralv2.camadas.schemas import new_public_id

        saved = []
        for item in rows or []:
            self._pk += 1
            row = {
                "id": self._pk,
                "public_id": new_public_id("element"),
                "creative_id": creative_pk,
                **item,
            }
            saved.append(row)
        self.elements[creative_pk] = saved
        return [dict(item) for item in saved]

    def list_elements(self, creative_pk):
        return [dict(item) for item in self.elements.get(creative_pk) or []]

    def get_element(self, public_id):
        from aicentralv2.camadas.repositories import CamadasNotFoundError

        for rows in self.elements.values():
            for item in rows:
                if item.get("public_id") == public_id:
                    creative = next(
                        row for row in self.creatives.values() if row["id"] == item["creative_id"]
                    )
                    return {**item, "creative_public_id": creative["public_id"]}
        raise CamadasNotFoundError("Elemento não encontrado.")

    def add_element(self, creative_pk, data):
        from aicentralv2.camadas.schemas import new_public_id

        self._pk += 1
        row = {
            "id": self._pk,
            "public_id": data.get("public_id") or new_public_id("element"),
            "creative_id": creative_pk,
            **data,
        }
        self.elements.setdefault(creative_pk, []).append(row)
        return dict(row)

    def update_element(self, public_id, **fields):
        for rows in self.elements.values():
            for item in rows:
                if item.get("public_id") == public_id:
                    item.update(fields)
                    return dict(item)
        from aicentralv2.camadas.repositories import CamadasNotFoundError

        raise CamadasNotFoundError("Elemento não encontrado.")

    def save_mask(self, element_pk, data):
        return {"element_id": element_pk, **data}

    def upsert_scene(self, creative_pk, document, version=1):
        row = {"creative_id": creative_pk, "version": version, "document": document}
        self.scenes[creative_pk] = row
        return dict(row)

    def get_scene(self, creative_pk):
        row = self.scenes.get(creative_pk)
        return dict(row) if row else None

    def update_scene_if_version(self, creative_pk, expected_version, document):
        from aicentralv2.camadas.repositories import CamadasConflictError, CamadasNotFoundError

        row = self.scenes.get(creative_pk)
        if not row:
            raise CamadasNotFoundError("Cena não encontrada.")
        if int(row["version"]) != int(expected_version):
            raise CamadasConflictError("A cena mudou. Recarregue e tente de novo.")
        next_row = {
            "creative_id": creative_pk,
            "version": int(expected_version) + 1,
            "document": document,
        }
        self.scenes[creative_pk] = next_row
        return dict(next_row)

    def list_collections(self, client_id):
        return [
            dict(item)
            for item in self.collections.values()
            if item.get("client_id") == client_id
        ]

    def get_collection(self, public_id):
        row = self.collections.get(public_id)
        return dict(row) if row else None

    def get_collection_by_pk(self, collection_pk):
        for item in self.collections.values():
            if item.get("id") == collection_pk:
                return dict(item)
        return None

    def find_collection_by_name(self, client_id, name):
        wanted = str(name or "").strip().lower()
        for item in self.collections.values():
            if item.get("client_id") == client_id and str(item.get("name") or "").lower() == wanted:
                return dict(item)
        return None

    def create_collection(self, data):
        from aicentralv2.camadas.schemas import new_public_id

        self._pk += 1
        row = {
            "id": self._pk,
            "public_id": data.get("public_id") or new_public_id("collection"),
            "client_id": data.get("client_id"),
            "name": data.get("name") or "Geral",
            "cover_thumb_path": "",
            "is_default": False,
        }
        self.collections[row["public_id"]] = row
        return dict(row)

    def update_collection(self, public_id, **fields):
        row = self.collections.get(public_id)
        if not row:
            return None
        row.update(fields)
        return dict(row)

    def delete_element(self, public_id):
        for key, rows in list(self.elements.items()):
            self.elements[key] = [item for item in rows if item.get("public_id") != public_id]

    def create_asset(self, data):
        from aicentralv2.camadas.schemas import new_public_id

        self._pk += 1
        row = {
            "id": self._pk,
            "public_id": data.get("public_id") or new_public_id("asset"),
            **data,
        }
        self.assets[row["public_id"]] = row
        return dict(row)

    def create_generation(self, data):
        from aicentralv2.camadas.schemas import new_public_id

        self._pk += 1
        row = {
            "id": self._pk,
            "public_id": data.get("public_id") or new_public_id("generation"),
            **data,
        }
        self.generations.append(row)
        return dict(row)

    def get_asset(self, public_id):
        row = self.assets.get(public_id)
        if not row:
            from aicentralv2.camadas.repositories import CamadasNotFoundError

            raise CamadasNotFoundError("Ativo não encontrado.")
        return dict(row)

    def find_asset_by_sha(self, client_id, sha256):
        for item in self.assets.values():
            if item.get("client_id") == client_id and item.get("sha256") == sha256:
                return dict(item)
        return None

    def list_assets(self, client_id, collection_pk=None):
        rows = []
        for item in self.assets.values():
            if item.get("client_id") != client_id:
                continue
            if collection_pk and item.get("collection_id") != collection_pk:
                continue
            collection = self.get_collection_by_pk(item.get("collection_id")) or {}
            rows.append({
                **item,
                "collection_public_id": collection.get("public_id") or "",
                "collection_name": collection.get("name") or "",
            })
        return rows


class FakeStorage:
    def save_original(self, file_storage, creative_id):
        return {
            "asset_path": f"/static/uploads/camadas/{creative_id}/original.png",
            "original_name": "still.png",
            "mime_type": "image/png",
            "sha256": "abc",
            "width": 480,
            "height": 180,
        }

    def as_data_url(self, public_path):
        return "data:image/png;base64,aaa"

    def sha256_of(self, public_path):
        import hashlib

        return hashlib.sha256(str(public_path or "x").encode()).hexdigest()

    def save_png(self, creative_id, name, image):
        return f"/static/uploads/camadas/{creative_id}/{name}.png"

    def save_thumb(self, creative_id, name, image, size=96):
        return f"/static/uploads/camadas/{creative_id}/{name}-th.png"

    def save_text_thumb(self, creative_id, name, text, size=96):
        return f"/static/uploads/camadas/{creative_id}/{name}-th.png"


def _still_file(name="still.png"):
    return FileStorage(stream=io.BytesIO(PNG_1PX), filename=name, content_type="image/png")


class CamadasV2ContractTest(unittest.TestCase):
    def test_flag_desligada_por_padrao(self):
        from aicentralv2.config import Config

        self.assertFalse(Config.CAMADAS_V2_ENABLED)

    def test_public_id_e_injections(self):
        from aicentralv2.camadas.schemas import is_public_id, new_public_id, strip_client_injections

        creative = new_public_id("creative")
        self.assertTrue(is_public_id(creative, "creative"))
        self.assertTrue(creative.startswith("crt_"))
        clean = strip_client_injections({
            "image": "x",
            "predictor": "malicioso",
            "text_callable": "malicioso",
            "image_callable": "malicioso",
        })
        self.assertEqual(clean, {"image": "x"})

    def test_migration_tem_as_tabelas(self):
        sql = (ROOT / "migrations" / "add_camadas_v2.sql").read_text(encoding="utf-8")
        for table in (
            "cx_camadas_creatives",
            "cx_camadas_jobs",
            "cx_camadas_elements",
            "cx_camadas_masks",
            "cx_camadas_scenes",
            "cx_camadas_collections",
            "cx_camadas_assets",
            "cx_camadas_generations",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", sql)
        self.assertIn("uq_cx_camadas_assets_client_sha", sql)
        workspace = (ROOT / "migrations" / "add_camadas_v2_workspace.sql").read_text(encoding="utf-8")
        self.assertIn("cover_thumb_path", workspace)
        self.assertIn("needs_review", workspace)
        self.assertIn("uq_cx_camadas_collections_client_name", workspace)

    def test_cena_guarda_dates_e_venue(self):
        from aicentralv2.camadas.html.scene import build_scene, text_elements_from_reading

        reading = {
            "headline": "Arraial de Belô",
            "support": "É de graça!",
            "dates": "24, 25 e 26 julho",
            "venue": "Mineirinho",
            "logo_text": "Belotur",
            "elements": [{"role": "person", "text": "Mumuzinho"}],
        }
        rows = text_elements_from_reading(reading)
        roles = [item["role"] for item in rows]
        self.assertIn("date", roles)
        self.assertIn("venue", roles)
        self.assertIn("person_label", roles)
        scene = build_scene("crt_test", reading, width=1600, height=900)
        self.assertEqual(scene["schema_version"], "2.0")
        self.assertEqual(scene["canvas"]["aspect_ratio"], "16:9")
        texts = {item["role"]: item["text"] for item in scene["layers"]}
        self.assertEqual(texts["date"], "24, 25 e 26 julho")
        self.assertEqual(texts["venue"], "Mineirinho")
        self.assertEqual(texts["person_label"], "Mumuzinho")

    def test_cena_nao_recoloca_ocr_depois_de_editar_texto(self):
        from aicentralv2.camadas.html.scene import build_scene

        reading = {"headline": "Grito da peça", "support": "É de graça!"}
        scene = build_scene(
            "crt_test",
            reading,
            elements=[
                {
                    "public_id": "el_ba5c59b6b900429e815322",
                    "role": "headline",
                    "label": "Headline",
                    "layer_type": "text",
                    "text_content": "Grito revisado",
                    "z_index": 10,
                    "visible": True,
                }
            ],
        )
        headlines = [item for item in scene["layers"] if item.get("role") == "headline"]
        self.assertEqual(len(headlines), 1)
        self.assertEqual(headlines[0]["id"], "el_ba5c59b6b900429e815322")
        self.assertEqual(headlines[0]["text"], "Grito revisado")

    def test_storage_rejeita_nao_imagem(self):
        from aicentralv2.camadas.storage import CamadasStorage, validate_still

        with self.assertRaises(ValueError):
            validate_still(FileStorage(stream=io.BytesIO(b"nope"), filename="nota.txt"))
        storage = CamadasStorage(root=self._tmp())
        saved = storage.save_original(_still_file(), "crt_ab12cd34ef56ab12cd34ef")
        self.assertTrue(saved["asset_path"].startswith("/static/uploads/camadas/"))
        self.assertEqual(saved["width"], 1)
        self.assertTrue(storage.as_data_url(saved["asset_path"]).startswith("data:image/png;"))

    def _tmp(self):
        import tempfile

        return Path(tempfile.mkdtemp())

    def test_create_e_analyze_persistem_read_full(self):
        from aicentralv2.camadas.service import CamadasService

        def text_callable(messages, **_kwargs):
            return {
                "content": {
                    "headline": "Arraial de Belô",
                    "support": "É de graça!",
                    "dates": "24, 25 e 26 julho",
                    "venue": "Mineirinho",
                    "cta": "",
                    "price": "",
                    "logo_text": "Belotur",
                }
            }

        repo = FakeRepository()
        service = CamadasService(
            repository=repo,
            storage=FakeStorage(),
            text_callable=text_callable,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        created = service.create_creative(_still_file(), {"name": "Arraial"}, user_id=9)
        self.assertTrue(created["creative_id"].startswith("crt_"))
        self.assertTrue(created["job_id"].startswith("job_"))
        job = service.get_job(created["job_id"])
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["progress"], 100)
        document = service.get_creative(created["creative_id"])
        self.assertEqual(document["creative"]["name"], "Arraial")
        self.assertEqual(document["creative"]["reading"]["ocr_status"], "succeeded")
        self.assertEqual(document["creative"]["reading"]["read_full"]["dates"], "24, 25 e 26 julho")
        self.assertIn("dates", document["creative"]["reading"]["read_full"])
        roles = [item["role"] for item in document["elements"]]
        self.assertIn("date", roles)
        self.assertIn("venue", roles)
        self.assertEqual(document["scene"]["schema_version"], "2.0")
        self.assertEqual(document["scene_version"], 1)

    def test_analyze_sem_ocr_nao_falha(self):
        from aicentralv2.camadas.service import CamadasService

        repo = FakeRepository()
        service = CamadasService(
            repository=repo,
            storage=FakeStorage(),
            text_callable=None,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        created = service.create_creative(_still_file())
        job = service.get_job(created["job_id"])
        self.assertEqual(job["status"], "done")
        document = service.get_creative(created["creative_id"])
        self.assertEqual(document["creative"]["reading"]["ocr_status"], "unavailable")
        self.assertEqual(document["elements"], [])

    def test_rotas_http(self):
        from aicentralv2.camadas.routes import register_camadas_routes
        from aicentralv2.camadas.service import CamadasService

        repo = FakeRepository()
        service = CamadasService(
            repository=repo,
            storage=FakeStorage(),
            text_callable=None,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
        register_camadas_routes(blueprint)
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(blueprint)
        with patch("aicentralv2.camadas.routes._service", return_value=service):
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_type"] = "admin"
            empty = client.post("/parametros/api/camadas/v2/creatives")
            self.assertEqual(empty.status_code, 400)
            response = client.post(
                "/parametros/api/camadas/v2/creatives",
                data={"file": (io.BytesIO(PNG_1PX), "still.png"), "name": "Peça"},
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 200)
            created = response.get_json()["data"]
            job = client.get(f"/parametros/api/camadas/v2/jobs/{created['job_id']}")
            self.assertEqual(job.status_code, 200)
            self.assertEqual(job.get_json()["data"]["status"], "done")
            document = client.get(f"/parametros/api/camadas/v2/creatives/{created['creative_id']}")
            self.assertEqual(document.status_code, 200)
            self.assertEqual(document.get_json()["data"]["creative"]["name"], "Peça")

    def test_desk_troca_painel_com_flag(self):
        from aicentralv2.creative_modeling_routes import register_creative_modeling_routes

        app = Flask(__name__)
        app.secret_key = "test"
        app.config["CAMADAS_V2_ENABLED"] = True
        register_creative_modeling_routes(app)
        with patch("aicentralv2.creative_modeling_routes.render_template", return_value="ok") as render:
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_type"] = "admin"
            response = client.get("/modelagem-criativos/camadas")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(render.call_args.kwargs["panel"], "parametros/_mc_camadas_v2.html")
        self.assertEqual(render.call_args.kwargs["mc_page_js"], "js/camadas/index.js")

    def test_v1_continua_no_desk(self):
        from aicentralv2.creative_modeling_routes import MC_DESKS

        self.assertEqual(MC_DESKS["camadas"]["panel"], "parametros/_mc_camadas.html")
        self.assertEqual(MC_DESKS["camadas"]["page_js"], "js/mc-camadas.js")
        desk = (ROOT / "aicentralv2" / "templates" / "parametros" / "modelagem_desk.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("mc_page_js) }}?v=76", desk)
        self.assertIn("js/camadas/index.js", desk)
        self.assertIn("camadas-v2.css", desk)

    def test_fase3_templates_e_modulos(self):
        templates = ROOT / "aicentralv2" / "templates" / "parametros"
        for name in (
            "_mc_camadas_v2.html",
            "_mc_camadas_toolbar.html",
            "_mc_camadas_library.html",
            "_mc_camadas_stage.html",
            "_mc_camadas_layers.html",
            "_mc_camadas_inspector.html",
            "_mc_camadas_html_stage.html",
            "_mc_camadas_animation.html",
        ):
            text = (templates / name).read_text(encoding="utf-8")
            self.assertTrue(text.strip())
        stage = (templates / "_mc_camadas_stage.html").read_text(encoding="utf-8")
        self.assertIn("data-stage-mode=\"original\"", stage)
        self.assertIn("data-stage-mode=\"layers\"", stage)
        self.assertIn("data-stage-mode=\"html\"", stage)
        self.assertIn("data-stage-mode=\"animation\"", stage)
        self.assertIn("mcCv2Canvas", stage)
        shell = (templates / "_mc_camadas_v2.html").read_text(encoding="utf-8")
        self.assertIn("mcCv2App", shell)
        self.assertIn("mc-cv2-bench", shell)
        self.assertIn("data-cv2-step=\"read\"", shell)
        icons = (templates / "_mc_camadas_icons.html").read_text(encoding="utf-8")
        self.assertIn("cv2-eye", icons)
        js = ROOT / "aicentralv2" / "static" / "js" / "camadas"
        for name in (
            "index.js",
            "api.js",
            "store.js",
            "events.js",
            "upload.js",
            "jobs.js",
            "stage.js",
            "canvas-renderer.js",
            "mask-editor.js",
            "contour-renderer.js",
            "transform-controls.js",
            "layers-panel.js",
            "asset-library.js",
            "html-preview.js",
            "html-runtime.js",
            "animation-panel.js",
            "inspector.js",
            "history.js",
            "utils.js",
        ):
            self.assertTrue((js / name).is_file(), name)
        index = (js / "index.js").read_text(encoding="utf-8")
        self.assertIn("createStore", index)
        self.assertIn("bindStage", index)
        self.assertNotIn("(() => {", index)
        upload = (js / "upload.js").read_text(encoding="utf-8")
        self.assertNotIn("const document =", upload)
        library_js = (js / "asset-library.js").read_text(encoding="utf-8")
        self.assertNotIn("const document =", library_js)
        css = (ROOT / "aicentralv2" / "static" / "css" / "camadas-v2.css").read_text(encoding="utf-8")
        self.assertIn("mc-cv2-check", css)
        self.assertIn("mc-cv2-handle", css)
        self.assertIn("--cv2-register", css)
        self.assertIn("mc-cv2-bench", css)

    def test_sam2_e_stub(self):
        from aicentralv2.camadas.segmentation.provider import probe_sam2, sam2_segment_all

        self.assertFalse(probe_sam2())
        self.assertEqual(sam2_segment_all(None), [])

    def test_duas_pessoas_viram_duas_camadas(self):
        from aicentralv2.camadas.service import CamadasService
        from aicentralv2.camadas.storage import CamadasStorage

        still, predict = _two_people()
        service = CamadasService(
            repository=FakeRepository(),
            storage=CamadasStorage(root=self._tmp()),
            text_callable=None,
            predictor=predict,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        created = service.create_creative(_image_file(still))
        document = service.get_creative(created["creative_id"])
        people = [item for item in document["elements"] if item["role"] == "person"]
        self.assertEqual(len(people), 2)
        self.assertEqual(people[0]["label"], "Pessoa 01")
        self.assertEqual(people[1]["label"], "Pessoa 02")
        self.assertTrue(people[0]["png_path"])
        self.assertTrue(people[0]["mask_path"])
        self.assertTrue(people[0]["thumb_path"])
        self.assertIn("-th.png", people[0]["thumb_path"])
        self.assertNotEqual(people[0]["thumb_path"], people[0]["png_path"])
        self.assertIn("person", [item["role"] for item in document["scene"]["layers"]])
        backgrounds = [item for item in document["elements"] if item["role"] == "background"]
        self.assertEqual(len(backgrounds), 1)

        hit = service.segment_point(
            created["creative_id"],
            {"positive_points": [{"x": 0.2, "y": 0.5}]},
        )
        self.assertFalse(hit["created"])
        self.assertEqual(hit["element"]["role"], "person")

        refined = service.refine_element_mask(
            people[0]["id"],
            {"expand_px": 3, "remove_halo": True},
        )
        self.assertEqual(refined["id"], people[0]["id"])
        self.assertTrue(refined["metadata"].get("points") or refined["mask_path"])

        patched = service.patch_element(people[0]["id"], {"label": "Pessoa principal", "approved": True})
        self.assertEqual(patched["label"], "Pessoa principal")
        self.assertTrue(patched["approved"])

    def test_rota_segment_descarta_predictor(self):
        from aicentralv2.camadas.routes import register_camadas_routes

        service = type("S", (), {"segment_point": lambda self, creative_id, payload: payload})()
        blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
        register_camadas_routes(blueprint)
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(blueprint)
        with patch("aicentralv2.camadas.routes._service", return_value=service):
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_type"] = "admin"
            response = client.post(
                "/parametros/api/camadas/v2/creatives/crt_ab/segment",
                json={
                    "positive_points": [{"x": 0.2, "y": 0.3}],
                    "predictor": "malicioso",
                    "text_callable": "malicioso",
                },
            )
        self.assertEqual(response.status_code, 200)
        sent = response.get_json()["data"]
        self.assertNotIn("predictor", sent)
        self.assertNotIn("text_callable", sent)

    def test_fase4_cena_compiler_e_patch(self):
        from aicentralv2.camadas.html.compiler import compile_scene
        from aicentralv2.camadas.html.sanitizer import sanitize_scene
        from aicentralv2.camadas.repositories import CamadasConflictError
        from aicentralv2.camadas.service import CamadasService

        dirty = sanitize_scene({
            "schema_version": "2.0",
            "creative_id": "crt_ab12cd34ef56ab12cd34ef",
            "canvas": {"width": 800, "height": 450, "background": "#011A54"},
            "layers": [{
                "id": "layer-headline-10",
                "type": "text",
                "role": "headline",
                "text": "<script>alert(1)</script>Arraial",
                "x": 8,
                "y": 14,
                "width": 40,
                "height": 20,
                "z_index": 30,
            }],
        })
        html = compile_scene(dirty)
        self.assertIn("Arraial", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

        def text_callable(messages, **_kwargs):
            return {"content": {"headline": "Grito original", "dates": "24 julho", "venue": "Mineirinho"}}

        service = CamadasService(
            repository=FakeRepository(),
            storage=FakeStorage(),
            text_callable=text_callable,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        created = service.create_creative(_still_file(), {"name": "Cena"})
        document = service.get_creative(created["creative_id"])
        headline = next(item for item in document["scene"]["layers"] if item["role"] == "headline")
        saved = service.patch_scene(
            created["creative_id"],
            {
                "version": document["scene_version"],
                "operations": [{
                    "operation": "update",
                    "layer_id": headline["id"],
                    "properties": {"text": "Novo grito"},
                }],
            },
        )
        self.assertEqual(saved["scene_version"], 2)
        texts = {item["role"]: item["text"] for item in saved["scene"]["layers"]}
        self.assertEqual(texts["headline"], "Novo grito")
        self.assertEqual(texts["date"], "24 julho")
        with self.assertRaises(CamadasConflictError):
            service.patch_scene(
                created["creative_id"],
                {
                    "version": 1,
                    "operations": [{
                        "operation": "update",
                        "layer_id": headline["id"],
                        "properties": {"text": "Stale"},
                    }],
                },
            )
        stage = (
            ROOT / "aicentralv2" / "templates" / "parametros" / "_mc_camadas_html_stage.html"
        ).read_text(encoding="utf-8")
        self.assertIn("mcHtmlStage", stage)
        self.assertIn("allow-same-origin", stage)
        self.assertIn("camadas_v2_html_stage", stage)
        runtime = (
            ROOT / "aicentralv2" / "static" / "js" / "camadas" / "html-runtime.js"
        ).read_text(encoding="utf-8")
        self.assertIn("camadas:render", runtime)
        self.assertIn("textContent", runtime)
        self.assertNotIn("innerHTML", runtime)

    def test_rota_scene_descarta_injection(self):
        from aicentralv2.camadas.routes import register_camadas_routes

        captured = {}

        class FakeService:
            def patch_scene(self, creative_id, payload):
                captured.update(payload)
                return {"scene": {"schema_version": "2.0", "layers": []}, "scene_version": 2}

        blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
        register_camadas_routes(blueprint)
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(blueprint)
        with patch("aicentralv2.camadas.routes._service", return_value=FakeService()):
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_type"] = "admin"
            response = client.patch(
                "/parametros/api/camadas/v2/creatives/crt_ab/scene",
                json={
                    "version": 1,
                    "operations": [{"operation": "update", "layer_id": "layer-headline-10", "properties": {"text": "Oi"}}],
                    "predictor": "malicioso",
                    "text_callable": "malicioso",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("predictor", captured)
        self.assertNotIn("text_callable", captured)
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        self.assertIn("/parametros/api/camadas/v2/creatives/<creative_id>/scene", rules)
        self.assertIn("/parametros/camadas/v2/stage", rules)

    def test_fase5_biblioteca_publish_dedup_e_place(self):
        from aicentralv2.camadas.schemas import PROVENANCE_LABELS, normalize_provenance
        from aicentralv2.camadas.service import CamadasService

        self.assertEqual(normalize_provenance("recorte_original"), "cutout")
        self.assertEqual(PROVENANCE_LABELS["cutout"], "Recorte original")
        self.assertEqual(PROVENANCE_LABELS["generated"], "Gerado por IA")

        def text_callable(messages, **_kwargs):
            return {"content": {"headline": "Grito", "cta": "Entrar"}}

        service = CamadasService(
            repository=FakeRepository(),
            storage=FakeStorage(),
            text_callable=text_callable,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        created = service.create_creative(_still_file(), {"name": "Peça", "brand_id": 10})
        document = service.get_creative(created["creative_id"])
        headline = next(item for item in document["elements"] if item["role"] == "headline")
        published = service.publish_element(headline["id"], {"name": "Grito", "tags": ["campanha"]})
        self.assertTrue(published["created"])
        self.assertFalse(published["duplicate"])
        self.assertTrue(published["asset"]["id"].startswith("ast_"))
        self.assertEqual(published["asset"]["provenance"], "html")
        self.assertEqual(published["asset"]["kind"], "composition")
        self.assertEqual(published["asset"]["tags"], ["campanha"])

        again = service.publish_element(headline["id"], {"name": "Grito 2"})
        self.assertFalse(again["created"])
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["asset"]["id"], published["asset"]["id"])

        library = service.list_brand_library(10, {"kind": "composition"})
        self.assertEqual(len(library["assets"]), 1)
        self.assertEqual(library["counts"]["composition"], 1)
        self.assertTrue(library["collections"])

        other = service.create_creative(_still_file(), {"name": "Outra", "brand_id": 10})
        placed = service.place_asset(other["creative_id"], {
            "asset_id": published["asset"]["id"],
            "x": 12,
            "y": 18,
        })
        self.assertTrue(placed["placed"])
        self.assertEqual(placed["scene_version"], 1)
        self.assertEqual(placed["element"]["provenance"], "html")
        self.assertEqual(placed["element"]["bbox"]["x"], 12)
        self.assertTrue(any(item["id"] == placed["element"]["id"] for item in placed["scene"]["layers"]))

        missing = service.create_creative(_still_file(), {"name": "Sem marca"})
        empty = service.get_creative(missing["creative_id"])
        with self.assertRaises(ValueError):
            service.publish_element(
                next(item["id"] for item in empty["elements"] if item["role"] == "headline"),
                {},
            )

        library_html = (
            ROOT / "aicentralv2" / "templates" / "parametros" / "_mc_camadas_library.html"
        ).read_text(encoding="utf-8")
        self.assertIn("data-library-group=\"composition\"", library_html)
        self.assertIn("mcCv2LibrarySearch", library_html)
        js = (ROOT / "aicentralv2" / "static" / "js" / "camadas" / "asset-library.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("application/x-camadas-asset", js)
        self.assertIn("placeAsset", js)

    def test_rota_publish_descarta_injection(self):
        from aicentralv2.camadas.routes import register_camadas_routes

        captured = {}

        class FakeService:
            def publish_element(self, element_id, payload):
                captured.update(payload)
                return {"asset": {"id": "ast_ab"}, "created": True, "duplicate": False}

        blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
        register_camadas_routes(blueprint)
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(blueprint)
        with patch("aicentralv2.camadas.routes._service", return_value=FakeService()):
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_type"] = "admin"
            response = client.post(
                "/parametros/api/camadas/v2/elements/el_ab/publish",
                json={"name": "Pessoa", "predictor": "malicioso"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("predictor", captured)
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        self.assertIn("/parametros/api/camadas/v2/elements/<element_id>/publish", rules)
        self.assertIn("/parametros/api/camadas/v2/brands/<brand_id>/assets", rules)
        self.assertIn("/parametros/api/camadas/v2/creatives/<creative_id>/place", rules)
        self.assertIn("/parametros/api/camadas/v2/creatives/<creative_id>/clean-background", rules)

    def test_fluxo_http_backend_completo(self):
        from aicentralv2.camadas.routes import register_camadas_routes
        from aicentralv2.camadas.service import CamadasService

        def text_callable(messages, **_kwargs):
            return {"content": {"headline": "Grito da peça", "cta": "Entrar", "dates": "24 julho"}}

        service = CamadasService(
            repository=FakeRepository(),
            storage=FakeStorage(),
            text_callable=text_callable,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
        register_camadas_routes(blueprint)
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(blueprint)
        with patch("aicentralv2.camadas.routes._service", return_value=service):
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_type"] = "admin"
            created = client.post(
                "/parametros/api/camadas/v2/creatives",
                data={"file": (io.BytesIO(PNG_1PX), "still.png"), "name": "Peça", "brand_id": "10"},
                content_type="multipart/form-data",
            )
            self.assertEqual(created.status_code, 200)
            ids = created.get_json()["data"]
            job = client.get(f"/parametros/api/camadas/v2/jobs/{ids['job_id']}")
            self.assertEqual(job.get_json()["data"]["status"], "done")
            document = client.get(f"/parametros/api/camadas/v2/creatives/{ids['creative_id']}")
            payload = document.get_json()["data"]
            self.assertEqual(payload["scene"]["schema_version"], "2.0")
            self.assertEqual(payload["scene_version"], 1)
            headline = next(item for item in payload["scene"]["layers"] if item["role"] == "headline")
            patched = client.patch(
                f"/parametros/api/camadas/v2/creatives/{ids['creative_id']}/scene",
                json={
                    "version": 1,
                    "operations": [{
                        "operation": "update",
                        "layer_id": headline["id"],
                        "properties": {"text": "Grito editado"},
                    }],
                },
            )
            self.assertEqual(patched.status_code, 200)
            self.assertEqual(patched.get_json()["data"]["scene_version"], 2)
            element = next(item for item in payload["elements"] if item["role"] == "headline")
            published = client.post(
                f"/parametros/api/camadas/v2/elements/{element['id']}/publish",
                json={"name": "Grito", "tags": ["live"]},
            )
            self.assertEqual(published.status_code, 200)
            asset = published.get_json()["data"]["asset"]
            self.assertTrue(asset["id"].startswith("ast_"))
            library = client.get("/parametros/api/camadas/v2/brands/10/assets?kind=composition")
            self.assertEqual(library.status_code, 200)
            self.assertEqual(len(library.get_json()["data"]["assets"]), 1)
            other = client.post(
                "/parametros/api/camadas/v2/creatives",
                data={"file": (io.BytesIO(PNG_1PX), "still.png"), "brand_id": "10"},
                content_type="multipart/form-data",
            )
            placed = client.post(
                f"/parametros/api/camadas/v2/creatives/{other.get_json()['data']['creative_id']}/place",
                json={"asset_id": asset["id"], "x": 15, "y": 20},
            )
            self.assertEqual(placed.status_code, 200)
            self.assertTrue(placed.get_json()["data"]["placed"])
            stale = client.patch(
                f"/parametros/api/camadas/v2/creatives/{ids['creative_id']}/scene",
                json={
                    "version": 1,
                    "operations": [{
                        "operation": "update",
                        "layer_id": headline["id"],
                        "properties": {"text": "velho"},
                    }],
                },
            )
            self.assertEqual(stale.status_code, 409)

    def test_export_delete_e_collections(self):
        from aicentralv2.camadas.routes import register_camadas_routes
        from aicentralv2.camadas.service import CamadasService
        from aicentralv2.camadas.storage import CamadasStorage

        still, predict = _two_people()
        service = CamadasService(
            repository=FakeRepository(),
            storage=CamadasStorage(root=self._tmp()),
            text_callable=lambda messages, **_k: {"content": {"headline": "Grito"}},
            predictor=predict,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        created = service.create_creative(_image_file(still), {"brand_id": 10})
        document = service.get_creative(created["creative_id"])
        person = next(item for item in document["elements"] if item["role"] == "person")
        exported = service.export_creative(created["creative_id"])
        self.assertIn("<!DOCTYPE html>", exported["html"])
        removed = service.delete_element(person["id"])
        self.assertTrue(removed["deleted"])
        leftover = service.get_creative(created["creative_id"])
        self.assertFalse(any(item["id"] == person["id"] for item in leftover["elements"]))
        listed = service.list_brand_collections(10)
        self.assertIn("collections", listed)

        blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
        register_camadas_routes(blueprint)
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(blueprint)
        with patch("aicentralv2.camadas.routes._service", return_value=service):
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_type"] = "admin"
            packs = client.get("/parametros/api/camadas/v2/brands/10/collections")
            self.assertEqual(packs.status_code, 200)
            html = client.get(f"/parametros/api/camadas/v2/creatives/{created['creative_id']}/export")
            self.assertEqual(html.status_code, 200)
            self.assertIn("html", html.get_json()["data"])

    def test_limpar_fundo_so_em_foto(self):
        import base64

        from PIL import Image

        from aicentralv2.camadas.service import PAPER_WELL, CamadasService
        from aicentralv2.camadas.storage import CamadasStorage
        from aicentralv2.creative_format_lab.decompose import GROUND_PROMPT

        paper, predict = _two_people()
        paper_service = CamadasService(
            repository=FakeRepository(),
            storage=CamadasStorage(root=self._tmp()),
            text_callable=lambda messages, **_k: {"content": {}},
            predictor=predict,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        paper_id = paper_service.create_creative(_image_file(paper), {"name": "Papel"})["creative_id"]
        with self.assertRaises(ValueError) as raised:
            paper_service.clean_background(paper_id)
        self.assertEqual(str(raised.exception), PAPER_WELL)

        photo, predict_photo = _lifestyle()
        calls = []

        def fake_image(prompt, **kwargs):
            calls.append({"prompt": prompt, **kwargs})
            well = Image.new("RGB", (240, 120), (12, 90, 40))
            buffer = io.BytesIO()
            well.save(buffer, format="PNG")
            return {"b64_json": base64.b64encode(buffer.getvalue()).decode("ascii")}

        repo = FakeRepository()
        service = CamadasService(
            repository=repo,
            storage=CamadasStorage(root=self._tmp()),
            text_callable=lambda messages, **_k: {"content": {}},
            predictor=predict_photo,
            image_callable=fake_image,
            spawn_job=lambda fn, job_id, creative_id: fn(job_id, creative_id),
        )
        created = service.create_creative(_image_file(photo), {"name": "Foto"})
        before = service.get_creative(created["creative_id"])
        self.assertTrue(before["creative"]["can_clean_background"])
        self.assertTrue(before["creative"]["clean_configured"])
        people = [item["png_path"] for item in before["elements"] if item["role"] == "person"]
        background = next(item for item in before["elements"] if item["role"] == "background")
        cleaned = service.clean_background(created["creative_id"])
        self.assertEqual(cleaned["element"]["provenance"], "generated")
        self.assertNotEqual(cleaned["element"]["png_path"], background["png_path"])
        self.assertTrue(cleaned["element"]["png_path"].endswith("background-clean.png"))
        after = service.get_creative(created["creative_id"])
        self.assertEqual(
            [item["png_path"] for item in after["elements"] if item["role"] == "person"],
            people,
        )
        self.assertEqual(calls[0]["prompt"], GROUND_PROMPT)
        self.assertEqual(calls[0]["resolution"], "1K")
        self.assertEqual(len(repo.generations), 1)

        service_text = (ROOT / "aicentralv2" / "camadas" / "service.py").read_text(encoding="utf-8")
        self.assertNotIn("google/gemini-3-pro-image", service_text)
        from aicentralv2.config import Config

        self.assertEqual(Config.CAMADAS_V2_IMAGE_MODEL, "")
        self.assertEqual(Config.CAMADAS_V2_IMAGE_RESOLUTION, "1K")

        captured = {}

        class FakeClean:
            def clean_background(self, creative_id):
                captured["id"] = creative_id
                return {"element": {"id": "el_bg"}}

        blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
        from aicentralv2.camadas.routes import register_camadas_routes

        register_camadas_routes(blueprint)
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(blueprint)
        with patch("aicentralv2.camadas.routes._service", return_value=FakeClean()):
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["user_type"] = "admin"
            response = client.post(
                "/parametros/api/camadas/v2/creatives/crt_ab/clean-background",
                json={"image_callable": "malicioso"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["id"], "crt_ab")


def _lifestyle():
    from PIL import Image, ImageDraw

    canvas = Image.new("RGB", (240, 120))
    pixels = canvas.load()
    for y in range(120):
        for x in range(240):
            pixels[x, y] = ((x * 13 + y * 7) % 220, (y * 17 + x) % 180, (x * 5 + y * 3) % 200)
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([12, 16, 88, 108], fill=(196, 122, 90))
    draw.ellipse([150, 16, 226, 108], fill=(196, 122, 90))

    def predict(image):
        first = Image.new("L", image.size, 0)
        ImageDraw.Draw(first).ellipse([12, 16, 88, 108], fill=255)
        second = Image.new("L", image.size, 0)
        ImageDraw.Draw(second).ellipse([150, 16, 226, 108], fill=255)
        return [{"label": "person", "mask": first}, {"label": "person", "mask": second}]

    return canvas, predict


def _two_people():
    from PIL import Image, ImageDraw

    canvas = Image.new("RGB", (240, 120), (0, 51, 255))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([12, 16, 88, 108], fill=(196, 122, 90))
    draw.ellipse([150, 16, 226, 108], fill=(196, 122, 90))

    def predict(image):
        first = Image.new("L", image.size, 0)
        ImageDraw.Draw(first).ellipse([12, 16, 88, 108], fill=255)
        second = Image.new("L", image.size, 0)
        ImageDraw.Draw(second).ellipse([150, 16, 226, 108], fill=255)
        return [{"label": "person", "mask": first}, {"label": "person", "mask": second}]

    return canvas, predict


def _image_file(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return FileStorage(stream=buffer, filename="still.png", content_type="image/png")


if __name__ == "__main__":
    unittest.main()
