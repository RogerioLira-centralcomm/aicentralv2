"""Testes isolados da Modelagem de Criativos, sem PostgreSQL ou APIs reais."""

import base64
from io import BytesIO
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from flask import Blueprint, Flask
from jinja2 import Environment
from werkzeug.datastructures import FileStorage

from aicentralv2.creative_brand_analysis import CreativeBrandAnalyzer
from aicentralv2.creative_modeling_generation import (
    CreativeGenerationClient,
    build_higgsfield_payload,
    normalize_image_aspect_ratio,
)
from aicentralv2.creative_modeling_repository import scene_count_for_format
from aicentralv2.creative_modeling_routes import register_creative_modeling_routes
from aicentralv2.creative_modeling_service import CreativeModelingService


class FakeRepository:
    def __init__(self):
        self.clients = []
        self.created_campaign = None
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

    def list_campaign_clients(self):
        return [{
            "selection_key": "crm:42",
            "source": "crm",
            "profile_status": "minimal",
            "crm_client_id": 42,
            "profile_id": None,
            "name": "Cliente CRM",
        }]

    def create_campaign_with_variation_a(self, data):
        self.created_campaign = data
        return {"id": 30, "variation_id": 20, "step_id": 8}

    def get_campaign(self, campaign_id):
        return {
            "id": campaign_id,
            "name": self.created_campaign["name"],
            "client": {"id": 10, "name": "Marca Exemplo"},
            "variations": [{
                "id": 20,
                "label": "A",
                "steps": [{
                    "id": 8,
                    "format_template_id": 7,
                    "mockup": "portal",
                }],
            }],
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
            "website_url": "https://example.com",
            "brand_profile": {
                "brand_summary": "Soluções seguras para morar bem.",
                "target_audience": "Famílias buscando o primeiro imóvel.",
                "ad_segments": ["Primeiro imóvel", "Investimento"],
                "creative_guidelines": "Arquitetura real, luz natural e pouco texto.",
            },
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


class CreativeBrandAnalyzerTest(unittest.TestCase):
    @patch(
        "aicentralv2.creative_brand_analysis._compact_web_evidence",
        return_value=(
            {
                "source_url": "https://marca.com.br",
                "title": "Marca",
                "logo_url": "https://marca.com.br/logo.svg",
            },
            {"logo_url": "https://marca.com.br/logo.svg"},
        ),
    )
    def test_cruza_site_imagem_e_normaliza_resultado(self, _evidence):
        captured = {}

        def llm(messages, **kwargs):
            captured["messages"] = messages
            captured["model"] = kwargs["model"]
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "name": "Marca",
                            "sector": "Varejo",
                            "brand_summary": "Produtos para o dia a dia.",
                            "tone_of_voice": "Direto e acolhedor",
                            "primary_color": "#123abc",
                            "secondary_color": "#fedcba",
                            "target_audience": "Famílias urbanas.",
                            "ad_segments": ["Economia", "Conveniência"],
                            "creative_guidelines": "Produto em uso real.",
                            "campaign_opportunities": ["Datas sazonais"],
                            "confidence": {
                                "identity": 0.9,
                                "audience": 0.7,
                                "visual": 0.8,
                            },
                            "sources": ["https://marca.com.br"],
                        }
                    )
                },
                "model": kwargs["model"],
            }

        image = FileStorage(
            stream=BytesIO(b"fake-image-content" * 4),
            filename="referencia.png",
            content_type="image/png",
        )
        result = CreativeBrandAnalyzer(llm=llm).analyze("marca.com.br", image)

        self.assertEqual(captured["model"], "perplexity/sonar-pro")
        self.assertEqual(result["primary_color"], "#123ABC")
        self.assertEqual(result["logo_url"], "https://marca.com.br/logo.svg")
        self.assertEqual(result["analysis_metadata"]["source_types"], ["url", "image"])
        user_content = captured["messages"][1]["content"]
        self.assertEqual(user_content[1]["type"], "image_url")

    def test_bloqueia_url_local(self):
        with self.assertRaisesRegex(ValueError, "site público"):
            CreativeBrandAnalyzer(llm=Mock()).analyze("http://127.0.0.1")


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

    def test_cliente_salva_base_enriquecida(self):
        self.service.create_client(
            {
                "name": "Cliente",
                "website_url": "https://example.com",
                "brand_summary": "Marca premium.",
                "target_audience": "Adultos urbanos.",
                "ad_segments": ["Conveniência", "Qualidade"],
                "creative_guidelines": "Fotografia editorial.",
                "campaign_opportunities": ["Lançamento"],
                "analysis_metadata": {"model": "perplexity/sonar-pro"},
            }
        )
        saved = self.repo.clients[0]
        self.assertEqual(saved["website_url"], "https://example.com")
        self.assertEqual(
            saved["brand_profile"]["ad_segments"], ["Conveniência", "Qualidade"]
        )
        self.assertEqual(
            saved["analysis_metadata"]["model"], "perplexity/sonar-pro"
        )

    def test_banner_estatico_tem_uma_cena_e_demais_formatos_quatro(self):
        self.assertEqual(scene_count_for_format({
            "mechanic": "static_display",
            "behavior_spec": {"type": "static"},
        }), 1)
        self.assertEqual(scene_count_for_format({
            "mechanic": "reveal",
            "behavior_spec": {"type": "interactive"},
        }), 4)
        self.assertIn(
            "Opening hook",
            CreativeModelingService.scene_role(1, 4),
        )
        self.assertIn(
            "CTA",
            CreativeModelingService.scene_role(4, 4),
        )

    def test_campanha_crm_cria_primeiro_step_no_mesmo_comando(self):
        result = self.service.create_campaign({
            "client_source": "crm",
            "client_id": 42,
            "name": "Campanha integrada",
            "budget_usd": 5,
            "show_price": False,
            "first_step": {
                "format_template_id": 7,
                "mockup": "portal",
            },
        })
        saved = self.repo.created_campaign
        self.assertEqual(saved["client_source"], "crm")
        self.assertEqual(saved["client_id"], 42)
        self.assertEqual(saved["first_step"]["format_template_id"], 7)
        self.assertEqual(result["created_step_id"], 8)
        self.assertEqual(result["variations"][0]["steps"][0]["id"], 8)

    def test_campanha_exige_primeiro_formato_valido(self):
        with self.assertRaisesRegex(ValueError, "Formato inicial"):
            self.service.create_campaign({
                "client_source": "creative",
                "client_id": 10,
                "name": "Sem formato",
            })
        with self.assertRaisesRegex(ValueError, "Ambiente inicial inválido"):
            self.service.create_campaign({
                "client_source": "creative",
                "client_id": 10,
                "name": "Mockup inválido",
                "first_step": {
                    "format_template_id": 7,
                    "mockup": "outdoor",
                },
            })

    def test_plano_cria_producao_por_formato_com_cenas(self):
        repository = Mock()
        repository.create_campaign_with_productions.return_value = {
            "id": 30,
            "productions": [{"id": 50}],
        }
        repository.get_campaign.return_value = {
            "id": 30,
            "name": "Campanha por cenas",
        }
        repository.get_production.return_value = {
            "id": 50,
            "scene_count": 4,
            "scenes": [{"id": index} for index in range(1, 5)],
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        result = service.create_production_plan({
            "client_source": "crm",
            "client_id": 42,
            "name": "Campanha por cenas",
            "budget_usd": 5,
            "productions": [{
                "format_template_id": 7,
                "scene_descriptions": ["Abertura", "Produto", "Benefício", "CTA"],
            }],
        })
        saved = repository.create_campaign_with_productions.call_args.args[0]
        self.assertEqual(saved["productions"][0]["format_template_id"], 7)
        self.assertEqual(len(saved["productions"][0]["scene_descriptions"]), 4)
        self.assertEqual(len(result["productions"][0]["scenes"]), 4)

    def test_prompt_deterministico_contem_variacao_e_identidades(self):
        context = self.repo.get_step_context(8)
        prompt = self.service.build_prompt(context, context["step"], 2)
        self.assertIn("[VARIAÇÃO A — STEP 1]", prompt)
        self.assertIn("Cor primária da marca: #1E4D4F", prompt)
        self.assertIn("Público-alvo: Famílias buscando o primeiro imóvel.", prompt)
        self.assertIn("Segmentos/ângulos recomendados: Primeiro imóvel", prompt)
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


class FakeHttpErrorResponse:
    status_code = 402

    def raise_for_status(self):
        raise requests.HTTPError(response=self)

    def json(self):
        return {"error": {"message": "Insufficient credits"}}


class FakeHttpError:
    def post(self, url, **kwargs):
        return FakeHttpErrorResponse()


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
        self.assertEqual(http.payload["resolution"], "2K")
        self.assertNotIn("size", http.payload)
        self.assertEqual(http.payload["background"], "opaque")
        self.assertEqual(result["actual_cost_usd"], 0.13)

    def test_proporcao_iab_e_normalizada_para_modelo_de_imagem(self):
        self.assertEqual(normalize_image_aspect_ratio("6:5"), "4:3")
        self.assertEqual(normalize_image_aspect_ratio("1:2"), "9:16")
        self.assertEqual(normalize_image_aspect_ratio("91:11"), "21:9")

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test"})
    def test_erro_de_credito_openrouter_e_acionavel(self):
        client = CreativeGenerationClient(http=FakeHttpError())
        with self.assertRaisesRegex(RuntimeError, "saldo.*insuficiente"):
            client.generate_image("prompt", aspect_ratio="16:9")

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
        service.list_campaign_clients.return_value = [{
            "selection_key": "crm:42",
            "name": "Cliente CRM",
        }]
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
            campaign_clients = self.client.get("/parametros/api/campaign-clients")
            campaigns = self.client.get("/parametros/api/campaigns")
        for response in (formats, viewers, clients, campaign_clients, campaigns):
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()["success"])

    def test_api_cria_campanha_com_step_atomico(self):
        service = Mock()
        service.create_campaign.return_value = {
            "id": 30,
            "created_step_id": 8,
            "variations": [{"id": 20, "steps": [{"id": 8}]}],
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        payload = {
            "client_source": "crm",
            "client_id": 42,
            "name": "Campanha integrada",
            "first_step": {"format_template_id": 7, "mockup": "portal"},
        }
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/campaigns",
                json=payload,
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["data"]["created_step_id"], 8)
        service.create_campaign.assert_called_once_with(payload)

    def test_apis_de_producao_operam_cenas_individuais(self):
        service = Mock()
        service.create_production_plan.return_value = {
            "campaign": {"id": 30},
            "productions": [{"id": 50, "scenes": [{"id": 51}]}],
        }
        service.production_detail.return_value = {
            "id": 50,
            "scenes": [{"id": 51, "status": "ready"}],
        }
        service.generate_scene_prompt.return_value = {"scene_id": 51}
        service.review_scene_prompt.return_value = {
            "id": 51,
            "prompt_status": "approved",
        }
        service.generate_scene.return_value = {"asset": {"id": 70}}
        service.review_scene.return_value = {"id": 51, "status": "approved"}
        service.select_scene_preview_asset.return_value = {
            "id": 50,
            "selected_asset_id": 70,
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            plan = self.client.post(
                "/parametros/api/production-plans",
                json={
                    "client_id": 42,
                    "name": "Campanha",
                    "productions": [{"format_template_id": 7}],
                },
            )
            detail = self.client.get("/parametros/api/productions/50")
            prompt = self.client.post("/parametros/api/scenes/51/prompt/generate")
            prompt_review = self.client.put(
                "/parametros/api/scenes/51/prompt",
                json={"prompt": "Direção", "approved": True},
            )
            image = self.client.post("/parametros/api/scenes/51/image/generate")
            review = self.client.put(
                "/parametros/api/scenes/51/review",
                json={"asset_id": 70, "status": "approved"},
            )
            preview = self.client.put(
                "/parametros/api/scenes/51/preview-asset",
                json={"asset_id": 70},
            )
        self.assertEqual(plan.status_code, 201)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(prompt.status_code, 201)
        self.assertEqual(prompt_review.status_code, 200)
        self.assertEqual(image.status_code, 201)
        self.assertEqual(review.status_code, 200)
        self.assertEqual(preview.status_code, 200)

    def test_api_analisa_site_e_imagem(self):
        service = Mock()
        service.analyze_brand.return_value = {
            "name": "Marca",
            "target_audience": "Famílias urbanas",
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/clients/analyze-brand",
                data={
                    "website_url": "https://marca.com.br",
                    "image": (BytesIO(b"image-data"), "marca.png"),
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["name"], "Marca")
        args = service.analyze_brand.call_args.args
        self.assertEqual(args[0], "https://marca.com.br")
        self.assertEqual(args[1].filename, "marca.png")


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
        self.assertIn("modelagem_criativos.css') }}?v=9", page)
        self.assertIn("modelagem_criativos.js') }}?v=9", page)
        for tab in ("preparar", "produzir", "formatos", "marcas", "historico"):
            self.assertIn(f'data-tab="{tab}"', page)
        self.assertNotIn("Variações A/B", page)
        generator = (template_dir / "_mc_gerador.html").read_text(encoding="utf-8")
        self.assertIn("mc-generator-workspace", generator)
        self.assertIn('id="mcGeneratorFormatList"', generator)
        self.assertIn('form="mcCampaignForm"', generator)
        self.assertIn('name="client_ref"', generator)
        self.assertIn("Iniciar produção", generator)
        self.assertNotIn("Variação A", generator)
        production = (
            template_dir / "_mc_variacoes.html"
        ).read_text(encoding="utf-8")
        self.assertIn('id="mcSceneRail"', production)
        self.assertIn('id="mcProductionStage"', production)
        self.assertIn("Bancada de produção", production)
        self.assertNotIn("mcBudgetStrip", production)
        self.assertNotIn("Orçamento", production)
        self.assertNotIn("mcGlobalContext", page)
        production_js = (
            root / "aicentralv2" / "static" / "js" / "modelagem_criativos.js"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Confirmar consumo de saldo", production_js)
        self.assertNotIn("Saldo atual:", production_js)
        self.assertIn("runProductionAction(action, button)", production_js)
        self.assertIn("title: 'Remover variação'", production_js)
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
        clients = (template_dir / "_mc_clientes.html").read_text(encoding="utf-8")
        self.assertIn('id="mcAnalyzeBrand"', clients)
        self.assertIn('name="target_audience"', clients)

    def test_migration_cria_vinculo_crm_antes_do_indice(self):
        root = Path(__file__).resolve().parents[1]
        migration = (
            root / "migrations" / "create_creative_modeling.sql"
        ).read_text(encoding="utf-8")
        compatibility_start = migration.index("ALTER TABLE cx_clients")
        add_column = migration.index(
            "ADD COLUMN IF NOT EXISTS crm_client_id",
            compatibility_start,
        )
        foreign_key = migration.index(
            "constraint_row.confrelid = 'tbl_cliente'::regclass",
            add_column,
        )
        unique_index = migration.index(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_clients_crm_client",
            add_column,
        )

        self.assertLess(add_column, foreign_key)
        self.assertLess(foreign_key, unique_index)
        self.assertNotIn(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_clients_crm_client",
            migration[:add_column],
        )

        incremental = (
            root / "migrations" / "add_creative_campaign_flow.sql"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "constraint_row.confrelid = 'tbl_cliente'::regclass",
            incremental,
        )
        self.assertIn("column_row.attname = 'crm_client_id'", incremental)

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
        self.assertIn("brand_profile JSONB", migration)
        self.assertIn("analysis_metadata JSONB", migration)
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
            '"$VENV_PYTHON" migrations/run_add_creative_campaign_flow.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_add_creative_scene_productions.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" scripts/seed_creative_formats.py',
            deploy,
        )
        self.assertLess(
            deploy.index('"$VENV_PYTHON" scripts/seed_creative_formats.py'),
            deploy.index(
                '"$VENV_PYTHON" migrations/run_seed_creative_format_layouts.py'
            ),
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
            "/parametros/api/campaign-clients",
            "/parametros/api/campaigns",
        ):
            self.assertIn(path, verifier)

        frontend = (
            root / "aicentralv2" / "static" / "js" / "modelagem_criativos.js"
        ).read_text(encoding="utf-8")
        self.assertIn("Promise.allSettled", frontend)
        self.assertIn("failures.join", frontend)
        create_start = frontend.index("async function createCampaign")
        create_end = frontend.index("// ====== VARIAÇÕES", create_start)
        create_flow = frontend[create_start:create_end]
        self.assertIn("data.productions", create_flow)
        self.assertIn("/parametros/api/production-plans", create_flow)
        self.assertIn("production?.scenes?.[0]?.id", create_flow)
        self.assertNotIn("/parametros/api/variations/", create_flow)
        self.assertIn("campaignClients: '/parametros/api/campaign-clients'", frontend)
        self.assertIn("function sceneCountForFormat", frontend)
        self.assertIn("function renderProduction", frontend)
        self.assertIn("/parametros/api/scenes/${scene.id}", frontend)
        self.assertIn("format.media_type === 'image'", frontend)
        campaign_flow_sql = (
            root / "migrations" / "add_creative_campaign_flow.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("crm_client_id", campaign_flow_sql)
        self.assertIn("display_motion_payload", campaign_flow_sql)
        repository = (
            root / "aicentralv2" / "creative_modeling_repository.py"
        ).read_text(encoding="utf-8")
        self.assertIn("SET position = position + 1000", repository)
        self.assertNotIn("SET position = -position", repository)
        scene_migration = (
            root / "migrations" / "add_creative_scene_productions.sql"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS cx_creative_productions",
            scene_migration,
        )
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS cx_creative_scenes",
            scene_migration,
        )
        self.assertIn("ADD COLUMN IF NOT EXISTS scene_id", scene_migration)


if __name__ == "__main__":
    unittest.main()
