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
from aicentralv2.design_system_ads.components import apply_background, density_for
from aicentralv2.design_system_ads.ingest import ingest_extracted
from aicentralv2.design_system_ads.materialize import ensure_brand_design_system
from aicentralv2.design_system_ads.refine import (
    apply_compose,
    apply_token_patches,
    clamp_passes,
    heal_contrast,
    improve_system,
    refine_design_system,
)
from aicentralv2.design_system_ads.tracks import prompt_for_track
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

    def test_extract_normalized_vira_tokens_de_anuncio(self):
        ingested = ingest_extracted(
            {
                "source": {"url": "https://acme.test"},
                "colors": {
                    "primary": "#0f172a",
                    "secondary": "#64748b",
                    "accent": "#16a34a",
                    "background": "#ffffff",
                    "foreground": "#0f172a",
                    "palette": ["#0f172a", "#ffffff", "#16a34a"],
                },
                "typography": {"headingFont": "Geist", "bodyFont": "Geist"},
                "radius": {"scale": ["0px", "6px", "999px"]},
            }
        )
        self.assertEqual(ingested["tokens"]["paper"], "#FFFFFF")
        self.assertEqual(ingested["tokens"]["ink"], "#0F172A")
        self.assertEqual(ingested["tokens"]["accent"], "#0F172A")
        self.assertEqual(ingested["tokens"]["highlight"], "#16A34A")
        self.assertEqual(ingested["tokens"]["font-display"], "Geist")
        self.assertEqual(ingested["tokens"]["cta-radius"], "6px")
        self.assertEqual(ingested["source_url"], "https://acme.test")

    def test_extract_ouro_nao_vira_cta(self):
        ingested = ingest_extracted(
            {
                "colors": {
                    "primary": "#F3B71B",
                    "foreground": "#1E4D4F",
                    "background": "#FFFFFF",
                }
            }
        )
        self.assertEqual(ingested["tokens"]["ink"], "#1E4D4F")
        self.assertEqual(ingested["tokens"]["accent"], "#1E4D4F")
        self.assertEqual(ingested["tokens"]["highlight"], "#F3B71B")

    def test_extract_voz_de_anuncio_nao_componente(self):
        tight = ingest_extracted(
            {
                "colors": {
                    "primary": "#0f172a",
                    "foreground": "#0f172a",
                    "background": "#ffffff",
                    "border": "#cbd5e1",
                },
                "typography": {
                    "headingFont": "Satoshi",
                    "styles": [
                        {"family": "Satoshi", "weight": 800, "letterSpacing": "-0.04em"}
                    ],
                },
                "spacing": {"scale": ["4px", "8px", "16px"]},
                "shadows": {"scale": ["0 1px 2px rgba(0,0,0,0.1)"]},
            }
        )
        self.assertEqual(tight["evidence"]["voice"]["density"], "compact")
        self.assertEqual(tight["tokens"]["weight-display"], "800")
        self.assertEqual(tight["tokens"]["tracking"], "-0.04em")
        self.assertEqual(tight["tokens"]["cta-pad"], "0.55em 0.95em")
        self.assertEqual(tight["tokens"]["cta-shadow"], "none")
        self.assertEqual(tight["tokens"]["hairline"], "#CBD5E1")
        lifted = ingest_extracted(
            {
                "colors": {"primary": "#111111", "background": "#ffffff", "foreground": "#111111"},
                "spacing": {"scale": ["16px", "24px"]},
                "shadows": {"scale": ["0 8px 16px rgba(15, 23, 42, 0.22)"]},
            }
        )
        self.assertEqual(lifted["evidence"]["voice"]["density"], "airy")
        self.assertEqual(lifted["evidence"]["voice"]["elevation"], "lifted")
        self.assertIn("8px 16px", lifted["tokens"]["cta-shadow"])

    def test_materializa_marca_com_extract(self):
        system = ensure_brand_design_system(
            {
                "id": 44,
                "name": "Acme Ads",
                "logo_url": "/static/images/cc_logo.png",
                "primary_color": "#123456",
                "brand_profile": {
                    "extracted_design_system": {
                        "colors": {
                            "primary": {"$value": "#0f172a"},
                            "background": "#f8fafc",
                            "foreground": "#0f172a",
                            "accent": "#22c55e",
                        },
                        "typography": {"headingFont": "Geist", "bodyFont": "IBM Plex Sans"},
                    }
                },
            }
        )
        self.assertEqual(system.source, "extract-design-system")
        self.assertEqual(system.tokens["font-display"], "Geist")
        self.assertEqual(system.tokens["font-body"], "IBM Plex Sans")
        self.assertEqual(system.tokens["ink"], "#0F172A")
        self.assertGreaterEqual(system.contrast["pairs"]["ink_on_paper"], MIN_CONTRAST)
        self.assertGreaterEqual(system.contrast["pairs"]["cta_on_accent"], MIN_CONTRAST)
        self.assertEqual(system.evidence.get("source"), "extract-design-system")

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

    def test_melhoria_por_intencao_muda_a_peca(self):
        system = centralcomm_preset()
        typed, report = improve_system(system, "type")
        self.assertEqual(typed.tokens["weight-display"], "800")
        self.assertEqual(typed.tokens["tracking"], "-0.03em")
        self.assertTrue(report.patches)
        compact, _ = improve_system(system, "compact")
        self.assertEqual(compact.tokens["safe"], "4%")
        self.assertEqual(compact.tokens["cta-pad"], "0.55em 0.95em")
        payload = payload_for(typed)
        self.assertTrue(payload["token_groups"])
        self.assertEqual(payload["intents"][0]["id"], "contrast")
        self.assertTrue(payload["backgrounds"])
        self.assertEqual(payload["archetype"], "brand")
        washed = apply_background(system.tokens, "wash")
        self.assertEqual(washed["ground-kind"], "wash")
        self.assertNotEqual(washed["overlay"], "transparent")
        imaged = apply_background(system.tokens, "image", image_url="/static/images/cc_logo.png")
        self.assertEqual(imaged["ground"], "/static/images/cc_logo.png")
        self.assertEqual(density_for("iab-leaderboard", "thin"), "compact")
        self.assertEqual(density_for("iab-billboard"), "rich")
        composed, _ = apply_compose(
            system,
            {
                "dna": {"personality": ["icônica"], "must": ["vermelho"]},
                "ad_copy": {"headline": "Sabor que aproxima"},
                "tracks": [{"id": "kv", "prompt": "KV 16:9 with ink space"}],
            },
        )
        self.assertIn("icônica", composed.dna.get("personality") or [])
        self.assertEqual(composed.ad_copy["headline"], "Sabor que aproxima")
        kv = next(item for item in composed.tracks if item["id"] == "kv")
        self.assertIn("16:9", kv["prompt"])
        self.assertIn("#1E4D4F", prompt_for_track(system, "packshot"))
        self.assertNotIn("reconhecível", prompt_for_track(system, "packshot"))
        catalog = payload_for(system)
        self.assertEqual(len(catalog["catalog"]["components"]), 7)
        self.assertEqual(len(catalog["archetypes"]), 4)
        self.assertEqual(catalog["loop"]["action"], "track")
        self.assertTrue(catalog["catalog"]["backgrounds"])
        empty = ensure_brand_design_system({"id": 21, "name": "Vazia", "primary_color": "#123456"})
        self.assertNotIn("reconhecível", empty.dna.get("personality") or [])
        empty.dna = {}
        from aicentralv2.design_system_ads.refine import (
            advance_loop,
            seed_campaign_compose,
            seed_local_compose,
        )

        seeded, info, _report = advance_loop(empty)
        self.assertTrue(seeded.dna.get("personality"))
        self.assertNotIn("reconhecível", seeded.dna.get("personality") or [])
        self.assertIn(info["action"], {"contrast", "review", "track", "ready", "rules"})
        local, _report = seed_local_compose(empty)
        self.assertNotIn("reconhecível", local.dna.get("personality") or [])
        self.assertTrue(local.ad_copy.get("headline"))
        self.assertNotIn("tinta certa", (local.ad_copy.get("headline") or "").lower())
        campaign, _ = seed_campaign_compose(system, {
            "name": "Verao",
            "objective": "Calor no visual",
            "cta_text": "Reservar",
        })
        self.assertEqual(campaign.scope, "campaign")
        self.assertIn("Calor", campaign.creative_line)
        self.assertEqual(campaign.ad_copy.get("cta"), "Reservar")
        self.assertNotEqual(campaign.ad_copy.get("headline"), system.ad_copy.get("headline"))

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
        self.assertIn("dsa-ad-stage", html)
        self.assertIn("--dsa-ink", html)
        self.assertIn("A campanha chega inteira", html)
        self.assertNotIn("A peça na tinta certa", html)
        self.assertNotIn("ink / paper", html)
        self.assertNotIn("dsa-kicker", html)
        self.assertIn("/static/images/cc_logo.png", html)
        payload = payload_for(centralcomm_preset())
        self.assertIn("/lab/design-system/marca/", payload["specimen_url"])
        self.assertIn("format=", payload["specimen_url"])
        self.assertIn("dsa-ad-stage", payload["specimen_html"])

    def test_copy_de_anuncio_nao_e_meta(self):
        from aicentralv2.design_system_ads.copy import (
            brand_ad_copy,
            clean_ad_copy,
            is_meta_copy,
        )

        house = brand_ad_copy("CentralComm")
        self.assertEqual(house["headline"], "A campanha chega inteira")
        self.assertFalse(is_meta_copy(house))
        self.assertTrue(is_meta_copy({"headline": "A peça na tinta certa"}))
        cleaned = clean_ad_copy(
            {
                "headline": "A peça na tinta certa",
                "support": "O anúncio herda o tema Tailwind da CentralComm.",
                "cta": "Ver o sistema",
            },
            "CentralComm",
        )
        self.assertEqual(cleaned["cta"], "Começar agora")
        self.assertNotIn("design system", " ".join(cleaned.values()).lower())
        brand = brand_ad_copy("Clara")
        self.assertIn("Clara", brand["headline"])
        self.assertEqual(brand["cta"], "Ver mais")
        self.assertNotEqual(brand["cta"], "Saiba mais")
        from aicentralv2.design_system_ads.copy import fit_ad_copy

        compact = fit_ad_copy(
            {
                "headline": "Uma headline longa demais para o leaderboard de anúncio",
                "support": "Apoio que some no compacto",
                "cta": "Começar agora mesmo",
                "legal": "CentralComm",
            },
            "compact",
            "CentralComm",
        )
        self.assertEqual(compact["support"], "")
        self.assertLessEqual(len(compact["headline"]), 32)
        self.assertLessEqual(len(compact["cta"]), 14)

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
        self.assertIn(
            "/parametros/api/design-system/brand/<client_id>/tokens",
            [rule.rule for rule in app.url_map.iter_rules()],
        )
        with app.test_request_context():
            self.assertEqual(
                url_for("parametros.modelagem_design-system"),
                "/parametros/modelagem-criativos/design-system",
            )
        desk = Path(__file__).resolve().parents[1] / "aicentralv2" / "templates" / "parametros" / "_mc_design_system.html"
        html = desk.read_text(encoding="utf-8")
        self.assertNotIn("data-mode", html)
        self.assertIn("Montar", html)
        self.assertIn("Montar campanha", html)
        self.assertIn("Aprovar", html)
        self.assertIn("mcDsaCatalog", html)
        self.assertIn("mcDsaStage", html)
        self.assertIn("mcDsaGrounds", html)
        self.assertIn("mcDsaArchetypes", html)
        self.assertNotIn("mcDsaIntents", html)
        self.assertNotIn("mcDsaLoop", html)
        self.assertNotIn("mcDsaCompose", html)
        self.assertNotIn("Continuar loop", html)
        self.assertIn(
            "/parametros/api/design-system/brand/<client_id>/compose",
            [rule.rule for rule in app.url_map.iter_rules()],
        )
        self.assertIn(
            "/parametros/api/design-system/brand/<client_id>/loop",
            [rule.rule for rule in app.url_map.iter_rules()],
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


class DesignSystemAdsFidelityTest(unittest.TestCase):
    def test_ouro_nao_vira_teal_da_casa(self):
        weak = ensure_brand_design_system(
            {"id": 1, "name": "Clara", "primary_color": "#F3B71B"}
        )
        self.assertEqual(weak.tokens["ink"].upper(), "#F3B71B")
        healed, patches = heal_contrast(weak)
        self.assertNotEqual(healed.tokens["ink"].upper(), "#1E4D4F")
        self.assertTrue(patches)
        self.assertGreaterEqual(healed.contrast["pairs"]["ink_on_paper"], MIN_CONTRAST)
        ink = healed.tokens["ink"].lstrip("#")
        red, _green, blue = int(ink[0:2], 16), int(ink[2:4], 16), int(ink[4:6], 16)
        self.assertGreater(red, blue)

    def test_asset_da_marca_entra_na_trilha(self):
        system = ensure_brand_design_system(
            {
                "id": 9,
                "name": "Clara",
                "primary_color": "#123456",
                "brand_assets": [
                    {"asset_url": "/media/clara-pack.jpg", "role": "packshot"},
                    {"asset_url": "/media/clara-kv.jpg", "role": "kv"},
                ],
            }
        )
        pack = next(item for item in system.tracks if item["id"] == "packshot")
        kv = next(item for item in system.tracks if item["id"] == "kv")
        self.assertEqual(pack["url"], "/media/clara-pack.jpg")
        self.assertEqual(kv["url"], "/media/clara-kv.jpg")

    def test_copy_estoque_volta_ao_compose(self):
        from aicentralv2.design_system_ads.catalog import inspect_loop
        from aicentralv2.design_system_ads.copy import is_stock_copy

        system = ensure_brand_design_system(
            {
                "id": 8,
                "name": "Clara",
                "primary_color": "#123456",
                "sector": "joalheria",
                "tone_of_voice": "cálida",
            }
        )
        system.ad_copy = {
            "headline": "Clara no primeiro olhar",
            "support": "O que Clara promete, no tamanho do anúncio.",
            "cta": "Saiba mais",
            "legal": "Clara",
        }
        self.assertTrue(is_stock_copy(system.ad_copy))
        self.assertEqual(inspect_loop(system)["action"], "compose")

    def test_loop_revisa_antes_das_trilhas(self):
        from aicentralv2.design_system_ads.catalog import inspect_loop
        from aicentralv2.design_system_ads.refine import advance_loop

        filled = ensure_brand_design_system(
            {
                "id": 8,
                "name": "Clara",
                "primary_color": "#123456",
                "sector": "joalheria",
                "tone_of_voice": "cálida",
            }
        )
        self.assertEqual(inspect_loop(filled)["action"], "review")
        advanced, info, _report = advance_loop(filled)
        self.assertTrue((advanced.evidence or {}).get("reviewed"))
        self.assertEqual(info["action"], "track")
        house = payload_for(centralcomm_preset())
        self.assertEqual(house["loop"]["action"], "track")
        self.assertNotIn("wash", house["loop"]["missing_tracks"])

    def test_extract_ouro_sozinho_nao_vira_teal(self):
        ingested = ingest_extracted(
            {"colors": {"primary": "#F3B71B", "background": "#FFFFFF"}}
        )
        self.assertNotEqual(ingested["tokens"]["ink"].upper(), "#1E4D4F")
        ink = ingested["tokens"]["ink"].lstrip("#")
        red, _green, blue = int(ink[0:2], 16), int(ink[2:4], 16), int(ink[4:6], 16)
        self.assertGreater(red, blue)
        self.assertGreaterEqual(contrast_ratio(ingested["tokens"]["ink"], "#FFFFFF"), MIN_CONTRAST)

    def test_asset_sem_papel_ainda_entra_no_packshot(self):
        system = ensure_brand_design_system(
            {
                "id": 11,
                "name": "Clara",
                "primary_color": "#123456",
                "brand_assets": [{"asset_url": "/media/clara-loose.jpg"}],
            }
        )
        pack = next(item for item in system.tracks if item["id"] == "packshot")
        self.assertEqual(pack["url"], "/media/clara-loose.jpg")

    def test_trilha_anexa_produto_e_logo(self):
        from aicentralv2.design_system_ads.fidelity import track_reference_urls
        from aicentralv2.services.openrouter_service import build_image_payload

        client = {
            "id": 19,
            "name": "Clara",
            "primary_color": "#123456",
            "logo_url": "/static/uploads/client_logos/clara.png",
            "brand_assets": [{"asset_url": "/media/clara-pack.jpg", "role": "packshot"}],
        }
        system = ensure_brand_design_system(client)
        pack = track_reference_urls(system, "packshot", client)
        self.assertEqual(pack[0], "/media/clara-pack.jpg")
        self.assertIn("/static/uploads/client_logos/clara.png", pack)
        self.assertLessEqual(len(pack), 2)
        kv = track_reference_urls(system, "kv", client)
        self.assertEqual(kv[0], "/media/clara-pack.jpg")
        self.assertEqual(track_reference_urls(system, "wash", client), [])
        payload = build_image_payload(
            "packshot",
            input_references=[
                "data:image/png;base64,cmVmMQ==",
                "https://cdn.test/logo.png",
                "/local/skip.png",
            ],
        )
        self.assertEqual(len(payload["input_references"]), 2)
        self.assertEqual(
            payload["input_references"][0]["image_url"]["url"],
            "data:image/png;base64,cmVmMQ==",
        )

    def test_campanha_liga_recorte_na_trilha(self):
        from aicentralv2.design_system_ads.campaign import ensure_campaign_design_system

        system, _elements = ensure_campaign_design_system(
            centralcomm_preset(),
            {"id": 9, "name": "Verao", "cta_text": "Reservar"},
            [{"asset_url": "/static/a.png", "role": "product"}],
        )
        pack = next(item for item in system.tracks if item["id"] == "packshot")
        self.assertEqual(pack["url"], "/static/a.png")

    def test_produto_ocupa_o_poco_no_hero(self):
        from aicentralv2.design_system_ads.adapt import adapt_system
        from aicentralv2.design_system_ads.schema import parse_system

        brand = parse_system(dump_system(centralcomm_preset()))
        brand.archetype = "product-hero"
        brand.tracks = [
            {**item, "url": "/media/pack.png"} if item["id"] == "packshot" else item
            for item in brand.tracks
        ]
        adapted, stack = adapt_system(brand, "iab-medium", 4)
        product = next(item for item in stack["layers"] if item["role"] == "product")
        self.assertFalse(product.get("parked"))
        self.assertEqual(product.get("asset_url"), "/media/pack.png")
        self.assertGreaterEqual(product["w"], 80)
        self.assertNotIn("visual", [item["role"] for item in stack["layers"]])
        html = render_specimen(adapted, standalone=True, stack=stack)
        self.assertIn("/media/pack.png", html)

    def test_curriculo_classifica_criativo_real(self):
        from aicentralv2.design_system_ads.learn import classify_creative, curriculum

        levels = {item["id"] for item in curriculum()}
        self.assertEqual(levels, {"L1", "L2", "L3", "L4", "L5"})
        pack = classify_creative({"type_on_image": False, "faces": 0})
        self.assertEqual(pack["id"], "L1")
        self.assertEqual(pack["lab"], "campaign-pack")
        self.assertEqual(pack["concept"], "packshot")
        car = classify_creative({"type_on_image": True, "aspect": "1.91:1"})
        self.assertEqual(car["id"], "L2")
        self.assertEqual(car["format"], "linkedin-landscape")
        self.assertEqual(car["lab"], "format-lab-swap-read")
        self.assertEqual(car["template"], "product-left-type")
        feed = classify_creative({"chrome": "meta", "aspect": "4:5", "faces": 1})
        self.assertEqual(feed["id"], "L3")
        self.assertTrue(feed["crop_first"])
        festa = classify_creative({"faces": 6, "name_pills": True, "aspect": "1:1"})
        self.assertEqual(festa["id"], "L4")
        self.assertEqual(festa["lab"], "decompose")
        print_google = classify_creative({"screenshot": True, "chrome": "google"})
        self.assertEqual(print_google["id"], "L5")
        self.assertEqual(print_google["lab"], "crop-then-learn")
        self.assertEqual(print_google["inner"], "L1")
        from aicentralv2.design_system_ads.catalog import catalog_for

        catalog = catalog_for(centralcomm_preset())
        self.assertEqual({item["id"] for item in catalog["curriculum"]}, levels)
        self.assertIn("event-kv", {item["id"] for item in catalog["training"]["concepts"]})

    def test_lote_real_aumenta_assertividade(self):
        from aicentralv2.design_system_ads.learn import measure_training, plan_training

        report = measure_training()
        self.assertGreaterEqual(report["before"]["accuracy"], 0.3)
        self.assertLess(report["before"]["accuracy"], 0.55)
        self.assertGreaterEqual(report["after"]["accuracy"], 0.95)
        self.assertGreaterEqual(report["delta"], 0.4)
        self.assertEqual(report["after"]["misses"], [])
        seniortec = plan_training(
            {"cropped": True, "aspect": "4:5", "faces": 2, "type_on_image": True, "event": True}
        )
        self.assertEqual(seniortec["concept"], "event-kv")
        self.assertNotEqual(seniortec["id"], "L3")
        self.assertEqual(seniortec["labs"]["format_skill"], "iab-banner")
        self.assertIn("reconstruct", seniortec["labs"]["packs"])

    def test_receitas_sociais_ficam_perfeitas(self):
        from aicentralv2.design_system_ads.adapt import adapt_system, list_iab_formats
        from aicentralv2.design_system_ads.layouts import validate_stack

        keys = {item["key"] for item in list_iab_formats()}
        self.assertIn("feed-1x1", keys)
        self.assertIn("feed-4x5", keys)
        self.assertIn("story-9x16", keys)
        for key in ("feed-1x1", "feed-4x5", "story-9x16", "linkedin-landscape"):
            for count in (4, 8):
                adapted, stack = adapt_system(centralcomm_preset(), key, count)
                issues = validate_stack(stack)
                self.assertEqual(issues, [], f"{key} × {count}: {issues}")
                cta = next(item for item in stack["layers"] if item["role"] == "cta")
                height = stack["format"]["height"]
                self.assertGreaterEqual(height * cta["h"] / 100, 28)


class DesignSystemAdsLiveCreativesTest(unittest.TestCase):
    FIXTURES = Path(__file__).resolve().parent / "fixtures" / "creatives"

    def test_dois_criativos_reais_passam_no_projeto(self):
        from aicentralv2.creative_skills.loader import load_format_skill, resolve_pack
        from aicentralv2.design_system_ads.adapt import adapt_system
        from aicentralv2.design_system_ads.layouts import validate_stack
        from aicentralv2.design_system_ads.learn import (
            inspect_creative_file,
            lesson_from_file,
            live_pair,
            plan_training,
        )

        pair = live_pair()
        self.assertEqual([item["id"] for item in pair], ["arraial", "mg-cyberster"])
        for item in pair:
            path = self.FIXTURES / item["filename"]
            self.assertTrue(path.is_file(), f"falta o criativo {path}")
            inspected = inspect_creative_file(path)
            self.assertEqual(inspected["width"], item["inspect"]["width"])
            self.assertEqual(inspected["height"], item["inspect"]["height"])
            self.assertEqual(inspected["screenshot"], item["inspect"]["screenshot"])
            lesson = lesson_from_file(path, item["hints"])
            for axis, expected in item["expect"].items():
                self.assertEqual(lesson.get(axis), expected, f"{item['id']}.{axis}")
            planned = plan_training({**inspected["hints"], **item["hints"]})
            self.assertEqual(planned["labs"]["format_skill"], "iab-banner")
            self.assertIn("reconstruct", planned["labs"]["packs"])
            pack = resolve_pack("reconstruct", lesson["format"], has_reference=True)
            self.assertEqual(pack["format_skill"], "iab-banner")
            self.assertIn(lesson["format"], load_format_skill(lesson["format"]))
            adapted, stack = adapt_system(centralcomm_preset(), lesson["format"], 8)
            self.assertEqual(validate_stack(stack), [], lesson["format"])
            html = render_specimen(adapted, standalone=True, stack=stack)
            self.assertIn("dsa-ad", html)
            payload = payload_for(
                centralcomm_preset(),
                format_key=lesson["format"],
                layer_count=8,
            )
            self.assertIn("dsa-ad", payload["specimen_html"])
            self.assertEqual(payload["layers"]["count"], 8)

        phone = inspect_creative_file(self.FIXTURES / "mg-discover.jpg")
        self.assertTrue(phone["screenshot"])
        self.assertNotEqual(phone["hints"].get("aspect"), "9:16")


class DesignSystemAdsContrastTest(unittest.TestCase):
    def test_teal_sobre_branco(self):
        self.assertGreaterEqual(contrast_ratio("#1E4D4F", "#FFFFFF"), 4.5)
        self.assertLess(contrast_ratio("#F3B71B", "#FFFFFF"), 4.5)


if __name__ == "__main__":
    unittest.main()
