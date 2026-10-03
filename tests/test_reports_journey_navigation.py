import uuid
from datetime import date, datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_journey as journey

SITE = str(uuid.uuid4())
URL = '/connect/api/v2/reports/journey/navigation'
_END = date.today() - timedelta(days=1)
PERIOD = f'start_date={(_END - timedelta(days=29)).isoformat()}&end_date={_END.isoformat()}'   # previous period stays inside retention


@pytest.mark.parametrize('args,expected', [
    ((None, None, None, None, 'exemplo.com.br'), 'direct'),
    (('', '', '', '', 'exemplo.com.br'), 'direct'),
    (('google', 'cpc', None, None, 'exemplo.com.br'), 'google_ads'),
    ((' Google ', ' CPC ', None, None, 'exemplo.com.br'), 'google_ads'),
    (('google', 'organic', None, None, 'exemplo.com.br'), 'organic'),
    ((None, None, 'Cj0KCQjw', None, 'exemplo.com.br'), 'google_ads'),          # gclid without UTM
    ((None, None, 'IwAR0abc', None, 'exemplo.com.br'), 'social'),              # fbclid without UTM
    ((None, None, None, 'www.google.com.br', 'exemplo.com.br'), 'organic'),
    ((None, None, None, 'mail.google.com', 'exemplo.com.br'), 'referral'),     # webmail is not search
    ((None, None, None, 'googleads.g.doubleclick.net', 'exemplo.com.br'), 'google_ads'),
    ((None, None, None, 'com.google.android.googlequicksearchbox', 'exemplo.com.br'), 'organic'),
    ((None, None, None, 'l.instagram.com', 'exemplo.com.br'), 'social'),
    ((None, None, None, 'parceiro.com', 'exemplo.com.br'), 'referral'),
    ((None, None, None, 'www.exemplo.com.br', 'exemplo.com.br'), 'unknown'),   # referred by the site itself
    ((None, None, None, 'blog.exemplo.com.br', 'www.exemplo.com.br'), 'unknown'),
    (('chatgpt.com', None, None, 'www.exemplo.com.br', 'exemplo.com.br'), 'referral'),
    (('ig', 'social', None, None, 'exemplo.com.br'), 'social'),
    (('newsletter', 'email', None, None, 'exemplo.com.br'), 'other'),
    ((None, 'referral', None, None, 'exemplo.com.br'), 'referral'),
    (('bing', 'cpc', None, None, 'exemplo.com.br'), 'other'),
])
def test_origin_group_separates_direct_from_unknown_and_groups_the_rest(args, expected):
    assert journey.origin_group(*args) == expected


def test_origin_sql_covers_every_group_and_keeps_percent_signs_out_of_the_query():
    sql = journey.origin_group_sql()
    for group in journey.ORIGIN_GROUPS:
        assert f"'{group}'" in sql
    assert '%' not in sql and '{' not in sql
    assert "->>'click_id'" in sql and "~ '^Iw'" in sql
    assert set(journey.ORIGIN_LABELS) == set(journey.ORIGIN_HINTS) == set(journey.ORIGIN_GROUPS)


def summary(**sessions):
    return [{'origin': origin, 'sessions': count, 'views': count * 2, 'single_page_sessions': count // 2,
             'converted_sessions': count // 10} for origin, count in sessions.items()]


def test_origin_groups_list_every_group_with_zeros_and_hide_small_rates():
    groups = journey.origin_groups(summary(direct=40, unknown=5))
    assert [item['origin'] for item in groups] == list(journey.ORIGIN_GROUPS)
    by = {item['origin']: item for item in groups}
    assert by['direct']['sessions'] == 40 and by['direct']['share'] == 88.9 and by['direct']['conversion_rate'] == 10.0
    assert by['unknown']['sessions'] == 5 and by['unknown']['conversion_rate'] is None
    assert by['social']['sessions'] == 0 and by['social']['share'] == 0.0 and by['social']['label'] == 'Social'


def test_totals_follow_the_chosen_origin():
    rows = summary(direct=40, google_ads=20)
    assert journey.navigation_totals(rows)['sessions'] == 60
    assert journey.navigation_totals(rows, 'google_ads') == {'sessions': 20, 'views': 40, 'single_page_sessions': 10, 'converted_sessions': 2}
    assert journey.navigation_totals(rows, 'social')['sessions'] == 0


def test_previous_window_has_the_same_length_and_ends_where_the_period_starts():
    zone = ZoneInfo('America/Sao_Paulo')
    since, until = datetime(2026, 9, 1, tzinfo=zone), datetime(2026, 10, 1, tzinfo=zone)
    assert journey.previous_window(since, until) == (datetime(2026, 8, 2, tzinfo=zone), since)


def test_changes_need_a_usable_sample_on_both_sides():
    current = {'sessions': 60, 'views': 120, 'single_page_sessions': 30, 'converted_sessions': 6}
    previous = {'sessions': 40, 'views': 100, 'single_page_sessions': 10, 'converted_sessions': 2}
    changes = journey.navigation_changes(current, previous)
    assert changes == {'sessions': 50.0, 'views_per_session': -20.0, 'single_page_rate': 100.0, 'conversion_rate': 100.0}
    assert journey.navigation_changes(current, {**previous, 'sessions': 29}) is None
    assert journey.navigation_changes({**current, 'sessions': 10}, previous) is None
    assert journey.navigation_changes(current, None) is None


def page(path, views, entries, exits, single, sessions, converted, **extra):
    return {'site_id': uuid.UUID(SITE), 'host': 'exemplo.com.br', 'path': path, 'views': views, 'visitors': views,
            'entries': entries, 'exits': exits, 'single_page': single, 'sessions': sessions, 'converted_sessions': converted,
            'conversions': converted, 'avg_active_seconds': extra.get('active')}


def test_pages_get_rates_only_on_a_usable_base_and_flag_leaks():
    totals = {'sessions': 100, 'views': 200, 'single_page_sessions': 40, 'converted_sessions': 10}   # site exit 50%, conversion 10%
    pages = journey.navigation_pages([
        page('/servicos', 40, 20, 30, 10, 35, 1, active=12.5),   # exits 75% > 50%, conversion 2.9% < 5% → leak
        page('/contato', 40, 5, 30, 2, 35, 10),                  # converts well → no leak
        page('/raro', 6, 6, 6, 6, 6, 0),                         # small base: no rates, no flag
    ], totals)
    by = {item['path']: item for item in pages}
    assert by['/servicos']['leak'] is True and by['/servicos']['exit_rate'] == 75.0 and by['/servicos']['bounce_rate'] == 50.0
    assert by['/servicos']['avg_active_seconds'] == 12.5 and by['/servicos']['site_id'] == SITE
    assert by['/contato']['leak'] is False and by['/contato']['bounce_rate'] is None          # 5 entries < base
    assert by['/raro']['small_base'] is True and by['/raro']['leak'] is False and by['/raro']['conversion_rate'] is None
    assert by['/raro']['exit_rate'] == 100.0                    # kept numeric for the pages list


def test_sequences_keep_two_to_five_pages_with_share_and_conversion():
    rows = [{'site_id': uuid.UUID(SITE), 'host': 'exemplo.com.br', 'pages': ['/', '/contato'], 'sessions': 12, 'converted_sessions': 3, 'continued': 0},
            {'site_id': uuid.UUID(SITE), 'host': 'exemplo.com.br', 'pages': ['/', '/a', '/b', '/c', '/d'], 'sessions': 4, 'converted_sessions': 1, 'continued': 2},
            {'site_id': uuid.UUID(SITE), 'host': 'exemplo.com.br', 'pages': ['/'], 'sessions': 9, 'converted_sessions': 0, 'continued': 0}]
    out = journey.path_sequences(rows, 40)
    assert [item['pages'] for item in out] == [['/', '/contato'], ['/', '/a', '/b', '/c', '/d']]
    assert out[0]['share'] == 30.0 and out[0]['conversion_rate'] == 25.0 and out[0]['site_id'] == SITE
    assert out[1]['conversion_rate'] is None and out[1]['continued'] == 2


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.secret_key = 'test'
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    journey.register(bp)
    flask_app.register_blueprint(bp)
    return flask_app


def fake_rows_for(seen):
    def fake_rows(sql, params=()):
        seen.append((sql, params))
        if 'GROUP BY origin' in sql:
            first = not any('GROUP BY origin' in earlier for earlier, _ in seen[:-1])
            return summary(direct=30, unknown=10) if first else summary(direct=20)
        if 'AS from_path' in sql:
            return [{'host': 'exemplo.com.br', 'from_path': '/', 'to_path': '/contato', 'sessions': 8}]
        if 'continued' in sql:
            return [{'site_id': uuid.UUID(SITE), 'host': 'exemplo.com.br', 'pages': ['/', '/contato'], 'sessions': 8, 'converted_sessions': 2, 'continued': 0}]
        return [page('/', 60, 40, 20, 10, 40, 4)]
    return fake_rows


def get(app, query=''):
    seen = []
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    with mock.patch.object(journey, '_rows', fake_rows_for(seen)), \
         mock.patch.object(journey, '_selection', return_value={'client_id': 174, 'role': 'admin', 'user_id': 1}):
        response = client.get(URL + query)
    return response, seen


def test_route_returns_origins_totals_previous_pages_and_sequences(app):
    response, seen = get(app, f'?{PERIOD}')
    body = response.get_json()
    assert response.status_code == 200
    assert body['totals']['sessions'] == 40 and body['previous']['sessions'] == 20 and body['quality']['low_sample'] is False
    assert body['changes'] is None                               # previous period below the minimum sample
    assert body['previous_window']['since'] and body['origin'] is None
    assert [item['origin'] for item in body['origin_groups']] == list(journey.ORIGIN_GROUPS)
    assert [item['platform'] for item in body['origins']] == ['direct', 'unknown']   # kept for the overview tab
    assert body['pages'][0]['bounce_rate'] == 25.0 and body['sequences'][0]['share'] == 20.0 and body['paths'][0]['to_path'] == '/contato'
    assert len(seen) == 5
    for sql, params in seen:
        assert '{site}' not in sql and '%(site)s' not in sql and params['client'] == 174 and params['origin'] is None
    previous = [params for sql, params in seen if 'GROUP BY origin' in sql][1]
    assert previous['until'] == seen[0][1]['since']


def test_route_filters_by_origin_and_site(app):
    response, seen = get(app, f'?origin=unknown&site_id={SITE}&{PERIOD}')
    body = response.get_json()
    assert response.status_code == 200 and body['origin'] == 'unknown'
    assert body['totals']['sessions'] == 10 and body['quality']['low_sample'] is True
    for sql, params in seen:
        assert 'AND e.site_id=%(site)s::uuid' in sql and params['site'] == SITE and params['origin'] == 'unknown'
    assert all('scoped' in sql for sql, _ in seen if 'GROUP BY origin' not in sql)


@pytest.mark.parametrize('query', ['?origin=facebook', '?site_id=nope', '?start_date=2026-09-01'])
def test_route_rejects_invalid_input(app, query):
    assert get(app, query)[0].status_code == 400


def test_route_requires_login(app):
    assert app.test_client().get(URL).status_code == 401
