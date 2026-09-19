import unittest

from aicentralv2.smart_planner.catalog import apply_review_defaults, review_score
from aicentralv2.smart_planner.generator import _pack, _places_law
from aicentralv2.smart_planner.helpers import campaign_from_campos
from aicentralv2.smart_planner.mix import allocate
from aicentralv2.smart_planner.one_page import match_pitch
from aicentralv2.smart_planner.places_bridge import (
    apply_places_to_campos,
    resolve_places,
    snapshot_places,
    suggest_places_from_material,
    places_minimum,
)
from aicentralv2.smart_planner.snapshot import build_snapshot


CATALOG = [
    {
        "slug": "confins",
        "title": "Confins",
        "code": "CNF",
        "place_type": "aeroporto",
        "type_label": "Aeroporto",
        "city": "bh",
        "city_label": "Belo Horizonte",
        "aliases": ["confins", "cnf", "bh airport"],
        "metrics": {"addressable": "190–280 mil", "four_weeks": "~1,01 mi"},
        "points": [
            {
                "id": "cnf-terminal",
                "name": "Terminal",
                "kind": "terminal",
                "radius_m": 350,
                "radius_label": "350 m",
                "reach": "190–280 mil",
                "apps": ["Uber"],
                "portals": [],
                "formats": ["Display no app"],
            },
            {
                "id": "cnf-corredor",
                "name": "MG-010",
                "kind": "halo",
                "radius_m": 1200,
                "radius_label": "1,2 km",
                "reach": "80–130 mil",
                "apps": [],
                "portals": [],
                "formats": ["Portais"],
            },
        ],
    },
    {
        "slug": "diamond-mall",
        "title": "Diamond Mall",
        "code": "",
        "place_type": "shopping",
        "type_label": "Shopping",
        "city": "bh",
        "city_label": "Belo Horizonte",
        "aliases": ["diamond mall", "diamond"],
        "metrics": {"addressable": "40–70 mil", "four_weeks": ""},
        "points": [
            {
                "id": "dm-mall",
                "name": "Mall",
                "kind": "marco",
                "radius_m": 180,
                "radius_label": "180 m",
                "reach": "40–70 mil",
                "apps": ["iFood"],
                "portals": [],
                "formats": [],
            }
        ],
    },
]


class PlacesBridgeTest(unittest.TestCase):
    def test_places_minimum_sums_unique_places_not_points(self):
        catalog = [
            {"slug": "a", "title": "A", "points": [{"id": "a-1"}, {"id": "a-2"}], "investment_min_brl": 18000},
            {"slug": "b", "title": "B", "points": [{"id": "b-1"}], "investment_min_brl": 28000},
        ]
        result = places_minimum([
            {"slug": "a", "point_ids": ["a-1", "a-2"]},
            {"slug": "b", "point_ids": ["b-1"]},
        ], catalog)
        self.assertEqual(result["minimum_brl"], 46000)
        self.assertEqual(len(result["items"]), 2)
    def test_drops_invented_slug_and_app(self):
        resolved = resolve_places(
            [{"slug": "aeroporto-inventado", "point_ids": ["gate"], "apps": ["Uber"]}],
            CATALOG,
        )
        self.assertEqual(resolved, [])
        resolved = resolve_places(
            [{"slug": "confins", "point_ids": ["cnf-terminal"], "apps": ["Uber", "AppFake"]}],
            CATALOG,
        )
        self.assertEqual(resolved[0]["slug"], "confins")
        self.assertEqual(resolved[0]["point_ids"], ["cnf-terminal"])
        self.assertEqual(resolved[0]["apps"], ["Uber"])

    def test_matches_point_by_kind(self):
        resolved = resolve_places(
            [{"slug": "confins", "point_ids": ["terminal"], "apps": []}],
            CATALOG,
        )
        self.assertEqual(resolved[0]["point_ids"], ["cnf-terminal"])

    def test_suggests_confins_from_material(self):
        found = suggest_places_from_material("Campanha no terminal de Confins com Uber.", CATALOG)
        self.assertEqual(found[0]["slug"], "confins")

    def test_extract_adds_places_channel_and_blocks_interativos_without_portal(self):
        campos = apply_places_to_campos(
            {
                "canais": ["meta_ads", "interativos"],
                "places": [{"slug": "confins", "point_ids": ["cnf-terminal"], "apps": ["Uber"]}],
                "interativos": {"formats": ["quiz", "hotspot"]},
            },
            CATALOG,
        )
        self.assertIn("places", campos["canais"])
        self.assertNotIn("interativos", campos["canais"])
        self.assertEqual(campos["interativos"]["formats"], [])

    def test_interativos_stay_with_portal(self):
        campos = apply_places_to_campos(
            {
                "canais": ["g1", "interativos"],
                "interativos": {"formats": ["quiz"]},
            },
            CATALOG,
        )
        self.assertIn("interativos", campos["canais"])
        self.assertEqual(campos["interativos"]["formats"], ["quiz"])

    def test_snapshot_does_not_sum_radii(self):
        rows = snapshot_places(
            [
                {"slug": "confins", "point_ids": ["cnf-terminal", "cnf-corredor"]},
                {"slug": "diamond-mall", "point_ids": ["dm-mall"]},
            ],
            CATALOG,
        )
        self.assertEqual(len(rows), 2)
        blob = str(rows)
        self.assertNotIn("reach_total", blob)
        self.assertEqual(rows[0]["points"][0]["radius_label"], "350 m")
        self.assertEqual(rows[0]["points"][1]["radius_label"], "1,2 km")

    def test_allocate_keeps_places_outside_digital_funil(self):
        digital = allocate(["google_ads", "meta_ads"], "vendas", "funil")
        mixed = allocate(["google_ads", "meta_ads", "places"], "vendas", "funil")
        self.assertEqual(sum(item["pct"] for item in digital), 100)
        self.assertEqual(sum(item["pct"] for item in mixed), 100)
        places_pct = next(item["pct"] for item in mixed if item["id"] == "places")
        self.assertGreaterEqual(places_pct, 6)
        self.assertLessEqual(places_pct, 12)

    def test_campaign_keeps_places(self):
        out = campaign_from_campos({
            "canais": ["places", "g1"],
            "places": [{"slug": "confins", "point_ids": ["cnf-terminal"]}],
            "interativos": {"formats": ["quiz"]},
        })
        self.assertEqual(out["places"][0]["slug"], "confins")
        self.assertEqual(out["interativos"]["formats"], ["quiz"])

    def test_defaults_and_live_score(self):
        campos = apply_review_defaults({"campanha": "Copasa", "objetivo": "leads"})
        self.assertEqual(campos["periodo"], "30 dias")
        self.assertEqual(campos["verba"], "A fechar")
        score = review_score({
            "campanha": "Copasa",
            "objetivo": "leads",
            "publico": "Moradores",
            "verba": "A fechar",
            "periodo": "30 dias",
            "praca": "geolocalizada",
            "kpis": ["Alcance"],
            "canais": ["places"],
        })
        # "A fechar" é um estado editorial, não um valor de verba confirmado.
        self.assertEqual(score, 88)

    def test_starter_pitch_blocked_when_places_exist(self):
        self.assertEqual(match_pitch("BH Airport", "Filadélfia")["id"], "bh-airport")
        self.assertIsNone(match_pitch("BH Airport", "Filadélfia", places=[{"slug": "confins"}]))

    def test_snapshot_and_pack_include_places_law(self):
        row = {
            "session_token": "tok-places",
            "nome_campanha": "Copasa Confins",
            "cliente": "COPASA",
            "objetivo": "leads",
            "budget": "A fechar",
            "prazo": "30 dias",
            "dados_detectados": {
                "campanha": {
                    "canais": ["g1", "places"],
                    "places": [{"slug": "confins", "point_ids": ["cnf-terminal"], "apps": ["Uber"]}],
                    "objetivo": "leads",
                    "praca": "geolocalizada",
                }
            },
        }
        snapshot = build_snapshot(row)
        self.assertTrue(snapshot["places"])
        self.assertEqual(snapshot["places"][0]["slug"], "confins")
        law = _places_law(snapshot)
        self.assertIn("não se somam", law["lei"].lower())
        packed = _pack(snapshot, {})
        self.assertIn("places_aprovado", packed)
        self.assertIn("cnf-terminal", packed or snapshot["places"][0]["points"][0]["id"])


if __name__ == "__main__":
    unittest.main()
