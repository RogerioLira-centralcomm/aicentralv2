import unittest
from pathlib import Path

from jinja2 import Environment

from aicentralv2.cadu_credits import (
    build_credit_recommendation,
    calculate_credit_position,
    movement_effect,
)


class CaduCreditsRulesTest(unittest.TestCase):
    def test_position_combines_allowance_adjustments_and_usage(self):
        self.assertEqual(
            calculate_credit_position(100, 35, 15),
            {
                'allowance': 100,
                'adjustments': 15,
                'used': 35,
                'available': 80,
                'effective_limit': 115,
                'usage_percentage': 30.4,
            },
        )

    def test_movement_effect_separates_balance_adjustment_from_usage(self):
        self.assertEqual(movement_effect('bonus', 10), {'adjustment_delta': 10, 'usage_delta': 0})
        self.assertEqual(movement_effect('withdrawal', 4), {'adjustment_delta': -4, 'usage_delta': 0})
        self.assertEqual(movement_effect('usage', 3), {'adjustment_delta': 0, 'usage_delta': 3})
        self.assertEqual(movement_effect('refund', 2), {'adjustment_delta': 0, 'usage_delta': -2})
        self.assertEqual(movement_effect('purchase', 25), {'adjustment_delta': 25, 'usage_delta': 0})

    def test_recommendation_projects_usage_and_selects_next_plan(self):
        position = calculate_credit_position(100, 60, 0)
        result = build_credit_recommendation(
            position, days_elapsed=15, days_in_month=30,
            plan_options=[{'name': '100', 'limit': 100}, {'name': 'Pro 150', 'limit': 150}],
        )
        self.assertEqual(result['projected'], 120)
        self.assertEqual(result['level'], 'attention')
        self.assertEqual(result['recommended_plan']['name'], 'Pro 150')

    def test_invalid_movement_is_rejected(self):
        with self.assertRaises(ValueError):
            movement_effect('unknown', 10)
        with self.assertRaises(ValueError):
            movement_effect('bonus', 0)

    def test_templates_parse_and_expose_management_contract(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ('cadu_creditos_lista.html', 'cadu_creditos_detalhe.html'):
            source = (root / 'aicentralv2' / 'templates' / filename).read_text(encoding='utf-8')
            Environment().parse(source)
        detail = (root / 'aicentralv2' / 'templates' / 'cadu_creditos_detalhe.html').read_text(encoding='utf-8')
        self.assertIn('name="movement_type"', detail)
        self.assertIn('Extrato de movimentações', detail)
        self.assertIn('purchaseDialog', detail)
        self.assertNotIn('window.confirm(', detail)
        self.assertNotIn('window.alert(', detail)


if __name__ == '__main__':
    unittest.main()
