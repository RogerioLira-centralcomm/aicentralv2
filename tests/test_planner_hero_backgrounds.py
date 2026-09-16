from unittest import mock

import pytest
from flask import Flask

from aicentralv2.cadu_family import register
from aicentralv2.product_domains import product_url
from tests.test_product_portals import ROOT, _app


ASSETS = {
    'inicio': 'planner-entry', 'audiencias': 'audiences',
    'formatos': 'formats', 'interativos': 'interactives', 'links': 'link-tester',
}


@pytest.mark.parametrize('authenticated', [False, True])
@pytest.mark.parametrize('module,asset', ASSETS.items())
def test_planner_entrances_share_backgrounds_without_exposing_guest_data(module, asset, authenticated):
    app = Flask(__name__, template_folder=str(ROOT / 'aicentralv2/templates'),
                static_folder=str(ROOT / 'aicentralv2/static'))
    app.config.update(SECRET_KEY='test', TESTING=True, CADU_FAMILY_ENABLED=True)
    app.context_processor(lambda: {'product_url': product_url})
    register(app)
    client = app.test_client()
    if authenticated:
        with client.session_transaction() as session:
            session['user_id'] = 7
    user = {'id': 7, 'organization_id': 12, 'name': 'Pessoa', 'role_id': 1}
    selected = {'client_id': 12, 'project_ref': None, 'brand_ref': None}
    with mock.patch('aicentralv2.cadu_family.context.identity', return_value=user), \
         mock.patch('aicentralv2.cadu_family.context.resolve', return_value=selected), \
         mock.patch('aicentralv2.cadu_family.context.authorized_clients', return_value=[]), \
         mock.patch('aicentralv2.cadu_family.context.inventory', return_value=[]), \
         mock.patch('aicentralv2.cadu_family.routes.product_pages.load_records', return_value=[]) as records:
        response = client.get('/familia/planner/' + module)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'images/planner/{asset}-hero-v2.png' in html
    assert 'css/cadu-planner-hero.css' in html
    assert (ROOT / f'aicentralv2/static/images/planner/{asset}-hero-v2.png').is_file()
    if not authenticated:
        records.assert_not_called()
        assert 'data-link-form' not in html


@pytest.mark.parametrize('authenticated', [False, True])
def test_public_planner_entry_keeps_appropriate_account_action(authenticated):
    app = _app()
    app.config['CADU_SESSION_COOKIE_DOMAIN'] = None
    client = app.test_client()
    if authenticated:
        with client.session_transaction() as session:
            session['user_id'] = 7
    response = client.get('/entrada/planner')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'planner-entry-hero-v2.png' in html
    assert 'Abrir Planner' in html if authenticated else 'Entrar em Planner' in html
    assert 'workspace-team.svg' not in html
