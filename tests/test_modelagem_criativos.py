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
from aicentralv2.creative_format_compose import compose_native_piece, png_size
from aicentralv2.creative_format_geometry import (
    SOCIAL_FORMAT_SLUGS,
    SOCIAL_PAINT_FAMILIES,
    canvas_mismatch,
    compose_layout,
    default_render_mode,
    format_direction,
    format_family_spec,
    should_compose,
)
from aicentralv2.creative_modeling_generation import (
    BRIEF_SYSTEM,
    SCENE_BEAT_SYSTEM,
    TEXT_TEMPERATURES,
    CreativeGenerationClient,
    build_higgsfield_payload,
    normalize_image_aspect_ratio,
    text_temperature,
)
from aicentralv2.creative_modeling_fx import reset_rate_cache
from aicentralv2.creative_modeling_prompts import (
    apply_render_mode_to_prompt,
    unfold_ab_instruction,
    unfold_image_lock,
)
from aicentralv2.creative_modeling_repository import scene_count_for_format
from aicentralv2.creative_modeling_routes import register_creative_modeling_routes
from aicentralv2.creative_image_fidelity import (
    apply_publish_upgrade,
    quote_image_publish,
    resolve_image_tier,
)
from aicentralv2.creative_modeling_service import (
    CreativeModelingService,
    _quality_review_data,
    client_identity_payload,
    hydrate_client_from_creative_line,
)


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

    def update_client(self, client_id, data):
        if self.clients:
            self.clients[0].update(data)
        else:
            self.clients.append(data)
        return client_id

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

    def add_generated_asset(self, job_id, step_id, asset_type, url, metadata, scene_id=None):
        return {"id": 99, "asset_url": url, "status": "done", "scene_id": scene_id}

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

    def list_campaigns(self):
        return []


class FakeGenerator:
    def generate_campaign_brief(self, context):
        count = context["format"]["scene_count"]
        roles = (
            ["composição_final"]
            if count == 1
            else ["gancho", "contexto_produto", "beneficio", "fechamento"]
        )
        return {
            "result": {
                "campaign_text": "Mensagem aprimorada em português.",
                "cta_text": "Conheça agora",
                "visual_bible": "Luz natural, fundo azul e produto sempre consistente.",
                "scenes": [
                    {
                        "position": index,
                        "role": role,
                        "description": f"Cena complementar {index} em português.",
                    }
                    for index, role in enumerate(roles, start=1)
                ],
            },
            "model": "openai/gpt-test",
            "usage": {"total_tokens": 40},
        }

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

    def generate_image(self, prompt, references, aspect_ratio, **kwargs):
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

    def extract_kv_locks(self, context, image_data_url=None):
        return {
            "result": {
                "headline": "Coleção Outono",
                "subhead": "Luz e linho",
                "cta": "Conheça a coleção",
                "other_lines": [],
                "has_logo": True,
            },
            "model": "openai/gpt-test",
            "usage": {},
            "actual_cost_usd": 0.001,
        }

    def generate_ab_prompt(self, context, level):
        return {
            "result": {
                "prompt_en": "Recolor only. Same crop.",
                "rationale_pt": "Variação simples.",
                "checks": [],
                "variant_level": level,
            },
            "model": "openai/gpt-test",
            "usage": {},
            "actual_cost_usd": 0.01,
        }

    def review_image(self, context, image_data_url):
        return {
            "result": {
                "approved_recommendation": True,
                "score": 94,
                "warnings": [],
                "checks": {"language_pt_br": True, "continuity": True},
            },
            "actual_cost_usd": 0.002,
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

        self.assertEqual(captured["model"], "openai/gpt-5.4")
        self.assertEqual(result["primary_color"], "#123ABC")
        self.assertEqual(result["logo_url"], "https://marca.com.br/logo.svg")
        self.assertEqual(result["analysis_metadata"]["source_types"], ["url", "image"])
        user_content = captured["messages"][1]["content"]
        self.assertEqual(user_content[1]["type"], "image_url")

    def test_bloqueia_url_local(self):
        with self.assertRaisesRegex(ValueError, "site público"):
            CreativeBrandAnalyzer(llm=Mock()).analyze("http://127.0.0.1")

    @patch(
        "aicentralv2.creative_brand_analysis._compact_web_evidence",
        return_value=(
            {
                "source_url": "https://marca.com.br",
                "screenshot": "https://cdn.marca.com/screenshot.png",
                "asset_candidates": [],
                "pages": [],
            },
            {"logo_url": None},
        ),
    )
    def test_refina_paleta_com_modelo_visual_e_pixels_do_site(self, _evidence):
        calls = []

        def llm(messages, **kwargs):
            calls.append((messages, kwargs))
            if len(calls) == 1:
                content = {
                    "name": "Marca",
                    "primary_color": "#111111",
                    "secondary_color": "#222222",
                }
            else:
                content = {
                    "primary_color": "#7A1632",
                    "secondary_color": "#E8D8C8",
                    "color_palette": [
                        {
                            "hex": "#7A1632",
                            "name": "Vinho institucional",
                            "usage": "Assinatura e CTA",
                            "confidence": 0.94,
                        },
                        {
                            "hex": "#E8D8C8",
                            "name": "Areia",
                            "usage": "Fundos",
                            "confidence": 0.83,
                        },
                    ],
                }
            return {
                "message": {"content": json.dumps(content)},
                "model": kwargs["model"],
            }

        result = CreativeBrandAnalyzer(llm=llm).analyze("marca.com.br")

        self.assertEqual([call[1]["model"] for call in calls], [
            "perplexity/sonar-pro",
            "openai/gpt-5.4",
        ])
        self.assertEqual(result["primary_color"], "#7A1632")
        self.assertEqual(result["color_palette"][0]["usage"], "Assinatura e CTA")
        self.assertEqual(result["analysis_metadata"]["visual_evidence_count"], 1)

    def test_aprende_linha_criativa_e_normaliza_instrucao_para_image_2(self):
        def llm(_messages, **kwargs):
            return {
                "message": {
                    "content": json.dumps({
                        "signature_summary": "Produto central e luz lateral suave.",
                        "color_palette": [{
                            "hex": "#6A1538",
                            "name": "Vinho",
                            "usage": "Assinatura",
                            "confidence": 0.9,
                        }],
                        "composition_rules": ["Produto ocupa o terço central."],
                        "imagery_rules": ["Luz natural lateral."],
                        "typography_rules": ["Título curto no topo."],
                        "graphic_devices": ["Faixa fina vinho."],
                        "copy_patterns": ["Poucas palavras."],
                        "copy_system": {
                            "headline_structure": "Título curto no topo, sem oferta.",
                            "body_density": "Uma linha de apoio.",
                            "legal_presence": "Ausente",
                            "typography": {
                                "role": "sans",
                                "case": "caixa alta",
                                "weight": "bold",
                                "family": "Gotham",
                            },
                            "placement": {
                                "logo": {"prose": "Canto superior esquerdo", "anchor": "topo"},
                                "headline": "Faixa central",
                                "product": {"prose": "Produto no centro", "anchor": "centro"},
                                "cta": {"prose": "Botão na base", "anchor": "base"},
                            },
                            "cta": {
                                "visual_pattern": "Pílula sólida no canto inferior",
                                "position": "base",
                                "case": "caixa alta",
                                "shape": "pílula",
                                "recurrent": True,
                            },
                            "observed_cta_patterns": ["Verbo + benefício curto"],
                        },
                        "must_preserve": ["Respiro amplo."],
                        "avoid": ["Fundos saturados."],
                        "confidence": 0.9,
                        "caveats": ["Amostra de uma única campanha."],
                        "gpt_image_instruction": "Preserve generous negative space.",
                    })
                },
                "model": kwargs["model"],
            }

        result = CreativeBrandAnalyzer(llm=llm).analyze_creative_line(
            ["data:image/png;base64,aW1hZ2U="],
            {"name": "Marca", "brand_profile": {}},
        )

        self.assertEqual(result["source_count"], 1)
        self.assertIn("negative space", result["gpt_image_instruction"])
        self.assertEqual(result["color_palette"][0]["hex"], "#6A1538")
        self.assertEqual(result["confidence"], 0.55)
        self.assertEqual(result["copy_system"]["headline_structure"], "Título curto no topo, sem oferta.")
        self.assertEqual(result["copy_system"]["placement"]["cta"]["anchor"], "base")
        self.assertEqual(result["copy_system"]["cta"]["confidence"], "hypothesis")
        self.assertFalse(result["copy_system"]["cta"]["recurrent"])
        self.assertIsNone(result["copy_system"]["typography"]["family"])
        self.assertIn("hipótese", result["caveats"][-1])

    def test_duas_pecas_confirmam_cta_e_fonte_como_regra(self):
        def llm(_messages, **kwargs):
            return {
                "message": {
                    "content": json.dumps({
                        "signature_summary": "Família visual recorrente.",
                        "copy_system": {
                            "headline_structure": "Título curto.",
                            "typography": {"role": "sans", "family": "Gotham"},
                            "cta": {
                                "visual_pattern": "Pílula na base",
                                "recurrent": True,
                            },
                        },
                        "confidence": 0.8,
                        "gpt_image_instruction": "Keep the CTA pill at the base.",
                    })
                },
                "model": kwargs["model"],
            }

        result = CreativeBrandAnalyzer(llm=llm).analyze_creative_line(
            [
                "data:image/png;base64,aW1hZ2U=",
                "data:image/png;base64,aW1hZ2U=",
            ],
            {"name": "Marca", "brand_profile": {}},
        )

        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["confidence"], 0.8)
        self.assertTrue(result["copy_system"]["cta"]["recurrent"])
        self.assertEqual(result["copy_system"]["cta"]["confidence"], "observed")
        self.assertEqual(result["copy_system"]["typography"]["family"], "Gotham")

    def test_coleta_paginas_e_imagens_do_dominio_oficial(self):
        from aicentralv2 import creative_brand_analysis as analysis

        home = {
            "branding": {"logo": "/assets/logo.svg"},
            "links": [
                "https://marca.com.br/sobre",
                "https://marca.com.br/produtos",
                "https://terceiro.example/banner",
            ],
            "images": ["/hero.jpg", "/produtos/anel.webp"],
            "markdown": "# Marca",
        }
        page = {
            "images": ["/campanhas/presente.jpg"],
            "markdown": "Joias para momentos importantes.",
        }
        with patch.object(
            analysis,
            "_firecrawl_scrape_com_variantes",
            return_value=(home, "https://marca.com.br"),
        ), patch.object(
            analysis,
            "_firecrawl_scrape",
            return_value=page,
        ) as scrape, patch.object(
            analysis,
            "_firecrawl_image_search",
            return_value=[],
        ):
            evidence, record = analysis._compact_web_evidence(
                "https://marca.com.br"
            )

        self.assertEqual(record["logo_url"], "https://marca.com.br/assets/logo.svg")
        self.assertEqual(len(evidence["pages"]), 3)
        self.assertEqual(scrape.call_count, 2)
        urls = [item["url"] for item in evidence["asset_candidates"]]
        self.assertIn("https://marca.com.br/produtos/anel.webp", urls)
        self.assertNotIn("https://terceiro.example/banner", urls)

    def test_og_image_nao_e_promovida_a_logo_sem_evidencia(self):
        from aicentralv2 import creative_brand_analysis as analysis

        with patch.object(
            analysis,
            "_firecrawl_scrape_com_variantes",
            return_value=(
                {"branding": {"images": {"ogImage": "/campanha.jpg"}}},
                "https://marca.com.br",
            ),
        ), patch.object(analysis, "_firecrawl_image_search", return_value=[]):
            evidence, record = analysis._compact_web_evidence(
                "https://marca.com.br"
            )

        self.assertIsNone(record["logo_url"])
        self.assertTrue(evidence["reference_images"])


class CreativeBrandAssetStorageTest(unittest.TestCase):
    def test_bloqueia_download_para_endereco_privado(self):
        from aicentralv2 import creative_modeling_storage as storage

        with patch.object(
            storage.socket,
            "getaddrinfo",
            return_value=[(None, None, None, None, ("127.0.0.1", 443))],
        ):
            with self.assertRaisesRegex(ValueError, "endereço público"):
                storage._validated_public_asset_url(
                    "https://arquivos.marca.com/logo.png"
                )


class CreativeServiceTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.service = CreativeModelingService(
            repository=self.repo,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )

    def test_referencias_aprovadas_da_marca_preenchem_vagas_da_geracao(self):
        self.repo.list_client_brand_assets = lambda _client_id: [
            {
                "id": 31,
                "asset_path": "/static/uploads/creative_references/marca.png",
                "mime_type": "image/png",
                "metadata": {"original_name": "marca.png"},
            }
        ]
        urls = []
        used = self.service._append_brand_references(10, urls, job_id=4)

        self.assertEqual(len(urls), 1)
        self.assertEqual(used[0]["id"], 31)

    def test_logo_completa_vaga_quando_ja_ha_ref_da_campanha(self):
        self.repo.list_client_brand_assets = lambda _client_id: [
            {
                "id": 41,
                "role": "creative",
                "asset_path": "/static/uploads/creative_references/antiga.png",
                "mime_type": "image/png",
            },
            {
                "id": 42,
                "role": "logo",
                "asset_path": "/static/uploads/creative_references/logo.png",
                "mime_type": "image/png",
            },
        ]
        urls = ["data:image/png;base64,pack"]
        used = self.service._append_brand_references(10, urls, job_id=4)

        self.assertEqual(len(urls), 2)
        self.assertEqual([item["id"] for item in used], [42])

    def test_aprendizado_da_linha_criativa_persiste_no_perfil(self):
        self.repo.list_client_brand_assets = lambda _client_id: [{
            "id": 41,
            "role": "creative",
            "asset_path": "/static/uploads/creative_references/campanha.png",
            "mime_type": "image/png",
        }]
        updated = {}
        self.repo.update_client_brand_profile = (
            lambda client_id, profile: updated.update(
                {"client_id": client_id, "profile": profile}
            )
        )
        self.service.brand_analyzer = Mock()
        self.service.brand_analyzer.analyze_creative_line.return_value = {
            "signature_summary": "Produto central com muito respiro.",
            "gpt_image_instruction": "Keep the product centered.",
            "source_count": 1,
        }

        result = self.service.learn_client_creative_line(10, [])

        self.assertEqual(result["creative_line"]["source_count"], 1)
        self.assertEqual(updated["client_id"], 10)
        self.assertIn("creative_line", updated["profile"])
        self.assertEqual(
            updated["profile"]["brand_summary"],
            "Produto central com muito respiro.",
        )

    def test_auditoria_pronta_hidrata_marca_e_payload_da_geracao(self):
        client = hydrate_client_from_creative_line({
            "name": "TIM CELULAR S.A.",
            "sector": None,
            "tone_of_voice": None,
            "primary_color": None,
            "secondary_color": None,
            "brand_profile": {
                "creative_line": {
                    "signature_summary": "Banners azuis com oferta à esquerda.",
                    "copy_patterns": [
                        "Copy curta com número dominante.",
                        "CTAs duplos na base esquerda.",
                    ],
                    "composition_rules": ["Informação à esquerda e hero à direita."],
                    "must_preserve": ["Azul profundo e números grandes."],
                    "avoid": ["Paletas quentes."],
                    "graphic_devices": ["Gradientes azuis."],
                    "color_palette": [
                        {"hex": "#082C9C", "name": "azul TIM"},
                        {"hex": "#FFFFFF", "name": "branco"},
                        {"hex": "#ED1C3A", "name": "vermelho TIM"},
                    ],
                }
            },
        })
        self.assertEqual(client["primary_color"], "#082C9C")
        self.assertEqual(client["secondary_color"], "#ED1C3A")
        self.assertIn("Copy curta", client["tone_of_voice"])
        self.assertEqual(
            client["brand_profile"]["brand_summary"],
            "Banners azuis com oferta à esquerda.",
        )
        self.assertEqual(client["brand_profile"]["color_palette"][0]["hex"], "#082C9C")

        identity = client_identity_payload({
            "client_name": "TIM CELULAR S.A.",
            "client_sector": None,
            "tone_of_voice": None,
            "logo_upload_path": "/static/uploads/client_logos/tim.webp",
            "logo_url": None,
            "primary_color": None,
            "secondary_color": None,
            "brand_profile": client["brand_profile"],
        })
        self.assertEqual(identity["logo"], "/static/uploads/client_logos/tim.webp")
        self.assertEqual(identity["primary_color"], "#082C9C")
        self.assertEqual(identity["tone"], client["tone_of_voice"])
        self.assertEqual(
            identity["profile"]["brand_summary"],
            "Banners azuis com oferta à esquerda.",
        )

    def test_prompt_injeta_dna_criativo_aprendido_para_gpt_image_2(self):
        context = self.repo.get_step_context(8)
        context["brand_profile"] = {
            "creative_line": {
                "signature_summary": "Produto central e fundo com respiro.",
                "composition_rules": ["Produto no terço central."],
                "must_preserve": ["Luz lateral suave."],
                "avoid": ["Fundos saturados."],
                "gpt_image_instruction": "Keep generous negative space.",
            }
        }
        prompt = self.service.build_prompt(
            context, context["step"], 1
        )

        self.assertIn("Assinatura aprendida de criativos reais", prompt)
        self.assertIn("[INSTRUÇÃO APRENDIDA PARA GPT IMAGE 2]", prompt)
        self.assertIn("Keep generous negative space.", prompt)

    def test_prompt_injeta_sistema_de_copy_aprendido(self):
        context = self.repo.get_step_context(8)
        context["brand_profile"] = {
            "creative_line": {
                "signature_summary": "Produto central.",
                "copy_system": {
                    "headline_structure": "Título curto no topo.",
                    "body_density": "Uma linha.",
                    "typography": {
                        "role": "sans",
                        "case": "caixa alta",
                        "weight": "bold",
                        "confidence": "observed",
                    },
                    "cta": {
                        "visual_pattern": "Pílula na base",
                        "position": "base",
                        "confidence": "observed",
                    },
                },
                "gpt_image_instruction": "Keep generous negative space.",
            }
        }
        prompt = self.service.build_prompt(context, context["step"], 1)

        self.assertIn("[SISTEMA DE COPY APRENDIDO]", prompt)
        self.assertIn("Título curto no topo.", prompt)
        self.assertIn("Pílula na base", prompt)

    def test_campanha_nova_nasce_com_prompt_herdado_do_storyboard(self):
        from aicentralv2.creative_modeling_prompts import build_inherited_scene_prompt

        prompt = build_inherited_scene_prompt(
            "Luz natural e produto consistente.",
            "Abertura com o produto no centro.",
            "Saiba mais",
            1,
        )
        repository = (
            Path(__file__).resolve().parents[1]
            / "aicentralv2"
            / "creative_modeling_repository.py"
        ).read_text(encoding="utf-8")

        self.assertIn("INHERITED CAMPAIGN SYSTEM — scene 1", prompt)
        self.assertIn("Luz natural e produto consistente.", prompt)
        self.assertIn("Abertura com o produto no centro.", prompt)
        self.assertIn("Saiba mais", prompt)
        self.assertIn("build_inherited_scene_prompt", repository)
        self.assertIn("prompt_status, status", repository)

    def test_direcao_da_cena_nao_espera_aprovacao_da_anterior(self):
        repository = (
            Path(__file__).resolve().parents[1]
            / "aicentralv2"
            / "creative_modeling_repository.py"
        ).read_text(encoding="utf-8")
        create_job = repository.split("def create_generation_job", 1)[1].split(
            "\n    def ", 1
        )[0]
        update_prompt = repository.split("def update_scene_prompt", 1)[1].split(
            "\n    def ", 1
        )[0]

        self.assertIn('job_type == "prompt"', create_job)
        self.assertIn('"blocked"', create_job)
        self.assertIn("'blocked'", update_prompt)
        self.assertIn("'review'", update_prompt)
        self.assertIn("'approved'", update_prompt)

    def test_cena_seguinte_adapta_o_prompt_mae(self):
        captured = {}
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 52,
            "position": 2,
            "description": "Produto em close",
            "campaign_name": "Campanha",
            "campaign_id": 30,
            "production_id": 50,
            "format_template_id": 7,
            "master_prompt": "MASTER VISUAL SYSTEM for scene 1",
            "storyboard": [{"position": 1, "description": "Abertura"}],
            "creative_brief": {"visual_bible": "Luz natural"},
            "cta_text": "Saiba mais",
            "campaign_text": "Mensagem",
            "show_price": False,
            "objective": "Conversão",
            "client_name": "Marca",
            "client_sector": "Varejo",
            "tone_of_voice": "Direto",
            "logo_url": None,
            "logo_upload_path": None,
            "primary_color": "#1E4D4F",
            "secondary_color": "#9CCF31",
            "brand_profile": {},
            "scene_count": 4,
            "format_slug": "hotspot",
            "mechanic": "hotspot",
            "default_size": "1920x1080",
            "behavior_spec": {"type": "hotspot"},
            "layers": [{"role": "base_scene"}],
        }
        repository.create_generation_job.return_value = 3
        repository.update_scene_prompt.return_value = {
            "id": 52,
            "prompt": "Adapted",
            "prompt_status": "generated",
        }

        class CapturingGenerator(FakeGenerator):
            def generate_prompt(self, context):
                captured["context"] = context
                return super().generate_prompt(context)

        service = CreativeModelingService(
            repository=repository,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        service.generate_scene_prompt(52, payload={"delta": "mais recorte no produto"})

        self.assertFalse(captured["context"]["inherit_from_master"])
        self.assertIsNone(captured["context"]["master_prompt"])
        self.assertEqual(captured["context"]["campaign"]["beat"]["role"], "contexto")
        self.assertEqual(
            captured["context"]["campaign"]["scene_delta"],
            "mais recorte no produto",
        )
        self.assertIn("sequence_bible", captured["context"])

    def test_cena_inicial_expande_o_roteiro_mae(self):
        captured = {}
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 51,
            "position": 1,
            "description": "Abertura",
            "campaign_name": "Campanha",
            "campaign_id": 30,
            "production_id": 50,
            "format_template_id": 7,
            "master_prompt": "INHERITED CAMPAIGN SYSTEM — scene 1",
            "storyboard": [],
            "creative_brief": {"visual_bible": "Luz natural"},
            "cta_text": "Saiba mais",
            "campaign_text": "Mensagem",
            "show_price": False,
            "objective": "Conversão",
            "client_name": "Marca",
            "client_sector": "Varejo",
            "tone_of_voice": "Direto",
            "logo_url": None,
            "logo_upload_path": None,
            "primary_color": "#1E4D4F",
            "secondary_color": "#9CCF31",
            "brand_profile": {},
            "scene_count": 4,
        }
        repository.create_generation_job.return_value = 2
        repository.update_scene_prompt.return_value = {
            "id": 51,
            "prompt": "Master",
            "prompt_status": "generated",
        }

        class CapturingGenerator(FakeGenerator):
            def generate_prompt(self, context):
                captured["context"] = context
                return super().generate_prompt(context)

        service = CreativeModelingService(
            repository=repository,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        service.generate_scene_prompt(51)

        self.assertFalse(captured["context"]["inherit_from_master"])
        self.assertIsNone(captured["context"]["master_prompt"])

    def test_prompt_nativo_traz_px_e_budget_sem_mockup_de_device(self):
        captured = {}
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 51,
            "position": 1,
            "description": "Peça display",
            "campaign_name": "Campanha",
            "campaign_id": 30,
            "production_id": 50,
            "format_template_id": 7,
            "format_slug": "iab-leaderboard",
            "default_size": "728x90",
            "master_prompt": "",
            "storyboard": [],
            "creative_brief": {},
            "cta_text": "Saiba mais",
            "campaign_text": "Mensagem",
            "show_price": False,
            "objective": "Conversão",
            "client_name": "Marca",
            "client_sector": "Varejo",
            "tone_of_voice": "Direto",
            "logo_url": None,
            "logo_upload_path": None,
            "primary_color": "#1E4D4F",
            "secondary_color": "#9CCF31",
            "brand_profile": {},
            "scene_count": 1,
        }
        repository.create_generation_job.return_value = 2
        repository.update_scene_prompt.return_value = {
            "id": 51, "prompt": "Native", "prompt_status": "generated",
        }

        class CapturingGenerator(FakeGenerator):
            def generate_prompt(self, context):
                captured["context"] = context
                return super().generate_prompt(context)

        service = CreativeModelingService(
            repository=repository,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        service.generate_scene_prompt(51, payload={"render_mode": "native"})
        saved = repository.update_scene_prompt.call_args.args[1]
        self.assertEqual(captured["context"]["format"]["render_mode"], "native")
        self.assertIn("728x90", saved)
        self.assertIn("wide_banner", saved)
        self.assertIn("Element budget", saved)
        self.assertIn("NATIVE ADVERTISING STILL", saved)
        self.assertNotIn("CLIENT-PRESENTATION MOCKUP", saved)
        self.assertNotIn("DEVICE PRESENTATION", saved)

    @patch.dict("os.environ", {"USD_BRL_RATE": "5"})
    def test_campanha_e_historico_trazem_custo_em_reais(self):
        reset_rate_cache()
        repository = Mock()
        repository.list_campaigns.return_value = [{
            "id": 30, "name": "Campanha", "client": "Marca", "spent_usd": 2,
        }]
        repository.list_generation_jobs.return_value = [{
            "id": 1,
            "campaign_name": "Campanha",
            "job_type": "image",
            "model": "openai/gpt-image-2",
            "actual_cost_usd": 1.2,
            "estimated_cost_usd": 1,
            "status": "done",
        }]
        repository.get_campaign.return_value = {
            "id": 30, "name": "Campanha", "spent_usd": 2,
            "client": {"name": "Marca"},
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        campaigns = service.list_campaigns()
        history = service.history()
        detail = service.campaign_detail(30)
        self.assertEqual(campaigns[0]["spent_brl"], 10.0)
        self.assertEqual(history["jobs"][0]["spent_brl"], 6.0)
        self.assertEqual(history["modelings"][0]["spent_brl"], 10.0)
        self.assertEqual(history["total_brl"], 10.0)
        self.assertEqual(detail["spent_brl"], 10.0)
        reset_rate_cache()

    def test_adaptacao_nao_usa_contrato_from_scratch(self):
        captured = {}

        def llm(messages, **_kwargs):
            captured["system"] = messages[0]["content"]
            return {
                "message": {
                    "content": json.dumps({
                        "prompt_en": "Adapted production prompt",
                        "rationale_pt": "Mantém o sistema.",
                        "checks": [],
                    })
                },
                "model": "openai/gpt-test",
            }

        client = CreativeGenerationClient(text_callable=llm)
        client.generate_prompt({
            "inherit_from_master": True,
            "master_prompt": "MASTER",
        })

        self.assertIn("batida", captured["system"])
        self.assertIn("não variações", captured["system"])
        self.assertNotIn("from scratch", captured["system"].lower())

    def test_refine_de_asset_reusa_prompt_do_job(self):
        captured = {}
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 51,
            "position": 1,
            "production_id": 50,
            "campaign_id": 30,
            "format_template_id": 7,
            "prompt": "Approved scene prompt",
            "media_type": "image",
            "aspect_ratio": "16:9",
            "client_id": 10,
        }
        repository.get_assets.return_value = [{
            "id": 88,
            "scene_id": 51,
            "asset_url": "/asset-88.png",
            "job_prompt": "ORIGINAL JOB PROMPT for scene 1",
        }]
        repository.create_generation_job.return_value = 7
        repository.add_generated_asset.return_value = {
            "id": 89,
            "asset_url": "/generated.png",
        }
        repository.list_client_brand_assets.return_value = []

        class CapturingGenerator(FakeGenerator):
            def generate_image(self, prompt, references, aspect_ratio, **kwargs):
                captured["prompt"] = prompt
                captured["references"] = references
                return super().generate_image(prompt, references, aspect_ratio)

        service = CreativeModelingService(
            repository=repository,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        service.refine_scene_asset(
            51, 88, {"instruction": "CTA maior na base", "intent": "cta"}
        )

        self.assertIn("ORIGINAL JOB PROMPT for scene 1", captured["prompt"])
        self.assertIn("Refinement instruction: CTA maior na base", captured["prompt"])
        self.assertTrue(
            repository.create_generation_job.call_args.kwargs["allow_existing_scene"]
        )
        self.assertEqual(len(captured["references"]), 1)

    def test_refine_chrome_usa_instrucao_fixa_sem_texto_livre(self):
        captured = {}
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 51,
            "position": 1,
            "production_id": 50,
            "campaign_id": 30,
            "format_template_id": 7,
            "format_slug": "iab-leaderboard",
            "default_size": "728x90",
            "prompt": "Approved scene prompt",
            "media_type": "image",
            "aspect_ratio": "8:1",
            "client_id": 10,
        }
        repository.get_assets.return_value = [{
            "id": 88,
            "scene_id": 51,
            "asset_url": "/asset-88.png",
            "job_prompt": "ORIGINAL JOB PROMPT for scene 1",
            "metadata": {"render_mode": "native", "source_raster": "/raw.png"},
        }]
        repository.create_generation_job.return_value = 8
        repository.add_generated_asset.return_value = {
            "id": 89,
            "asset_url": "/generated.png",
        }
        repository.list_client_brand_assets.return_value = []

        class CapturingGenerator(FakeGenerator):
            def generate_image(self, prompt, references, aspect_ratio, **kwargs):
                captured["prompt"] = prompt
                return super().generate_image(prompt, references, aspect_ratio)

        service = CreativeModelingService(
            repository=repository,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        service.refine_scene_asset(51, 88, {"intent": "chrome"})
        self.assertIn("Remove all icon rows", captured["prompt"])
        self.assertEqual(
            repository.create_generation_job.call_args.kwargs["request_payload"][
                "refine_intent"
            ],
            "chrome",
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
        self.assertEqual(self.repo.clients[0]["crm_client_id"], 174)
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
                "color_palette": [{
                    "hex": "#7a1632",
                    "name": "Vinho",
                    "usage": "Assinatura",
                    "confidence": 0.91,
                }],
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
        self.assertEqual(
            saved["brand_profile"]["color_palette"][0]["hex"], "#7A1632"
        )
        self.service.update_client(
            10,
            {
                "name": "Cliente editado",
                "primary_color": "#123ABC",
                "secondary_color": "#FEDCBA",
                "brand_summary": "Marca atualizada.",
            },
        )
        self.assertEqual(self.repo.clients[0]["name"], "Cliente editado")
        self.assertEqual(
            self.repo.clients[0]["brand_profile"]["brand_summary"],
            "Marca atualizada.",
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
            "Opening beat",
            CreativeModelingService.scene_role(1, 4),
        )
        self.assertIn(
            "only if the format has one",
            CreativeModelingService.scene_role(4, 4),
        )
        hotspot = format_direction({
            "slug": "hotspot",
            "mechanic": "hotspot",
            "default_size": "1920x1080",
            "behavior_spec": {"type": "hotspot"},
            "layers": [{"role": "base_scene"}],
        })
        self.assertEqual(hotspot["size_label"], "1920 × 1080 px")
        self.assertEqual(hotspot["orientation"], "horizontal")
        self.assertEqual(hotspot["beats"][1]["role"], "contexto")
        self.assertFalse(any(item["key"] == "cta" and item["present"] for item in hotspot["elements"]))
        banner = format_direction({
            "slug": "iab-leaderboard",
            "mechanic": "static_display",
            "default_size": "728x90",
            "behavior_spec": {"type": "static"},
            "layers": [{"role": "headline"}, {"role": "cta"}],
        })
        self.assertEqual(banner["orientation"], "horizontal")
        self.assertEqual(banner["family"], "wide_banner")
        self.assertEqual(banner["beats"][0]["label"], "Faixa horizontal")
        visual = next(item for item in banner["layout"]["slots"] if item["key"] == "visual")
        self.assertLess(visual["width"], 40)
        story = format_direction({
            "slug": "instagram-story",
            "mechanic": "static_display",
            "default_size": "1080x1920",
            "behavior_spec": {"type": "static"},
            "layers": [{"role": "headline"}, {"role": "cta"}],
        })
        self.assertEqual(story["orientation"], "vertical")
        self.assertEqual(story["family"], "story_9x16")
        self.assertIn("9:16", story["beats"][0]["job"])
        half = format_direction({
            "slug": "iab-half-page",
            "mechanic": "static_display",
            "default_size": "300x600",
            "behavior_spec": {"type": "static"},
        })
        self.assertEqual(half["orientation"], "vertical")
        self.assertIn("Coluna", half["beats"][0]["label"])
        compare_h = format_direction({
            "slug": "arraste-descubra",
            "mechanic": "arraste-descubra",
            "default_size": "728x90",
            "behavior_spec": {"type": "compare"},
        })
        self.assertIn("linha vertical", compare_h["beats"][1]["job"])
        compare_v = format_direction({
            "slug": "arraste-descubra",
            "mechanic": "arraste-descubra",
            "default_size": "300x600",
            "behavior_spec": {"type": "compare"},
        })
        self.assertIn("linha horizontal", compare_v["beats"][1]["job"])
        prompt = CreativeModelingService.build_scene_prompt({
            "position": 1,
            "scene_count": 1,
            "format_name": "Leaderboard",
            "slug": "iab-leaderboard",
            "mechanic": "static_display",
            "default_size": "728x90",
            "behavior_spec": {"type": "static"},
            "description": "Oferta da marca",
        })
        self.assertIn("Orientation: horizontal", prompt)
        self.assertIn("Visual left", prompt)

    def test_formatos_expoem_contagem_canonica_de_cenas(self):
        repository = Mock()
        repository.list_formats.return_value = [
            {"mechanic": "static_display", "behavior_spec": {"type": "static"}},
            {"mechanic": "reveal", "behavior_spec": {"type": "reveal"}},
        ]
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        listed = service.list_formats()
        self.assertEqual([item["scene_count"] for item in listed], [1, 4])
        self.assertIn("direction", listed[1])
        self.assertEqual(listed[1]["direction"]["behavior"], "reveal")

    def test_perfil_de_viewer_preserva_hero_e_catalogo_seguro(self):
        self.repo.viewer_profiles[1]["shell_spec"] = {
            "nav": ["Início", "Filmes"],
            "network_links": ["globo.com", "g1"],
            "edition_label": "Notícias",
            "hero": {
                "eyebrow": "Em destaque",
                "title": "Cidade Invisível",
                "description": "Uma produção fictícia.",
                "image": "/static/images/creative-viewers/g1-mobilidade-eletrica.jpg",
            },
            "sections": [{
                "title": "Em alta",
                "items": [{
                    "title": "Arquivo 27",
                    "image": "/static/images/creative-viewers/catalog/hbo-catalog.svg",
                    "category": "Cultura",
                    "summary": "Uma notícia demonstrativa.",
                    "time": "Há 1 hora",
                }],
            }],
        }
        profiles = self.service.list_viewer_profiles()
        netflix = next(item for item in profiles if item["slug"] == "netflix")
        self.assertEqual(netflix["shell_spec"]["hero"]["title"], "Cidade Invisível")
        self.assertEqual(
            netflix["shell_spec"]["sections"][0]["items"][0]["title"],
            "Arquivo 27",
        )
        self.assertEqual(netflix["shell_spec"]["network_links"], ["globo.com", "g1"])
        self.assertEqual(
            netflix["shell_spec"]["sections"][0]["items"][0]["category"],
            "Cultura",
        )

    def test_aprimora_briefing_em_quatro_cenas_complementares(self):
        result = self.service.enhance_campaign_brief({
            "client_name": "Marca Exemplo",
            "name": "Lançamento",
            "objective": "Consideração",
            "campaign_text": "Apresentar o novo produto para famílias.",
            "cta_text": "Conheça",
            "format_name": "Pause Ad",
            "mechanic": "interactive_on_pause",
            "scene_count": 4,
        })
        self.assertEqual(len(result["scenes"]), 4)
        self.assertEqual(result["scenes"][0]["role"], "gancho")
        self.assertIn("português", result["campaign_text"])
        self.assertTrue(result["visual_bible"])

    def test_aprimora_briefing_com_pack_sem_mensagem(self):
        captured = {}

        class CapturingGenerator(FakeGenerator):
            def generate_campaign_brief(self, context):
                captured["context"] = context
                return super().generate_campaign_brief(context)

        service = CreativeModelingService(
            repository=self.repo,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        result = service.enhance_campaign_brief({
            "client_name": "Marca Exemplo",
            "name": "Lançamento",
            "scene_count": 1,
            "campaign_pack": {
                "extracted": {
                    "headline": "Coleção Outono",
                    "offer": "Linho e luz para a temporada",
                    "cta": "Conheça",
                }
            },
        })
        self.assertEqual(len(result["scenes"]), 1)
        self.assertEqual(
            captured["context"]["campaign"]["message"],
            "Linho e luz para a temporada",
        )
        self.assertEqual(
            captured["context"]["reference_weight"]["campaign_pack"],
            "primary",
        )
        self.assertIn("campaign_pack existir", BRIEF_SYSTEM)
        self.assertIn("campaign_pack existir", SCENE_BEAT_SYSTEM)

    def test_fallback_de_cenas_nao_repete_a_mesma_descricao(self):
        scenes = self.service.fallback_scene_descriptions("Produto sustentável", 4)
        self.assertEqual(len(scenes), 4)
        self.assertEqual(len(set(scenes)), 4)
        self.assertIn("Gancho", scenes[0])
        self.assertIn("Fechamento", scenes[3])

    def test_prompt_de_cena_exige_copy_em_portugues_e_storyboard(self):
        prompt = self.service.build_scene_prompt({
            "position": 2,
            "scene_count": 4,
            "description": "Apresentar o produto.",
            "campaign_text": "Mensagem",
            "storyboard": [
                {"position": 1, "description": "Gancho"},
                {"position": 2, "description": "Produto"},
            ],
            "creative_brief": {"visual_bible": "Luz suave e fundo azul"},
            "behavior_spec": {"type": "carousel"},
        })
        self.assertIn("Brazilian Portuguese", prompt)
        self.assertIn("Full storyboard", prompt)
        self.assertIn("Shared visual bible", prompt)
        self.assertIn("one beat of the same ad", prompt)
        self.assertIn("BRIEF LOCK", prompt)
        self.assertIn("FORBID AI LOOK", prompt)
        pack_prompt = self.service.build_scene_prompt({
            "position": 1,
            "scene_count": 1,
            "description": "Peça",
            "creative_brief": {
                "campaign_pack": {
                    "extracted": {"headline": "Coleção Outono", "cta": "Conheça"},
                }
            },
        })
        self.assertIn("Campaign pack is the primary offer source", pack_prompt)
        self.assertIn("Pack headline (literal): Coleção Outono", pack_prompt)
        self.assertIn("não variação", prompt)

    def test_geracao_usa_cena_anterior_e_salva_revisao_multimodal(self):
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 51,
            "production_id": 50,
            "campaign_id": 30,
            "format_template_id": 7,
            "position": 2,
            "description": "Apresentar o produto.",
            "campaign_name": "Campanha",
            "prompt": "Prompt aprovado em português.",
            "prompt_status": "approved",
            "media_type": "image",
            "aspect_ratio": "16:9",
            "previous_approved_asset_url": "/previous.png",
            "creative_brief": {"visual_bible": "Luz natural"},
        }
        repository.create_generation_job.return_value = 90
        repository.add_generated_asset.return_value = {
            "id": 99,
            "asset_url": "/generated.png",
            "status": "review",
        }
        generator = Mock()
        generator.generate_image.return_value = {
            "b64_json": base64.b64encode(b"image").decode(),
            "model": "openai/gpt-image-2",
            "usage": {},
            "actual_cost_usd": 0.13,
            "output_format": "png",
        }
        generator.review_image.return_value = {
            "result": {
                "approved_recommendation": False,
                "score": 78,
                "warnings": ["Corrigir o CTA em inglês."],
                "checks": {"language_pt_br": False, "continuity": True},
            },
            "actual_cost_usd": 0.002,
        }
        service = CreativeModelingService(
            repository=repository,
            generator=generator,
            storage=FakeStorage(),
        )
        service.generate_scene(51, [], created_by=3)
        references = generator.generate_image.call_args.args[1]
        self.assertEqual(len(references), 1)
        metadata = repository.add_generated_asset.call_args.args[4]
        self.assertEqual(metadata["quality_review"]["score"], 78)
        self.assertFalse(
            metadata["quality_review"]["checks"]["language_pt_br"]
        )
        self.assertEqual(repository.create_generation_job.call_count, 1)
        self.assertNotIn(
            "refine_intent",
            repository.create_generation_job.call_args.kwargs["request_payload"],
        )

    def test_cena_1_usa_pack_antes_da_linha_criativa(self):
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 51,
            "production_id": 50,
            "campaign_id": 30,
            "client_id": 10,
            "format_template_id": 7,
            "position": 1,
            "description": "Composição final",
            "campaign_name": "Campanha",
            "prompt": "Prompt aprovado em português.",
            "prompt_status": "approved",
            "media_type": "image",
            "aspect_ratio": "16:9",
            "creative_brief": {
                "visual_bible": "Luz natural",
                "campaign_pack": {
                    "sources": [{
                        "kind": "image",
                        "asset_url": "/static/uploads/creative_references/pack.png",
                    }],
                    "extracted": {"headline": "Coleção Outono"},
                },
            },
        }
        repository.list_client_brand_assets.return_value = [{
            "id": 41,
            "role": "creative",
            "asset_path": "/static/uploads/creative_references/antiga.png",
            "mime_type": "image/png",
        }]
        repository.create_generation_job.return_value = 90
        repository.add_generated_asset.return_value = {
            "id": 99,
            "asset_url": "/generated.png",
            "status": "review",
        }
        generator = Mock()
        generator.generate_image.return_value = {
            "b64_json": base64.b64encode(b"image").decode(),
            "model": "openai/gpt-image-2",
            "usage": {},
            "actual_cost_usd": 0.13,
            "output_format": "png",
        }
        generator.review_image.return_value = {
            "result": {"approved_recommendation": True, "score": 90, "warnings": [], "checks": {}},
            "actual_cost_usd": 0.002,
        }
        service = CreativeModelingService(
            repository=repository,
            generator=generator,
            storage=FakeStorage(),
        )
        service.generate_scene(51, [], created_by=3)
        references = generator.generate_image.call_args.args[1]
        self.assertEqual(len(references), 1)
        self.assertTrue(references[0].startswith("data:image/"))

    def test_le_pack_da_campanha_a_partir_da_imagem(self):
        service = CreativeModelingService(
            repository=FakeRepository(),
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        result = service.read_campaign_pack(
            {},
            [FileStorage(stream=BytesIO(b"kv"), filename="kv.png", content_type="image/png")],
        )
        self.assertEqual(result["extracted"]["headline"], "Coleção Outono")
        self.assertEqual(result["campaign_pack"]["sources"][0]["kind"], "image")
        self.assertTrue(result["preview_url"])

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
        self.assertIn("visual_bible", saved["creative_brief"])
        self.assertEqual(len(saved["creative_brief"]["scenes"]), 4)
        self.assertTrue(saved["productions"][0]["approve_prompts"])
        self.assertEqual(len(saved["productions"][0]["scene_prompts"]), 4)
        self.assertIn("BRIEF LOCK", saved["productions"][0]["scene_prompts"][0])
        self.assertIn("FORBID AI LOOK", saved["productions"][0]["scene_prompts"][0])

    def test_plano_persiste_campaign_pack(self):
        repository = Mock()
        repository.get_format.return_value = {
            "mechanic": "static_display",
            "behavior_spec": {"type": "static"},
        }
        repository.create_campaign_with_productions.return_value = {
            "id": 31,
            "productions": [{"id": 51}],
        }
        repository.get_campaign.return_value = {"id": 31, "name": "Pack"}
        repository.get_production.return_value = {
            "id": 51,
            "scene_count": 1,
            "scenes": [{"id": 1}],
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        service.create_production_plan({
            "name": "Pack",
            "productions": [{"format_template_id": 7, "scene_descriptions": ["Peça"]}],
            "campaign_pack": {
                "sources": [{
                    "kind": "image",
                    "name": "kv.png",
                    "asset_url": "/static/uploads/creative_references/kv.png",
                }],
                "extracted": {"headline": "Coleção Outono", "cta": "Conheça"},
            },
        })
        saved = repository.create_campaign_with_productions.call_args.args[0]
        pack = saved["creative_brief"]["campaign_pack"]
        self.assertEqual(pack["extracted"]["headline"], "Coleção Outono")
        self.assertEqual(pack["sources"][0]["kind"], "image")

    def test_campanha_sem_cliente_usa_centralcomm(self):
        repository = Mock()
        repository.get_format.return_value = {
            "mechanic": "static_display",
            "behavior_spec": {"type": "static"},
        }
        repository.create_campaign_with_productions.return_value = {
            "id": 30,
            "productions": [{"id": 50}],
        }
        repository.get_campaign.return_value = {"id": 30, "name": "Sem vínculo"}
        repository.get_production.return_value = {
            "id": 50,
            "scene_count": 1,
            "scenes": [{"id": 1}],
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        service.create_production_plan({
            "name": "Sem vínculo",
            "productions": [{"format_template_id": 7, "scene_descriptions": ["Peça"]}],
        })
        saved = repository.create_campaign_with_productions.call_args.args[0]
        self.assertEqual(saved["client_id"], 174)
        self.assertEqual(saved["client_source"], "crm")

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

    def test_link_publico_agrupa_cenas_aprovadas_em_um_carrossel(self):
        for index, asset in enumerate(self.repo.assets):
            asset["production_id"] = 50 if index < 3 else 60
        result = self.service.create_public_collection(
            30, {"title": "Apresentação", "asset_ids": [1, 2, 3, 4]}
        )
        self.assertEqual(self.repo.public_collection["asset_ids"], [1, 4])
        self.assertEqual(result["asset_count"], 2)

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

    def test_formato_aceita_carrossel_automatico(self):
        self.service.update_format_modeling(
            7,
            {
                "safe_area": {},
                "placement_spec": self.repo.format_data["placement_spec"],
                "behavior_spec": {
                    "type": "carousel",
                    "trigger": "auto",
                    "transition_ms": 2800,
                },
                "default_viewer_profile_id": 1,
            },
        )
        self.assertEqual(self.repo.format_data["behavior_spec"]["type"], "carousel")
        self.assertEqual(self.repo.format_data["behavior_spec"]["trigger"], "auto")

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

    def test_mockup_de_formato_usa_dna_e_referencias_aprovadas_da_marca(self):
        client = self.repo.get_client(10)
        client["brand_profile"] = {
            "creative_guidelines": "Produto real com luz natural.",
            "visual_motifs": ["Fundo areia"],
            "color_palette": [{
                "hex": "#7A1632",
                "name": "Vinho",
                "usage": "Assinatura",
            }],
            "creative_line": {
                "signature_summary": "Produto central com respiro amplo.",
                "composition_rules": ["Produto no terço central."],
                "copy_system": {
                    "headline_structure": "Título curto no topo.",
                    "cta": {"visual_pattern": "Pílula na base"},
                },
                "gpt_image_instruction": "Keep generous negative space.",
            },
        }
        self.repo.get_client = lambda _client_id: client
        self.repo.list_client_brand_assets = lambda _client_id: [{
            "id": 55,
            "role": "logo",
            "asset_path": "/static/uploads/creative_references/logo.png",
            "mime_type": "image/png",
        }]

        self.service.generate_format_mockup(
            7,
            {"slot": "1", "reference_type": "full_mockup", "client_id": 10},
            [],
        )
        job = self.repo.format_jobs[-1]

        self.assertIn("Observed palette: #7A1632", job["prompt"])
        self.assertIn("LEARNED CREATIVE LINE", job["prompt"])
        self.assertIn("COPY SYSTEM", job["prompt"])
        self.assertIn("Título curto no topo.", job["prompt"])
        self.assertIn("Keep generous negative space.", job["prompt"])
        self.assertIn("BRAND REFERENCE RULES", job["prompt"])
        self.assertNotIn("STRUCTURAL REFERENCE RULES", job["prompt"])
        self.assertEqual(job["input_references"], [])

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
    def test_revisao_multimodal_envia_imagem_e_retorna_checks(self):
        captured = {}

        def llm(messages, **kwargs):
            captured["messages"] = messages
            return {
                "message": {
                    "content": json.dumps({
                        "approved_recommendation": False,
                        "score": 72,
                        "warnings": ["CTA em inglês."],
                        "checks": {"language_pt_br": False},
                    })
                },
                "model": "openai/gpt-test",
                "usage": {},
            }

        client = CreativeGenerationClient(text_callable=llm)
        result = client.review_image(
            {"required_language": "pt-BR"},
            "data:image/png;base64,aW1hZ2U=",
        )
        content = captured["messages"][1]["content"]
        self.assertEqual(content[1]["type"], "image_url")
        self.assertEqual(result["result"]["score"], 72)
        self.assertFalse(result["result"]["checks"]["language_pt_br"])

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
        self.assertEqual(normalize_image_aspect_ratio("32:5"), "21:9")

    def test_familia_iab_relaciona_streaming_sem_confundir_pixel(self):
        leader = format_family_spec("iab-leaderboard", "728x90")
        netflix = format_family_spec("netflix-pause-banner", "1920x300")
        self.assertEqual(leader["family"], "wide_banner")
        self.assertEqual(netflix["family"], "wide_banner")
        self.assertEqual(netflix["iab_cousin"], "billboard")
        self.assertNotEqual(leader["size"], netflix["size"])
        self.assertEqual(
            format_family_spec("hbomax-pause-ad")["family"], "slate_16x9"
        )
        self.assertEqual(
            format_family_spec("video-outstream")["family"], "sequence_16x9"
        )
        self.assertFalse(should_compose("sequence_16x9", "native", 1, 4))
        self.assertTrue(should_compose("sequence_16x9", "native", 4, 4))
        self.assertTrue(canvas_mismatch((728, 90), "21:9"))
        self.assertFalse(canvas_mismatch((1920, 1080), "16:9"))
        leader_slots = compose_layout("wide_banner", (728, 90))
        half_slots = compose_layout("half_page", (300, 600))
        slate_slots = compose_layout("slate_16x9", (1920, 1080))
        self.assertLess(leader_slots["headline"][0], leader_slots["cta"][0])
        self.assertLess(half_slots["headline"][1], half_slots["cta"][1])
        self.assertGreater(slate_slots["headline"][2], slate_slots["cta"][2])
        self.assertNotEqual(leader_slots["cta"][1:], half_slots["cta"][1:])

    def test_compose_devolve_png_no_retangulo_alvo(self):
        rectangle = compose_native_piece(
            b"not-a-png",
            format_family_spec("iab-medium-rectangle", "300x250"),
            {"headline": "Marca", "cta": "Saiba mais"},
        )
        pause = compose_native_piece(
            b"not-a-png",
            format_family_spec("netflix-pause-banner", "1920x300"),
            {"headline": "Campanha", "cta": "Assista"},
        )
        self.assertEqual(png_size(rectangle), (300, 250))
        self.assertEqual(png_size(pause), (1920, 300))

    def test_prompt_nativo_nao_usa_regras_de_mockup(self):
        prompt = apply_render_mode_to_prompt(
            "Premium still of the product.",
            "native",
            format_family_spec("iab-leaderboard", "728x90"),
            {"cta": "Saiba mais"},
        )
        self.assertIn("728x90", prompt)
        self.assertIn("wide_banner", prompt)
        self.assertIn("Element budget", prompt)
        self.assertNotIn("CLIENT-PRESENTATION MOCKUP", prompt)

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

    def test_api_aprimora_briefing_autenticado(self):
        service = Mock()
        service.enhance_campaign_brief.return_value = {
            "campaign_text": "Mensagem aprimorada",
            "cta_text": "Conheça",
            "visual_bible": "Luz natural",
            "scenes": [{"position": 1, "role": "composição_final", "description": "Cena"}],
        }
        payload = {
            "client_name": "Marca",
            "name": "Campanha",
            "campaign_text": "Mensagem",
            "scene_count": 1,
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/campaigns/enhance-brief",
                json=payload,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["data"]["campaign_text"],
            "Mensagem aprimorada",
        )
        service.enhance_campaign_brief.assert_called_once_with(payload)

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
        service.refine_scene_asset.return_value = {"asset": {"id": 71}}
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
            refine = self.client.post(
                "/parametros/api/scenes/51/assets/70/refine",
                json={"instruction": "CTA maior", "intent": "cta"},
            )
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
        self.assertEqual(refine.status_code, 201)
        self.assertEqual(review.status_code, 200)
        self.assertEqual(preview.status_code, 200)

    def test_api_desdobramentos_lista_e_cria(self):
        service = Mock()
        service.list_campaigns.return_value = [{"id": 40, "flow_kind": "unfold"}]
        service.create_unfolding.return_value = {
            "campaign": {"id": 40},
            "productions": [{"id": 80}],
        }
        service.generate_unfolding.return_value = {
            "id": 40,
            "pieces": [{"scene_id": 81}],
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            listing = self.client.get("/parametros/api/unfoldings")
            created = self.client.post(
                "/parametros/api/unfoldings",
                data={
                    "name": "Outono social",
                    "client_id": "10",
                    "headline": "Coleção Outono",
                    "cta_text": "Conheça",
                    "format_ids": "[7]",
                    "generate": "true",
                    "kv": (BytesIO(b"kv"), "kv.png"),
                },
                content_type="multipart/form-data",
            )
            generate = self.client.post("/parametros/api/unfoldings/40/generate")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(generate.status_code, 200)
        service.list_campaigns.assert_called_with("unfold")
        self.assertTrue(service.create_unfolding.called)
        service.generate_unfolding.assert_called()

    def test_api_read_kv_devolve_headline_cta_e_nome(self):
        service = CreativeModelingService(
            repository=FakeRepository(),
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/unfoldings/read-kv",
                data={"kv": (BytesIO(b"kv"), "kv.png")},
                content_type="multipart/form-data",
            )
        payload = response.get_json()["data"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["headline"], "Coleção Outono")
        self.assertEqual(payload["cta"], "Conheça a coleção")
        self.assertEqual(payload["name"], "Coleção Outono")

    def test_api_le_pack_da_campanha(self):
        service = CreativeModelingService(
            repository=FakeRepository(),
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/campaigns/read-pack",
                data={"images": (BytesIO(b"kv"), "kv.png")},
                content_type="multipart/form-data",
            )
        payload = response.get_json()["data"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["extracted"]["headline"], "Coleção Outono")
        self.assertEqual(payload["campaign_pack"]["sources"][0]["kind"], "image")

    def test_api_lotes_publicaveis_e_tiers(self):
        service = Mock()
        service.list_image_tiers.return_value = [
            {"name": "draft", "quality": "low", "resolution": "1K"},
            {"name": "publish", "quality": "high", "resolution": "2K"},
        ]
        service.quote_campaign_publish.return_value = {
            "count": 2, "total_brl": 2.28, "pieces": [],
        }
        service.publish_campaign.return_value = {"id": 40, "pieces": []}
        service.prepare_campaign_video.return_value = {
            "status": "mocked",
            "ready": False,
            "message": "Pipeline de vídeo ainda não está pronto.",
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            tiers = self.client.get("/parametros/api/image-tiers")
            quote = self.client.get("/parametros/api/campaigns/40/publish-quote")
            published = self.client.post(
                "/parametros/api/campaigns/40/publish",
                json={"asset_ids": [90, 91]},
            )
            video = self.client.post("/parametros/api/campaigns/40/video/prepare")
        self.assertEqual(tiers.status_code, 200)
        self.assertEqual(quote.status_code, 200)
        self.assertEqual(published.status_code, 200)
        self.assertEqual(video.status_code, 200)
        service.publish_campaign.assert_called()
        service.prepare_campaign_video.assert_called_once_with(40)

    def test_api_atualiza_cliente(self):
        service = Mock()
        service.update_client.return_value = {"id": 10, "name": "Cliente editado"}
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.put(
                "/parametros/api/clients/10",
                json={"name": "Cliente editado", "primary_color": "#123ABC"},
            )
        self.assertEqual(response.status_code, 200)
        service.update_client.assert_called_once()

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
        self.assertEqual(args[1][0].filename, "marca.png")

    def test_api_aprende_linha_criativa_com_multiplas_pecas(self):
        service = Mock()
        service.learn_client_creative_line.return_value = {
            "client_id": 10,
            "creative_line": {"source_count": 2},
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/clients/10/creative-line/analyze",
                data={
                    "creatives": [
                        (BytesIO(b"image-one"), "campanha-1.png"),
                        (BytesIO(b"image-two"), "campanha-2.png"),
                    ],
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 200)
        files = service.learn_client_creative_line.call_args.args[1]
        self.assertEqual([item.filename for item in files], [
            "campanha-1.png",
            "campanha-2.png",
        ])


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
            "_mc_desdobrar.html",
        ]
        for name in names:
            source = (template_dir / name).read_text(encoding="utf-8")
            Environment().parse(source)
            self.assertNotIn("btn btn-", source)
        page = (template_dir / "modelagem_criativos.html").read_text(encoding="utf-8")
        self.assertIn('extends "base_erp.html"', page)
        self.assertIn("cx-tabs", page)
        self.assertIn("modelagem_criativos.css') }}?v=35", page)
        self.assertIn("modelagem_criativos.js') }}?v=35", page)
        for tab in ("preparar", "produzir", "desdobrar", "formatos", "marcas", "historico"):
            self.assertIn(f'data-tab="{tab}"', page)
        self.assertNotIn("Variações A/B", page)
        generator = (template_dir / "_mc_gerador.html").read_text(encoding="utf-8")
        self.assertIn("mc-generator-workspace", generator)
        self.assertIn('id="mcGeneratorFormatList"', generator)
        self.assertIn('value="social"', generator)
        self.assertIn('form="mcCampaignForm"', generator)
        self.assertIn('name="client_ref"', generator)
        self.assertIn('id="mcEnhanceBrief"', generator)
        self.assertIn("Gerar roteiro", generator)
        self.assertIn('id="mcCampaignPackDrop"', generator)
        self.assertIn('id="mcCampaignPackUrl"', generator)
        self.assertIn('id="mcStoryboardEditor"', generator)
        self.assertIn("Iniciar produção", generator)
        self.assertNotIn("Variação A", generator)
        self.assertNotIn("Limite de IA", generator)
        self.assertNotIn("Limite inicial", generator)
        self.assertNotIn('name="budget_usd"', generator)
        production = (
            template_dir / "_mc_variacoes.html"
        ).read_text(encoding="utf-8")
        self.assertIn('id="mcSceneRail"', production)
        self.assertIn('id="mcContinuitySpine"', production)
        self.assertIn("Direção do formato", production)
        self.assertIn('id="mcProductionStage"', production)
        self.assertIn('data-preview-device="desktop"', production)
        self.assertIn('data-preview-device="mobile"', production)
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
        self.assertIn("viewer_shell.sections", public_page)
        self.assertIn("pv-tv-catalog", public_page)
        self.assertIn("data-carousel", public_page)
        self.assertIn("asset.carousel_assets", public_page)
        self.assertIn("data-behavior", public_page)
        repository_source = (
            root / "aicentralv2" / "creative_modeling_repository.py"
        ).read_text(encoding="utf-8")
        self.assertIn("f.behavior_spec", repository_source)
        self.assertIn("AS carousel_assets", repository_source)
        self.assertNotIn('src="{{ asset.asset_url }}"', public_page)
        library = (template_dir / "_mc_biblioteca.html").read_text(encoding="utf-8")
        self.assertIn("mcFormatStage", library)
        self.assertIn("mcAdSlot", library)
        self.assertIn("mcLibraryDetail", library)
        clients = (template_dir / "_mc_clientes.html").read_text(encoding="utf-8")
        self.assertIn("mc-brand-studio", clients)
        self.assertIn('data-brand-col="add"', clients)
        self.assertIn('data-brand-col="edit"', clients)
        self.assertIn('data-brand-col="audit"', clients)
        self.assertIn('id="mcClientForm"', clients)
        self.assertIn('id="mcNewBrand"', clients)
        self.assertIn('id="mcAnalyzeBrand"', clients)
        self.assertIn('name="target_audience"', clients)
        self.assertIn('id="mcBrandDropzone"', clients)
        self.assertIn('id="mcBrandAssetStrip"', clients)
        self.assertIn('id="mcBrandSelectionTray"', clients)
        self.assertIn('id="mcBrandPalette"', clients)
        self.assertIn('id="mcCreativeLine"', clients)
        self.assertIn('id="mcCreativeLineDropzone"', clients)
        self.assertIn('id="mcCreativeLineResult"', clients)
        self.assertIn('class="mc-visually-hidden"', clients)
        self.assertNotIn('class="cx-input" name="brand_image"', clients)
        historico = (template_dir / "_mc_historico.html").read_text(encoding="utf-8")
        self.assertIn('id="mcHistorySpend"', historico)
        self.assertIn('id="mcModelingLedger"', historico)
        self.assertIn('id="mcHistoryFinish"', historico)
        self.assertIn("Todas as modelagens", historico)
        unfold = (template_dir / "_mc_desdobrar.html").read_text(encoding="utf-8")
        self.assertIn('id="mcUnfoldForm"', unfold)
        self.assertIn('id="mcUnfoldDropzone"', unfold)
        self.assertIn('id="mcUnfoldKvReview"', unfold)
        self.assertIn('id="mcUnfoldFormatList"', unfold)
        self.assertIn('id="mcUnfoldGenerate"', unfold)
        self.assertIn('id="mcUnfoldSpend"', unfold)
        self.assertIn('id="mcUnfoldPieces"', unfold)
        self.assertIn("Gerar rascunhos", unfold)
        self.assertNotIn("Gerar desdobramentos", unfold)
        self.assertNotIn('id="mcUnfoldSourceCampaign"', unfold)
        self.assertIn('type="hidden" name="source_asset_id" id="mcUnfoldSourceAsset"', unfold)
        self.assertEqual(unfold.count("<select"), 1)
        self.assertNotIn('name="offer"', unfold)
        self.assertIn("publicáveis em alta", unfold)
        self.assertIn('id="mcUnfoldOpenPublish"', unfold)
        self.assertNotIn('id="mcUnfoldPublishBatch"', unfold)
        production_html = (template_dir / "_mc_variacoes.html").read_text(encoding="utf-8")
        self.assertIn('id="mcOpenPublishBatch"', production_html)
        self.assertIn('id="mcCreatePublicLink"', production_html)
        self.assertIn('id="mcOpenPresentation"', production_html)
        self.assertIn('id="mcShareDialog"', production_html)
        self.assertIn("Abrir apresentação", production_html)
        self.assertIn("Criar e abrir", production_html)
        self.assertIn('id="mcPublishDialog"', page)
        self.assertIn('id="mcPublishBatch"', page)
        self.assertIn("setupBrandDropzone(", production_js)
        self.assertIn("data-brand-select", production_js)
        self.assertIn("learnCreativeLine(button)", production_js)
        self.assertIn("creative-line/analyze", production_js)
        catalog_dir = (
            root / "aicentralv2" / "static" / "images"
            / "creative-viewers" / "catalog"
        )
        for filename in (
            "disney-catalog.svg", "netflix-catalog.svg", "netflix-top10.svg",
            "hbo-catalog.svg", "hbo-cinema.svg",
        ):
            self.assertTrue((catalog_dir / filename).is_file())
        for filename in (
            "g1-mobilidade-eletrica.jpg",
            "g1-lobo-guara.jpg",
            "g1-festival-gastronomia.jpg",
        ):
            self.assertTrue(
                (root / "aicentralv2" / "static" / "images"
                 / "creative-viewers" / filename).is_file()
            )

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
            "DROP CONSTRAINT IF EXISTS uq_cx_clients_crm_client",
            add_column,
        )
        drop_unique_start = migration.index(
            "DROP CONSTRAINT IF EXISTS uq_cx_clients_crm_client"
        )

        self.assertLess(drop_unique_start, migration.index("CREATE TABLE IF NOT EXISTS"))
        self.assertLess(add_column, foreign_key)
        self.assertLess(foreign_key, unique_index)
        self.assertIn("DROP INDEX IF EXISTS uq_cx_clients_crm_client", migration)
        self.assertIn("CREATE INDEX IF NOT EXISTS idx_cx_clients_crm_client", migration)
        self.assertNotIn(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_clients_crm_client",
            migration,
        )

        incremental = (
            root / "migrations" / "add_creative_campaign_flow.sql"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "constraint_row.confrelid = 'tbl_cliente'::regclass",
            incremental,
        )
        self.assertIn("column_row.attname = 'crm_client_id'", incremental)
        self.assertIn("DROP CONSTRAINT IF EXISTS uq_cx_clients_crm_client", incremental)
        self.assertIn("DROP INDEX IF EXISTS uq_cx_clients_crm_client", incremental)
        self.assertLess(
            incremental.index("DROP INDEX IF EXISTS uq_cx_clients_crm_client"),
            incremental.index("ADD COLUMN IF NOT EXISTS crm_client_id"),
        )
        self.assertNotIn(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_clients_crm_client",
            incremental,
        )
        for runner in (
            "run_fix_cx_clients_crm_index.py",
            "run_create_creative_modeling.py",
            "run_add_creative_campaign_flow.py",
            "run_add_creative_house_client.py",
        ):
            source = (root / "migrations" / runner).read_text(encoding="utf-8")
            self.assertIn("liberar_crm_client_id", source)
            self.assertIn("validar_crm_client_id", source)
            self.assertNotIn(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_cx_clients_crm_client",
                source,
            )

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
        self.assertIn('"netflix-pause-banner"', seed)
        self.assertIn('"1920x300"', seed)
        self.assertIn('"portal_generico", "click_expand", "image"', seed)
        self.assertIn('"image_carousel"', seed)
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
        self.assertIn('row.get("slug")', layout_seed)
        self.assertIn('"type": "carousel"', layout_seed)
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
        self.assertIn('"layout": "ranked_portrait"', viewer_seed)
        self.assertIn('"layout": "premium_layers"', viewer_seed)
        self.assertIn('"ranked": True', viewer_seed)
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
            '"$VENV_PYTHON" migrations/run_fix_cx_clients_crm_index.py',
            deploy,
        )
        self.assertLess(
            deploy.index(
                '"$VENV_PYTHON" migrations/run_fix_cx_clients_crm_index.py'
            ),
            deploy.index(
                '"$VENV_PYTHON" migrations/run_create_creative_modeling.py'
            ),
        )
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
            '"$VENV_PYTHON" migrations/run_add_creative_house_client.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_add_creative_scene_productions.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_add_creative_client_brand_assets.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_add_creative_brand_lineage.py',
            deploy,
        )
        brand_assets_migration = (
            root / "migrations" / "add_creative_client_brand_assets.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS cx_client_brand_assets", brand_assets_migration)
        self.assertIn("uq_cx_client_brand_assets_primary_logo", brand_assets_migration)
        brand_lineage_migration = (
            root / "migrations" / "add_creative_brand_lineage.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("'creative'", brand_lineage_migration)
        self.assertIn(
            '"$VENV_PYTHON" scripts/seed_creative_formats.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_add_creative_storyboards_and_catalogs.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_convert_interactive_formats_to_image_carousels.py',
            deploy,
        )
        carousel_migration = (
            root / "migrations"
            / "convert_interactive_formats_to_image_carousels.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("'portal_generico'", carousel_migration)
        self.assertIn("'image_carousel'", carousel_migration)
        self.assertIn('"type":"carousel"', carousel_migration)
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
            "/parametros/api/unfoldings",
            "/parametros/api/image-tiers",
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
        self.assertIn("CentralComm · marca", frontend)
        repository = (
            root / "aicentralv2" / "creative_modeling_repository.py"
        ).read_text(encoding="utf-8")
        self.assertIn("HOUSE_CRM_CLIENT_ID = 174", repository)
        self.assertIn("'profile:' || cx.id::text", repository)
        self.assertNotIn(
            "WHERE cx.crm_client_id IS NULL",
            repository,
        )
        self.assertIn("function sceneCountForFormat", frontend)
        self.assertIn("function renderProduction", frontend)
        self.assertIn("function renderContinuitySpine", frontend)
        self.assertIn("Gerar roteiro desta cena", frontend)
        self.assertIn("Confirmar e gerar", frontend)
        self.assertIn("Gerar outra", frontend)
        self.assertIn("reject-asset", frontend)
        self.assertIn("Tirar cara de IA", frontend)
        self.assertIn("Colocar logo", frontend)
        self.assertIn("function formatDirection", frontend)
        self.assertIn("function renderFormatSlotMap", frontend)
        self.assertIn("function groupedGeneratorFormats", frontend)
        self.assertIn("function formatOrientationKey", frontend)
        self.assertIn("mc-format-group", frontend)
        self.assertIn("mc-orient is-${orientation}", frontend)
        self.assertIn("aspect-ratio:${direction.width}/${direction.height}", frontend)
        self.assertIn("mc-slot-map", frontend)
        generator_js = frontend.split("function renderGeneratorFormats")[1].split("function updateGeneratorAvailability")[0]
        self.assertNotIn("GPT Image 2", generator_js)
        self.assertNotIn("formatExperienceIcon", generator_js)
        self.assertNotIn("mc-generator-format-icon", generator_js)
        self.assertIn("mc-scene-px", frontend)
        self.assertIn("Direção visual", frontend)
        self.assertIn("mc-refine-bar", frontend)
        self.assertIn("/assets/${assetId}/refine", frontend)
        self.assertNotIn("Roteiro herdado", frontend)
        self.assertIn("Peça nativa", frontend)
        self.assertIn("Limpar chrome", frontend)
        self.assertIn("Recentrar", frontend)
        self.assertIn('data-render-mode="native"', frontend)
        self.assertIn("mc-native-frame", frontend)
        self.assertEqual(frontend.count('id="mcPromptEditor"'), 2)
        self.assertIn("const brl = (value)", frontend)
        self.assertIn("mcHistorySpend", frontend)
        self.assertIn("mcModelingLedger", frontend)
        self.assertIn("function historyTotal", frontend)
        self.assertIn("mc-campaign-cost", frontend)
        self.assertIn("unfoldings: '/parametros/api/unfoldings'", frontend)
        self.assertIn("readKv: '/parametros/api/unfoldings/read-kv'", frontend)
        self.assertIn("readPack: '/parametros/api/campaigns/read-pack'", frontend)
        self.assertIn("function setupSceneReferenceDrop", frontend)
        self.assertIn("function acceptSceneReferences", frontend)
        self.assertIn("sceneRefFiles", frontend)
        self.assertIn("function acceptCampaignPackFiles", frontend)
        self.assertIn("function readUnfoldKv", frontend)
        self.assertIn("function syncUnfoldReview", frontend)
        self.assertIn("Lendo o KV", frontend)
        self.assertIn("acceptUnfoldKv", frontend)
        self.assertIn("#mcUnfoldDropzone", frontend)
        self.assertIn("syncUnfoldReview();", frontend)
        self.assertNotIn("function renderUnfoldSources", frontend)
        self.assertNotIn("mcUnfoldSourceCampaign", frontend)
        self.assertIn("function createUnfolding", frontend)
        self.assertIn("function unfoldVariation", frontend)
        self.assertIn("flow_kind: 'model'", frontend)
        self.assertIn("data-unfold-ab", frontend)
        self.assertIn("Variação simples", frontend)
        self.assertIn("Variação máxima", frontend)
        self.assertIn("function renderPublishBatch", frontend)
        self.assertIn("function openPublishModal", frontend)
        self.assertIn("Gerar publicáveis", frontend)
        self.assertIn("Os rascunhos saem em low/1K", frontend)
        self.assertIn("produce.hidden = true", frontend)
        self.assertIn("function syncShareTriggers", frontend)
        self.assertIn("function openPublicLink", frontend)
        self.assertIn("window.open(href, '_blank', 'noopener')", frontend)
        self.assertIn('target="_blank"', frontend)
        self.assertIn("function selectBrand", frontend)
        self.assertIn("function saveClient", frontend)
        self.assertIn("function brandLine", frontend)
        self.assertIn("function brandPalette", frontend)
        self.assertIn("function brandTone", frontend)
        self.assertIn("function brandSummary", frontend)
        self.assertIn("brandLine(client).signature_summary", frontend)
        self.assertIn("Atualizar perfil", frontend)
        self.assertIn("`${API.clients}/${current.id}`", frontend)
        self.assertIn("Gerar alta resolução", frontend)
        self.assertIn("video/prepare", frontend)
        self.assertIn("collectDraftPieces(productions, true)", frontend)
        self.assertIn("Pipeline de vídeo ainda não está pronto.", frontend)
        review_js = frontend[frontend.index("function renderSceneReview"):frontend.index("function renderProductionViewer")]
        self.assertLess(
            review_js.index("mc-scene-direction"),
            review_js.index('data-scene-action="generate-prompt"'),
        )
        self.assertLess(
            review_js.index('data-scene-action="generate-prompt"'),
            review_js.index('data-scene-action="approve-prompt"'),
        )
        self.assertIn("Aprovar direção", review_js)
        self.assertIn("mc-scene-dropzone", review_js)
        self.assertIn("Confirmar e gerar", review_js)
        self.assertIn("Gerar outra", review_js)
        self.assertIn("canIterateMockup", review_js)
        self.assertIn("Direção visual", review_js)
        self.assertIn("fidelity', 'draft'", frontend)
        self.assertNotIn("Confirmar consumo de saldo", frontend)
        self.assertIn("mc-scene-thumb", frontend)
        self.assertIn("copy_system", frontend)
        self.assertIn("/parametros/api/scenes/${scene.id}", frontend)
        self.assertIn("format.media_type === 'image'", frontend)
        campaign_flow_sql = (
            root / "migrations" / "add_creative_campaign_flow.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("crm_client_id", campaign_flow_sql)
        self.assertIn("display_motion_payload", campaign_flow_sql)
        house_sql = (
            root / "migrations" / "add_creative_house_client.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("DROP CONSTRAINT IF EXISTS uq_cx_clients_crm_client", house_sql)
        self.assertIn("DROP INDEX IF EXISTS uq_cx_clients_crm_client", house_sql)
        self.assertIn("SET crm_client_id = 174", house_sql)
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


class CreativeUnfoldContractTest(unittest.TestCase):
    def test_temperaturas_nomeadas_e_override_de_ambiente(self):
        self.assertEqual(TEXT_TEMPERATURES["extract_kv_locks"], 0.05)
        self.assertEqual(TEXT_TEMPERATURES["unfold_prompt"], 0.20)
        self.assertEqual(TEXT_TEMPERATURES["ab_simple_prompt"], 0.30)
        self.assertEqual(TEXT_TEMPERATURES["ab_max_prompt"], 0.45)
        self.assertEqual(TEXT_TEMPERATURES["review_locks"], 0.10)
        with patch.dict("os.environ", {"CREATIVE_TEMP_UNFOLD_PROMPT": "0.33"}):
            self.assertEqual(text_temperature("unfold_prompt", 0.20), 0.33)

    def test_diretor_de_desdobramento_usa_pacote_e_temperatura(self):
        captured = {}

        def llm(messages, **kwargs):
            captured["system"] = messages[0]["content"]
            captured["user"] = messages[1]["content"]
            captured["temperature"] = kwargs.get("temperature")
            return {
                "message": {
                    "content": json.dumps({
                        "prompt_en": (
                            "LOCK\nHeadline verbatim: \"Coleção Outono\"\n"
                            "KEEP\nBrand DNA\nADAPT\nCrop for 1080x1080\n"
                            "FORBID\nNo new claim"
                        ),
                        "rationale_pt": "Adapta só a geometria.",
                        "checks": ["locks"],
                    })
                },
                "model": "openai/gpt-test",
            }

        client = CreativeGenerationClient(text_callable=llm)
        result = client.generate_prompt({
            "flow_kind": "unfold",
            "locks": {"headline": "Coleção Outono", "cta": "Conheça a coleção"},
        })
        self.assertEqual(captured["temperature"], 0.20)
        self.assertIn("LOCK", captured["system"])
        self.assertIn("FORBID", captured["system"])
        self.assertIn("Coleção Outono", result["result"]["prompt_en"])

    def test_extracao_de_travas_e_ab_respeitam_temperatura(self):
        captured = []

        def llm(messages, **kwargs):
            captured.append({
                "system": messages[0]["content"],
                "temperature": kwargs.get("temperature"),
            })
            return {
                "message": {
                    "content": json.dumps({
                        "headline": "Coleção Outono",
                        "cta": "Conheça",
                        "prompt_en": "recolor only; same crop; same positions",
                        "rationale_pt": "ok",
                        "checks": [],
                    })
                },
                "model": "openai/gpt-test",
            }

        client = CreativeGenerationClient(text_callable=llm)
        client.extract_kv_locks({"kv_notes": {"offer": "Outono"}})
        client.generate_ab_prompt({"locks": {"cta": "Conheça"}}, "ab_simple")
        client.generate_ab_prompt({"locks": {"cta": "Conheça"}}, "ab_max")
        client.review_image({"locks": {"cta": "Conheça"}}, "data:image/png;base64,aW1hZ2U=")
        self.assertEqual(captured[0]["temperature"], 0.05)
        self.assertIn("Não invente", captured[0]["system"])
        self.assertEqual(captured[1]["temperature"], 0.30)
        self.assertIn("SIMPLES", captured[1]["system"])
        self.assertNotIn("recortar", captured[1]["system"].lower())
        self.assertEqual(captured[2]["temperature"], 0.45)
        self.assertIn("MÁXIMA", captured[2]["system"])
        self.assertNotIn("reescreva texto", captured[2]["system"].lower())
        self.assertEqual(captured[3]["temperature"], 0.10)

    def test_ab_simples_nao_pede_recorte_e_maxima_nao_reescreve_copy(self):
        simple = unfold_ab_instruction("ab_simple", {
            "headline": "Coleção Outono",
            "cta": "Conheça a coleção",
        })
        maximum = unfold_ab_instruction("ab_max", {
            "headline": "Coleção Outono",
            "cta": "Conheça a coleção",
        })
        self.assertIn("recolor only", simple)
        self.assertIn("Same crop", simple)
        self.assertNotIn("recrop", simple)
        self.assertIn("Coleção Outono", simple)
        self.assertIn("recrop", maximum)
        self.assertIn("may not change wording", maximum)
        self.assertIn("Conheça a coleção", maximum)

    def test_review_recusa_cta_travado_ausente(self):
        reviewed = _quality_review_data({
            "approved_recommendation": False,
            "score": 40,
            "warnings": ["CTA sumiu."],
            "checks": {"cta_locked": False, "text_locked": True, "logo_locked": True},
            "defects": [],
        })
        self.assertIn("cta_changed", reviewed["defects"])
        self.assertNotIn("text_rewritten", reviewed["defects"])

    def test_social_nao_passa_pelo_compositor_e_pinta_a_peca(self):
        feed = format_family_spec("instagram-feed", "1080x1080")
        story = format_family_spec("instagram-story", "1080x1920")
        share = format_family_spec("linkedin-share", "1200x627")
        self.assertEqual(feed["family"], "square_1x1")
        self.assertEqual(story["family"], "story_9x16")
        self.assertEqual(share["family"], "landscape_social")
        self.assertEqual(SOCIAL_PAINT_FAMILIES, {
            "square_1x1", "story_9x16", "landscape_social",
        })
        self.assertEqual(SOCIAL_FORMAT_SLUGS, {
            "instagram-feed", "instagram-story", "tiktok-vertical",
            "facebook-feed", "linkedin-share",
        })
        self.assertEqual(default_render_mode("square_1x1"), "native")
        self.assertFalse(should_compose("square_1x1", "native"))
        self.assertFalse(should_compose("story_9x16", "native"))
        prompt = apply_render_mode_to_prompt(
            "Premium still of the product.",
            "native",
            feed,
            {"cta": "Conheça"},
            flow_kind="unfold",
            locks={"headline": "Coleção Outono", "cta": "Conheça a coleção"},
        )
        self.assertIn("COMPLETE SOCIAL ADVERTISEMENT", prompt)
        self.assertIn("Coleção Outono", prompt)
        self.assertIn("LOCK BLOCK FOR GPT IMAGE 2", prompt)
        self.assertNotIn("composed later", prompt)
        leader = apply_render_mode_to_prompt(
            "Premium still of the product.",
            "native",
            format_family_spec("iab-leaderboard", "728x90"),
            {"cta": "Conheça"},
            flow_kind="unfold",
            locks={"headline": "Coleção Outono", "cta": "Conheça a coleção"},
        )
        self.assertIn("NATIVE ADVERTISING STILL", leader)
        self.assertIn("LOCK BLOCK FOR GPT IMAGE 2", leader)

    def test_seed_social_e_cena_unica(self):
        seed = (
            Path(__file__).resolve().parents[1]
            / "scripts" / "seed_creative_formats.py"
        ).read_text(encoding="utf-8")
        self.assertIn('("social", "Redes sociais")', seed)
        for slug in SOCIAL_FORMAT_SLUGS:
            self.assertIn(f'"{slug}"', seed)
            self.assertEqual(scene_count_for_format({
                "slug": slug,
                "mechanic": "static_display",
                "behavior_spec": {"type": "static"},
            }), 1)
        self.assertIn("1080x1080", seed)
        self.assertIn("1080x1920", seed)
        self.assertIn("1200x627", seed)

    def test_create_unfolding_grava_flow_kind_e_travas(self):
        repository = Mock()
        repository.get_format.return_value = {
            "id": 7,
            "slug": "instagram-feed",
            "mechanic": "static_display",
            "behavior_spec": {"type": "static"},
        }
        repository.create_campaign_with_productions.return_value = {
            "id": 40,
            "productions": [{"id": 80}],
        }
        repository.get_campaign.return_value = {
            "id": 40,
            "name": "Outono social",
            "creative_brief": {"flow_kind": "unfold"},
        }
        repository.get_production.return_value = {
            "id": 80,
            "scene_count": 1,
            "scenes": [{"id": 81}],
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        kv = FileStorage(stream=BytesIO(b"kv-bytes"), filename="kv.png")
        result = service.create_unfolding({
            "client_source": "creative",
            "client_id": 10,
            "name": "Outono social",
            "headline": "Coleção Outono",
            "cta_text": "Conheça a coleção",
            "offer": "Linho e luz de outono.",
            "format_ids": [7],
        }, files=[kv])
        saved = repository.create_campaign_with_productions.call_args.args[0]
        self.assertEqual(saved["creative_brief"]["flow_kind"], "unfold")
        self.assertEqual(saved["creative_brief"]["locks"]["headline"], "Coleção Outono")
        self.assertEqual(saved["creative_brief"]["locks"]["cta"], "Conheça a coleção")
        self.assertEqual(saved["creative_brief"]["source"]["type"], "upload")
        self.assertEqual(len(saved["productions"]), 1)
        self.assertEqual(result["campaign"]["id"], 40)

    def test_read_kv_usa_ocr_e_sugere_nome_sem_gravar(self):
        repository = Mock()
        repository.get_assets.return_value = [{
            "id": 3,
            "asset_url": "/static/uploads/creative_references/kv.png",
            "asset_type": "image",
        }]
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        uploaded = service.read_kv({}, files=[
            FileStorage(stream=BytesIO(b"kv-bytes"), filename="kv.png"),
        ])
        self.assertEqual(uploaded["headline"], "Coleção Outono")
        self.assertEqual(uploaded["cta"], "Conheça a coleção")
        self.assertEqual(uploaded["name"], "Coleção Outono")
        chosen = service.read_kv({"source_asset_id": 3})
        self.assertEqual(chosen["headline"], "Coleção Outono")
        self.assertEqual(chosen["preview_url"], "/static/uploads/creative_references/kv.png")
        repository.create_campaign_with_productions.assert_not_called()

    def test_prompt_de_unfold_nao_herda_cena_e_auto_aprova(self):
        captured = {}
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 81,
            "position": 2,
            "description": "Feed",
            "campaign_name": "Outono",
            "campaign_id": 40,
            "production_id": 80,
            "format_template_id": 7,
            "format_slug": "instagram-feed",
            "default_size": "1080x1080",
            "master_prompt": "MASTER from scene 1",
            "storyboard": [],
            "creative_brief": {
                "flow_kind": "unfold",
                "locks": {"headline": "Coleção Outono", "cta": "Conheça a coleção"},
            },
            "cta_text": "Conheça a coleção",
            "campaign_text": "Coleção Outono",
            "show_price": False,
            "objective": "Desdobramento",
            "client_name": "Marca",
            "client_sector": "Moda",
            "tone_of_voice": "Calmo",
            "logo_url": None,
            "logo_upload_path": None,
            "primary_color": "#1E4D4F",
            "secondary_color": "#9CCF31",
            "brand_profile": {},
            "scene_count": 1,
        }
        repository.create_generation_job.return_value = 9
        repository.update_scene_prompt.return_value = {
            "id": 81, "prompt": "Unfold", "prompt_status": "approved",
        }

        class CapturingGenerator(FakeGenerator):
            def generate_prompt(self, context):
                captured["context"] = context
                return super().generate_prompt(context)

        service = CreativeModelingService(
            repository=repository,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        service.generate_scene_prompt(81)
        self.assertEqual(captured["context"]["flow_kind"], "unfold")
        self.assertFalse(captured["context"]["inherit_from_master"])
        self.assertEqual(
            repository.update_scene_prompt.call_args.args[2], "approved"
        )
        prompt = repository.update_scene_prompt.call_args.args[1]
        self.assertIn("LOCK BLOCK FOR GPT IMAGE 2", prompt)
        self.assertIn("Coleção Outono", prompt)

    def test_imagem_de_unfold_usa_kv_como_primeira_referencia(self):
        captured = {}
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 81,
            "position": 1,
            "production_id": 80,
            "campaign_id": 40,
            "format_template_id": 7,
            "format_slug": "instagram-feed",
            "default_size": "1080x1080",
            "prompt": "Approved unfold prompt",
            "prompt_status": "approved",
            "media_type": "image",
            "aspect_ratio": "1:1",
            "client_id": 10,
            "creative_brief": {
                "flow_kind": "unfold",
                "source": {"kv_asset_url": "/static/uploads/creative_references/kv.png"},
                "locks": {"headline": "Coleção Outono", "cta": "Conheça"},
            },
        }
        repository.create_generation_job.return_value = 11
        repository.add_generated_asset.return_value = {
            "id": 90, "asset_url": "/generated.png",
        }
        repository.list_client_brand_assets.return_value = []

        class CapturingGenerator(FakeGenerator):
            def generate_image(self, prompt, references, aspect_ratio, **kwargs):
                captured["prompt"] = prompt
                captured["references"] = references
                return super().generate_image(prompt, references, aspect_ratio)

        service = CreativeModelingService(
            repository=repository,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        service.generate_scene(81, [])
        self.assertTrue(captured["references"])
        self.assertTrue(captured["references"][0].startswith("data:image/"))
        payload = repository.create_generation_job.call_args.kwargs["request_payload"]
        self.assertEqual(payload["variant_level"], "source")
        self.assertEqual(payload["flow_kind"], "unfold")
        self.assertIn("LOCK BLOCK FOR GPT IMAGE 2", captured["prompt"])

    def test_refine_ab_grava_variant_level(self):
        captured = {}
        repository = Mock()
        repository.get_scene_context.return_value = {
            "id": 81,
            "position": 1,
            "production_id": 80,
            "campaign_id": 40,
            "format_template_id": 7,
            "format_slug": "instagram-feed",
            "default_size": "1080x1080",
            "prompt": "Approved unfold prompt",
            "media_type": "image",
            "aspect_ratio": "1:1",
            "client_id": 10,
            "creative_brief": {
                "flow_kind": "unfold",
                "locks": {"headline": "Coleção Outono", "cta": "Conheça"},
            },
        }
        repository.get_assets.return_value = [{
            "id": 90,
            "scene_id": 81,
            "asset_url": "/asset-90.png",
            "job_prompt": "SOURCE UNFOLD PROMPT",
        }]
        repository.create_generation_job.return_value = 12
        repository.add_generated_asset.return_value = {
            "id": 91, "asset_url": "/generated.png",
        }
        repository.list_client_brand_assets.return_value = []

        class CapturingGenerator(FakeGenerator):
            def generate_image(self, prompt, references, aspect_ratio, **kwargs):
                captured["prompt"] = prompt
                return super().generate_image(prompt, references, aspect_ratio)

        service = CreativeModelingService(
            repository=repository,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        service.refine_scene_asset(81, 90, {"intent": "ab_simple"})
        payload = repository.create_generation_job.call_args.kwargs["request_payload"]
        self.assertEqual(payload["variant_level"], "ab_simple")
        self.assertIn("recolor only", captured["prompt"])
        self.assertNotIn("recrop", captured["prompt"])
        service.refine_scene_asset(81, 90, {"intent": "ab_max"})
        payload = repository.create_generation_job.call_args.kwargs["request_payload"]
        self.assertEqual(payload["variant_level"], "ab_max")
        self.assertIn("recrop", captured["prompt"])
        self.assertIn("may not change wording", captured["prompt"])

    @patch.dict("os.environ", {"USD_BRL_RATE": "5"})
    def test_flow_kind_isola_gasto_em_reais(self):
        reset_rate_cache()
        repository = Mock()
        repository.list_campaigns.return_value = [
            {
                "id": 30, "name": "Modelagem", "client": "Marca",
                "spent_usd": 2, "flow_kind": "model",
            },
            {
                "id": 40, "name": "Desdobrar", "client": "Marca",
                "spent_usd": 4, "flow_kind": "unfold",
                "creative_brief": {"flow_kind": "unfold"},
            },
        ]
        repository.list_generation_jobs.return_value = [
            {
                "id": 1, "campaign_id": 30, "campaign_name": "Modelagem",
                "job_type": "image", "model": "openai/gpt-image-2",
                "actual_cost_usd": 1.2, "estimated_cost_usd": 1, "status": "done",
            },
            {
                "id": 2, "campaign_id": 40, "campaign_name": "Desdobrar",
                "job_type": "image", "model": "openai/gpt-image-2",
                "actual_cost_usd": 3, "estimated_cost_usd": 3, "status": "done",
            },
        ]
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        models = service.list_campaigns("model")
        unfolds = service.list_campaigns("unfold")
        history = service.history(flow_kind="unfold")
        self.assertEqual([item["id"] for item in models], [30])
        self.assertEqual([item["id"] for item in unfolds], [40])
        self.assertEqual(unfolds[0]["spent_brl"], 20.0)
        self.assertEqual([item["id"] for item in history["modelings"]], [40])
        self.assertEqual(history["modelings"][0]["spent_brl"], 20.0)
        self.assertEqual([job["id"] for job in history["jobs"]], [2])
        self.assertEqual(history["total_brl"], 20.0)
        reset_rate_cache()

    def test_sufixo_de_lock_sempre_cita_as_travas(self):
        lock = unfold_image_lock({
            "headline": "Coleção Outono",
            "cta": "Conheça a coleção",
            "has_logo": True,
        })
        self.assertIn("LOCK BLOCK FOR GPT IMAGE 2", lock)
        self.assertIn("Coleção Outono", lock)
        self.assertIn("Conheça a coleção", lock)
        self.assertIn("logo mark", lock)

    @patch.dict("os.environ", {"USD_BRL_RATE": "5.5"})
    def test_rascunho_e_lote_publicavel_nao_mudam_montagem(self):
        reset_rate_cache()
        draft = resolve_image_tier("draft")
        publish = resolve_image_tier("publicavel")
        self.assertEqual((draft["quality"], draft["resolution"]), ("low", "1K"))
        self.assertEqual((publish["quality"], publish["resolution"]), ("high", "2K"))
        quote = quote_image_publish(3)
        self.assertEqual(quote["count"], 3)
        self.assertEqual(quote["quality"], "high")
        self.assertGreater(quote["total_brl"], quote["unit_brl"])
        self.assertIn("RESOLUTION UPGRADE ONLY", apply_publish_upgrade("LOCK copy"))
        captured = {}
        repository = Mock()
        context = {
            "id": 81,
            "position": 1,
            "production_id": 80,
            "campaign_id": 40,
            "format_template_id": 7,
            "format_slug": "instagram-feed",
            "default_size": "1080x1080",
            "prompt": "Approved unfold prompt",
            "prompt_status": "approved",
            "media_type": "image",
            "aspect_ratio": "1:1",
            "client_id": 10,
            "creative_brief": {
                "flow_kind": "unfold",
                "source": {"kv_asset_url": "/static/uploads/creative_references/kv.png"},
                "locks": {"headline": "Coleção Outono", "cta": "Conheça"},
            },
        }
        repository.get_scene_context.return_value = context
        repository.get_assets.return_value = [{
            "id": 90,
            "scene_id": 81,
            "asset_url": "/draft.png",
            "job_prompt": "Approved unfold prompt",
            "metadata": {"fidelity": "draft"},
        }]
        repository.create_generation_job.return_value = 21
        repository.add_generated_asset.return_value = {
            "id": 92, "asset_url": "/generated.png",
        }
        repository.list_client_brand_assets.return_value = []
        repository.get_campaign.return_value = {
            "id": 40,
            "name": "Outono",
            "spent_usd": 0,
            "client": {"name": "Marca"},
            "creative_brief": {"flow_kind": "unfold"},
            "productions": [{
                "id": 80,
                "format_template_id": 7,
                "scenes": [{
                    "id": 81,
                    "assets": [{
                        "id": 90,
                        "asset_type": "image",
                        "metadata": {"fidelity": "draft"},
                    }],
                }],
            }],
        }

        class CapturingGenerator(FakeGenerator):
            def generate_image(self, prompt, references, aspect_ratio, **kwargs):
                captured.setdefault("calls", []).append({
                    "prompt": prompt,
                    "references": references,
                    "quality": kwargs.get("quality"),
                    "resolution": kwargs.get("resolution"),
                })
                return super().generate_image(prompt, references, aspect_ratio, **kwargs)

        service = CreativeModelingService(
            repository=repository,
            generator=CapturingGenerator(),
            storage=FakeStorage(),
        )
        service.generate_scene(81, [])
        self.assertEqual(captured["calls"][0]["quality"], "low")
        self.assertEqual(captured["calls"][0]["resolution"], "1K")
        self.assertTrue(
            repository.create_generation_job.call_args.kwargs.get("allow_existing_scene")
            in (False, None)
        )
        service.publish_scene_asset(81, 90)
        self.assertEqual(captured["calls"][1]["quality"], "high")
        self.assertEqual(captured["calls"][1]["resolution"], "2K")
        self.assertIn("RESOLUTION UPGRADE ONLY", captured["calls"][1]["prompt"])
        self.assertTrue(captured["calls"][1]["references"])
        self.assertTrue(
            repository.create_generation_job.call_args.kwargs["allow_existing_scene"]
        )
        quoted = service.quote_campaign_publish(40, [90])
        self.assertEqual(quoted["count"], 1)
        self.assertEqual(quoted["pieces"][0]["asset_id"], 90)
        reset_rate_cache()

    def test_modelagem_alta_so_cenas_aprovadas_e_video_mockado(self):
        repository = Mock()
        approved = {
            "id": 90,
            "asset_type": "image",
            "status": "approved",
            "metadata": {"fidelity": "draft"},
        }
        pending = {
            "id": 91,
            "asset_type": "image",
            "status": "draft",
            "metadata": {"fidelity": "draft"},
        }
        high = {
            "id": 92,
            "asset_type": "image",
            "status": "approved",
            "metadata": {"fidelity": "publish"},
        }
        repository.get_campaign.return_value = {
            "id": 40,
            "name": "Outono",
            "spent_usd": 0,
            "client": {"name": "Marca"},
            "creative_brief": {"flow_kind": "model"},
            "productions": [{
                "id": 80,
                "format_template_id": 7,
                "scenes": [{"id": 81, "assets": [approved, pending]}],
            }],
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        quoted = service.quote_campaign_publish(40)
        self.assertEqual(quoted["count"], 1)
        self.assertEqual(quoted["pieces"][0]["asset_id"], 90)
        self.assertEqual(service.quote_campaign_publish(40, [91])["count"], 0)
        with self.assertRaises(ValueError) as error:
            service.publish_campaign(40, {"asset_ids": [91]})
        self.assertIn("aprovadas", str(error.exception))
        with self.assertRaises(ValueError) as error:
            service.prepare_campaign_video(40)
        self.assertIn("alta resolução", str(error.exception))
        repository.get_campaign.return_value["productions"][0]["scenes"][0]["assets"] = [
            approved, high,
        ]
        video = service.prepare_campaign_video(40)
        self.assertEqual(video["status"], "mocked")
        self.assertFalse(video["ready"])
        self.assertIn("não está pronto", video["message"])


if __name__ == "__main__":
    unittest.main()
