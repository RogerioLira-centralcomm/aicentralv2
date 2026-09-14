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
    def test_fill_art_slot_replaces_empty_figure(self):
        from aicentralv2.training_studio.service import _fill_art_slot

        html = '<figure class="ts-page-art" data-slot="ilustracao"></figure>'
        out = _fill_art_slot(html, "/static/x.png")
        self.assertIn('src="/static/x.png"', out)
        self.assertNotIn(html, out)
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

    def test_parse_youtube_id(self):
        from aicentralv2.training_studio.youtube import parse_storyboard_level, parse_youtube_id

        self.assertEqual(
            parse_youtube_id("https://www.youtube.com/watch?v=c8o1RttjqZw"),
            "c8o1RttjqZw",
        )
        self.assertEqual(parse_youtube_id("https://youtu.be/c8o1RttjqZw"), "c8o1RttjqZw")
        self.assertEqual(
            parse_youtube_id("https://www.youtube.com/embed/c8o1RttjqZw"),
            "c8o1RttjqZw",
        )
        self.assertIsNone(parse_youtube_id("https://example.com/watch?v=c8o1RttjqZw"))
        spec = (
            "https://i.ytimg.com/sb/c8o1RttjqZw/storyboard3_L$L/$N.jpg?sqp=x|"
            "48#27#100#10#10#0#default#rs$aaa|"
            "80#45#154#10#10#5000#M$M#rs$bbb|"
            "320#180#154#3#3#5000#M$M#rs$ccc"
        )
        level = parse_storyboard_level(spec)
        self.assertEqual(level["width"], 320)
        self.assertEqual(level["cols"], 3)
        self.assertIn("L2/M0.jpg", level["sheet_url"](0))
        self.assertIn("sigh=ccc", level["sheet_url"](0))

    def test_caption_and_briefing_html(self):
        from aicentralv2.training_studio.extract import _session_html
        from aicentralv2.training_studio.youtube import _parse_caption_body

        text = _parse_caption_body(
            '{"events":[{"segs":[{"utf8":"Agentes "},{"utf8":"autônomos"}]}]}'
        )
        self.assertEqual(text, "Agentes autônomos")
        html = _session_html("Astra", "```html\n<p>Tese</p>\n```")
        self.assertIn('class="ts-page"', html)
        self.assertIn("<p>Tese</p>", html)
        self.assertIn("ts-page-art", html)

    def test_import_plan_splits_long_video(self):
        from aicentralv2.training_studio.import_plan import (
            build_import_sessions,
            is_large_import,
            preview_import_plan,
        )

        payload = {
            "titulo": "GPT-6 Astra",
            "autor": "InvestNews",
            "duracao_s": 760,
            "transcript": "x" * 2000,
            "briefing_html": "<h2>Tese</h2><p>Agentes.</p>",
            "frames": ["/static/a.jpg", "/static/b.jpg", "/static/c.jpg", "/static/d.jpg"],
        }
        self.assertTrue(is_large_import(payload))
        plan = preview_import_plan(payload)
        self.assertGreaterEqual(len(plan), 2)
        sessions = build_import_sessions(payload)
        self.assertIn("data-surface=\"slide\"", sessions[0]["conteudo_html"])
        self.assertTrue(any("quadros" in item["titulo"] for item in sessions))

    def test_schema_keeps_import_and_vision_cost(self):
        from aicentralv2.training_studio.schema import SCHEMA_PATCH_SQL, SCHEMA_SQL

        self.assertIn("cx_treinamento_importacoes", SCHEMA_PATCH_SQL)
        self.assertIn("palco_json", SCHEMA_PATCH_SQL)
        self.assertIn("applied_mode", SCHEMA_PATCH_SQL)
        self.assertIn("visao_video", SCHEMA_SQL)
        self.assertIn("visao_video", SCHEMA_PATCH_SQL)
        self.assertIn("importacao_id", SCHEMA_PATCH_SQL)

    def test_merge_import_keeps_transcript(self):
        from aicentralv2.training_studio.service import _merge_import_payload

        packed = _merge_import_payload(
            {"titulo": "Astra"},
            {
                "transcript": "agentes autônomos",
                "frames": [{"asset_url": "/static/a.png"}],
                "autor": "InvestNews",
            },
            {"titulo": "fallback"},
        )
        self.assertEqual(packed["titulo"], "Astra")
        self.assertEqual(packed["autor"], "InvestNews")
        self.assertEqual(packed["transcript"], "agentes autônomos")
        self.assertEqual(packed["frame_urls"], ["/static/a.png"])

    def test_live_deck_prefers_stored_palco(self):
        from aicentralv2.training_studio.slides.live import deck_from_sessao

        deck = deck_from_sessao(
            {
                "titulo": "Astra",
                "slug": "fonte-astra",
                "conteudo_html": "<p>ignore</p>",
                "palco_json": [{"layout": "title", "title": "Agentes", "lede": "Tese"}],
            }
        )
        self.assertEqual(deck["slides"][0]["title"], "Agentes")

    def test_live_deck_prefers_palco_pages(self):
        from aicentralv2.training_studio.slides.live import deck_from_html

        html = (
            '<article class="ts-page" data-layout="copy" data-surface="roteiro">'
            '<div class="ts-page-copy"><h2>Nota</h2><p>Fica no editor.</p></div></article>'
            '<article class="ts-page" data-layout="title" data-surface="slide">'
            '<div class="ts-page-copy"><h2>Comprem atenção</h2><p>Unidade de valor.</p></div></article>'
        )
        deck = deck_from_html({"titulo": "Fonte", "slug": "fonte-astra", "conteudo_html": html})
        self.assertEqual(len(deck["slides"]), 1)
        self.assertEqual(deck["slides"][0]["title"], "Comprem atenção")
        self.assertTrue(deck["live"])

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
        self.assertIn("tsAddPage", page)
        self.assertIn("tsPageLayout", page)
        self.assertIn("tsImportModal", page)
        self.assertIn("tsImportApplyRoteiro", page)
        self.assertIn("tsFocus", page)
        self.assertIn("Gerar palco", page)
        self.assertIn("tsSurfaceBtn", page)
        self.assertIn("Criar sessão", page)

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
        self.assertEqual(AGENDA_REVISION, 4)
        self.assertIn('class="ts-page"', moeda)
        self.assertIn("ts-page-art", familias)
        self.assertEqual(SESSIONS[0]["titulo"], "Comprem atenção, não impressão")
        self.assertEqual(SESSIONS[2]["titulo"], "O lugar não é a audiência")
        self.assertEqual(SESSIONS[-1]["titulo"], "Banca: moeda, família, first-wave")
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
