"""Incremento 5: copy por formato e needs_input."""

import unittest

from aicentralv2.design_system_ads.adapt import adapt_system
from aicentralv2.design_system_ads.catalog import inspect_loop
from aicentralv2.design_system_ads.centralcomm import centralcomm_preset
from aicentralv2.design_system_ads.copy import compute_needs_input
from aicentralv2.design_system_ads.materialize import ensure_brand_design_system
from aicentralv2.design_system_ads.prompt_context import build_ads_prompt_context
from aicentralv2.design_system_ads.refine import advance_loop, apply_compose
from aicentralv2.design_system_ads.schema import dump_system, parse_system


class DesignSystemAdsFormatCopyTest(unittest.TestCase):
    def test_mobile_encurta_sem_mudar_default(self):
        data = dump_system(centralcomm_preset())
        data["ad_copy_by_format"] = {
            "iab-mobile": {"headline": "Campanha inteira", "cta": "Começar"}
        }
        system = parse_system(data)
        self.assertEqual(system.ad_copy["headline"], "A campanha chega inteira")
        adapted, stack = adapt_system(system, "iab-mobile", 6)
        self.assertEqual(adapted.ad_copy["headline"], "A campanha chega inteira")
        self.assertEqual(stack["ad_copy"]["headline"], "Campanha inteira")
        self.assertEqual(stack["ad_copy"]["support"], "")

    def test_compose_ignora_ink_e_grava_variante(self):
        system = ensure_brand_design_system(
            {
                "id": 44,
                "name": "Clara",
                "primary_color": "#082C9C",
                "brand_assets": [{"asset_url": "/media/clara-pack.jpg", "role": "packshot"}],
            }
        )
        ink = system.tokens["ink"]
        composed, _ = apply_compose(
            system,
            {
                "ad_copy": {"headline": "Clara no pulso"},
                "ad_copy_by_format": {"iab-mobile": {"headline": "Clara"}},
                "patches": [{"token_id": "ink", "css": "#00FF00", "reason": "troca"}],
            },
        )
        self.assertEqual(composed.tokens["ink"], ink)
        self.assertEqual(composed.ad_copy["headline"], "Clara no pulso")
        self.assertEqual(composed.ad_copy_by_format["iab-mobile"]["headline"], "Clara")

    def test_sem_produto_loop_para_antes_da_imagem(self):
        filled = ensure_brand_design_system(
            {
                "id": 45,
                "name": "Clara",
                "primary_color": "#082C9C",
                "sector": "joalheria",
                "tone_of_voice": "cálida",
            }
        )
        self.assertIn("produto", compute_needs_input(filled))
        _advanced, info, _report = advance_loop(filled)
        self.assertEqual(info["action"], "needs_input")
        self.assertIn("produto", info["needs_input"])
        with_pack = parse_system(
            {
                **dump_system(filled),
                "tracks": [{"id": "packshot", "url": "/media/clara-pack.jpg", "role": "product"}],
            }
        )
        self.assertNotIn("produto", compute_needs_input(with_pack))
        self.assertNotEqual(inspect_loop(with_pack)["action"], "needs_input")
        house = inspect_loop(centralcomm_preset())
        self.assertEqual(house["needs_input"], [])
        self.assertEqual(house["action"], "track")

    def test_prompt_lista_campos_bloqueados(self):
        context = build_ads_prompt_context(
            "compose",
            ensure_brand_design_system({"id": 46, "name": "Nova", "primary_color": "#111111"}),
        )
        ask = context["contract"]["ask"]
        self.assertIn("needs_input", ask)
        self.assertIn("ink", context["contract"]["blocked_fields"])
        self.assertIn("produto", context["user_payload"]["needs_input"])


if __name__ == "__main__":
    unittest.main()
