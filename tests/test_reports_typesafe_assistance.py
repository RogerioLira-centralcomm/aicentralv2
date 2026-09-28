from unittest import TestCase
from unittest.mock import Mock, patch

import pytest
from flask import Blueprint, Flask

from aicentralv2.cadu_connect import report_review, reports_typesafe, reports_v1
from aicentralv2.services.typesafe_service import TypeSafeError


def choice_answer(options, selected):
    keys = list(options)
    remainder = 0.1 / (len(keys) - 1)
    probabilities = {key: remainder for key in keys}
    probabilities[selected] = 0.9
    return {'type': 'choice', 'choice': selected,
            'probabilities': probabilities,
            'confidence': (len(keys) * 0.9 - 1) / (len(keys) - 1)}


class ReportsTypeSafeAssistanceTest(TestCase):
    @patch('aicentralv2.cadu_connect.reports_typesafe.system_one')
    def test_planner_selects_only_from_actions_eligible_for_the_report(self, system_one):
        def evaluate(state, questions):
            options = questions['next_action']['criteria']
            self.assertIn('compare_periods', options)
            self.assertIn('reconcile_sources', options)
            self.assertIn('validate_tracking', options)
            self.assertEqual(state['reviewed_metrics'][0]['name'], 'Leads')
            return {'answers': {'next_action': choice_answer(options, 'reconcile_sources')},
                    'model': 'jev-1.13.0', 'usage': {'input_tokens': 30, 'output_tokens': 4}}

        system_one.side_effect = evaluate
        plan = reports_typesafe.suggest_report_plan(
            {'objective': 'Gerar leads qualificados', 'goals': 'Aumentar conversões'},
            [
                {'name': 'Leads', 'value': '100', 'unit': 'count', 'period': '2026-09'},
                {'name': 'Leads', 'value': '90', 'unit': 'count', 'period': '2026-09'},
                {'name': 'Leads', 'value': '120', 'unit': 'count', 'period': '2026-08'},
            ], reviewed_source_count=2)

        self.assertEqual(plan['action'], 'reconcile_sources')
        self.assertEqual(plan['title'], reports_typesafe.PLAN_ACTIONS['reconcile_sources']['title'])
        self.assertEqual(plan['source_count'], 2)
        system_one.assert_called_once()

    @patch('aicentralv2.cadu_connect.reports_typesafe.system_one')
    def test_planner_does_not_call_different_scopes_a_source_conflict(self, system_one):
        def evaluate(state, questions):
            self.assertNotIn('reconcile_sources', questions['next_action']['criteria'])
            return {'answers': {'next_action': choice_answer(
                questions['next_action']['criteria'], 'collect_evidence')},
                'model': 'jev-1.13.0', 'usage': {}}

        system_one.side_effect = evaluate
        reports_typesafe.suggest_report_plan(
            {'objective': 'Leads', 'goals': '100 leads'},
            [{'name': 'Leads', 'value': '20', 'unit': 'count',
              'definition': 'Leads do site', 'scope': 'Orgânico', 'period': '2026-09'},
             {'name': 'Leads', 'value': '10', 'unit': 'count',
              'definition': 'Leads do site', 'scope': 'Pago', 'period': '2026-09'}])

    @patch('aicentralv2.cadu_connect.reports_typesafe.system_one')
    def test_planner_falls_back_to_evidence_collection_when_data_is_missing(self, system_one):
        def evaluate(state, questions):
            options = questions['next_action']['criteria']
            self.assertIn('collect_evidence', options)
            self.assertIn('collect_baseline', options)
            self.assertIn('complete_brief', options)
            self.assertNotIn('compare_periods', options)
            return {'answers': {'next_action': choice_answer(options, 'collect_baseline')},
                    'model': 'jev-1.13.0', 'usage': {'input_tokens': 12, 'output_tokens': 3}}

        system_one.side_effect = evaluate
        plan = reports_typesafe.suggest_report_plan({}, [], reviewed_source_count=0)
        self.assertEqual(plan['action'], 'collect_baseline')
        self.assertEqual(plan['metric_count'], 0)

    @patch('aicentralv2.cadu_connect.reports_typesafe.system_one')
    def test_evidence_reviewer_returns_typed_findings_without_editing_metrics(self, system_one):
        metrics = [{'name': 'Cliques', 'raw': '1250', 'unit': 'count',
                    'definition': 'Cliques no período', 'scope': 'Meta Ads · setembro',
                    'evidence': 'Cliques: 1250; contato: dados@example.test, +55 11 99999-1234'}]

        def evaluate(state, questions):
            self.assertIn('`metrics[0].evidence`', questions['m0']['instructions']['question'])
            self.assertEqual(state['metrics'][0]['evidence'],
                             'Cliques: 1250; contato: [email], [telefone]')
            return {'answers': {'m0': choice_answer(questions['m0']['criteria'], 'supported')},
                    'model': 'jev-1.13.0', 'usage': {'input_tokens': 40, 'output_tokens': 4}}

        system_one.side_effect = evaluate
        review = reports_typesafe.review_source_metrics(metrics, source_context={'supplier': 'Meta Ads'})
        self.assertEqual(review['judgments'][0]['judgment'], 'supported')
        self.assertEqual(review['omitted_count'], 0)
        self.assertEqual(metrics[0]['raw'], '1250')

    @patch('aicentralv2.cadu_connect.reports_typesafe.system_one')
    def test_evidence_reviewer_caps_batch_and_reports_unreviewed_metrics(self, system_one):
        metrics = [{'name': f'Métrica {i}', 'raw': str(i), 'unit': 'count',
                    'definition': 'Definição', 'scope': 'Escopo', 'evidence': f'Valor {i}'}
                   for i in range(reports_typesafe.MAX_REVIEW_METRICS + 3)]

        def evaluate(state, questions):
            self.assertEqual(len(state['metrics']), reports_typesafe.MAX_REVIEW_METRICS)
            answers = {key: choice_answer(question['criteria'], 'unclear')
                       for key, question in questions.items()}
            return {'answers': answers, 'model': 'jev-1.13.0',
                    'usage': {'input_tokens': 200, 'output_tokens': 60}}

        system_one.side_effect = evaluate
        review = reports_typesafe.review_source_metrics(metrics)
        self.assertEqual(len(review['judgments']), reports_typesafe.MAX_REVIEW_METRICS)
        self.assertEqual(review['omitted_count'], 3)

    def test_reviewer_rejects_invalid_unit_and_incomplete_typed_answer(self):
        with self.assertRaises(ValueError):
            reports_typesafe.review_source_metrics([{'name': 'Cliques', 'raw': '3', 'unit': 'money',
                'definition': 'x', 'scope': 'x', 'evidence': 'x'}])
        with pytest.raises(TypeSafeError, match='inconsistente'):
            reports_typesafe.validate_choice({'answers': {'q': {'type': 'choice', 'choice': 'a',
                'probabilities': {'a': .4, 'b': .4}, 'confidence': .3}}}, 'q', {'a': 'A', 'b': 'B'}, 'teste')

    @patch('aicentralv2.cadu_connect.reports_typesafe.system_one')
    def test_reviewer_preserves_large_numeric_evidence_and_redacts_phone_context(self, system_one):
        metric = {'name': 'Receita', 'raw': '12345678901', 'unit': 'BRL',
                  'definition': 'Receita total', 'scope': 'Setembro',
                  'evidence': 'Receita 12345678901; suporte (11) 99999-1234'}

        def evaluate(state, questions):
            self.assertIn('Receita 12345678901', state['metrics'][0]['evidence'])
            self.assertIn('[telefone]', state['metrics'][0]['evidence'])
            self.assertEqual(state['source_context']['supplier'], 'contato [telefone]')
            return {'answers': {'m0': choice_answer(questions['m0']['criteria'], 'supported')},
                    'model': 'jev-1.13.0', 'usage': {}}

        system_one.side_effect = evaluate
        reports_typesafe.review_source_metrics(
            [metric], source_context={'supplier': 'contato (11) 99999-1234'})

    def test_planner_rejects_invalid_metric_collections(self):
        for metrics in (None, {'name': 'Leads'}, ['invalid']):
            with self.subTest(metrics=metrics), self.assertRaises(ValueError):
                reports_typesafe.suggest_report_plan({}, metrics)

    def test_reviewer_rejects_ambiguous_numeric_values_before_model_call(self):
        with self.assertRaisesRegex(ValueError, 'separador de milhar'):
            reports_typesafe.review_source_metrics([{'name': 'Cliques', 'raw': '1.250', 'unit': 'count',
                'definition': 'Total', 'scope': 'Setembro', 'evidence': 'Cliques: 1.250'}])


class ReportsTypeSafeRoutesTest(TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = 'reports-typesafe-test'
        blueprint = Blueprint('reports_typesafe_test', __name__)
        reports_v1.register(blueprint)
        self.report_rows = Mock(return_value=[])
        report_review.register(blueprint, self.report_rows)
        app.register_blueprint(blueprint)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = 42
            session['family_csrf'] = 'csrf-test'

    def test_planner_is_scoped_to_selected_client_and_read_only(self):
        selected = {'organization_id': 23, 'client_id': 1000000000,
                    'client_name': 'Reports', 'role': 'admin', 'client_kind': 'reports'}
        report = {'id': 5, 'campaign_name': 'Campanha',
                  'document': {'objective': 'Leads', 'goals': '10'}, 'revision': 3}

        def query(_sql, _params=()):
            return [{'ready': False}] if 'to_regclass' in _sql else [report]

        plan = {'action': 'collect_evidence', 'title': 'Reunir evidência suficiente',
                'steps': ['Adicionar fonte.']}
        with patch.object(reports_v1, '_selection', return_value=selected), \
                patch.object(reports_v1, '_write_guard') as write_guard, \
                patch.object(reports_v1, '_rows', side_effect=query), \
                patch('aicentralv2.cadu_connect.reports_typesafe.suggest_report_plan',
                      return_value=plan) as suggest:
            response = self.client.post('/api/v1/reports/workspaces/5/plan',
                                        json={'client_id': 1000000000},
                                        headers={'X-CSRF-Token': 'csrf-test'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['plan'], plan)
        suggest.assert_called_once_with({'objective': 'Leads', 'goals': '10'}, [],
                                        reviewed_source_count=0)
        write_guard.assert_called_once_with(selected)

    def test_viewer_cannot_use_planner(self):
        selected = {'organization_id': 23, 'client_id': 1000000000,
                    'client_name': 'Reports', 'role': 'viewer', 'client_kind': 'reports'}
        with patch.object(reports_v1, '_selection', return_value=selected), \
                patch.object(reports_v1, '_rows') as query:
            response = self.client.post('/api/v1/reports/workspaces/5/plan',
                                        json={'client_id': 1000000000},
                                        headers={'X-CSRF-Token': 'csrf-test'})
        self.assertEqual(response.status_code, 403)
        query.assert_not_called()

    def test_evidence_reviewer_is_bound_to_source_and_returns_unpersisted_review(self):
        report = {'id': 5, 'document': {'objective': 'Leads'}, 'revision': 3}
        selected = {'organization_id': 23, 'client_id': 1000000000,
                    'client_name': 'Reports', 'role': 'admin', 'client_kind': 'reports'}
        source = {'id': 9, 'supplier': 'Meta Ads',
                  'period_start': '2026-09-01', 'period_end': '2026-09-30'}
        review = {'judgments': [], 'omitted_count': 0}
        metrics = [{'name': 'Leads', 'raw': '12', 'unit': 'count', 'evidence': 'Leads: 12'}]
        with patch('aicentralv2.cadu_connect.report_review.authorized_report',
                   return_value=(report, selected)), \
                patch('aicentralv2.cadu_connect.reports_typesafe.review_source_metrics',
                      return_value=review) as reviewer:
            self.report_rows.return_value = [source]
            response = self.client.post('/relatorios/5/fontes/9/revisar-typesafe',
                                        json={'metrics': metrics},
                                        headers={'X-CSRF-Token': 'csrf-test'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['review'], review)
        reviewer.assert_called_once()
        self.report_rows.assert_called_once()

    def test_viewer_cannot_request_source_evidence_review(self):
        selected = {'organization_id': 23, 'client_id': 1000000000,
                    'client_name': 'Reports', 'role': 'viewer', 'client_kind': 'reports'}
        with patch('aicentralv2.cadu_connect.report_review.authorized_report',
                   return_value=({'document': {}, 'revision': 3}, selected)):
            response = self.client.post('/relatorios/5/fontes/9/revisar-typesafe',
                                        json={'metrics': []},
                                        headers={'X-CSRF-Token': 'csrf-test'})
        self.assertEqual(response.status_code, 403)
        self.report_rows.assert_not_called()


if __name__ == '__main__':
    import unittest
    unittest.main()
