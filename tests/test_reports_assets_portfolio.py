import datetime

from aicentralv2.cadu_connect import reports_assets as assets


def analysis(**overrides):
    base = {'totals': {'cost': 900.0, 'conversions': 4},
            'recommendations': [
                {'severity': 'high', 'impact': {'kind': 'cost', 'value': 300.0}, 'proposal': {'op': 'x'}, 'queued': None},
                {'severity': 'high', 'impact': {'kind': 'conversions', 'value': 2}, 'proposal': None},
                {'severity': 'medium', 'impact': {'kind': 'cost', 'value': 50.5}, 'proposal': {'op': 'y'}, 'queued': {'status': 'approved'}},
                {'severity': 'low', 'impact': {'kind': 'none', 'value': 0}}],
            'terms': [{'action': 'negate', 'cost': 120.0}, {'action': 'negate', 'cost': 30.5}, {'action': 'add_keyword', 'cost': 5}, {'action': 'keep', 'cost': 9}],
            'keywords': [{'quality_score': 3, 'cost': 10}, {'quality_score': 4, 'cost': 1}, {'quality_score': 4, 'cost': 0}, {'quality_score': 8, 'cost': 50}, {'quality_score': None, 'cost': 5}]}
    return {**base, **overrides}


ACCOUNT = {'id': 2, 'name': 'Loja', 'external_id': '123', 'last_run_at': datetime.datetime(2026, 10, 2, 12, 0),
           'datasets': [{'name': 'keyword_metrics', 'status': 'ok'}, {'name': 'ads', 'status': 'error'}]}


def test_row_agrees_with_the_action_center_counts():
    row = assets.account_row(ACCOUNT, analysis(), weak_ads=3)
    assert (row['high'], row['medium'], row['low']) == (2, 1, 1)
    assert row['at_stake'] == 350.5  # only recommendations measured in money
    assert row['pending_changes'] == 1  # a proposal that is not already queued
    assert row['waste_terms'] == 2 and row['waste_cost'] == 150.5 and row['opportunities'] == 1
    assert row['low_quality_keywords'] == 2  # score <= 4 with spend
    assert row['collection_problems'] == ['ads']


def test_gap_orders_by_work_and_counts_weak_ads_double():
    with_ads = assets.account_row(ACCOUNT, analysis(), weak_ads=3)
    without = assets.account_row(ACCOUNT, analysis(), weak_ads=None)
    assert with_ads['gap'] - without['gap'] == 6
    assert without['gap'] == 2 * 3 + 1 * 2 + 1 + 2 and without['weak_ads'] is None
