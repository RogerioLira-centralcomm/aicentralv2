"""Lab isolado de formato CTV: skill, spec, router, camadas e QA."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Blueprint, Flask
from pydantic import ValidationError

from aicentralv2.creative_format_lab.campaign_models import list_campaign_models, load_campaign_model
from aicentralv2.creative_format_lab.engineer import build_spec
from aicentralv2.creative_format_lab.catalog import (
    FORMAT_GROUPS,
    FORMATS,
    is_end_card,
    logo_visible_for,
    plate_for,
)
from aicentralv2.creative_format_lab.mockup import scene_logo_visible
from aicentralv2.creative_format_lab.stack import build_stack
from aicentralv2.creative_format_lab.decompose import decompose_creative
from aicentralv2.creative_format_lab.html_builder import build_scene_html, prototype_dir
from aicentralv2.creative_format_lab.layer_export import export_layers
from aicentralv2.creative_format_lab.pipeline import run_session
from aicentralv2.creative_format_lab.router import route_format
from aicentralv2.creative_format_lab.service import FormatLabService
from aicentralv2.creative_format_lab.spec import CreativeFormatSpec, parse_format_spec
from aicentralv2.creative_format_lab.storyboard import build_storyboard, quote_concept
from aicentralv2.creative_format_lab.close import close_scene
from aicentralv2.creative_format_lab.swap import (
    build_swap_prompt,
    quote_swap,
    read_swap_reference,
    resolve_aspect_ratio,
    swap_input_references,
    swap_reference,
)
from aicentralv2.creative_format_lab.guidelines import check_stack, protect_box
from aicentralv2.creative_format_lab.visual_qa import run_qa_loop
from aicentralv2.creative_modeling_repository import CreativeConflictError
from aicentralv2.creative_modeling_routes import register_creative_modeling_routes
from aicentralv2.creative_modeling_service import CreativeModelingService
from aicentralv2.creative_skills.loader import FORMAT_SKILL_KEYS, load_format_skill, load_skill, resolve_pack
from tests.test_modelagem_criativos import FakeGenerator, FakeRepository


TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
    b"\x00\x04\x00\x01\xf6\x17\x18\xd3\x00\x00\x00\x00IEND\xaeB`\x82"
)
PROTOTYPES = (
    Path(__file__).resolve().parents[1]
    / "aicentralv2"
    / "templates"
    / "format_prototypes"
    / "ctv"
    / "generic_ctv"
)


def _shot(_html, _width, _height):
    return TINY_PNG


def _qa_fail(*_args, **_kwargs):
    return {
        "message": {
            "content": {
                "passed": False,
                "score": 0.2,
                "defects": ["CTA fora do lugar"],
                "patches": [{"layer_id": "layer-cta", "text": "Veja agora"}],
            }
        }
    }


class CreativeFormatLabTest(unittest.TestCase):
    def test_loader_carrega_so_o_formato_pedido(self):
        skill = load_skill()
        self.assertIn("Creative Format Engineer", skill)
        linear = load_format_skill("ctv-video-linear-30")
        fifteen = load_format_skill("video-linear-15")
        qr = load_format_skill("ctv-video-qr")
        self.assertIn("ctv-video-linear-30", linear)
        self.assertIn("15 seconds", fifteen)
        self.assertNotIn("layer-qr", linear)
        self.assertIn("ctv-video-qr", qr)
        self.assertIn("layer-qr", qr)
        banner = load_format_skill("iab-billboard")
        self.assertIn("IAB banner", banner)
        self.assertIn("layer-headline", banner)
        self.assertIn("video-linear-15", FORMAT_SKILL_KEYS)
        self.assertIn("ctv-video-linear-30", FORMAT_SKILL_KEYS)
        self.assertIn("iab-billboard", FORMAT_SKILL_KEYS)
        with self.assertRaises(ValueError):
            load_format_skill("mobile-carousel")
        pack = resolve_pack("create", "iab-halfpage")
        self.assertEqual(pack["format_skill"], "iab-banner")

    def test_router_mapeia_qr_no_final(self):
        routed = route_format("QR no final do filme de 15s")
        self.assertEqual(routed["format"], "video-qr-15")
        self.assertEqual(routed["adapter"], "youtube_ctv")
        explicit = route_format("qualquer", format_key="ctv-video-linear-30")
        self.assertEqual(explicit["format"], "video-linear-15")

    def test_spec_rejeita_html_solto(self):
        payload = {
            "intent": "reconstruct",
            "format": "ctv-video-linear-30",
            "variant": "A",
            "adapter": "generic_ctv",
            "scenes": [
                {
                    "id": "scene_01",
                    "purpose": "hook",
                    "headline": "<!doctype html><html><body>x</body></html>",
                    "support": "ok",
                },
                {"id": "scene_02", "purpose": "benefit"},
                {"id": "scene_03", "purpose": "proof"},
                {"id": "scene_04", "purpose": "cta"},
            ],
        }
        with self.assertRaises(ValidationError):
            parse_format_spec(payload)
        with self.assertRaises(ValidationError):
            CreativeFormatSpec.model_validate({
                "format": "ctv-video-linear-30",
                "scenes": [],
            })
        echoed = parse_format_spec(
            {
                "intent": "create",
                "format": "iab-banner",
                "kind": "banner",
                "size_label": "300×250",
                "orientation": "horizontal",
                "adapter": "iab_box",
                "scenes": [
                    {"id": "scene_01", "purpose": "hook", "role": "gancho"},
                    {"id": "scene_02", "purpose": "benefit"},
                    {"id": "scene_03", "purpose": "proof"},
                    {"id": "scene_04", "purpose": "cta"},
                ],
            },
            expected_format="iab-halfpage",
        )
        self.assertEqual(echoed.format, "iab-halfpage")
        self.assertEqual(echoed.canvas.height, 600)
        self.assertEqual(echoed.scenes[0].purpose, "hook")

    def test_layer_export_nas_quatro_cenas_generic(self):
        for name in ("scene-01.html", "scene-02.html", "scene-03.html", "scene-04.html"):
            html = (PROTOTYPES / name).read_text(encoding="utf-8")
            layers = export_layers(html, "scene_01")
            ids = {item["id"] for item in layers}
            self.assertIn("scene_01-layer-brand", ids)
            self.assertIn("scene_01-layer-copy", ids)
            self.assertIn("scene_01-layer-key-visual", ids)
            self.assertTrue(all(item["w"] > 0 and item["h"] > 0 for item in layers))
        cta = export_layers((PROTOTYPES / "scene-04.html").read_text(encoding="utf-8"), "scene_04")
        self.assertTrue(any(item["tipo"] == "cta" for item in cta))

    def test_html_builder_preenche_marca_sem_redesenhar(self):
        spec = build_spec(
            route={
                "format": "ctv-video-linear-30",
                "adapter": "generic_ctv",
                "platform_label": "GENERIC CTV",
            },
            brand_name="CentralComm",
        )
        html = build_scene_html(spec, spec.scenes[0], dna={"logo": {"asset_url": ""}})
        self.assertIn("CentralComm", html)
        self.assertIn("plate-split", html)
        self.assertIn('id="layer-platform"', html)
        self.assertIn("16:9", html)
        self.assertNotIn("N:9", html)
        self.assertIn('id="layer-brand"', html)
        self.assertIn("class=\"render\"", html)
        self.assertIn("--brand-ink", html)
        hero = build_scene_html(spec, spec.scenes[2])
        end = build_scene_html(spec, spec.scenes[3])
        self.assertIn('class="stage plate-hero"', hero)
        self.assertIn('class="stage plate-center"', end)
        self.assertEqual(plate_for("proof"), "hero")
        self.assertEqual(plate_for("cta"), "center")
        self.assertTrue((prototype_dir("generic_ctv") / "scene-01.html").is_file())
        self.assertTrue((prototype_dir("iab_horizontal") / "scene-01.html").is_file())
        self.assertTrue((prototype_dir("iab_vertical") / "styles.css").is_file())
        banner = build_spec(
            route={
                "format": "iab-halfpage",
                "adapter": "iab_vertical",
                "platform_label": "300×600",
            },
            brand_name="Tim",
        )
        self.assertEqual(banner.canvas.width, 300)
        self.assertEqual(banner.canvas.height, 600)
        half = build_scene_html(banner, banner.scenes[0])
        self.assertIn("layer-headline", half)
        self.assertIn("--stage-ratio:300 / 600", half)
        self.assertIn("is-tall", half)
        self.assertIn("is-banner", half)
        keys = {item["key"] for item in FORMATS}
        self.assertIn("iab-billboard", keys)
        self.assertIn("iab-leaderboard", keys)
        self.assertIn("iab-medium", keys)
        self.assertIn("iab-skyscraper", keys)
        self.assertEqual(
            {item["key"] for item in FORMAT_GROUPS},
            {"15s", "horizontal", "vertical", "retangulo", "social"},
        )
        lead = build_spec(
            route={
                "format": "iab-leaderboard",
                "adapter": "iab_horizontal",
                "platform_label": "728×90",
            },
            brand_name="Tim",
        )
        self.assertEqual(lead.canvas.width, 728)
        self.assertEqual(lead.canvas.height, 90)
        board = build_scene_html(lead, lead.scenes[0])
        self.assertIn("is-thin", board)
        self.assertIn("is-wide", board)
        self.assertIn("is-banner", board)
        self.assertIn("layer-headline", board)

    def test_cartaz_separa_elenco_e_fundo_no_html(self):
        from aicentralv2.creative_format_lab.stack import build_stack

        spec = build_spec(
            route={
                "format": "ctv-video-linear-30",
                "adapter": "generic_ctv",
                "platform_label": "16:9",
            },
            brand_name="Belotur",
        )
        html = build_scene_html(
            spec,
            spec.scenes[0],
            dna={"colors": {"accent": "#7c4dff"}},
            assets={
                "cast_url": "https://cdn.example/elenco.png",
                "ground_url": "https://cdn.example/campo.png",
                "field": "#7c4dff",
            },
        )
        self.assertIn("plate-cast", html)
        self.assertIn("layer-cast", html)
        self.assertIn("layer-ground", html)
        self.assertIn("--cast-image:url('https://cdn.example/elenco.png')", html)
        self.assertIn("--field:#7c4dff", html)
        self.assertIn("--pennant", html)
        html = build_scene_html(
            spec,
            spec.scenes[0],
            dna={"colors": {"accent": "#7c4dff"}},
            assets={
                "cast_url": "https://cdn.example/elenco.png",
                "field": "#7c4dff",
                "chips": ["Zé Vaqueiro", "Mumuzinho"],
                "meta": "24, 25 e 26 julho",
                "lockup": "Belotur",
            },
        )
        self.assertIn('class="chip"', html)
        self.assertIn("Zé Vaqueiro", html)
        self.assertIn("24, 25 e 26 julho", html)
        self.assertIn("Belotur", html)
        stack = build_stack(
            spec.scenes[0],
            brand={"name": "Belotur", "primary_color": "#7c4dff"},
            assets={"cast_url": "https://cdn.example/elenco.png"},
        )
        self.assertEqual(stack["plate"], "cast")
        self.assertEqual(stack["background"]["kind"], "field")
        self.assertTrue(any(item["role"] == "cast" for item in stack["layers"]))
        empty = decompose_creative("https://cdn.example/ref.png")
        self.assertEqual(empty["cast_url"], "")
        calls = []

        def fake(prompt, **kwargs):
            calls.append((prompt, kwargs.get("background")))
            return b"png"

        parts = decompose_creative("https://cdn.example/ref.png", fake)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], "opaque")
        self.assertEqual(calls[1][1], "opaque")
        self.assertTrue(parts["cast_url"].startswith("data:image/png;base64,"))

    def test_qa_loop_para_no_terceiro_patch(self):
        spec = build_spec(
            route={
                "format": "ctv-video-linear-30",
                "adapter": "generic_ctv",
                "platform_label": "GENERIC CTV",
            },
            brand_name="Marca",
        )
        scenes = [
            {
                "id": scene.id,
                "html": build_scene_html(spec, scene),
                "label": scene.purpose,
                "duration": scene.duration,
                "role": "gancho",
            }
            for scene in spec.scenes
        ]
        result = run_qa_loop(
            spec=spec,
            scenes=scenes,
            renders=3,
            text_callable=_qa_fail,
            screenshot=_shot,
        )
        first_versions = [item for item in result["versions"] if item["scene_id"] == "scene_01"]
        self.assertEqual(len(first_versions), 3)
        self.assertEqual(len([item for item in first_versions if item["discarded"]]), 2)
        self.assertFalse(result["qa"]["passed"])
        self.assertIn("Veja agora", result["scenes"][-1]["html"])

    def test_handoff_recusado_se_qa_nao_passou(self):
        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)
        session = lab.create_session({"client_id": 10, "campaign_id": 30})
        self.assertIn(session["id"], repository.concept_sessions)
        stored = repository.campaign_briefs[30]["format_lab"]["sessions"][session["id"]]
        stored["qa"] = {"passed": False}
        stored["cards"] = [{"id": "scene_01", "layers": [{"tipo": "cta", "x": 6, "y": 78, "w": 18, "h": 8}]}]
        with self.assertRaises(CreativeConflictError):
            lab.handoff(session["id"])

    def test_run_sem_llm_gera_html_e_camadas(self):
        result = run_session(
            {
                "format": "ctv-video-qr",
                "variant": "A",
                "intent": "html",
                "message": "QR no final",
                "renders": 1,
                "brand_name": "Marca Exemplo",
            },
            client={"id": 10, "name": "Marca Exemplo", "primary_color": "#111111"},
            screenshot=_shot,
        )
        self.assertEqual(result["format"], "video-qr-15")
        self.assertEqual(len(result["scenes"]), 4)
        self.assertEqual(result["duration"], 15)
        self.assertTrue(result["qa"]["passed"])
        self.assertTrue(any("layer-qr" in item["id"] for item in result["cards"][2]["layers"]))

    def test_pack_create_nao_carrega_reconstruct(self):
        plan = resolve_pack("create", "ctv-video-linear-30")
        ids = [item["id"] for item in plan["skills"]]
        self.assertEqual(plan["intent"], "create")
        self.assertIn("create", ids)
        self.assertIn("implement", ids)
        self.assertIn("validate", ids)
        self.assertIn("video-15", ids)
        self.assertNotIn("reconstruct", ids)
        self.assertNotIn("refine", ids)

    def test_campanhas_modelo_tem_quatro_cenas(self):
        slugs = {item["slug"] for item in list_campaign_models()}
        self.assertEqual(
            slugs,
            {"tim-controle-ctv", "vivara-presente-ctv", "rededor-cuidado-ctv"},
        )
        for slug in slugs:
            model = load_campaign_model(slug)
            self.assertEqual(len(model["scenes"]), 4)
            self.assertTrue(all(scene.get("headline") for scene in model["scenes"]))

    def test_run_com_campanha_tim_usa_headline_do_modelo(self):
        result = run_session(
            {
                "campaign_slug": "tim-controle-ctv",
                "intent": "create",
                "renders": 1,
            },
            client={
                "id": 11,
                "name": "Tim",
                "primary_color": "#0033A0",
                "brand_profile": {
                    "brand_summary": "Conexão que acompanha o mês.",
                    "campaign_opportunities": ["Controle que cabe no mês"],
                    "products_services": ["Tim Controle"],
                    "forbidden_elements": ["preço inventado"],
                },
            },
            screenshot=_shot,
        )
        headlines = [scene["headline"] for scene in result["scenes"]]
        self.assertEqual(result["format"], "video-linear-15")
        self.assertEqual(len(result["scenes"]), 4)
        self.assertIn("O mês acabou. A internet, não.", headlines)
        self.assertNotIn("Sua história entra em cena.", headlines)
        self.assertEqual(result["brand"]["source"], "marcas")
        self.assertIn("create", result["trace"]["packs"])
        self.assertTrue(result["trace"]["skills"])
        self.assertTrue(result["trace"]["steps"])
        self.assertEqual(result["spec"]["canvas"]["width"], 1920)
        self.assertEqual(result["spec"]["canvas"]["height"], 1080)

    def test_arquivos_da_mesa_entram_no_html(self):
        photo = "https://cdn.example/ref-sala.jpg"
        result = run_session(
            {
                "campaign_slug": "tim-controle-ctv",
                "intent": "create",
                "renders": 1,
                "images": [photo],
            },
            client={"id": 11, "name": "Tim"},
            screenshot=_shot,
        )
        self.assertIn("has-photo", result["scenes"][0]["html"])
        self.assertIn(photo, result["scenes"][0]["html"])
        self.assertIn(photo, result["references"])

    def test_storyboard_aceita_quatro_ou_cinco_cenas(self):
        client = {"id": 11, "name": "Tim", "primary_color": "#0033A0"}
        four = build_storyboard(
            {"campaign_slug": "tim-controle-ctv", "scene_count": 4},
            client=client,
        )
        five = build_storyboard(
            {"campaign_slug": "tim-controle-ctv", "scene_count": 5},
            client=client,
        )
        self.assertEqual(len(four["storyboard"]), 4)
        self.assertEqual(len(five["storyboard"]), 5)
        self.assertEqual(five["storyboard"][1]["purpose"], "context")
        self.assertEqual(four["duration"], 15)
        self.assertEqual(len(four["passes"]), 2)
        self.assertGreater(quote_concept({"scene_count": 4})["cost_usd"], 0)
        full = quote_concept({"scene_count": 4, "kind": "full"})
        story = quote_concept({"scene_count": 4, "kind": "storyboard"})
        scene = quote_concept({"kind": "scene"})
        self.assertEqual(story["passes"], 2)
        self.assertEqual(scene["scene_versions"], 3)
        self.assertGreater(full["cost_usd"], story["cost_usd"])

    def test_conceito_usa_campanha_quando_o_provedor_falha(self):
        from aicentralv2.creative_modeling_generation import OpenRouterError

        def boom(*_a, **_k):
            raise OpenRouterError("Não foi possível consultar o provedor de IA.")

        board = build_storyboard(
            {"campaign_slug": "tim-controle-ctv", "scene_count": 4},
            client={"id": 11, "name": "Tim"},
            text_callable=boom,
        )
        self.assertEqual(len(board["storyboard"]), 4)
        self.assertEqual(board["provider"], "campaign")
        self.assertTrue(board["storyboard"][0]["headline"])

    def test_conceito_usa_campanha_quando_o_json_do_provedor_e_invalido(self):
        def bad(*_a, **_k):
            return {"message": {"content": {"format": "video-linear-15", "scenes": []}}}

        board = build_storyboard(
            {"campaign_slug": "vivara-presente-ctv", "scene_count": 4},
            client={"id": 4, "name": "Vivara"},
            text_callable=bad,
        )
        self.assertEqual(len(board["storyboard"]), 4)
        self.assertEqual(board["provider"], "campaign")
        self.assertIn("momentos", board["storyboard"][0]["headline"].lower())

    def test_engenheiro_chama_o_provedor_sem_papel_developer(self):
        called = {}

        def fake(messages, **_kwargs):
            called["roles"] = [item["role"] for item in messages]
            content = messages[-1]["content"]
            called["urls"] = []
            if isinstance(content, list):
                for block in content:
                    url = ((block or {}).get("image_url") or {}).get("url")
                    if url:
                        called["urls"].append(url)
            return {
                "message": {
                    "content": {
                        "intent": "create",
                        "format": "video-linear-15",
                        "variant": "A",
                        "adapter": "generic_ctv",
                        "platform_label": "CTV",
                        "brand_name": "Tim",
                        "scenes": [
                            {"id": "scene_01", "headline": "A", "purpose": "hook"},
                            {"id": "scene_02", "headline": "B", "purpose": "context"},
                            {"id": "scene_03", "headline": "C", "purpose": "benefit"},
                            {"id": "scene_04", "headline": "D", "purpose": "cta", "cta": "Monte o seu"},
                        ],
                    }
                }
            }

        board = build_storyboard(
            {
                "campaign_slug": "tim-controle-ctv",
                "scene_count": 4,
                "images": [
                    "/static/uploads/client_logos/tim.png",
                    "https://cdn.example/ok.jpg",
                ],
            },
            client={"id": 11, "name": "Tim"},
            text_callable=fake,
        )
        self.assertEqual(called["roles"], ["system", "user"])
        self.assertEqual(called["urls"], ["https://cdn.example/ok.jpg"])
        self.assertEqual(len(board["storyboard"]), 4)

    def test_conceito_e_base_viram_historico_da_campanha(self):
        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)
        first = lab.create_session({
            "client_id": 10,
            "campaign_id": 30,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
        })
        board = lab.storyboard(first["id"], {
            "campaign_slug": "vivara-presente-ctv",
            "scene_count": 4,
        })
        again = lab.create_session({
            "client_id": 10,
            "campaign_id": 30,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
        })
        self.assertEqual(again["id"], first["id"])
        self.assertEqual(len(again["storyboard"] or board["storyboard"]), 4)
        listed = lab.list_sessions({
            "client_id": 10,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
        })
        self.assertEqual(listed["active"]["id"], first["id"])
        self.assertEqual(listed["history"][0]["stage"], "concept")
        self.assertEqual(listed["history"][0]["session_id"], first["id"])
        base = lab.mockup(first["id"], {
            "campaign_slug": "vivara-presente-ctv",
            "text_callable": None,
            "screenshot": _shot,
        })
        self.assertTrue(base["base_html"])
        listed = lab.list_sessions({
            "client_id": 10,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
        })
        self.assertEqual(listed["active"]["stage"], "base")
        self.assertEqual(listed["history"][0]["stage"], "base")
        fresh = lab.create_session({
            "client_id": 10,
            "campaign_id": 30,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
            "fresh": True,
        })
        self.assertNotEqual(fresh["id"], first["id"])

    def test_storyboard_cobrado_no_ledger(self):
        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)
        session = lab.create_session({"client_id": 10, "campaign_id": 30})
        result = lab.storyboard(session["id"], {"campaign_slug": "tim-controle-ctv", "scene_count": 4})
        self.assertEqual(len(result["storyboard"]), 4)
        self.assertTrue(repository.jobs)
        self.assertGreater(float(repository.jobs[-1]["args"][6]), 0)
        self.assertEqual(repository.jobs[-1]["kwargs"]["concept_session_id"], session["id"])
        self.assertEqual(len(repository.concept_scenes[session["id"]]), 4)
        self.assertEqual(repository.get_concept_session(session["id"])["status"], "concept")
        self.assertTrue(
            any(item.get("pass_kind") == "refine" for item in repository.concept_passes[session["id"]])
        )

    def test_prompts_recusam_copy_pobre_e_respeitam_edicao(self):
        root = Path(__file__).resolve().parents[1]
        create = (root / "aicentralv2" / "creative_skills" / "packs" / "create" / "SKILL.md").read_text(encoding="utf-8")
        refine = (root / "aicentralv2" / "creative_skills" / "packs" / "refine" / "SKILL.md").read_text(encoding="utf-8")
        video = (root / "aicentralv2" / "creative_skills" / "formats" / "video-15" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Refuse generic hooks", create)
        self.assertIn("key-visual", create)
        self.assertIn("user locks", refine)
        self.assertIn("3 stills per scene", video)
        client = {
            "id": 22,
            "name": "Vivara",
            "primary_color": "#1A1208",
            "brand_assets": [
                {"role": "creative", "asset_url": "https://cdn.example/vivara-caixa.jpg"},
                {"role": "reference", "asset_url": "https://cdn.example/vivara-anel.jpg"},
            ],
        }
        board = build_storyboard(
            {
                "campaign_slug": "vivara-presente-ctv",
                "scene_count": 4,
                "images": ["https://cdn.example/vivara-caixa.jpg"],
                "key_visuals": {"scene_01": "https://cdn.example/vivara-caixa.jpg"},
                "storyboard": [{"id": "scene_01", "headline": "A caixa abre no escuro."}],
            },
            client=client,
        )
        headlines = [item["headline"] for item in board["storyboard"]]
        self.assertEqual(headlines[0], "A caixa abre no escuro.")
        self.assertIn("A peça que fica.", headlines)
        self.assertNotIn("Sua história entra em cena.", headlines)
        self.assertTrue(board["storyboard"][0]["set_note"])
        self.assertEqual(board["storyboard"][0]["key_visual"], "https://cdn.example/vivara-caixa.jpg")

    def test_gera_uma_cena_com_tres_versoes_e_descartadas(self):
        photo = "https://cdn.example/vivara-anel.jpg"
        scores = [0.25, 0.45, 0.88]
        calls = {"n": 0}

        def _qa_progress(*_args, **_kwargs):
            calls["n"] += 1
            score = scores[min(calls["n"], 3) - 1]
            return {
                "message": {
                    "content": {
                        "passed": score >= 0.8,
                        "score": score,
                        "defects": [] if score >= 0.8 else ["Densidade alta para TV"],
                        "patches": [] if score >= 0.8 else [{"layer_id": "layer-cta", "text": "Encontre a peça"}],
                    }
                }
            }

        draft = build_storyboard(
            {"campaign_slug": "vivara-presente-ctv", "scene_count": 4},
            client={"id": 22, "name": "Vivara"},
        )
        shell = run_session(
            {
                "campaign_slug": "vivara-presente-ctv",
                "stage": "mockup",
                "mockup_passes": 1,
                "spec": draft["spec"],
                "images": [photo],
            },
            client={"id": 22, "name": "Vivara"},
            screenshot=_shot,
        )
        first = run_session(
            {
                "campaign_slug": "vivara-presente-ctv",
                "intent": "create",
                "scene_id": "scene_02",
                "renders": 3,
                "images": [photo],
                "key_visuals": {"scene_02": photo},
                "spec": draft["spec"],
                "base_html": shell.get("base_html"),
                "mockup": shell.get("mockup"),
            },
            client={"id": 22, "name": "Vivara", "primary_color": "#1A1208"},
            text_callable=_qa_progress,
            screenshot=_shot,
        )
        versions = [item for item in first["versions"] if item["scene_id"] == "scene_02"]
        self.assertEqual(first["scenes"][1]["id"], "scene_02")
        self.assertIn(photo, first["scenes"][1]["html"])
        self.assertEqual(len(versions), 3)
        self.assertEqual(len([item for item in versions if item["discarded"]]), 2)
        self.assertTrue(any(item["chosen"] for item in versions))
        self.assertGreater(versions[-1]["score"], versions[0]["score"])
        second = run_session(
            {
                **first,
                "scene_id": "scene_03",
                "renders": 3,
                "key_visuals": {"scene_02": photo, "scene_03": photo},
            },
            client={"id": 22, "name": "Vivara"},
            screenshot=_shot,
        )
        self.assertTrue(any(item.get("html") for item in second["scenes"] if item["id"] == "scene_02"))
        self.assertTrue(any(item["scene_id"] == "scene_02" and item["discarded"] for item in second["versions"]))

    def test_mockup_preto_define_o_padrao_e_logo_nao_vai_em_toda_cena(self):
        self.assertTrue(logo_visible_for("brand"))
        self.assertTrue(logo_visible_for("cta"))
        self.assertFalse(logo_visible_for("hook"))
        self.assertFalse(logo_visible_for("product"))
        self.assertFalse(logo_visible_for("lifestyle"))
        client = {
            "id": 22,
            "name": "Vivara",
            "primary_color": "#C4A574",
            "brand_assets": [{"role": "creative", "asset_url": "https://cdn.example/vivara-caixa.jpg"}],
        }
        base = run_session(
            {
                "campaign_slug": "vivara-presente-ctv",
                "stage": "mockup",
                "mockup_passes": 2,
                "images": ["https://cdn.example/vivara-caixa.jpg"],
            },
            client=client,
            screenshot=_shot,
        )
        self.assertTrue(base["base_html"])
        self.assertIn("background:#111", base["base_html"])
        self.assertIn("layer-key-visual", base["base_html"])
        self.assertIn("plate-split", base["base_html"])
        self.assertNotIn("text-transform:uppercase", (PROTOTYPES / "styles.css").read_text(encoding="utf-8"))
        self.assertIn("--brand-ink", base["base_html"])
        self.assertEqual(len(base["mockup"]["versions"]), 2)
        self.assertEqual(base["mockup"]["model"], "openai/gpt-4o-mini")
        product = run_session(
            {
                **base,
                "scene_id": "scene_02",
                "renders": 1,
                "key_visuals": {"scene_02": "https://cdn.example/vivara-anel.jpg"},
            },
            client=client,
            screenshot=_shot,
        )
        html = product["scenes"][1]["html"]
        self.assertFalse(product["scenes"][1]["logo_visible"])
        self.assertIn('id="layer-brand"', html)
        self.assertIn("hidden", html)
        self.assertIn("layer-key-visual", html)
        self.assertIn("--brand-ink", html)
        hook = run_session(
            {
                **product,
                "scene_id": "scene_01",
                "renders": 1,
            },
            client=client,
            screenshot=_shot,
        )
        self.assertTrue(hook["scenes"][0]["logo_visible"])
        self.assertEqual(hook["scenes"][0]["purpose"], "brand")
        self.assertIn("Vivara", hook["scenes"][0]["html"])
        end = run_session(
            {
                **hook,
                "scene_id": "scene_04",
                "renders": 1,
            },
            client=client,
            screenshot=_shot,
        )
        last = end["scenes"][3]
        self.assertTrue(last["logo_visible"])
        self.assertIn("plate-center", last["html"])
        self.assertNotIn("hidden", last["html"].split('id="layer-brand"')[1][:40])
        cheap = quote_concept({"kind": "mockup"})
        full = quote_concept({"scene_count": 4, "kind": "full"})
        self.assertLess(cheap["cost_usd"], quote_concept({"kind": "storyboard"})["cost_usd"])
        self.assertIn("mockup_passes", full)

    def test_mockup_entrega_html_se_o_provedor_falha(self):
        from aicentralv2.creative_modeling_generation import OpenRouterError

        def boom(*_args, **_kwargs):
            raise OpenRouterError("Provider returned error")

        base = run_session(
            {
                "campaign_slug": "vivara-presente-ctv",
                "stage": "mockup",
                "mockup_passes": 2,
            },
            client={"id": 22, "name": "Vivara"},
            text_callable=boom,
            screenshot=_shot,
        )
        self.assertTrue(base["base_html"])
        self.assertIn("layer-key-visual", base["base_html"])
        self.assertEqual(base["mockup"]["provider"], "plate")
        self.assertEqual(len(base["mockup"]["versions"]), 2)

    def test_mockup_entrega_html_se_o_screenshot_falha(self):
        def boom(*_args, **_kwargs):
            raise RuntimeError("chromium down")

        base = run_session(
            {
                "campaign_slug": "vivara-presente-ctv",
                "stage": "mockup",
                "mockup_passes": 2,
            },
            client={"id": 22, "name": "Vivara"},
            text_callable=None,
            screenshot=boom,
        )
        self.assertTrue(base["base_html"])
        self.assertIn("layer-key-visual", base["base_html"])
        self.assertTrue(base["mockup"]["render_url"].startswith("data:image/png"))
        self.assertEqual(len(base["mockup"]["versions"]), 2)

    def test_mockup_devolve_html_se_a_gravacao_explode(self):
        from aicentralv2.creative_format_lab.service import _slim_lab_session

        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)
        session = lab.create_session({"client_id": 10, "campaign_id": 30})
        lab.storyboard(session["id"], {"campaign_slug": "vivara-presente-ctv", "scene_count": 4})
        repository.update_campaign_bancada = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("jsonb")
        )
        repository.upsert_concept_session = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("jsonb")
        )
        result = lab.mockup(session["id"], {
            "campaign_slug": "vivara-presente-ctv",
            "text_callable": None,
            "screenshot": _shot,
        })
        self.assertTrue(result["base_html"])
        self.assertIn("layer-key-visual", result["base_html"])
        slim = _slim_lab_session({
            "mockup": {
                "html": "<html></html>",
                "render_url": "data:image/png;base64,abc",
                "versions": [{"attempt": 1, "html": "<html></html>", "png_data_url": "data:image/png;base64,abc"}],
            },
            "renders": [{"png_data_url": "data:image/png;base64,abc"}],
        })
        self.assertNotIn("png_data_url", slim["mockup"]["versions"][0])
        self.assertEqual(slim["renders"][0]["png_data_url"], "")

    def test_screenshot_html_devolve_png_se_o_chromium_cai(self):
        from aicentralv2 import creative_html_compose as compose

        with patch.object(compose, "_browser_instance", side_effect=RuntimeError("no chrome")):
            png = compose.screenshot_html("<html></html>", 64, 64)
        self.assertEqual(png, compose.BACKUP_PNG)

    def test_logo_opcional_no_gancho_e_obrigatoria_no_fechamento(self):
        self.assertFalse(is_end_card("proof", "scene_04", 5))
        self.assertTrue(is_end_card("proof", "scene_04", 4))
        self.assertTrue(is_end_card("cta", "scene_05", 5))
        self.assertFalse(scene_logo_visible("hook", "scene_01", {"scene_count": 4}))
        self.assertTrue(scene_logo_visible(
            "hook",
            "scene_01",
            {"scene_count": 4, "storyboard": [{"id": "scene_01", "logo_visible": True}]},
        ))
        self.assertTrue(scene_logo_visible(
            "cta",
            "scene_04",
            {"scene_count": 4, "storyboard": [{"id": "scene_04", "logo_visible": False}]},
        ))
        self.assertTrue(scene_logo_visible("hook", "scene_01", {"scene_count": 4}, scene_flag=True))
        stack = build_stack({"id": "scene_04", "purpose": "cta", "cta": "Encontre a loja"})
        logo = next(item for item in stack["layers"] if item["role"] == "logo")
        self.assertGreaterEqual(logo["y"], 20)
        self.assertLessEqual(logo["y"], 40)
        self.assertEqual(stack["plate"], "center")

    def test_overlay_skill_entra_ou_sai_do_prompt_da_cena(self):
        from aicentralv2.creative_format_lab.catalog import catalog_payload
        from aicentralv2.creative_format_lab.engineer import normalize_knobs
        from aicentralv2.creative_format_lab.mockup import _mockup_system
        from aicentralv2.creative_skills.visual import load_visual_brief

        catalog = catalog_payload()
        ids = {item["id"] for item in catalog["visual_skills"]}
        self.assertIn("imagegen-frontend-web", ids)
        self.assertIn("frontend-design", ids)
        self.assertTrue(all(item.get("locked") for item in catalog["base_skills"]))
        self.assertEqual(load_visual_brief([], stage="html"), "")
        with_skill = load_visual_brief(["imagegen-frontend-web"], stage="html")
        self.assertIn("Uma placa por cena", with_skill)
        self.assertIn("esquerda-texto", with_skill)
        self.assertNotIn("Uma placa por cena", _mockup_system({"selected_skills": []}))
        self.assertIn("Uma placa por cena", _mockup_system({"selected_skills": ["imagegen-frontend-web"]}))
        knobs = normalize_knobs({"selected_skills": []})
        self.assertEqual(knobs["selected_skills"], [])
        default = normalize_knobs({})
        self.assertIn("imagegen-frontend-web", default["selected_skills"])


class CreativeFormatLabDeskTest(unittest.TestCase):
    def test_mesa_registrada_no_shell(self):
        from aicentralv2.creative_modeling_routes import MC_DESKS

        self.assertIn("mesa", MC_DESKS)
        self.assertIn("lab", MC_DESKS)
        self.assertIn("placas", MC_DESKS)
        self.assertIn("trocar", MC_DESKS)
        self.assertEqual(MC_DESKS["trocar"]["page_js"], "js/mc-trocar.js")
        self.assertEqual(MC_DESKS["mesa"]["panel"], "parametros/_mc_mesa.html")
        self.assertEqual(MC_DESKS["mesa"]["page_js"], "js/mc-mesa.js")
        self.assertEqual(MC_DESKS["placas"]["page_js"], "js/mc-placas.js")
        root = Path(__file__).resolve().parents[1]
        shell = (root / "aicentralv2" / "templates" / "parametros" / "_mc_shell.html").read_text(encoding="utf-8")
        self.assertIn("mc-desk-nav-flow", shell)
        self.assertIn("mc-desk-nav-lab", shell)
        self.assertIn("mc-chrome", shell)
        self.assertIn("mc-desk-drop", shell)
        self.assertNotIn("'Fluxo'", shell)
        self.assertNotIn("'Páginas'", shell)
        self.assertNotIn("Início", shell)
        self.assertIn("mcFormatDrop", shell)
        self.assertIn("mcFormatMenu", shell)
        self.assertIn("modelagem_mesa", shell)
        self.assertIn("modelagem_placas", shell)
        self.assertIn("modelagem_trocar", shell)
        html = (root / "aicentralv2" / "templates" / "parametros" / "_mc_mesa.html").read_text(encoding="utf-8")
        self.assertIn("mc-mesa-stage", html)
        self.assertIn("mcMesaStage", html)
        self.assertIn("Solte a foto no quadro", html)
        self.assertIn("Montar conceito", html)
        self.assertIn("Montar cena 1", html)
        self.assertIn("mcMesaSkills", html)
        self.assertIn("mcMesaBaseSkills", html)
        self.assertIn("Fechar cena", html)
        self.assertIn("Modelar base", html)
        self.assertIn("mcMesaMockup", html)
        self.assertIn("mcMesaBaseDialog", html)
        self.assertIn("Montar a base", html)
        self.assertIn("mcMesaBaseWait", html)
        self.assertIn("mcMesaBaseFrame", html)
        self.assertIn("mcMesaRunKey", html)
        self.assertIn("mcMesaRunSeq", html)
        self.assertIn("mcMesaRunTakes", html)
        self.assertIn("mcMesaRunBeats", html)
        self.assertIn("mcMesaBaseNote", html)
        self.assertIn("mcMesaHistory", html)
        self.assertIn("Histórico desta campanha", html)
        self.assertIn("mcMesaLogo", html)
        self.assertIn("mcMesaKeys", html)
        self.assertIn("mcMesaVersions", html)
        self.assertIn("mcMesaOffer", html)
        self.assertIn("mcMesaTrace", html)
        self.assertIn("mcMesaOps", html)
        self.assertIn("Ordem do 15s", html)
        self.assertIn("Duas passagens no roteiro de 15s", html)
        self.assertIn("mcMesaStrip", html)
        self.assertIn("Abrir Marcas", html)
        js = (root / "aicentralv2" / "static" / "js" / "mc-mesa.js").read_text(encoding="utf-8")
        self.assertIn("/parametros/api/format-lab/sessions", js)
        self.assertIn("storyboard", js)
        self.assertIn("handoff", js)
        self.assertIn("tim-controle-ctv", js)
        self.assertIn("Tim", js)
        self.assertIn("Vivara", js)
        self.assertIn("Rede D", js)
        self.assertIn("campaign_slug", js)
        self.assertIn("autofillVivara", js)
        self.assertIn("vivara-presente-ctv", js)
        self.assertIn("key_visuals", js)
        self.assertIn("/mockup", js)
        self.assertIn("openBaseDialog", js)
        self.assertIn("runCurrentBeat", js)
        self.assertIn("paintRunStill", js)
        self.assertIn("startRunProgress", js)
        self.assertIn("resumeDesk", js)
        self.assertIn("renderHistory", js)
        self.assertIn("openSavedSession", js)
        self.assertIn("showBasePreview", js)
        self.assertIn("srcdoc", js)
        self.assertIn("mcMesaBaseWait", js)
        self.assertIn("mcMesaBaseDialog", js)
        self.assertIn("logo_visible", js)
        self.assertIn("isLastScene", js)
        self.assertIn("plateLabel", js)
        self.assertIn("renders: 3", js)
        self.assertIn("selected_skills", js)
        self.assertIn("assembleSceneOne", js)
        self.assertIn("scene_id", js)
        self.assertIn("/close", js)
        self.assertIn("closeScene", js)
        self.assertIn("/mockup", js)
        self.assertIn("logo_visible", js)
        self.assertIn("function renderOps", js)
        self.assertIn("function currentOp", js)
        self.assertIn("function applyStage", js)
        self.assertIn("state.mounting", js)
        self.assertIn("function currentFormat", js)
        self.assertIn("mcFormatMenu", js)
        self.assertIn("format_groups", js)
        self.assertIn("formatTouched", js)
        self.assertIn("--mc-stage-ratio", js)
        self.assertIn("frame.style.transform = ''", js)
        self.assertNotIn("1920px", js)
        trocar = (root / "aicentralv2" / "templates" / "parametros" / "_mc_trocar.html").read_text(encoding="utf-8")
        self.assertIn("mcSwapOut", trocar)
        self.assertIn("9:16", trocar)
        self.assertIn("mcSwapElements", trocar)
        swap_js = (root / "aicentralv2" / "static" / "js" / "mc-trocar.js").read_text(encoding="utf-8")
        self.assertIn("/parametros/api/format-lab/swap/read", swap_js)
        self.assertIn("aspect_ratio", swap_js)
        self.assertIn("logo_used", swap_js)
        placas = (root / "aicentralv2" / "templates" / "parametros" / "_mc_placas.html").read_text(encoding="utf-8")
        self.assertIn("mcPlacasStudio", placas)
        self.assertIn("mcPlacasList", placas)
        self.assertIn("Montar IAB base", placas)
        placas_js = (root / "aicentralv2" / "static" / "js" / "mc-placas.js").read_text(encoding="utf-8")
        self.assertIn("/parametros/api/format-lab/plates", placas_js)
        self.assertIn("/parametros/api/format-lab/plates/bind", placas_js)
        self.assertIn("/parametros/api/format-lab/plates/patch", placas_js)
        self.assertIn("apply_to_all", placas_js)
        self.assertIn("selected_channels", placas_js)


class CreativeFormatLabPlatesTest(unittest.TestCase):
    def test_kit_da_marca_monta_html_e_canais(self):
        from aicentralv2.creative_format_lab.catalog import plate_kit_formats
        from aicentralv2.creative_format_lab.plates import (
            build_plate_kit,
            kit_auto_name,
            normalize_bindings,
            patch_plate_kit,
            starter_copy,
        )

        keys = {item["key"] for item in plate_kit_formats()}
        self.assertIn("iab-leaderboard", keys)
        self.assertIn("feed-1x1", keys)
        self.assertIn("story-9x16", keys)
        self.assertIn("video-linear-15", keys)
        copy = starter_copy({
            "name": "Vivara",
            "products_services": ["Joias"],
            "campaign_opportunities": ["O presente que marca o momento"],
            "brand_summary": "Joia como memória.",
        })
        self.assertEqual(copy["brand_name"], "Vivara")
        self.assertIn("presente", copy["headline"].lower())
        kit = build_plate_kit({
            "id": 9,
            "name": "Vivara",
            "brand_profile": {
                "brand_summary": "Joia como memória.",
                "products_services": ["Joias"],
                "fonts": [{"family": "Playfair Display", "role": "display"}],
                "brand_dna": {
                    "fonts": {"primary": "Playfair Display", "fallback": "Georgia"},
                },
                "plate_channels": {"feed-1x1": ["instagram"]},
            },
        }, refine=False)
        self.assertGreaterEqual(len(kit["plates"]), 10)
        self.assertTrue(all(item["scene_id"] == "scene_01" for item in kit["plates"]))
        self.assertIn("IAB base", kit["name"])
        self.assertRegex(kit["name"], r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")
        self.assertIn("Vivara", kit_auto_name("Vivara"))
        feed = next(item for item in kit["plates"] if item["key"] == "feed-1x1")
        self.assertIn("layer-headline", feed["html"])
        self.assertIn("Playfair Display", feed["html"])
        self.assertIn("fonts.googleapis.com", feed["html"])
        self.assertIn("1080×1080", feed["size_label"])
        self.assertTrue(any(channel["key"] == "instagram" for channel in feed["channels"]))
        self.assertIn("instagram", feed["selected_channels"])
        self.assertTrue(feed["checked"])
        thin = next(item for item in kit["plates"] if item["key"] == "iab-mobile")
        self.assertEqual(thin["canvas"]["height"], 50)
        self.assertIn("is-thin", thin["html"])
        bound = normalize_bindings({
            "bindings": {
                "feed-1x1": ["instagram", "portal", "instagram"],
                "missing": ["ctv"],
            }
        })
        self.assertEqual(bound["feed-1x1"], ["instagram"])
        self.assertNotIn("missing", bound)

    def test_recorte_de_produto_nao_derruba_o_lote_se_o_provedor_recusar(self):
        from aicentralv2.creative_format_lab.plates import (
            build_plate_kit,
            build_product_cutouts,
        )

        def refuse(*_args, **_kwargs):
            raise RuntimeError(
                'O provedor recusou a imagem: background: not supported. Accepted: auto, opaque'
            )

        cutouts = build_product_cutouts(
            {"name": "Vivara"}, "Joias", refuse
        )
        self.assertEqual(cutouts, {"horizontal": "", "vertical": ""})
        kit = build_plate_kit(
            {
                "id": 9,
                "name": "Vivara",
                "brand_profile": {"products_services": ["Joias"]},
            },
            image_callable=refuse,
            product="Joias",
            refine=False,
        )
        self.assertGreaterEqual(len(kit["plates"]), 10)
        self.assertTrue(all(item["html"] for item in kit["plates"]))

    def test_lab_nao_pede_fundo_transparente_ao_gpt_image_2(self):
        from aicentralv2.creative_format_lab.close import close_scene
        from aicentralv2.creative_format_lab.plates import build_product_cutouts

        seen = []

        def fake(prompt, **kwargs):
            seen.append(kwargs.get("background"))
            return TINY_PNG

        cutouts = build_product_cutouts({"name": "Vivara"}, "Anel", fake)
        self.assertTrue(cutouts["horizontal"])
        close_scene(
            {
                "id": "scene_04",
                "purpose": "cta",
                "headline": "Encontre a loja",
                "cta": "Encontre a loja",
            },
            brand={"name": "Vivara"},
            image_callable=fake,
        )
        self.assertTrue(seen)
        self.assertTrue(all(item == "opaque" for item in seen))
        root = Path(__file__).resolve().parents[1]
        for path in (root / "aicentralv2" / "creative_format_lab").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('background="transparent"', text, path.name)
            self.assertNotIn("background='transparent'", text, path.name)
        service = (root / "aicentralv2" / "creative_format_lab" / "service.py").read_text(encoding="utf-8")
        wrapper = (root / "aicentralv2" / "creative_modeling_service.py").read_text(encoding="utf-8")
        self.assertIn('background="opaque"', service)
        self.assertNotIn('background="transparent"', wrapper)

    def test_kit_passa_texto_produto_e_tres_refinos_por_familia(self):
        from aicentralv2.creative_format_lab.plates import build_plate_kit, patch_plate_kit

        calls = []

        def fake_text(messages, **kwargs):
            calls.append(messages)
            blob = str(messages)
            if "campanha-piloto" in blob:
                return {
                    "message": {
                        "content": {
                            "offer": "Joia de presente",
                            "headline": "Linha nova da marca",
                            "support": "Qualidade em cada peça",
                            "cta": "Veja agora",
                        }
                    }
                }
            return {
                "message": {
                    "content": {
                        "patches": [{"layer_id": "layer-cta", "text": "Veja agora"}],
                        "css_vars": {"--brand-accent": "#C4A574"},
                    }
                }
            }

        kit = build_plate_kit(
            {
                "id": 9,
                "name": "Vivara",
                "brand_profile": {
                    "brand_summary": "Joia como memória.",
                    "products_services": ["Anel Solitário"],
                },
            },
            text_callable=fake_text,
            image_callable=lambda *args, **kwargs: TINY_PNG,
            product="Anel Solitário",
        )
        self.assertEqual(kit["campaign"]["headline"], "Linha nova da marca")
        self.assertEqual(kit["product"], "Anel Solitário")
        self.assertTrue(kit["product_assets"]["horizontal"].startswith("data:image/png"))
        self.assertTrue(kit["product_assets"]["vertical"].startswith("data:image/png"))
        self.assertEqual({item["family"] for item in kit["passes"]}, {"horizontal", "box", "vertical"})
        self.assertEqual(len(kit["passes"]), 9)
        story = next(item for item in kit["plates"] if item["key"] == "story-9x16")
        self.assertIn("has-product", story["html"])
        self.assertIn("layer-key-visual", story["html"])
        patched = patch_plate_kit(kit, {"headline": "Título único", "apply_to_all": True})
        self.assertTrue(all("Título único" in item["html"] for item in patched["plates"]))

    def test_servico_grava_kit_por_marca(self):
        from tests.test_modelagem_criativos import FakeGenerator, FakeRepository

        repository = FakeRepository()
        service = FormatLabService(CreativeModelingService(repository, FakeGenerator()))
        kit = service.build_plates({"client_id": 10, "refine": False})
        self.assertEqual(kit["client_id"], 10)
        self.assertTrue(kit["id"])
        self.assertIn("IAB base", kit["name"])
        listed = service.list_plates(10)
        self.assertEqual(listed[0]["id"], kit["id"])
        opened = service.get_plates(kit["id"])
        self.assertEqual(opened["id"], kit["id"])
        patched = service.patch_plates({
            "kit_id": kit["id"],
            "headline": "Ajuste da mesa",
            "apply_to_all": True,
        })
        self.assertTrue(all("Ajuste da mesa" in item["html"] for item in patched["plates"]))


class CreativeFormatLabCloseTest(unittest.TestCase):
    def test_margem_segura_empurra_camada_para_dentro(self):
        x, y, w, h = protect_box(-4, 2, 40, 20)
        self.assertGreaterEqual(x, 6)
        self.assertGreaterEqual(y, 6)
        self.assertLessEqual(x + w, 94)

    def test_fecha_still_1920x1080_com_fundo_e_tipo(self):
        from PIL import Image
        import io

        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), (196, 165, 116)).save(buffer, format="PNG")
        closed = close_scene(
            {
                "id": "scene_04",
                "purpose": "cta",
                "headline": "Entregue em loja",
                "support": "Um verbo só",
                "cta": "Encontre a loja",
                "logo_visible": True,
            },
            brand={"name": "Vivara", "primary_color": "#C4A574"},
            assets={"scene_image": buffer.getvalue()},
            generate=False,
        )
        self.assertEqual(closed["width"], 1920)
        self.assertEqual(closed["height"], 1080)
        self.assertTrue(closed["png_data_url"].startswith("data:image/png"))
        self.assertEqual(closed["stack"]["background"]["kind"], "wash")
        self.assertTrue(closed["stack"]["ready_for_motion"])
        self.assertTrue(any(item["role"] == "cta" for item in closed["stack"]["layers"]))
        logo = next(item for item in closed["stack"]["layers"] if item["role"] == "logo")
        self.assertGreaterEqual(logo["y"], 20)
        self.assertLessEqual(logo["y"], 40)
        self.assertGreaterEqual(logo["x"], 28)
        report = check_stack(closed["stack"])
        self.assertTrue(report["passed"], report["defects"])

    def test_stack_da_cena_vem_no_run(self):
        result = run_session(
            {
                "campaign_slug": "vivara-presente-ctv",
                "scene_id": "scene_01",
                "renders": 1,
                "base_html": "<html><body class=\"render\"><main class=\"stage\"></main></body></html>",
            },
            client={"id": 22, "name": "Vivara", "primary_color": "#C4A574"},
            screenshot=lambda html, w, h: TINY_PNG,
        )
        stack = result["scenes"][0]["stack"]
        self.assertEqual(stack["canvas"]["width"], 1920)
        self.assertIn(stack["background"]["kind"], {"wash", "image"})
        self.assertTrue(stack["guidelines"])


class CreativeFormatLabSwapTest(unittest.TestCase):
    def test_prompt_mantem_quadro_e_pede_portugues(self):
        prompt = build_swap_prompt(
            {
                "brand_name": "Vivara",
                "headline": "O presente que marca o momento",
                "cta": "Encontre a loja",
                "note": "Trocar Cyrella por Vivara.",
                "logo_url": "https://cdn.example/vivara-logo.png",
            }
        )
        self.assertIn("Brazilian Portuguese", prompt)
        self.assertIn("Vivara", prompt)
        self.assertIn("Keep the same composition", prompt)
        self.assertIn("Trocar Cyrella por Vivara", prompt)
        self.assertIn("official brand logo", prompt)
        self.assertIn("exactly", prompt)
        self.assertIn("neon", prompt)

    def test_swap_usa_a_referencia_e_devolve_png(self):
        called = {}

        def fake_image(prompt, input_references=None, **_kwargs):
            called["prompt"] = prompt
            called["refs"] = input_references
            called["aspect"] = _kwargs.get("aspect_ratio")
            return {"b64_json": "aGVsbG8="}

        result = swap_reference(
            {
                "reference": "data:image/png;base64,aaa",
                "brand_name": "Rede D'Or",
                "aspect_ratio": "9:16",
            },
            brand={"logo_url": "https://cdn.example/redor-logo.png"},
            image_callable=fake_image,
        )
        self.assertTrue(result["png_data_url"].startswith("data:image/png"))
        self.assertEqual(
            called["refs"],
            ["data:image/png;base64,aaa", "https://cdn.example/redor-logo.png"],
        )
        self.assertEqual(called["aspect"], "9:16")
        self.assertTrue(result["logo_used"])
        self.assertIn("Rede D'Or", called["prompt"])
        self.assertEqual(quote_swap()["model"], "openai/gpt-image-2")
        self.assertEqual(resolve_aspect_ratio({"output": "mobile"}), "9:16")

    def test_swap_sem_logo_mantem_uma_referencia(self):
        refs = swap_input_references(
            {"reference": "data:image/png;base64,aaa"},
            brand={"name": "TIM"},
        )
        self.assertEqual(refs, ["data:image/png;base64,aaa"])

    def test_le_elementos_da_referencia(self):
        def fake_text(_messages, **_kwargs):
            return {
                "message": {
                    "content": {
                        "headline": "500 MEGA",
                        "support": "Internet que cabe no mês",
                        "cta": "Monte o seu",
                        "logo_text": "TIM",
                        "aspect_hint": "16:9",
                        "style": "foto de produto, fundo azul",
                        "elements": [
                            {"role": "logo", "text": "TIM", "note": "canto superior"},
                            {"role": "headline", "text": "500 MEGA"},
                        ],
                    }
                }
            }

        result = read_swap_reference(
            {"reference": "data:image/png;base64,aaa"},
            text_callable=fake_text,
        )
        self.assertEqual(result["headline"], "500 MEGA")
        self.assertEqual(result["cta"], "Monte o seu")
        self.assertEqual(result["elements"][0]["role"], "logo")
        self.assertEqual(result["aspect_hint"], "16:9")

    def test_swap_sem_referencia_falha(self):
        with self.assertRaises(ValueError):
            swap_reference({"brand_name": "Vivara"}, image_callable=lambda *_a, **_k: b"x")
        with self.assertRaises(ValueError):
            read_swap_reference({}, text_callable=lambda *_a, **_k: {})


class CreativeFormatLabRoutesTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SECRET_KEY="format-lab-test")
        bp = Blueprint("parametros_format_lab", __name__, url_prefix="/parametros")
        register_creative_modeling_routes(bp)
        app.register_blueprint(bp)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["user_type"] = "admin"

    def test_catalogo_e_handoff_bloqueado(self):
        service = Mock()
        service.format_lab_formats.return_value = {
            "family": "ctv",
            "formats": [{"key": "ctv-video-linear-30"}],
        }
        service.handoff_format_lab_session.side_effect = CreativeConflictError(
            "QA ainda não passou."
        )
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            catalog = self.client.get("/parametros/api/format-lab/formats")
            blocked = self.client.post("/parametros/api/format-lab/sessions/flab-x/handoff")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.get_json()["data"]["family"], "ctv")
        self.assertEqual(blocked.status_code, 409)
        self.assertFalse(blocked.get_json()["success"])
        service.list_format_lab_sessions.return_value = {
            "sessions": [{"id": "flab-x", "stage": "concept"}],
            "active": {"id": "flab-x", "storyboard": [{"id": "scene_01"}]},
            "history": [{"session_id": "flab-x", "stage": "concept"}],
        }
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            listed = self.client.get(
                "/parametros/api/format-lab/sessions?client_id=10&format=video-linear-15"
            )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["data"]["history"][0]["stage"], "concept")

    def test_ler_referencia_do_trocar(self):
        service = Mock()
        service.read_format_lab_swap.return_value = {
            "headline": "500 MEGA",
            "cta": "Monte o seu",
            "elements": [{"role": "logo", "text": "TIM"}],
        }
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/format-lab/swap/read",
                json={"reference": "data:image/png;base64,aaa"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["headline"], "500 MEGA")
        service.read_format_lab_swap.assert_called_once()
