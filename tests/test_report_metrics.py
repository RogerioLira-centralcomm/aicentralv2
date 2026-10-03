"""Métricas personalizadas do relatório: fórmulas seguras, metas e cálculo no retrato publicado."""
import unittest

from aicentralv2.cadu_connect.report_metrics import compute, parse, validate_metric, validate_metrics

TOTALS = {'cost': 1000.0, 'impressions': 20000, 'clicks': 400, 'conversions': 10, 'conversion_value': 5000.0}
JOURNEY = {'entries': 300, 'conversions': 25}


class FormulaTests(unittest.TestCase):
    def test_precedence_parentheses_and_unary_minus(self):
        result = compute([{'kind': 'formula', 'formula': '(custo + 200) / -(-conversoes_fluxo) * 2', 'unit': 'count'}], TOTALS, JOURNEY)
        self.assertAlmostEqual(result[0]['result'], 96.0)

    def test_rejects_anything_outside_the_grammar(self):
        for bad in ('__import__("os")', 'custo ** 2', 'custo; 1', 'desconhecida / 2', 'custo /', '(custo', '', 'x' * 201, 'custo 2'):
            with self.assertRaises(ValueError, msg=bad):
                parse(bad)

    def test_missing_variable_or_zero_division_gives_none(self):
        result = compute([{'kind': 'formula', 'formula': 'custo / conversoes_fluxo', 'unit': 'BRL'},
                          {'kind': 'formula', 'formula': 'custo / (cliques - cliques)', 'unit': 'BRL'}], TOTALS, None)
        self.assertEqual([item['result'] for item in result], [None, None])

    def test_percent_unit_multiplies_by_100_and_target_direction(self):
        result = compute([
            {'kind': 'formula', 'formula': 'conversoes_fluxo / entradas_fluxo', 'unit': 'percent', 'target': 5, 'direction': 'higher'},
            {'kind': 'formula', 'formula': 'custo / conversoes_fluxo', 'unit': 'BRL', 'target': 30, 'direction': 'lower'},
            {'kind': 'manual', 'value': 12.5, 'unit': 'count', 'target': None}], TOTALS, JOURNEY)
        self.assertAlmostEqual(result[0]['result'], 8.3333, places=3)
        self.assertEqual(result[0]['status'], 'met')
        self.assertEqual(result[1]['result'], 40.0)
        self.assertEqual(result[1]['status'], 'missed')
        self.assertIsNone(result[2]['status'])


class ValidationTests(unittest.TestCase):
    def test_clean_metric(self):
        metric = validate_metric({'name': ' Custo  por lead ', 'kind': 'formula', 'formula': ' CUSTO / conversoes_fluxo ', 'target': '30,5', 'unit': 'BRL', 'direction': 'lower'})
        self.assertEqual(metric['name'], 'Custo por lead')
        self.assertEqual(metric['formula'], 'custo / conversoes_fluxo')
        self.assertEqual(metric['target'], 30.5)
        self.assertEqual(metric['id'], 'custo-por-lead')

    def test_manual_needs_value_and_list_limits(self):
        with self.assertRaises(ValueError):
            validate_metric({'name': 'Leads CRM', 'kind': 'manual'})
        with self.assertRaises(ValueError):
            validate_metrics([{'name': 'A', 'kind': 'manual', 'value': 1, 'id': 'a'}] * 2)
        with self.assertRaises(ValueError):
            validate_metrics([{'name': f'M{n}', 'kind': 'manual', 'value': 1} for n in range(21)])


if __name__ == '__main__':
    unittest.main()
