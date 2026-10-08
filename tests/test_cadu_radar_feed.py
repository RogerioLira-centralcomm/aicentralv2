from datetime import datetime, timedelta, timezone

from aicentralv2.cadu_radar import feed


def test_score_prefers_angles_then_strong_sources_then_recent():
    now = datetime.now(timezone.utc)
    base = {'published_at': now, 'detected_at': now, 'saved': False, 'tier': 'C', 'angle_count': 0}
    with_angle = {**base, 'angle_count': 1}
    old_strong = {**base, 'tier': 'A', 'published_at': now - timedelta(days=20)}
    old_weak = {**base, 'published_at': now - timedelta(days=20)}
    assert feed._score(with_angle, now) > feed._score(old_strong, now) > feed._score(old_weak, now)


def test_plan_from_signal_uses_the_news_as_briefing(monkeypatch):
    from contextlib import contextmanager
    from aicentralv2.cadu_planner import plans
    from aicentralv2.cadu_radar import repository as radar

    signal = {'id': 's1', 'headline': 'CTV ganha atenção', 'description': 'Estudo mostra atenção ativa.', 'source': 'Exame',
              'url': 'https://exame.com/x', 'published_at': datetime(2026, 9, 27, tzinfo=timezone.utc), 'focus': 'CTV para varejo',
              'brand_ref': 'b1', 'project_ref': None, 'params': {'places': 'Brasil'}}

    def rows(sql, params=()):
        if 'FROM cadu_radar_signals' in sql:
            return [signal]
        if 'cadu_radar_opportunities' in sql:
            return [{'title': 'CTV como praça de varejo'}]
        return [{'column_name': 'signal_id'}]

    created, updates = [], []

    class Cursor:
        def execute(self, sql, params=()):
            updates.append((sql, params))

    @contextmanager
    def fake_transaction():
        yield Cursor()

    monkeypatch.setattr(radar.repository, 'rows', rows)
    monkeypatch.setattr('aicentralv2.cadu_radar.db.transaction', fake_transaction)
    monkeypatch.setattr(plans, 'create_plan', lambda client, actor, payload, ctx: created.append(payload) or {'id': 'p1'})
    monkeypatch.setattr(plans, 'get_plan', lambda client, actor, plan_id: {'id': plan_id})
    assert radar.create_plan_from_signal(5, 8, 's1', {}) == {'id': 'p1'}
    (payload,) = created
    assert payload['title'] == 'CTV ganha atenção' and payload['briefing']['geography'] == 'Brasil'
    notes = payload['briefing']['notes']
    assert 'Fonte: Exame (27/09/2026) · https://exame.com/x' in notes and 'Radar: CTV para varejo' in notes
    assert 'CTV como praça de varejo' in notes
    assert updates and "source = 'radar'" in updates[0][0] and updates[0][1] == ('s1', 'p1')
