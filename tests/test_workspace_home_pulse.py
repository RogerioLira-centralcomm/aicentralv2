from datetime import datetime, timezone

import pytest
from flask import Flask

from aicentralv2.cadu_workspace import home_pulse

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


@pytest.fixture
def app():
    flask_app = Flask(__name__)
    flask_app.config['PLANNER_URL'] = ''
    with flask_app.app_context():
        yield flask_app


def test_cards_are_independent_and_empty_ones_are_omitted(app, monkeypatch):
    monkeypatch.setattr(home_pulse, '_plans', lambda c, u: None)
    monkeypatch.setattr(home_pulse, '_radar', lambda c, u: (_ for _ in ()).throw(RuntimeError('db down')))
    monkeypatch.setattr(home_pulse, '_studio', lambda c, u: {'id': 'studio'})
    monkeypatch.setattr(home_pulse, '_reports', lambda c, u: None)
    assert home_pulse.build_home_pulse(1, 2) == [{'id': 'studio'}]


def test_studio_card_counts_working_assets_and_keeps_three_thumbs(app, monkeypatch):
    rows = [{'title': str(i), 'asset_url': f'/a{i}.png', 'kind': 'image', 'updated_at': NOW} for i in range(5)]
    monkeypatch.setattr(home_pulse, '_table_exists', lambda name: True)
    monkeypatch.setattr(home_pulse.repository, 'rows', lambda sql, args=(): rows)
    card = home_pulse._studio(1, 2)
    assert card['count'] == 5 and card['noun'] == 'criativos'
    assert card['detail']['thumbs'] == ['/a0.png', '/a1.png', '/a2.png'] and card['detail']['more'] == 2


def test_studio_and_reports_are_skipped_when_table_is_missing(app, monkeypatch):
    monkeypatch.setattr(home_pulse, '_table_exists', lambda name: False)
    assert home_pulse._studio(1, 2) is None and home_pulse._reports(1, 2) is None


def test_plans_card_only_counts_drafts_and_links_latest(app, monkeypatch):
    from aicentralv2.cadu_planner import plans
    monkeypatch.setattr(plans, 'list_plans', lambda c, u: [
        {'id': 'p2', 'title': 'B', 'status': 'draft', 'item_count': 3, 'updated_at': NOW},
        {'id': 'p1', 'title': 'A', 'status': 'ready', 'item_count': 9, 'updated_at': NOW}])
    monkeypatch.setattr(home_pulse, 'product_url', lambda product, path='/': f'{product}:{path}')
    card = home_pulse._plans(1, 2)
    assert card['count'] == 1 and card['noun'] == 'plano' and card['href'] == 'planner:/planos/p2'
