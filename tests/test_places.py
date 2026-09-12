import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from aicentralv2.places.brand import PUBLIC_TOKENS, zone_color
from aicentralv2.places.catalog import CONGONHAS, CONFINS, SANTOS_DUMONT, SEED_PLACES
from aicentralv2.places.repository import PlacesError, inquiry_payload
from aicentralv2.places.routes import bp as places_bp
from aicentralv2.places.research import FINALIZE_MODEL, ResearchError, search_places
from aicentralv2.places.schema import normalize_payload, public_view, sum_zone_reaches
from aicentralv2.places.service import serialize
from aicentralv2.places.share import public_path, slugify

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CSS = ROOT / "aicentralv2" / "static" / "css" / "places_public.css"
ADMIN_CSS = ROOT / "aicentralv2" / "static" / "css" / "places.css"


class PlacesCatalogTest(unittest.TestCase):
    def test_seed_has_three_airports(self):
        self.assertEqual(
            [item["slug"] for item in SEED_PLACES],
            ["confins", "congonhas", "santos-dumont"],
        )

    def test_anac_2025_passenger_labels(self):
        self.assertEqual(CONFINS["payload"]["metrics"]["passengers"]["label"], "13,2 mi")
        self.assertEqual(CONFINS["payload"]["metrics"]["passengers"]["value"], 13_183_039)
        self.assertEqual(CONGONHAS["payload"]["metrics"]["passengers"]["label"], "24,6 mi")
        self.assertEqual(CONGONHAS["payload"]["metrics"]["passengers"]["value"], 24_583_610)
        self.assertEqual(SANTOS_DUMONT["payload"]["metrics"]["passengers"]["label"], "6,2 mi")
        self.assertEqual(SANTOS_DUMONT["payload"]["metrics"]["passengers"]["value"], 6_184_233)
        self.assertEqual(SANTOS_DUMONT["payload"]["metrics"]["four_weeks"]["label"], "~476 mil")

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
        self.assertEqual(len(leads), 3)
        for item in SEED_PLACES:
            self.assertGreaterEqual(len(item["payload"]["offer"]["lines"]), 3)
            format_sets = {tuple(point["formats"]) for point in item["payload"]["points"]}
            self.assertGreater(len(format_sets), 1)

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
        self.assertIn(":focus-visible", css)
        self.assertIn("100svh", css)
        self.assertIn("leaflet-container", css)

    def test_admin_css_uses_centralx_tokens(self):
        css = ADMIN_CSS.read_text(encoding="utf-8")
        self.assertIn("--cx-brand", css)
        self.assertNotIn("#0c1a1b", css)

    def test_zone_color_from_brand(self):
        self.assertEqual(zone_color("CORE"), "#167A3A")
        self.assertEqual(PUBLIC_TOKENS["logo"], "/static/images/cc_logo.png")
        self.assertEqual(PUBLIC_TOKENS["font_display"], "Nunito")


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
        self.assertIn("O SDU é o centro", html)
        self.assertIn("cc-map-label", html)
        self.assertIn("4 semanas no halo", html)
        self.assertNotIn("Não some ao terminal", html)
        self.assertIn("Como o número é feito", html)
        self.assertNotIn("geofence", html.lower())
        self.assertIn("cc_logo.png", html)
        self.assertIn("cc-map", html)
        self.assertIn("cc-foot", html)
        self.assertNotIn("proposta", html.lower())
        self.assertNotIn("Falar com especialista", html)
        self.assertNotIn("cc-inquiry", html)
        self.assertNotIn("Fraunces", html)

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
        self.assertIn("sdu-hero.jpg", html)
        self.assertNotIn("cc-map-art", html)

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
