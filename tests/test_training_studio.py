"""Testes isolados do Studio de Treinamentos."""

import unittest

from aicentralv2.training_studio.extract import validate_public_url
from aicentralv2.training_studio.logos import logo_path
from aicentralv2.training_studio.prompts import SYSTEM_PROMPT, style_prompt
from aicentralv2.training_studio.schema import AGENDA_REVISION, DEFAULT_STYLE_GUIDE
from aicentralv2.training_studio.service import annotate_consumo, format_brl
from aicentralv2.training_studio.tools import (
    EDIT_INSTRUCTIONS,
    edit_text,
    parse_classification,
    research_market,
)


class TrainingStudioHelpersTest(unittest.TestCase):
    def test_format_brl_zero(self):
        self.assertEqual(format_brl(0), "R$ 0,00")

    def test_format_brl_thousands(self):
        self.assertEqual(format_brl(12.4), "R$ 12,40")
        self.assertEqual(format_brl(1234.5), "R$ 1.234,50")

    def test_annotate_consumo_empty(self):
        data = annotate_consumo({})
        self.assertEqual(data["cost_brl_label"], "R$ 0,00")

    def test_style_prompt_includes_palette(self):
        text = style_prompt(DEFAULT_STYLE_GUIDE)
        self.assertIn("#071422", text)
        self.assertIn("#5EEAD4", text)
        self.assertIn("MediaHacks", text)

    def test_prompt_is_for_specialists(self):
        self.assertIn("especialistas em mídia", SYSTEM_PROMPT)
        self.assertIn("Não defina MRC", SYSTEM_PROMPT)

    def test_validate_url_rejects_localhost(self):
        with self.assertRaises(ValueError):
            validate_public_url("http://localhost/secret")
        with self.assertRaises(ValueError):
            validate_public_url("ftp://example.com")

    def test_edit_requires_selection(self):
        with self.assertRaises(ValueError):
            edit_text(object(), "reescrever", "", "documento")

    def test_edit_actions_are_known(self):
        self.assertIn("reescrever", EDIT_INSTRUCTIONS)
        self.assertIn("expandir", EDIT_INSTRUCTIONS)

    def test_research_requires_web_toggle(self):
        with self.assertRaises(ValueError):
            research_market(object(), "Instagram Brasil", buscar_web=False)

    def test_parse_classification_json(self):
        data = parse_classification(
            '{"sessao_slug":"dooh-places","bloco":"case","titulo":"Case","html":"<p>ok</p>","resumo":"ok"}'
        )
        self.assertEqual(data["sessao_slug"], "dooh-places")
        self.assertEqual(data["bloco"], "case")
        self.assertIn("<p>ok</p>", data["html"])

    def test_parse_classification_rejects_unknown_block(self):
        data = parse_classification('{"bloco":"hack","html":"<p>x</p>"}')
        self.assertEqual(data["bloco"], "dado")

    def test_local_logos(self):
        self.assertTrue(logo_path("linkedin").startswith("/static/"))
        self.assertTrue(logo_path("g1").startswith("/static/"))
        self.assertIn("instagram", logo_path("instagram"))


class TrainingStudioRoutesTest(unittest.TestCase):
    def test_register_is_idempotent(self):
        from flask import Blueprint

        from aicentralv2.training_studio.routes import register_training_studio_routes

        blueprint = Blueprint("parametros", __name__, url_prefix="/parametros")
        register_training_studio_routes(blueprint)
        count = len(blueprint.deferred_functions)
        register_training_studio_routes(blueprint)
        self.assertEqual(len(blueprint.deferred_functions), count)
        self.assertTrue(blueprint._training_studio_registered)

    def test_menu_lists_treinamentos(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        menu = (root / "aicentralv2" / "templates" / "base_erp.html").read_text(encoding="utf-8")
        self.assertIn("'label': 'Treinamentos'", menu)
        self.assertIn("parametros.treinamentos", menu)

    def test_page_template_exists(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        page = (root / "aicentralv2" / "templates" / "parametros" / "treinamentos.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("data-training-studio", page)
        self.assertIn("Buscar na internet", page)
        self.assertIn("tsAddSession", page)
        self.assertIn("tsUploadFile", page)
        self.assertIn("tsFontes", page)
        self.assertIn("9h30–12h30", page)
        self.assertIn("tsProjectBtn", page)
        self.assertIn("/parametros/treinamentos/projetar", page)

    def test_agenda_has_nine_specialist_sessions(self):
        from aicentralv2.training_studio.agenda import CHANNELS, SESSIONS, session_html

        self.assertEqual(len(SESSIONS), 9)
        slugs = [item["slug"] for item in SESSIONS]
        self.assertEqual(slugs[0], "atencao-mercado")
        self.assertEqual(slugs[2], "dooh-places")
        self.assertEqual(slugs[-1], "dinamica-planos")
        self.assertEqual(SESSIONS[0]["horario_inicio"], "09:30")
        self.assertEqual(SESSIONS[2]["horario_inicio"], "10:00")
        self.assertEqual(SESSIONS[-1]["horario_fim"], "12:30")
        moeda = session_html(SESSIONS[0])
        self.assertIn("185 milhões", moeda)
        self.assertIn("não mau", moeda.lower().replace(" é ", " "))
        self.assertIn("IAB", moeda)
        familias = session_html(SESSIONS[1])
        self.assertIn("Tiro verba daqui", familias)
        self.assertIn("linkedin", familias)
        places = session_html(SESSIONS[2])
        self.assertIn("CNF", places)
        self.assertIn("CGH", places)
        self.assertIn("SDU", places)
        self.assertIn("GIG", places)
        self.assertIn("/static/images/places/", places)
        self.assertIn("24,6 mi", places)
        dinamica = session_html(SESSIONS[-1])
        self.assertIn("Banca", dinamica)
        self.assertIn("R$ 80 mil", dinamica)
        self.assertGreaterEqual(len(CHANNELS), 14)
        self.assertEqual(AGENDA_REVISION, 3)
        self.assertNotIn("<p><figure", places)
        atencao = next(item for item in SESSIONS if item["slug"] == "atencao-mercado")
        self.assertTrue(atencao.get("fontes"))
        self.assertTrue(
            any("datareportal" in (item.get("url") or "") for item in atencao["fontes"])
        )
        places_item = next(item for item in SESSIONS if item["slug"] == "dooh-places")
        self.assertGreaterEqual(len(places_item.get("fontes") or []), 3)

    def test_replace_channel_block(self):
        from aicentralv2.training_studio.research import replace_channel_block

        html = (
            '<article class="ts-canal"><!-- CANAL:linkedin -->velho'
            "<!-- /CANAL:linkedin --></article>"
        )
        out = replace_channel_block(
            html, "linkedin", "<!-- CANAL:linkedin -->novo<!-- /CANAL:linkedin -->"
        )
        self.assertIn("novo", out)
        self.assertNotIn("velho", out)
        self.assertNotIn("<article class=\"ts-canal\"></article>", out.replace(" ", ""))


class TrainingStudioSlidesTest(unittest.TestCase):
    def test_every_session_has_a_deck(self):
        from aicentralv2.training_studio.agenda import SESSIONS
        from aicentralv2.training_studio.slides import morning_deck, session_deck

        seen_charts = set()
        for item in SESSIONS:
            deck = session_deck(item["slug"])
            self.assertEqual(deck["slug"], item["slug"])
            self.assertGreaterEqual(len(deck["slides"]), 2)
            for slide in deck["slides"]:
                self.assertTrue(slide.get("title") or slide.get("place"))
                chart = (slide.get("chart") or {}).get("id")
                if chart:
                    self.assertNotIn(chart, seen_charts)
                    seen_charts.add(chart)
        manha = morning_deck()
        self.assertGreater(len(manha["slides"]), 40)
        self.assertEqual(manha["slides"][0]["layout"], "title")

    def test_places_deck_uses_catalog_photos(self):
        from aicentralv2.training_studio.slides import session_deck

        deck = session_deck("dooh-places")
        places = [slide for slide in deck["slides"] if slide["layout"] == "place"]
        self.assertEqual(len(places), 4)
        for slide in places:
            self.assertTrue(slide["place"]["hero"].startswith("/static/images/places/"))
            self.assertTrue(slide["place"]["pax"])

    def test_project_template_exists(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        page = (
            root / "aicentralv2" / "templates" / "parametros" / "treinamento_projetar.html"
        ).read_text(encoding="utf-8")
        self.assertIn("data-slide-deck", page)
        self.assertIn("chart.js", page.lower())


if __name__ == "__main__":
    unittest.main()
