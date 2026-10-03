"""Agentes do relatório: revisor determinístico, redator e sugestor com o modelo simulado."""
import json
import unittest
from unittest import mock

from aicentralv2.cadu_connect import report_agents

RESULTS = {'period': {'start': '2026-09-01', 'end': '2026-09-05', 'previous_start': '2026-08-27', 'previous_end': '2026-08-31', 'defaulted': False},
           'currency': 'BRL', 'totals': {'cost': 500.0, 'impressions': 10000, 'clicks': 200, 'conversions': 20, 'conversion_value': 0, 'ctr': 2.0, 'cpa': 25.0, 'roas': None},
           'previous': {'cost': 400.0, 'clicks': 180, 'conversions': 18}, 'campaigns': [{'id': 1, 'name': 'Search', 'cost': 500.0, 'clicks': 200, 'conversions': 20, 'cpa': 25.0}],
           'daily': [{'date': '2026-09-01'}, {'date': '2026-09-02'}, {'date': '2026-09-05'}]}
FLOW_DOC = {'scope': 'flow', 'flow_name': 'Lead', 'flow_campaigns': [{'id': 1}], 'objective': 'Gerar leads', 'goals': 'CPL abaixo de R$ 30',
            'management_notes': 'Texto antigo', 'blocks': [{'id': 'notes', 'type': 'notes', 'title': 'Contexto', 'hidden': False},
                                                          {'id': 'rec-1', 'type': 'recommendations', 'title': 'Recomendações', 'hidden': False, 'text': ''}]}
JOURNEY = {'entries': 40, 'conversions': 4, 'steps': [{'name': 'Landing', 'sessions': 40}, {'name': 'Obrigado', 'sessions': 0}]}


def fake_llm(content):
    return mock.patch('aicentralv2.services.openrouter_service.chat_completion',
                      return_value={'message': {'content': json.dumps(content)}, 'model': 'test', 'usage': {}})


class ReviewTests(unittest.TestCase):
    def test_finds_gaps_duplicates_unlinked_and_flow_mismatches(self):
        findings = report_agents.review_findings(document=FLOW_DOC, results=RESULTS, journey=JOURNEY,
                                                 duplicate_days=['2026-09-02'], unlinked_campaigns=[{'campaign_name': 'PMax'}])
        codes = [item['code'] for item in findings]
        for code in ('missing_days', 'duplicate_sources', 'unlinked_campaigns', 'silent_steps', 'conversion_gap', 'landing_loss'):
            self.assertIn(code, codes)
        self.assertEqual(findings[0]['severity'], 'high')
        self.assertIn('2026-09-03', next(item for item in findings if item['code'] == 'missing_days')['evidence'])

    def test_clean_campaign_report_has_no_findings(self):
        results = {**RESULTS, 'daily': [{'date': f'2026-09-0{day}'} for day in range(1, 6)]}
        self.assertEqual(report_agents.review_findings(document={}, results=results, journey=None, duplicate_days=[], unlinked_campaigns=[]), [])

    def test_prioritize_skips_single_finding(self):
        self.assertIsNone(report_agents.prioritize([{'code': 'a', 'severity': 'high', 'title': 'A', 'evidence': ''}]))


class WriterTests(unittest.TestCase):
    def test_draft_keeps_only_known_blocks_and_real_changes(self):
        with fake_llm({'resumo': 'CPA caiu.', 'blocos': [{'id': 'notes', 'texto': 'CPA de R$ 25,00.'}, {'id': 'inventado', 'texto': 'x'},
                                                         {'id': 'rec-1', 'texto': ''}],
                       'novos_blocos': [{'tipo': 'next_steps', 'titulo': 'Próximos passos', 'texto': 'Testar nova landing.'},
                                        {'tipo': 'script', 'texto': 'x'}]}):
            draft = report_agents.draft_version(FLOW_DOC, RESULTS, JOURNEY)
        self.assertEqual([item['id'] for item in draft['changes']], ['notes'])
        self.assertEqual(draft['changes'][0]['before'], 'Texto antigo')
        self.assertEqual([item['type'] for item in draft['added']], ['next_steps'])

    def test_draft_without_changes_is_an_error(self):
        with fake_llm({'blocos': [{'id': 'notes', 'texto': 'Texto antigo'}]}):
            with self.assertRaises(report_agents.AgentError):
                report_agents.draft_version(FLOW_DOC, RESULTS, JOURNEY)


class SuggesterTests(unittest.TestCase):
    def test_only_valid_new_formulas_with_preview(self):
        with fake_llm({'metricas': [
            {'nome': 'Custo por lead do fluxo', 'formula': 'custo / conversoes_fluxo', 'unidade': 'BRL', 'melhor_quando': 'lower', 'meta': 30, 'definicao': 'Custo ÷ leads'},
            {'nome': 'Perigosa', 'formula': '__import__("os")', 'unidade': 'count'},
            {'nome': 'Custo por lead do fluxo', 'formula': 'custo / 2', 'unidade': 'BRL'}]}):
            result = report_agents.suggest_metrics(FLOW_DOC, RESULTS, JOURNEY)
        self.assertEqual(len(result['suggestions']), 1)
        self.assertEqual(result['suggestions'][0]['preview'], 125.0)


if __name__ == '__main__':
    unittest.main()
