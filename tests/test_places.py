import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from aicentralv2.places.brand import PUBLIC_TOKENS, zone_color
from aicentralv2.places.catalog import CONGONHAS, CONFINS, GALEAO, SANTOS_DUMONT, SEED_PLACES
from aicentralv2.places.repository import PlacesError, inquiry_payload
from aicentralv2.places.routes import bp as places_bp
from aicentralv2.places.research import (
    FINALIZE_MODEL,
    ResearchError,
    geocode_one,
    polish_one_page,
    refine_generated_fiche,
    search_places,
)
from aicentralv2.places.images import _point_prompt, next_image_target, point_matches
from aicentralv2.places.pipeline import assemble_fiche, fiche_output
from aicentralv2.places.schema import format_usd, normalize_payload, public_view, sum_zone_reaches
from aicentralv2.places.service import apply_images, apply_import, serialize
from aicentralv2.places.share import public_path, slugify

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CSS = ROOT / "aicentralv2" / "static" / "css" / "places_public.css"
PUBLIC_JS = ROOT / "aicentralv2" / "static" / "js" / "places_public.js"
ADMIN_CSS = ROOT / "aicentralv2" / "static" / "css" / "places.css"
ADMIN_JS = ROOT / "aicentralv2" / "static" / "js" / "places.js"
ADMIN_INDEX = ROOT / "aicentralv2" / "templates" / "places" / "index.html"
ADMIN_EDIT = ROOT / "aicentralv2" / "templates" / "places" / "edit.html"


class PlacesCatalogTest(unittest.TestCase):
    def test_seed_has_four_airports(self):
        self.assertEqual(
            [item["slug"] for item in SEED_PLACES],
            ["confins", "congonhas", "santos-dumont", "galeao"],
        )

    def test_anac_2025_passenger_labels(self):
        self.assertEqual(CONFINS["payload"]["metrics"]["passengers"]["label"], "13,2 mi")
        self.assertEqual(CONFINS["payload"]["metrics"]["passengers"]["value"], 13_183_039)
        self.assertEqual(CONGONHAS["payload"]["metrics"]["passengers"]["label"], "24,6 mi")
        self.assertEqual(CONGONHAS["payload"]["metrics"]["passengers"]["value"], 24_583_610)
        self.assertEqual(SANTOS_DUMONT["payload"]["metrics"]["passengers"]["label"], "6,2 mi")
        self.assertEqual(SANTOS_DUMONT["payload"]["metrics"]["passengers"]["value"], 6_184_233)
        self.assertEqual(SANTOS_DUMONT["payload"]["metrics"]["four_weeks"]["label"], "~476 mil")
        self.assertEqual(GALEAO["payload"]["metrics"]["passengers"]["label"], "17,8 mi")
        self.assertEqual(GALEAO["payload"]["metrics"]["passengers"]["value"], 17_836_134)
        self.assertEqual(GALEAO["payload"]["metrics"]["four_weeks"]["value"], 1_372_010)

    def test_sdu_does_not_keep_book_49(self):
        self.assertNotIn("4,9", SANTOS_DUMONT["payload"]["metrics"]["passengers"]["label"])

    def test_metrics_carry_source_status(self):
        passengers = CONFINS["payload"]["metrics"]["passengers"]
        four_weeks = CONFINS["payload"]["metrics"]["four_weeks"]
        self.assertEqual(passengers["source_status"], "official")
        self.assertEqual(four_weeks["source_status"], "estimate")
        self.assertIn("ANAC", passengers["source"])

    def test_cannot_sum_zone_reaches(self):
        with self.assertRaisesRegex(ValueError, "Não some"):
            sum_zone_reaches(CONFINS["payload"]["zones"])

    def test_sdu_avoids_runway_copy(self):
        body = SANTOS_DUMONT["payload"]["methodology"]["body"]
        self.assertIn("pistas", body.lower())

    def test_confins_international_is_to_validate(self):
        zone = next(item for item in CONFINS["payload"]["zones"] if item["id"] == "CNF-03")
        self.assertEqual(zone["reach"], "8–14 mil")
        self.assertEqual(zone["reach_status"], "to_validate")
        point = next(item for item in CONFINS["payload"]["points"] if item["id"] == "cnf-internacional")
        self.assertEqual(point["reach_status"], "to_validate")
        self.assertEqual(point["radius_m"], 200)

    def test_addressable_is_below_physical_four_weeks(self):
        for item in SEED_PLACES:
            physical = item["payload"]["metrics"]["four_weeks"]["value"]
            addressable = item["payload"]["metrics"]["addressable"]["value"]
            self.assertIsNotNone(physical)
            self.assertIsNotNone(addressable)
            self.assertLess(addressable, physical * 0.4)
            self.assertGreater(addressable, physical * 0.1)

    def test_points_have_distinct_radii(self):
        for item in SEED_PLACES:
            radii = {point["radius_m"] for point in item["payload"]["points"]}
            self.assertGreaterEqual(len(radii), 3)
            self.assertTrue(all(point["reach"] for point in item["payload"]["points"]))
            self.assertTrue(all(point["formats"] for point in item["payload"]["points"]))

    def test_catchment_uses_official_census_recorte(self):
        cnf = CONFINS["payload"]["catchment"]
        self.assertEqual(cnf["population"]["value"], 211_741)
        self.assertEqual(cnf["population"]["label"], "212 mil")
        self.assertEqual(cnf["population"]["source_status"], "official")
        self.assertEqual(cnf["density"]["label"], "~620 hab/km²")
        self.assertEqual(cnf["density"]["source_status"], "official")

        cgh = CONGONHAS["payload"]["catchment"]
        self.assertEqual(cgh["population"]["value"], 152_933)
        self.assertEqual(cgh["population"]["label"], "153 mil")
        self.assertEqual(cgh["population"]["source_status"], "official")
        self.assertEqual(cgh["density"]["label"], "~8,6 mil hab/km²")
        self.assertEqual(cgh["neighborhoods"], ["Campo Belo", "Moema"])
        self.assertNotIn("Brooklin", cgh["neighborhoods"])

        sdu = SANTOS_DUMONT["payload"]["catchment"]
        self.assertEqual(sdu["population"]["value"], 96_156)
        self.assertEqual(sdu["population"]["label"], "96 mil")
        self.assertEqual(sdu["population"]["source_status"], "official")
        self.assertEqual(sdu["density"]["label"], "~10,8 mil hab/km²")
        self.assertEqual(sdu["neighborhoods"], ["Centro", "Glória", "Catete", "Flamengo"])

        gig = GALEAO["payload"]["catchment"]
        self.assertEqual(gig["population"]["value"], 211_018)
        self.assertEqual(gig["population"]["label"], "211 mil")
        self.assertEqual(gig["population"]["source_status"], "official")
        self.assertEqual(gig["density"]["label"], "~5,2 mil hab/km²")
        self.assertEqual(gig["neighborhoods"], ["Galeão", "Portuguesa", "Jardim Guanabara"])
        self.assertNotIn("Vinte e Oito de Setembro", str(GALEAO))

    def test_seed_has_geo_and_points(self):
        for item in SEED_PLACES:
            geo = item["payload"]["geo"]
            self.assertIsNotNone(geo["lat"])
            self.assertIsNotNone(geo["lng"])
            self.assertTrue(item["payload"]["points"])
            self.assertTrue(all(point["lat"] is not None for point in item["payload"]["points"]))

    def test_public_view_labels_city_and_type(self):
        view = public_view(CONGONHAS)
        self.assertEqual(view["city_label"], "São Paulo")
        self.assertEqual(view["type_label"], "Aeroporto")
        self.assertTrue(view["catchment"]["neighborhoods"])
        self.assertEqual(view["offer"]["lines"][0]["title"], "No T1")

    def test_each_airport_has_its_own_offer(self):
        leads = {item["payload"]["offer"]["lead"] for item in SEED_PLACES}
        self.assertEqual(len(leads), 4)
        for item in SEED_PLACES:
            self.assertGreaterEqual(len(item["payload"]["offer"]["lines"]), 3)
            format_sets = {tuple(point["formats"]) for point in item["payload"]["points"]}
            self.assertGreater(len(format_sets), 1)
            self.assertTrue(all(point.get("image_url") for point in item["payload"]["points"]))

    def test_normalize_keeps_polygon(self):
        payload = normalize_payload(CONFINS["payload"])
        self.assertTrue(payload["zones"][0]["polygon"].startswith("43,43"))

    def test_normalize_keeps_point_image(self):
        payload = normalize_payload(
            {
                "points": [
                    {
                        "name": "Terminal",
                        "kind": "terminal",
                        "lat": -19.62,
                        "lng": -43.97,
                        "image_url": "/static/images/places/generated/t.png",
                    }
                ]
            }
        )
        self.assertEqual(payload["points"][0]["image_url"], "/static/images/places/generated/t.png")

    def test_slug_and_public_path(self):
        self.assertEqual(slugify("Santos Dumont"), "santos-dumont")
        self.assertEqual(public_path("confins"), "/places/p/confins")

    def test_search_requires_query(self):
        with self.assertRaises(ResearchError):
            search_places("a")

    def test_finalize_uses_gpt5_family(self):
        self.assertIn("gpt-5", FINALIZE_MODEL)
        self.assertTrue(callable(polish_one_page))
        self.assertTrue(callable(refine_generated_fiche))

    def test_research_prompt_covers_airport_kinds(self):
        from aicentralv2.places import research as research_mod

        source = research_mod.research_region.__code__.co_consts
        blob = " ".join(item for item in source if isinstance(item, str))
        self.assertIn("embarque", blob)
        self.assertIn("premium", blob)

    def test_image_model_is_per_airport(self):
        from aicentralv2.places.images import resolve_place_image_spec

        self.assertEqual(resolve_place_image_spec({"code": "CNF"}), ("openai/gpt-image-2", "2K"))
        self.assertEqual(resolve_place_image_spec({"code": "SDU"}), ("openai/gpt-image-2", "2K"))
        self.assertEqual(resolve_place_image_spec({"code": "CGH"}), ("google/gemini-3-pro-image", "1K"))
        self.assertEqual(resolve_place_image_spec({"code": "GIG"}), ("bytedance-seed/seedream-5-0-lite", "2K"))

    def test_inquiry_requires_name_and_contact(self):
        with self.assertRaises(PlacesError):
            inquiry_payload({"name": "", "email": "a@b.com"})
        with self.assertRaises(PlacesError):
            inquiry_payload({"name": "Ana"})
        row = inquiry_payload({"name": "Ana", "email": "ana@marca.com"})
        self.assertEqual(row["email"], "ana@marca.com")

    def test_public_css_follows_logo_not_erp(self):
        css = PUBLIC_CSS.read_text(encoding="utf-8")
        self.assertNotIn("--cx-", css)
        self.assertNotIn("#4FFF82", css)
        self.assertNotIn("Fraunces", css)
        self.assertIn("#1e4d4f", css)
        self.assertIn("#f5a623", css)
        self.assertIn("#4aff6b", css)
        self.assertIn("#167a3a", css)
        self.assertIn("#080808", css)
        self.assertIn("Nunito", css)
        self.assertIn("safe-area-inset", css)
        self.assertIn("cc-zone-chip", css)
        self.assertIn("cc-foot", css)
        self.assertIn("cc-gallery", css)
        self.assertIn("cc-point-photo", css)
        self.assertIn("cc-map-art", css)
        self.assertIn("cc-map-label", css)
        self.assertIn("cc-flag", css)
        self.assertIn("cc-flag[hidden]", css)
        self.assertIn("cc-air-code", css)
        self.assertIn("minmax(0, 36rem)", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("100svh", css)
        self.assertIn("leaflet-container", css)
        self.assertIn("cc-gallery-cap", css)
        self.assertNotIn(".cc-docs", css)
        self.assertNotIn(".cc-overlay", css)

    def test_public_map_uses_satellite(self):
        js = PUBLIC_JS.read_text(encoding="utf-8")
        self.assertIn("World_Imagery", js)
        self.assertNotIn("tile.openstreetmap.org", js)
        self.assertIn("is-in", js)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("ArrowRight", js)

    def test_queue_bar_uses_css_var(self):
        css = ADMIN_CSS.read_text(encoding="utf-8")
        js = ADMIN_JS.read_text(encoding="utf-8")
        self.assertIn("--pct", css)
        self.assertIn('setProperty("--pct"', js)
        self.assertIn("is-busy", css)

    def test_point_prompts_cover_airport_kinds(self):
        embarque = _point_prompt("Confins", "Belo Horizonte", "Embarque doméstico", "embarque", "")
        premium = _point_prompt("Confins", "Belo Horizonte", "Internacional", "premium", "")
        self.assertIn("departures", embarque)
        self.assertIn("international", premium)
        self.assertIn("Documentary photography", embarque)

    def test_named_point_prompts_match_the_place_not_the_kind(self):
        avenue = _point_prompt("Congonhas", "São Paulo", "Washington Luís", "embarque", "")
        moema = _point_prompt("Congonhas", "São Paulo", "Moema", "halo", "")
        centro = _point_prompt("Santos Dumont", "Rio de Janeiro", "Centro", "halo", "")
        self.assertIn("Washington Luís", avenue)
        self.assertNotIn("departures hall", avenue)
        self.assertIn("street-level", moema)
        self.assertIn("Forbidden: airport runway", moema)
        self.assertIn("Rio Branco", centro)
        self.assertIn("street-level", centro)

    def test_admin_css_uses_centralx_tokens(self):
        css = ADMIN_CSS.read_text(encoding="utf-8")
        self.assertIn("--cx-brand", css)
        self.assertNotIn("#0c1a1b", css)
        self.assertIn(".pl-table", css)
        self.assertIn(".pl-queue", css)
        self.assertIn("letter-spacing: 0", css)

    def test_desk_is_a_table_and_a_single_trail(self):
        listing = ADMIN_INDEX.read_text(encoding="utf-8")
        form = ADMIN_EDIT.read_text(encoding="utf-8")
        js = ADMIN_JS.read_text(encoding="utf-8")
        self.assertIn("pl-table", listing)
        self.assertIn("Custo IA", listing)
        self.assertIn("data-copy", listing)
        self.assertIn('target="_blank"', listing)
        self.assertNotIn("pl-card", listing)
        self.assertIn("pl-trail", form)
        self.assertIn("Fechar ficha", form)
        self.assertIn("Gerar fotos que faltam", form)
        self.assertNotIn("pl-steps", form)
        self.assertNotIn("GPT Image 2", form)
        self.assertIn("runQueue", js)
        self.assertIn('kind: job.kind', js)
        self.assertIn("Fechando a ficha", js)
        self.assertIn("data-share-link", form)
        self.assertIn('setAttribute("data-copy"', js)
        self.assertIn('name: "Ponto "', js)
        self.assertIn("numberOrNull(item.lat)", js)
        self.assertIn("escapeHtml(point.name)", js)

    def test_zone_color_from_brand(self):
        self.assertEqual(zone_color("CORE"), "#167A3A")
        self.assertEqual(PUBLIC_TOKENS["logo"], "/static/images/cc_logo.png")
        self.assertEqual(PUBLIC_TOKENS["font_display"], "Nunito")

    def test_assemble_fiche_filters_and_fixes_points(self):
        fiche = assemble_fiche(
            {"code": "GIG", "title": "Galeão", "city_label": "Rio de Janeiro"},
            refined={
                "subtitle": "T2 na Ilha",
                "offer": {"lead": "Compre o T2", "lines": []},
                "points": [
                    {"name": "Terminal T2", "kind": "terminal", "commercial": "Saguão."},
                    {"name": "Base Aérea do Galeão", "kind": "marco"},
                    {"name": "Acesso rodoviário — Av. Vinte e Oito de Setembro", "kind": "mobilidade"},
                ],
            },
        )
        names = [item["name"] for item in fiche["points"]]
        self.assertEqual(names, ["Terminal T2", "Vinte de Janeiro"])
        self.assertTrue(any("Base" in item or "corrigido" in item.lower() for item in fiche["warnings"]))
        self.assertTrue(all(item["id"] for item in fiche["points"]))

    def test_geocode_one_keeps_query_clean_and_picks_nearest(self):
        with patch("aicentralv2.places.research.search_places") as search:
            search.return_value = [
                {"title": "longe", "lat": -23.0, "lng": -43.0},
                {"title": "perto", "lat": -22.81, "lng": -43.25},
            ]
            hit = geocode_one("Jardim Guanabara", near={"lat": -22.811, "lng": -43.250})
        self.assertEqual(search.call_args.args[0], "Jardim Guanabara")
        self.assertEqual(hit["title"], "perto")

    def test_fiche_output_exposes_image_spec_and_point_urls(self):
        out = fiche_output(
            {
                "title": "Galeão",
                "code": "GIG",
                "points": [{"id": "gig-t2", "name": "T2", "image_url": "/static/t2.png"}],
                "media": {"hero_url": "/static/hero.png"},
            }
        )
        self.assertEqual(out["images"]["spec"]["model"], "bytedance-seed/seedream-5-0-lite")
        self.assertEqual(out["images"]["spec"]["resolution"], "2K")
        self.assertEqual(out["images"]["hero_url"], "/static/hero.png")
        self.assertEqual(out["images"]["points"][0]["url"], "/static/t2.png")
        self.assertEqual(out["identity"]["code"], "GIG")

    def test_normalize_keeps_points_without_coords_and_costs(self):
        payload = normalize_payload(
            {
                "points": [{"id": "gig-ilha", "name": "Ilha", "kind": "halo"}],
                "costs": {
                    "entries": [
                        {"step": "image-hero", "model": "bytedance-seed/seedream-5-0-lite", "usd": 0.12, "label": "Hero"}
                    ]
                },
            }
        )
        self.assertEqual(payload["points"][0]["name"], "Ilha")
        self.assertIsNone(payload["points"][0]["lat"])
        self.assertEqual(payload["costs"]["total_usd"], 0.12)
        self.assertEqual(payload["costs"]["label"], "US$ 0,12")
        self.assertEqual(format_usd(0), "—")

    def test_next_image_is_one_missing_asset(self):
        target = next_image_target(
            {
                "media": {"hero_url": "/h.png"},
                "points": [
                    {"id": "gig-t2", "name": "T2", "image_url": "/t2.png"},
                    {"id": "gig-ilha", "name": "Ilha"},
                ],
            }
        )
        self.assertEqual(target["kind"], "map")
        point = next_image_target(
            {
                "media": {"hero_url": "/h.png", "map_url": "/m.png"},
                "points": [{"id": "gig-ilha", "name": "Ilha"}],
            }
        )
        self.assertEqual(point["kind"], "point")
        self.assertEqual(point["point_id"], "gig-ilha")
        self.assertTrue(point_matches({"id": "gig-ilha", "name": "Jardim Guanabara"}, "jardim-guanabara"))

    def test_normalize_keeps_pipeline_and_image_model(self):
        payload = normalize_payload(
            {
                "media": {
                    "hero_url": "/h.png",
                    "image_model": "google/gemini-3-pro-image",
                    "image_resolution": "1K",
                    "images": [{"id": "hero", "role": "hero", "url": "/h.png"}],
                },
                "pipeline": {
                    "steps": ["research", "images"],
                    "models": {"image": "google/gemini-3-pro-image"},
                    "warnings": ["Sem coordenada: X."],
                },
            }
        )
        self.assertEqual(payload["media"]["image_model"], "google/gemini-3-pro-image")
        self.assertEqual(payload["media"]["images"][0]["url"], "/h.png")
        self.assertIn("research", payload["pipeline"]["steps"])
        self.assertEqual(payload["pipeline"]["warnings"][0], "Sem coordenada: X.")

    def test_apply_images_next_generates_only_one(self):
        row = {
            "id": 9,
            "slug": "galeao",
            "code": "GIG",
            "title": "Galeão",
            "city": "rj",
            "status": "draft",
            "payload": normalize_payload(
                {
                    "geo": {"lat": -22.81, "lng": -43.25},
                    "points": [{"id": "gig-t2", "name": "T2", "kind": "terminal", "lat": -22.81, "lng": -43.25}],
                }
            ),
        }

        def _save(_id, record):
            row.update(record)
            return row

        with patch("aicentralv2.places.service.get_by_id", return_value=row), patch(
            "aicentralv2.places.service.update_place", side_effect=_save
        ), patch(
            "aicentralv2.places.service.generate_place_images",
            return_value={"hero_url": "/static/hero.png", "usages": [{"step": "image-hero", "label": "Hero", "usage": {"cost": 0.2}}]},
        ) as gen_place, patch(
            "aicentralv2.places.service.generate_point_images"
        ) as gen_point:
            saved = apply_images(9, kind="next")
        gen_place.assert_called_once()
        self.assertEqual(gen_place.call_args.kwargs.get("kind") or gen_place.call_args[1].get("kind"), "hero")
        gen_point.assert_not_called()
        self.assertEqual(saved["media"]["hero_url"], "/static/hero.png")
        self.assertAlmostEqual(saved["ai_cost_usd"], 0.2)
        self.assertEqual(saved["image_job"]["kind"], "hero")

    def test_apply_images_continues_when_one_point_fails(self):
        row = {
            "id": 9,
            "slug": "galeao",
            "code": "GIG",
            "title": "Galeão",
            "city": "rj",
            "status": "draft",
            "payload": normalize_payload(
                {
                    "geo": {"lat": -22.81, "lng": -43.25},
                    "points": [
                        {"id": "gig-t2", "name": "T2", "kind": "terminal", "lat": -22.81, "lng": -43.25},
                        {"id": "gig-ilha", "name": "Ilha", "kind": "halo", "lat": -22.81, "lng": -43.20},
                    ],
                }
            ),
        }
        generated = [
            {"id": "gig-t2", "name": "T2", "image_url": "/static/t2.png"},
            {"id": "gig-ilha", "name": "Ilha", "error": "falhou"},
        ]
        with patch("aicentralv2.places.service.get_by_id", return_value=row), patch(
            "aicentralv2.places.service.update_place", side_effect=lambda _id, record: record
        ), patch(
            "aicentralv2.places.service.generate_place_images",
            return_value={"hero_url": "/static/hero.png"},
        ), patch(
            "aicentralv2.places.service.generate_point_images",
            return_value=generated,
        ):
            saved = apply_images(9, kind="all")
        self.assertEqual(saved["images"]["hero_url"], "/static/hero.png")
        self.assertEqual(saved["images"]["spec"]["model"], "bytedance-seed/seedream-5-0-lite")
        self.assertTrue(any(item["id"] == "gig-t2" for item in saved["images"]["points"]))
        self.assertTrue(any("falhou" in item for item in saved["images"]["errors"]))

    def test_apply_import_returns_fiche_and_pipeline(self):
        row = {
            "id": 9,
            "slug": "galeao",
            "code": "GIG",
            "title": "Galeão",
            "city": "rj",
            "status": "draft",
            "payload": normalize_payload({"geo": {"lat": -22.81, "lng": -43.25}}),
        }

        def _save(_id, record):
            row.update(record)
            return row

        with patch("aicentralv2.places.service.apply_research", return_value={**serialize(row), "suggested_points": []}), patch(
            "aicentralv2.places.service.get_by_id", return_value=row
        ), patch("aicentralv2.places.service.update_place", side_effect=_save), patch(
            "aicentralv2.places.service.finalize_import",
            return_value={"model": "openai/gpt-5-mini", "review": "ok", "changes": ["fechou"], "points": []},
        ), patch(
            "aicentralv2.places.service.refine_generated_fiche",
            return_value={
                "model": "openai/gpt-5-mini",
                "subtitle": "T2 na Ilha",
                "offer": {"lead": "Compre o T2", "lines": [{"title": "No T2", "body": "Saguão."}]},
                "points": [
                    {"name": "Terminal T2", "kind": "terminal", "commercial": "Saguão."},
                    {"name": "Base Aérea do Galeão", "kind": "marco"},
                ],
            },
        ), patch(
            "aicentralv2.places.pipeline.geocode_one",
            return_value={"lat": -22.811, "lng": -43.250, "title": "T2"},
        ), patch(
            "aicentralv2.places.service.polish_one_page",
            return_value={"subtitle": "T2 na Ilha do Governador", "offer": {"lead": "Compre o T2", "lines": []}, "points": []},
        ):
            saved = apply_import(9)
        self.assertEqual(saved["fiche"]["identity"]["subtitle"], "T2 na Ilha do Governador")
        self.assertEqual(saved["fiche"]["images"]["spec"]["model"], "bytedance-seed/seedream-5-0-lite")
        self.assertIn("refine", saved["pipeline"]["steps"])
        self.assertIn("polish", saved["pipeline"]["steps"])
        self.assertTrue(any("Base" in item for item in saved["pipeline"]["warnings"]))
        self.assertEqual(saved["review_changes"], ["fechou"])


class PlacesPublicRoutesTest(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=str(ROOT / "aicentralv2" / "templates"),
            static_folder=str(ROOT / "aicentralv2" / "static"),
        )
        app.config.update(TESTING=True, SECRET_KEY="places-test")
        app.register_blueprint(places_bp)
        self.client = app.test_client()
        self.place = serialize(dict(SANTOS_DUMONT, id=3, preview_token="preview-sdu", status="published"))

    def test_public_index_renders_seed(self):
        with patch("aicentralv2.places.service.public_catalog", return_value=[self.place]):
            response = self.client.get("/places/p")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Santos Dumont", html)
        self.assertIn("95–150 mil", html)
        self.assertIn("cc-air-code", html)
        self.assertIn("SDU", html)
        self.assertNotIn("sdu-hero.jpg", html)
        self.assertNotIn("--cx-", html)

    def test_public_place_renders_catchment(self):
        with patch("aicentralv2.places.service.public_place", return_value=self.place), patch(
            "aicentralv2.places.service.public_catalog", return_value=[self.place]
        ):
            response = self.client.get("/places/p/santos-dumont")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Quem vive no entorno", html)
        self.assertIn("96 mil", html)
        self.assertIn("Ir para o mapa", html)
        self.assertIn("O que você compra", html)
        self.assertIn("O SDU liga hotel", html)
        self.assertIn("cc-map-label", html)
        self.assertIn("4 semanas no halo", html)
        self.assertNotIn("Não some ao terminal", html)
        self.assertIn("Como o número é feito", html)
        self.assertIn("Quem a campanha atinge", html)
        self.assertNotIn("Página única", html)
        self.assertNotIn("Plano completo", html)
        self.assertNotIn("geofence", html.lower())
        self.assertIn("cc_logo.png", html)
        self.assertIn("cc-map", html)
        self.assertIn("cc-foot", html)
        self.assertNotIn("proposta", html.lower())
        self.assertNotIn("Falar com especialista", html)
        self.assertNotIn("cc-inquiry", html)
        self.assertNotIn("Fraunces", html)
        self.assertNotIn("CentralX", html)
        self.assertNotIn("base_erp", html)

    def test_legacy_plan_url_redirects_to_public_place(self):
        response = self.client.get("/places/p/santos-dumont/plano")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.headers["Location"].endswith("/places/p/santos-dumont"))

    def test_public_routes_do_not_require_login(self):
        with patch("aicentralv2.places.service.public_catalog", return_value=[self.place]):
            index = self.client.get("/places/p")
        with patch("aicentralv2.places.service.public_place", return_value=self.place), patch(
            "aicentralv2.places.service.public_catalog", return_value=[self.place]
        ):
            page = self.client.get("/places/p/santos-dumont")
        self.assertEqual(index.status_code, 200)
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("/login", page.headers.get("Location", ""))

    def test_public_place_shows_point_gallery_and_map_art(self):
        place = dict(self.place)
        media = dict(place.get("media") or {})
        media["map_url"] = "/static/images/places/sdu-map.jpg"
        place["media"] = media
        place["points"] = [
            {
                **(place.get("points") or [{}])[0],
                "name": "Terminal Santos Dumont",
                "kind": "terminal",
                "kind_label": "Terminal",
                "lat": -22.91,
                "lng": -43.16,
                "image_url": "/static/images/places/sdu-hero.jpg",
            }
        ]
        with patch("aicentralv2.places.service.public_place", return_value=place), patch(
            "aicentralv2.places.service.public_catalog", return_value=[place]
        ):
            response = self.client.get("/places/p/santos-dumont")
        html = response.get_data(as_text=True)
        self.assertIn("Como é o ponto", html)
        self.assertIn("cc-gallery", html)
        self.assertIn("cc-gallery-cap", html)
        self.assertIn("sdu-hero.jpg", html)
        self.assertNotIn("<figcaption>", html)
        self.assertNotIn("cc-map-art", html)
        self.assertNotIn("cc-docs", html)

    def test_confins_public_shows_validate_and_offer(self):
        place = serialize(dict(CONFINS, id=1, preview_token="preview-cnf", status="published"))
        with patch("aicentralv2.places.service.public_place", return_value=place), patch(
            "aicentralv2.places.service.public_catalog", return_value=[place]
        ):
            response = self.client.get("/places/p/confins")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("A validar", html)
        self.assertIn("Na estrada", html)
        self.assertIn("cnf-internacional", html)


if __name__ == "__main__":
    unittest.main()
