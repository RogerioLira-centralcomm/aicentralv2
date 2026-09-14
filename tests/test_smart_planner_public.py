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
        self.assertEqual(view["media"]["channels"], [])

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
        self.assertIn("cc-exec-media", html)
        self.assertIn("Distribuição do investimento", html)
        self.assertIn("cc-plan-hero", html)
        self.assertIn("cc-donut", html)
        self.assertIn("cc-exec-gantt", html)
        self.assertIn("Destaques do plano", html)
        self.assertIn("Leitura do mix", html)
        self.assertIn("Resumo por canal", html)
        self.assertIn("cc-doc-card", html)
        self.assertIn("is-lead", html)
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

    def test_public_view_exposes_media_board_and_exec_facts(self):
        view = public_view({
            "nome_campanha": "Lançamento",
            "cliente": "BDMG",
            "publico_alvo": "Quem busca crédito em Minas",
            "dados_detectados": {
                "plan_mode": "one_page",
                "folha": {
                    "meta": {
                        "objective": "Tráfego",
                        "publico": "Quem busca crédito em Minas",
                        "canais": "2 canais · Funil do objetivo",
                        "ritmo": "Começa menor, solta no meio e no fim.",
                        "period": "outubro a novembro",
                    },
                    "media": {
                        "method_label": "Funil do objetivo",
                        "channels": [
                            {"id": "ooh", "label": "OOH / Painéis", "pct": 60, "amount_label": "R$ 240.000", "role": "Alcance"},
                            {"id": "google_ads", "label": "Google Ads", "pct": 40, "amount_label": "R$ 160.000"},
                        ],
                        "pace": {
                            "how": "Começa menor, solta no meio e no fim.",
                            "months": [
                                {"label": "Out", "amount": 160000, "amount_label": "R$ 160.000"},
                                {"label": "Nov", "amount": 240000, "amount_label": "R$ 240.000"},
                            ],
                        },
                    },
                    "sections": [{"cards": [{"type": "strategy", "body": "Tese."}]}],
                },
            },
            "plan_content": {"sections": []},
        })
        self.assertEqual(view["media"]["channels"][0]["pct"], 60)
        self.assertEqual(view["media"]["months"][0]["label"], "Out")
        self.assertGreater(view["media"]["months"][1]["bar"], view["media"]["months"][0]["bar"])
        labels = [item[0] for item in view["facts"]]
        self.assertIn("Público", labels)
        self.assertIn("Canais", labels)
        self.assertEqual(dict(view["facts"])["Período"], "outubro a novembro")
        self.assertEqual(dict(view["facts"])["Canais"], "2 canais")
        self.assertEqual(view["media"]["how"], "Começa menor, solta no meio e no fim.")
        self.assertFalse(view["media"]["note"])
        self.assertFalse(view["show_market"])
        self.assertTrue(view["media"]["donut"].startswith("conic-gradient"))
        self.assertEqual(view["media"]["channels"][0]["color"], "#1e4d4f")
        self.assertEqual(view["media"]["channels"][0]["bars"][0]["pct"], 60)
        self.assertTrue(view["hero"]["tagline"])

    def test_public_view_prefers_approved_mix_over_theme_density(self):
        view = public_view({
            "nome_campanha": "Canais digitais",
            "cliente": "COPASA",
            "dados_detectados": {
                "plan_mode": "one_page",
                "publico": "Principalmente clientes da Copasa, adultos, usuários de canais digitais em Minas Gerais com um parágrafo longo o bastante para não caber na faixa de fatos.",
                "campanha": {
                    "objetivo": "conversao",
                    "mix": {
                        "method": "manual",
                        "weights": [
                            {"id": "google_ads", "pct": 59},
                            {"id": "youtube", "pct": 17},
                            {"id": "ooh", "pct": 24},
                        ],
                    },
                },
                "folha": {
                    "theme": {"density": [
                        {"label": "Serasa", "value": 44},
                        {"label": "Redes", "value": 36},
                        {"label": "Interativo", "value": 20},
                    ]},
                    "sections": [{"cards": [
                        {"type": "strategy", "body": "Resolver no digital. Fácil, seguro e mais rápido."},
                        {"type": "defense", "body": "Google Ads captura a demanda. YouTube ensina o hábito."},
                    ]}],
                },
            },
            "plan_content": {"sections": []},
        })
        labels = [item["label"] for item in view["media"]["channels"]]
        self.assertEqual(labels, ["Google Ads", "YouTube", "OOH / Painéis"])
        self.assertEqual(view["media"]["channels"][0]["pct"], 59)
        self.assertTrue(view["audience"])
        self.assertNotIn("Principalmente clientes da Copasa, adultos, usuários", dict(view["facts"]).get("Público", ""))
        self.assertEqual(view["hero"]["tagline"], "Resolver no digital.")
        self.assertEqual(view["highlights"][0]["text"], "Resolver no digital.")
        self.assertEqual(view["highlights"][0]["title"], "Foco em conversão")
        titles = [item["title"] for item in view["highlights"]]
        self.assertIn("Digital e rua", titles)
        self.assertIn("Canais no mesmo plano", titles)
        self.assertEqual(view["reading"]["defense"], "Google Ads captura a demanda.")

    def test_media_only_folha_is_ready(self):
        view = public_view({
            "nome_campanha": "Só mix",
            "cliente": "BDMG",
            "dados_detectados": {
                "plan_mode": "one_page",
                "folha": {
                    "media": {
                        "method_label": "Funil do objetivo",
                        "channels": [{"id": "ooh", "label": "OOH", "pct": 100}],
                    },
                    "sections": [{"cards": []}],
                },
            },
            "plan_content": {"sections": []},
        })
        self.assertTrue(view["tem_folha"])
        self.assertFalse(view["tem_completo"])
        self.assertEqual(view["default_tab"], "folha")
        self.assertEqual(view["media"]["channels"][0]["label"], "OOH")

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
        self.assertEqual(row["href"], "/smart-planner/p/abc123/editar")
        self.assertEqual(row["canvas_href"], "/smart-planner/p/abc123/editar")
