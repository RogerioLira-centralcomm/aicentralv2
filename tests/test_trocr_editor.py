"""Regression tests for recoverable, bounded still-editor drafts."""
import copy
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from aicentralv2.creative_format_lab.editor_draft import normalize_editor_draft
from aicentralv2.creative_format_lab.swap_session import write_run, wrap_store, pick_run


class TrocrEditorDraftTest(unittest.TestCase):
    def draft(self):
        return {
            "version": 1, "base_id": "v1", "aspect_ratio": "16:9",
            "values": {"mcTrocrPrice": "R$ 99,90", "mcSwapNote": "Preservar as pessoas"},
            "checks": {"mcTrocrAlter": ["price"], "mcTrocrPreserve": ["people"]},
            "region": {"field": "price", "box": [20, 30, 200, 100], "ref_width": 1280, "ref_height": 720},
        }

    def test_draft_survives_run_roundtrip_without_modifying_original(self):
        versions = [{"id": "v1", "origin": "original", "params": {"price": "R$ 89,99"}}]
        before = copy.deepcopy(versions)
        run = write_run({}, {"base_id": "v1", "editor_draft": self.draft()}, versions, 1, 2)
        restored = pick_run(wrap_store({"schema": "runs-v1", "active_run_id": run["run_id"], "runs": [run]}, 1))
        self.assertEqual(restored["editor_draft"]["values"]["mcTrocrPrice"], "R$ 99,90")
        self.assertEqual(restored["revision"], 2)
        self.assertEqual(versions, before)

    def test_legacy_write_preserves_draft_and_explicit_null_clears_it(self):
        versions = [{"id": "v1"}]
        run = write_run({}, {"editor_draft": self.draft()}, versions, 1, 1)
        self.assertEqual(write_run(run, {}, versions, 1, 2)["editor_draft"], run["editor_draft"])
        self.assertIsNone(write_run(run, {"editor_draft": None}, versions, 1, 3)["editor_draft"])

    def test_rejects_draft_from_another_base(self):
        with self.assertRaises(ValueError):
            write_run({}, {"editor_draft": self.draft()}, [{"id": "v2"}], 1, 1)

    def test_rejects_overflow_and_invalid_coordinates(self):
        for box in ([0, 0, 1300, 100], [20, 20, 10, 10], [0, 0, float("nan"), 20], [0, 0, 10]):
            draft = self.draft()
            draft["region"]["box"] = box
            with self.subTest(box=box), self.assertRaises(ValueError):
                normalize_editor_draft(draft)
        draft = self.draft()
        draft["values"]["mcSwapNote"] = "a" * 501
        with self.assertRaises(ValueError):
            normalize_editor_draft(draft)

    def test_unknown_fields_are_not_persisted(self):
        draft = self.draft()
        draft["values"]["arbitrary"] = "untrusted"
        draft["unexpected"] = {"large": "content"}
        normalized = normalize_editor_draft(draft)
        self.assertNotIn("unexpected", normalized)
        self.assertNotIn("arbitrary", normalized["values"])

    def test_workspace_renders_unique_controls_and_tabs(self):
        from html.parser import HTMLParser
        class Controls(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []
                self.formats = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get("id"):
                    self.ids.append(attrs["id"])
                if attrs.get("name") == "mcSwapOut":
                    self.formats.append(attrs["value"])
        root = Path(__file__).resolve().parents[1] / "aicentralv2" / "templates"
        page = Environment(loader=FileSystemLoader(root)).get_template("parametros/_mc_trocar.html").render()
        controls = Controls()
        controls.feed(page)
        self.assertEqual(len(controls.ids), len(set(controls.ids)))
        self.assertEqual(set(controls.formats), {"16:9", "9:16", "1:1", "4:5"})
        for ident in ("mcSwapRun", "mcTrocrInspector", "mcTrocrOrder", "trocrElementList", "trocrProperties", "trocrAi"):
            self.assertIn(ident, controls.ids)
