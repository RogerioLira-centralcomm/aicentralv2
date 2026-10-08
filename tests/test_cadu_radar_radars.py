from datetime import datetime, timedelta, timezone

import pytest

from aicentralv2.cadu_radar import radars

NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def run(run_id, hours_ago, *, status='done', watch_id=None, urls=(), titles=(), broken=0, focus='CTV para varejo'):
    return {'id': run_id, 'status': status, 'created_at': NOW - timedelta(hours=hours_ago), 'finished_at': None, 'error': None,
            'trigger': 'agendado' if watch_id else 'manual', 'tokens': 100, 'in_plan': 0, 'broken_sources': broken,
            'watch_id': watch_id, 'focus': focus, 'brand_ref': 'b1', 'project_ref': None, 'params': {'places': 'Brasil'},
            'signal_rows': [{'url': url, 'source': url.split('/')[2], 'ok': True} for url in urls],
            'angle_rows': [{'title': title} for title in titles]}


WATCH = {'id': 'w1', 'name': 'CTV para varejo', 'status': 'ativo', 'frequency': 1, 'last_run_at': None, 'next_run_at': None}


def test_schedule_label():
    assert radars.schedule_label(1) == 'Diário · 08h'
    assert radars.schedule_label(3) == '3x ao dia · 08h e 13h e 18h'


def test_never_opened_radar_is_new_and_has_no_changes():
    group = [run('r2', 1, watch_id='w1', urls=['https://a.com/1', 'https://b.com/2']), run('r1', 30, watch_id='w1', urls=['https://a.com/1'])]
    item = radars._build('w1', 'watch', group, WATCH, None)
    assert item['reading'] == 'new' and item['changes'] == {'signals': 0, 'angles': 0}
    assert item['phase'] == 'programado' and item['executions'] == 2 and item['schedule']['label'] == 'Diário · 08h'


def test_execution_after_last_visit_counts_only_new_links_and_titles():
    group = [run('r2', 1, watch_id='w1', urls=['https://a.com/1/', 'https://c.com/3'], titles=['Do varejo à sala', 'Ângulo novo']),
             run('r1', 30, watch_id='w1', urls=['https://A.com/1'], titles=['do varejo à sala'])]
    item = radars._build('w1', 'watch', group, WATCH, {'last_seen_at': NOW - timedelta(hours=10), 'favorite': True})
    assert item['reading'] == 'updated' and item['changes'] == {'signals': 1, 'angles': 1} and item['favorite'] is True


def test_execution_without_novelty_is_reported_as_no_change():
    group = [run('r2', 1, watch_id='w1', urls=['https://a.com/1'], titles=['X']), run('r1', 30, watch_id='w1', urls=['https://a.com/1'], titles=['X'])]
    item = radars._build('w1', 'watch', group, WATCH, {'last_seen_at': NOW - timedelta(hours=10)})
    assert item['reading'] == 'nochange'


def test_seen_after_latest_execution_has_nothing_to_highlight():
    group = [run('r2', 5, watch_id='w1', urls=['https://c.com/3']), run('r1', 30, watch_id='w1')]
    item = radars._build('w1', 'watch', group, WATCH, {'last_seen_at': NOW - timedelta(hours=1)})
    assert item['reading'] == 'seen' and item['changes'] == {'signals': 0, 'angles': 0}


def test_favorite_without_visit_is_still_new():
    item = radars._build('r1', 'single', [run('r1', 2)], None, {'last_seen_at': None, 'favorite': True})
    assert item['reading'] == 'new' and item['phase'] == 'concluido' and item['schedule'] is None


@pytest.mark.parametrize('status, broken, reading, phase', [
    ('running', 0, 'running', 'em_execucao'), ('failed', 0, 'attention', 'falha'), ('done', 2, 'attention', 'programado')])
def test_running_failed_and_broken_sources(status, broken, reading, phase):
    item = radars._build('w1', 'watch', [run('r1', 1, status=status, watch_id='w1', broken=broken)], WATCH, {'last_seen_at': NOW})
    assert item['reading'] == reading and item['phase'] == phase


def test_paused_and_out_of_credit_watches():
    assert radars._build('w1', 'watch', [run('r1', 1, watch_id='w1')], {**WATCH, 'status': 'pausado'}, None)['phase'] == 'pausado'
    assert radars._build('w1', 'watch', [run('r1', 1, watch_id='w1')], {**WATCH, 'status': 'sem_credito'}, None)['phase'] == 'falha'


def test_list_groups_executions_of_a_watch_and_keeps_single_searches_apart(monkeypatch):
    runs = [run('r3', 1, watch_id='w1'), run('r2', 5, focus='Energia'), run('r1', 30, watch_id='w1'), run('r0', 40, watch_id='apagado')]
    monkeypatch.setattr(radars, '_load', lambda client_id: runs)
    monkeypatch.setattr(radars, '_watches_available', lambda: True)
    monkeypatch.setattr(radars.watches, 'list_watches', lambda client_id: [WATCH])
    monkeypatch.setattr(radars, '_user_state', lambda client_id, user_id: {})
    items = radars.list_radars(5, 8)
    assert [(item['id'], item['kind'], item['executions']) for item in items] == [('w1', 'watch', 2), ('r2', 'single', 1), ('r0', 'single', 1)]


def test_get_radar_history_and_what_changed_since_last_visit(monkeypatch):
    runs = [run('r3', 1, watch_id='w1', urls=['https://a.com/1', 'https://c.com/3'], titles=['A', 'C']),
            run('r2', 20, watch_id='w1', urls=['https://a.com/1', 'https://b.com/2'], titles=['A']),
            run('r1', 40, watch_id='w1', urls=['https://a.com/1'], titles=['A'])]
    monkeypatch.setattr(radars, '_load', lambda client_id: runs)
    monkeypatch.setattr(radars, '_watches_available', lambda: True)
    monkeypatch.setattr(radars.watches, 'list_watches', lambda client_id: [WATCH])
    monkeypatch.setattr(radars, '_user_state', lambda client_id, user_id: {'w1': {'last_seen_at': NOW - timedelta(hours=10)}})
    full = {'id': 'r3', 'status': 'done',
            'signals': [{'id': 's1', 'url': 'https://a.com/1'}, {'id': 's3', 'url': 'https://c.com/3/'}],
            'opportunities': [{'id': 'o1', 'title': 'A'}, {'id': 'o3', 'title': 'C'}]}
    monkeypatch.setattr(radars.pipeline, 'get_run', lambda client_id, run_id: full)
    data = radars.get_radar(5, 8, 'w1')
    assert [(item['id'], item['new_signals'], item['new_angles']) for item in data['history']] == [('r3', 1, 1), ('r2', 1, 0), ('r1', None, None)]
    assert data['changed'] == {'signals': ['s3'], 'angles': ['o3']}
    assert data['radar']['reading'] == 'updated'


def test_get_radar_unknown_id(monkeypatch):
    from werkzeug.exceptions import NotFound
    monkeypatch.setattr(radars, '_groups', lambda client_id: ({}, {}))
    with pytest.raises(NotFound):
        radars.get_radar(5, 8, 'nada')
