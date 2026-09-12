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
    build_optimized_prompt,
    build_swap_prompt,
    preview_swap_prompt,
    quote_swap,
    read_swap_reference,
    resolve_aspect_ratio,
    swap_input_references,
    swap_reference,
)
from aicentralv2.creative_format_lab.guidelines import check_stack, protect_box
from aicentralv2.creative_format_lab.visual_qa import run_qa_loop
from aicentralv2.creative_modeling_repository import CreativeConflictError
from aicentralv2.creative_modeling_routes import (
    register_creative_modeling_routes,
    register_modeling_ux_lab,
)
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
        self.assertIn("feed-4x5", banner)
        self.assertIn("linkedin-landscape", banner)
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
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], "opaque")
        self.assertEqual(parts["cast_url"], "")
        self.assertTrue(parts["ground_url"].startswith("data:image/png;base64,"))

    def test_split_still_recorte_pessoa_e_fundo(self):
        import base64
        import io

        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.split_layers import split_still

        canvas = Image.new("RGB", (20, 10), (0, 51, 255))
        pixels = canvas.load()
        for y in range(10):
            for x in range(10, 20):
                pixels[x, y] = (200, 40, 40)
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")

        def predict(image):
            width, height = image.size
            mask = Image.new("L", (width, height), 0)
            ImageDraw.Draw(mask).rectangle([width // 2, 0, width, height], fill=255)
            return [{"label": "person", "mask": mask}]

        result = split_still(buffer.getvalue(), predictor=predict)
        roles = [item["role"] for item in result["layers"]]
        self.assertIn("cast", roles)
        self.assertIn("ground", roles)
        self.assertTrue(result["field"].startswith("#"))
        cast = next(item for item in result["layers"] if item["role"] == "cast")
        self.assertTrue(cast["png_data_url"].startswith("data:image/png;base64,"))
        cut = Image.open(io.BytesIO(base64.b64decode(cast["png_data_url"].split(",", 1)[1])))
        self.assertEqual(cut.mode, "RGBA")
        self.assertGreater(cut.size[0], 0)
        with self.assertRaises(ValueError):
            split_still("", predictor=predict)

    def test_split_hipotetico_so_python(self):
        from aicentralv2.creative_format_lab.split_layers import (
            example_still_payload,
            hypothetical_still,
            split_still,
        )

        result = split_still(hypothetical_still())
        roles = [item["role"] for item in result["layers"]]
        self.assertEqual(result["engine"], "python")
        self.assertIn("cast", roles)
        self.assertIn("ground", roles)
        self.assertEqual(roles.count("product"), 0)
        self.assertTrue(result["field"].startswith("#"))
        example = example_still_payload()
        self.assertTrue(example["image"].startswith("data:image/png;base64,"))
        self.assertEqual(example["engine"], "python")
        self.assertEqual(result["ground_kind"], "paper")

    def test_split_tim_like_sem_segmentador_vira_wash(self):
        from aicentralv2.creative_format_lab.split_layers import (
            field_predictor,
            split_still,
            tim_like_still,
        )

        result = split_still(tim_like_still(), predictor=field_predictor)
        self.assertFalse(result["cast_ok"])
        self.assertEqual(result["ground_kind"], "paper")
        self.assertTrue(result["field"].upper().startswith("#01"))
        self.assertNotIn("cast", [item["role"] for item in result["layers"]])
        self.assertIn("ground", [item["role"] for item in result["layers"]])

    def test_split_tim_like_com_predictor_mantem_wash(self):
        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.split_layers import split_still, tim_like_still

        still = tim_like_still()

        def predict(image):
            mask = Image.new("L", image.size, 0)
            ImageDraw.Draw(mask).ellipse([430, 20, 512, 220], fill=255)
            return [{"label": "person", "mask": mask}]

        result = split_still(still, predictor=predict)
        self.assertTrue(result["cast_ok"])
        self.assertEqual(result["ground_kind"], "paper")
        self.assertIn("cast", [item["role"] for item in result["layers"]])

    def test_split_sempre_devolve_ocr_no_html(self):
        from aicentralv2.creative_format_lab.service import FormatLabService
        from aicentralv2.creative_format_lab.split_layers import example_still_payload

        class Modeling:
            repository = None
            generator = None

        def text_callable(_messages, **_kwargs):
            return {
                "message": {
                    "content": {
                        "headline": "Acesse vantagens exclusivas",
                        "price": "R$ 169,99",
                        "cta": "Contratar",
                    }
                }
            }

        result = FormatLabService(Modeling()).split_layers({
            "image": example_still_payload()["image"],
            "text_callable": text_callable,
        })
        self.assertEqual(result["read"]["price"], "R$ 169,99")
        self.assertEqual(result["read"]["cta"], "Contratar")

    def test_split_still_nao_engole_tipo_nem_letra_3d(self):
        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.split_layers import split_still

        canvas = Image.new("RGB", (640, 240), (255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle([8, 8, 632, 232], radius=20, fill=(1, 21, 74))
        draw.rectangle([28, 36, 210, 72], fill=(255, 255, 255))
        draw.rectangle([28, 100, 140, 168], fill=(255, 255, 255))
        draw.ellipse([430, 22, 498, 90], fill=(196, 122, 90))
        draw.rectangle([442, 86, 488, 148], fill=(1, 21, 74))
        draw.rectangle([428, 146, 508, 220], fill=(180, 20, 40))
        result = split_still(canvas)
        cast = next(item for item in result["layers"] if item["role"] == "cast")
        self.assertGreater(cast["box"]["x"], 48)
        self.assertLess(cast["box"]["w"], 48)
        self.assertGreater(cast["box"]["h"], 45)

    def test_split_still_parte_da_pele_nao_do_sofa(self):
        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.split_layers import split_still

        canvas = Image.new("RGB", (640, 240), (2, 20, 90))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([24, 150, 220, 220], fill=(28, 38, 72))
        draw.ellipse([430, 16, 524, 112], fill=(196, 122, 90))
        draw.rectangle([448, 104, 508, 172], fill=(2, 20, 90))
        draw.ellipse([438, 168, 472, 204], fill=(196, 122, 90))
        draw.ellipse([488, 168, 522, 204], fill=(196, 122, 90))
        result = split_still(canvas)
        cast = next(item for item in result["layers"] if item["role"] == "cast")
        self.assertGreater(cast["box"]["x"], 50)
        self.assertLess(cast["box"]["y"], 25)
        self.assertGreater(cast["box"]["h"], 55)
        self.assertLess(cast["box"]["w"], 45)

    def test_ocr_do_still_trava_oferta_e_cta(self):
        from aicentralv2.creative_format_lab.engineer import apply_still_read, normalize_knobs

        knobs = normalize_knobs({})

        def fake(_messages, **_kwargs):
            return {
                "message": {
                    "content": {
                        "headline": "Perfeito para o seu bolso e para o seu dia a dia",
                        "price": "30GB · 12x R$30",
                        "cta": "Conferir planos",
                        "logo_text": "TIM Controle Fit",
                    }
                }
            }

        updated = apply_still_read(knobs, ["data:image/png;base64," + ("a" * 40)], fake)
        self.assertEqual(updated["cta_lock"], "Conferir planos")
        self.assertIn("30GB", updated["offer"])
        self.assertIn("TIM Controle Fit", updated["offer"])
        self.assertEqual(updated["still_read"]["cta"], "Conferir planos")
        self.assertFalse(apply_still_read(knobs, ["data:image/png;base64," + ("a" * 40)], None).get("still_read"))

    def test_split_engine_image2_empacota_decompose(self):
        from aicentralv2.creative_format_lab.service import FormatLabService
        from aicentralv2.creative_format_lab.split_layers import (
            _png_data_url,
            example_still_payload,
            lifestyle_still,
        )
        from aicentralv2.creative_modeling_repository import CreativeConflictError

        calls = []

        def fake(prompt, **kwargs):
            calls.append(kwargs.get("aspect_ratio"))
            return b"png"

        class Generator:
            def generate_image(self, prompt, **kwargs):
                return {"b64_json": "cG5n"}

        class Modeling:
            generator = Generator()
            repository = None

        service = FormatLabService(Modeling())
        with self.assertRaises(CreativeConflictError):
            service.split_layers({
                "image": example_still_payload()["image"],
                "engine": "image",
                "image_callable": fake,
            })
        still = _png_data_url(lifestyle_still())
        result = service.split_layers({"image": still, "engine": "image", "image_callable": fake})
        self.assertEqual(result["engine"], "image2")
        self.assertEqual(result["ground_kind"], "image")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], "16:9")
        self.assertEqual([item["role"] for item in result["layers"]], ["ground"])
        self.assertEqual(result["replace"], "ground")
        self.assertEqual(result["cast_status"], "not_run")
        self.assertNotIn("read", result)

    def test_split_cutout_usa_bbox_e_box_percentual(self):
        import base64
        import io

        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.split_layers import split_still

        canvas = Image.new("RGB", (20, 10), (0, 51, 255))
        pixels = canvas.load()
        for y in range(10):
            for x in range(10, 20):
                pixels[x, y] = (196, 122, 90)

        def predict(image):
            mask = Image.new("L", image.size, 0)
            ImageDraw.Draw(mask).rectangle([10, 0, 19, 9], fill=255)
            return [{"label": "person", "mask": mask}]

        result = split_still(canvas, predictor=predict)
        cast = next(item for item in result["layers"] if item["role"] == "cast")
        ground = next(item for item in result["layers"] if item["role"] == "ground")
        cut = Image.open(io.BytesIO(base64.b64decode(cast["png_data_url"].split(",", 1)[1])))
        well = Image.open(io.BytesIO(base64.b64decode(ground["png_data_url"].split(",", 1)[1])))
        self.assertEqual(cut.size, (10, 10))
        self.assertEqual(well.size, (20, 10))
        self.assertEqual(cast["box"]["x"], 50.0)
        self.assertEqual(cast["box"]["w"], 50.0)
        self.assertEqual(cast["box"]["h"], 100.0)
        self.assertEqual(result["width"], 20)
        self.assertEqual(result["height"], 10)

    def test_split_leftover_foto_mantem_pixels_fora_da_mascara(self):
        import base64
        import io

        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.split_layers import lifestyle_still, split_still

        still = lifestyle_still().convert("RGB")
        ImageDraw.Draw(still).rectangle([8, 8, 70, 36], fill=(255, 255, 255))

        def predict(image):
            mask = Image.new("L", image.size, 0)
            ImageDraw.Draw(mask).ellipse([200, 24, 292, 164], fill=255)
            return [{"label": "person", "mask": mask}]

        result = split_still(still, predictor=predict)
        self.assertTrue(result["cast_ok"])
        self.assertEqual(result["ground_kind"], "image")
        ground = next(item for item in result["layers"] if item["role"] == "ground")
        well = Image.open(io.BytesIO(base64.b64decode(ground["png_data_url"].split(",", 1)[1])))
        self.assertEqual(well.size, still.size)
        self.assertGreater(sum(well.getpixel((20, 16))[:3]) / 3, 240)

    def test_example_still_dimensoes_nao_sao_16_9(self):
        from aicentralv2.creative_format_lab.split_layers import (
            example_still_payload,
            hypothetical_still,
        )

        still = hypothetical_still()
        payload = example_still_payload()
        self.assertEqual(still.size, (480, 180))
        self.assertEqual(payload["width"], 480)
        self.assertEqual(payload["height"], 180)
        self.assertNotAlmostEqual(payload["width"] / payload["height"], 16 / 9, places=2)
        self.assertEqual(payload["ground_kind"], "paper")

    def test_read_attached_still_projeta_chips_e_descarta_dates(self):
        from aicentralv2.creative_format_lab.engineer import read_attached_still
        from aicentralv2.creative_format_lab.split_layers import example_still_payload

        def text_callable(_messages, **_kwargs):
            return {
                "message": {
                    "content": {
                        "headline": "Arraial de Belô",
                        "support": "É de graça!",
                        "dates": "24, 25 e 26 julho",
                        "venue": "Mineirinho",
                        "logo_text": "Belotur",
                        "price": "",
                        "cta": "",
                    }
                }
            }

        read = read_attached_still(example_still_payload()["image"], text_callable)
        self.assertEqual(read["headline"], "Arraial de Belô")
        self.assertEqual(read["support"], "É de graça!")
        self.assertEqual(read["logo_text"], "Belotur")
        self.assertNotIn("dates", read)
        self.assertNotIn("venue", read)
        self.assertNotIn("status", read)

    def test_split_mascara_rejeitada_nao_tenta_segundo_predictor(self):
        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.split_layers import split_still, tim_like_still

        calls = []

        def predict(image):
            calls.append(image.size)
            mask = Image.new("L", image.size, 255)
            ImageDraw.Draw(mask).rectangle([0, 0, image.size[0], image.size[1]], fill=255)
            return [{"label": "person", "mask": mask}]

        result = split_still(tim_like_still(), predictor=predict)
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["cast_ok"])
        self.assertNotIn("cast", [item["role"] for item in result["layers"]])

    def test_resolve_predictor_escolhe_o_primeiro_disponivel(self):
        from aicentralv2.creative_format_lab import split_layers as sl

        dummy = lambda image: []
        with patch.object(sl, "_load_rembg", return_value=dummy):
            predict, engine = sl.resolve_predictor()
            self.assertEqual(engine, "rembg")
            self.assertIs(predict, dummy)
        with patch.object(sl, "_load_rembg", side_effect=RuntimeError("ausente")):
            with patch.object(sl, "_load_yolo_person", return_value=dummy):
                predict, engine = sl.resolve_predictor()
                self.assertEqual(engine, "yolo")
        with patch.object(sl, "_load_rembg", side_effect=RuntimeError("ausente")):
            with patch.object(sl, "_load_yolo_person", side_effect=RuntimeError("ausente")):
                predict, engine = sl.resolve_predictor()
                self.assertEqual(engine, "python")
                self.assertIs(predict, sl.field_predictor)

    def test_open_image_recusa_url_http(self):
        from aicentralv2.creative_format_lab.split_layers import split_still

        with self.assertRaises(ValueError):
            split_still("https://cdn.example/still.png", predictor=lambda image: [])

    def test_generate_image_wrapper_nao_declara_mask(self):
        import inspect

        from aicentralv2.services.openrouter_service import build_image_payload, generate_image

        self.assertNotIn("mask", inspect.signature(generate_image).parameters)
        self.assertNotIn("mask", inspect.signature(build_image_payload).parameters)

    def test_camadas_lab_capabilities_sem_baixar_peso(self):
        from aicentralv2.creative_format_lab.camadas_lab import list_capabilities

        caps = {item["engine_id"]: item for item in list_capabilities()}
        self.assertIsInstance(caps["rembg_u2net_human"]["available"], bool)
        self.assertTrue(caps["field_predictor"]["available"])
        self.assertEqual(caps["image2_well"]["limitation"], "no_mask")

    def test_camadas_lab_compara_candidato_fake_e_remove(self):
        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.camadas_lab import compare_segmenters
        from aicentralv2.creative_format_lab.split_layers import hypothetical_still

        still = hypothetical_still()

        def fake(image):
            mask = Image.new("L", image.size, 0)
            ImageDraw.Draw(mask).ellipse([320, 20, 460, 170], fill=255)
            return [{"label": "person", "mask": mask}]

        def boom(_image):
            raise RuntimeError("candidato caiu")

        report = compare_segmenters(still, fake)
        self.assertIn(report["baseline"]["cast_status"], {"succeeded", "rejected", "not_found"})
        self.assertEqual(report["candidate"]["cast_status"], "succeeded")
        self.assertIsNone(report["candidate"]["cast_confidence"])
        failed = compare_segmenters(still, boom)
        self.assertEqual(failed["candidate"]["status"], "failed")
        missing = compare_segmenters(still, "nao-e-callable")
        self.assertEqual(missing["candidate"]["status"], "unavailable")
        empty = compare_segmenters(still)
        self.assertIsNone(empty["candidate"])

    def test_camadas_lab_geometria_incompativel(self):
        from aicentralv2.creative_format_lab.camadas_lab import geometry_compatible

        self.assertTrue(geometry_compatible({"width": 20, "height": 10, "layers": []}, 20, 10))
        self.assertFalse(geometry_compatible({"width": 40, "height": 10, "layers": []}, 20, 10))
        self.assertFalse(geometry_compatible({
            "width": 20,
            "height": 10,
            "layers": [{"box": {"x": 80, "y": 0, "w": 40, "h": 10}}],
        }, 20, 10))

    def test_split_status_rejeitado_nao_e_so_cast_ok(self):
        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.split_layers import split_still, tim_like_still

        def predict(image):
            mask = Image.new("L", image.size, 255)
            ImageDraw.Draw(mask).rectangle([0, 0, image.size[0], image.size[1]], fill=255)
            return [{"label": "person", "mask": mask}]

        result = split_still(tim_like_still(), predictor=predict)
        self.assertFalse(result["cast_ok"])
        self.assertEqual(result["cast_status"], "rejected")
        self.assertEqual(result["cast_reason"], "full-frame")
        self.assertIsNone(result["cast_confidence"])

    def test_split_devolve_read_full_e_chips(self):
        from aicentralv2.creative_format_lab.service import FormatLabService
        from aicentralv2.creative_format_lab.split_layers import example_still_payload

        class Modeling:
            repository = None
            generator = None

        def text_callable(_messages, **_kwargs):
            return {
                "message": {
                    "content": {
                        "headline": "Arraial de Belô",
                        "support": "É de graça!",
                        "dates": "24, 25 e 26 julho",
                        "venue": "Mineirinho",
                        "logo_text": "Belotur",
                    }
                }
            }

        result = FormatLabService(Modeling()).split_layers({
            "image": example_still_payload()["image"],
            "text_callable": text_callable,
            "operation_id": "7",
        })
        self.assertEqual(result["read"]["headline"], "Arraial de Belô")
        self.assertNotIn("dates", result["read"])
        self.assertEqual(result["read_full"]["dates"], "24, 25 e 26 julho")
        self.assertEqual(result["read_full"]["venue"], "Mineirinho")
        self.assertEqual(result["ocr_status"], "succeeded")
        self.assertEqual(result["operation_id"], "7")
        self.assertEqual(result["replace"], "pack")

    def test_rota_split_descarta_injections_do_cliente(self):
        service = Mock()
        service.split_format_lab_layers.return_value = {"layers": [], "field": "#000"}
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            app = Flask(__name__)
            register_creative_modeling_routes(app)
            client = app.test_client()
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["is_admin"] = True
            response = client.post(
                "/parametros/api/format-lab/layers/split",
                json={
                    "image": "data:image/png;base64,aaa",
                    "predictor": "malicioso",
                    "text_callable": "malicioso",
                    "image_callable": "malicioso",
                    "operation_id": "9",
                },
            )
        self.assertEqual(response.status_code, 200)
        sent = service.split_format_lab_layers.call_args[0][0]
        self.assertNotIn("predictor", sent)
        self.assertNotIn("text_callable", sent)
        self.assertNotIn("image_callable", sent)
        self.assertEqual(sent["operation_id"], "9")

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

    def test_tim_recarga_sem_slug_nao_trava_controle(self):
        from aicentralv2.creative_format_lab.campaign_models import (
            campaign_fits_hint,
            campaign_from_brand,
            match_campaign_for_brand,
        )
        from aicentralv2.creative_format_lab.engineer import payload_locks

        offer = "Recarregue R$30 e tenha internet por até 30 dias"
        controle = load_campaign_model("tim-controle-ctv")
        self.assertFalse(campaign_fits_hint(controle, offer))
        self.assertIsNone(match_campaign_for_brand("TIM", hint=offer))
        generated = campaign_from_brand(
            {"name": "TIM", "campaign_opportunities": ["Controle que cabe no mês"]},
            hint=offer,
            has_reference=True,
        )
        self.assertTrue(generated.get("generated_from_marcas"))
        self.assertFalse(generated.get("lock_copy"))
        self.assertNotIn(
            "O mês acabou. A internet, não.",
            [scene["headline"] for scene in generated["scenes"]],
        )
        self.assertEqual(payload_locks(generated, {}), [])
        board = build_storyboard(
            {"offer": offer, "scene_count": 4, "images": ["https://cdn.example/tim-pre.png"]},
            client={"id": 11, "name": "Tim"},
        )
        headlines = [card["headline"] for card in board["storyboard"]]
        self.assertNotIn("O mês acabou. A internet, não.", headlines)

    def test_tim_slug_explicito_trava_controle_mesmo_com_recarga(self):
        board = build_storyboard(
            {
                "campaign_slug": "tim-controle-ctv",
                "scene_count": 4,
                "offer": "Recarregue R$30 e tenha internet por até 30 dias",
            },
            client={"id": 11, "name": "Tim"},
        )
        headlines = [card["headline"] for card in board["storyboard"]]
        self.assertIn("O mês acabou. A internet, não.", headlines)

    def test_create_nao_embute_bytes_de_imagem_no_json(self):
        import json

        from aicentralv2.creative_format_lab.engineer import _user_payload, normalize_knobs

        png = "data:image/png;base64," + ("A" * 200)
        knobs = normalize_knobs({"offer": "Recarregue R$30", "key_visuals": {"scene_01": png}})
        blob = _user_payload(
            {"format": "video-linear-15", "adapter": "generic_ctv", "platform_label": "CTV"},
            "create",
            "A",
            "Recarregue R$30",
            "TIM",
            {},
            {"name": "TIM", "logo_url": png, "assets": {"references": [png]}},
            {
                "lock_copy": False,
                "scenes": [{"id": "scene_01", "headline": "X", "key_visual": png}],
            },
            knobs,
        )
        self.assertNotIn("data:image/png;base64", blob)
        self.assertIn("data:image/attached", blob)
        self.assertFalse(json.loads(blob)["campaign"]["lock_copy"])

    def test_qa_has_render_so_conta_still_da_placa(self):
        from aicentralv2.creative_format_lab.visual_qa import _qa_images

        kv = "https://cdn.example/tim-pre.png"
        self.assertEqual(_qa_images("", {"key_visual": kv}, [kv]), [])
        self.assertEqual(_qa_images(kv, {"key_visual": kv}, [])[0], kv)

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

    def test_engenheiro_nao_manda_orchestrator_no_system(self):
        from aicentralv2.creative_skills.loader import combined_system_prompt, load_bundle

        bundle = load_bundle("create", "video-linear-15")
        system = combined_system_prompt(bundle, ["create"])
        self.assertIn("CreativeFormatSpec", system)
        self.assertNotIn("Your job is NOT to directly design", system)
        self.assertNotIn("loading every skill", system)

    def test_spec_aceita_cenas_sem_id_na_ordem(self):
        spec = parse_format_spec(
            {
                "format": "video-linear-15",
                "scenes": [
                    {"title": "A", "beat": "hook"},
                    {"headline": "B", "role": "product"},
                    {"headline": "C"},
                    {"headline": "D", "purpose": "cta"},
                ],
            },
            expected_format="video-linear-15",
        )
        self.assertEqual([item.id for item in spec.scenes], ["scene_01", "scene_02", "scene_03", "scene_04"])
        self.assertEqual(spec.scenes[0].headline, "A")
        self.assertEqual(spec.scenes[0].purpose, "hook")

    def test_spec_aceita_cenas_como_objeto(self):
        spec = parse_format_spec(
            {
                "format": "video-linear-15",
                "scenes": {
                    "scene_01": {"headline": "A", "purpose": "brand"},
                    "scene_02": {"headline": "B", "purpose": "product"},
                    "scene_03": {"headline": "C", "purpose": "lifestyle"},
                    "scene_04": {"headline": "D", "purpose": "cta"},
                },
            },
            expected_format="video-linear-15",
        )
        self.assertEqual([item.id for item in spec.scenes], ["scene_01", "scene_02", "scene_03", "scene_04"])
        self.assertEqual(spec.scenes[0].headline, "A")

    def test_refine_manda_delta_e_nao_a_campanha_inteira(self):
        import json

        payloads = []

        def fake(messages, **_kwargs):
            content = messages[-1]["content"]
            text = content if isinstance(content, str) else next(
                block.get("text") for block in content if isinstance(block, dict) and block.get("type") == "text"
            )
            payloads.append(json.loads(text))
            return {
                "message": {
                    "content": {
                        "intent": "create",
                        "format": "video-linear-15",
                        "variant": "C",
                        "adapter": "generic_ctv",
                        "platform_label": "CTV",
                        "brand_name": "Vivara",
                        "scenes": [
                            {"id": "scene_01", "headline": "Alguns momentos pedem marca.", "purpose": "brand"},
                            {"id": "scene_02", "headline": "A peça que fica.", "purpose": "product"},
                            {"id": "scene_03", "headline": "Quem ganha, lembra.", "purpose": "lifestyle"},
                            {"id": "scene_04", "headline": "Encontre a peça.", "purpose": "cta", "cta": "Encontre a peça"},
                        ],
                    }
                }
            }

        board = build_storyboard(
            {"campaign_slug": "vivara-presente-ctv", "scene_count": 4},
            client={"id": 22, "name": "Vivara"},
            text_callable=fake,
        )
        self.assertEqual(len(payloads), 2)
        create, refine = payloads
        self.assertEqual(create["intent"], "create")
        self.assertIn("scenes", create["campaign"])
        self.assertNotIn("scenes", refine["campaign"])
        self.assertEqual(refine["campaign"]["slug"], "vivara-presente-ctv")
        self.assertEqual(len(refine["draft"]["scenes"]), 4)
        self.assertTrue(refine["locked"])
        self.assertEqual(refine["locked"][0]["headline"], "Alguns momentos pedem marca.")
        self.assertIn("Do not replace locked headline", " ".join(refine["rules"]))
        self.assertTrue(refine["improve"])
        self.assertEqual(board["storyboard"][0]["headline"], "Alguns momentos pedem marca.")

    def test_mockup_manda_estado_da_placa(self):
        import json

        payloads = []
        images = []

        def fake(messages, **_kwargs):
            content = messages[-1]["content"]
            text = next(block.get("text") for block in content if block.get("type") == "text")
            payloads.append(json.loads(text))
            images.append([
                (block.get("image_url") or {}).get("url")
                for block in content
                if block.get("type") == "image_url"
            ])
            return {"message": {"content": {"passed": True, "score": 0.8, "patches": [], "css_vars": {}}}}

        run_session(
            {
                "campaign_slug": "vivara-presente-ctv",
                "stage": "mockup",
                "mockup_passes": 2,
                "images": ["https://cdn.example/vivara-caixa.jpg"],
            },
            client={"id": 22, "name": "Vivara"},
            text_callable=fake,
            screenshot=_shot,
        )
        self.assertEqual(len(payloads), 2)
        self.assertTrue(payloads[0]["layers"])
        self.assertIn("layer-headline", {item["id"] for item in payloads[0]["layers"]})
        self.assertFalse(payloads[0]["has_previous_still"])
        self.assertFalse(payloads[1]["has_previous_still"])
        self.assertFalse(any(url and str(url).startswith("data:image/") for url in images[1]))
        self.assertNotIn("<html", json.dumps(payloads[0]))

    def test_qa_manda_headline_camadas_e_marca(self):
        import json

        seen = {}

        def fake(messages, **_kwargs):
            content = messages[-1]["content"]
            text = next(block.get("text") for block in content if block.get("type") == "text")
            seen["payload"] = json.loads(text)
            return {
                "message": {
                    "content": {"passed": True, "score": 0.9, "defects": [], "patches": []}
                }
            }

        spec = build_spec(
            route={
                "format": "video-linear-15",
                "adapter": "generic_ctv",
                "platform_label": "CTV",
            },
            brand_name="Vivara",
            campaign=load_campaign_model("vivara-presente-ctv"),
        )
        scenes = [
            {
                "id": spec.scenes[0].id,
                "html": build_scene_html(spec, spec.scenes[0]),
                "headline": spec.scenes[0].headline,
                "support": spec.scenes[0].support,
                "purpose": spec.scenes[0].purpose,
                "logo_visible": True,
            }
        ]
        run_qa_loop(
            spec=spec,
            scenes=scenes,
            renders=1,
            text_callable=fake,
            screenshot=_shot,
            brand={"name": "Vivara", "palette": ["#C4A574"], "forbidden_elements": ["preço"]},
        )
        payload = seen["payload"]
        self.assertEqual(payload["scene"]["headline"], "Alguns momentos pedem marca.")
        self.assertEqual(payload["brand"]["name"], "Vivara")
        self.assertEqual(payload["locked"]["headline"], "Alguns momentos pedem marca.")
        self.assertFalse(payload["has_render"])
        self.assertIn("layer-headline", payload["layer_ids"])
        self.assertTrue(payload["layers"])

    def test_qa_nao_aplica_cta_generico(self):
        from aicentralv2.creative_format_lab.visual_qa import lock_copy_patches

        kept = lock_copy_patches(
            [
                {"layer_id": "layer-headline", "text": "Alguns momentos pedem marca."},
                {"layer_id": "layer-cta", "text": "Explore Now"},
                {"layer_id": "layer-cta", "text": "Encontre a peça"},
            ],
            {"headline": "Alguns momentos pedem marca.", "cta": "Encontre a peça"},
        )
        texts = [item.get("text") for item in kept]
        self.assertIn("Alguns momentos pedem marca.", texts)
        self.assertIn("Encontre a peça", texts)
        self.assertNotIn("Explore Now", texts)

    def test_qa_sem_still_ignora_typo_inventado(self):
        from aicentralv2.creative_format_lab.visual_qa import png_data_url, review_render

        spec = build_spec(
            route={
                "format": "video-linear-15",
                "adapter": "generic_ctv",
                "platform_label": "CTV",
            },
            brand_name="Vivara",
            campaign=load_campaign_model("vivara-presente-ctv"),
        )
        scene = spec.scenes[0]

        def fake(*_args, **_kwargs):
            return {
                "message": {
                    "content": {
                        "passed": False,
                        "score": 0.8,
                        "defects": [
                            "The headline text has a typo: 'momentospedem'.",
                            "The CTA layer contains placeholder text 'CTA'.",
                        ],
                        "patches": [{"layer_id": "layer-cta", "text": "Explore Now"}],
                    }
                }
            }

        report = review_render(
            spec=spec,
            scene_html=build_scene_html(spec, scene),
            render_url=png_data_url(TINY_PNG),
            attempt=1,
            scene={
                "id": scene.id,
                "purpose": scene.purpose,
                "headline": scene.headline,
                "support": scene.support,
                "cta": scene.cta,
            },
            brand={"name": "Vivara"},
            text_callable=fake,
        )
        self.assertTrue(report.passed)
        self.assertEqual(report.defects, [])
        self.assertFalse(any((item.text or "") == "Explore Now" for item in report.patches))

    def test_stack_brand_mantem_logo_mesmo_sem_flag(self):
        stack = build_stack(
            {
                "id": "scene_01",
                "purpose": "brand",
                "headline": "Alguns momentos pedem marca.",
                "logo_visible": False,
            },
            brand={"name": "Vivara", "primary_color": "#C4A574"},
        )
        self.assertTrue(any(item["role"] == "logo" for item in stack["layers"]))
        self.assertTrue(check_stack(stack)["passed"], check_stack(stack)["defects"])

    def test_fechar_usa_image_prompt_da_campanha(self):
        seen = []

        def fake(prompt, **kwargs):
            seen.append(prompt)
            return TINY_PNG

        close_scene(
            {
                "id": "scene_02",
                "purpose": "product",
                "headline": "A peça que fica.",
                "image_prompt": "Macro 16:9 of a yellow-gold ring on dark linen.",
            },
            brand={"name": "Vivara"},
            image_callable=fake,
        )
        self.assertTrue(seen)
        self.assertIn("yellow-gold ring", seen[0])
        self.assertIn("opaque background", seen[0])
        self.assertNotIn("transparent background", seen[0])

    def test_offer_da_campanha_vence_o_titulo_da_mesa(self):
        from aicentralv2.creative_format_lab.engineer import normalize_knobs

        knobs = normalize_knobs(
            {"offer": "O presente que marca o momento", "scene_count": 4},
            load_campaign_model("vivara-presente-ctv"),
        )
        self.assertIn("joia", knobs["offer"].lower())
        self.assertNotEqual(knobs["offer"], "O presente que marca o momento")

    def test_qa_segunda_pass_leva_defeitos_anteriores(self):
        import json

        payloads = []

        def fake(messages, **_kwargs):
            content = messages[-1]["content"]
            text = next(block.get("text") for block in content if block.get("type") == "text")
            payloads.append(json.loads(text))
            return _qa_fail()

        spec = build_spec(
            route={
                "format": "video-linear-15",
                "adapter": "generic_ctv",
                "platform_label": "CTV",
            },
            brand_name="Vivara",
            campaign=load_campaign_model("vivara-presente-ctv"),
        )
        run_qa_loop(
            spec=spec,
            scenes=[{
                "id": spec.scenes[0].id,
                "html": build_scene_html(spec, spec.scenes[0]),
                "headline": spec.scenes[0].headline,
                "key_visual": "https://cdn.example/vivara-caixa.jpg",
            }],
            renders=2,
            reference_urls=["https://cdn.example/vivara-anel.jpg"],
            text_callable=fake,
            screenshot=_shot,
            brand={"name": "Vivara"},
        )
        self.assertEqual(payloads[0].get("prior"), {})
        self.assertIn("CTA fora do lugar", payloads[1]["prior"]["defects"])

    def test_ledger_cobra_o_modelo_que_a_mesa_chama(self):
        from aicentralv2.creative_format_lab.lab_models import lab_chat_model

        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)
        session = lab.create_session({"client_id": 10, "campaign_id": 30})
        lab.storyboard(session["id"], {"campaign_slug": "vivara-presente-ctv", "scene_count": 4})
        self.assertEqual(repository.jobs[-1]["args"][5], lab_chat_model("storyboard"))
        self.assertEqual(
            repository.concept_passes[session["id"]][-1]["model"],
            lab_chat_model("storyboard"),
        )
        lab.mockup(session["id"], {
            "campaign_slug": "vivara-presente-ctv",
            "text_callable": None,
            "screenshot": _shot,
        })
        self.assertEqual(repository.jobs[-1]["args"][5], lab_chat_model("mockup"))

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

    def test_criar_sessao_abre_existente_antes_de_criar_campanha(self):
        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)
        first = lab.create_session({
            "client_id": 10,
            "campaign_id": 30,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
        })

        def should_not_create(*_args, **_kwargs):
            raise AssertionError("não deveria criar campanha ao retomar")

        repository.create_campaign_with_variation_a = should_not_create
        again = lab.create_session({
            "client_id": 10,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
        })
        self.assertEqual(again["id"], first["id"])

    def test_criar_sessao_usa_campanha_leve_quando_o_passo_quebra(self):
        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)
        repository.find_latest_campaign_for_client = lambda *_args, **_kwargs: None

        def boom(*_args, **_kwargs):
            raise RuntimeError("engine check")

        repository.create_campaign_with_variation_a = boom
        repository.create_mesa_campaign = lambda *_args, **_kwargs: {"id": 88}
        session = lab.create_session({
            "client_id": 10,
            "format": "video-linear-15",
        })
        self.assertEqual(session["campaign_id"], 88)
        self.assertEqual(session["client_id"], 10)
        self.assertTrue(session["id"])

    def test_criar_sessao_nao_quebra_se_a_campanha_nao_carrega(self):
        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)

        def boom(*_args, **_kwargs):
            raise RuntimeError("column does not exist")

        repository.get_campaign = boom
        session = lab.create_session({
            "client_id": 10,
            "campaign_id": 30,
            "format": "video-linear-15",
        })
        self.assertTrue(session["id"])
        self.assertEqual(session["campaign_id"], 30)
        self.assertEqual(session["client_id"], 10)

    def test_lista_sessoes_nao_derruba_a_mesa_se_o_banco_falha(self):
        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)

        def boom(*_args, **_kwargs):
            raise RuntimeError("undefined table")

        repository.list_concept_sessions = boom
        listed = lab.list_sessions({
            "client_id": 10,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
        })
        self.assertEqual(listed["sessions"], [])
        self.assertIsNone(listed["active"])
        self.assertEqual(listed["history"], [])

    def test_lista_sessoes_usa_as_abertas_se_a_campanha_sumiu(self):
        from aicentralv2.creative_modeling_repository import CreativeNotFoundError

        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        lab = FormatLabService(modeling)
        first = lab.create_session({
            "client_id": 10,
            "campaign_id": 30,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
        })
        lab.storyboard(first["id"], {
            "campaign_slug": "vivara-presente-ctv",
            "scene_count": 4,
        })

        def missing(_campaign_id):
            raise CreativeNotFoundError("Campanha não encontrada.")

        repository.get_campaign = missing
        listed = lab.list_sessions({
            "client_id": 10,
            "format": "video-linear-15",
            "campaign_slug": "vivara-presente-ctv",
        })
        self.assertEqual(listed["active"]["id"], first["id"])
        self.assertEqual(listed["history"][0]["session_id"], first["id"])

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
        self.assertIn("camadas", MC_DESKS)
        self.assertIn("design-system", MC_DESKS)
        self.assertEqual(MC_DESKS["trocar"]["page_js"], "js/mc-trocar.js")
        self.assertEqual(MC_DESKS["camadas"]["page_js"], "js/mc-camadas.js")
        self.assertEqual(MC_DESKS["camadas"]["panel"], "parametros/_mc_camadas.html")
        self.assertEqual(MC_DESKS["design-system"]["page_js"], "js/mc-design-system.js")
        self.assertEqual(MC_DESKS["mesa"]["panel"], "parametros/_mc_mesa.html")
        self.assertEqual(MC_DESKS["mesa"]["page_js"], "js/mc-mesa.js")
        self.assertEqual(MC_DESKS["placas"]["page_js"], "js/mc-placas.js")
        root = Path(__file__).resolve().parents[1]
        self.assertNotIn("states", MC_DESKS)
        docs = (root / "docs" / "modeling-ux-refactor.md").read_text(encoding="utf-8")
        self.assertIn("--cx-mesa-teal", docs)
        self.assertIn("/lab/modelagem/states", docs)
        app = Flask(__name__)
        register_modeling_ux_lab(app)
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        self.assertIn("/lab/modelagem/states", rules)
        self.assertIn("/lab/trocr/states", rules)
        self.assertIn("/lab/design-system/marca/<client_id>", rules)
        self.assertIn("/lab/design-system/campanha/<campaign_id>", rules)
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
        self.assertIn("modelagem_camadas", shell)
        self.assertIn("modelagem_design-system", shell)
        desk = (root / "aicentralv2" / "templates" / "parametros" / "modelagem_desk.html").read_text(encoding="utf-8")
        self.assertIn("modelagem_criativos.css') }}?v=104", desk)
        self.assertIn("mc_page_js) }}?v=65", desk)
        self.assertIn("js/mc-dsa-write-queue.js", desk)
        camadas = (root / "aicentralv2" / "templates" / "parametros" / "_mc_camadas.html").read_text(encoding="utf-8")
        self.assertIn("mcLayersRun", camadas)
        self.assertIn("Separar", camadas)
        self.assertIn("mcLayersImage", camadas)
        self.assertIn("Limpar poço", camadas)
        self.assertNotIn("Os dois", camadas)
        self.assertIn("mcLayersCopy", camadas)
        self.assertIn("Abrir criativo de teste", camadas)
        self.assertIn("O still vira acetato", camadas)
        js = (root / "aicentralv2" / "static" / "js" / "mc-camadas.js").read_text(encoding="utf-8")
        self.assertIn("/api/format-lab/layers/split", js)
        self.assertIn("/api/format-lab/layers/example", js)
        self.assertIn("Tipo fica no HTML", js)
        dsa = (root / "aicentralv2" / "templates" / "parametros" / "_mc_design_system.html").read_text(encoding="utf-8")
        self.assertLess(dsa.find("mc-dsa-preview"), dsa.find("mc-dsa-side"))
        self.assertIn("Montar", dsa)
        self.assertIn("Aprovar", dsa)
        self.assertIn("mcDsaCatalog", dsa)
        self.assertIn("mcDsaStage", dsa)
        self.assertNotIn("data-mode", dsa)
        self.assertNotIn("Folha", dsa)
        self.assertNotIn("Pedir ao modelo", dsa)
        self.assertNotIn("Continuar loop", dsa)
        css = (root / "aicentralv2" / "static" / "css" / "modelagem_criativos.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: minmax(0, 1fr) 20rem;", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr) 22rem;", css)
        self.assertNotIn("grid-template-columns: 15rem minmax(0, 1fr) 22rem;", css)
        mesa_dir = root / "aicentralv2" / "templates" / "parametros"
        html = (mesa_dir / "_mc_mesa.html").read_text(encoding="utf-8")
        for path in sorted((mesa_dir / "mesa").glob("*.html")):
            html += path.read_text(encoding="utf-8")
        self.assertIn("mc-mesa-stage", html)
        self.assertIn("mcMesaStage", html)
        self.assertIn("Selecionar key visual", html)
        self.assertIn("Selecione um asset da campanha ou envie uma nova imagem.", html)
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
        self.assertIn("As batidas do 15s", html)
        self.assertIn("mcMesaStrip", html)
        self.assertIn("mcMesaRead", html)
        self.assertIn("Ler still de novo", html)
        self.assertIn("Ver textos reconhecidos", html)
        self.assertIn("Sem still de referência.", html)
        js = (root / "aicentralv2" / "static" / "js" / "mc-mesa.js").read_text(encoding="utf-8")
        self.assertIn("reread_still", js)
        self.assertIn("Leitura concluída.", js)
        self.assertIn("Leitura parcial. Há conteúdo pendente.", js)
        self.assertIn("Nenhum texto identificado.", js)
        self.assertIn("Leitura indisponível.", js)
        self.assertIn("Não foi possível concluir a leitura.", js)
        self.assertIn("Campanha travada", js)
        self.assertIn("readToken", js)
        self.assertIn("Abrir Marcas", html)
        self.assertIn("data-state", html)
        self.assertIn("mcMesaConfirm", html)
        self.assertNotIn("states", MC_DESKS)
        states = (mesa_dir / "mesa" / "states.html").read_text(encoding="utf-8")
        self.assertIn("Canvas vazio", states)
        self.assertIn("Conceito idle", states)
        self.assertIn("Loading", states)
        self.assertIn("Sucesso", states)
        self.assertIn("Warning", states)
        self.assertIn("Erro", states)
        self.assertIn("Confirmação", states)
        self.assertIn("Toast e inline", states)
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
        self.assertIn("setModalState", js)
        self.assertIn("askConfirm", js)
        self.assertIn("runCurrentBeat", js)
        self.assertIn("paintRunStill", js)
        self.assertIn("startRunProgress", js)
        self.assertIn("resumeDesk", js)
        self.assertIn("renderHistory([])", js)
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
        trocar_dir = root / "aicentralv2" / "templates" / "parametros"
        trocar = (trocar_dir / "_mc_trocar.html").read_text(encoding="utf-8")
        for path in sorted((trocar_dir / "trocr").glob("*.html")):
            trocar += path.read_text(encoding="utf-8")
        self.assertIn("mcSwapOut", trocar)
        self.assertIn("9:16", trocar)
        self.assertIn("Rotacionar layout", trocar)
        self.assertIn("mcSwapElements", trocar)
        self.assertIn("Editar criativo com IA", trocar)
        self.assertIn("Prompt otimizado", trocar)
        self.assertIn("mcTrocrRisk", trocar)
        self.assertIn("mcTrocrForceImage", trocar)
        self.assertIn("mcTrocrRoute", trocar)
        self.assertIn("mcTrocrDates", trocar)
        self.assertIn("mcTrocrSubtitle", trocar)
        self.assertIn("mcTrocrLogo", trocar)
        self.assertIn("mcTrocrDisclaimer", trocar)
        self.assertIn("Tipo na foto", trocar)
        self.assertIn("Compor na foto", trocar)
        self.assertIn("Todas as versões são preservadas", trocar)
        states = (trocar_dir / "trocr" / "states.html").read_text(encoding="utf-8")
        self.assertIn("Canvas vazio", states)
        self.assertIn("Histórico com 4 versões", states)
        self.assertIn("Reprocessamento OCR", states)
        docs = (root / "docs" / "trocr-editor-refactor.md").read_text(encoding="utf-8")
        self.assertIn("OCR dinâmico", docs)
        self.assertIn("/lab/trocr/states", docs)
        self.assertIn("Faixa de etapas no topo", docs)
        self.assertIn("/parametros/api/format-lab/swap/history", docs)
        self.assertNotIn("Sidebar de fluxo", docs)
        swap_js = (root / "aicentralv2" / "static" / "js" / "mc-trocar.js").read_text(encoding="utf-8")
        self.assertIn("/parametros/api/format-lab/swap/read", swap_js)
        self.assertIn("/parametros/api/format-lab/swap/prompt", swap_js)
        self.assertIn("/parametros/api/format-lab/swap/history", swap_js)
        self.assertIn("parent_id", swap_js)
        self.assertIn("histórico mudou", swap_js)
        self.assertIn("X-Trocr-CSRF-Token", swap_js)
        self.assertIn("data-csrf", trocar)
        self.assertIn("register_trocr_routes", (root / "aicentralv2" / "creative_format_lab" / "swap_routes.py").read_text(encoding="utf-8"))
        self.assertIn("persistHistory", swap_js)
        self.assertIn("loadHistory", swap_js)
        self.assertIn("aspect_ratio", swap_js)
        self.assertIn("logo_text", swap_js)
        self.assertIn("mcTrocrSubtitle", swap_js)
        self.assertIn("item.kind === 'face'", swap_js)
        self.assertIn("logo_used", swap_js)
        self.assertIn("pushVersion", swap_js)
        self.assertIn("useAsBase", swap_js)
        self.assertIn("Usar como base", swap_js)
        self.assertIn("rotateLayout", swap_js)
        self.assertIn("paintRisk", swap_js)
        self.assertIn("paintRoute", swap_js)
        self.assertIn("force_image", swap_js)
        self.assertIn("typeset", swap_js)
        self.assertIn("recrop", swap_js)
        self.assertIn("Compor na foto", swap_js)
        self.assertIn("Recortar e compor", swap_js)
        self.assertIn("mcTrocrDates", swap_js)
        self.assertIn("mcTrocrCta2", swap_js)
        self.assertIn("withCtas", swap_js)
        self.assertIn("renderEditPanels", swap_js)
        ocr_fields = (trocar_dir / "trocr" / "_ocr_fields.html").read_text(encoding="utf-8")
        self.assertIn("mcTrocrCta2", ocr_fields)
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

    def test_camadas_js_substitui_o_pacote_inteiro(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "aicentralv2" / "static" / "js" / "mc-camadas.js").read_text(encoding="utf-8")
        self.assertIn("function showPack(data)", js)
        self.assertIn("function escapeHtml(value)", js)
        self.assertIn("operationId", js)
        self.assertIn("operation_id", js)
        self.assertIn("replace === 'ground'", js)
        self.assertIn("lastNonGround.concat(ground)", js)
        self.assertIn("lastRead", js)
        self.assertIn("split('image')", js)


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
                "alter": ["headline"],
                "headline": "Cuidado que se vê",
                "force_image": True,
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
        self.assertIn("analysis", result)
        self.assertTrue(result["analysis"]["logo"])
        self.assertTrue(result["analysis"]["headline"])
        self.assertEqual(result["status"], "completed")

    def test_cartela_de_elenco_compõe_tipo_sem_image2(self):
        from aicentralv2.creative_format_lab.swap import (
            looks_scrambled,
            score_swap_copy,
            swap_mode,
            swap_reference,
        )

        fixture = Path(__file__).resolve().parent / "fixtures" / "creatives" / "arraial-1x1.png"
        raw = fixture.read_bytes()
        reference = "data:image/png;base64," + __import__("base64").b64encode(raw).decode("ascii")
        payload = {
            "reference": reference,
            "aspect_ratio": "1:1",
            "preserve": ["layout", "people", "colors", "graphic"],
            "alter": ["secondary"],
            "support": "Entrada franca",
            "ref_width": 640,
            "ref_height": 640,
            "regions": {"secondary": [486, 172, 633, 261]},
            "elements": [
                {"role": "person", "text": "Mumuzinho"},
                {"role": "person", "text": "Zé Vaqueiro"},
                {"role": "person", "text": "Chama Chuva"},
                {"role": "person", "text": "Felipe Araújo"},
            ],
            "faces": 6,
        }
        self.assertEqual(swap_mode(payload), "typeset")
        called = {"n": 0}

        def boom(*_a, **_k):
            called["n"] += 1
            raise AssertionError("Image 2 não deveria rodar")

        result = swap_reference(payload, image_callable=boom)
        self.assertEqual(result["mode"], "typeset")
        self.assertEqual(called["n"], 0)
        self.assertTrue(result["png_data_url"].startswith("data:image/png"))
        self.assertEqual(result["patches"][0]["text"], "Entrada franca")
        from PIL import Image
        import io
        original = Image.open(io.BytesIO(raw)).convert("RGB")
        painted = Image.open(
            io.BytesIO(__import__("base64").b64decode(result["png_data_url"].split(",", 1)[1]))
        ).convert("RGB")
        self.assertEqual(original.size, painted.size)
        self.assertEqual(original.getpixel((320, 280)), painted.getpixel((320, 280)))
        self.assertEqual(original.getpixel((430, 250)), painted.getpixel((430, 250)))
        self.assertFalse(looks_scrambled("Entrada franca"))
        self.assertTrue(looks_scrambled("Entradada franceça"))
        scored = score_swap_copy(
            {"support": "Entrada franca", "elements": [{"role": "person", "text": "Mumuzinho"}]},
            locks=["Entrada franca", "Mumuzinho"],
            forbidden=["É de graça"],
        )
        self.assertEqual(scored["accuracy"], 1.0)
        self.assertFalse(scored["scrambled"])

    def test_typeset_16x9_nao_pinta_a_pessoa(self):
        import base64
        import io

        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.swap import swap_mode, swap_reference

        canvas = Image.new("RGB", (640, 240), (1, 21, 74))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([28, 32, 250, 48], fill=(255, 255, 255))
        draw.rectangle([28, 56, 210, 72], fill=(255, 255, 255))
        draw.ellipse([470, 30, 610, 210], fill=(200, 40, 40))
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        reference = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        payload = {
            "reference": reference,
            "aspect_ratio": "16:9",
            "aspect_hint": "16:9",
            "preserve": ["people", "logo", "colors", "style"],
            "alter": ["headline"],
            "headline": "Internet extra que cabe no mês",
            "faces": 1,
            "ref_width": 640,
            "ref_height": 240,
            "regions": {"headline": [20, 24, 260, 80]},
        }
        self.assertEqual(swap_mode(payload), "typeset")
        result = swap_reference(payload)
        painted = Image.open(io.BytesIO(base64.b64decode(result["png_data_url"].split(",", 1)[1]))).convert("RGB")
        self.assertEqual(canvas.getpixel((540, 120)), painted.getpixel((540, 120)))
        self.assertEqual(painted.getpixel((400, 40)), canvas.getpixel((400, 40)))

    def test_typeset_slot_cego_nao_preenche_a_pessoa(self):
        import base64
        import io

        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.swap import typeset_reference

        canvas = Image.new("RGB", (640, 240), (1, 21, 74))
        draw = ImageDraw.Draw(canvas)
        draw.ellipse([470, 30, 610, 210], fill=(200, 40, 40))
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        reference = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        result = typeset_reference({
            "reference": reference,
            "aspect_ratio": "16:9",
            "alter": ["headline"],
            "headline": "Internet extra",
        })
        painted = Image.open(io.BytesIO(base64.b64decode(result["png_data_url"].split(",", 1)[1]))).convert("RGB")
        self.assertEqual(canvas.getpixel((540, 120)), painted.getpixel((540, 120)))
        self.assertFalse((result.get("patches") or [{}])[0].get("masked"))

    def test_recrop_compõe_tipo_depois_do_image2(self):
        from aicentralv2.creative_format_lab.swap import (
            inflated_numbers,
            needs_recrop,
            score_swap_copy,
            swap_mode,
            swap_reference,
        )

        fixture = Path(__file__).resolve().parent / "fixtures" / "creatives" / "arraial-1x1.png"
        raw = fixture.read_bytes()
        reference = "data:image/png;base64," + __import__("base64").b64encode(raw).decode("ascii")
        payload = {
            "reference": reference,
            "aspect_ratio": "9:16",
            "aspect_hint": "16:9",
            "preserve": ["people", "logo", "colors"],
            "alter": ["price"],
            "headline": "Aproveite muita internet pra falar à vontade com a família toda",
            "support": "ATÉ 2000 GB",
            "price": "R$ 199,90/mês",
            "cta": "Contratar",
            "force_image": True,
        }
        self.assertTrue(needs_recrop(payload))
        self.assertEqual(swap_mode(payload), "recrop")
        called = {"n": 0}

        def fake_image(*_a, **_k):
            called["n"] += 1
            return {"b64_json": __import__("base64").b64encode(raw).decode("ascii")}

        result = swap_reference(payload, image_callable=fake_image)
        self.assertEqual(called["n"], 1)
        self.assertEqual(result["mode"], "recrop")
        self.assertEqual(result["passes"], ["image", "typeset"])
        texts = [item["text"] for item in result["patches"]]
        self.assertIn("R$ 199,90/mês", texts)
        self.assertNotIn("ATÉ 2000 GB", texts)
        self.assertTrue(inflated_numbers("ATÉ 17000 GB R$ 1999,90", ["1700", "2000"]))
        scored = score_swap_copy({"support": "17000 GB"}, locks=["1700"])
        self.assertTrue(scored["scrambled"])
        self.assertIn("1700", scored["inflated"])

    def test_prompt_de_item_nao_pede_troca_de_marca(self):
        from aicentralv2.creative_format_lab.swap import score_swap_copy

        prompt = build_optimized_prompt(
            {
                "headline": "Te encontro no Arraial de Belô",
                "support": "É de graça!",
                "aspect_ratio": "1:1",
                "preserve": ["layout", "people", "colors", "graphic"],
                "alter": ["secondary"],
                "locks": ["Mumuzinho", "Mineirinho", "Belô Horizonte"],
                "note": "Trocar só o selo 'É de graça!' por 'Entrada franca'.",
            }
        )
        self.assertIn("item swap", prompt)
        self.assertIn("name-pill", prompt)
        self.assertIn("Mumuzinho", prompt)
        self.assertIn("glyph by glyph", prompt)
        self.assertIn("Clone those text regions", prompt)
        self.assertIn("Change only", prompt)
        self.assertNotIn("Swap only the advertised brand, product and copy", prompt)
        risk = preview_swap_prompt(
            {
                "preserve": ["people"],
                "alter": ["secondary"],
                "faces": 6,
            }
        )["risk"]
        self.assertEqual(risk["level"], "high")
        scored = score_swap_copy(
            {"support": "Entrada franca", "elements": [{"role": "person", "text": "Mumuzinho"}]},
            locks=["Mumuzinho", "Entrada franca"],
            forbidden=["É de graça"],
        )
        self.assertEqual(scored["accuracy"], 1.0)
        self.assertEqual(scored["misses"], [])

    def test_prompt_otimizado_respeita_preservar_e_qualidade(self):
        prompt = build_optimized_prompt(
            {
                "brand_name": "TIM",
                "headline": "TIM ULTRA COMBO",
                "price": "R$ 149,90",
                "cta": "Assine",
                "note": "Diminuir o TIM ULTRA COMBO.",
                "preserve": ["layout", "people", "logo"],
                "alter": ["headline", "price"],
                "quality": "draft",
                "use_brand_context": True,
            },
            brand={"name": "TIM", "tone_of_voice": "direto"},
        )
        self.assertIn("Preserve exactly", prompt)
        self.assertIn("Change only", prompt)
        self.assertIn("draft preview", prompt)
        self.assertIn("Brand tone", prompt)
        preview = preview_swap_prompt(
            {
                "brand_name": "TIM",
                "headline": "TIM ULTRA COMBO",
                "preserve": ["logo"],
                "alter": ["headline"],
                "quality": "production",
            }
        )
        self.assertIn("identidade visual", preview["preview"])
        self.assertEqual(preview["quality"], "production")
        self.assertNotEqual(quote_swap({"quality": "draft"})["estimated_cost_usd"], quote_swap()["estimated_cost_usd"])

    def test_prompt_override_nao_reescreve_o_texto(self):
        prompt = build_optimized_prompt({"prompt_override": "Manter as pessoas e só trocar o CTA."})
        self.assertEqual(prompt, "Manter as pessoas e só trocar o CTA.")

    def test_geracao_nao_reusa_id_da_versao(self):
        first = swap_reference(
            {"reference": "data:image/png;base64,aaa", "quality": "draft", "alter": ["cta"], "cta": "A", "force_image": True},
            image_callable=lambda *_a, **_k: {"b64_json": "YQ=="},
        )
        second = swap_reference(
            {"reference": "data:image/png;base64,bbb", "quality": "production", "alter": ["cta"], "cta": "B", "force_image": True},
            image_callable=lambda *_a, **_k: {"b64_json": "Yg=="},
        )
        self.assertNotEqual(first["png_data_url"], second["png_data_url"])
        self.assertEqual(first["quality"], "draft")
        self.assertEqual(second["quality"], "production")

    def test_swap_sem_referencia_falha(self):
        with self.assertRaises(ValueError):
            swap_reference({"brand_name": "Vivara"}, image_callable=lambda *_a, **_k: b"x")
        with self.assertRaises(ValueError):
            read_swap_reference({}, text_callable=lambda *_a, **_k: {})

    def test_historico_grava_por_marca_sem_data_url(self):
        class _MemStorage:
            def __init__(self):
                self.n = 0
                self.sessions = {}

            def save_generated_base64(self, encoded, output_format="png"):
                self.n += 1
                return f"/static/uploads/creative_generated/trocr{self.n}.png"

            def save_trocr_session(self, key, data):
                self.sessions[key] = data

            def load_trocr_session(self, key):
                return self.sessions.get(key)

        repository = FakeRepository()
        modeling = CreativeModelingService(repository, FakeGenerator(), storage=_MemStorage())
        lab = FormatLabService(modeling)
        png = "data:image/png;base64," + TINY_PNG.hex()
        saved = lab.save_swap_history(
            {
                "client_id": 10,
                "active_id": "v2",
                "base_id": "v1",
                "aspect_ratio": "9:16",
                "versions": [
                    {"id": "v1", "name": "Original", "origin": "original", "image": png},
                    {"id": "v2", "name": "Produção", "origin": "production", "image": png},
                ],
            },
            user_id=7,
        )
        self.assertEqual(len(saved["versions"]), 2)
        self.assertTrue(saved["versions"][0]["image_url"].startswith("/static/uploads/"))
        self.assertFalse(saved["versions"][0]["image_url"].startswith("data:"))
        self.assertEqual(repository.brand_profiles[10]["trocr"]["active_id"], "v2")
        loaded = lab.load_swap_history({"client_id": 10}, user_id=7)
        self.assertEqual(loaded["active_id"], "v2")
        self.assertEqual(loaded["versions"][1]["name"], "Produção")
        self.assertEqual(loaded["revision"], 1)
        empty = lab.load_swap_history({"client_id": 11}, user_id=7)
        self.assertEqual(empty["versions"], [])

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
        swapped = lab.save_swap_history(
            {
                "client_id": 10,
                "revision": 2,
                "versions": [
                    {
                        "id": "v1",
                        "name": "Original",
                        "origin": "edited",
                        "image": "https://evil.example/track.png",
                    },
                    dropped["versions"][1],
                ],
            },
            user_id=7,
        )
        self.assertEqual(swapped["versions"][0]["origin"], "original")
        self.assertEqual(swapped["versions"][0]["image_url"], original)
        rejected = lab.save_swap_history(
            {
                "client_id": 10,
                "revision": 3,
                "versions": [
                    swapped["versions"][0],
                    swapped["versions"][1],
                    {"id": "v3", "origin": "edited", "image": "https://evil.example/track.png"},
                ],
            },
            user_id=7,
        )
        self.assertEqual([item["id"] for item in rejected["versions"]], ["v1", "v2"])
        with self.assertRaises(CreativeConflictError) as raised:
            lab.save_swap_history(
                {
                    "client_id": 10,
                    "revision": 1,
                    "versions": [swapped["versions"][0]],
                },
                user_id=7,
            )
        self.assertIn("histórico mudou", str(raised.exception).lower())

    def test_schema_legado_nao_funde_dates_e_subtitle(self):
        from aicentralv2.creative_format_lab.swap import prepare_swap, typeset_patches
        from aicentralv2.creative_format_lab.swap_schema import apply_swap_schema, infer_kind

        prepared = prepare_swap({
            "dates": "24 e 25 de julho",
            "subtitle": "",
            "headline": "Entrada franca",
            "instruction": "Não mexer no elenco.",
        })
        self.assertEqual(prepared["dates"], "24 e 25 de julho")
        self.assertEqual(prepared["subtitle"], "")
        self.assertEqual(prepared["note"], "Não mexer no elenco.")
        self.assertEqual(infer_kind("person", "Mumuzinho"), "name_pill")
        self.assertEqual(infer_kind("person", ""), "face")
        schema = apply_swap_schema({
            "elements": [
                {"role": "cta", "text": "Conferir planos"},
                {"role": "cta", "text": "Contratar"},
                {"role": "person", "text": ""},
                {"role": "person", "text": "Mumuzinho"},
            ],
            "logo_text": "TIM",
            "disclaimer": "Consulte condições.",
            "preserve": ["logo"],
        })
        ids = [item["id"] for item in schema["elements"]]
        kinds = {item["id"]: item["kind"] for item in schema["elements"]}
        self.assertIn("cta_01", ids)
        self.assertIn("cta_02", ids)
        self.assertEqual(kinds["cta_01"], "type")
        self.assertEqual(kinds["face_01"], "face")
        self.assertEqual(kinds["name_pill_01"], "name_pill")
        self.assertEqual(schema["faces"], 1)
        self.assertIn("TIM", schema["locks"])
        self.assertIn("Consulte condições.", schema["locks"])
        self.assertEqual(schema["logo_text"], "TIM")
        patches = typeset_patches({
            "alter": ["secondary"],
            "dates": "24 e 25 de julho",
            "subtitle": "linha que não é data",
            "support": "Entrada franca",
        })
        self.assertEqual(
            [item["slot"] for item in patches],
            ["secondary", "dates"],
        )
        self.assertEqual(patches[1]["text"], "24 e 25 de julho")

    def test_schema_recusa_texto_acima_do_limite_e_nao_descarta_lock(self):
        from aicentralv2.creative_format_lab.swap import prepare_swap
        from aicentralv2.creative_format_lab.swap_schema import apply_swap_schema, normalize_read

        with self.assertRaises(ValueError):
            prepare_swap({"price": "R$ " + ("9" * 40)})
        many = apply_swap_schema({
            "elements": [
                {"role": "person", "text": f"Nome {index}"}
                for index in range(1, 16)
            ],
        })
        self.assertGreaterEqual(len(many["locks"]), 15)
        self.assertTrue(many["locks_overflow"])
        read = normalize_read({
            "headline": "A" * 90,
            "cta": "Monte o seu",
        })
        self.assertEqual(len(read["headline"]), 90)
        self.assertIn("headline", read["overflow"])
        self.assertFalse(read["locks_overflow"])
        self.assertEqual(read["cta"], "Monte o seu")
        with self.assertRaises(ValueError) as raised:
            prepare_swap({"headline": "<html>oferta</html>"})
        self.assertIn("HTML", str(raised.exception))
        dup = apply_swap_schema({
            "elements": [
                {"id": "cta_01", "role": "cta", "text": "Conferir planos", "bbox_px": [10, 10, 40, 40]},
                {"id": "cta_01", "role": "cta", "text": "Contratar"},
                {"role": "person", "kind": "pessoa", "text": ""},
            ],
        })
        ids = [item["id"] for item in dup["elements"]]
        self.assertEqual(ids.count("cta_01"), 1)
        self.assertIn("cta_02", ids)
        self.assertEqual(dup["elements"][2]["kind"], "face")
        self.assertIsNone(dup["elements"][0]["bbox_px"])
        prepared = prepare_swap({
            "locks": [f"Nome {index}" for index in range(1, 16)],
        })
        from aicentralv2.creative_format_lab.swap import _lock_list
        self.assertEqual(len(_lock_list(prepared)), 15)

    def test_plano_unico_hash_conflitos_e_noop(self):
        from aicentralv2.creative_format_lab.swap import (
            read_swap_reference,
            swap_input_references,
            swap_reference,
            typeset_patches,
        )
        from aicentralv2.creative_format_lab.swap_plan import assert_swap_plan, build_swap_plan

        legado = {
            "base_id": "v1",
            "reference": "data:image/png;base64,aaa",
            "alter": ["headline"],
            "headline": "Internet extra",
            "force_image": True,
        }
        preview = preview_swap_prompt(legado)
        self.assertFalse(preview["noop"])
        self.assertFalse(preview["blocked"])
        self.assertEqual(preview["plan_hash"], build_swap_plan(legado)["plan_hash"])
        called = {"n": 0}

        def fake_image(*_a, **_k):
            called["n"] += 1
            return {"b64_json": "YQ=="}

        ran = swap_reference({**legado, "plan_hash": preview["plan_hash"]}, image_callable=fake_image)
        self.assertEqual(called["n"], 1)
        self.assertEqual(ran["plan_hash"], preview["plan_hash"])
        self.assertTrue(ran["png_data_url"].startswith("data:image/png"))
        with self.assertRaises(ValueError) as stale:
            swap_reference({**legado, "plan_hash": "deadbeef"}, image_callable=fake_image)
        self.assertIn("plano mudou", str(stale.exception).lower())

        noop = swap_reference({"reference": "data:image/png;base64,aaa", "base_id": "v1"})
        self.assertEqual(noop["mode"], "noop")
        self.assertTrue(noop["noop"])
        self.assertEqual(noop["png_data_url"], "")

        overlap = preview_swap_prompt({"preserve": ["people"], "alter": ["people"], "headline": "X"})
        self.assertTrue(any(item["code"] == "preserve_and_alter" for item in overlap["conflicts"]))
        self.assertTrue(overlap["blocked"])
        with self.assertRaises(ValueError):
            assert_swap_plan({
                "preserve": ["people"],
                "alter": ["people"],
                "headline": "X",
                "reference": "data:image/png;base64,aaa",
            })

        note = preview_swap_prompt({
            "note": "Trocar o preço para R$ 99",
            "alter": ["headline"],
            "headline": "Oferta",
        })
        self.assertTrue(any(item["code"] == "note_mismatch" for item in note["conflicts"]))

        field = preview_swap_prompt({
            "headline": "Novo título",
            "elements": [{"role": "headline", "text": "Título velho", "text_original": "Título velho"}],
        })
        self.assertTrue(any(item["code"] == "field_without_operation" for item in field["conflicts"]))

        patches = typeset_patches({
            "alter": ["price"],
            "headline": "Não pintar",
            "support": "ATÉ 2000 GB",
            "price": "R$ 10",
        })
        self.assertEqual([item["slot"] for item in patches], ["price"])

        unread = read_swap_reference({"reference": "data:image/png;base64,aaa"}, text_callable=None)
        self.assertEqual(unread["status"], "unavailable")
        self.assertTrue(unread["error"])
        broken = read_swap_reference(
            {"reference": "data:image/png;base64,aaa"},
            text_callable=lambda *_a, **_k: {"message": {"content": "isso não é json"}},
        )
        self.assertEqual(broken["status"], "invalid")
        self.assertNotEqual(broken["status"], "completed")

        refs = swap_input_references(
            {"reference": "data:image/png;base64,aaa", "preserve": ["logo"]},
            brand={"logo_url": "https://cdn.example/logo.png"},
        )
        self.assertEqual(refs, ["data:image/png;base64,aaa"])

        confirmed = {
            "reference": "data:image/png;base64,aaa",
            "preserve": ["people"],
            "alter": ["people"],
            "confirm_conflicts": True,
        }
        preview_ok = preview_swap_prompt(confirmed)
        self.assertFalse(preview_ok["blocked"])
        allowed = swap_reference(
            {**confirmed, "plan_hash": preview_ok["plan_hash"]},
            image_callable=fake_image,
        )
        self.assertEqual(allowed["mode"], "image")

        layout = preview_swap_prompt({
            "aspect_ratio": "9:16",
            "aspect_hint": "16:9",
            "preserve": ["layout"],
            "alter": ["price"],
            "price": "R$ 10",
        })
        self.assertTrue(any(item["code"] == "layout_vs_format" for item in layout["conflicts"]))

        with self.assertRaises(ValueError) as masked:
            assert_swap_plan({
                "preserve": ["logo"],
                "alter": ["headline"],
                "headline": "Oferta",
                "note": "Trocar o preço para R$ 99",
                "reference": "data:image/png;base64,aaa",
            }, brand={"logo_url": "https://cdn.example/logo.png"})
        self.assertIn("instrução", str(masked.exception).lower())

        def boom(*_a, **_k):
            raise RuntimeError("down")

        down = read_swap_reference(
            {"reference": "data:image/png;base64,aaa"},
            text_callable=boom,
        )
        self.assertEqual(down["status"], "provider_error")

    def test_hash_obsoleto_vira_409_no_servico(self):
        repository = FakeRepository()
        modeling = CreativeModelingService(repository, FakeGenerator())
        lab = FormatLabService(modeling)
        with self.assertRaises(CreativeConflictError) as raised:
            lab.swap({
                "reference": "data:image/png;base64,aaa",
                "alter": ["cta"],
                "cta": "A",
                "plan_hash": "deadbeef",
            })
        self.assertIn("plano mudou", str(raised.exception).lower())

    def test_noop_nao_grava_versao(self):
        class _MemStorage:
            def __init__(self):
                self.n = 0

            def save_generated_base64(self, encoded, output_format="png"):
                self.n += 1
                return f"/static/uploads/creative_generated/noop{self.n}.png"

        repository = FakeRepository()
        modeling = CreativeModelingService(repository, FakeGenerator(), storage=_MemStorage())
        lab = FormatLabService(modeling)
        result = lab.swap(
            {"reference": "data:image/png;base64,aaa", "client_id": 10},
            user_id=7,
        )
        self.assertTrue(result["noop"])
        self.assertEqual(result["mode"], "noop")
        self.assertFalse(result.get("png_data_url"))
        self.assertEqual(modeling.storage.n, 0)
        self.assertNotIn("trocr", repository.brand_profiles.get(10) or {})

    def test_typeset_com_mascara_nao_mexe_fora_da_bbox(self):
        import base64
        import io

        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.swap import (
            score_typeset_qa,
            typeset_reference,
        )
        from aicentralv2.creative_format_lab.swap_plan import build_swap_plan

        canvas = Image.new("RGB", (320, 120), (1, 21, 74))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([16, 40, 150, 88], fill=(255, 255, 255))
        draw.ellipse([230, 20, 300, 100], fill=(200, 40, 40))
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        reference = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        box = [16, 40, 150, 88]
        result = typeset_reference({
            "reference": reference,
            "alter": ["price"],
            "price": "R$ 99",
            "ref_width": 320,
            "ref_height": 120,
            "regions": {"price": box},
        })
        painted = Image.open(io.BytesIO(base64.b64decode(result["png_data_url"].split(",", 1)[1]))).convert("RGB")
        self.assertEqual(canvas.getpixel((260, 60)), painted.getpixel((260, 60)))
        self.assertEqual(result["qa"]["status"], "pass")
        self.assertEqual(result["qa"]["pixels_outside_mask"], 0)
        self.assertTrue(result["patches"][0]["masked"])
        leaked = canvas.copy()
        leaked.putpixel((260, 60), (0, 255, 0))
        failed = score_typeset_qa(canvas, leaked, [box])
        self.assertEqual(failed["status"], "fail")
        self.assertGreater(failed["pixels_outside_mask"], 0)
        with self.assertRaises(ValueError) as remote:
            typeset_reference({
                "reference": "https://evil.test/still.png",
                "alter": ["price"],
                "price": "R$ 1",
            })
        self.assertIn("URL", str(remote.exception))
        first = build_swap_plan({
            "alter": ["price"],
            "price": "R$ 99",
            "regions": {"price": [16, 40, 150, 88]},
        })
        second = build_swap_plan({
            "alter": ["price"],
            "price": "R$ 99",
            "regions": {"price": [20, 44, 160, 92]},
        })
        self.assertNotEqual(first["plan_hash"], second["plan_hash"])
        from aicentralv2.creative_format_lab import swap as swap_mod

        previous = swap_mod.TYPESET_MAX_PIXELS
        swap_mod.TYPESET_MAX_PIXELS = 100
        try:
            with self.assertRaises(ValueError) as huge:
                typeset_reference({
                    "reference": reference,
                    "alter": ["price"],
                    "price": "R$ 99",
                })
        finally:
            swap_mod.TYPESET_MAX_PIXELS = previous
        self.assertIn("pixels", str(huge.exception))

    def test_typeset_sem_regiao_nao_pinta_no_escuro(self):
        from aicentralv2.creative_format_lab.swap_plan import assert_swap_plan, build_swap_plan

        payload = {
            "reference": "data:image/png;base64,aaa",
            "preserve": ["people"],
            "alter": ["price"],
            "price": "R$ 99",
            "faces": 4,
            "confirm_conflicts": True,
        }
        plan = build_swap_plan(payload)
        self.assertTrue(any(item["code"] == "needs_region" for item in plan["conflicts"]))
        self.assertTrue(plan["blocked"])
        self.assertEqual(plan["mode"], "blocked")
        with self.assertRaises(ValueError) as raised:
            assert_swap_plan(payload)
        self.assertIn("região", str(raised.exception).lower())
        with_box = build_swap_plan({
            **payload,
            "regions": {"price": [16, 40, 150, 88]},
            "ref_width": 320,
            "ref_height": 120,
        })
        self.assertFalse(any(item["code"] == "needs_region" for item in with_box["conflicts"]))
        self.assertFalse(with_box["blocked"])
        self.assertEqual(with_box["mode"], "typeset")

    def test_texto_sem_elenco_e_regiao_vai_para_typeset(self):
        import base64
        import io

        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.swap import (
            _patch_ink,
            ratio_from_size,
            resolve_aspect_ratio,
            swap_mode,
            typeset_patches,
            typeset_reference,
        )

        self.assertEqual(ratio_from_size(640, 640), "1:1")
        self.assertEqual(ratio_from_size(1080, 1080), "1:1")
        self.assertEqual(ratio_from_size(1080, 1920), "9:16")
        self.assertEqual(resolve_aspect_ratio({"ref_width": 1080, "ref_height": 1920}), "9:16")
        self.assertEqual(resolve_aspect_ratio({"aspect_ratio": "1:1", "ref_width": 1080, "ref_height": 1920}), "1:1")
        self.assertEqual(swap_mode({"alter": ["price"], "price": "R$ 99"}), "typeset")

        canvas = Image.new("RGB", (320, 140), (1, 21, 74))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([12, 20, 140, 60], fill=(255, 255, 255))
        draw.rectangle([170, 80, 300, 120], fill=(250, 220, 40))
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        reference = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        result = typeset_reference({
            "reference": reference,
            "alter": ["price"],
            "price": "R$ 79",
            "ref_width": 320,
            "ref_height": 140,
            "regions": {"price": [12, 20, 140, 60]},
        })
        self.assertEqual(result["mode"], "typeset")
        self.assertEqual(result["qa"]["status"], "pass")
        painted = Image.open(io.BytesIO(base64.b64decode(result["png_data_url"].split(",", 1)[1]))).convert("RGB")
        self.assertEqual(canvas.getpixel((230, 100)), painted.getpixel((230, 100)))

        cta_ink = _patch_ink("cta", {"ink": (250, 220, 40), "cover": [(1, 1)]}, (1, 21, 74))
        self.assertEqual(cta_ink, (250, 220, 40))
        self.assertNotEqual(cta_ink, (17, 17, 17))

        pills = Image.new("RGB", (320, 80), (1, 21, 74))
        pill_draw = ImageDraw.Draw(pills)
        pill_draw.rectangle([12, 20, 120, 60], fill=(250, 220, 40))
        pill_draw.rectangle([200, 20, 308, 60], fill=(250, 220, 40))
        gap = pills.getpixel((160, 40))
        pill_buf = io.BytesIO()
        pills.save(pill_buf, format="PNG")
        two_ctas = typeset_reference({
            "reference": "data:image/png;base64," + base64.b64encode(pill_buf.getvalue()).decode("ascii"),
            "alter": ["cta"],
            "cta": "Conferir planos",
            "ref_width": 320,
            "ref_height": 80,
            "elements": [
                {"id": "cta_01", "role": "cta", "text": "Ver planos", "bbox_px": [12, 20, 120, 60]},
                {"id": "cta_02", "role": "cta", "text": "Contratar", "bbox_px": [200, 20, 308, 60]},
            ],
        })
        self.assertEqual(len(two_ctas["patches"]), 2)
        self.assertEqual([item["text"] for item in two_ctas["patches"]], ["Ver planos", "Contratar"])
        painted_ctas = Image.open(io.BytesIO(base64.b64decode(two_ctas["png_data_url"].split(",", 1)[1]))).convert("RGB")
        self.assertEqual(gap, painted_ctas.getpixel((160, 40)))

        preview = preview_swap_prompt({
            "headline": "Internet extra",
            "price": "R$ 169,99",
            "cta": "Assine",
            "alter": ["headline"],
            "elements": [
                {"role": "headline", "text": "Linha velha", "text_original": "Linha velha", "source": "ocr"},
            ],
        })
        self.assertIn("Internet extra", preview["prompt"])
        self.assertNotIn("Price exactly", preview["prompt"])
        self.assertIn("→", preview["preview"])

    def test_prompt_deriva_so_das_operacoes(self):
        prompt = build_optimized_prompt(
            {
                "headline": "Internet extra",
                "price": "R$ 169,99",
                "cta": "Assine",
                "alter": ["headline"],
            },
            operations=[{"field": "headline", "from": "Linha velha", "to": "Internet extra"}],
        )
        self.assertIn("Headline exactly: Internet extra", prompt)
        self.assertIn("Replace only the line 'Linha velha'", prompt)
        self.assertNotIn("Price exactly", prompt)
        self.assertNotIn("CTA exactly", prompt)

    def test_rascunho_do_trocr_manda_qualidade_media(self):
        from aicentralv2.creative_format_lab.swap import image_quality

        self.assertEqual(image_quality({"quality": "draft"}), "medium")
        self.assertEqual(image_quality({"quality": "rascunho"}), "medium")
        self.assertEqual(image_quality({"quality": "production"}), "high")

        seen = {}

        class Generator:
            def generate_image(self, prompt, **kwargs):
                seen.update(kwargs)
                return {"b64_json": __import__("base64").b64encode(TINY_PNG).decode()}

        class Modeling:
            generator = Generator()
            repository = None

        lab = FormatLabService(Modeling())
        lab._image_callable({"generate": True, "image_quality": "medium"})("x")
        self.assertEqual(seen.get("quality"), "medium")
        seen.clear()
        lab._image_callable({"generate": True})("x")
        self.assertNotIn("quality", seen)

    def test_duas_pills_sem_caixa_nao_pintam_o_vao(self):
        import base64
        import io

        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.swap import typeset_reference
        from aicentralv2.creative_format_lab.swap_plan import build_swap_plan

        pills = Image.new("RGB", (320, 80), (1, 21, 74))
        draw = ImageDraw.Draw(pills)
        draw.rectangle([12, 20, 120, 60], fill=(250, 220, 40))
        draw.rectangle([200, 20, 308, 60], fill=(250, 220, 40))
        gap = pills.getpixel((160, 40))
        buffer = io.BytesIO()
        pills.save(buffer, format="PNG")
        payload = {
            "reference": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
            "alter": ["cta"],
            "cta": "Ver planos",
            "ref_width": 320,
            "ref_height": 80,
            "elements": [
                {"id": "cta_01", "role": "cta", "text": "Ver planos"},
                {"id": "cta_02", "role": "cta", "text": "Contratar"},
            ],
        }
        plan = build_swap_plan({k: v for k, v in payload.items() if k != "reference"})
        self.assertFalse(plan["blocked"])
        self.assertEqual(plan["mode"], "typeset")
        result = typeset_reference(payload)
        self.assertEqual(len(result["patches"]), 2)
        self.assertEqual([item["text"] for item in result["patches"]], ["Ver planos", "Contratar"])
        self.assertTrue(all(item.get("bbox_px") for item in result["patches"]))
        painted = Image.open(io.BytesIO(base64.b64decode(result["png_data_url"].split(",", 1)[1]))).convert("RGB")
        self.assertEqual(gap, painted.getpixel((160, 40)))
        self.assertEqual(result["qa"]["status"], "pass")

    def test_um_cta_pinta_so_a_pill_da_esquerda(self):
        import base64
        import io

        from PIL import Image, ImageDraw

        from aicentralv2.creative_format_lab.swap import typeset_reference
        from aicentralv2.creative_format_lab.swap_plan import build_swap_plan

        pills = Image.new("RGB", (320, 80), (1, 21, 74))
        draw = ImageDraw.Draw(pills)
        draw.rectangle([12, 20, 120, 60], fill=(250, 220, 40))
        draw.rectangle([200, 20, 308, 60], fill=(250, 220, 40))
        second = pills.getpixel((250, 40))
        gap = pills.getpixel((160, 40))
        buffer = io.BytesIO()
        pills.save(buffer, format="PNG")
        payload = {
            "reference": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
            "alter": ["cta"],
            "cta": "Assine agora",
            "ref_width": 320,
            "ref_height": 80,
        }
        plan = build_swap_plan({k: v for k, v in payload.items() if k != "reference"})
        self.assertFalse(plan["blocked"])
        self.assertEqual(plan["mode"], "typeset")
        result = typeset_reference(payload)
        self.assertEqual(len(result["patches"]), 1)
        painted = Image.open(io.BytesIO(base64.b64decode(result["png_data_url"].split(",", 1)[1]))).convert("RGB")
        self.assertEqual(gap, painted.getpixel((160, 40)))
        self.assertEqual(second, painted.getpixel((250, 40)))
        self.assertNotEqual(pills.getpixel((66, 40)), painted.getpixel((66, 40)))
        self.assertEqual(result["qa"]["status"], "pass")

        empty = Image.new("RGB", (320, 80), (1, 21, 74))
        empty_buf = io.BytesIO()
        empty.save(empty_buf, format="PNG")
        with self.assertRaises(ValueError) as raised:
            typeset_reference({
                "reference": "data:image/png;base64," + base64.b64encode(empty_buf.getvalue()).decode("ascii"),
                "alter": ["cta"],
                "cta": "Assine agora",
            })
        self.assertIn("pill", str(raised.exception).lower())


class CreativeFormatLabStillBeatsTest(unittest.TestCase):
    BLACK_READ = {
        "headline": "Acesse vantagens exclusivas e um superbônus de internet",
        "support": "até 110GB + bônus para redes sociais",
        "price": "R$ 169,99",
        "cta": "Conferir planos",
        "logo_text": "TIM Black",
    }
    STILL = "https://cdn.example/tim-black.png"

    def _payload(self, **extra):
        from aicentralv2.creative_format_lab.engineer import _still_fingerprint

        data = {
            "scene_count": 4,
            "variant": "A",
            "images": [self.STILL],
            "still_read": dict(self.BLACK_READ),
            "still_fingerprint": _still_fingerprint(self.STILL),
            "ocr_status": "succeeded",
        }
        data.update(extra)
        return data

    def _adversary(self, messages, **_k):
        blob = str(messages)
        if "CreativeFormatSpec" in blob:
            return {
                "message": {
                    "content": {
                        "intent": "create",
                        "format": "video-linear-15",
                        "variant": "A",
                        "adapter": "generic_ctv",
                        "platform_label": "CTV",
                        "brand_name": "TIM",
                        "scenes": [
                            {"id": "scene_01", "purpose": "hook", "headline": "Internet infinita"},
                            {"id": "scene_02", "purpose": "benefit", "headline": "TIM Black"},
                            {"id": "scene_03", "purpose": "proof", "headline": "R$ 99"},
                            {
                                "id": "scene_04",
                                "purpose": "cta",
                                "headline": "TIM Black",
                                "cta": "Saiba mais",
                            },
                        ],
                    }
                }
            }
        if "Leia os elementos editáveis deste still." in blob:
            return {"message": {"content": dict(self.BLACK_READ)}}
        return {"message": {"content": {"passed": True, "score": 0.9, "defects": [], "patches": []}}}

    def test_tim_black_herda_papeis_do_still(self):
        board = build_storyboard(
            self._payload(),
            client={"id": 32, "name": "TIM"},
            text_callable=self._adversary,
        )
        cards = {item["id"]: item for item in board["storyboard"]}
        bind = board["copy_bind"]
        self.assertEqual(bind["ocr_status"], "succeeded")
        self.assertEqual(cards["scene_01"]["headline"], self.BLACK_READ["headline"])
        self.assertEqual(cards["scene_02"]["headline"], self.BLACK_READ["support"])
        self.assertEqual(cards["scene_03"]["headline"], self.BLACK_READ["price"])
        self.assertEqual(cards["scene_04"]["cta"], "Conferir planos")
        self.assertNotEqual(cards["scene_02"]["headline"], "TIM Black")
        self.assertNotEqual(cards["scene_04"]["cta"], "TIM Black")
        self.assertNotIn("Internet infinita", [item["headline"] for item in board["storyboard"]])
        roles = {item["scene_id"]: item["source_block"] for item in bind["beats"]}
        self.assertEqual(roles["scene_01"], "headline")
        self.assertEqual(roles["scene_02"], "support")
        self.assertEqual(roles["scene_03"], "price")
        self.assertEqual(roles["scene_04"], "cta")
        self.assertEqual(board["provider"], "llm")

    def test_modelo_adversarial_nao_chega_ao_html(self):
        result = run_session(
            {**self._payload(), "format": "video-linear-15", "renders": 1},
            client={"id": 32, "name": "TIM", "primary_color": "#0033A0"},
            text_callable=self._adversary,
            screenshot=_shot,
        )
        headlines = [item["headline"] for item in result["scenes"]]
        self.assertEqual(headlines[0], self.BLACK_READ["headline"])
        self.assertEqual(headlines[1], self.BLACK_READ["support"])
        self.assertEqual(headlines[2], self.BLACK_READ["price"])
        self.assertEqual(result["scenes"][3]["cta"], "Conferir planos")
        html = " ".join(item.get("html") or "" for item in result["scenes"])
        self.assertIn("Conferir planos", html)
        self.assertIn("110GB", html)
        self.assertNotIn("Internet infinita", html)
        self.assertEqual(result["spec"]["scenes"][1]["headline"], self.BLACK_READ["support"])
        self.assertEqual(result["copy_bind"]["ocr_status"], "succeeded")
        self.assertEqual(result["copy_bind"]["beats"][1]["source_block"], "support")

    def test_copy_insuficiente_nao_inventa_beneficio(self):
        payload = self._payload(still_read={
            "headline": "Acesse vantagens exclusivas",
            "support": "",
            "price": "",
            "cta": "Conferir planos",
            "logo_text": "TIM Black",
        })
        board = build_storyboard(payload, client={"id": 32, "name": "TIM"}, text_callable=self._adversary)
        cards = {item["id"]: item for item in board["storyboard"]}
        states = {item["scene_id"]: item["bind_state"] for item in board["copy_bind"]["beats"]}
        self.assertEqual(states["scene_01"], "bound")
        self.assertEqual(states["scene_02"], "insufficient")
        self.assertEqual(states["scene_03"], "insufficient")
        self.assertEqual(states["scene_04"], "bound")
        self.assertEqual(cards["scene_02"]["headline"], "")
        self.assertNotEqual(cards["scene_02"]["headline"], "TIM Black")
        self.assertNotEqual(cards["scene_02"]["headline"], "Internet infinita")
        self.assertEqual(cards["scene_03"]["headline"], "")
        self.assertEqual(board["copy_bind"]["ocr_status"], "partial")
        self.assertEqual(board["provider"], "llm")

    def test_leitura_parcial_nao_completa_campo_ilegivel(self):
        payload = self._payload(still_read={
            "headline": "Acesse vantagens exclusivas",
            "support": "",
            "price": "R$ 169,99",
            "cta": "Conferir planos",
            "logo_text": "TIM Black",
        })
        board = build_storyboard(payload, client={"id": 32, "name": "TIM"}, text_callable=self._adversary)
        cards = {item["id"]: item for item in board["storyboard"]}
        self.assertEqual(cards["scene_03"]["headline"], "R$ 169,99")
        self.assertEqual(cards["scene_02"]["headline"], "")
        self.assertEqual(cards["scene_04"]["cta"], "Conferir planos")

    def test_ocr_falhou_nao_e_sem_still(self):
        from aicentralv2.creative_format_lab.engineer import _still_fingerprint, apply_still_read, normalize_knobs

        knobs = apply_still_read(
            normalize_knobs({
                "still_read": {},
                "ocr_status": "failed",
                "still_fingerprint": _still_fingerprint(self.STILL),
            }),
            [self.STILL],
        )
        bind = knobs["still_bind"]
        self.assertEqual(bind["ocr_status"], "failed")
        self.assertNotEqual(bind["ocr_status"], "none")
        self.assertTrue(all(item["bind_state"] == "failed" for item in bind["beats"]))

    def test_ocr_indisponivel_nao_declara_heranca(self):
        board = build_storyboard(
            {
                "scene_count": 4,
                "images": [self.STILL],
            },
            client={"id": 32, "name": "TIM"},
        )
        bind = board["copy_bind"]
        self.assertEqual(bind["ocr_status"], "unavailable")
        self.assertTrue(all(item["bind_state"] == "unavailable" for item in bind["beats"]))
        self.assertNotEqual(bind["ocr_status"], "none")
        self.assertFalse(any(item["headline"] == "TIM Black" for item in board["storyboard"]))

    def test_troca_de_still_descarta_lock_obsoleto(self):
        payload = self._payload(storyboard=[
            {"id": "scene_02", "headline": "TIM Black", "purpose": "benefit"},
            {"id": "scene_01", "headline": self.BLACK_READ["headline"]},
        ])
        board = build_storyboard(payload, client={"id": 32, "name": "TIM"}, text_callable=self._adversary)
        cards = {item["id"]: item for item in board["storyboard"]}
        self.assertEqual(cards["scene_01"]["headline"], self.BLACK_READ["headline"])
        self.assertEqual(cards["scene_02"]["headline"], self.BLACK_READ["support"])
        self.assertNotEqual(cards["scene_02"]["headline"], "TIM Black")

    def test_regenerar_visual_preserva_copy_autorizada(self):
        payload = self._payload(storyboard=[
            {"id": "scene_01", "headline": self.BLACK_READ["headline"]},
            {"id": "scene_03", "headline": self.BLACK_READ["price"]},
        ])
        board = build_storyboard(payload, client={"id": 32, "name": "TIM"}, text_callable=self._adversary)
        cards = {item["id"]: item for item in board["storyboard"]}
        self.assertEqual(cards["scene_01"]["headline"], self.BLACK_READ["headline"])
        self.assertEqual(cards["scene_03"]["headline"], self.BLACK_READ["price"])
        self.assertEqual(cards["scene_04"]["cta"], "Conferir planos")

    def test_sem_still_preserva_campanha(self):
        board = build_storyboard(
            {"campaign_slug": "vivara-presente-ctv", "scene_count": 4},
            client={"id": 4, "name": "Vivara"},
        )
        self.assertEqual(board["copy_bind"]["ocr_status"], "none")
        self.assertIn("momentos", board["storyboard"][0]["headline"].lower())

    def test_dois_ctas_na_leitura_nao_sao_concatenados(self):
        payload = self._payload(still_read_full={
            "cta": "Conferir planos",
            "elements": [
                {"id": "cta_01", "role": "cta", "text": "Conferir planos"},
                {"id": "cta_02", "role": "cta", "text": "Contratar"},
            ],
        })
        board = build_storyboard(payload, client={"id": 32, "name": "TIM"}, text_callable=self._adversary)
        options = board["copy_bind"]["cta_options"]
        self.assertEqual([item["text"] for item in options], ["Conferir planos", "Contratar"])
        self.assertEqual(board["storyboard"][3]["cta"], "Conferir planos")
        self.assertNotIn("Conferir planos Contratar", board["storyboard"][3]["cta"])
        origin = board["copy_origin"]["beats"][3]["fields"]
        self.assertEqual(origin["headline"]["source_block"], "price")
        self.assertEqual(origin["cta"]["source_block"], "cta")
        self.assertNotEqual(origin["headline"]["source_block"], origin["cta"]["source_block"])


class CreativeFormatLabStillReadLifecycleTest(unittest.TestCase):
    STILL = "https://cdn.example/tim-black.png"
    OTHER = "https://cdn.example/tim-fit.png"
    BLACK = {
        "headline": "Acesse vantagens exclusivas e um superbônus de internet",
        "support": "até 110GB + bônus para redes sociais",
        "price": "R$ 169,99",
        "cta": "Conferir planos",
        "logo_text": "TIM Black",
    }

    def _lab(self):
        repository = FakeRepository()
        modeling = CreativeModelingService(repository=repository, generator=FakeGenerator())
        return FormatLabService(modeling), repository

    def _session(self, lab, **extra):
        payload = {
            "client_id": 10,
            "campaign_id": 30,
            "format": "video-linear-15",
            "fresh": True,
        }
        payload.update(extra)
        return lab.create_session(payload)

    def _spy(self, ocr_calls, read=None):
        chips = dict(read or self.BLACK)

        def fake(messages, **_k):
            blob = str(messages)
            if "Leia os elementos editáveis deste still." in blob:
                ocr_calls.append(1)
                return {"message": {"content": chips}}
            if "CreativeFormatSpec" in blob:
                return {
                    "message": {
                        "content": {
                            "intent": "create",
                            "format": "video-linear-15",
                            "variant": "A",
                            "adapter": "generic_ctv",
                            "platform_label": "CTV",
                            "brand_name": "TIM",
                            "scenes": [
                                {"id": "scene_01", "purpose": "hook", "headline": "Internet infinita"},
                                {"id": "scene_02", "purpose": "benefit", "headline": "TIM Black"},
                                {"id": "scene_03", "purpose": "proof", "headline": "R$ 99"},
                                {"id": "scene_04", "purpose": "cta", "headline": "TIM Black", "cta": "Saiba mais"},
                            ],
                        }
                    }
                }
            return {"message": {"content": {"passed": True, "score": 0.9, "defects": [], "patches": []}}}

        return fake

    def test_regenerar_reutiliza_a_mesma_leitura(self):
        lab, _repo = self._lab()
        session = self._session(lab)
        calls = []
        first = lab.storyboard(session["id"], {
            "images": [self.STILL],
            "scene_count": 4,
            "text_callable": self._spy(calls),
        })
        self.assertEqual(len(calls), 1)
        self.assertTrue(first["still_read"]["read_id"])
        second = lab.storyboard(session["id"], {
            "images": [self.STILL],
            "scene_count": 4,
            "text_callable": self._spy(calls),
        })
        self.assertEqual(len(calls), 1)
        self.assertEqual(second["still_read"]["read_id"], first["still_read"]["read_id"])
        self.assertTrue(second["still_read"]["reused"])
        self.assertEqual(second["copy_origin"]["read_id"], first["still_read"]["read_id"])

    def test_restaurar_sessao_recupera_vinculo_sem_ocr(self):
        lab, _repo = self._lab()
        session = self._session(lab)
        calls = []
        created = lab.storyboard(session["id"], {
            "images": [self.STILL],
            "scene_count": 4,
            "text_callable": self._spy(calls),
        })
        stored = lab.get_session(session["id"])
        listed = lab.list_sessions({"client_id": 10, "format": "video-linear-15"})
        self.assertEqual(stored["still_read"]["read_id"], created["still_read"]["read_id"])
        self.assertEqual(stored["copy_origin"]["beats"][1]["fields"]["headline"]["text"], self.BLACK["support"])
        self.assertEqual(listed["active"]["still_read"]["read_id"], created["still_read"]["read_id"])
        self.assertEqual(len(calls), 1)

    def test_trocar_still_nao_reusa_leitura_anterior(self):
        lab, _repo = self._lab()
        session = self._session(lab)
        calls = []
        first = lab.storyboard(session["id"], {
            "images": [self.STILL],
            "scene_count": 4,
            "text_callable": self._spy(calls),
        })
        other = dict(self.BLACK, headline="Outro gancho", support="Outro benefício")
        second = lab.storyboard(session["id"], {
            "images": [self.OTHER],
            "scene_count": 4,
            "text_callable": self._spy(calls, other),
        })
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(second["still_read"]["read_id"], first["still_read"]["read_id"])
        self.assertEqual(second["storyboard"][0]["headline"], "Outro gancho")
        stored = lab.get_session(session["id"])
        self.assertEqual(stored["still_read_prev"]["read_id"], first["still_read"]["read_id"])

    def test_releitura_explicita_gera_revisao(self):
        lab, _repo = self._lab()
        session = self._session(lab)
        calls = []
        first = lab.storyboard(session["id"], {
            "images": [self.STILL],
            "scene_count": 4,
            "text_callable": self._spy(calls),
        })
        second = lab.storyboard(session["id"], {
            "images": [self.STILL],
            "scene_count": 4,
            "reread_still": True,
            "text_callable": self._spy(calls),
        })
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(second["still_read"]["read_id"], first["still_read"]["read_id"])
        self.assertEqual(second["still_read"]["revision"], first["still_read"]["revision"] + 1)

    def test_leitura_parcial_preserva_pendencia(self):
        lab, _repo = self._lab()
        session = self._session(lab)
        partial = {"headline": "Acesse vantagens exclusivas", "support": "", "price": "R$ 169,99", "cta": "Conferir planos", "logo_text": "TIM Black"}
        board = lab.storyboard(session["id"], {
            "images": [self.STILL],
            "scene_count": 4,
            "text_callable": self._spy([], partial),
        })
        states = {item["scene_id"]: item["bind_state"] for item in board["copy_bind"]["beats"]}
        self.assertEqual(board["still_read"]["ocr_status"], "partial")
        self.assertEqual(states["scene_02"], "insufficient")
        self.assertTrue(board["copy_origin"]["beats"][1]["fields"]["headline"]["pending"])

    def test_ocr_falhou_nao_repete_sozinho(self):
        lab, _repo = self._lab()
        session = self._session(lab)
        calls = []

        def boom(messages, **_k):
            blob = str(messages)
            if "Leia os elementos editáveis deste still." in blob:
                calls.append(1)
                raise ValueError("ocr down")
            if "CreativeFormatSpec" in blob:
                return {
                    "message": {
                        "content": {
                            "intent": "create",
                            "format": "video-linear-15",
                            "scenes": [
                                {"id": "scene_01", "headline": "A"},
                                {"id": "scene_02", "headline": "B"},
                                {"id": "scene_03", "headline": "C"},
                                {"id": "scene_04", "headline": "D", "cta": "Saiba mais"},
                            ],
                        }
                    }
                }
            return {"message": {"content": {"passed": True, "score": 0.9, "defects": [], "patches": []}}}

        first = lab.storyboard(session["id"], {"images": [self.STILL], "scene_count": 4, "text_callable": boom})
        second = lab.storyboard(session["id"], {"images": [self.STILL], "scene_count": 4, "text_callable": boom})
        self.assertEqual(first["still_read"]["ocr_status"], "failed")
        self.assertEqual(len(calls), 1)
        self.assertTrue(second["still_read"]["reused"])

    def test_read_id_de_outra_sessao_nao_autoriza(self):
        lab, _repo = self._lab()
        first = lab.storyboard(self._session(lab)["id"], {
            "images": [self.STILL],
            "scene_count": 4,
            "text_callable": self._spy([]),
        })
        other = self._session(lab)
        calls = []
        forged = lab.storyboard(other["id"], {
            "images": [self.STILL],
            "scene_count": 4,
            "still_read_id": first["still_read"]["read_id"],
            "still_read": {"chips": {"headline": "Texto de outra sessão"}, "fingerprint": "x"},
            "text_callable": self._spy(calls),
        })
        self.assertNotEqual(forged["still_read"]["read_id"], first["still_read"]["read_id"])
        self.assertNotEqual(forged["storyboard"][0]["headline"], "Texto de outra sessão")
        self.assertEqual(len(calls), 1)

    def test_payload_adulterado_nao_e_autoritativo(self):
        lab, _repo = self._lab()
        session = self._session(lab)
        board = lab.storyboard(session["id"], {
            "scene_count": 4,
            "still_read": dict(self.BLACK),
            "ocr_status": "succeeded",
            "still_fingerprint": "forjado",
        })
        self.assertNotEqual(board["copy_bind"]["ocr_status"], "succeeded")
        self.assertNotIn(self.BLACK["support"], [item["headline"] for item in board["storyboard"]])

    def test_sessao_antiga_nao_declara_heranca(self):
        lab, repo = self._lab()
        session = self._session(lab)
        stored = repo.get_concept_session(session["id"])
        stored["storyboard"] = [{"id": "scene_01", "headline": "Linha antiga", "purpose": "hook"}]
        repo.upsert_concept_session(stored)
        data = lab.get_session(session["id"])
        self.assertFalse((data.get("still_read") or {}).get("read_id"))
        self.assertNotEqual((data.get("copy_origin") or {}).get("ocr_status"), "succeeded")

    def test_campanha_travada_mostra_origem_final(self):
        lab, _repo = self._lab()
        session = self._session(lab, campaign_slug="tim-controle-ctv")
        board = lab.storyboard(session["id"], {
            "campaign_slug": "tim-controle-ctv",
            "images": [self.STILL],
            "scene_count": 4,
            "text_callable": self._spy([]),
        })
        origin = board["copy_origin"]
        self.assertTrue(origin["lock_copy"])
        self.assertEqual(origin["beats"][0]["fields"]["headline"]["origin"], "campaign")
        self.assertTrue(origin["campaign_overrides_still"])
        self.assertIn("O mês acabou", board["storyboard"][0]["headline"])

    def test_estado_persistido_nao_tem_base64(self):
        lab, _repo = self._lab()
        session = self._session(lab)
        png = "data:image/png;base64," + ("A" * 80)
        board = lab.storyboard(session["id"], {
            "images": [self.STILL],
            "key_visuals": {"scene_01": png},
            "scene_count": 4,
            "text_callable": self._spy([]),
        })
        blob = str(board["still_read"]) + str(board["copy_origin"])
        self.assertNotIn("base64", blob)
        self.assertNotIn(png, blob)
        stored = lab.get_session(session["id"])
        self.assertNotIn("base64", str(stored.get("still_read") or {}))


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
            session["trocr_csrf_token"] = "trocr-test-csrf"

    def _trocr_headers(self):
        return {"X-Trocr-CSRF-Token": "trocr-test-csrf"}

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

    def test_listar_sessoes_nao_devolve_500(self):
        service = Mock()
        service.list_format_lab_sessions.side_effect = RuntimeError("undefined table")
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            listed = self.client.get(
                "/parametros/api/format-lab/sessions?client_id=4&format=video-linear-15"
                "&campaign_slug=vivara-presente-ctv"
            )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["data"]["sessions"], [])
        self.assertIsNone(listed.get_json()["data"]["active"])

    def test_criar_sessao_nao_devolve_500(self):
        service = Mock()
        service.create_format_lab_session.side_effect = RuntimeError("column does not exist")
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            created = self.client.post(
                "/parametros/api/format-lab/sessions",
                json={"client_id": 10, "format": "video-linear-15"},
            )
        self.assertEqual(created.status_code, 409)
        self.assertFalse(created.get_json()["success"])
        self.assertIn("sessão", created.get_json()["error"].lower())

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
                headers=self._trocr_headers(),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["headline"], "500 MEGA")
        service.read_format_lab_swap.assert_called_once()

    def test_preview_do_prompt_do_trocar(self):
        service = Mock()
        service.preview_format_lab_swap.return_value = {
            "prompt": "Edit the attached advertising reference.",
            "preview": "Edite o criativo preservando a identidade visual.",
        }
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/format-lab/swap/prompt",
                json={"headline": "TIM ULTRA COMBO", "preserve": ["logo"]},
                headers=self._trocr_headers(),
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("identidade visual", response.get_json()["data"]["preview"])
        service.preview_format_lab_swap.assert_called_once()

    def test_historico_do_trocar(self):
        service = Mock()
        service.load_format_lab_swap_history.return_value = {
            "versions": [{"id": "v1", "image_url": "/static/uploads/creative_generated/a.png"}],
            "active_id": "v1",
        }
        service.save_format_lab_swap_history.return_value = {
            "versions": [{"id": "v1", "image_url": "/static/uploads/creative_generated/a.png"}],
            "active_id": "v1",
        }
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            listed = self.client.get("/parametros/api/format-lab/swap/history?client_id=10")
            saved = self.client.post(
                "/parametros/api/format-lab/swap/history",
                json={"client_id": 10, "versions": [{"id": "v1", "image": "/static/uploads/creative_generated/a.png"}]},
                headers=self._trocr_headers(),
            )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["data"]["active_id"], "v1")
        self.assertEqual(saved.status_code, 200)
        service.load_format_lab_swap_history.assert_called_once()
        service.save_format_lab_swap_history.assert_called_once()

    def test_still_do_trocar_exige_login_e_serve_arquivo(self):
        import tempfile
        from pathlib import Path

        from aicentralv2.creative_modeling_repository import CreativeNotFoundError

        service = Mock()
        service.serve_format_lab_swap_still.side_effect = CreativeNotFoundError(
            "Still do Trocr não encontrado."
        )
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            missing = self.client.get("/parametros/api/format-lab/swap/still/missing.png")
        self.assertEqual(missing.status_code, 404)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ("a" * 32 + ".png")
            path.write_bytes(TINY_PNG)
            service.serve_format_lab_swap_still.side_effect = None
            service.serve_format_lab_swap_still.return_value = path
            with patch(
                "aicentralv2.creative_modeling_routes._service",
                return_value=service,
            ):
                found = self.client.get(f"/parametros/api/format-lab/swap/still/{path.name}")
            self.assertEqual(found.status_code, 200)
            self.assertEqual(found.data, TINY_PNG)
            found.close()
        guest = Flask(__name__)
        guest.config.update(TESTING=True, SECRET_KEY="format-lab-test")
        bp = Blueprint("parametros_format_lab_guest", __name__, url_prefix="/parametros")
        register_creative_modeling_routes(bp)
        guest.register_blueprint(bp)
        anon = guest.test_client()
        blocked = anon.get("/parametros/api/format-lab/swap/still/" + ("b" * 32) + ".png")
        self.assertEqual(blocked.status_code, 401)

    def test_split_camadas_devolve_layers_e_field(self):
        service = Mock()
        service.split_format_lab_layers.return_value = {
            "layers": [
                {
                    "role": "cast",
                    "label": "person",
                    "box": {"x": 50, "y": 0, "w": 50, "h": 100},
                    "png_data_url": "data:image/png;base64,aaa",
                }
            ],
            "field": "#0033FF",
        }
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/format-lab/layers/split",
                json={"image": "data:image/png;base64,aaa"},
            )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["field"], "#0033FF")
        self.assertEqual(data["layers"][0]["role"], "cast")
        service.split_format_lab_layers.assert_called_once()

    def test_rota_split_descarta_injections_do_cliente(self):
        service = Mock()
        service.split_format_lab_layers.return_value = {"layers": [], "field": "#000"}
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.post(
                "/parametros/api/format-lab/layers/split",
                json={
                    "image": "data:image/png;base64,aaa",
                    "predictor": "malicioso",
                    "text_callable": "malicioso",
                    "image_callable": "malicioso",
                    "operation_id": "9",
                },
            )
        self.assertEqual(response.status_code, 200)
        sent = service.split_format_lab_layers.call_args[0][0]
        self.assertNotIn("predictor", sent)
        self.assertNotIn("text_callable", sent)
        self.assertNotIn("image_callable", sent)
        self.assertEqual(sent["operation_id"], "9")

    def test_exemplo_camadas_devolve_still_python(self):
        service = Mock()
        service.example_format_lab_layers.return_value = {
            "image": "data:image/png;base64,aaa",
            "engine": "python",
            "width": 480,
            "height": 180,
        }
        with patch(
            "aicentralv2.creative_modeling_routes._service",
            return_value=service,
        ):
            response = self.client.get("/parametros/api/format-lab/layers/example")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["engine"], "python")
        service.example_format_lab_layers.assert_called_once()
