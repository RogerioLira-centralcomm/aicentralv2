from pathlib import Path
from unittest import TestCase

from aicentralv2.smart_planner.public_view import plan_chapters, public_view
from aicentralv2.smart_planner.repository import serialize_list_row


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "aicentralv2" / "templates" / "smart_planner"


class PublicPlannerTest(TestCase):
    def test_one_page_only_marks_complete_as_missing(self):
        view = public_view({
            "nome_campanha": "Lançamento cartão",
            "cliente": "Banco exemplo",
            "objetivo": "reconhecimento",
            "budget": "R$ 180 mil",
            "prazo": "set a nov",
            "dados_detectados": {
                "plan_mode": "one_page",
                "public_token": "tok-pub",
                "folha": {
                    "sections": [{
                        "id": "one_page",
                        "cards": [
                            {"type": "strategy", "title": "Recomendação", "body": "CTV e portais primeiro."},
                            {"type": "defense", "title": "Defesa", "body": "Presença no lançamento."},
                        ],
                    }],
                    "share": {"public_token": "tok-pub", "url": "https://exemplo/p/tok-pub"},
                },
            },
            "plan_content": {"sections": [{"id": "one_page", "cards": []}]},
        })
        self.assertTrue(view["tem_folha"])
        self.assertFalse(view["tem_completo"])
        self.assertEqual(view["default_tab"], "folha")
        self.assertEqual(view["sheet"]["strategy"]["body"], "CTV e portais primeiro.")
        self.assertEqual(view["house"]["name"], "Centralcomm")

    def test_complete_plan_splits_markdown_chapters(self):
        chapters = plan_chapters(
            "## Capa\nCampanha X\n\n## Estratégia e Mix\n| Canal | % |\n| --- | --- |\n| G1 | 20 |\n"
        )
        self.assertEqual(chapters[0]["title"], "Capa")
        self.assertEqual(chapters[1]["title"], "Estratégia e Mix")
        self.assertEqual(chapters[1]["blocks"][0]["type"], "table")
        self.assertEqual(chapters[1]["blocks"][0]["head"], ["Canal", "%"])
        self.assertEqual(chapters[1]["blocks"][0]["rows"][0], ["G1", "20"])

        view = public_view({
            "nome_campanha": "Campanha X",
            "cliente": "Cliente",
            "dados_detectados": {
                "plan_mode": "completo",
                "planejamento": "## Capa\nCampanha X\n",
                "folha": {"sections": [{"cards": [{"type": "strategy", "body": "Tese."}]}]},
            },
            "plan_content": {
                "sections": [
                    {"id": "context", "title": "Contexto", "cards": [{"title": "Resumo", "body": "Entrada."}]},
                ],
            },
        })
        self.assertTrue(view["tem_folha"])
        self.assertTrue(view["tem_completo"])
        self.assertEqual(view["chapters"][0]["title"], "Capa")

    def test_confidential_hides_advertiser_name(self):
        view = public_view({
            "nome_campanha": "Campanha digital",
            "cliente": "COPASA",
            "dados_detectados": {
                "plan_mode": "one_page",
                "anunciante_confidencial": True,
                "folha": {"sections": [{"cards": [{"type": "strategy", "body": "Tese."}]}]},
            },
            "plan_content": {"sections": []},
        })
        self.assertEqual(view["client"], "Confidencial")
        self.assertIn(("Anunciante", "Confidencial"), view["facts"])
        self.assertNotIn("COPASA", str(view["facts"]))

    def test_public_page_is_centralcomm_not_centralx(self):
        html = (TEMPLATES / "public.html").read_text()
        error = (TEMPLATES / "public_error.html").read_text()
        wizard = (TEMPLATES / "wizard.html").read_text()
        index = (TEMPLATES / "index.html").read_text()
        canvas = (TEMPLATES / "canvas.html").read_text()
        self.assertIn("Centralcomm", html)
        self.assertIn("Smart Planner", html)
        self.assertNotIn("CentralX", html)
        self.assertNotIn("base_erp.html", html)
        self.assertIn('data-cc-tab="folha"', html)
        self.assertIn('data-cc-tab="plano"', html)
        self.assertIn("ainda não foi criado", html)
        self.assertIn("Centralcomm", error)
        self.assertIn("Smart Planner", error)
        self.assertNotIn("base_erp.html", error)
        self.assertIn('target="_blank"', wizard)
        self.assertIn("noopener noreferrer", wizard)
        self.assertIn('target="_blank"', index)
        self.assertIn("row.share_url", index)
        self.assertIn('target="_blank"', canvas)
        self.assertIn("share_url", canvas)

    def test_history_row_exposes_public_link(self):
        row = serialize_list_row({
            "id": 3,
            "session_token": "sess",
            "nome_campanha": "Voo",
            "cliente": "Marca",
            "dados_detectados": {"plan_mode": "one_page", "public_token": "abc123"},
            "plan_content": {
                "sections": [{"id": "one_page", "cards": [{"type": "strategy", "body": "Ok"}]}],
                "share": {"public_token": "abc123", "url": "https://host/smart-planner/p/abc123"},
            },
        })
        self.assertEqual(row["share_url"], "https://host/smart-planner/p/abc123")
        self.assertEqual(row["public_token"], "abc123")
