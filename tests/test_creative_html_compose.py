"""Compositor HTML do Estúdio: filme 16:9 Netflix, sem Chromium."""

import os
import unittest
from unittest.mock import Mock, patch

from aicentralv2.creative_format_compose import compose_native_piece, png_size
from aicentralv2.creative_construct_params import (
    normalize_context_design,
    scene_copy_on_frame,
)
from aicentralv2.creative_html_compose import (
    can_html_compose,
    compose_studio_result,
    render_compose_html,
)
from aicentralv2.creative_modeling_service import CreativeModelingService
from tests.test_modelagem_criativos import FakeStorage


class CreativeHtmlComposeTest(unittest.TestCase):
    def test_flag_so_libera_filme_do_estudio(self):
        with patch.dict(os.environ, {"CREATIVE_HTML_COMPOSE": "1"}):
            self.assertTrue(can_html_compose("sequence_16x9", "model"))
            self.assertFalse(can_html_compose("sequence_16x9", "unfold"))
            self.assertTrue(can_html_compose("square_1x1", "model"))
            self.assertTrue(can_html_compose("half_page", "model"))
            self.assertTrue(can_html_compose("story_9x16", "model"))
            self.assertTrue(can_html_compose("rectangle", "model"))
            self.assertFalse(can_html_compose("portal_unit", "model"))
        with patch.dict(os.environ, {"CREATIVE_HTML_COMPOSE": ""}):
            self.assertTrue(can_html_compose("sequence_16x9", "model"))
        with patch.dict(os.environ, {"CREATIVE_HTML_COMPOSE": "0"}):
            self.assertFalse(can_html_compose("sequence_16x9", "model"))

    def test_template_sequence_injeta_copy_e_logo(self):
        html = render_compose_html(
            {"family": "sequence_16x9", "size": (1920, 1080)},
            {
                "headline": "Oferta TIM",
                "cta": "Ver plano",
                "legal": "Consulte condições",
                "brand_color": "#E50914",
            },
            still_url="data:image/png;base64,c3RpbGw=",
            logo_url="data:image/png;base64,bG9nbw==",
            font_url="data:font/ttf;base64,Zm9udA==",
        )
        self.assertIn('data-family="sequence_16x9"', html)
        self.assertIn("Oferta TIM", html)
        self.assertIn("Ver plano", html)
        self.assertIn("Consulte condições", html)
        self.assertIn("data:image/png;base64,c3RpbGw=", html)
        self.assertIn('class="logo"', html)
        self.assertIn("#E50914", html)

    def test_template_quadrado_respeita_params_do_schema(self):
        html = render_compose_html(
            {"family": "square_1x1", "size": (1080, 1080)},
            {
                "headline": "Oferta TIM",
                "cta": "Assine",
                "brand_color": "#0033A0",
                "compose_params": {
                    "photo_side": "left",
                    "headline_font_size": 30,
                    "cta_gap": 10,
                },
            },
            still_url="data:image/png;base64,c3RpbGw=",
        )
        self.assertIn('data-family="square_1x1"', html)
        self.assertIn('data-photo-side="left"', html)
        self.assertIn("font-size: 30px", html)
        self.assertIn("Oferta TIM", html)
        self.assertIn("Assine", html)

    def test_mapa_extraido_vira_slots_absolutos(self):
        html = render_compose_html(
            {"family": "square_1x1", "size": (1080, 1080)},
            {
                "headline": "Oferta TIM",
                "cta": "Assine",
                "price": "R$ 29",
                "compose_params": {
                    "regions": [
                        {"tipo": "foto_produto", "x": 0, "y": 0, "w": 60, "h": 100},
                        {"tipo": "headline", "x": 62, "y": 20, "w": 36, "h": 20},
                        {"tipo": "cta", "x": 62, "y": 70, "w": 30, "h": 12},
                        {"tipo": "preco", "x": 62, "y": 50, "w": 20, "h": 10},
                    ],
                },
            },
            still_url="data:image/png;base64,c3RpbGw=",
        )
        self.assertIn('data-mapped="1"', html)
        self.assertIn('data-tipo="foto_produto"', html)
        self.assertIn("slot-photo", html)
        self.assertIn("slot-headline", html)
        self.assertIn("slot-cta", html)
        self.assertIn("slot-price", html)
        self.assertIn("left:62.0%;top:20.0%;width:36.0%;height:20.0%;", html)
        self.assertIn("Oferta TIM", html)
        self.assertIn("R$ 29", html)
        self.assertNotIn('data-photo-side=', html)

    def test_iab_e_story_usam_geometria_do_formato(self):
        rectangle = render_compose_html(
            {"family": "rectangle", "size": (300, 250)},
            {"headline": "Oferta", "cta": "Ver"},
            still_url="data:image/png;base64,c3RpbGw=",
        )
        self.assertIn('data-family="rectangle"', rectangle)
        self.assertIn('data-mapped="1"', rectangle)
        self.assertIn("slot-photo", rectangle)
        self.assertIn("Oferta", rectangle)
        story = render_compose_html(
            {"family": "story_9x16", "size": (1080, 1920)},
            {"headline": "Stories", "cta": "Abrir"},
        )
        self.assertIn('data-family="story_9x16"', story)
        self.assertIn("Stories", story)

    def test_sem_browser_cai_no_pillow(self):
        with patch.dict(os.environ, {"CREATIVE_HTML_COMPOSE": "1"}):
            with patch(
                "aicentralv2.creative_html_compose.screenshot_html",
                side_effect=RuntimeError("no chrome"),
            ):
                result = compose_studio_result(
                    b"not-a-png",
                    {"family": "sequence_16x9", "size": (1920, 1080)},
                    {"headline": "Oferta", "cta": "Ver"},
                    None,
                    flow_kind="model",
                )
        self.assertTrue(result["composed"])
        self.assertEqual(result["renderer"], "pillow")
        self.assertEqual(png_size(result["png"]), (1920, 1080))

    def test_estudio_grava_renderer_html_quando_o_screenshot_volta(self):
        png = compose_native_piece(
            b"not-a-png",
            {"family": "sequence_16x9", "size": (1920, 1080)},
            {"headline": "Oferta", "cta": "Ver"},
        )
        service = CreativeModelingService(
            repository=Mock(),
            generator=Mock(),
            storage=FakeStorage(),
        )
        with patch(
            "aicentralv2.creative_modeling_service.compose_studio_result",
            return_value={
                "png": png,
                "composed": True,
                "logo_applied": True,
                "font": "OpenSans-Regular.ttf",
                "require_logo": True,
                "renderer": "html",
                "size": (1920, 1080),
            },
        ) as mocked:
            result = service._compose_native_asset(
                "/still.png",
                "eA==",
                {
                    "campaign_name": "Oferta",
                    "cta_text": "Ver",
                    "creative_brief": {
                        "flow_kind": "model",
                        "construct_path": {"engine": "construct"},
                        "locks": {
                            "headline": "Oferta",
                            "cta": "Ver",
                            "items": {"logo": {"status": "seen"}},
                        },
                    },
                },
                {"family": "sequence_16x9", "size": (1920, 1080)},
                "native",
                engine="construct",
                html_compose=True,
            )
        mocked.assert_called_once()
        self.assertTrue(result["composed"])
        self.assertTrue(result["logo_applied"])
        self.assertEqual(result["renderer"], "html")
        self.assertEqual(result["font"], "OpenSans-Regular.ttf")

    def test_desdobrar_nao_usa_html_mesmo_com_flag(self):
        service = CreativeModelingService(
            repository=Mock(),
            generator=Mock(),
            storage=FakeStorage(),
        )
        with patch.dict(os.environ, {"CREATIVE_HTML_COMPOSE": "1"}):
            with patch(
                "aicentralv2.creative_modeling_service.compose_studio_result"
            ) as mocked:
                result = service._compose_native_asset(
                    "/still.png",
                    "eA==",
                    {
                        "campaign_name": "Oferta",
                        "cta_text": "Ver",
                        "creative_brief": {
                            "flow_kind": "unfold",
                            "construct_path": {"engine": "construct"},
                            "locks": {"headline": "Oferta", "cta": "Ver"},
                        },
                    },
                    {"family": "sequence_16x9", "size": (1920, 1080)},
                    "native",
                    engine="construct",
                    html_compose=False,
                )
        mocked.assert_not_called()
        self.assertTrue(result["composed"])
        self.assertEqual(result.get("renderer"), "pillow")

    def test_context_design_trava_elenco_e_copy_so_no_fechamento(self):
        design = normalize_context_design({
            "cast_count": 2,
            "scenography": "line",
            "scenes": [{"position": 2, "copy_on_frame": True, "set_note": "Sala azul"}],
        }, scene_count=4)
        self.assertEqual(design["cast_count"], 2)
        self.assertTrue(design["cast_lock"])
        self.assertTrue(design["product_lock"])
        self.assertEqual(design["scenography"], "line")
        self.assertFalse(scene_copy_on_frame(design, 1, 4))
        self.assertTrue(scene_copy_on_frame(design, 2, 4))
        self.assertTrue(scene_copy_on_frame(design, 4, 4))
        prompt = CreativeModelingService.build_scene_prompt({
            "position": 1,
            "scene_count": 4,
            "description": "Gancho",
            "campaign_name": "TIM",
            "creative_brief": {"context_design": design},
            "format_slug": "netflix-anuncio-simulado",
        })
        self.assertIn("Cast lock", prompt)
        self.assertIn("Product lock", prompt)
        self.assertIn("Do not paint logos", prompt)
        self.assertIn("Full-bleed photographic still only", prompt)
        self.assertIn("Sala azul", CreativeModelingService.build_scene_prompt({
            "position": 2,
            "scene_count": 4,
            "description": "Contexto",
            "campaign_name": "TIM",
            "creative_brief": {"context_design": design},
            "format_slug": "netflix-anuncio-simulado",
        }))

    def test_sequence_sem_copy_nao_compõe(self):
        service = CreativeModelingService(
            repository=Mock(),
            generator=Mock(),
            storage=FakeStorage(),
        )
        result = service._compose_native_asset(
            "/still.png",
            "eA==",
            {
                "position": 1,
                "scene_count": 4,
                "campaign_name": "Oferta",
                "cta_text": "Ver",
                "creative_brief": {
                    "flow_kind": "model",
                    "construct_path": {"engine": "construct"},
                    "context_design": normalize_context_design({}, 4),
                    "locks": {"headline": "Oferta", "cta": "Ver"},
                },
            },
            {"family": "sequence_16x9", "size": (1920, 1080)},
            "native",
            engine="construct",
            html_compose=True,
        )
        self.assertFalse(result["composed"])
        self.assertEqual(result["asset_url"], "/still.png")


if __name__ == "__main__":
    unittest.main()
