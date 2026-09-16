"""Domain rules tested without initializing the application or database."""
import importlib.util
from pathlib import Path
import unittest
from datetime import date
from decimal import Decimal

spec = importlib.util.spec_from_file_location(
    "report_rules", Path(__file__).resolve().parents[1]
    / "aicentralv2/cadu_connect/report_rules.py",
)
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


class ReportRulesTests(unittest.TestCase):
    def test_snapshot_change_is_difference_not_sum(self):
        change = rules.metric_change("10000", "15000", comparable=True)
        self.assertEqual(change["difference"], Decimal("5000"))
        self.assertEqual(change["relative_percent"], Decimal("50"))
        self.assertEqual(change["status"], "changed")

    def test_changes_handle_missing_zero_and_incompatible_observations(self):
        self.assertIsNone(rules.metric_change(0, 100, comparable=True)["relative_percent"])
        self.assertEqual(rules.metric_change(10, 10, comparable=True)["status"], "unchanged")
        self.assertEqual(rules.metric_change(None, 10, comparable=True)["status"], "missing_value")
        self.assertIsNone(rules.metric_change(10, 20, comparable=False)["difference"])

    def test_rate_changes_are_percentage_points(self):
        change = rules.metric_change("1.5", "2.0", comparable=True, percentage_points=True)
        self.assertEqual(change["difference"], Decimal("0.5"))
        self.assertEqual(change["difference_unit"], "percentage_points")
        self.assertIsNone(change["relative_percent"])

    def test_end_date_inclusive_and_does_not_claim_campaign_completed(self):
        start, end = date(2026, 9, 1), date(2026, 9, 16)
        self.assertEqual(rules.planned_phase(start, end, today=end), "within_planned_window")
        self.assertEqual(rules.planned_phase(start, end, today=date(2026, 9, 17)), "after_planned_end")

    def test_incomplete_and_invalid_dates(self):
        self.assertEqual(rules.planned_phase(None, None, today=date.today()), "unknown")
        with self.assertRaises(ValueError):
            rules.planned_phase(date(2026, 10, 1), date(2026, 9, 1), today=date.today())

    def test_zero_unknown_and_exact_decimal_calculations(self):
        self.assertEqual(rules.ratio("0", "10"), Decimal("0"))
        self.assertEqual(rules.ratio("0.3", "3"), Decimal("0.1"))
        self.assertIsNone(rules.ratio("10", "0"))
        self.assertIsNone(rules.ratio(None, "10"))
        for invalid in ("NaN", "Infinity", True, "1.234,56"):
            with self.assertRaises(ValueError):
                rules.decimal_value(invalid)

    def test_goals_require_comparability_and_support_cost_ceilings(self):
        self.assertEqual(rules.goal_assessment(900, 500, direction="minimum", comparable=False), "not_comparable")
        self.assertEqual(rules.goal_assessment(None, 500, direction="minimum", comparable=True), "unknown")
        self.assertEqual(rules.goal_assessment(8, 10, direction="maximum", comparable=True), "met")
        self.assertEqual(rules.goal_assessment(320, 500, direction="minimum", comparable=True), "below_target")


if __name__ == "__main__":
    unittest.main()
