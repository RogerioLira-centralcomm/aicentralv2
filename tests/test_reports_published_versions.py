"""Publicação de relatórios: retrato da jornada, página pública congelada e senha."""
import unittest
from datetime import datetime

from aicentralv2.cadu_connect.reports_v1 import _journey_summary


class JourneySummaryTests(unittest.TestCase):
    def test_keeps_only_counts_and_step_names(self):
        summary = _journey_summary({'funnel': {'entries': 390, 'conversions': 21, 'rate': 5.4, 'visitor': 'x'},
                                    'steps': [{'name': 'Landing', 'sessions': 390, 'email': 'a@b.c'},
                                              {'name': '', 'sessions': 3}, {'name': 'Form', 'sessions': None}]})
        self.assertEqual(summary, {'entries': 390, 'conversions': 21, 'steps': [{'name': 'Landing', 'sessions': 390}]})

    def test_rejects_invalid_values(self):
        self.assertIsNone(_journey_summary('nope'))
        summary = _journey_summary({'funnel': {'entries': -1, 'conversions': True}, 'steps': 'x'})
        self.assertEqual(summary, {'entries': None, 'conversions': None, 'steps': []})


class PublicTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from aicentralv2 import create_app
        cls.app = create_app()

    def render(self, **context):
        from flask import render_template
        with self.app.test_request_context('/connect/r/token'):
            return render_template('cadu_connect/public_report.html', token='token', **context)

    def test_frozen_flow_report_shows_results_funnel_and_versions(self):
        snapshot = {'document': {'scope': 'flow', 'flow_name': 'Lead', 'objective': 'Leads'},
                    'results': {'period': {'start': '2026-09-01', 'end': '2026-09-30', 'previous_start': '2026-08-02', 'previous_end': '2026-08-31'},
                                'currency': 'BRL', 'totals': {'impressions': 1000, 'clicks': 50, 'cost': 100.0, 'conversions': 2, 'ctr': 5.0, 'cpa': 50.0, 'roas': None},
                                'previous': {'cost': 80.0}, 'campaigns': [{'name': 'Search', 'cost': 100.0, 'clicks': 50, 'ctr': 5.0, 'conversions': 2, 'cpa': 50.0}]},
                    'journey': {'entries': 40, 'conversions': 4, 'steps': [{'name': 'Landing', 'sessions': 40}]}}
        html = self.render(report={'campaign_name': 'Setembro', 'revision': 3, 'updated_at': datetime(2026, 10, 1, 9, 0), 'document': snapshot['document']},
                           snapshot=snapshot, versions=[3, 2], latest=3)
        for text in ('Relatório do fluxo', '01/09/2026 a 30/09/2026', 'R$ 100,00', 'Custo por conversão do fluxo', 'R$ 25,00', 'Landing', '?v=2', 'noindex'):
            self.assertIn(text, html)

    def test_legacy_link_without_snapshot_still_renders_text(self):
        html = self.render(report={'campaign_name': 'Antigo', 'revision': 1, 'updated_at': 'ontem', 'document': {'objective': 'Objetivo X'}},
                           snapshot=None, versions=[], latest=None)
        self.assertIn('Objetivo X', html)
        self.assertNotIn('Resultados', html)

    def test_password_page(self):
        from flask import render_template
        with self.app.test_request_context('/connect/r/token'):
            html = render_template('cadu_connect/public_report_password.html', title='Setembro', error='Senha incorreta.')
        self.assertIn('type="password"', html)
        self.assertIn('Senha incorreta.', html)


if __name__ == '__main__':
    unittest.main()
