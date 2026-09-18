from unittest import TestCase

from aicentralv2.cadu_workspace.conversations import result_cards


class ResultCardsTest(TestCase):
    def test_projects_research_with_safe_sources_and_action(self):
        card = result_cards.project({
            "event": "tool_result", "tool": "market_research", "tool_output": {
                "title": "Mercado", "summary": "O mercado acelerou.",
                "sources": [
                    {"title": "Fonte confiável", "url": "https://example.com/report", "excerpt": "Dado relevante."},
                    {"title": "Não abrir", "url": "javascript:alert(1)", "excerpt": "Ignorado como link."},
                ],
            },
        })
        self.assertEqual(card["event"], "result")
        result = card["result"]
        self.assertEqual(result["type"], "research")
        self.assertEqual(result["items"][0]["url"], "https://example.com/report")
        self.assertEqual(result["items"][1]["url"], "")
        self.assertEqual(result["actions"][0]["id"], "continue_research")

    def test_projects_audience_card_excludes_commercial_metrics(self):
        card = result_cards.project({
            "tool_name": "search_audiencias", "output": {
                "audiences": [{"nome": "Executivos", "alcance": "1,2 mi", "cpm": "R$ 28", "plataforma": "Programática"}],
            },
        })
        result = card["result"]
        self.assertEqual(result["type"], "audience")
        self.assertEqual(result["items"][0]["title"], "Executivos")
        self.assertEqual(result["items"][0]["metrics"], [
            {"label": "Alcance", "value": "1,2 mi"},
            {"label": "Plataforma", "value": "Programática"},
        ])
        self.assertNotIn("CPM", str(result))
        self.assertNotIn("custo", result["actions"][0]["prompt"])

    def test_projects_link_and_screenshot_with_https_media_only(self):
        card = result_cards.project({
            "tool": "screenshot_url", "result": {
                "url": "https://example.com", "score": "Aprovado",
                "image_url": "javascript:bad", "issues": ["Sem problemas críticos"],
            },
        })
        result = card["result"]
        self.assertEqual(result["type"], "link")
        self.assertEqual(result["media"], [])
        self.assertEqual(result["actions"][0]["url"], "https://example.com")

    def test_projects_document_card_and_ignores_unknown_tool(self):
        card = result_cards.project({
            "tool": "pdf_process", "tool_output": {"filename": "briefing.pdf", "page_count": 4, "excerpt": "Objetivo: lançar."},
        })
        self.assertEqual(card["result"]["type"], "document")
        self.assertEqual(card["result"]["items"][0]["metrics"][0]["value"], "4")
        self.assertIsNone(result_cards.project({"tool": "untrusted_tool", "output": {"x": 1}}))

    def test_projects_all_enabled_dify_pdf_plugin_names_as_documents(self):
        names = ("pdf_single_page_extractor", "pdf_multi_pages_extractor", "pdf_page_counter",
                 "pdf_splitter", "pdf_to_png")
        for name in names:
            with self.subTest(name=name):
                card = result_cards.project({"tool": name, "output": {"filename": "arquivo.pdf", "summary": "Conteúdo extraído."}})
                self.assertEqual(card["result"]["type"], "document")

    def test_projects_dify_agent_observation_without_exposing_tool_input(self):
        card = result_cards.project({
            "event": "agent_thought", "tool": "market_research", "tool_input": "PRIVATE",
            "observation": '{"title":"Mercado","summary":"Tendência identificada."}',
        })
        self.assertEqual(card["event"], "result")
        self.assertEqual(card["result"]["type"], "research")
        self.assertNotIn("PRIVATE", str(card))

    def test_completed_briefing_becomes_a_safe_work_card(self):
        card = result_cards.from_answer(
            'Crie um briefing para a campanha.',
            '## Briefing inicial\n\n1) Objetivo de negócio\n\n2) Público-alvo\n\n3) Prazo',
            'ci:123',
        )
        self.assertEqual(card['event'], 'result')
        self.assertEqual(card['result']['type'], 'briefing')
        self.assertEqual([item['title'] for item in card['result']['items']],
                         ['Briefing inicial', 'Objetivo de negócio', 'Público-alvo', 'Prazo'])
        self.assertTrue(any(action['id'] == 'briefing_project' for action in card['result']['actions']))
