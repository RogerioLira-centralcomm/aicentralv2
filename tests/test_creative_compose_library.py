"""Biblioteca viva do Estúdio: schema, promoção e loop de aprovação."""

import unittest
from unittest.mock import Mock

from aicentralv2.creative_compose_library import (
    apply_script_params,
    clamp_params,
    LAYOUT_SQUARE_SCHEMA,
    next_variation_status,
    normalize_compose_choice,
    propose_variation_adjust,
    SCRIPT_SEQUENCE_SCHEMA,
    suggest_variation,
    tokens_from_brand_profile,
)
from aicentralv2.creative_modeling_service import CreativeModelingService
from tests.test_modelagem_criativos import FakeGenerator, FakeStorage


class CreativeComposeLibraryTest(unittest.TestCase):
    def test_clamp_respeita_min_max_step_e_enum(self):
        params = clamp_params(
            LAYOUT_SQUARE_SCHEMA,
            {
                "headline_font_size": 99,
                "photo_side": "up",
                "cta_gap": 3,
            },
        )
        self.assertEqual(params["headline_font_size"], 32)
        self.assertEqual(params["photo_side"], "left")
        self.assertEqual(params["cta_gap"], 8)

    def test_promocao_e_arquivo_pelos_cliques(self):
        self.assertEqual(next_variation_status(3, 0, "experimental"), "approved")
        self.assertEqual(next_variation_status(3, 2, "experimental"), "approved")
        self.assertEqual(next_variation_status(0, 3, "experimental"), "archived")
        self.assertEqual(next_variation_status(2, 1, "experimental"), "experimental")
        self.assertEqual(next_variation_status(9, 1, "archived"), "archived")

    def test_ajuste_so_caminha_dentro_do_schema(self):
        nxt = propose_variation_adjust(
            LAYOUT_SQUARE_SCHEMA,
            {"headline_font_size": 26, "photo_side": "right", "cta_gap": 12},
        )
        self.assertEqual(nxt["photo_side"], "left")
        self.assertIn(nxt["headline_font_size"], range(22, 33, 2))
        self.assertIn(nxt["cta_gap"], range(8, 17))

    def test_roteiro_trava_copy_no_fechamento(self):
        design = apply_script_params(
            {},
            {"scenography": "change", "cast_count": 2, "copy_on_last_only": True},
            4,
        )
        self.assertEqual(design["scenography"], "change")
        self.assertEqual(design["cast_count"], 2)
        self.assertFalse(design["scenes"][0]["copy_on_frame"])
        self.assertTrue(design["scenes"][-1]["copy_on_frame"])

    def test_sugestao_prioriza_aprovada(self):
        picked = suggest_variation([
            {
                "id": 1,
                "family": "square_1x1",
                "status": "experimental",
                "approve_count": 9,
            },
            {
                "id": 2,
                "family": "square_1x1",
                "status": "approved",
                "approve_count": 3,
            },
            {
                "id": 3,
                "family": "square_1x1",
                "status": "archived",
                "approve_count": 20,
            },
        ], "square_1x1")
        self.assertEqual(picked["id"], 2)

    def test_tokens_saem_do_brand_profile(self):
        tokens = tokens_from_brand_profile({
            "creative_line": {
                "color_palette": [{"hex": "#0033A0"}, "#FFFFFF"],
            }
        })
        self.assertEqual(tokens["palette"][0], "#0033A0")

    def test_plano_anexa_variacao_do_feed_quadrado(self):
        repository = Mock()
        repository.get_format.return_value = {
            "id": 9,
            "slug": "instagram-feed",
            "mechanic": "static_display",
            "behavior_spec": {"type": "static"},
            "default_size": "1080x1080",
        }
        repository.create_campaign_with_productions.return_value = {
            "id": 40,
            "productions": [{"id": 60}],
        }
        repository.get_campaign.return_value = {"id": 40, "name": "Feed"}
        repository.get_production.return_value = {
            "id": 60,
            "scene_count": 1,
            "scenes": [{"id": 1}],
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        service.create_production_plan({
            "name": "Feed",
            "productions": [{"format_template_id": 9, "scene_descriptions": ["Peça"]}],
        })
        saved = repository.create_campaign_with_productions.call_args.args[0]
        choice = saved["creative_brief"]["compose_library"]
        self.assertEqual(choice["family"], "square_1x1")
        self.assertEqual(choice["kind"], "layout")
        self.assertEqual(choice["params"]["photo_side"], "right")
        self.assertIn(choice["params"]["headline_font_size"], range(22, 33, 2))

    def test_plano_roteiro_aplica_params_quando_nao_vem_contexto(self):
        repository = Mock()
        repository.get_format.return_value = {
            "id": 3,
            "slug": "netflix-anuncio-simulado",
            "default_size": "1920x1080",
        }
        repository.create_campaign_with_productions.return_value = {
            "id": 41,
            "productions": [{"id": 61}],
        }
        repository.get_campaign.return_value = {"id": 41, "name": "Netflix"}
        repository.get_production.return_value = {
            "id": 61,
            "scene_count": 4,
            "scenes": [{"id": index} for index in range(1, 5)],
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        service.create_production_plan({
            "name": "Netflix",
            "variation_id": "seed-sequence-line",
            "productions": [{
                "format_template_id": 3,
                "scene_descriptions": ["A", "B", "C", "D"],
            }],
        })
        saved = repository.create_campaign_with_productions.call_args.args[0]
        brief = saved["creative_brief"]
        self.assertEqual(brief["compose_library"]["kind"], "script")
        self.assertFalse(brief["context_design"]["scenes"][0]["copy_on_frame"])
        self.assertTrue(brief["context_design"]["scenes"][-1]["copy_on_frame"])

    def test_aprovar_peca_alimenta_variacao_persistida(self):
        repository = Mock()
        repository.review_scene_asset.return_value = {"status": "approved"}
        repository.get_scene_context.return_value = {
            "campaign_id": 8,
            "creative_brief": {
                "flow_kind": "model",
                "compose_library": {
                    "variation_id": 15,
                    "template_id": 2,
                    "family": "square_1x1",
                    "params": {"photo_side": "right"},
                },
            },
        }
        repository.record_compose_feedback.return_value = {
            "id": 15,
            "template_id": 2,
            "status": "experimental",
            "params": {"photo_side": "right"},
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        service.review_scene(3, {"status": "approved", "asset_id": 99})
        repository.record_compose_feedback.assert_called_once_with(
            15, 8, 99, "approved"
        )
        repository.create_compose_variation.assert_not_called()

    def test_rejeitar_cria_irma_experimental(self):
        repository = Mock()
        repository.review_scene_asset.return_value = {"status": "rejected"}
        repository.get_scene_context.return_value = {
            "campaign_id": 8,
            "creative_brief": {
                "flow_kind": "model",
                "compose_library": {
                    "variation_id": 15,
                    "template_id": 2,
                    "family": "square_1x1",
                    "params": {
                        "headline_font_size": 26,
                        "photo_side": "right",
                        "cta_gap": 12,
                    },
                },
            },
        }
        repository.record_compose_feedback.return_value = {
            "id": 15,
            "template_id": 2,
            "status": "experimental",
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        service.review_scene(3, {"status": "rejected", "asset_id": 99})
        repository.create_compose_variation.assert_called_once()
        args = repository.create_compose_variation.call_args.args
        self.assertEqual(args[0], 2)
        self.assertEqual(args[3], "experimental")
        self.assertEqual(args[2]["photo_side"], "left")

    def test_desdobrar_nao_grava_biblioteca(self):
        repository = Mock()
        repository.review_scene_asset.return_value = {"status": "approved"}
        repository.get_scene_context.return_value = {
            "campaign_id": 8,
            "creative_brief": {
                "flow_kind": "unfold",
                "compose_library": {"variation_id": 15},
            },
        }
        service = CreativeModelingService(
            repository=repository,
            generator=FakeGenerator(),
            storage=FakeStorage(),
        )
        service.review_scene(3, {"status": "approved", "asset_id": 99})
        repository.record_compose_feedback.assert_not_called()

    def test_choice_normaliza_params_invalidos(self):
        choice = normalize_compose_choice({
            "id": "seed-square-right",
            "family": "square_1x1",
            "params": {"headline_font_size": 11, "photo_side": "diagonal"},
        })
        self.assertEqual(choice["params"]["headline_font_size"], 22)
        self.assertEqual(choice["params"]["photo_side"], "left")


if __name__ == "__main__":
    unittest.main()
