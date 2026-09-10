"""Testes isolados do Studio de Treinamentos."""

import unittest

from aicentralv2.training_studio.extract import validate_public_url
from aicentralv2.training_studio.prompts import style_prompt
from aicentralv2.training_studio.schema import DEFAULT_STYLE_GUIDE
from aicentralv2.training_studio.service import annotate_consumo, format_brl
from aicentralv2.training_studio.tools import EDIT_INSTRUCTIONS, edit_text


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
        self.assertIn("Cole um link para adicionar contexto", page)
        self.assertIn("Gerar imagem", page)
        self.assertIn("tsSessionList", page)
        self.assertIn("Enriquecer canais", page)
        self.assertIn("9h30–12h30", page)

    def test_agenda_has_seven_sessions_and_dinamica(self):
        from aicentralv2.training_studio.agenda import CHANNELS, SESSIONS, session_html

        self.assertEqual(len(SESSIONS), 7)
        slugs = [item["slug"] for item in SESSIONS]
        self.assertEqual(slugs[0], "mercado-canais")
        self.assertEqual(slugs[-1], "dinamica-planos")
        self.assertEqual(SESSIONS[0]["horario_inicio"], "09:30")
        self.assertEqual(SESSIONS[-1]["horario_inicio"], "11:50")
        self.assertEqual(SESSIONS[-1]["horario_fim"], "12:30")
        dinamica = session_html(SESSIONS[-1])
        self.assertIn("ponto alto", dinamica)
        self.assertIn("R$ 80 mil", dinamica)
        self.assertIn("R$ 250 mil", dinamica)
        self.assertIn("R$ 800 mil", dinamica)
        self.assertGreaterEqual(len(CHANNELS), 14)
        coffee_idx = slugs.index("coffee")
        self.assertLess(coffee_idx, slugs.index("dinamica-planos"))
        self.assertEqual(SESSIONS[-1]["titulo"], "Dinâmica e resultado")

    def test_replace_channel_block(self):
        from aicentralv2.training_studio.research import replace_channel_block

        html = "<!-- CANAL:linkedin -->velho<!-- /CANAL:linkedin -->"
        out = replace_channel_block(html, "linkedin", "<!-- CANAL:linkedin -->novo<!-- /CANAL:linkedin -->")
        self.assertIn("novo", out)
        self.assertNotIn("velho", out)


if __name__ == "__main__":
    unittest.main()
