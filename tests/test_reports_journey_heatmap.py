import uuid
from unittest import mock

import pytest
from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_journey as journey
from aicentralv2.cadu_connect import reports_page_captures as captures
from aicentralv2.cadu_tool_billing import InsufficientToolCredits

SITE = str(uuid.uuid4())
URL = '/connect/api/v2/reports/journey/heatmap-pages'


def row(path, views, clicks, sessions=10, **extra):
    return {'site_id': uuid.UUID(SITE), 'host': 'exemplo.com.br', 'path': path, 'views': views, 'clicks': clicks,
            'sessions': sessions, 'scroll_25': 8, 'scroll_50': 5, 'scroll_75': 2, 'scroll_100': 0, **extra}


def test_pages_without_views_or_clicks_are_dropped_and_the_rest_ordered_by_clicks():
    pages = journey.heatmap_pages([row('/a', 10, 2), row('/b', 0, 5), row('/c', 7, 0), row('/d', 3, 9), row('/e', 50, 2)])
    assert [page['path'] for page in pages] == ['/d', '/e', '/a']
    assert pages[0]['site_id'] == SITE and pages[0]['scroll_25'] == 80.0 and pages[0]['scroll_100'] == 0.0


def test_scroll_reach_is_none_without_sessions():
    assert journey.heatmap_pages([row('/a', 1, 1, sessions=0)])[0]['scroll_50'] is None


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.secret_key = 'test'
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    journey.register(bp)
    flask_app.register_blueprint(bp)
    return flask_app


def get(app, query='', rows=(), cost=17):
    seen = []

    def fake_rows(sql, params=()):
        seen.append((sql, params))
        return list(rows)
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    with mock.patch.object(journey, '_rows', fake_rows), \
         mock.patch.object(journey, '_selection', return_value={'client_id': 174, 'role': 'admin', 'user_id': 1}), \
         mock.patch.object(captures, 'capture_cost_tokens', return_value=cost):
        response = client.get(URL + query)
    return response, seen


def test_route_filters_by_device_site_and_period_and_returns_the_capture_cost(app):
    response, seen = get(app, f'?device=mobile&site_id={SITE}&start_date=2026-09-01&end_date=2026-09-30',
                         rows=[row('/a', 10, 2), row('/b', 4, 0)])
    body = response.get_json()
    assert response.status_code == 200 and body['device'] == 'mobile' and body['cost_tokens'] == 17
    assert [page['path'] for page in body['pages']] == ['/a'] and body['window']['days'] == 30
    sql, params = seen[0]
    assert 'e.viewport_width<1024' in sql and 'e.site_id=%(site)s::uuid' in sql and '{device}' not in sql and '{site}' not in sql
    assert params['client'] == 174 and params['site'] == SITE
    assert "e.event_kind IN ('click','whatsapp_click')" in sql and 'WHERE views>0 AND clicks>0' in sql


def test_route_defaults_to_desktop_for_every_site_and_tolerates_a_missing_price(app):
    response, seen = get(app, cost=None)
    assert response.status_code == 200 and response.get_json()['cost_tokens'] is None
    assert 'e.viewport_width>=1024' in seen[0][0] and '%(site)s' not in seen[0][0]


@pytest.mark.parametrize('query', ['?device=tablet', '?device=tv', '?site_id=nope', '?start_date=2026-09-01'])
def test_route_rejects_invalid_input(app, query):
    assert get(app, query)[0].status_code == 400


def test_route_requires_login(app):
    assert app.test_client().get(URL).status_code == 401


def test_capture_cost_is_none_when_the_client_has_no_token_price(app):
    with app.app_context():
        with mock.patch('aicentralv2.cadu_credit_connector.CaduCreditConnector.estimate_firecrawl_tokens', return_value=17):
            assert captures.capture_cost_tokens(174) == 17
        with mock.patch('aicentralv2.cadu_credit_connector.CaduCreditConnector.estimate_firecrawl_tokens',
                        side_effect=ValueError('Preço comercial de Tokens Cadu indisponível para este cliente.')):
            assert captures.capture_cost_tokens(174) is None


def test_ensure_balance_answers_409_only_when_credits_are_short(app):
    from werkzeug.exceptions import Conflict
    actor = mock.Mock(client_id=174, user_id=1)
    with app.app_context():
        with mock.patch('aicentralv2.cadu_credit_connector.CaduCreditConnector.authorize_firecrawl',
                        side_effect=InsufficientToolCredits('Saldo insuficiente.')), pytest.raises(Conflict):
            captures.ensure_balance(actor)
        with mock.patch('aicentralv2.cadu_credit_connector.CaduCreditConnector.authorize_firecrawl', side_effect=ValueError('sem preço')):
            captures.ensure_balance(actor)                    # pricing problems are left to the capture itself


def test_the_click_layer_of_celular_uses_the_same_device_split_as_the_page_list():
    from aicentralv2.cadu_connect import reports_pages
    from aicentralv2.cadu_connect.reports_page_metrics import DEVICES
    assert 'handheld' in DEVICES
    assert reports_pages._DEVICE_SQL['handheld'] == journey.HEATMAP_DEVICES['mobile']
    assert reports_pages._DEVICE_SQL['desktop'] == journey.HEATMAP_DEVICES['desktop']


DETAIL = '/connect/api/v2/reports/journey/heatmap-detail'


def test_heat_grid_is_sparse_and_ignores_cells_outside_the_page():
    grid = journey.heat_grid([{'cx': 3, 'cy': 5, 'clicks': 4}, {'cx': 3, 'cy': 5, 'clicks': 1}, {'cx': journey.HEAT_COLUMNS, 'cy': 1, 'clicks': 9},
                              {'cx': journey.HEAT_COLUMNS - 1, 'cy': journey.HEAT_ROWS - 1, 'clicks': 2}])
    assert grid['points'] == [[3, 5, 5], [journey.HEAT_COLUMNS - 1, journey.HEAT_ROWS - 1, 2]] and grid['peak'] == 5 and grid['total'] == 7
    zones = journey.heat_zones(grid)
    assert [zone['clicks'] for zone in zones] == [5, 0, 0, 2] and zones[0]['share'] == 71.4


def test_elements_group_marked_ids_and_names_and_count_unnamed_clicks():
    rows = [{'element_id': 'cta', 'label': None, 'kind': 'button', 'clicks': 3},
            {'element_id': 'cta', 'label': 'Fale conosco', 'kind': 'button', 'clicks': 2},
            {'element_id': None, 'label': 'Instagram', 'kind': 'icon', 'clicks': 4},
            {'element_id': None, 'label': 'Instagram', 'kind': 'link', 'clicks': 1},
            {'element_id': None, 'label': None, 'kind': 'link', 'clicks': 10}]
    elements = journey.heat_elements(rows, 20)
    assert [(item['label'], item['clicks'], item['kind_label']) for item in elements['items']] == [
        ('Fale conosco', 5, 'Botão'), ('Instagram', 4, 'Ícone'), ('Instagram', 1, 'Link')]
    assert elements['items'][0]['share'] == 25.0 and elements['unnamed_clicks'] == 10 and elements['unnamed_share'] == 50.0


def test_devices_keep_a_fixed_order_with_zeros():
    devices = journey.heat_devices([{'device': 'mobile', 'views': 30, 'clicks': 6}, {'device': 'desktop', 'views': 70, 'clicks': 28}])
    assert [(item['device'], item['share'], item['clicks_per_view']) for item in devices] == [
        ('desktop', 70.0, 0.4), ('mobile', 30.0, 0.2), ('tablet', 0.0, None)]



def test_detail_route_reads_one_page_on_one_device_in_the_period(app):
    seen = []

    def fake_rows(sql, params=()):
        seen.append((sql, params))
        if 'AS cx' in sql:
            return [{'cx': 2, 'cy': 3, 'clicks': 4}]
        if 'el_label' in sql:
            return [{'element_id': None, 'label': 'Comprar', 'kind': 'button', 'clicks': 4}]
        if 'AS device' in sql:
            return [{'device': 'mobile', 'views': 9, 'clicks': 4}]
        return [{'views': 9, 'sessions': 5, 'clicks': 4, 'scroll_25': 4, 'scroll_50': 2, 'scroll_75': 1, 'scroll_100': 0}]
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    with mock.patch.object(journey, '_rows', fake_rows), \
         mock.patch.object(journey, '_selection', return_value={'client_id': 174, 'role': 'admin', 'user_id': 1}):
        response = client.get(f'{DETAIL}?device=mobile&site_id={SITE}&path=/lp&start_date=2026-09-01&end_date=2026-09-30')
    body = response.get_json()
    assert response.status_code == 200 and body['summary']['clicks'] == 4 and body['summary']['scroll_25'] == 80.0
    assert body['heat']['points'] == [[2, 3, 4]] and body['positioned_share'] == 100.0
    assert body['elements']['items'][0]['label'] == 'Comprar'
    for sql, params in seen:
        assert '%(path)s' in sql and 'e.site_id=%(site)s::uuid' in sql and '{device}' not in sql
        assert params['path'] == '/lp' and params['site'] == SITE and params['client'] == 174
    assert sum('AND (e.viewport_width<1024)' in sql for sql, _ in seen) == 3      # every query but the device split


@pytest.mark.parametrize('query', [f'?site_id={SITE}', '?path=/lp', f'?site_id={SITE}&path=lp', f'?site_id={SITE}&path=/a b',
                                   f'?site_id={SITE}&path=/lp&device=tablet'])
def test_detail_route_rejects_invalid_input(app, query):
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
    with mock.patch.object(journey, '_rows', lambda *args: []), \
         mock.patch.object(journey, '_selection', return_value={'client_id': 174, 'role': 'admin', 'user_id': 1}):
        assert client.get(DETAIL + query).status_code == 400
