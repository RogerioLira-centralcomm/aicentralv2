from datetime import datetime, timedelta, timezone
from unittest import TestCase

from aicentralv2.cadu_connect import reports_google_ads_rules as rules

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
ACCOUNT = {'id': 1, 'name': 'Cemig Search', 'last_run_at': NOW - timedelta(hours=3), 'negatives_at': NOW - timedelta(days=1),
           'datasets': [], 'timed_out': False}
TERM = {'account_id': 1, 'campaign_external_id': '10', 'ad_group_external_id': '20', 'term_hash': 'h', 'campaign_name': 'C',
        'ad_group_name': 'G', 'status': 'NONE'}
NEGATIVE = {'account_id': 1, 'level': 'campaign', 'campaign_external_id': '10', 'ad_group_external_id': None,
            'attached_campaign_ids': [], 'keyword_text': 'gratis', 'match_type': 'BROAD', 'campaign_name': 'C'}


def build(**overrides):
    args = dict(accounts=[ACCOUNT], campaigns=[], terms=[], keywords=[], devices=[], negatives=[],
                totals={'cost': 1000, 'conversions': 20}, now=NOW)
    args.update(overrides)
    return rules.build_recommendations(**args)


class GoogleAdsRulesTest(TestCase):
    def test_term_action_follows_the_decision_order(self):
        self.assertEqual('excluded', rules.term_action({**TERM, 'status': 'EXCLUDED', 'clicks': 50, 'conversions': 0}, [], True))
        self.assertEqual('added', rules.term_action({**TERM, 'status': 'ADDED', 'clicks': 50, 'conversions': 0}, [], True))
        self.assertEqual('covered', rules.term_action({**TERM, 'search_term': 'curso gratis', 'clicks': 50, 'conversions': 0}, [NEGATIVE], True))
        self.assertEqual('add_keyword', rules.term_action({**TERM, 'search_term': 'tarifa social', 'clicks': 5, 'conversions': 3}, [], True))
        self.assertEqual('negate', rules.term_action({**TERM, 'search_term': 'tarifa emprego', 'clicks': 12, 'conversions': 0}, [], True))
        # Without a recent negative snapshot the system cannot tell the term is not blocked already.
        self.assertEqual('review', rules.term_action({**TERM, 'search_term': 'tarifa emprego', 'clicks': 12, 'conversions': 0}, [], False))
        self.assertEqual('keep', rules.term_action({**TERM, 'search_term': 'tarifa', 'clicks': 3, 'conversions': 0}, [], True))

    def test_stale_script_and_incomplete_run_come_first(self):
        account = {**ACCOUNT, 'last_run_at': NOW - timedelta(hours=60), 'datasets': [{'name': 'search_term_metrics', 'status': 'truncated'}]}
        items = build(accounts=[account], terms=[{**TERM, 'search_term': 'x y', 'clicks': 30, 'conversions': 0, 'cost': 90}])
        self.assertEqual(['script_stale', 'data_incomplete', 'negative_candidate'], [item['rule'] for item in items][:3])
        self.assertIn('2 dias', items[0]['summary'])
        self.assertIn('termos de pesquisa (cortado no limite de linhas)', items[1]['summary'])

    def test_negative_candidates_need_a_fresh_snapshot(self):
        term = {**TERM, 'search_term': 'tarifa emprego', 'clicks': 30, 'conversions': 0, 'cost': 90}
        items = build(accounts=[{**ACCOUNT, 'negatives_at': NOW - timedelta(days=9)}], terms=[term])
        self.assertEqual(['negatives_unknown'], [item['rule'] for item in items])

    def test_negative_conflict_with_active_keyword(self):
        keyword = {'account_id': 1, 'campaign_external_id': '10', 'ad_group_external_id': '20', 'criterion_external_id': '30',
                   'keyword_text': 'curso gratis', 'campaign_name': 'C', 'ad_group_name': 'G', 'impressions': 100, 'clicks': 5,
                   'conversions': 0, 'cost': 40}
        items = build(keywords=[keyword], negatives=[NEGATIVE])
        self.assertEqual('negative_conflict', items[0]['rule'])
        self.assertEqual('high', items[0]['severity'])
        self.assertIn('gratis', items[0]['summary'])

    def test_budget_limited_only_when_it_converts_at_or_below_account_cpa(self):
        campaign = {'account_id': 1, 'campaign_external_id': '10', 'campaign_name': 'C', 'clicks': 300, 'conversions': 30,
                    'cost': 990, 'budget': 100, 'active_days': 10}
        self.assertIn('budget_limited', [item['rule'] for item in build(campaigns=[campaign])])
        expensive = {**campaign, 'conversions': 5}
        self.assertNotIn('budget_limited', [item['rule'] for item in build(campaigns=[expensive])])

    def test_ordering_is_severity_then_impact(self):
        terms = [{**TERM, 'term_hash': str(i), 'search_term': f'termo {i}', 'clicks': 20, 'conversions': 0, 'cost': cost}
                 for i, cost in enumerate((10, 90, 40))]
        items = [item for item in build(terms=terms) if item['rule'] == 'negative_candidate']
        self.assertEqual([90, 40, 10], [item['impact']['value'] for item in items])

    def test_device_with_high_cpa(self):
        devices = [{'device': 'TABLET', 'clicks': 40, 'conversions': 1, 'cost': 200}]
        items = build(devices=devices)
        self.assertEqual('device_cpa', items[0]['rule'])
        self.assertEqual('Tablet', items[0]['object']['label'])


class GoalRulesTest(TestCase):
    base = {'account_id': 1, 'campaign_external_id': '10', 'campaign_name': 'Luz', 'budget': 150}

    def test_pacing_over_suggests_the_daily_budget_that_closes_the_month_at_the_cap(self):
        campaign = {**self.base, 'cost': 1000, 'conversions': 30, 'goal': {'monthly_budget_cap': 3000},
                    'pacing': {'mtd_cost': 1200, 'days_left': 18, 'projected_cost': 3900, 'projected_conversions': 80}}
        item = rules.goal_recommendations([campaign])[0]
        self.assertEqual('pacing_over', item['rule'])
        self.assertIn('para 100,00', item['action'])  # (3000 - 1200) / 18

    def test_cap_reached_and_flight_ended_are_high(self):
        campaign = {**self.base, 'cost': 3100, 'conversions': 30, 'goal': {'monthly_budget_cap': 3000, 'flight_end': '2026-09-30', 'flight_ended': True},
                    'pacing': {'mtd_cost': 3100, 'days_left': 10, 'projected_cost': 4000, 'last3_cost': 300}}
        found = {item['rule']: item['severity'] for item in rules.goal_recommendations([campaign])}
        self.assertEqual('high', found['cap_reached'])
        self.assertEqual('high', found['flight_ended'])
        self.assertNotIn('pacing_over', found)

    def test_cpa_and_conversion_goal(self):
        campaign = {**self.base, 'cost': 6000, 'conversions': 80, 'target_cpa': 60,
                    'goal': {'target_cpa': 40, 'target_conversions_month': 200},
                    'pacing': {'mtd_cost': 300, 'days_left': 20, 'projected_cost': 3000, 'projected_conversions': 100}}
        found = [item['rule'] for item in rules.goal_recommendations([campaign])]
        self.assertEqual(['cpa_above_target', 'target_mismatch', 'conversion_goal_risk'], found)

    def test_room_in_the_budget_when_cpa_is_within_target(self):
        campaign = {**self.base, 'cost': 800, 'conversions': 40, 'goal': {'monthly_budget_cap': 3000, 'target_cpa': 30},
                    'pacing': {'mtd_cost': 800, 'days_left': 20, 'projected_cost': 1600}}
        item = rules.goal_recommendations([campaign])[0]
        self.assertEqual('pacing_under', item['rule'])
        self.assertIn('110,00', item['action'])  # (3000 - 800) / 20

    def test_no_goal_no_recommendation(self):
        self.assertEqual([], rules.goal_recommendations([{**self.base, 'cost': 999, 'conversions': 0}]))


class CollectionPlanTest(TestCase):
    def test_backfills_one_slice_per_run_until_the_history_floor(self):
        from datetime import date
        from aicentralv2.cadu_connect.reports_ingest_v2 import BACKFILL_STEP_DAYS, HISTORY_DAYS, collection_plan
        today = date(2026, 10, 2)
        first = collection_plan(today, None)
        self.assertEqual(['recent', 'backfill'], [item['kind'] for item in first])
        self.assertEqual('2026-09-19', first[0]['since'])
        second = collection_plan(today, date.fromisoformat(first[1]['since']))
        self.assertEqual((date.fromisoformat(first[1]['since']) - date.fromisoformat(second[1]['since'])).days, BACKFILL_STEP_DAYS)
        floor = today.toordinal() - HISTORY_DAYS + 1
        self.assertEqual(['recent'], [item['kind'] for item in collection_plan(today, date.fromordinal(floor))])
