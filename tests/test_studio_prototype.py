"""Studio: roteiro → refs → cenas HTML → Seedance. Sem Trocr."""

import unittest
from types import SimpleNamespace

from aicentralv2.creative_format_lab.campaign_models import load_campaign_model
from aicentralv2.creative_format_lab.catalog import (
    clamp_scene_count,
    composition_purposes,
    format_entry,
    is_ctv_format,
    last_scene_id,
    toggles_for_purpose,
)
from aicentralv2.creative_format_lab.prototype import (
    SEEDANCE_MODEL,
    SEEDANCE_PROMPT,
    animate_spec,
    build_script,
    compose_scenes,
    infer_persona,
    quote_prototype,
    video_payload,
)
from aicentralv2.creative_format_lab.refine import refine_image_prompt, refine_script
from aicentralv2.creative_format_lab.service import FormatLabService


class StudioPrototypeTest(unittest.TestCase):
    def test_ctv_g1_catalog_e_cta_instrucao(self):
        entry = format_entry("video-linear-15")
        self.assertEqual(entry["canvas"], {"width": 1920, "height": 1080})
        self.assertEqual(entry["duration"], 15)
        self.assertEqual(entry["aspect_ratio"], "16:9")
        self.assertTrue(is_ctv_format("video-linear-15"))
        recipe = toggles_for_purpose("cta", format_key="video-linear-15")
        self.assertTrue(recipe["cta"])
        self.assertEqual(recipe["cta_kind"], "instruction")
        model = load_campaign_model("g1-ctv")
        self.assertEqual(model["format"], "video-linear-15")
        self.assertEqual(model["cta"], "Procure na loja")
        self.assertEqual([item["purpose"] for item in model["scenes"]], [
            "brand", "product", "lifestyle", "cta",
        ])

    def test_composition_4_e_6(self):
        self.assertEqual(clamp_scene_count(4), 4)
        self.assertEqual(clamp_scene_count(6), 6)
        self.assertEqual(
            composition_purposes("C", 4),
            ["brand", "product", "lifestyle", "cta"],
        )
        self.assertEqual(
            composition_purposes("C", 6),
            ["brand", "product", "lifestyle", "proof", "experience", "cta"],
        )
        self.assertEqual(last_scene_id(4), "scene_04")
        self.assertEqual(last_scene_id(6), "scene_06")

    def test_early_exit_quando_critica_nao_acha_problema(self):
        v1 = [{"id": "scene_01", "purpose": "brand", "headline": "Ok"}]

        def critic(_messages, **_kwargs):
            return {"message": {"content": {"problems": [], "storyboard": v1}}}

        packed = refine_script(v1, text_callable=critic)
        self.assertTrue(packed["early_exit"])
        self.assertEqual(packed["selected"], "v3")
        self.assertEqual(packed["v3"]["storyboard"], v1)

    def test_roteiro_fallback_g1_sem_llm(self):
        brand = {
            "name": "G1",
            "target_audience": "Adulto em casa, sofá",
            "forbidden_elements": ["saiba mais"],
        }
        result = build_script(
            {
                "format_key": "video-linear-15",
                "scene_count": 4,
                "variant": "C",
                "cta": "Procure na loja",
                "offer": "O que importa, no ar, na hora.",
            },
            brand=brand,
            text_callable=None,
        )
        self.assertEqual(len(result["storyboard"]), 4)
        self.assertEqual(result["storyboard"][-1]["purpose"], "cta")
        self.assertEqual(result["storyboard"][-1]["cta"], "Procure na loja")
        self.assertEqual(result["persona"]["elenco"], "1 pessoa")

    def test_cenas_g1_html_cta_nao_e_botao(self):
        model = load_campaign_model("g1-ctv")
        built = compose_scenes(
            {
                "format_key": "video-linear-15",
                "scene_count": 4,
                "variant": "C",
                "storyboard": model["scenes"],
            },
            brand={"name": "G1", "primary_color": "#C4170C", "logo_url": ""},
        )
        self.assertEqual(built["canvas"]["width"], 1920)
        self.assertEqual(built["safe_area"], 0.9)
        last = built["scenes"][-1]
        self.assertEqual(last["purpose"], "cta")
        self.assertEqual(last["cta_kind"], "instruction")
        self.assertIn("background:transparent", last["html"])
        self.assertNotIn("swap.py", last["html"])
        stack_cta = next(item for item in last["stack"]["layers"] if item["role"] == "cta")
        self.assertEqual(stack_cta["tipo"], "instruction")
        self.assertIn("scene_image", last)

    def test_quote_e_video_seedance(self):
        quote = quote_prototype({"need_cast": True, "fundo": "lavagem", "video": True})
        self.assertGreater(quote["estimated_cost_usd"], 0.4)
        self.assertEqual(quote["line"]["display_css"], 0)
        plan = video_payload({
            "format_key": "video-linear-15",
            "resolution": "720p",
            "scenes": [
                {"id": "scene_01", "render_url": "https://example.com/a.png"},
                {"id": "scene_04", "render_url": "https://example.com/b.png"},
            ],
        })
        self.assertEqual(plan["model"], SEEDANCE_MODEL)
        self.assertEqual(plan["duration"], 5)
        self.assertFalse(plan["generate_audio"])
        self.assertIn("Gentle camera", SEEDANCE_PROMPT)
        self.assertEqual(len(plan["frame_images"]), 2)
        self.assertEqual(plan["frame_images"][0]["frame_type"], "first_frame")

    def test_animate_css_custa_zero(self):
        spec = animate_spec({
            "format_key": "video-linear-15",
            "seconds": 5,
            "scenes": [{"id": "scene_01"}, {"id": "scene_02"}],
        })
        self.assertEqual(spec["mode"], "css")
        self.assertEqual(spec["cost_usd"], 0)
        self.assertEqual(len(spec["timeline"]), 2)

    def test_prompt_imagem_early_exit(self):
        def critic(_messages, **_kwargs):
            return {"message": {"content": {"problems": [], "prompt": "keep this"}}}

        packed = refine_image_prompt("draft prompt", text_callable=critic)
        self.assertTrue(packed["early_exit"])
        self.assertEqual(packed["v3"]["prompt"], "keep this")

    def test_g1_campaign_slug_preenche_cta_sem_cliente(self):
        lab = FormatLabService(SimpleNamespace(repository=None, generator=None))
        result = lab.prototype_script({"campaign_slug": "g1-ctv", "text_callable": None})
        self.assertEqual(result["format_key"], "video-linear-15")
        self.assertEqual(result["variant"], "C")
        self.assertEqual(result["storyboard"][-1]["cta"], "Procure na loja")
        self.assertEqual(result["persona"]["elenco"], "1 pessoa")

    def test_video_submit_false_nao_chama_provedor(self):
        lab = FormatLabService(SimpleNamespace(repository=None))
        result = lab.prototype_video({
            "submit": False,
            "format_key": "video-linear-15",
            "scenes": [{"render_url": "https://example.com/a.png"}],
        })
        self.assertEqual(result["model"], SEEDANCE_MODEL)
        self.assertNotIn("job", result)


if __name__ == "__main__":
    unittest.main()
