"""Radares ativos: horários, validação e o agendador, sem banco."""
from datetime import datetime, timezone

import pytest
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_radar import db as radar_db, watches


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
    """Conexão compartilhada de mentira: registra commit, rollback e, principalmente, se alguém a fechou."""
    def __init__(self, cursor):
        self.cursor_, self.commits, self.rollbacks, self.closed = cursor, 0, 0, False

    def cursor(self):
        return self.cursor_

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_run_due_picks_with_skip_locked_reschedules_and_runs_inline(monkeypatch):
    from aicentralv2.cadu_radar import pipeline
    watch = {'id': 'w1', 'client_id': 5, 'owner_id': 8, 'focus': 'tema', 'brand_ref': 'studio:1', 'project_ref': None,
             'params': {}, 'frequency': 2}
    cursor = FakeCursor([watch])
    conn = FakeConn(cursor)
    monkeypatch.setattr(radar_db, 'get_db', lambda: conn)
    started = []
    monkeypatch.setattr(pipeline, 'start_run', lambda *args, **kwargs: started.append((args, kwargs)) or {'id': 'r1', 'status': 'done'})
    results = watches.run_due(3)
    assert results == [{'watch': 'w1', 'status': 'done', 'run': 'r1'}]
    assert any('FOR UPDATE SKIP LOCKED' in sql for sql, _ in cursor.queries)
    assert any(sql.startswith('UPDATE cadu_radar_watches SET next_run_at') for sql, _ in cursor.queries)
    (args, kwargs), = started
    assert args == (5, 8) and kwargs['background'] is False and kwargs['trigger'] == 'agendado' and kwargs['watch_id'] == 'w1'
    assert not conn.closed and conn.commits >= 2  # o lock do SKIP LOCKED é liberado no commit


def test_run_due_pauses_the_radar_when_credits_run_out(monkeypatch):
    from aicentralv2.cadu_radar import pipeline
    from aicentralv2.cadu_tool_billing import InsufficientToolCredits
    watch = {'id': 'w2', 'client_id': 5, 'owner_id': 8, 'focus': 'tema', 'brand_ref': None, 'project_ref': None, 'params': {}, 'frequency': 1}
    cursor = FakeCursor([watch])
    conn = FakeConn(cursor)
    monkeypatch.setattr(radar_db, 'get_db', lambda: conn)

    def broke(*args, **kwargs):
        raise InsufficientToolCredits('sem saldo')

    monkeypatch.setattr(pipeline, 'start_run', broke)
    assert watches.run_due(3) == [{'watch': 'w2', 'status': 'sem_credito'}]
    assert any("status = 'sem_credito'" in sql for sql, _ in cursor.queries)


def test_transaction_commits_and_never_closes_the_shared_connection(monkeypatch):
    conn = FakeConn(FakeCursor([]))
    monkeypatch.setattr(radar_db, 'get_db', lambda: conn)
    with radar_db.transaction() as cur:
        cur.execute('SELECT 1')
    assert conn.commits == 1 and not conn.closed
    with pytest.raises(RuntimeError), radar_db.transaction():
        raise RuntimeError('falhou no meio')
    assert conn.rollbacks == 1 and not conn.closed


def test_radar_code_never_uses_the_shared_connection_as_a_context_manager():
    """`with get_db() as conn` fecha a conexão da requisição (psycopg 3) e o resto da busca falha."""
    from pathlib import Path
    root = Path(radar_db.__file__).parent
    offenders = [path.name for path in root.glob('*.py') if path.name != 'db.py' and 'get_db() as' in path.read_text()]
    assert offenders == []


def test_create_watch_adopts_the_search_that_was_started_with_it(monkeypatch):
    cursor = FakeCursor([])
    conn = FakeConn(cursor)
    monkeypatch.setattr(radar_db, 'get_db', lambda: conn)
    monkeypatch.setattr(watches.repository, 'rows', lambda sql, params=(): [{'total': 0}])
    monkeypatch.setattr(watches, 'get_watch', lambda client_id, watch_id: {'id': watch_id})
    watch = watches.create_watch(5, 8, focus='CTV para varejo', adopt_run_id='r1')
    adopt = [params for sql, params in cursor.queries if sql.startswith('UPDATE cadu_radar_runs SET watch_id')]
    assert adopt == [(watch['id'], 'r1', 5)]
