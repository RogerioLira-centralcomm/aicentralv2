"""Pipeline de treinamento, placeholder, assets e revisões."""

from unittest import TestCase

from aicentralv2.creative_modeling_prompts import compose_format_mockup_prompt
from aicentralv2.creative_format_assets import resolve_assets
from aicentralv2.creative_format_placeholder import render_placeholder
from aicentralv2.creative_format_registry import FORMATS
from aicentralv2.format_lab_agents import run_training
from aicentralv2.format_lab_reviews import (
    approve_revision,
    clone_approved,
    create_revision,
    list_revisions,
)


class FormatLabAgentsTest(TestCase):
    def test_placeholder_para_toda_a_base(self):
        for item in FORMATS:
            result = render_placeholder(item["format_key"])
            self.assertEqual(result["status"], "ok", item["format_key"])
            self.assertIn("Placeholder de formato", result["html"])
            self.assertIn(str(item["width"]), result["html"])
            self.assertIn("cx-format-ph-box", result["html"])

    def test_resolver_cai_no_placeholder(self):
        result = resolve_assets({"format_key": "iab-medium"})
        self.assertEqual(result["source_type"], "smart_placeholder")
        self.assertEqual(result["public_label"], "Placeholder de formato")
        self.assertFalse(result.get("brand_invented", False))

    def test_resolver_usa_criativo_aprovado(self):
        result = resolve_assets({
            "format_key": "iab-medium",
            "approved_creative": {
                "url": "/x.png", "width": 300, "height": 250,
            },
        })
        self.assertEqual(result["source_type"], "client_creative")
        self.assertEqual(result["public_label"], "Criativo fornecido pelo cliente")

    def test_treino_ok_para_medium_no_portal(self):
        result = run_training({
            "format_key": "iab-medium-rectangle",
            "channel": "portal",
            "device": "desktop",
            "zone": "in_feed",
        })
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["format_key"], "iab-medium")
        self.assertEqual(result["path"], "C")
        self.assertEqual(result["steps"]["placement"]["zone"], "in_feed")
        self.assertEqual(result["steps"]["viewer"]["viewer_type"], "portal")
        self.assertIn("scores", result["steps"]["quality"])

    def test_treino_bloqueia_social_no_portal(self):
        result = run_training({
            "format_key": "feed-1x1",
            "channel": "portal",
            "zone": "in_feed",
        })
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocked"]["code"], "PLACEMENT_INCOMPATIBLE")

    def test_revisao_aprovada_nao_e_sobrescrita(self):
        create_revision("var-1", {"format_key": "iab-medium"}, 1)
        approve_revision("var-1", 1)
        again = create_revision("var-1", {"format_key": "iab-billboard"}, 2)
        self.assertEqual(again["status"], "approved")
        self.assertEqual(again["revision"], 1)
        self.assertEqual(clone_approved("var-1")["revision"], 1)
        self.assertEqual(len(list_revisions("var-1")), 1)

    def test_mock_rapido_nao_pinta_copy_na_imagem(self):
        prompt = compose_format_mockup_prompt(
            {
                "name_pt": "Medium",
                "mechanic": "static",
                "placement_spec": {
                    "context": "portal",
                    "viewport": {"width": 1280, "height": 800},
                    "slot": {"x": 8, "y": 38, "width": 54, "height": 28},
                },
            }
        )
        self.assertIn("Do not paint words", prompt)
        self.assertIn("proof of concept", prompt)
