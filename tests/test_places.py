import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from aicentralv2.places.brand import PUBLIC_TOKENS, zone_color
from aicentralv2.places.catalog import (
    CONGONHAS,
    CONFINS,
    DIAMOND_MALL,
    GALEAO,
    IGUATEMI_SP,
    EXPOMINAS,
    IBIRAPUERA,
    SANTOS_DUMONT,
    SEED_PLACES,
)
from aicentralv2.places.venues import VENUE_PLACES
from aicentralv2.places.repository import PlacesError, inquiry_payload
from aicentralv2.places.routes import bp as places_bp
from aicentralv2.places.research import (
    ENRICH_MODEL,
    FINALIZE_MODEL,
    ResearchError,
    enrich_points,
    geocode_one,
    polish_one_page,
    refine_generated_fiche,
    search_places,
)
from aicentralv2.places.images import (
    _hero_prompt,
    _point_prompt,
    generate_place_images,
    next_image_target,
    point_matches,
)
from aicentralv2.places.visual_refs import (
    _score,
    official_pages,
    scrape_page_images,
    search_visual_refs,
    select_gallery,
    selected_gallery_refs,
    usable_image_url,
    visual_query,
)
from aicentralv2.places.pipeline import assemble_fiche, fiche_output
from aicentralv2.places.schema import (
    directory_card,
    featured_card,
    format_usd,
    match_directory,
    normalize_payload,
    public_view,
    sum_zone_reaches,
)
from aicentralv2.places.service import (
    apply_enrich,
    apply_images,
    apply_import,
    collect_place_gallery,
    merge_enrich_points,
    select_place_gallery,
    serialize,
)
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
            [item["slug"] for item in SEED_PLACES if item["place_type"] == "aeroporto"],
            ["confins", "congonhas", "santos-dumont", "galeao"],
        )

    def test_seed_has_shoppings_and_event_venues(self):
        shoppings = [item["slug"] for item in SEED_PLACES if item["place_type"] == "shopping"]
        events = [item["slug"] for item in SEED_PLACES if item["place_type"] == "evento"]
        self.assertIn("diamond-mall", shoppings)
        self.assertIn("iguatemi-sao-paulo", shoppings)
        self.assertIn("bh-shopping", shoppings)
        self.assertIn("barra-shopping", shoppings)
        self.assertIn("ibirapuera", events)
        self.assertIn("expominas", events)
        self.assertIn("maracana", events)
        self.assertGreaterEqual(len(shoppings), 10)
        self.assertGreaterEqual(len(events), 6)
        self.assertEqual(IBIRAPUERA["payload"]["metrics"]["passengers"]["label"], "17 mi")
        self.assertEqual(DIAMOND_MALL["payload"]["metrics"]["passengers"]["value"], 5_400_000)

    def test_each_city_has_at_least_five_venues(self):
        venues = [item for item in SEED_PLACES if item["place_type"] in ("shopping", "evento")]
        for city in ("bh", "sp", "rj"):
            self.assertGreaterEqual(len([item for item in venues if item["city"] == city]), 5)

    def test_places_carry_defense_and_four_week_investment(self):
        for item in SEED_PLACES:
            payload = item["payload"]
            self.assertTrue(payload["investment"]["label"])
            self.assertTrue(all(point["investment"] for point in payload["points"]))
            self.assertTrue(all(point["defense"] for point in payload["points"]))
        for item in VENUE_PLACES:
            self.assertTrue(item["payload"]["defense"]["lead"])
            self.assertTrue(item["payload"]["media"]["hero_url"].startswith("/static/images/places/gallery/"))
            self.assertTrue(item["payload"]["points"][0]["image_url"].startswith("/static/images/places/gallery/"))
            hero = ROOT / "aicentralv2" / item["payload"]["media"]["hero_url"].lstrip("/")
            self.assertTrue(hero.exists(), hero)

    def test_anac_2025_passenger_labels(self):
        self.assertEqual(
            CONFINS["payload"]["media"]["hero_url"],
            "/static/images/places/generated/confins-hero-bad23d6b.png",
        )
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

    def test_points_sit_on_the_site_not_the_arp(self):
        for item in SEED_PLACES:
            scopes = []
            for point in item["payload"]["points"]:
                self.assertIn(point["scope"], ("internal", "external"))
                self.assertTrue(point["scope_label"])
                if point["kind"] == "halo":
                    self.assertEqual(point["scope"], "external")
                else:
                    self.assertEqual(point["scope"], "internal")
                scopes.append(point["scope"])
            if "external" in scopes:
                last_internal = max(i for i, scope in enumerate(scopes) if scope == "internal")
                first_external = min(i for i, scope in enumerate(scopes) if scope == "external")
                self.assertLess(last_internal, first_external)

        terminal = next(item for item in CONFINS["payload"]["points"] if item["id"] == "cnf-terminal")
        self.assertAlmostEqual(terminal["lat"], -19.630503, places=4)
        self.assertGreater(abs(terminal["lat"] - (-19.624445)), 0.004)

        sdu = next(item for item in SANTOS_DUMONT["payload"]["points"] if item["id"] == "sdu-terminal")
        self.assertGreater(abs(sdu["lng"] - (-43.163056)), 0.003)

        gig = next(item for item in GALEAO["payload"]["points"] if item["id"] == "gig-terminal")
        self.assertGreater(abs(gig["lng"] - (-43.2585631)), 0.008)

        mall = DIAMOND_MALL["payload"]["geo"]
        self.assertGreater(abs(mall["lat"] - (-19.9376)), 0.006)
        self.assertEqual(DIAMOND_MALL["payload"]["catchment"]["neighborhoods"][0], "Santo Agostinho")

        expo = next(item for item in EXPOMINAS["payload"]["points"] if item["id"] == "exp-pavilhao")
        self.assertGreater(abs(expo["lng"] - (-44.0005)), 0.008)

        lima = next(item for item in IGUATEMI_SP["payload"]["points"] if item["id"] == "igt-faria-lima")
        self.assertEqual(lima["scope"], "external")
        self.assertGreater(abs(lima["lat"] - IGUATEMI_SP["payload"]["geo"]["lat"]), 0.006)

    def test_public_view_labels_city_and_type(self):
        view = public_view(CONGONHAS)
        self.assertEqual(view["city_label"], "São Paulo")
        self.assertEqual(view["type_label"], "Aeroporto")
        self.assertTrue(view["catchment"]["neighborhoods"])
        self.assertEqual(view["offer"]["lines"][0]["title"], "No T1")

    def test_each_airport_has_its_own_offer(self):
        airports = [item for item in SEED_PLACES if item["place_type"] == "aeroporto"]
        leads = {item["payload"]["offer"]["lead"] for item in airports}
        self.assertEqual(len(leads), 4)
        for item in airports:
            self.assertGreaterEqual(len(item["payload"]["offer"]["lines"]), 3)
            format_sets = {tuple(point["formats"]) for point in item["payload"]["points"]}
            self.assertGreater(len(format_sets), 1)
            self.assertTrue(all(point.get("image_url") for point in item["payload"]["points"]))

    def test_directory_card_carries_geo_and_search_fields(self):
        confins = directory_card(serialize(dict(CONFINS, id=1, preview_token="x", status="published")))
        sdu = directory_card(serialize(dict(SANTOS_DUMONT, id=3, preview_token="y", status="published")))
        self.assertEqual(confins["code"], "CNF")
        self.assertAlmostEqual(confins["lat"], -19.630503)
        self.assertTrue(confins["href"].endswith("/places/p/confins"))
        self.assertEqual(featured_card([sdu, confins])["slug"], "confins")
        self.assertTrue(match_directory(confins, "cnf"))
        self.assertTrue(match_directory(confins, "Belo"))
        self.assertFalse(match_directory(confins, "cnf", "shopping"))
        self.assertTrue(match_directory(sdu, "", "aeroporto"))

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
        self.assertIn("gpt-5", ENRICH_MODEL)
        self.assertTrue(callable(polish_one_page))
        self.assertTrue(callable(refine_generated_fiche))
        self.assertTrue(callable(enrich_points))

    def test_enrich_points_reads_open_inventory(self):
        place = serialize(dict(IGUATEMI_SP, id=6, preview_token="preview-igt", status="published"))
        with patch("aicentralv2.places.research.chat_completion") as chat:
            chat.return_value = {
                "model": "openai/gpt-5.4",
                "usage": {},
                "message": {
                    "content": (
                        '{"lead":"No mall o celular é Instagram.",'
                        '"notes":"Praça a validar.",'
                        '"points":[{"id":"igt-mall","apps":[{"name":"Instagram","why":"Stories"}],'
                        '"portals":[{"name":"G1","why":"intervalo"}],'
                        '"formats":["Display no app","Banner","Portais"]}]}'
                    )
                },
            }
            result = enrich_points(place)
        self.assertEqual(chat.call_args.kwargs["model"], ENRICH_MODEL)
        self.assertEqual(result["points"][0]["id"], "igt-mall")
        self.assertEqual(result["points"][0]["apps"][0]["name"], "Instagram")
        self.assertEqual(result["points"][0]["formats"], ["Display no app", "Portais"])
        self.assertNotIn("Banner", result["points"][0]["formats"])

    def test_enrich_points_needs_a_point(self):
        with self.assertRaisesRegex(ResearchError, "ponto"):
            enrich_points({"title": "Vazio", "payload": {}})

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
        self.assertIn("cc-hero", css)
        self.assertIn("cc-desk", css)
        self.assertIn("cc-sheet", css)
        self.assertIn("cc-chips", css)
        self.assertIn("cc-inventory", css)
        self.assertIn("cc-night", css)
        self.assertIn("cc-find", css)
        self.assertIn("cc-atlas", css)
        self.assertIn("cc-mesa", css)
        self.assertIn(".cc-pick[hidden]", css)
        self.assertIn("cc-point-photo", css)
        self.assertIn("cc-picks", css)
        self.assertIn("cc-pick-code", css)
        self.assertIn("display: block", css)
        self.assertIn("cc-board", css)
        self.assertIn("cc-mega", css)
        self.assertIn("cc-menu-btn", css)
        self.assertIn("cc-scrim", css)
        self.assertIn("position: sticky", css)
        self.assertIn("cursor: pointer", css)
        self.assertIn("cc-flag", css)
        self.assertIn("cc-flag[hidden]", css)
        self.assertIn("cc-scope", css)
        self.assertIn("cc-defense", css)
        self.assertIn("cc-fiche", css)
        self.assertIn('data-scope="external"', css)
        self.assertIn("minmax(0, 36rem)", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("100svh", css)
        self.assertIn("leaflet-container", css)
        self.assertNotIn("cc-gallery", css)
        self.assertNotIn("cc-air-code", css)
        self.assertNotIn(".cc-docs", css)
        self.assertNotIn(".cc-overlay", css)

    def test_public_map_uses_satellite(self):
        js = PUBLIC_JS.read_text(encoding="utf-8")
        self.assertIn("World_Imagery", js)
        self.assertNotIn("tile.openstreetmap.org", js)
        self.assertIn("is-in", js)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("ArrowRight", js)
        self.assertIn("cc-mega", js)
        self.assertIn("Escape", js)
        self.assertIn("is-mega", js)
        self.assertIn("requestClose", js)
        self.assertIn("paintChannels", js)
        self.assertIn("channelItems", js)
        self.assertIn("zoneApps", js)
        self.assertIn("zonePortals", js)
        self.assertIn("zoneScope", js)
        self.assertIn("zoneInvest", js)
        self.assertIn("data-scope", js)
        self.assertIn("bootIndex", js)
        self.assertIn("URLSearchParams", js)
        self.assertIn('params.set("q"', js)
        self.assertIn('params.set("tipo"', js)

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
        self.assertIn(".pl-gallery", css)
        self.assertIn(".pl-report", css)
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
        self.assertIn('id="pl-enrich"', form)
        self.assertIn("Enriquecer pontos", form)
        self.assertIn("data-inventory-report", form)
        self.assertIn("Gerar fotos que faltam", form)
        self.assertIn("Firecrawl", form)
        self.assertIn("Firecrawl", js)
        self.assertIn("pl-collect-gallery", form)
        self.assertIn("data-gallery-grid", form)
        self.assertIn("/gallery", js)
        self.assertIn("reference_ids", js)
        self.assertNotIn("pl-steps", form)
        self.assertNotIn("GPT Image 2", form)
        self.assertIn("runQueue", js)
        self.assertIn('kind: job.kind', js)
        self.assertIn("Fechando a ficha", js)
        self.assertIn("/enrich", js)
        self.assertIn("pl-point-extra", js)
        self.assertIn("renderInventory", js)
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

    def test_normalize_keeps_apps_portals_and_inventory(self):
        payload = normalize_payload(
            {
                "points": [
                    {
                        "id": "igt-mall",
                        "name": "Mall",
                        "kind": "marco",
                        "lat": -23.5768,
                        "lng": -46.687,
                        "reach": "150–230 mil",
                        "formats": ["Display no app", "Portais"],
                        "apps": [{"name": "Instagram", "why": "Stories no mall", "confidence": "estimate"}],
                        "portals": [["G1", "intervalo no café"]],
                    }
                ],
                "inventory": {
                    "lead": "No mall o celular é Instagram e G1.",
                    "notes": "A validar o mix da praça.",
                    "model": "openai/gpt-5.4",
                    "reviewed_at": "2026-09-14T12:00:00+00:00",
                },
            }
        )
        point = payload["points"][0]
        self.assertEqual(point["apps"][0]["name"], "Instagram")
        self.assertEqual(point["apps"][0]["why"], "Stories no mall")
        self.assertEqual(point["portals"][0]["name"], "G1")
        self.assertEqual(point["portals"][0]["why"], "intervalo no café")
        self.assertEqual(payload["inventory"]["lead"], "No mall o celular é Instagram e G1.")
        view = public_view({"slug": "iguatemi-sao-paulo", "title": "Iguatemi", "payload": payload})
        self.assertEqual(view["inventory"]["model"], "openai/gpt-5.4")
        self.assertEqual(view["points"][0]["apps"][0]["name"], "Instagram")

    def test_merge_enrich_keeps_coords_and_reach(self):
        merged = merge_enrich_points(
            [
                {
                    "id": "igt-mall",
                    "name": "Mall",
                    "lat": -23.5768,
                    "lng": -46.687,
                    "reach": "150–230 mil",
                    "image_url": "/mall.png",
                    "formats": ["Display"],
                }
            ],
            [
                {
                    "id": "igt-mall",
                    "apps": [{"name": "Instagram", "why": "Stories", "confidence": "estimate"}],
                    "portals": [{"name": "G1", "why": "intervalo", "confidence": "estimate"}],
                    "formats": ["Display no app", "Portais"],
                }
            ],
        )
        self.assertEqual(merged[0]["lat"], -23.5768)
        self.assertEqual(merged[0]["reach"], "150–230 mil")
        self.assertEqual(merged[0]["image_url"], "/mall.png")
        self.assertEqual(merged[0]["apps"][0]["name"], "Instagram")
        self.assertEqual(merged[0]["formats"], ["Display no app", "Portais"])
        by_name = merge_enrich_points(
            [{"id": "igt-mall", "name": "Mall", "lat": -23.57}],
            [{"name": "Mall", "apps": [{"name": "iFood", "why": "praça", "confidence": "estimate"}]}],
        )
        self.assertEqual(by_name[0]["apps"][0]["name"], "iFood")
        self.assertEqual(by_name[0]["lat"], -23.57)

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

    def test_visual_query_confins_asks_for_the_real_facade(self):
        query = visual_query(
            {"title": "Confins", "code": "CNF", "city": "bh", "place_type": "aeroporto"},
            kind="hero",
        )
        self.assertIn("Confins", query)
        self.assertIn("CNF", query)
        self.assertIn("fachada", query)
        self.assertIn("BH Airport", query)
        interior = visual_query(
            {"title": "Confins", "code": "CNF", "city": "bh", "place_type": "aeroporto"},
            kind="point",
            point={"name": "Terminal", "kind": "terminal"},
        )
        self.assertIn("interior", interior)
        halo = visual_query(
            {"title": "Confins", "code": "CNF", "city": "bh", "place_type": "aeroporto"},
            kind="point",
            point={"name": "MG-010", "kind": "halo"},
        )
        self.assertIn("bairro", halo)
        self.assertNotIn("interior", halo)

    def test_visual_query_iguatemi_asks_faria_lima_not_jk(self):
        query = visual_query(
            {
                "title": "Iguatemi São Paulo",
                "code": "IGT",
                "city": "sp",
                "city_label": "São Paulo",
                "place_type": "shopping",
            },
            kind="hero",
        )
        self.assertIn("Faria Lima", query)
        self.assertIn("Jardim Paulistano", query)
        self.assertNotIn("JK", query)

    def test_visual_refs_penalize_jk_iguatemi(self):
        jk = _score({"url": "https://cdn.example/jk-iguatemi-fachada.jpg", "title": "JK Iguatemi"})
        real = _score({"url": "https://cdn.example/iguatemi-faria-lima.jpg", "title": "Iguatemi Faria Lima"})
        self.assertLess(jk, real)

    def test_visual_refs_skip_instagram_widgets(self):
        self.assertFalse(usable_image_url("https://lookaside.instagram.com/seo/foo"))
        self.assertTrue(usable_image_url("https://images.adsttc.com/media/confins.jpg"))
        self.assertTrue(usable_image_url("data:image/jpeg;base64,abc"))
        self.assertTrue(usable_image_url("/static/images/places/gallery/cnf.jpg"))

    def test_search_visual_refs_without_key_is_empty(self):
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": ""}, clear=False):
            self.assertEqual(
                search_visual_refs({"title": "Confins", "code": "CNF", "city": "bh"}),
                [],
            )

    def test_hero_prompt_confins_forbids_wavy_roof(self):
        prompt = _hero_prompt("Confins", "Belo Horizonte", "CNF")
        self.assertIn("flat", prompt.lower())
        self.assertIn("Hadid", prompt)
        self.assertIn("Bacco", prompt)

    def test_generate_place_images_uses_firecrawl_refs(self):
        import base64
        import tempfile

        captured = {}

        def fake_image(prompt, **kwargs):
            captured["prompt"] = prompt
            captured["refs"] = kwargs.get("input_references")
            return {"b64_json": base64.b64encode(b"png-bytes").decode("ascii"), "usage": {}}

        with tempfile.TemporaryDirectory() as tmp, patch(
            "aicentralv2.places.images.resolve_generation_refs",
            return_value=[{"url": "https://images.adsttc.com/confins.jpg", "title": "CNF", "query": "Confins"}],
        ), patch("aicentralv2.places.images.generate_image", side_effect=fake_image), patch(
            "aicentralv2.places.images._art_dir",
            return_value=tmp,
        ):
            result = generate_place_images(
                {"title": "Confins", "code": "CNF", "slug": "confins", "city": "bh", "place_type": "aeroporto"},
                kind="hero",
            )
        self.assertEqual(captured["refs"], ["https://images.adsttc.com/confins.jpg"])
        self.assertIn("reference photos", captured["prompt"])
        self.assertTrue(result["hero_url"].startswith("/static/images/places/generated/confins-hero-"))
        self.assertEqual(result["visual_refs"][0]["url"], "https://images.adsttc.com/confins.jpg")

    def test_generate_place_images_without_refs_still_renders(self):
        import base64
        import tempfile

        captured = {}

        def fake_image(prompt, **kwargs):
            captured["prompt"] = prompt
            captured["refs"] = kwargs.get("input_references")
            return {"b64_json": base64.b64encode(b"png-bytes").decode("ascii"), "usage": {}}

        with tempfile.TemporaryDirectory() as tmp, patch(
            "aicentralv2.places.images.resolve_generation_refs",
            return_value=[],
        ), patch("aicentralv2.places.images.generate_image", side_effect=fake_image), patch(
            "aicentralv2.places.images._art_dir",
            return_value=tmp,
        ):
            result = generate_place_images(
                {"title": "Confins", "code": "CNF", "slug": "confins", "city": "bh"},
                kind="hero",
            )
        self.assertFalse(captured["refs"])
        self.assertNotIn("reference photos", captured["prompt"])
        self.assertNotIn("visual_refs", result)

    def test_normalize_keeps_visual_refs(self):
        payload = normalize_payload(
            {
                "media": {
                    "hero_url": "/h.png",
                    "visual_refs": [{"kind": "hero", "url": "https://images.adsttc.com/confins.jpg", "title": "CNF"}],
                }
            }
        )
        self.assertEqual(payload["media"]["visual_refs"][0]["url"], "https://images.adsttc.com/confins.jpg")
        self.assertEqual(payload["media"]["visual_refs"][0]["kind"], "hero")

    def test_normalize_keeps_gallery(self):
        payload = normalize_payload(
            {
                "media": {
                    "gallery": [
                        {
                            "id": "cnf-hero",
                            "kind": "hero",
                            "url": "/static/images/places/gallery/cnf.jpg",
                            "source_url": "https://images.adsttc.com/confins.jpg",
                            "selected": True,
                        }
                    ]
                }
            }
        )
        self.assertEqual(payload["media"]["gallery"][0]["id"], "cnf-hero")
        self.assertTrue(payload["media"]["gallery"][0]["selected"])

    def test_official_pages_cover_seed_codes(self):
        self.assertTrue(official_pages({"code": "CNF"}))
        self.assertIn("bh-airport", official_pages({"code": "CNF"})[0])
        for item in SEED_PLACES:
            self.assertTrue(official_pages({"code": item["code"]}), item["code"])

    def test_scrape_page_images_reads_og(self):
        class Fake:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "data": {
                        "metadata": {"ogImage": "https://images.adsttc.com/confins.jpg", "title": "CNF"},
                        "markdown": "![hall](https://images.adsttc.com/saguao.jpg)",
                    }
                }

        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "fc-test"}, clear=False), patch(
            "aicentralv2.places.visual_refs.requests.post", return_value=Fake()
        ):
            refs = scrape_page_images("https://www.bh-airport.com.br/", kind="hero")
        urls = [item["url"] for item in refs]
        self.assertIn("https://images.adsttc.com/confins.jpg", urls)
        self.assertIn("https://images.adsttc.com/saguao.jpg", urls)

    def test_selected_gallery_wins_over_search(self):
        place = {
            "title": "Confins",
            "code": "CNF",
            "media": {
                "gallery": [
                    {
                        "id": "pick",
                        "kind": "hero",
                        "url": "/static/images/places/gallery/cnf.jpg",
                        "selected": True,
                    }
                ]
            },
        }
        picked = selected_gallery_refs(place, kind="hero")
        self.assertEqual(picked[0]["id"], "pick")

    def test_select_gallery_marks_one_hero(self):
        rows = select_gallery(
            [
                {"id": "a", "kind": "hero", "url": "/a.jpg", "selected": True},
                {"id": "b", "kind": "hero", "url": "/b.jpg", "selected": False},
            ],
            "b",
        )
        self.assertFalse(rows[0]["selected"])
        self.assertTrue(rows[1]["selected"])

    def test_collect_and_select_gallery_persist(self):
        row = {
            "id": 9,
            "slug": "confins",
            "code": "CNF",
            "title": "Confins",
            "city": "bh",
            "status": "draft",
            "payload": normalize_payload({}),
        }

        def _save(_id, record):
            row["payload"] = record["payload"]
            return row

        incoming = [
            {
                "id": "pick",
                "kind": "hero",
                "url": "/static/images/places/gallery/cnf.jpg",
                "source_url": "https://images.adsttc.com/confins.jpg",
                "title": "CNF",
                "query": "Confins",
            }
        ]
        with patch("aicentralv2.places.service.get_by_id", return_value=row), patch(
            "aicentralv2.places.service.update_place", side_effect=_save
        ), patch("aicentralv2.places.service.collect_visual_refs", return_value=incoming):
            saved = collect_place_gallery(9, kind="hero")
        self.assertEqual(saved["media"]["gallery"][0]["id"], "pick")
        self.assertTrue(saved["media"]["gallery"][0]["selected"])
        with patch("aicentralv2.places.service.get_by_id", return_value=row), patch(
            "aicentralv2.places.service.update_place", side_effect=_save
        ):
            selected = select_place_gallery(9, "pick")
        self.assertTrue(selected["media"]["gallery"][0]["selected"])

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
            return_value={
                "hero_url": "/static/hero.png",
                "visual_refs": [{"kind": "hero", "url": "https://images.adsttc.com/gig.jpg"}],
                "usages": [{"step": "image-hero", "label": "Hero", "usage": {"cost": 0.2}}],
            },
        ) as gen_place, patch(
            "aicentralv2.places.service.generate_point_images"
        ) as gen_point:
            saved = apply_images(9, kind="next")
        gen_place.assert_called_once()
        self.assertEqual(gen_place.call_args.kwargs.get("kind") or gen_place.call_args[1].get("kind"), "hero")
        gen_point.assert_not_called()
        self.assertEqual(saved["media"]["hero_url"], "/static/hero.png")
        self.assertEqual(saved["media"]["visual_refs"][0]["url"], "https://images.adsttc.com/gig.jpg")
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

    def test_apply_enrich_merges_inventory_without_moving_the_point(self):
        row = {
            "id": 6,
            "slug": "iguatemi-sao-paulo",
            "code": "IGT",
            "title": "Iguatemi São Paulo",
            "city": "sp",
            "status": "published",
            "payload": normalize_payload(
                {
                    "geo": {"lat": -23.5768, "lng": -46.687},
                    "points": [
                        {
                            "id": "igt-mall",
                            "name": "Mall",
                            "kind": "marco",
                            "lat": -23.5768,
                            "lng": -46.687,
                            "reach": "150–230 mil",
                            "image_url": "/mall.png",
                        }
                    ],
                }
            ),
        }

        def _save(_id, record):
            row.update(record)
            return row

        with patch("aicentralv2.places.service.get_by_id", return_value=row), patch(
            "aicentralv2.places.service.update_place", side_effect=_save
        ), patch(
            "aicentralv2.places.service.enrich_points",
            return_value={
                "model": "openai/gpt-5.4",
                "usage": {"cost": 0.15},
                "lead": "No mall o celular é Instagram e G1.",
                "notes": "Praça ficou a validar.",
                "points": [
                    {
                        "id": "igt-mall",
                        "apps": [{"name": "Instagram", "why": "Stories no mall", "confidence": "estimate"}],
                        "portals": [{"name": "G1", "why": "intervalo", "confidence": "estimate"}],
                        "formats": ["Display no app", "Portais"],
                    }
                ],
            },
        ):
            saved = apply_enrich(6)
        point = saved["points"][0]
        self.assertEqual(point["lat"], -23.5768)
        self.assertEqual(point["reach"], "150–230 mil")
        self.assertEqual(point["image_url"], "/mall.png")
        self.assertEqual(point["apps"][0]["name"], "Instagram")
        self.assertEqual(saved["inventory"]["lead"], "No mall o celular é Instagram e G1.")
        self.assertIn("enrich", saved["pipeline"]["steps"])
        self.assertAlmostEqual(saved["ai_cost_usd"], 0.15)

    def test_apply_enrich_rejects_empty_research(self):
        row = {
            "id": 6,
            "slug": "iguatemi-sao-paulo",
            "code": "IGT",
            "title": "Iguatemi São Paulo",
            "city": "sp",
            "status": "published",
            "payload": normalize_payload({
                "points": [{"id": "igt-mall", "name": "Mall", "kind": "marco", "lat": -23.57, "lng": -46.68}],
            }),
        }
        with patch("aicentralv2.places.service.get_by_id", return_value=row), patch(
            "aicentralv2.places.service.enrich_points",
            return_value={"model": "openai/gpt-5.4", "usage": {}, "lead": "", "notes": "", "points": []},
        ):
            with self.assertRaisesRegex(ResearchError, "apps nem portais"):
                apply_enrich(6)


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
        self.assertIn("cc-pick-code", html)
        self.assertIn("cc-board", html)
        self.assertIn("cc-mega", html)
        self.assertIn("Aeroportos", html)
        self.assertIn("Shoppings", html)
        self.assertIn("Parques e eventos", html)
        self.assertIn("SDU", html)
        self.assertIn("santos-dumont-hero", html)
        self.assertIn("cc-find", html)
        self.assertIn("cc-atlas", html)
        self.assertIn("cc-index-data", html)
        self.assertIn("CNF, Iguatemi ou Belo Horizonte", html)
        self.assertIn("O lugar vira audiência.", html)
        self.assertNotIn("Sobre", html)
        self.assertNotIn("Fale conosco", html)
        self.assertNotIn("Ver todos", html)
        self.assertNotIn("20+", html)
        self.assertNotIn("--cx-", html)

    def test_public_place_renders_catchment(self):
        with patch("aicentralv2.places.service.public_place", return_value=self.place), patch(
            "aicentralv2.places.service.public_catalog", return_value=[self.place]
        ):
            response = self.client.get("/places/p/santos-dumont")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("96 mil moram no entorno", html)
        self.assertIn("Ir para o mapa", html)
        self.assertIn("O SDU liga hotel", html)
        self.assertIn("cc-hero", html)
        self.assertIn("cc-desk", html)
        self.assertIn("santos-dumont-hero", html)
        self.assertIn("Isso não é presença no terminal", html)
        self.assertNotIn("Quem vive no entorno", html)
        self.assertNotIn("O que você compra", html)
        self.assertNotIn("Quem a campanha atinge", html)
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

    def test_public_place_shows_point_photo_in_the_sheet(self):
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
        self.assertIn("cc-sheet", html)
        self.assertIn("cc-point-photo", html)
        self.assertIn("sdu-hero.jpg", html)
        self.assertIn("Terminal Santos Dumont", html)
        self.assertNotIn("cc-gallery", html)
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
        self.assertIn("confins-hero-bad23d6b.png", html)
        self.assertIn("A validar", html)
        self.assertIn("MG-010", html)
        self.assertIn("cnf-internacional", html)
        self.assertIn("No sítio", html)
        self.assertIn("-19.630503", html)
        self.assertIn("cc-scope", html)
        self.assertIn("Investimento, 4 semanas", html)
        self.assertIn("R$", html)

    def test_ibirapuera_public_is_an_event_sheet(self):
        place = serialize(dict(IBIRAPUERA, id=7, preview_token="preview-ibi", status="published"))
        with patch("aicentralv2.places.service.public_place", return_value=place), patch(
            "aicentralv2.places.service.public_catalog", return_value=[place]
        ):
            response = self.client.get("/places/p/ibirapuera")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("No Ibirapuera você compra o portão", html)
        self.assertIn("No lugar, 2025", html)
        self.assertIn("A validar", html)
        self.assertIn("ibi-bienal", html)

    def test_iguatemi_public_shows_apps_portals_and_report(self):
        place = serialize(dict(IGUATEMI_SP, id=6, preview_token="preview-igt", status="published"))
        points = list(place.get("points") or [])
        if points:
            points[0] = {
                **points[0],
                "apps": [{"name": "Instagram", "why": "Stories no mall", "confidence": "estimate"}],
                "portals": [{"name": "G1", "why": "intervalo", "confidence": "estimate"}],
            }
        place["points"] = points
        place["inventory"] = {
            "lead": "No Iguatemi o celular é Instagram e G1.",
            "notes": "",
            "model": "openai/gpt-5.4",
            "reviewed_at": "2026-09-14T12:00:00+00:00",
        }
        with patch("aicentralv2.places.service.public_place", return_value=place), patch(
            "aicentralv2.places.service.public_catalog", return_value=[place]
        ):
            response = self.client.get("/places/p/iguatemi-sao-paulo")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("zoneApps", html)
        self.assertIn("zonePortals", html)
        self.assertIn("Instagram", html)
        self.assertIn("G1", html)
        self.assertIn("cc-inventory", html)
        self.assertIn("No Iguatemi o celular é Instagram e G1.", html)
        self.assertIn("igt-mall", html)

    def test_bh_shopping_public_shows_defense_and_photo(self):
        mall = next(item for item in VENUE_PLACES if item["slug"] == "bh-shopping")
        place = serialize(dict(mall, id=20, preview_token="preview-bhs", status="published"))
        with patch("aicentralv2.places.service.public_place", return_value=place), patch(
            "aicentralv2.places.service.public_catalog", return_value=[place]
        ):
            response = self.client.get("/places/p/bh-shopping")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("É o mall regional do sul de BH", html)
        self.assertIn("Investimento, 4 semanas", html)
        self.assertIn("bh-shopping-hero", html)
        self.assertIn("cc-defense", html)
        self.assertNotIn("cc-gallery", html)


if __name__ == "__main__":
    unittest.main()
