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

    def test_standalone_studio_receives_editor_layout_and_clear_upload_entry(self):
        root = Path(__file__).resolve().parents[1]
        css = (root / "aicentralv2" / "static" / "css" / "trocr-editor.css").read_text(encoding="utf-8")
        page = Environment(loader=FileSystemLoader(root / "aicentralv2" / "templates")) \
            .get_template("parametros/_mc_trocar.html").render()
        self.assertIn(":is(.mc-shell,.trocr-product) .mc-trocr.trocr-editor", css)
        self.assertIn('.trocr-editor[data-flow="upload"] .mc-trocr-main', css)
        self.assertIn(".trocr-editor .mc-trocr-main {\n  grid-area:3 / 2 / 4 / 3;\n  display:grid;", css)
        self.assertIn(".trocr-editor .trocr-desk {\n  align-self:stretch;", css)
        for token in ("--tr-ink:#ececec", "--tr-muted:#b4b4b4", "--tr-floor:#212121", "--tr-accent:#58d39a"):
            with self.subTest(token=token):
                self.assertIn(token, css)
        self.assertIn("Envie uma peça para começar", page)
        self.assertIn("Nova peça", page)
        self.assertIn("Elementos clicáveis", page)
        self.assertIn("Formato de saída", page)
        self.assertIn("Comparar peças", page)
        self.assertIn('data-editor-tab="ai"', page)
        self.assertIn("Agente de mídia", page)
        self.assertIn("Analisar pedido", page)
        self.assertIn("Enter envia", page)

    def test_generation_keeps_initial_and_latest_reference(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "aicentralv2" / "static" / "js" / "mc-trocar.js").read_text(encoding="utf-8")
        self.assertIn("initial_reference", source)
        self.assertIn("runRequestedGeneration", source)
        self.assertIn("compareIds: ['', '']", source)
        self.assertIn("submitAgentRequest", source)
        self.assertIn("applyAgentDirectives", source)

    def test_studio_session_controls_are_wired_to_the_editor(self):
        root = Path(__file__).resolve().parents[1]
        template_root = root / "aicentralv2" / "templates"
        page = Environment(loader=FileSystemLoader(template_root)).get_template("parametros/_mc_trocar.html").render()
        source = (root / "aicentralv2" / "static" / "js" / "mc-trocar.js").read_text(encoding="utf-8")
        css = (root / "aicentralv2" / "static" / "css" / "trocr-editor.css").read_text(encoding="utf-8")
        for ident in (
            "mcTrocrSessionSave", "mcTrocrFinish", "mcTrocrFinalizedBanner",
            "mcTrocrContinueSession", "mcTrocrFinishDialog", "mcTrocrConfirmFinish",
        ):
            self.assertIn(f'id="{ident}"', page)
            self.assertIn(ident, source)
        self.assertIn("/format-lab/studio/sessions", source)
        self.assertIn("studio_session_id", source)
        self.assertIn("registerStudioVersion(version, 'accepted')", source)
        self.assertIn("/discard", source)
        self.assertIn("--tr-floor:#212121", css)
        self.assertIn("color-scheme:dark", css)

    def test_trocr_styles_have_one_dark_contract_and_no_retired_navigation(self):
        root = Path(__file__).resolve().parents[1]
        editor_css = (root / "aicentralv2" / "static" / "css" / "trocr-editor.css").read_text(encoding="utf-8")
        standalone_css = (root / "aicentralv2" / "static" / "css" / "trocr-standalone.css").read_text(encoding="utf-8")
        page = (root / "aicentralv2" / "templates" / "cadu_studio" / "trocr.html").read_text(encoding="utf-8")
        self.assertEqual(editor_css.count("color-scheme:dark"), 1)
        self.assertNotIn("color-scheme:light", editor_css)
        self.assertNotIn("Final light-surface cascade", editor_css)
        self.assertNotIn("Final layout cascade", editor_css)
        self.assertNotIn(".trocr-product-bar", standalone_css)
        self.assertNotIn("body.portal--studio", standalone_css)
        self.assertIn("#mcTrocrClipCompare", standalone_css)
        self.assertIn("trocr-editor.css') }}?v=16", page)
        self.assertIn("trocr-standalone.css') }}?v=6", page)
