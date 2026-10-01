import datetime
import uuid
from unittest import mock

import pytest
from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_pages as pages
from aicentralv2.cadu_connect.reports_page_identity import canonical_page, split_url, sql_normalized_path
from aicentralv2.cadu_connect.reports_page_metrics import (
    DICTIONARY, MIN_RELIABLE_SESSIONS, breakdown, build_metrics, compare, device_bucket, pct, sum_groups)

SITE = str(uuid.uuid4())


def test_page_identity_ignores_query_fragment_case_www_and_trailing_slash():
    expected = ('exemplo.com.br', '/lp/verao')
    assert split_url('https://WWW.Exemplo.com.br/LP/Verao/?utm_source=google#topo') == expected
    assert split_url('http://exemplo.com.br/lp/verao') == expected
    assert canonical_page('www.exemplo.com.br', '/LP/Verao/') == expected
    assert split_url('https://exemplo.com.br') == ('exemplo.com.br', '/')


def test_identity_rule_matches_the_flow_matcher_when_it_is_available():
    matching = pytest.importorskip('aicentralv2.cadu_connect.reports_flow_matching')
    if not hasattr(matching, 'normalize_path'):
        pytest.skip('flow matcher not updated in this checkout')
    for host, path in (('WWW.A.com', '/X/'), ('a.com', ''), ('sub.a.com', '/LP/verao/')):
        assert canonical_page(host, path) == (matching.normalize_host(host), matching.normalize_path(path))


def test_page_identity_rejects_non_web_addresses():
    for value in ('', None, '{lpurl}', 'javascript:alert(1)', 'ftp://x.com/a', 'android-app://pkg'):
        assert split_url(value) is None


def test_sql_expression_matches_the_python_rule():
    assert sql_normalized_path('e.page_path') == "COALESCE(NULLIF(LOWER(RTRIM(e.page_path,'/')),''),'/')"


def test_every_dictionary_metric_is_defined_and_unique():
    keys = [item['key'] for item in DICTIONARY]
    assert len(keys) == len(set(keys))
    assert all(item['definition'] and item['label'] and item['unit'] and item['source'] for item in DICTIONARY)
    produced = set(build_metrics({}, {}))
    assert {key for key in keys} <= produced


def test_unmeasured_values_are_none_never_zero():
    metrics = build_metrics({'sessions': 0}, {})
    assert metrics['exit_rate'] is None and metrics['session_conversion_rate'] is None
    assert metrics['avg_active_seconds'] is None and metrics['clicks_per_session'] is None
    assert metrics['scroll_50'] is None and metrics['sessions'] == 0 and metrics['reliable'] is False


def test_time_is_none_without_measured_visits_even_if_an_average_exists():
    assert build_metrics({'sessions': 5, 'avg_active_ms': 9000, 'measured_visits': 0}, {})['avg_active_seconds'] is None


def test_rates_use_their_declared_denominators():
    metrics = build_metrics({'sessions': 40, 'clicks': 10, 'scroll_50': 20, 'measured_visits': 4, 'avg_active_ms': 6000},
                            {'entrances': 20, 'exits': 10, 'single_page': 5, 'converted': 4})
    assert metrics['exit_rate'] == 25.0 and metrics['single_page_rate'] == 25.0 and metrics['session_conversion_rate'] == 10.0
    assert metrics['scroll_50'] == 50.0 and metrics['clicks_per_session'] == 0.25 and metrics['avg_active_seconds'] == 6.0
    assert metrics['reliable'] is (40 >= MIN_RELIABLE_SESSIONS)


def test_compare_skips_missing_values_and_zero_baselines():
    assert compare({'sessions': 5}, None) is None
    change = compare({'sessions': 10, 'exit_rate': None, 'conversions_on_page': 3, 'reliable': True},
                     {'sessions': 5, 'exit_rate': 10.0, 'conversions_on_page': 0, 'reliable': False})
    assert change['sessions'] == {'absolute': 5, 'relative': 100.0}
    assert change['conversions_on_page']['relative'] is None
    assert 'exit_rate' not in change and 'reliable' not in change


def test_device_buckets_and_helpers():
    assert [device_bucket(w) for w in (None, 390, 800, 1440)] == ['unknown', 'mobile', 'tablet', 'desktop']
    assert pct(1, 3) == 33.3 and pct(1, 0) is None
    groups = [{'sessions': 2, 'converted': 1, 'entrances': 1, 'exits': 2, 'single_page': 1},
              {'sessions': 3, 'converted': 0, 'entrances': 2, 'exits': 0, 'single_page': 0}]
    assert sum_groups(groups)['entrances'] == 3
    assert breakdown(groups, lambda row: 'a' if row['sessions'] == 2 else 'b')[0] == ('b', {'sessions': 3, 'converted': 0})


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = 'test'
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    pages.register(bp)
    app.register_blueprint(bp)
    http = app.test_client()
    with http.session_transaction() as session:
        session['user_id'] = 1
    return http


def fake_rows(site_found=True, paid_table=True):
    counts = {'views': 3, 'sessions': 3, 'visitors': 3, 'clicks': 1, 'form_submits': 0, 'conversions_on_page': 1,
              'measured_visits': 2, 'avg_active_ms': 8000, 'median_active_ms': 8000,
              'scroll_25': 2, 'scroll_50': 1, 'scroll_75': 0, 'scroll_100': 0}
    group = {'origin': 'utm:google', 'device': 'mobile', 'campaign': 'verao', 'sessions': 3, 'entrances': 2, 'exits': 1,
             'single_page': 1, 'converted': 1}
    paid = {'account_id': 5, 'account_name': 'Conta', 'currency': 'BRL', 'campaign_external_id': '111', 'campaign_name': 'Verão',
            'impressions': 1000, 'clicks': 100, 'cost_micros': 50_000_000, 'conversions': 5, 'conversion_value_micros': 0,
            'last_date': datetime.date.today()}

    def rows(sql, params=()):
        if 'FROM cadu_reports_supertag_sites' in sql:
            return [{'id': SITE, 'label': 'Site', 'allowed_host': 'www.exemplo.com.br'}] if site_found else []
        if 'to_regclass' in sql:
            return [{'ok': paid_table}]
        if 'COUNT(*) FILTER (WHERE event_kind=' in sql:
            return [counts]
        if 'WITH ps AS' in sql:
            return [group]
        if 'FROM cadu_reports_gads_landing_page_daily' in sql:
            return [paid]
        if 'search_term_daily' in sql or 'keyword_daily' in sql:
            return []
        if 'cadu_reports_flow_monitor_checks' in sql:
            return [{'checked_at': datetime.datetime.now(datetime.timezone.utc), 'status': 'online',
                     'pages': [{'host': 'exemplo.com.br', 'path': '/LP/Verao/', 'status': 'online', 'http_status': 200,
                                'duration_ms': 150, 'detail': 'ok'},
                               {'host': 'exemplo.com.br', 'path': '/outra', 'status': 'offline'}]}]
        raise AssertionError(sql)
    return rows


def call(client, query, **kwargs):
    with mock.patch.object(pages, '_rows', fake_rows(**kwargs)), \
         mock.patch.object(pages, '_selection', return_value={'client_id': 7, 'role': 'admin'}):
        return client.get('/connect/api/v2/reports/pages/overview?' + query)


def test_overview_joins_numbers_paid_origin_and_health_on_one_canonical_page(client):
    body = call(client, f'site_id={SITE}&path=/LP/Verao/%3Futm=1&days=30').get_json()
    assert body['page'] == {'site_id': SITE, 'site_label': 'Site', 'host': 'exemplo.com.br', 'path': '/lp/verao'}
    assert body['metrics']['sessions'] == 3 and body['metrics']['session_conversion_rate'] == 33.3
    assert body['paid']['campaigns'][0]['cost_per_conversion_micros'] == 10_000_000
    assert body['paid']['observed_campaigns'][0]['matched_campaign_id'] is None  # utm name 'verao' != 'Verão' ... accents differ
    assert body['health']['monitored'] and body['health']['latest']['http_status'] == 200 and len(body['health']['timeline']) == 1
    assert body['sources'][0]['label'] == 'Google Ads' and body['devices'][0]['label'] == 'Celular'
    assert len(body['dictionary']) == len(DICTIONARY) and body['window']['rolling'] is True


def test_previous_window_is_dropped_when_it_falls_outside_retention(client):
    body = call(client, f'site_id={SITE}&path=/lp&days=60').get_json()
    assert body['previous'] is None and body['change'] is None and '90 dias' in body['previous_unavailable']
    assert call(client, f'site_id={SITE}&path=/lp&days=30').get_json()['previous'] is not None


def test_paid_side_degrades_when_the_google_ads_tables_are_missing(client):
    body = call(client, f'site_id={SITE}&path=/lp', paid_table=False).get_json()
    assert body['paid']['available'] is False and 'script v2' in body['paid']['reason']


def test_request_validation(client):
    assert call(client, f'site_id={SITE}&path=sem-barra').status_code == 400
    assert call(client, f'site_id={SITE}&path=/a&days=91').status_code == 400
    assert call(client, f'site_id={SITE}&path=/a&days=0').status_code == 400
    assert call(client, 'site_id=nao-e-uuid&path=/a').status_code == 400
    assert call(client, f'site_id={SITE}&path=/a', site_found=False).status_code == 404


def test_requires_login():
    app = Flask(__name__)
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    pages.register(bp)
    app.register_blueprint(bp)
    assert app.test_client().get('/connect/api/v2/reports/pages/overview').status_code == 401


# ---- interaction map -------------------------------------------------------
from aicentralv2.cadu_connect.reports_page_metrics import build_elements, build_grid  # noqa: E402


def test_grid_buckets_clicks_into_a_ten_by_ten_viewport():
    grid = build_grid([{'cx': 0, 'cy': 0, 'clicks': 4}, {'cx': 9, 'cy': 9, 'clicks': 6}, {'cx': 12, 'cy': 3, 'clicks': 99}])
    assert grid['cells'][0][0] == 4 and grid['cells'][9][9] == 6 and grid['peak'] == 6 and grid['total'] == 10
    assert build_grid([])['peak'] == 0


def test_element_rate_needs_visibility_tracking_and_never_exceeds_100():
    rows = [{'element_id': 'cta', 'clicks': 12, 'whatsapp_clicks': 2, 'click_sessions': 10, 'seen_sessions': 8},
            {'element_id': 'menu', 'clicks': 3, 'whatsapp_clicks': 0, 'click_sessions': 3, 'seen_sessions': 0}]
    cta, menu = build_elements(rows, 40)
    assert cta['click_rate_of_seen'] == 100.0 and cta['share_of_sessions'] == 25.0 and cta['clicks_per_session'] == 1.2
    assert menu['seen_sessions'] is None and menu['click_rate_of_seen'] is None
    assert build_elements(rows, 0)[0]['share_of_sessions'] is None


def interactions_rows(device_rows=None):
    def rows(sql, params=()):
        if 'FROM cadu_reports_supertag_sites' in sql:
            return [{'id': SITE, 'label': 'Site', 'allowed_host': 'exemplo.com.br'}]
        if "AS cx" in sql and "'dx'" not in sql:
            assert 'viewport_width<768' in sql or 'TRUE' in sql or 'viewport_width>=' in sql
            return [{'cx': 4, 'cy': 2, 'clicks': 40}]
        if "AS cx" in sql and "'dx'" in sql:
            return [{'cx': 3, 'cy': 7, 'clicks': 30}]
        if 'median_height' in sql:
            return [{'clicks': 30, 'median_height': 5400}]
        if 'AS element_id' in sql:
            return [{'element_id': 'cta', 'clicks': 40, 'whatsapp_clicks': 5, 'click_sessions': 30, 'seen_sessions': 50}]
        if 'AS unidentified' in sql:
            return [{'clicks': 60, 'unidentified': 20, 'sessions': 100, 'visibility_events': 70}]
        if 'AS device' in sql:
            return device_rows if device_rows is not None else [{'device': 'mobile', 'clicks': 40}, {'device': 'desktop', 'clicks': 20}]
        raise AssertionError(sql)
    return rows


def interactions(client, query, **kwargs):
    with mock.patch.object(pages, '_rows', interactions_rows(**kwargs)), \
         mock.patch.object(pages, '_selection', return_value={'client_id': 7, 'role': 'admin'}):
        return client.get('/connect/api/v2/reports/pages/interactions?' + query)


def test_interactions_flag_mixed_layouts_and_report_honest_coverage(client):
    body = interactions(client, f'site_id={SITE}&path=/LP/Verao/').get_json()
    assert body['page']['path'] == '/lp/verao' and body['device'] == 'all' and body['mixed_layouts'] is True
    assert body['clicks'] == 60 and body['unidentified_clicks'] == 20 and body['reliable'] is True
    assert body['marked_elements'] and body['visibility_tracked'] and body['grid']['cells'][2][4] == 40
    assert body['elements'][0]['click_rate_of_seen'] == 60.0 and len(body['notes']) == 4
    assert body['document']['cells'][7][3] == 30 and body['document']['coverage'] == 50.0 and body['document']['median_height'] == 5400


def test_a_single_device_is_not_a_mixed_layout(client):
    body = interactions(client, f'site_id={SITE}&path=/lp&device=mobile', device_rows=[{'device': 'mobile', 'clicks': 60}]).get_json()
    assert body['mixed_layouts'] is False and body['device'] == 'mobile'


def test_interactions_validate_device_and_path(client):
    assert interactions(client, f'site_id={SITE}&path=/lp&device=tv').status_code == 400
    assert interactions(client, f'site_id={SITE}&path=lp').status_code == 400


# ---- conversion map --------------------------------------------------------
from aicentralv2.cadu_connect.reports_page_metrics import build_conversion_map  # noqa: E402

MAP_ROWS = [
    {'origin': 'google', 'kind': 'page', 'next_path': '/contato', 'converted': True, 'sessions': 10, 'lead': 6, 'qualified': 3, 'sale': 1},
    {'origin': 'google', 'kind': 'exit', 'next_path': None, 'converted': False, 'sessions': 20, 'lead': 0, 'qualified': 0, 'sale': 0},
    {'origin': 'direct', 'kind': 'form', 'next_path': None, 'converted': True, 'sessions': 5, 'lead': 2, 'qualified': 0, 'sale': 0},
    {'origin': 'direct', 'kind': 'page', 'next_path': '/blog', 'converted': False, 'sessions': 5, 'lead': 0, 'qualified': 0, 'sale': 0},
]


def column_totals(result):
    node_column = {item['id']: item['column'] for item in result['nodes']}
    by_column = {}
    for link in result['links']:
        column = node_column[link['target']]
        by_column[column] = by_column.get(column, 0) + link['value']
    return by_column


def test_conversion_map_columns_all_sum_to_the_same_total():
    result = build_conversion_map(MAP_ROWS, lambda key: key.title(), True)
    assert result['total'] == 40 and result['reliable'] is True
    assert column_totals(result) == {1: 40, 2: 40, 3: 40}
    labels = {item['id']: item['label'] for item in result['nodes']}
    assert labels['n:exit'] == 'Saiu do site' and labels['r:yes'] == 'Converteu no site' and labels['o:google'] == 'Google'


def test_conversion_map_crm_strip_counts_sessions_and_hides_without_integration():
    stages = {item['key']: item for item in build_conversion_map(MAP_ROWS, str, True)['crm']['stages']}
    assert stages['lead']['sessions'] == 8 and stages['lead']['rate'] == 20.0 and stages['sale']['sessions'] == 1
    assert build_conversion_map(MAP_ROWS, str, False)['crm'] == {'available': False, 'stages': []}


def test_conversion_map_groups_the_long_tail_of_next_pages():
    rows = [{'origin': 'direct', 'kind': 'page', 'next_path': f'/p{i}', 'converted': False, 'sessions': 10 - i, 'lead': 0, 'qualified': 0, 'sale': 0}
            for i in range(9)]
    result = build_conversion_map(rows, str, False)
    next_nodes = [item for item in result['nodes'] if item['column'] == 2]
    assert len(next_nodes) == 7 and any(item['id'] == 'n:other' for item in next_nodes)
    assert column_totals(result)[2] == result['total']


def test_conversion_map_of_an_empty_page_is_empty_not_zeroed():
    result = build_conversion_map([], str, True)
    assert result['total'] == 0 and result['links'] == [] and result['reliable'] is False


def map_rows(crm_events=5, with_visitor=3, table=True):
    def rows(sql, params=()):
        if 'FROM cadu_reports_supertag_sites' in sql:
            return [{'id': SITE, 'label': 'Site', 'allowed_host': 'exemplo.com.br'}]
        if 'to_regclass' in sql:
            return [{'ok': table}]
        if 'AS with_visitor' in sql:
            return [{'events': crm_events, 'with_visitor': with_visitor}]
        if 'WITH ps AS' in sql:
            assert ('external_conversions x' in sql) is (with_visitor > 0), 'CRM columns only when visitor-level events exist'
            return [{**row, 'origin': {'google': 'utm:google', 'direct': None}[row['origin']]} for row in MAP_ROWS]
        raise AssertionError(sql)
    return rows


def conversion_map(client, **kwargs):
    with mock.patch.object(pages, '_rows', map_rows(**kwargs)), \
         mock.patch.object(pages, '_selection', return_value={'client_id': 7, 'role': 'admin'}):
        return client.get(f'/connect/api/v2/reports/pages/conversion-map?site_id={SITE}&path=/LP/Verao/')


def test_conversion_map_endpoint_maps_origins_and_reports_crm_coverage(client):
    body = conversion_map(client).get_json()
    assert body['page']['path'] == '/lp/verao' and body['total'] == 40 and body['has_data'] is True
    labels = {item['id']: item['label'] for item in body['nodes']}
    assert labels['o:google'] == 'Google Ads' and labels['o:direct'] == 'Acesso direto'
    assert body['crm']['available'] and body['crm_coverage'] == {'events': 5, 'with_visitor': 3} and len(body['notes']) == 5


def test_conversion_map_without_visitor_level_crm_events_skips_the_crm_columns(client):
    body = conversion_map(client, with_visitor=0, crm_events=4).get_json()
    assert body['crm'] == {'available': False, 'stages': []} and body['crm_coverage']['events'] == 4
    assert conversion_map(client, table=False, with_visitor=0, crm_events=0).status_code == 200


from aicentralv2.cadu_connect.reports_page_metrics import build_document_grid  # noqa: E402


def test_document_grid_has_twenty_bands_and_reports_how_many_clicks_it_covers():
    grid = build_document_grid([{'cx': 0, 'cy': 0, 'clicks': 5}, {'cx': 9, 'cy': 19, 'clicks': 3}, {'cx': 3, 'cy': 40, 'clicks': 9}], 8, 32, 4800.4)
    assert (grid['columns'], grid['rows']) == (10, 20) and grid['cells'][19][9] == 3 and grid['total'] == 8 and grid['peak'] == 5
    assert grid['coverage'] == 25.0 and grid['median_height'] == 4800
    empty = build_document_grid([], 0, 0, None)
    assert empty['coverage'] is None and empty['median_height'] is None and empty['total'] == 0
