from datetime import date, timedelta
from unittest import mock

import pytest
from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_overview as overview


def test_windows_keep_the_same_length_and_rolling_windows_end_yesterday():
    windows = overview.windows_for(date(2026, 9, 1), date(2026, 9, 10), today=date(2026, 10, 3))
    assert windows['period'] == (date(2026, 9, 1), date(2026, 9, 10))
    assert windows['period_previous'] == (date(2026, 8, 22), date(2026, 8, 31))
    assert windows['last7'] == (date(2026, 9, 26), date(2026, 10, 2))
    assert windows['previous7'] == (date(2026, 9, 19), date(2026, 9, 25))
    assert windows['last30'] == (date(2026, 9, 3), date(2026, 10, 2))
    assert windows['previous30'] == (date(2026, 8, 4), date(2026, 9, 2))


def test_media_windows_sum_days_and_null_cost_without_currency():
    daily = [{'date': date(2026, 10, 2), 'impressions': 100, 'clicks': 10, 'cost': 5.0, 'conversions': 1},
             {'date': date(2026, 9, 24), 'impressions': 50, 'clicks': 5, 'cost': None, 'conversions': 0}]
    windows = {'a': (date(2026, 9, 26), date(2026, 10, 2)), 'b': (date(2026, 9, 19), date(2026, 9, 25))}
    out = overview.media_windows(daily, windows)
    assert out['a'] == {'impressions': 100, 'clicks': 10, 'cost': 5.0, 'conversions': 1}
    assert out['b']['impressions'] == 50 and out['b']['cost'] is None


def test_fill_days_has_one_entry_per_day():
    days = [date(2026, 9, 1), date(2026, 9, 2)]
    rows = [{'date': date(2026, 9, 2), 'impressions': 3, 'clicks': 1, 'cost': 2.5, 'conversions': 0}]
    assert overview.fill_days(rows, days, overview.MEDIA_FIELDS, 'BRL') == [
        {'date': '2026-09-01', 'impressions': 0.0, 'clicks': 0.0, 'cost': 0.0, 'conversions': 0.0},
        {'date': '2026-09-02', 'impressions': 3.0, 'clicks': 1.0, 'cost': 2.5, 'conversions': 0.0}]
    assert overview.fill_days(rows, days, overview.MEDIA_FIELDS, None)[1]['cost'] is None


@pytest.fixture
def http():
    app = Flask(__name__)
    app.secret_key = 'test'
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    overview.register(bp)
    app.register_blueprint(bp)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 42
    return client


def test_compare_is_scoped_to_the_client_and_filters(http):
    calls = []
    # Recent dates, so every window is still inside the Super Tag retention.
    start = date.today() - timedelta(days=20)
    end = start + timedelta(days=9)

    def rows(sql, params=()):
        calls.append((sql, params))
        if 'to_regclass' in sql:
            return [{'ready': True}]
        if 'cadu_reports_campaign_daily_metrics' in sql:
            return [{'date': start + timedelta(days=4), 'impressions': 1000, 'clicks': 40, 'cost_micros': 20_000_000,
                     'conversions': 2, 'currencies': ['BRL']}]
        if 'GROUP BY 1' in sql:
            return [{'date': start - timedelta(days=1), 'sessions': 7, 'conversions': 1}]
        if 'supertag_events' in sql:
            return [{'period_sessions': 10, 'period_visitors': 8, 'period_conversions': 2, 'period_previous_sessions': 5}]
        return []
    with mock.patch.object(overview, '_rows', rows), mock.patch.object(overview, '_ready', return_value=True), \
         mock.patch.object(overview, '_selection', return_value={'client_id': 7, 'role': 'admin', 'user_id': 42}):
        response = http.get(f'/connect/api/v2/reports/overview/compare?start_date={start}&end_date={end}&account_id=3')
    assert response.status_code == 200
    body = response.get_json()
    media_sql, media_params = next(call for call in calls if 'campaign_daily_metrics' in call[0])
    assert media_params['client'] == 7 and media_params['account_id'] == 3 and 'a.id=%(account_id)s' in media_sql
    assert all(params.get('client') == 7 for sql, params in calls if 'to_regclass' not in sql)
    assert body['currency'] == 'BRL' and body['media_source'] == 'google_ads_script'
    assert body['media']['period'] == {'impressions': 1000, 'clicks': 40, 'cost': 20.0, 'conversions': 2}
    assert body['media']['period_previous']['impressions'] == 0
    assert body['site']['period'] == {'sessions': 10, 'visitors': 8, 'conversions': 2}
    assert body['windows']['period_previous'] == {'start': (start - timedelta(days=10)).isoformat(), 'end': (start - timedelta(days=1)).isoformat()}
    assert len(body['previous_daily']['media']) == 10
    assert body['previous_daily']['site'][-1] == {'date': (start - timedelta(days=1)).isoformat(), 'sessions': 7.0, 'conversions': 1.0}


def test_compare_rejects_bad_input_and_needs_login(http):
    with mock.patch.object(overview, '_selection', return_value={'client_id': 7}):
        assert http.get('/connect/api/v2/reports/overview/compare?start_date=2026-09-10&end_date=2026-09-01').status_code == 400
        assert http.get('/connect/api/v2/reports/overview/compare?campaign_id=x').status_code == 400
    app = Flask(__name__)
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    overview.register(bp)
    app.register_blueprint(bp)
    assert app.test_client().get('/connect/api/v2/reports/overview/compare').status_code == 401
