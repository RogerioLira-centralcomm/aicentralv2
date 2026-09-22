from pathlib import Path
from unittest import TestCase

from flask import Flask, render_template

from aicentralv2.smart_planner.public_view import format_public_updated, plan_chapters, public_view
from aicentralv2.smart_planner.repository import serialize_list_row


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "aicentralv2" / "templates" / "smart_planner"


class PublicPlannerTest(TestCase):
    def test_separate_public_documents_render_as_executive_plan_and_primary_format(self):
        row = {
            "nome_campanha": "Proposta BDMG",
            "cliente": "BDMG",
            "dados_detectados": {
                "plan_mode": "completo",
                "public_token": "pub-docs",
                "planejamento": "## Estratégia\nTese.\n\n## Indicadores\nAlcance e frequência.\n\n## Direção criativa\nUma linha visual.\n",
                "one_page_v2": {
                    "commercial_defense": {"why_this_mix": ["O mix conecta atenção e resposta."]},
                    "creative_plan": [{
                        "channel_id": "youtube",
                        "primary_format": "Vídeo horizontal · 15s",
                        "deliverables": {"concepts": 1, "variations": 2, "final_files": 2},
                    }],
                },
                "folha": {
                    "media": {"channels": [{"id": "youtube", "label": "YouTube", "pct": 100}]},
                    "sections": [{"cards": [
                        {"type": "strategy", "body": "Ganhar atenção com uma proposta simples."},
                        {"type": "creative", "title": "Crédito que move", "body": "Apoio."},
                        {"type": "defense", "body": "A proposta abre a conversa."},
                    ]}],
                },
            },
            "plan_content": {"sections": [{"id": "execution", "title": "Execução", "cards": [{"title": "Próximo passo", "body": "Aprovar."}]}]},
        }
        proposal = public_view(row, document="proposal")
        complete = public_view(row, document="full_plan")
        self.assertTrue(proposal["proposal_url"].endswith("/proposta"))
        self.assertTrue(complete["full_plan_url"].endswith("/plano"))
        self.assertEqual(complete["creative_plan"][0]["primary_format"], "Vídeo horizontal · 15s")
        self.assertEqual([item["label"] for item in complete["full_groups"]], ["Estratégia e indicadores", "Mídia e distribuição", "Criação e execução"])

        app = Flask(__name__, template_folder=str(ROOT / "aicentralv2" / "templates"), static_folder=str(ROOT / "aicentralv2" / "static"))
        with app.test_request_context("/"):
            proposal_html = render_template("smart_planner/public_document.html", **proposal)
            complete_html = render_template("smart_planner/public_document.html", **complete)
        self.assertIn("Plano de mídia executivo", proposal_html)
        self.assertNotIn('role="tablist" aria-label="Proposta comercial"', proposal_html)
        self.assertNotIn("Capítulo 1 de 5", proposal_html)
        self.assertNotIn('role="tablist"', complete_html)
        self.assertIn("Planejamento completo", complete_html)
        self.assertNotIn("planning_structure_json", complete_html)
        self.assertNotIn("Estrutura de dados do planejamento", complete_html)

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

    def test_public_document_uses_at_most_two_images_in_editorial_order(self):
        view = public_view({
            "nome_campanha": "Campanha visual",
            "cliente": "Cliente",
            "dados_detectados": {
                "folha": {
                    "sections": [{"cards": [
                        {"type": "strategy", "body": "Tese."},
                        {"type": "creative", "image_url": "/generated/creative.png"},
                    ]}],
                    "supporting_visuals": [
                        {"kind": "persona", "image_url": "/generated/persona.png"},
                        {"kind": "place", "image_url": "/generated/place.png"},
                    ],
                    "asset_manifest": [{"kind": "persona", "asset_url": "/generated/persona.png", "status": "approved"}],
                },
            },
            "plan_content": {"sections": []},
        })
        self.assertEqual(view["hero"]["creative_image"], "/generated/creative.png")
        self.assertEqual(view["hero"]["support_image"]["url"], "/generated/persona.png")
        self.assertTrue(view["hero"]["has_generated_visual"])

    def test_public_document_does_not_publish_unapproved_support_or_theme_images(self):
        view = public_view({
            "nome_campanha": "Campanha sem aprovação visual",
            "cliente": "Cliente",
            "dados_detectados": {
                "folha": {
                    "sections": [{"cards": [
                        {"type": "strategy", "body": "Tese."},
                        {"type": "creative", "image_url": "/generated/creative.png"},
                    ]}],
                    "supporting_visuals": [
                        {"kind": "persona", "image_url": "/generated/draft-persona.png"},
                    ],
                    "asset_manifest": [
                        {"kind": "persona", "asset_url": "/generated/draft-persona.png", "status": "draft"},
                    ],
                    "theme": {"bg_url": "/static/images/unrelated-theme.png"},
                },
            },
            "plan_content": {"sections": []},
        })
        self.assertEqual(view["hero"]["creative_image"], "/generated/creative.png")
        self.assertEqual(view["hero"]["support_image"], {})
        self.assertTrue(view["hero"]["has_generated_visual"])
        self.assertFalse(view["hero"]["uses_image_background"])

    def test_public_document_honors_editor_hero_selection_and_background_choice(self):
        view = public_view({
            "nome_campanha": "Campanha visual",
            "cliente": "Cliente",
            "dados_detectados": {
                "folha": {
                    "sections": [{"cards": [
                        {"type": "strategy", "body": "Tese."},
                        {"type": "creative", "image_url": "/generated/creative.png"},
                    ]}],
                    "asset_manifest": [{"kind": "persona", "asset_url": "/generated/persona.png"}],
                    "public_design": {"hero": {"asset_url": "/generated/persona.png", "use_as_background": True}},
                },
            },
            "plan_content": {"sections": []},
        })
        self.assertEqual(view["hero"]["creative_image"], "/generated/persona.png")
        self.assertEqual(view["hero"]["background_image"], "/generated/persona.png")
        self.assertTrue(view["hero"]["uses_image_background"])

    def test_public_views_hide_dv360_from_one_page_and_complete_plan_copy(self):
        row = {
            "nome_campanha": "Campanha editorial",
            "cliente": "Marca",
            "dados_detectados": {
                "planejamento": "## Mídia\nDV360 seleciona portais por contexto.",
                "one_page_v2": {"commercial_defense": {"why_this_mix": ["DV 360 amplia cobertura."]}},
                "folha": {"sections": [{"cards": [
                    {"type": "strategy", "body": "DV360 organiza a presença editorial."},
                    {"type": "creative", "title": "DV 360 em contexto", "body": "Peça de apoio."},
                ]}]},
            },
            "plan_content": {"sections": [{"id": "media", "title": "Mídia", "cards": [
                {"title": "DV360", "body": "DV 360 por segmentos."},
            ]}]},
        }
        proposal = public_view(row, document="proposal")
        complete = public_view(row, document="full_plan")
        self.assertNotIn("dv360", proposal["sheet"]["strategy"]["body"].lower())
        self.assertIn("Rede de portais e sites", proposal["defense_points"][0])
        self.assertNotIn("dv360", str(complete["chapters"]).lower())
        self.assertNotIn("dv360", str(complete["board"]).lower())

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
        self.assertEqual([item["id"] for item in view["views"]], ["folha", "plano"])
        self.assertEqual(view["default_view"], "plano")
        self.assertEqual(view["nav"][0]["id"], "plano-doc")
        self.assertTrue(view["nav_folha"])
        self.assertIn("cap-0", [item["id"] for item in view["nav_plano"]])

    def test_complete_plan_renders_nested_markdown_without_tokens(self):
        chapters = plan_chapters(
            "## Indicadores\n"
            "### UTM recomendado\n"
            "Use **leads qualificados** em `utm_campaign`.\n\n"
            "1. Validar origem\n"
            "   - Meta Ads\n"
            "   - Places\n\n"
            "| KPI | Meta |\n| --- | --- |\n| CTR | *A definir* |\n"
        )
        blocks = chapters[0]["blocks"]
        self.assertEqual([block["type"] for block in blocks], ["heading", "p", "list", "table"])
        self.assertIn("<strong>leads qualificados</strong>", blocks[1]["html"])
        self.assertIn("<code>utm_campaign</code>", blocks[1]["html"])
        self.assertTrue(blocks[2]["ordered"])
        self.assertEqual(blocks[2]["items"][0]["children"][0]["type"], "list")
        self.assertIn("<em>A definir</em>", blocks[3]["rows"][0][1])

    def test_public_context_has_friendly_updated_time_and_executive_fallback(self):
        view = public_view({
            "nome_campanha": "Campanha X", "cliente": "Cliente", "updated_at": "2026-09-15T00:02:45+00:00",
            "dados_detectados": {"plan_mode": "completo", "planejamento": "## Estratégia\nTexto.", "folha": {"sections": [{"cards": [{"type": "strategy", "body": "Tese."}]}]}},
            "plan_content": {"sections": []},
        })
        self.assertTrue(view["updated_at"].startswith("Atualizado"))
        self.assertEqual(len(view["executive_facts"]), 1)
        self.assertNotIn("Verba", {item[0] for item in view["executive_facts"]})
        self.assertFalse(view["hero"]["has_image"])
        self.assertEqual(format_public_updated("not-a-date")["label"], "Atualizado em not-a-date")

    def test_completo_only_uses_plano_view_on_same_link(self):
        view = public_view({
            "nome_campanha": "Só documento",
            "cliente": "Cliente",
            "dados_detectados": {
                "plan_mode": "completo",
                "planejamento": "## Capa\nTexto.\n\n## Mix\nDetalhe.\n",
            },
            "plan_content": {"sections": []},
        })
        self.assertFalse(view["tem_folha"])
        self.assertTrue(view["tem_completo"])
        self.assertEqual(view["views"], [{"id": "plano", "label": "Plano completo"}])
        self.assertEqual(view["default_view"], "plano")
        self.assertEqual(view["nav_folha"], [])
        self.assertEqual(view["nav"][0]["id"], "plano-doc")
        self.assertNotIn("visao", [item["id"] for item in view["nav"]])

    def test_one_page_with_completo_defaults_to_folha(self):
        view = public_view({
            "nome_campanha": "Folha e plano",
            "cliente": "Cliente",
            "dados_detectados": {
                "plan_mode": "one_page",
                "planejamento": "## Capa\nTexto.\n",
                "folha": {"sections": [{"cards": [{"type": "strategy", "body": "Tese."}]}]},
            },
            "plan_content": {"sections": []},
        })
        self.assertTrue(view["tem_folha"])
        self.assertTrue(view["tem_completo"])
        self.assertEqual(view["default_view"], "folha")
        self.assertEqual(view["nav"][0]["id"], "visao")
        self.assertEqual(len(view["nav_folha"]), 6)

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
        self.assertIn('id="visao"', html)
        self.assertIn('id="estrategia"', html)
        self.assertIn('id="investimento"', html)
        self.assertIn('id="periodo"', html)
        self.assertIn('id="canais"', html)
        self.assertNotIn('id="portais"', html)
        self.assertIn('id="criativos"', html)
        self.assertNotIn('id="premissas"', html)
        self.assertIn("cc-hero", html)
        self.assertIn("cc-donut", html)
        self.assertIn("cc-gantt", html)
        self.assertIn('property="og:image"', html)
        self.assertIn('name="twitter:card" content="summary_large_image"', html)
        self.assertIn('rel="icon"', html)
        self.assertIn("Visão geral", html)
        self.assertIn("Salvar PDF", html)
        self.assertIn("Compartilhar", html)
        self.assertIn("cc-doc-card", html)
        self.assertIn("is-lead", html)
        self.assertIn("data-cc-view", html)
        self.assertIn("cc-panel-folha", html)
        self.assertIn("cc-panel-plano", html)
        self.assertIn("plano-doc", html)
        self.assertIn("ainda não tem conteúdo público", html)
        self.assertIn("Centralcomm", error)
        self.assertIn("Smart Planner", error)
        self.assertNotIn("base_erp.html", error)
        self.assertIn('target="_blank"', wizard)
        self.assertIn("noopener noreferrer", wizard)
        self.assertIn('target="_blank"', index)
        self.assertIn("row.share_url", index)
        self.assertIn('target="_blank"', canvas)
        self.assertIn("share_url", canvas)
        self.assertIn('id="sp-folha-form"', canvas)
        self.assertIn("sp-gallery", canvas)
        self.assertIn("Criar marca no Workspace", canvas)
        self.assertNotIn("sp-qr", canvas)
        self.assertNotIn("sp-mockup", canvas)

    def test_public_view_always_exposes_a_share_image(self):
        view = public_view({
            "nome_campanha": "Lançamento",
            "cliente": "Marca exemplo",
            "dados_detectados": {"folha": {"sections": [{"cards": [{"type": "strategy", "body": "Tese."}]}]}},
            "plan_content": {"sections": []},
        })
        self.assertIn("share-placeholder.svg", view["share_image"])

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

    def test_water_campaign_builds_balanced_book(self):
        view = public_view({
            "nome_campanha": "Uso Consciente da Água",
            "cliente": "Anunciante",
            "objetivo": "reconhecimento",
            "publico_alvo": "População geral, com foco em responsáveis pelas decisões domésticas.",
            "budget": "R$ 250.000",
            "prazo": "3 meses",
            "dados_detectados": {
                "plan_mode": "one_page",
                "anunciante_confidencial": True,
                "folha": {
                    "meta": {
                        "objective": "Reconhecimento",
                        "publico": "População geral, com foco em responsáveis pelas decisões domésticas.",
                        "period": "3 meses",
                        "market": "interior",
                        "market_detail": "Interior de Minas Gerais",
                        "budget": "R$ 250.000 no total",
                        "canais": "3 canais",
                    },
                    "media": {
                        "method_label": "Funil do objetivo",
                        "channels": [
                            {"id": "youtube", "label": "YouTube", "pct": 45, "amount_label": "R$ 112.500"},
                            {"id": "meta_ads", "label": "Meta Ads", "pct": 33, "amount_label": "R$ 82.500"},
                            {"id": "dv360", "label": "Rede de portais e sites", "pct": 22, "amount_label": "R$ 55.000"},
                        ],
                        "pace": {
                            "how": "R$ 250.000 no período · ~R$ 83.333/mês",
                            "months": [
                                {"label": "Set", "amount": 45640, "amount_label": "R$ 45.640"},
                                {"label": "Out", "amount": 88357, "amount_label": "R$ 88.357"},
                                {"label": "Nov", "amount": 116003, "amount_label": "R$ 116.003"},
                            ],
                        },
                    },
                    "sections": [{"cards": [
                        {"type": "strategy", "body": "Tese sobre economia de água no interior.\n\nLiderar em YouTube.\n\nLevar a mensagem institucional."},
                        {"type": "creative", "title": "Economizar água começa em casa", "body": "Pequenas atitudes no dia a dia."},
                        {"type": "defense", "body": "YouTube lidera.\n\nMeta reforça.\n\nDV360 cobre."},
                    ]}],
                },
            },
            "plan_content": {"sections": []},
        })
        self.assertEqual(view["title"], "Uso Consciente da Água")
        self.assertEqual(view["client"], "Confidencial")
        self.assertEqual(view["media"]["total"], 250000)
        self.assertEqual(sum(item["amount"] for item in view["media"]["months"]), 250000)
        self.assertEqual(sum(item["pct"] for item in view["media"]["channels"]), 100)
        self.assertEqual(len(view["nav"]), 6)
        self.assertEqual(view["views"], [{"id": "folha", "label": "Página única"}])
        self.assertEqual(view["default_view"], "folha")
        self.assertEqual(view["nav_plano"], [])
        self.assertTrue(view["hero"]["image"].endswith("hero-water.svg"))
        self.assertTrue(view["inventory"])
        month_from_bars = [
            sum(channel["bars"][index]["amount"] for channel in view["media"]["channels"])
            for index in range(3)
        ]
        self.assertEqual(month_from_bars, [45640, 88357, 116003])
        board_titles = [item["title"] for item in view["strategy_board"]]
        self.assertIn("Tese estratégica", board_titles)
        self.assertIn("Diretriz", board_titles)
        self.assertIn("Público prioritário", board_titles)
        self.assertEqual(view["funnel"][0]["channel"], "YouTube")
        self.assertEqual(view["funnel"][0]["title"], "Sensibilizar")
        self.assertIn("45%", view["funnel"][0]["text"])
        self.assertTrue(view["overview"].startswith("Tese sobre economia"))
        self.assertNotIn("Abrir a conversa com escala audiovisual.", [item["text"] for item in view["funnel"]])
        self.assertIn("R$ 116.003", view["reading_items"][-1]["text"])
        youtube = view["media"]["channels"][0]
        self.assertEqual(len(youtube["week_bars"]), 12)
        self.assertEqual(sum(cell["amount"] for cell in youtube["week_bars"]), 112500)
        self.assertGreater(youtube["week_bars"][-1]["heat"], youtube["week_bars"][0]["heat"])
        self.assertIn("Novembro", youtube["flight_note"])
        self.assertTrue(view["media"]["has_weekly"])
        self.assertEqual(view["media"]["week_count"], 12)
        self.assertEqual(view["media"]["checks"], [])
        self.assertEqual(youtube["role_short"], "Canal líder")
        self.assertTrue(view["inventory"])
        self.assertEqual(view["inventory_filters"][0]["id"], "todos")
        self.assertIn("portais", [item["id"] for item in view["inventory_filters"]])
        self.assertNotIn("assumptions", view)
        self.assertNotIn("metric_note", view)
        self.assertTrue(any(item.get("status_tone") == "soft" for item in view["inventory"]))

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
        self.assertEqual(row["share_url"], "/smart-planner/p/abc123/proposta")
        self.assertEqual(row["public_token"], "abc123")
        self.assertEqual(row["href"], "/smart-planner/p/abc123/editar")
        self.assertEqual(row["canvas_href"], "/smart-planner/p/abc123/editar")
