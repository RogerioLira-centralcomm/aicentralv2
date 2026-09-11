"""Design System Ads: contrato, CentralComm, loop e rotas de specimen."""

import unittest
from pathlib import Path

from flask import Flask

from aicentralv2.creative_format_lab.brand_context import build_brand_context
from aicentralv2.creative_modeling_routes import register_modeling_ux_lab
from aicentralv2.design_system_ads.centralcomm import (
    CENTRALCOMM_TOKENS,
    centralcomm_preset,
    is_centralcomm_client,
)
from aicentralv2.design_system_ads.materialize import ensure_brand_design_system
from aicentralv2.design_system_ads.refine import (
    apply_token_patches,
    clamp_passes,
    heal_contrast,
    refine_design_system,
)
from aicentralv2.design_system_ads.render import render_specimen, table_html, tailwind_theme
from aicentralv2.design_system_ads.schema import MIN_CONTRAST, contrast_ratio, dump_system
from aicentralv2.design_system_ads.service import payload_for, read_preset


class DesignSystemAdsContractTest(unittest.TestCase):
    def test_centralcomm_nasce_do_tailwind(self):
        system = centralcomm_preset()
        self.assertEqual(system.tokens["ink"], CENTRALCOMM_TOKENS["ink"])
        self.assertEqual(system.tokens["highlight"], "#F3B71B")
        self.assertEqual(system.tokens["font-display"], "Inter")
        self.assertGreaterEqual(system.contrast["pairs"]["ink_on_paper"], MIN_CONTRAST)
        self.assertGreaterEqual(system.contrast["pairs"]["cta_on_accent"], MIN_CONTRAST)
        self.assertTrue(is_centralcomm_client({"name": "CentralComm"}))

    def test_tabela_e_tema_tailwind(self):
        html = table_html(centralcomm_preset())
        self.assertIn("<table", html)
        self.assertIn("--dsa-ink", html)
        self.assertIn("bg-dsa-paper", html)
        theme = tailwind_theme(centralcomm_preset())
        self.assertEqual(theme["base"], "tailwind")
        self.assertIn("dsa", theme["theme"]["extend"]["colors"])

    def test_materializa_marca_sem_llm(self):
        system = ensure_brand_design_system(
            {
                "id": 9,
                "name": "Marca Nova",
                "primary_color": "#123456",
                "logo_url": "/static/images/cc_logo.png",
                "brand_profile": {"fonts": [{"family": "Manrope", "role": "display"}]},
            }
        )
        self.assertEqual(system.tokens["ink"], "#123456")
        self.assertEqual(system.tokens["font-display"], "Manrope")
        self.assertTrue(system.name.startswith("Marca Nova"))

    def test_reusa_sistema_ja_gravado(self):
        stored = dump_system(centralcomm_preset(client_id=3))
        again = ensure_brand_design_system(
            {"id": 3, "name": "Outra", "brand_profile": {"design_system_ads": stored}}
        )
        self.assertEqual(again.id, stored["id"])

    def test_centralcomm_cliente_usa_preset(self):
        system = ensure_brand_design_system({"id": 12, "name": "CentralComm"})
        self.assertEqual(system.source, "tailwind-centralcomm")
        self.assertEqual(system.tokens["ink"], "#1E4D4F")

    def test_heal_e_patch(self):
        weak = ensure_brand_design_system(
            {"id": 1, "name": "Clara", "primary_color": "#F3B71B"}
        )
        healed, patches = heal_contrast(weak)
        self.assertTrue(healed.contrast["passed"] or patches)
        patched, applied = apply_token_patches(
            healed, [{"token_id": "cta", "css": "Comprar agora"}]
        )
        self.assertEqual(applied, [])
        patched, applied = apply_token_patches(
            healed, [{"token_id": "ink", "css": "#153638", "reason": "Mais escuro"}]
        )
        self.assertEqual(patched.tokens["ink"], "#153638")
        self.assertEqual(applied[0]["token_id"], "ink")

    def test_loop_para_em_4_e_cedo_se_passou(self):
        self.assertEqual(clamp_passes(9), 4)
        self.assertEqual(clamp_passes("x"), 1)
        system, reports = refine_design_system(centralcomm_preset(), attempts=4)
        self.assertLessEqual(len(system.passes), 4)
        self.assertTrue(reports)
        self.assertTrue(system.contrast["passed"])

        calls = []

        def text_callable(messages, **kwargs):
            calls.append(1)
            return {
                "message": {
                    "content": {
                        "passed": True,
                        "score": 0.95,
                        "defects": [],
                        "notes": ["ok"],
                        "patches": [],
                    }
                }
            }

        weak = ensure_brand_design_system(
            {"id": 2, "name": "Clara", "primary_color": "#EEEEEE"}
        )
        refined, reports = refine_design_system(
            weak, attempts=4, text_callable=text_callable
        )
        self.assertLessEqual(len(calls), 3)
        self.assertLessEqual(len(refined.passes), 4)
        self.assertTrue(any(item.passed for item in reports))

    def test_specimen_centralcomm(self):
        html = render_specimen(read_preset(), standalone=True)
        self.assertIn("cdn.tailwindcss.com", html)
        self.assertIn("--dsa-ink", html)
        self.assertIn("A peça na tinta certa", html)
        self.assertIn("/static/images/cc_logo.png", html)
        payload = payload_for(centralcomm_preset())
        self.assertIn("/lab/design-system/marca/", payload["specimen_url"])

    def test_brand_context_expoe_ds(self):
        context = build_brand_context(
            {
                "name": "Marca",
                "brand_profile": {
                    "design_system_ads": dump_system(centralcomm_preset())
                },
            }
        )
        self.assertEqual(context["design_system_ads"]["framework"], "design-system-ads")

    def test_rota_specimen_registrada(self):
        from flask import Blueprint, url_for

        from aicentralv2.creative_modeling_routes import register_creative_modeling_routes

        app = Flask(__name__)
        register_modeling_ux_lab(app)
        blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
        register_creative_modeling_routes(blueprint)
        app.register_blueprint(blueprint)
        self.assertIn(
            "/lab/design-system/marca/<client_id>",
            [rule.rule for rule in app.url_map.iter_rules()],
        )
        self.assertIn(
            "/lab/design-system/campanha/<campaign_id>",
            [rule.rule for rule in app.url_map.iter_rules()],
        )
        with app.test_request_context():
            self.assertEqual(
                url_for("parametros.modelagem_design-system"),
                "/parametros/modelagem-criativos/design-system",
            )


class DesignSystemAdsAdaptTest(unittest.TestCase):
    def test_iab_e_camadas_4_a_40(self):
        from aicentralv2.design_system_ads.adapt import (
            adapt_system,
            clamp_layer_count,
            list_iab_formats,
            swap_layer_positions,
        )

        keys = {item["key"] for item in list_iab_formats()}
        self.assertIn("iab-billboard", keys)
        self.assertIn("iab-leaderboard", keys)
        self.assertIn("iab-mobile", keys)
        self.assertEqual(clamp_layer_count(2), 4)
        self.assertEqual(clamp_layer_count(80), 40)
        adapted, stack = adapt_system(centralcomm_preset(), "iab-leaderboard", 8)
        self.assertEqual(stack["layer_count"], 8)
        self.assertEqual(len(stack["layers"]), 8)
        self.assertLess(int(adapted.tokens["type-headline"].replace("px", "")), 72)
        copy = [item for item in stack["layers"] if item["role"] in {"logo", "headline", "cta"}]
        self.assertTrue(copy)
        self.assertGreaterEqual(copy[0]["x"], stack["safe"]["x"] - 0.01)
        logo = next(item for item in stack["layers"] if item["role"] == "logo")
        cta = next(item for item in stack["layers"] if item["role"] == "cta")
        swapped = swap_layer_positions(stack, logo["id"], cta["id"])
        new_logo = next(item for item in swapped["layers"] if item["role"] == "logo")
        self.assertEqual(new_logo["x"], cta["x"])
        _, packed = adapt_system(centralcomm_preset(), "iab-medium", 40)
        self.assertEqual(len(packed["layers"]), 40)

    def test_receitas_iab_ficam_perfeitas(self):
        from aicentralv2.design_system_ads.adapt import adapt_system
        from aicentralv2.design_system_ads.layouts import validate_stack
        from aicentralv2.design_system_ads.render import render_specimen

        keys = (
            "iab-billboard",
            "iab-leaderboard",
            "iab-medium",
            "iab-halfpage",
            "iab-skyscraper",
            "iab-mobile",
        )
        for key in keys:
            for count in (4, 8, 40):
                adapted, stack = adapt_system(centralcomm_preset(), key, count)
                issues = validate_stack(stack)
                self.assertEqual(issues, [], f"{key} × {count}: {issues}")
                self.assertEqual(len(stack["layers"]), count)
                cta = next(item for item in stack["layers"] if item["role"] == "cta")
                height = stack["format"]["height"]
                self.assertGreaterEqual(height * cta["h"] / 100, 28)
                html = render_specimen(adapted, standalone=True, stack=stack)
                self.assertIn("dsa-ad-stage", html)
                self.assertNotIn("dsa-ad-chip", html)
                if key in {"iab-leaderboard", "iab-mobile"}:
                    self.assertIn("is-thin", html)
                    self.assertNotIn("dsa-ad-support'>", html)

    def test_branco_vira_transparente(self):
        from PIL import Image

        from aicentralv2.design_system_ads.cutouts import (
            paint_white_background,
            white_to_transparent,
        )

        image = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
        image.putpixel((3, 3), (30, 80, 80, 255))
        cut = white_to_transparent(paint_white_background(image))
        self.assertEqual(cut.getpixel((0, 0))[3], 0)
        self.assertEqual(cut.getpixel((3, 3))[3], 255)

    def test_campanha_herda_marca(self):
        from aicentralv2.design_system_ads.campaign import ensure_campaign_design_system

        system, elements = ensure_campaign_design_system(
            centralcomm_preset(),
            {"id": 9, "name": "Verao", "cta_text": "Reservar"},
            [{"asset_url": "/static/a.png", "role": "product"}] * 3,
        )
        self.assertEqual(system.scope, "campaign")
        self.assertEqual(system.tokens["ink"], "#1E4D4F")
        self.assertEqual(len(elements), 3)
        self.assertEqual(system.ad_copy["cta"], "Reservar")
        self.assertEqual(system.inherits_brand_id, centralcomm_preset().id)
        self.assertEqual(system.creative_line, "")

        from aicentralv2.design_system_ads.adapt import adapt_system
        from aicentralv2.design_system_ads.campaign import (
            CENTRALCOMM_CAMPAIGN_SLUG,
            classify_role,
            layer_count_from_elements,
        )
        from aicentralv2.design_system_ads.render import render_specimen
        from aicentralv2.design_system_ads.service import read_campaign_preset

        self.assertEqual(classify_role({"title": "produto verao"}, 1), "product")
        self.assertEqual(layer_count_from_elements(elements), 6)
        adapted, stack = adapt_system(system, "iab-medium", 8)
        self.assertEqual(adapted.ad_copy["cta"], "Reservar")
        visual = next(item for item in stack["layers"] if item["role"] == "visual")
        self.assertEqual(visual.get("asset_url"), "/static/a.png")
        html = render_specimen(adapted, standalone=True, stack=stack)
        self.assertIn("dsa-cutout", html)
        self.assertIn("/static/a.png", html)
        preset = read_campaign_preset()
        self.assertEqual(preset["scope"], "campaign")
        self.assertIn(CENTRALCOMM_CAMPAIGN_SLUG, preset["specimen_url"])
        self.assertEqual(preset["ad_copy"]["cta"], "Reservar")
        self.assertEqual(preset["tokens"]["ink"], "#1E4D4F")


class DesignSystemAdsDeployTest(unittest.TestCase):
    def test_deploy_aplica_migration(self):
        root = Path(__file__).resolve().parents[1]
        migration = (root / "migrations" / "add_design_system_ads.sql").read_text(
            encoding="utf-8"
        )
        runner = (root / "migrations" / "run_add_design_system_ads.py").read_text(
            encoding="utf-8"
        )
        deploy = (root / "deploy.sh").read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN IF NOT EXISTS brand_profile", migration)
        self.assertIn("ADD COLUMN IF NOT EXISTS creative_brief", migration)
        self.assertIn("uq_cx_brand_visual_systems_design_system_ads", migration)
        self.assertIn("design-system-ads", migration)
        self.assertIn("add_design_system_ads.sql", runner)
        self.assertIn("uq_cx_brand_visual_systems_design_system_ads", runner)
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_add_design_system_ads.py',
            deploy,
        )
        self.assertIn(
            '"$VENV_PYTHON" migrations/run_add_creative_plate_kits.py',
            deploy,
        )
        self.assertLess(
            deploy.index(
                '"$VENV_PYTHON" migrations/run_add_creative_storyboards_and_catalogs.py'
            ),
            deploy.index(
                '"$VENV_PYTHON" migrations/run_add_design_system_ads.py'
            ),
        )
        self.assertLess(
            deploy.index(
                '"$VENV_PYTHON" migrations/run_add_creative_compose_library.py'
            ),
            deploy.index(
                '"$VENV_PYTHON" migrations/run_add_design_system_ads.py'
            ),
        )


class DesignSystemAdsContrastTest(unittest.TestCase):
    def test_teal_sobre_branco(self):
        self.assertGreaterEqual(contrast_ratio("#1E4D4F", "#FFFFFF"), 4.5)
        self.assertLess(contrast_ratio("#F3B71B", "#FFFFFF"), 4.5)


if __name__ == "__main__":
    unittest.main()
