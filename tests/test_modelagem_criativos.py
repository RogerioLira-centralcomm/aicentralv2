"""Testes isolados da Modelagem de Criativos, sem PostgreSQL ou APIs reais."""

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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
                "asset_type": "image",
                "status": "approved",
                "campaign_id": 30,
                "format_template_id": 7,
                "aspect_ratio": "4:1",
            }
            for index in range(1, 5)
        ]
        self.format_jobs = []
        self.format_data = {
            "id": 7,
            "name_pt": "Leaderboard",
            "aspect_ratio": "4:1",
            "default_size": "728x90",
            "media_type": "image",
            "screen_context_template": "Portal editorial em desktop",
            "background_guidance": "Conteúdo editorial ao redor",
            "placement_spec": {
                "context": "portal",
                "viewport": {"width": 1280, "height": 800},
                "slot": {"x": 12, "y": 18, "width": 76, "height": 12},
                "fit": "contain",
                "responsive": "scale",
            },
            "behavior_spec": {
                "type": "static",
                "trigger": "none",
                "transition_ms": 0,
            },
            "default_viewer_profile_id": 1,
        }
        self.viewer_profiles = [
            {
                "id": 1, "slug": "g1", "name": "G1",
                "viewer_kind": "portal", "palette": {}, "shell_spec": {},
                "disclaimer": "Simulação sem afiliação",
            },
            {
                "id": 2, "slug": "netflix", "name": "Netflix",
                "viewer_kind": "tv", "palette": {}, "shell_spec": {},
                "disclaimer": "Simulação sem afiliação",
            },
        ]

    def create_client(self, data):
        self.clients.append(data)
        return 10

    def get_format(self, format_id):
        if format_id != 7:
            raise LookupError("Formato não encontrado")
        return dict(self.format_data)

    def update_format_modeling(self, format_id, data):
        self.format_data.update(data)

    def list_viewer_profiles(self):
        return [dict(item) for item in self.viewer_profiles]

    def get_viewer_profile(self, profile_id):
        return next(
            dict(item) for item in self.viewer_profiles if item["id"] == profile_id
        )

    def get_client(self, client_id):
        return {
            "id": client_id,
            "name": "Marca Exemplo",
            "sector": "Imobiliário",
            "tone_of_voice": "Seguro",
            "primary_color": "#123ABC",
            "secondary_color": "#FEDCBA",
        }

    def create_format_modeling_job(
        self, format_id, client_id, parent_id, slot, reference_type, model,
        prompt, references, estimate, refinement=None, created_by=None,
    ):
        job_id = len(self.format_jobs) + 1
        self.format_jobs.append({
            "id": job_id, "format_template_id": format_id,
            "client_id": client_id, "parent_job_id": parent_id,
            "slot": slot, "reference_type": reference_type,
            "model": model, "prompt": prompt, "input_references": references,
            "estimated_cost_usd": estimate, "status": "queued",
            "refinement_instruction": refinement,
        })
        return job_id

    def mark_format_modeling_job_generating(self, job_id):
        self.format_jobs[job_id - 1]["status"] = "generating"

    def complete_format_modeling_job(self, job_id, asset_url, cost, metadata):
        self.format_jobs[job_id - 1].update(
            status="review", asset_url=asset_url,
            actual_cost_usd=cost, response_metadata=metadata,
        )
        return dict(self.format_jobs[job_id - 1])

    def fail_format_modeling_job(self, job_id, error):
        self.format_jobs[job_id - 1].update(status="failed", error=str(error))

    def get_format_modeling_job(self, job_id):
        return dict(self.format_jobs[job_id - 1])

    def list_format_modeling_jobs(self, format_id):
        return [dict(item) for item in self.format_jobs]

    def approve_format_modeling_job(self, job_id, slot):
        self.format_jobs[job_id - 1].update(status="approved", slot=slot)
        return {"id": job_id, "slot": slot, "status": "approved"}

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
            {
                **asset,
                "campaign_id": campaign_id,
                "asset_type": "image",
                "placement_spec": self.format_data["placement_spec"],
                "default_viewer_profile_id": 1,
            }
            for asset in self.assets
        ]

    def reorder_campaign_assets(self, campaign_id, asset_ids):
        self.reordered = (campaign_id, asset_ids)

    def create_public_collection(
        self, campaign_id, token, title, description, asset_ids,
        viewer_profiles, created_by
    ):
        self.public_collection = {
            "campaign_id": campaign_id,
            "token": token,
            "title": title,
            "description": description,
            "asset_ids": asset_ids,
            "viewer_profiles": viewer_profiles,
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

    def generated_as_data_url(self, path):
        return "data:image/png;base64,aW1hZ2U="

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

    def test_prepara_complemento_animado_de_tres_segundos(self):
        result = self.service.prepare_display_motion(1, created_by=9)
        self.assertEqual(result["payload"]["duration_seconds"], 3)
        self.assertEqual(result["payload"]["source_asset_id"], 1)
        self.assertEqual(len(result["payload"]["image_inputs"]), 1)
        self.assertEqual(self.repo.jobs[-1]["args"][3], "display_motion_payload")

    def test_link_publico_usa_token_criptografico_e_preserva_ordem(self):
        result = self.service.create_public_collection(
            30, {"title": "Apresentação", "asset_ids": [4, 2, 1]}, created_by=9
        )
        token = result["public_url"].rsplit("/", 1)[-1]
        self.assertRegex(token, r"^[A-Za-z0-9_-]{40,}$")
        self.assertEqual(self.repo.public_collection["asset_ids"], [4, 2, 1])
        self.assertEqual(result["asset_count"], 3)

    def test_link_publico_persiste_ambiente_por_criativo(self):
        self.service.create_public_collection(
            30,
            {
                "title": "Apresentação",
                "asset_ids": [1, 2],
                "viewer_profiles": {"1": 1},
            },
        )
        self.assertEqual(self.repo.public_collection["viewer_profiles"], {1: 1})

    def test_ambiente_incompativel_com_formato_e_rejeitado(self):
        with self.assertRaisesRegex(ValueError, "não corresponde"):
            self.service.update_format_modeling(
                7,
                {
                    "safe_area": {},
                    "placement_spec": self.repo.format_data["placement_spec"],
                    "behavior_spec": self.repo.format_data["behavior_spec"],
                    "default_viewer_profile_id": 2,
                },
            )

    def test_reordenacao_rejeita_assets_duplicados(self):
        with self.assertRaisesRegex(ValueError, "duplicados"):
            self.service.reorder_campaign_assets(
                30, {"asset_ids": [1, 2, 2, 4]}
            )

    def test_mockup_de_formato_funciona_sem_cliente_e_registra_custo(self):
        result = self.service.generate_format_mockup(
            7,
            {"slot": "2", "reference_type": "background"},
            [],
            created_by=9,
        )
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["slot"], 2)
        self.assertIsNone(self.repo.format_jobs[0]["client_id"])
        self.assertIn("Keep the advertising slot empty", self.repo.format_jobs[0]["prompt"])

    def test_prompt_de_quatro_variacoes_preserva_um_unico_sistema(self):
        prompt = self.service.build_format_mockup_prompt(
            self.repo.format_data,
            self.repo.get_client(10),
            "full_mockup",
            "four_horizontal",
            "Four product states with the same card.",
            True,
        )
        self.assertIn("exactly FOUR identical devices", prompt)
        self.assertIn("Do not redesign the format", prompt)
        self.assertIn("not a free-form campaign poster", prompt)

    def test_prompt_multiformato_muda_mecanica_sem_mudar_campanha(self):
        prompt = self.service.build_format_mockup_prompt(
            self.repo.format_data,
            self.repo.get_client(10),
            "full_mockup",
            "multi_format_board",
            "360, carousel, masterplan hotspots and drag comparison.",
        )
        normalized = " ".join(prompt.split())
        self.assertIn("DIFFERENT interactive advertising format", normalized)
        self.assertIn("campaign design must not", normalized)
        self.assertIn("exactly FOUR advertising mockups", normalized)
        self.assertIn("Do not default every format to a smartphone", normalized)

    def test_formato_interativo_forca_quatro_variacoes(self):
        self.repo.format_data["behavior_spec"]["type"] = "drag"
        self.service.generate_format_mockup(
            7,
            {
                "slot": "1",
                "reference_type": "full_mockup",
                "presentation_mode": "single",
            },
            [],
        )
        self.assertIn(
            "exactly FOUR identical devices",
            self.repo.format_jobs[-1]["prompt"],
        )

    def test_prompt_escolhe_ambiente_nativo_do_placement(self):
        portal_prompt = self.service.build_format_mockup_prompt(
            self.repo.format_data
        )
        self.assertIn("editorial portal shell", portal_prompt)
        self.assertIn("Do not place the portal ad inside a smartphone", portal_prompt)

        tv_format = dict(self.repo.format_data)
        tv_format["placement_spec"] = {
            **self.repo.format_data["placement_spec"],
            "context": "streaming",
        }
        tv_prompt = self.service.build_format_mockup_prompt(tv_format)
        self.assertIn("CTV PRESENTATION", tv_prompt)
        self.assertIn("not inside a phone", tv_prompt)

    def test_refinamento_usa_mockup_anterior_como_referencia(self):
        parent = self.service.generate_format_mockup(
            7,
            {"slot": "1", "reference_type": "full_mockup"},
            [],
        )
        refined = self.service.refine_format_mockup(
            parent["id"], {"instruction": "Aumente o contraste"}, []
        )
        self.assertEqual(refined["parent_job_id"], parent["id"])
        self.assertEqual(refined["status"], "review")
        self.assertIn("Aumente o contraste", refined["prompt"])

    def test_layout_rejeita_slot_fora_do_viewport(self):
        payload = {
            "safe_area": {},
            "placement_spec": {
                "context": "portal",
                "viewport": {"width": 1280, "height": 800},
                "slot": {"x": 90, "y": 10, "width": 20, "height": 20},
                "fit": "contain",
                "responsive": "scale",
            },
            "behavior_spec": {
                "type": "static", "trigger": "none", "transition_ms": 0
            },
        }
        with self.assertRaisesRegex(ValueError, "ultrapassa a largura"):
            self.service.update_format_modeling(7, payload)

    def test_layout_valido_persiste_geometria_e_comportamento(self):
        placement = dict(self.repo.format_data["placement_spec"])
        placement["slot"] = {"x": 10, "y": 15, "width": 70, "height": 20}
        result = self.service.update_format_modeling(7, {
            "safe_area": {},
            "placement_spec": placement,
            "behavior_spec": {
                "type": "hotspot",
                "trigger": "hover_tap",
                "transition_ms": 220,
            },
        })
        self.assertEqual(result["id"], 7)
        self.assertEqual(self.repo.format_data["placement_spec"]["slot"]["width"], 70.0)
        self.assertEqual(self.repo.format_data["behavior_spec"]["type"], "hotspot")


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
        references = [
            "data:image/png;base64,cmVmMQ==",
            "data:image/png;base64,cmVmMg==",
        ]
        result = client.generate_image("prompt", references, "16:9")
        self.assertEqual(http.payload["model"], "openai/gpt-image-2")
        self.assertEqual(
            http.payload["input_references"],
            [
                {"type": "image_url", "image_url": {"url": references[0]}},
                {"type": "image_url", "image_url": {"url": references[1]}},
            ],
        )
        self.assertEqual(http.payload["size"], "2K")
        self.assertNotIn("resolution", http.payload)
        self.assertEqual(http.payload["background"], "opaque")
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

    def test_apis_iniciais_retornam_200(self):
        service = Mock()
        service.list_formats.return_value = [{"id": 7, "name_pt": "Leaderboard"}]
        service.list_viewer_profiles.return_value = [{"id": 1, "slug": "g1"}]
        service.list_clients.return_value = [{"id": 10, "name": "Marca"}]
        service.list_campaigns.return_value = [{"id": 30, "name": "Campanha"}]
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            formats = self.client.get("/parametros/api/formats")
            viewers = self.client.get("/parametros/api/viewer-profiles")
            clients = self.client.get("/parametros/api/clients")
            campaigns = self.client.get("/parametros/api/campaigns")
        for response in (formats, viewers, clients, campaigns):
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()["success"])


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
        self.assertIn("modelagem_criativos.css') }}?v=5", page)
        self.assertIn("modelagem_criativos.js') }}?v=5", page)
        generator = (template_dir / "_mc_gerador.html").read_text(encoding="utf-8")
        self.assertIn("mc-generator-workspace", generator)
        self.assertIn('id="mcGeneratorFormatList"', generator)
        self.assertIn('form="mcCampaignForm"', generator)
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
        library = (template_dir / "_mc_biblioteca.html").read_text(encoding="utf-8")
        self.assertIn("mcFormatStage", library)
        self.assertIn("mcAdSlot", library)
        self.assertIn("mcLibraryDetail", library)

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
        studio_migration = (
            root / "migrations" / "add_creative_format_studio.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("placement_spec JSONB", studio_migration)
        self.assertIn("behavior_spec JSONB", studio_migration)
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS cx_format_modeling_jobs",
            studio_migration,
        )
        layout_seed = (
            root / "migrations" / "run_seed_creative_format_layouts.py"
        ).read_text(encoding="utf-8")
        self.assertIn("COALESCE(f.placement_spec", layout_seed)
        self.assertIn("from psycopg.types.json import Jsonb", layout_seed)
        self.assertIn("Jsonb(_placement(row))", layout_seed)
        self.assertIn("Jsonb(behavior)", layout_seed)
        self.assertIn("THEN %s::jsonb ELSE placement_spec", layout_seed)
        self.assertIn("THEN %s::jsonb ELSE behavior_spec", layout_seed)
        viewer_migration = (
            root / "migrations" / "add_creative_viewer_profiles.sql"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS cx_creative_viewer_profiles",
            viewer_migration,
        )
        self.assertIn("default_viewer_profile_id", viewer_migration)
        self.assertIn("viewer_profile_id", viewer_migration)
        viewer_seed = (
            root / "scripts" / "seed_creative_viewer_profiles.py"
        ).read_text(encoding="utf-8")
        for slug in ("g1", "cnn-brasil", "sbt-news", "netflix", "disney-plus", "hbo-max"):
            self.assertIn(f'"slug": "{slug}"', viewer_seed)
        deploy = (root / "deploy.sh").read_text(encoding="utf-8")
        migration_call = (
            '"$VENV_PYTHON" migrations/run_add_creative_viewer_profiles.py'
        )
        seed_call = '"$VENV_PYTHON" scripts/seed_creative_viewer_profiles.py'
        start_call = "sudo systemctl start aicentralv2"
        verify_call = (
            '"$VENV_PYTHON" scripts/verify_creative_viewer_apis.py'
        )
        self.assertIn(migration_call, deploy)
        self.assertIn(seed_call, deploy)
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_create_creative_modeling.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_add_creative_format_studio.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_seed_creative_format_layouts.py',
            deploy,
        )
        self.assertIn(verify_call, deploy)
        self.assertIn('VENV_PYTHON="$(dirname "$VENV_PIP")/python"', deploy)
        self.assertIn("restore_service_on_error", deploy)
        normal_start = deploy.index(start_call, deploy.index(migration_call))
        self.assertLess(deploy.index(migration_call), normal_start)
        self.assertLess(deploy.index(seed_call), normal_start)
        self.assertLess(normal_start, deploy.index(verify_call))
        verifier = (
            root / "scripts" / "verify_creative_viewer_apis.py"
        ).read_text(encoding="utf-8")
        self.assertIn("sys.path.insert(0, str(ROOT))", verifier)
        self.assertLess(
            verifier.index("sys.path.insert"),
            verifier.index("from run import app"),
        )
        for path in (
            "/parametros/api/viewer-profiles",
            "/parametros/api/formats",
            "/parametros/api/clients",
            "/parametros/api/campaigns",
        ):
            self.assertIn(path, verifier)

        frontend = (
            root / "aicentralv2" / "static" / "js" / "modelagem_criativos.js"
        ).read_text(encoding="utf-8")
        self.assertIn("Promise.allSettled", frontend)
        self.assertIn("failures.join", frontend)


if __name__ == "__main__":
    unittest.main()
