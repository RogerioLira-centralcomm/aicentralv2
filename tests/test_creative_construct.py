"""Caminho C do desdobrador: itens do KV, cenas e custo previsto."""

import unittest

from aicentralv2.creative_construct_params import (
    ENGINE_CONSTRUCT,
    ENGINE_PAINT,
    locks_from_kv_items,
    normalize_kv_items,
    quote_unfold_path,
    resolve_construct_path,
    scene_key_for_slug,
    unique_scenes_for_slugs,
)
from aicentralv2.creative_format_geometry import should_compose
from aicentralv2.creative_modeling_prompts import (
    apply_render_mode_to_prompt,
    normalize_locks,
    paints_full_copy,
)
from aicentralv2.creative_modeling_fx import reset_rate_cache


class CreativeConstructPathTest(unittest.TestCase):
    def setUp(self):
        reset_rate_cache()
        import os
        os.environ.setdefault("USD_BRL_RATE", "5.5")

    def test_pack_6_agrupa_redes_e_reusa_mobile_no_wide(self):
        slugs = [
            "instagram-feed",
            "facebook-feed",
            "instagram-story",
            "tiktok-vertical",
            "linkedin-share",
            "iab-half-page",
            "iab-medium-rectangle",
            "iab-leaderboard",
            "iab-mobile-banner",
        ]
        self.assertEqual(scene_key_for_slug("facebook-feed", 6), "square")
        self.assertEqual(scene_key_for_slug("tiktok-vertical", 6), "story")
        self.assertEqual(scene_key_for_slug("iab-mobile-banner", 6), "wide")
        self.assertEqual(len(unique_scenes_for_slugs(slugs, 6)), 6)
        self.assertEqual(scene_key_for_slug("iab-mobile-banner", 8), "mobile")

    def test_quote_c_cobra_cenas_e_a_cobra_pecas(self):
        slugs = ["instagram-feed", "facebook-feed", "instagram-story"]
        construct = quote_unfold_path(
            {
                "engine": "construct",
                "scene_pack": 6,
                "image_model": "black-forest-labs/flux.2-pro",
            },
            slugs,
        )
        paint = quote_unfold_path(
            {
                "engine": "paint",
                "image_model": "openai/gpt-image-2",
                "fidelity": "draft",
            },
            slugs,
        )
        self.assertEqual(construct["engine"], ENGINE_CONSTRUCT)
        self.assertEqual(construct["photo_calls"], 2)
        self.assertEqual(construct["shared_pieces"], 1)
        self.assertEqual(construct["pieces"], 3)
        self.assertGreater(construct["total_brl"], 0)
        self.assertEqual(paint["engine"], ENGINE_PAINT)
        self.assertEqual(paint["photo_calls"], 3)
        self.assertLess(paint["total_usd"], construct["total_usd"])

    def test_caminho_c_nao_pinta_copy_e_compõe_social(self):
        self.assertFalse(paints_full_copy("square_1x1", "unfold", "construct"))
        self.assertTrue(paints_full_copy("square_1x1", "unfold", "paint"))
        self.assertTrue(should_compose("square_1x1", "native", engine="construct"))
        self.assertFalse(should_compose("square_1x1", "native"))
        prompt = apply_render_mode_to_prompt(
            "Base",
            "native",
            {"family": "square_1x1", "size": (1080, 1080)},
            {"headline": "Oferta", "cta": "Ver"},
            flow_kind="unfold",
            locks={"headline": "Oferta", "cta": "Ver"},
            engine="construct",
        )
        self.assertIn("NATIVE ADVERTISING STILL", prompt)
        self.assertNotIn("COMPLETE SOCIAL ADVERTISEMENT", prompt)

    def test_itens_do_kv_nao_inventam_cta(self):
        items = normalize_kv_items({
            "headline": "Aproveite muita internet",
            "has_logo": True,
            "items": {
                "logo": {"text": "TIM", "status": "seen"},
                "product_lockup": {"text": "TIM BLACK FAMÍLIA", "status": "seen"},
                "cta": {"text": "", "status": "absent"},
            },
        })
        self.assertEqual(items["cta"]["status"], "absent")
        self.assertEqual(items["logo"]["status"], "seen")
        locks = normalize_locks({
            "headline": "Coleção Outono",
            "cta": "Conheça a coleção",
            "has_logo": True,
        })
        self.assertEqual(locks["headline"], "Coleção Outono")
        self.assertEqual(locks["cta"], "Conheça a coleção")
        self.assertIn("items", locks)
        merged = locks_from_kv_items(items)
        self.assertEqual(merged["headline"], "Aproveite muita internet")
        self.assertEqual(merged["cta"], "")

    def test_resolve_path_c_usa_flux_e_publish(self):
        path = resolve_construct_path({"engine": "c"})
        self.assertEqual(path["engine"], ENGINE_CONSTRUCT)
        self.assertEqual(path["image_model"], "black-forest-labs/flux.2-pro")
        self.assertEqual(path["fidelity"], "publish")
        self.assertEqual(path["scene_pack"], 6)


if __name__ == "__main__":
    unittest.main()
