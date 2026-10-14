import unittest
import unittest.mock

from aicentralv2.cadu_planner import places as planner_places
from aicentralv2.places import service
from aicentralv2.places.schema import shown_label


class WeeklyReachTest(unittest.TestCase):
    def test_four_week_range_becomes_weekly(self):
        self.assertEqual(planner_places.weekly_reach("190–280 mil"), "48–70 mil")
        self.assertEqual(planner_places.weekly_reach("1,2–1,8 mi"), "300–450 mil")
        self.assertEqual(planner_places.weekly_reach("3,5 milhões"), "875 mil")

    def test_dot_decimal_and_rounding_edges(self):
        self.assertEqual(planner_places.weekly_reach("1.5 mi"), "375 mil")
        self.assertEqual(planner_places.weekly_reach("3,998 mi"), "1 mi")

    def test_each_bound_keeps_its_own_unit(self):
        self.assertEqual(planner_places.weekly_reach("641 mil–1,07 mi"), "160–268 mil")
        self.assertEqual(planner_places.weekly_reach("2–4 mil"), "500–1.000")

    def test_pending_reach_has_no_weekly_number(self):
        self.assertEqual(planner_places.weekly_reach("A validar"), "")
        self.assertEqual(planner_places.weekly_reach(""), "")


class PlaceRecordTest(unittest.TestCase):
    def _row(self, **extra):
        return {"id": 1, "slug": "confins", "title": "Confins", "metrics": {
            "addressable": {"label": "A validar", "source_status": "to_validate"},
            "passengers": {"label": "13,2 mi", "source_status": "official"}}, **extra}

    def test_pending_number_is_not_shown_as_text(self):
        record = planner_places._serialize(self._row())
        self.assertEqual(record["audience"], "")
        self.assertEqual(record["traffic"], "13,2 mi")

    def test_pending_variants_are_hidden(self):
        self.assertEqual(shown_label("A validar com o operador"), "")
        self.assertEqual(shown_label("~12 mi"), "~12 mi")

    def test_points_carry_weekly_audience_and_apps(self):
        row = self._row(points=[
            {"name": "Terminal", "scope_label": "Ponto principal", "reach": "190–280 mil", "apps": [{"name": "WhatsApp"}, {"name": "Uber"}]},
            {"name": "Internacional", "reach": "A validar", "apps": []},
        ])
        points = planner_places._serialize(row, full=True)["points"]
        self.assertEqual(points[0], {"name": "Terminal", "scope": "Ponto principal", "weekly": "48–70 mil", "apps": ["WhatsApp", "Uber"]})
        self.assertEqual(points[1]["weekly"], "")


class GalleryCurationTest(unittest.TestCase):
    def test_rejected_svg_and_duplicate_photos_leave_the_gallery(self):
        rejected = next(iter(service._rejected_photos()))
        view = {"slug": "nowhere-place", "media": {"hero_url": f"/static/images/places/gallery/{rejected}", "gallery": [
            {"kind": "hero", "url": f"/static/images/places/gallery/{rejected}"},
            {"kind": "hero", "url": "https://example.com/logo.svg"},
            {"kind": "hero", "url": "/static/images/places/gallery/nowhere-place-hero-abc12345.jpg"},
            {"kind": "point", "url": "/static/images/places/gallery/nowhere-place-point-abc12345.jpg"},
        ]}}
        media = service._attach_bundled_gallery(view)["media"]
        self.assertEqual([item["url"] for item in media["gallery"]], ["/static/images/places/gallery/nowhere-place-hero-abc12345.jpg"])
        self.assertEqual(media["hero_url"], "/static/images/places/gallery/nowhere-place-hero-abc12345.jpg")

    def test_confins_opens_with_its_chosen_cover(self):
        media = service._attach_bundled_gallery({"slug": "confins", "media": {"hero_url": "/static/images/places/generated/confins-hero-bad23d6b.png"}})["media"]
        self.assertTrue(media["gallery"][0]["url"].endswith(service.COVERS["confins"]))
        self.assertEqual(media["hero_url"], media["gallery"][0]["url"])
        names = {item["url"].rsplit("/", 1)[-1] for item in media["gallery"]}
        self.assertNotIn("confins-hero-a67e7bb0.png", names)

    def test_missing_cover_keeps_the_stored_hero(self):
        with unittest.mock.patch.dict(service.COVERS, {"confins": "confins-hero-gone.jpg"}):
            media = service._attach_bundled_gallery({"slug": "confins", "media": {"hero_url": "/static/x/stored.png"}})["media"]
        self.assertEqual(media["hero_url"], "/static/x/stored.png")


if __name__ == "__main__":
    unittest.main()
