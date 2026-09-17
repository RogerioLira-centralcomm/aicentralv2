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

    def test_projects_audience_card_with_compact_metrics(self):
        card = result_cards.project({
            "tool_name": "search_audiencias", "output": {
                "audiences": [{"nome": "Executivos", "alcance": "1,2 mi", "cpm": "R$ 28", "plataforma": "Programática"}],
            },
        })
        result = card["result"]
        self.assertEqual(result["type"], "audience")
        self.assertEqual(result["items"][0]["title"], "Executivos")
        self.assertEqual(len(result["items"][0]["metrics"]), 3)

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

    def test_projects_dify_agent_observation_without_exposing_tool_input(self):
        card = result_cards.project({
            "event": "agent_thought", "tool": "market_research", "tool_input": "PRIVATE",
            "observation": '{"title":"Mercado","summary":"Tendência identificada."}',
        })
        self.assertEqual(card["event"], "result")
        self.assertEqual(card["result"]["type"], "research")
        self.assertNotIn("PRIVATE", str(card))
