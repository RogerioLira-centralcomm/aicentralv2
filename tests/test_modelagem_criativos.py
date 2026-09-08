"""Testes isolados da Modelagem de Criativos, sem PostgreSQL ou APIs reais."""

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Blueprint, Flask
from jinja2 import Environment

from aicentralv2.creative_modeling_generation import (
    CreativeGenerationClient,
    build_higgsfield_payload,
)
from aicentralv2.creative_modeling_routes import register_creative_modeling_routes
from aicentralv2.creative_modeling_service import CreativeModelingService


class FakeRepository:
    def __init__(self):
        self.clients = []
        self.jobs = []
        self.prompts = []
        self.scripts = []
        self.failed = []
        self.assets = [
            {
                "id": index,
                "job_id": 90 + index,
                "asset_url": f"/asset-{index}.png",
                "status": "approved",
            }
            for index in range(1, 5)
        ]

    def create_client(self, data):
        self.clients.append(data)
        return 10

    def get_step_context(self, step_id):
        return {
            "id": 20,
            "campaign_id": 30,
            "campaign_name": "Lançamento",
            "label": "A",
            "objective": "Conversão",
            "campaign_text": "Conheça o produto",
            "cta_text": "Saiba mais",
            "show_price": False,
            "budget_usd": 5,
            "reserved_usd": 0,
            "spent_usd": 0,
            "client_name": "Marca Exemplo",
            "client_sector": "Imobiliário",
            "tone_of_voice": "Seguro e humano",
            "logo_url": "https://example.com/logo.png",
            "logo_upload_path": None,
            "primary_color": "#1E4D4F",
            "secondary_color": "#F3B71B",
            "step": {
                "id": step_id,
                "position": 1,
                "format_template_id": 7,
                "format_name": "Vídeo Outstream",
                "format_slug": "video-outstream",
                "mechanic": "linear_video",
                "media_type": "video",
                "engine": "higgsfield",
                "mockup": "tv",
                "scene_description": None,
                "rendered_prompt": "Approved image prompt",
                "prompt_status": "approved",
                "script_text": '{"title":"Roteiro"}',
                "script_status": "approved",
                "aspect_ratio": "16:9",
                "default_size": "1920x1080",
                "safe_area": {},
                "layers": [],
                "forbidden_elements": [],
                "channel_name": "Netflix",
                "partner_primary_color": "#E50914",
                "partner_secondary_color": "#141414",
                "brand_guidelines": {},
            },
        }

    def create_generation_job(self, *args, **kwargs):
        job_id = len(self.jobs) + 1
        self.jobs.append({"id": job_id, "args": args, "kwargs": kwargs})
        return job_id

    def mark_job_generating(self, job_id):
        self.jobs[job_id - 1]["status"] = "generating"

    def complete_generation_job(self, job_id, cost, metadata, status="done"):
        self.jobs[job_id - 1].update(
            status=status, cost=float(cost), metadata=metadata
        )

    def fail_generation_job(self, job_id, error):
        self.failed.append((job_id, str(error)))

    def update_step_prompt(self, step_id, prompt, status):
        self.prompts.append((step_id, prompt, status))
        return {"id": step_id, "rendered_prompt": prompt, "prompt_status": status}

    def update_step_script(self, step_id, script, status):
        self.scripts.append((step_id, script, status))
        return {"id": step_id, "script_text": script, "script_status": status}

    def add_job_reference(self, job_id, reference):
        return {"id": 1, "position": 1}

    def add_generated_asset(self, job_id, step_id, asset_type, url, metadata):
        return {"id": 99, "asset_url": url, "status": "done"}

    def get_assets(self, ids, approved_only=True):
        index = {asset["id"]: asset for asset in self.assets}
        return [index[value] for value in ids if value in index]

    def list_campaign_assets(self, campaign_id):
        return [
            {**asset, "campaign_id": campaign_id, "asset_type": "image"}
            for asset in self.assets
        ]

    def reorder_campaign_assets(self, campaign_id, asset_ids):
        self.reordered = (campaign_id, asset_ids)

    def create_public_collection(
        self, campaign_id, token, title, description, asset_ids, created_by
    ):
        self.public_collection = {
            "campaign_id": campaign_id,
            "token": token,
            "title": title,
            "description": description,
            "asset_ids": asset_ids,
            "created_by": created_by,
        }
        return {"id": 77, "token": token}

    def link_video_assets(self, job_id, assets):
        self.jobs[job_id - 1]["linked"] = [asset["id"] for asset in assets]

    def list_generation_jobs(self, campaign_id=None):
        return self.jobs


class FakeGenerator:
    def generate_prompt(self, context):
        return {
            "result": {
                "prompt_en": "Premium campaign image using both brand palettes.",
                "rationale_pt": "Combina anunciante e contexto parceiro.",
                "checks": ["safe area"],
            },
            "model": "openai/gpt-test",
            "usage": {"total_tokens": 20},
            "actual_cost_usd": 0.01,
        }

    def generate_image(self, prompt, references, aspect_ratio):
        return {
            "b64_json": base64.b64encode(b"image").decode(),
            "model": "openai/gpt-image-2",
            "usage": {},
            "actual_cost_usd": 0.13,
            "output_format": "png",
        }

    def generate_script(self, context):
        return {
            "result": {
                "title": "Quatro cenas",
                "duration_seconds": 15,
                "voiceover_pt": "Texto",
                "shots": [{"position": index} for index in range(1, 5)],
                "endcard": "Saiba mais",
            },
            "model": "openai/gpt-test",
            "usage": {},
            "actual_cost_usd": 0.01,
        }


class FakeStorage:
    def __init__(self):
        self.saved = []

    def save_reference(self, file_storage):
        item = {
            "asset_path": f"/ref-{len(self.saved) + 1}.png",
            "original_name": "ref.png",
            "mime_type": "image/png",
        }
        self.saved.append(item)
        return item

    def reference_as_data_url(self, path, mime):
        return "data:image/png;base64,aW1hZ2U="

    def save_generated_base64(self, encoded, output_format):
        return "/generated.png"

    def delete(self, path):
        pass


class CreativeServiceTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.service = CreativeModelingService(
            repository=self.repo,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )

    def test_cliente_valida_cores_e_salva_identidade(self):
        result = self.service.create_client(
            {
                "name": "Cliente",
                "primary_color": "#123ABC",
                "secondary_color": "#FEDCBA",
            }
        )
        self.assertEqual(result["id"], 10)
        self.assertEqual(self.repo.clients[0]["primary_color"], "#123ABC")
        with self.assertRaisesRegex(ValueError, "RRGGBB"):
            self.service.create_client({"name": "Inválido", "primary_color": "azul"})

    def test_prompt_deterministico_contem_variacao_e_identidades(self):
        context = self.repo.get_step_context(8)
        prompt = self.service.build_prompt(context, context["step"], 2)
        self.assertIn("[VARIAÇÃO A — STEP 1]", prompt)
        self.assertIn("Cor primária da marca: #1E4D4F", prompt)
        self.assertIn("Cor de contexto do parceiro: #E50914", prompt)

    @patch.dict("os.environ", {"CREATIVE_PROMPT_ESTIMATED_COST_USD": "0.02"})
    def test_gera_prompt_via_gpt_e_registra_custo(self):
        result = self.service.generate_step_prompt(8, created_by=3)
        self.assertEqual(result["job_id"], 1)
        self.assertEqual(self.repo.prompts[0][2], "generated")
        self.assertEqual(self.repo.jobs[0]["status"], "review")
        self.assertEqual(self.repo.jobs[0]["cost"], 0.01)

    def test_imagem_limita_duas_referencias(self):
        with self.assertRaisesRegex(ValueError, "no máximo duas"):
            self.service.generate_step_image(8, [object(), object(), object()])

    def test_roteiro_exige_quatro_assets_aprovados(self):
        with self.assertRaisesRegex(ValueError, "exatamente quatro"):
            self.service.generate_video_script(8, [1, 2, 3])
        result = self.service.generate_video_script(8, [1, 2, 3, 4])
        self.assertEqual(len(result["script"]["shots"]), 4)

    def test_prepara_higgsfield_com_quatro_imagens(self):
        result = self.service.prepare_higgsfield(8, [1, 2, 3, 4])
        self.assertEqual(result["payload"]["status"], "ready_for_higgsfield")
        self.assertEqual(len(result["payload"]["image_inputs"]), 4)

    def test_link_publico_usa_token_criptografico_e_preserva_ordem(self):
        result = self.service.create_public_collection(
            30, {"title": "Apresentação", "asset_ids": [4, 2, 1]}, created_by=9
        )
        token = result["public_url"].rsplit("/", 1)[-1]
        self.assertRegex(token, r"^[A-Za-z0-9_-]{40,}$")
        self.assertEqual(self.repo.public_collection["asset_ids"], [4, 2, 1])
        self.assertEqual(result["asset_count"], 3)

    def test_reordenacao_rejeita_assets_duplicados(self):
        with self.assertRaisesRegex(ValueError, "duplicados"):
            self.service.reorder_campaign_assets(
                30, {"asset_ids": [1, 2, 2, 4]}
            )


class FakeHttpResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "model": "openai/gpt-image-2",
            "data": [{"b64_json": "aW1hZ2U="}],
            "usage": {"cost": 0.13},
        }


class FakeHttp:
    def __init__(self):
        self.payload = None

    def post(self, url, **kwargs):
        self.payload = kwargs["json"]
        return FakeHttpResponse()


class CreativeGenerationContractTest(unittest.TestCase):
    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    def test_image_api_usa_modelo_e_duas_referencias(self):
        http = FakeHttp()
        client = CreativeGenerationClient(http=http)
        result = client.generate_image("prompt", ["ref1", "ref2"], "16:9")
        self.assertEqual(http.payload["model"], "openai/gpt-image-2")
        self.assertEqual(http.payload["input_references"], ["ref1", "ref2"])
        self.assertEqual(result["actual_cost_usd"], 0.13)

    def test_payload_higgsfield_exige_quatro_assets(self):
        assets = [{"asset_url": f"/{index}.png"} for index in range(4)]
        payload = build_higgsfield_payload(1, "roteiro", assets, "16:9", 15)
        self.assertEqual(len(payload["image_inputs"]), 4)
        with self.assertRaises(ValueError):
            build_higgsfield_payload(1, "roteiro", assets[:3], "16:9", 15)


class CreativeRoutesTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY="creative-test")
        bp = Blueprint("parametros_test", __name__, url_prefix="/parametros")
        register_creative_modeling_routes(bp)
        self.app.register_blueprint(bp)
        self.client = self.app.test_client()

    def test_api_exige_login(self):
        response = self.client.get("/parametros/api/formats")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_api_exige_admin(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "client"
        response = self.client.get("/parametros/api/formats")
        self.assertEqual(response.status_code, 403)


class CreativeFilesContractTest(unittest.TestCase):
    def test_templates_sao_jinja_valido_e_usam_design_system(self):
        root = Path(__file__).resolve().parents[1]
        template_dir = root / "aicentralv2" / "templates" / "parametros"
        names = [
            "modelagem_criativos.html",
            "_mc_gerador.html",
            "_mc_variacoes.html",
            "_mc_biblioteca.html",
            "_mc_clientes.html",
            "_mc_historico.html",
        ]
        for name in names:
            source = (template_dir / name).read_text(encoding="utf-8")
            Environment().parse(source)
            self.assertNotIn("btn btn-", source)
        page = (template_dir / "modelagem_criativos.html").read_text(encoding="utf-8")
        self.assertIn('extends "base_erp.html"', page)
        self.assertIn("cx-tabs", page)
        public_page = (
            root
            / "aicentralv2"
            / "templates"
            / "public"
            / "creative_collection.html"
        ).read_text(encoding="utf-8")
        Environment().parse(public_page)
        self.assertIn("cc_logo.png", public_page)
        self.assertIn("pv-player", public_page)
        self.assertIn("data-mechanic", public_page)
        self.assertIn("public_collection_asset", public_page)
        self.assertNotIn('src="{{ asset.asset_url }}"', public_page)

    def test_migration_cobre_custos_referencias_iab_e_video(self):
        root = Path(__file__).resolve().parents[1]
        migration = (root / "migrations" / "create_creative_modeling.sql").read_text(
            encoding="utf-8"
        )
        for table in (
            "cx_generation_jobs",
            "cx_generation_references",
            "cx_generated_assets",
            "cx_format_references",
            "cx_video_input_assets",
            "cx_generation_cost_ledger",
            "cx_public_creative_collections",
            "cx_public_collection_assets",
        ):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", migration)
        seed = (root / "scripts" / "seed_creative_formats.py").read_text(
            encoding="utf-8"
        )
        for size in ("300x250", "728x90", "300x600", "320x50"):
            self.assertIn(size, seed)


if __name__ == "__main__":
    unittest.main()
