from datetime import datetime, timezone

from aicentralv2.cadu_family import repository
from aicentralv2.cadu_planner import portals


def test_attach_prints_uses_only_approved_rows_and_static_urls(monkeypatch):
    seen = {}

    def fake_rows(sql, params=()):
        seen['sql'] = sql
        return [{'portal_id': 1, 'kind': 'home', 'file_path': 'images/portais/prints/1/20261006-home.webp',
                 'source_url': 'https://g1.globo.com', 'captured_at': datetime(2026, 10, 6, tzinfo=timezone.utc)}]

    monkeypatch.setattr(repository, 'rows', fake_rows)
    rows = portals.attach_prints([{'id': 1}, {'id': 2}])
    assert "status = 'aprovado'" in seen['sql']
    assert rows[0]['print_url'] == '/static/images/portais/prints/1/20261006-home.webp'
    assert rows[0]['prints'][0]['source_url'] == 'https://g1.globo.com'
    assert rows[1]['prints'] == [] and rows[1]['print_url'] == ''


def test_attach_prints_survives_missing_table(monkeypatch):
    def boom(sql, params=()):
        raise RuntimeError('relation "cadu_planner_portal_prints" does not exist')

    monkeypatch.setattr(repository, 'rows', boom)
    rows = portals.attach_prints([{'id': 7}])
    assert rows[0]['prints'] == [] and rows[0]['print_url'] == ''
