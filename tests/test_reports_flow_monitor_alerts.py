"""Alerta por e-mail quando páginas do fluxo caem: janela 7h–23h (Brasília), um aviso por ciclo, aviso de volta."""
from datetime import datetime, timedelta, timezone

import pytest

from aicentralv2.cadu_connect import reports_flow_monitor as monitor
from aicentralv2.cadu_connect.reports_flow_metrics import ai_agent_for, origin_platform

FLOW = {'id': 'f1', 'client_id': 7, 'name': 'Serviços', 'allowed_host': 'www.exemplo.com'}
DOWN = [{'path': '/', 'status': 'offline', 'detail': 'HTTP 503'}, {'path': '/lp', 'status': 'online'}]
UP = [{'path': '/', 'status': 'online'}]
DAY = datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)   # 12:00 em Brasília
NIGHT = datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)  # 00:00 em Brasília


class FakeDb:
    def __init__(self):
        self.updates, self.commits = [], 0
    def cursor(self):
        db = self
        class Cursor:
            def __enter__(self_): return self_
            def __exit__(self_, *a): return False
            def execute(self_, sql, params): db.updates.append(params)
        return Cursor()
    def commit(self): self.commits += 1
    def rollback(self): pass


@pytest.fixture
def env(monkeypatch):
    box = type('Box', (), {})()
    box.state = {'monitor_down_since': None, 'monitor_last_alert_at': None}
    box.sent, box.db = [], FakeDb()
    def rows(sql, params=()):
        if 'FROM cadu_reports_flow_registry f' in sql and 'tbl_contato_cliente' in sql:
            return [{'email': 'Dono@Exemplo.com'}]
        return [box.state]
    monkeypatch.setattr(monitor, '_rows', rows)
    monkeypatch.setattr(monitor, 'get_db', lambda: box.db)
    monkeypatch.setattr(monitor, '_send_monitor_email',
                        lambda flow, recipients, status, pages, since, recovered=False: box.sent.append((tuple(recipients), recovered)) or True)
    return box


def test_window_is_7h_to_23h_in_sao_paulo():
    for hour_utc, expected in [(10, True), (9, False), (1, True), (2, False)]:
        assert monitor.in_alert_window(datetime(2026, 10, 7, hour_utc, 30 if hour_utc in (1, 9) else 0, tzinfo=timezone.utc)) is expected


def test_recipients_are_the_flow_creator_and_apolo(monkeypatch):
    monkeypatch.setattr(monitor, '_rows', lambda *a, **k: [{'email': 'Dono@Exemplo.com'}])
    assert monitor._alert_recipients('f1', 7) == ['apolo@centralcomm.media', 'dono@exemplo.com']


def test_first_failure_sends_and_records_the_time(env):
    monitor.notify_transition(FLOW, 'offline', DOWN, now=DAY)
    assert len(env.sent) == 1 and env.db.updates[-1][0] == DAY and env.db.updates[-1][1] == DAY


def test_repeats_every_cycle_but_not_inside_one(env):
    env.state = {'monitor_down_since': DAY, 'monitor_last_alert_at': DAY}
    monitor.notify_transition(FLOW, 'offline', DOWN, now=DAY + timedelta(minutes=2))
    assert env.sent == []
    monitor.notify_transition(FLOW, 'offline', DOWN, now=DAY + timedelta(minutes=5))
    assert len(env.sent) == 1


def test_night_keeps_the_outage_but_sends_nothing(env):
    monitor.notify_transition(FLOW, 'offline', DOWN, now=NIGHT)
    assert env.sent == [] and env.db.updates[-1][0] == NIGHT and env.db.updates[-1][1] is None


def test_recovery_sends_one_mail_and_clears_state(env):
    env.state = {'monitor_down_since': DAY, 'monitor_last_alert_at': DAY}
    monitor.notify_transition(FLOW, 'online', UP, now=DAY + timedelta(minutes=5))
    assert env.sent == [(('apolo@centralcomm.media', 'dono@exemplo.com'), True)] and env.db.updates[-1] == ('f1',)


def test_healthy_flow_does_nothing(env):
    monitor.notify_transition(FLOW, 'online', UP, now=DAY)
    assert env.sent == [] and env.db.updates == []


def test_send_failure_does_not_mark_the_alert_as_sent(env, monkeypatch):
    monkeypatch.setattr(monitor, '_send_monitor_email', lambda *a, **k: False)
    monitor.notify_transition(FLOW, 'offline', DOWN, now=DAY)
    assert env.db.updates[-1][1] is None   # tries again next cycle


def test_ai_agents_are_recognised_by_referrer_and_utm():
    assert ai_agent_for('chatgpt.com') == 'chatgpt' and ai_agent_for('www.claude.ai') == 'claude'
    assert ai_agent_for('gemini.google.com') == 'gemini' and ai_agent_for('www.google.com') is None
    assert origin_platform('utm:chatgpt.com|x') == 'chatgpt' and origin_platform('ref:gemini.google.com') == 'gemini'
    assert origin_platform('ref:www.google.com') == 'organic' and origin_platform('ref:claude.ai') == 'claude'


def test_recovery_at_night_is_held_until_the_window_opens(env):
    env.state = {'monitor_down_since': DAY, 'monitor_last_alert_at': DAY}
    monitor.notify_transition(FLOW, 'online', UP, now=NIGHT)
    assert env.sent == [] and env.db.updates == []          # state kept: the all-clear is still owed
    monitor.notify_transition(FLOW, 'online', UP, now=DAY + timedelta(days=1))
    assert len(env.sent) == 1 and env.db.updates[-1] == ('f1',)


def test_failed_recovery_mail_is_retried(env, monkeypatch):
    env.state = {'monitor_down_since': DAY, 'monitor_last_alert_at': DAY}
    monkeypatch.setattr(monitor, '_send_monitor_email', lambda *a, **k: False)
    monitor.notify_transition(FLOW, 'online', UP, now=DAY + timedelta(minutes=5))
    assert env.db.updates == []
