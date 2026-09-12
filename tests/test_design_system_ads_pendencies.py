"""Incremento 6: pendências por formato."""

from pathlib import Path
import unittest

from aicentralv2.design_system_ads.centralcomm import centralcomm_preset
from aicentralv2.design_system_ads.materialize import ensure_brand_design_system
from aicentralv2.design_system_ads.pendencies import list_pendencies
from aicentralv2.design_system_ads.schema import dump_system, parse_system
from aicentralv2.design_system_ads.service import payload_for
from aicentralv2.design_system_ads.validate import (
    build_validation_report,
    mark_format_state,
    stamp_validation,
)

ROOT = Path(__file__).resolve().parents[1]


def _complete_brand(client_id=61):
    system = ensure_brand_design_system(
        {
            "id": client_id,
            "name": "Clara",
            "primary_color": "#082C9C",
            "brand_assets": [{"asset_url": "/media/clara-pack.jpg", "role": "packshot"}],
        }
    )
    data = dump_system(system)
    data["dna"] = {
        "name": "Clara",
        "personality": ["icônica", "de joia"],
        "must": ["logo no canto"],
        "avoid": ["resize"],
    }
    data["ad_copy"] = {**(system.ad_copy or {}), "legal": "Clara"}
    return parse_system(data)


class DesignSystemAdsPendenciesTest(unittest.TestCase):
    def test_centralcomm_aprovado_sem_pendencia_falsa(self):
        system = centralcomm_preset(status="approved")
        self.assertEqual(list_pendencies(system), [])
        payload = payload_for(system)
        self.assertEqual(payload["pendencies"], [])
        self.assertEqual(payload["catalog"]["pendencies"], [])

    def test_billboard_fica_stale_depois_do_ink(self):
        system, _ = stamp_validation(_complete_brand())
        system = mark_format_state(system, "iab-billboard", "ok")
        data = dump_system(system)
        data["tokens"] = {**system.tokens, "ink": "#111111"}
        after = parse_system(data)
        report = build_validation_report(after)
        items = list_pendencies(after, report=report)
        billboard = next(item for item in items if item["format"] == "iab-billboard")
        self.assertEqual(billboard["state"], "stale")
        payload = payload_for(after, report=report)
        listed = next(
            item for item in payload["catalog"]["iab_formats"] if item["key"] == "iab-billboard"
        )
        self.assertEqual(listed["pending"], "stale")

    def test_mobile_mostra_needs_input(self):
        system = ensure_brand_design_system(
            {
                "id": 62,
                "name": "Clara",
                "primary_color": "#082C9C",
                "sector": "joalheria",
            }
        )
        items = list_pendencies(system)
        mobile = next(item for item in items if item["format"] == "iab-mobile")
        self.assertEqual(mobile["state"], "needs_input")
        self.assertIn("produto", mobile["detail"].lower())

    def test_mesa_lista_pendencias_fora_do_console(self):
        js = (ROOT / "aicentralv2" / "static" / "js" / "mc-design-system.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("function renderPendencies", js)
        self.assertIn("mc-dsa-pendencies", js)
        self.assertIn('data-block="pendencies"', js)
        self.assertNotIn("pushConsole", js.split("function renderPendencies")[1].split("function renderGrounds")[0])


if __name__ == "__main__":
    unittest.main()
