"""Radares ativos: horários, validação e o agendador, sem banco."""
from datetime import datetime, timezone

import pytest
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_radar import watches


def utc(day, hour):
    return datetime(2026, 10, day, hour, 0, tzinfo=timezone.utc)


def test_next_run_follows_brasilia_hours():
    # 12h em Brasília (15h UTC): 1x → 8h de amanhã; 3x → 13h de hoje; 2x → 17h de hoje.
    assert watches.next_run_at(1, utc(6, 15)) == utc(7, 11)
    assert watches.next_run_at(3, utc(6, 15)) == utc(6, 16)
    assert watches.next_run_at(2, utc(6, 15)) == utc(6, 20)
    # 20h em Brasília (23h UTC): qualquer frequência cai nas 8h de amanhã.
    assert watches.next_run_at(3, utc(6, 23)) == utc(7, 11)


def test_next_run_is_always_in_the_future_even_exactly_on_the_hour():
    assert watches.next_run_at(3, utc(6, 11)) == utc(6, 16)  # 8h em ponto → próxima é 13h, não a mesma


def test_frequency_outside_the_menu_falls_back_to_once_a_day():
    assert watches.next_run_at(9, utc(6, 15)) == watches.next_run_at(1, utc(6, 15))


def test_create_watch_needs_a_theme_or_a_brand():
    with pytest.raises(BadRequest):
        watches.create_watch(1, 2, focus=' ab ', params={})


def test_create_watch_rejects_bad_frequency_before_touching_the_database():
    with pytest.raises(BadRequest):
        watches.create_watch(1, 2, focus='tema válido', frequency='muitas')


class FakeCursor:
    def __init__(self, due):
        self.due, self.queries = list(due), []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.queries.append((' '.join(sql.split()), params))

    def fetchone(self):
        return self.due.pop(0) if self.due else None


class FakeConn:
    def __init__(self, cursor):
        self.cursor_ = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_


def test_run_due_picks_with_skip_locked_reschedules_and_runs_inline(monkeypatch):
    from aicentralv2.cadu_radar import pipeline
    watch = {'id': 'w1', 'client_id': 5, 'owner_id': 8, 'focus': 'tema', 'brand_ref': 'studio:1', 'project_ref': None,
             'params': {}, 'frequency': 2}
    cursor = FakeCursor([watch])
    monkeypatch.setattr(watches.repository, 'get_db', lambda: FakeConn(cursor))
    started = []
    monkeypatch.setattr(pipeline, 'start_run', lambda *args, **kwargs: started.append((args, kwargs)) or {'id': 'r1', 'status': 'done'})
    results = watches.run_due(3)
    assert results == [{'watch': 'w1', 'status': 'done', 'run': 'r1'}]
    assert any('FOR UPDATE SKIP LOCKED' in sql for sql, _ in cursor.queries)
    assert any(sql.startswith('UPDATE cadu_radar_watches SET next_run_at') for sql, _ in cursor.queries)
    (args, kwargs), = started
    assert args == (5, 8) and kwargs['background'] is False and kwargs['trigger'] == 'agendado' and kwargs['watch_id'] == 'w1'


def test_run_due_pauses_the_radar_when_credits_run_out(monkeypatch):
    from aicentralv2.cadu_radar import pipeline
    from aicentralv2.cadu_tool_billing import InsufficientToolCredits
    watch = {'id': 'w2', 'client_id': 5, 'owner_id': 8, 'focus': 'tema', 'brand_ref': None, 'project_ref': None, 'params': {}, 'frequency': 1}
    cursor = FakeCursor([watch])
    monkeypatch.setattr(watches.repository, 'get_db', lambda: FakeConn(cursor))

    def broke(*args, **kwargs):
        raise InsufficientToolCredits('sem saldo')

    monkeypatch.setattr(pipeline, 'start_run', broke)
    assert watches.run_due(3) == [{'watch': 'w2', 'status': 'sem_credito'}]
    assert any("status = 'sem_credito'" in sql for sql, _ in cursor.queries)
