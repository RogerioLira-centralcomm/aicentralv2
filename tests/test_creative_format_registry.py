"""Registro canônico, aliases e recusa de placement."""

from unittest import TestCase

from aicentralv2.creative_format_geometry import (
    format_family_spec,
    placement_zone_for,
)
from aicentralv2.creative_format_lab.catalog import resolve_format_key
from aicentralv2.creative_format_registry import (
    FORMATS,
    aliases_for,
    catalog_entries,
    compatibility,
    default_zone,
    entry,
    resolve_format_key as resolve_canonical,
)


SPEC_KEYS = (
    "iab-billboard",
    "iab-leaderboard",
    "iab-medium",
    "iab-halfpage",
    "iab-skyscraper",
    "iab-mobile",
    "native-infeed",
    "hotspot",
    "cartas",
    "puxe-descubra",
    "arraste-descubra",
    "quiz",
    "video-linear-15",
    "video-cta-15",
    "video-qr-15",
    "youtube-infeed",
    "feed-1x1",
    "feed-4x5",
    "story-9x16",
    "reels-9x16",
    "shorts-9x16",
    "linkedin-landscape",
)


class CreativeFormatRegistryTest(TestCase):
    def test_todas_as_chaves_do_spec_existem(self):
        keys = {item["format_key"] for item in FORMATS}
        self.assertTrue(set(SPEC_KEYS).issubset(keys))
        for key in SPEC_KEYS:
            item = entry(key)
            self.assertEqual(item["format_key"], key)
            self.assertGreater(item["width"], 0)
            self.assertGreater(item["height"], 0)
            self.assertTrue(item["channels"])
            self.assertTrue(item["devices"])
            self.assertTrue(item["viewer_types"])
            self.assertIn("required_elements", item)

    def test_aliases_resolvem_para_chave_unica(self):
        pairs = {
            "iab-medium-rectangle": "iab-medium",
            "iab-banner": "iab-medium",
            "iab-half-page": "iab-halfpage",
            "iab-mobile-banner": "iab-mobile",
            "instagram-feed": "feed-1x1",
            "facebook-feed": "feed-1x1",
            "instagram-feed-4x5": "feed-4x5",
            "instagram-story": "story-9x16",
            "instagram-reels": "reels-9x16",
            "tiktok-vertical": "reels-9x16",
            "youtube-shorts": "shorts-9x16",
            "linkedin-share": "linkedin-landscape",
            "ctv-video-linear-30": "video-linear-15",
            "ctv-video-cta": "video-cta-15",
            "ctv-video-qr": "video-qr-15",
        }
        for raw, expected in pairs.items():
            self.assertEqual(resolve_canonical(raw), expected, raw)
            self.assertEqual(resolve_format_key(raw), expected, raw)
        self.assertIn("iab-medium-rectangle", aliases_for("iab-medium"))
        self.assertIn("iab-mobile-banner", aliases_for("iab-mobile"))

    def test_lab_delega_mobile_banner(self):
        self.assertEqual(resolve_format_key("iab-mobile-banner"), "iab-mobile")
        self.assertEqual(resolve_format_key("iab-medium"), "iab-medium")

    def test_geometry_usa_chave_canonica(self):
        spec = format_family_spec("iab-medium-rectangle", "300x250")
        self.assertEqual(spec["canonical_key"], "iab-medium")
        self.assertEqual(spec["family"], "rectangle")
        self.assertEqual(spec["placement_zone"], "in_feed")
        billboard = format_family_spec("iab-billboard")
        self.assertEqual(billboard["placement_zone"], "leaderboard")
        self.assertEqual(billboard["size"], (970, 250))

    def test_zonas_canonicas(self):
        self.assertEqual(default_zone("iab-billboard"), "leaderboard")
        self.assertEqual(default_zone("iab-leaderboard"), "leaderboard")
        self.assertEqual(default_zone("iab-leaderboard", device="mobile"), "sticky")
        self.assertEqual(default_zone("iab-medium"), "in_feed")
        self.assertEqual(default_zone("hotspot"), "in_feed")
        self.assertEqual(default_zone("quiz"), "in_feed")
        self.assertEqual(default_zone("iab-halfpage"), "rail")
        self.assertEqual(default_zone("iab-skyscraper"), "rail")
        self.assertEqual(default_zone("iab-mobile", device="mobile"), "sticky")
        self.assertIsNone(default_zone("video-linear-15"))
        self.assertIsNone(default_zone("feed-1x1"))

    def test_placement_zone_for_aceita_slugs_curtos(self):
        self.assertEqual(
            placement_zone_for(slug="iab-billboard", size=(970, 250)),
            "leaderboard",
        )
        self.assertEqual(
            placement_zone_for(slug="iab-skyscraper", size=(160, 600)),
            "rail",
        )
        self.assertEqual(
            placement_zone_for(slug="iab-medium", size=(300, 250)),
            "in_feed",
        )
        self.assertEqual(
            placement_zone_for(slug="iab-mobile", size=(320, 50)),
            "sticky",
        )
        self.assertIsNone(placement_zone_for(slug="video-linear-15"))
        self.assertIsNone(placement_zone_for(slug="feed-1x1"))

    def test_recusa_combinacao_incompativel(self):
        blocked = compatibility("iab-medium", channel="ctv", zone="rail")
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["code"], "PLACEMENT_INCOMPATIBLE")
        unknown = compatibility("formato-inventado")
        self.assertEqual(unknown["code"], "PLACEMENT_NOT_DEFINED")
        social_on_portal = compatibility(
            "feed-1x1", channel="portal", zone="in_feed",
        )
        self.assertEqual(social_on_portal["status"], "blocked")
        sticky_billboard = compatibility(
            "iab-billboard", channel="portal", device="desktop", zone="sticky",
        )
        self.assertEqual(sticky_billboard["status"], "blocked")
        medium_on_leaderboard = compatibility(
            "iab-medium", channel="portal", device="desktop", zone="leaderboard",
        )
        self.assertEqual(medium_on_leaderboard["status"], "blocked")
        ok = compatibility(
            "iab-medium", channel="portal", device="desktop", zone="in_feed",
        )
        self.assertEqual(ok["status"], "ok")
        self.assertEqual(ok["zone"], "in_feed")

    def test_catalog_entries_tem_contrato_do_agente(self):
        items = catalog_entries()
        self.assertGreaterEqual(len(items), len(SPEC_KEYS))
        sample = entry("iab-medium")
        for field in (
            "format_key", "aliases", "width", "height", "family", "density",
            "channels", "devices", "placement_zones", "fit",
            "required_elements", "optional_elements", "forbidden_elements",
            "safe_areas", "viewer_types", "recomposition_rules",
        ):
            self.assertIn(field, sample, field)
        self.assertIn("logo", sample["required_elements"])
        self.assertIn("portal_chrome", sample["forbidden_elements"])
