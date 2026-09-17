from unittest import TestCase

from aicentralv2.cadu_connect.report_review import compare_metrics, parse_metrics
from aicentralv2.cadu_connect.report_analysis import MAX_EXTRACTION_TOKENS


class ReportReviewTests(TestCase):
    def test_extraction_budget_is_bounded_before_provider_call(self):
        self.assertEqual(MAX_EXTRACTION_TOKENS, 3200)

    def test_parses_explicit_brazilian_decimal_and_evidence(self):
        form = {
            'metric_name': ['Investimento'], 'metric_value': ['12450,80'],
            'metric_unit': ['BRL'], 'metric_definition': ['Valor gasto'],
            'metric_scope': ['01 a 31 de maio'], 'metric_evidence': ['Print: resumo da conta'],
        }
        metric = parse_metrics(_Form(form))[0]
        self.assertEqual(metric['value'], '12450.80')
        self.assertEqual(metric['raw'], '12450,80')

    def test_rejects_ambiguous_numeric_format_and_duplicate_identity(self):
        bad = {
            'metric_name': ['Impressões'], 'metric_value': ['12.500'], 'metric_unit': ['count'],
            'metric_definition': ['Entrega'], 'metric_scope': ['Maio'], 'metric_evidence': ['Print'],
        }
        with self.assertRaises(ValueError):
            parse_metrics(_Form(bad))
        duplicate = {key: value * 2 for key, value in dict(bad, metric_value=['12500']).items()}
        with self.assertRaises(ValueError):
            parse_metrics(_Form(duplicate))

    def test_compares_same_metric_as_percent_points(self):
        before = [dict(name='CTR', value='1.2', unit='percent', definition='Cliques / impressões', scope='Maio', evidence='A')]
        after = [dict(name='CTR', value='1.8', unit='percent', definition='Cliques / impressões', scope='Maio', evidence='B')]
        change = compare_metrics(before, after)[0]
        self.assertEqual(change['status'], 'changed')
        self.assertEqual(str(change['difference']), '0.6')


class _Form(dict):
    def getlist(self, key):
        return self.get(key, [])
