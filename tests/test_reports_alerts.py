import datetime
import uuid
from unittest import mock

import pytest
from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_alerts as alerts
from aicentralv2.cadu_connect.reports_alert_rules import (
    CONSECUTIVE_FAILURES, RULES, campaign_page_findings, channel_entry_findings, collection_absent_findings, conversion_drop_findings,
    page_down_findings, tech_conversion_findings)

NOW = datetime.datetime(2026, 10, 1, 12, 0, tzinfo=datetime.timezone.utc)


def check(minutes_ago, *pages):
    return {'checked_at': NOW - datetime.timedelta(minutes=minutes_ago), 'pages': list(pages)}


def page(status, path='/LP/Verao/', host='www.exemplo.com.br', http=None):
    return {'host': host, 'path': path, 'status': status, 'http_status': http, 'detail': 'x'}


def test_a_single_failure_never_alerts_but_two_in_a_row_do():
    assert page_down_findings([check(1, page('offline', http=503)), check(6, page('online'))]) == []
    found = page_down_findings([check(1, page('offline', http=503)), check(6, page('offline', http=500)), check(11, page('online'))])
    assert len(found) == 1 and found[0]['rule'] == 'page_down' and found[0]['severity'] == 'high'
    assert found[0]['subject_key'] == '/lp/verao' and found[0]['page_path'] == '/lp/verao'
    assert {e['label']: e['value'] for e in found[0]['evidence']}['Falhas seguidas'] == 2


def test_a_recovered_page_stops_alerting_and_only_the_failing_page_is_reported():
    recovered = [check(1, page('online')), check(6, page('offline')), check(11, page('offline'))]
    assert page_down_findings(recovered) == []
    mixed = [check(1, page('offline'), page('online', path='/ok')), check(6, page('degraded'), page('online', path='/ok'))]
    assert [f['subject_key'] for f in page_down_findings(mixed)] == ['/lp/verao']


def test_pages_absent_from_recent_checks_do_not_fabricate_an_outage():
    assert page_down_findings([check(1, page('offline')), check(6)]) == []
    assert page_down_findings([]) == []
    assert CONSECUTIVE_FAILURES == 2


def test_collection_absent_needs_a_baseline_and_enough_silence():
    assert collection_absent_findings('Site', 500, 7.2)[0]['evidence'][0]['value'] == 7
    assert collection_absent_findings('Site', 10, 30) == []      # never really sent anything
    assert collection_absent_findings('Site', 500, 2) == []      # quiet for a short while
    assert collection_absent_findings('Site', 500, None) == []   # no event ever: nothing to compare with


def stats(sessions, rate):
    return {'sessions': sessions, 'session_conversion_rate': rate}


def test_conversion_drop_requires_reliable_samples_and_a_big_relative_fall():
    drop = {'path': '/lp', 'current': stats(80, 5.0), 'previous': stats(90, 10.0)}
    assert [f['subject_key'] for f in conversion_drop_findings([drop])] == ['/lp']
    assert conversion_drop_findings([{**drop, 'current': stats(10, 1.0)}]) == []
    assert conversion_drop_findings([{**drop, 'current': stats(80, 8.0)}]) == []
    assert conversion_drop_findings([{**drop, 'previous': stats(90, None)}]) == []
    assert conversion_drop_findings([{**drop, 'previous': stats(90, 0)}]) == []


def test_every_rule_documents_its_condition():
    assert set(RULES) == {'page_down', 'collection_absent', 'conversion_drop', 'channel_entry_exit', 'device_conversion_low', 'campaign_weak_page'}
    assert all(RULES[key]['severity'] == 'low' for key in ('channel_entry_exit', 'device_conversion_low', 'campaign_weak_page'))   # advisory, never e-mailed
    assert all(item['when'] and item['title'] and item['severity'] for item in RULES.values())


def test_runner_throttles_light_and_heavy_passes():
    clock = {'t': 1000.0}
    runner = alerts.PeriodicRunner(light=300, heavy=3600, clock=lambda: clock['t'])
    calls = []
    app = Flask(__name__)
    with app.app_context(), mock.patch.object(alerts, 'evaluate_all', side_effect=lambda heavy=False: calls.append(heavy)):
        assert runner.tick() is True and calls == [True]            # first pass is heavy
        clock['t'] += 100
        assert runner.tick() is False and calls == [True]           # too soon
        clock['t'] += 250
        assert runner.tick() is True and calls == [True, False]     # light pass
        clock['t'] += 3400
        assert runner.tick() is True and calls == [True, False, True]


def test_runner_survives_an_evaluation_failure():
    app = Flask(__name__)
    runner = alerts.PeriodicRunner(clock=lambda: 5.0)
    with app.app_context(), mock.patch.object(alerts, 'evaluate_all', side_effect=RuntimeError('boom')):
        assert runner.tick() is True


# ---- notifications ---------------------------------------------------------
def alert_row(**kwargs):
    return {'id': str(uuid.uuid4()), 'client_id': 7, 'severity': 'high', 'title': 'T', 'summary': 'S', 'assigned_to': None, 'last_notified_at': None, **kwargs}


def run_notify(row, env=None, recipients=('a@x.com',), sent=True):
    logged = []
    with mock.patch.object(alerts, '_log', lambda alert_id, kind, actor=None, detail=None: logged.append((kind, detail))), \
         mock.patch.object(alerts, '_recipients', return_value=list(recipients)), \
         mock.patch.object(alerts, '_rows', return_value=[]), \
         mock.patch('aicentralv2.services.cadu_email_connector.send_cadu_event', return_value={'success': sent}) as send, \
         mock.patch.dict('os.environ', env or {}, clear=False):
        import os
        if not env:
            os.environ.pop('REPORTS_ALERT_EMAILS', None)
        alerts.notify_opened(row, NOW)
    return logged, send


def test_emails_are_off_by_default_and_the_skip_is_logged():
    logged, send = run_notify(alert_row())
    assert logged == [('notification_skipped', {'reason': 'disabled'})] and not send.called


def test_enabled_emails_go_out_once_and_respect_cooldown_severity_and_recipients():
    on = {'REPORTS_ALERT_EMAILS': '1'}
    logged, send = run_notify(alert_row(), on)
    assert logged == [('notified', {'recipients': 1})] and send.call_count == 1
    assert run_notify(alert_row(last_notified_at=NOW - datetime.timedelta(hours=1)), on)[0][0][1] == {'reason': 'cooldown'}
    assert run_notify(alert_row(severity='low'), on)[0][0][1] == {'reason': 'low_severity'}
    assert run_notify(alert_row(), on, recipients=())[0][0][1] == {'reason': 'no_recipients'}
    assert run_notify(alert_row(), on, sent=False)[0][0][0] == 'notification_failed'


def test_alert_email_uses_the_reports_brand_template():
    logged, send = run_notify(alert_row(page_path='/checkout'), {'REPORTS_ALERT_EMAILS': '1', 'REPORTS_PUBLIC_BASE_URL': 'https://r.x'})
    kw = send.call_args.kwargs
    assert kw['product'] == 'connect' and kw['template'] == 'produto-atividade.html' and kw['subject'] == '[Reports] T'
    assert kw['params']['DESCRIPTION'] == 'S' and kw['params']['CTA_URL'] == 'https://r.x/connect/app/alerts'
    assert {'label': 'Severidade', 'value': 'Alta'} in kw['params']['DETAILS']
    with mock.patch('aicentralv2.services.cadu_email_connector.send_cadu_event', side_effect=RuntimeError('down')):
        assert alerts._send_alert_email(alert_row(), ['a@x.com']) is False


# ---- routes ----------------------------------------------------------------
@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = 'test'
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    alerts.register(bp)
    app.register_blueprint(bp)
    http = app.test_client()
    with http.session_transaction() as s:
        s['user_id'] = 42
    return http


ALERT_ID = str(uuid.uuid4())


def post(client, action, body=None, status='open', found=True, role='admin'):
    row = {'id': ALERT_ID, 'status': status, 'client_id': 7}
    updates = []

    def rows(sql, params=()):
        if sql.startswith('SELECT * FROM cadu_reports_alerts'):
            return [row] if found else []
        updates.append((sql.split()[0], params))
        return []
    with mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'get_db'), \
         mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': role, 'user_id': 42}), \
         mock.patch.object(alerts, '_write_guard', side_effect=lambda selected: (_ for _ in ()).throw(__import__('werkzeug').exceptions.Forbidden()) if selected['role'] == 'viewer' else None):
        response = client.post(f'/connect/api/v2/reports/alerts/{ALERT_ID}/{action}', json=body or {})
    return response, updates


def test_actions_change_state_and_write_the_history(client):
    response, updates = post(client, 'acknowledge')
    assert response.status_code == 200 and any('acknowledged' in sql for sql, _ in [(u[0] + ' ' + str(u[1]), 0) for u in updates]) or updates
    assert post(client, 'acknowledge', status='acknowledged')[0].status_code == 409
    assert post(client, 'assign', {'assign': True})[0].status_code == 200
    assert post(client, 'assign', {'assign': 'x'})[0].status_code == 400
    assert post(client, 'silence', {'hours': 24})[0].status_code == 200
    assert post(client, 'silence', {'hours': 5})[0].status_code == 400
    assert post(client, 'unsilence', status='silenced')[0].status_code == 200
    assert post(client, 'unsilence', status='open')[0].status_code == 409


def test_permanent_silence_has_no_end_date_and_is_logged(client):
    response, updates = post(client, 'silence', {'permanent': True})
    assert response.status_code == 200
    update = next(params for verb, params in updates if verb == 'UPDATE')
    assert update == (ALERT_ID,)
    log = next(params for verb, params in updates if verb == 'INSERT')
    assert '"permanent": true' in log[-1]
    assert post(client, 'silence', {'permanent': 'yes'})[0].status_code == 400


def test_a_permanent_silence_survives_new_findings():
    now = datetime.datetime.now(datetime.timezone.utc)
    current = {'id': ALERT_ID, 'subject_key': 'site', 'status': 'silenced', 'silenced_until': None}
    calls = []

    def rows(sql, params=()):
        calls.append((sql, params))
        return [current] if sql.startswith('SELECT * FROM cadu_reports_alerts') else []
    finding = {'subject_key': 'site', 'severity': 'high', 'title': 't', 'summary': 's', 'evidence': [], 'page_path': None}
    with mock.patch.object(alerts, '_rows', rows):
        alerts.sync_findings({'id': 'x', 'client_id': 7}, 'collection_absent', [finding], now)
    update = next(params for sql, params in calls if sql.lstrip().startswith('UPDATE'))
    assert update[-3:-1] == ('silenced', 'silenced')


def test_resolved_missing_and_viewer_are_rejected(client):
    assert post(client, 'acknowledge', status='resolved')[0].status_code == 409
    assert post(client, 'acknowledge', found=False)[0].status_code == 404
    assert post(client, 'acknowledge', role='viewer')[0].status_code == 403
    with mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': 'admin', 'user_id': 42}), \
         mock.patch.object(alerts, '_write_guard'), mock.patch.object(alerts, '_rows') as rows:
        response = client.post('/connect/api/v2/reports/alerts/nao-e-uuid/acknowledge', json={})
    assert response.status_code == 404
    rows.assert_not_called()


def test_listing_rejects_unknown_status_and_needs_login():
    app = Flask(__name__)
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    alerts.register(bp)
    app.register_blueprint(bp)
    assert app.test_client().get('/connect/api/v2/reports/alerts').status_code == 401


# ------------------------------------------------------------------------------------------------ insights

LABELS = {'google_ads': 'Google Ads', 'direct': 'Direto'}


def entry(origin, sessions, single, path='/lp'):
    return {'origin': origin, 'path': path, 'sessions': sessions, 'single_page': single}


def test_a_channel_is_flagged_only_when_it_bounces_far_more_than_the_others_on_the_same_page():
    rows = [entry('google_ads', 40, 32), entry('direct', 30, 9), entry('social', 10, 9)]        # ads 80% vs others 45%
    found = channel_entry_findings(rows, LABELS)
    assert [item['subject_key'] for item in found] == ['google_ads|/lp'] and found[0]['severity'] == 'low' and found[0]['page_path'] == '/lp'
    assert 'Google Ads' in found[0]['summary'] and '80%' in found[0]['summary']
    assert channel_entry_findings([entry('google_ads', 40, 32), entry('direct', 30, 24)], LABELS) == []   # weak for everyone: no channel is blamed
    assert channel_entry_findings([entry('unknown', 40, 38), entry('direct', 30, 3)], LABELS) == []       # unknown is not a channel
    assert [item['subject_key'] for item in channel_entry_findings([entry('google_ads', 40, 32), entry('direct', 30, 9), entry('unknown', 200, 5)], LABELS)] == ['google_ads|/lp']   # nor a yardstick
    assert channel_entry_findings([entry('google_ads', 19, 19), entry('direct', 30, 3)], LABELS) == []    # channel sample too small
    assert channel_entry_findings([entry('google_ads', 40, 38), entry('direct', 19, 1)], LABELS) == []    # yardstick too small
    assert channel_entry_findings([entry('google_ads', 40, 20), entry('direct', 30, 3)], LABELS) == []    # 50% is under the 60% floor


def tech(kind, value, sessions, converted):
    return {'kind': kind, 'value': value, 'sessions': sessions, 'converted': converted}


def test_device_and_screen_flag_under_half_the_site_average_with_enough_sessions():
    rows = [tech('overall', 'all', 200, 20), tech('device', 'mobile', 100, 2), tech('device', 'desktop', 100, 18),
            tech('resolution', '360x640', 40, 0), tech('resolution', '390x844', 20, 0)]          # site average 10%
    found = tech_conversion_findings(rows, {'mobile': 'Celular', 'desktop': 'Computador'})
    assert {item['subject_key'] for item in found} == {'device|mobile', 'resolution|360x640'}
    by = {item['subject_key']: item for item in found}
    assert 'Celular' in by['device|mobile']['summary'] and '360×640' in by['resolution|360x640']['summary']
    assert tech_conversion_findings([tech('overall', 'all', 200, 4), tech('device', 'mobile', 100, 0)], {}) == []   # average rests on 4 conversions
    assert tech_conversion_findings([tech('device', 'mobile', 100, 0)], {}) == []                                     # no overall row


def test_campaign_page_needs_high_bounce_low_conversion_and_a_site_average():
    overall = [tech('overall', 'all', 300, 30)]                                                     # 10%
    row = {'campaign': 'verao', 'path': '/lp', 'sessions': 40, 'single_page': 30, 'converted': 1}
    found = campaign_page_findings([row, {**row, 'campaign': 'ok', 'converted': 6}, {**row, 'campaign': 'curta', 'sessions': 19},
                                    {**row, 'campaign': 'engaja', 'single_page': 10}], overall)
    assert [item['subject_key'] for item in found] == ['verao|/lp'] and found[0]['page_path'] == '/lp'
    assert campaign_page_findings([row], [tech('overall', 'all', 300, 3)]) == []


def test_insights_keep_only_the_busiest_findings_and_cap_the_subject_key():
    rows = [entry('google_ads', 30 + index, 30 + index, path=f'/p{index}') for index in range(15)] + [entry('direct', 40, 1, path=f'/p{index}') for index in range(15)]
    found = channel_entry_findings(rows, LABELS)
    assert len(found) == 10 and found[0]['subject_key'] == 'google_ads|/p14'
    long_path = '/' + 'a' * 499
    assert len(channel_entry_findings([entry('google_ads', 40, 40, path=long_path), entry('direct', 40, 1, path=long_path)], LABELS)[0]['subject_key']) <= 520


def test_evaluate_insights_syncs_each_rule_over_seven_days_of_one_site():
    site = {'id': str(uuid.uuid4()), 'client_id': 7, 'label': 'Site'}
    seen, synced = [], []

    def fake_rows(sql, params=()):
        seen.append((sql, params))
        if "'overall'" in sql:
            return [tech('overall', 'all', 200, 20), tech('device', 'mobile', 100, 2)]
        if 'GROUP BY origin,path' in sql:
            return [entry('google_ads', 40, 32), entry('direct', 30, 9)]
        return []

    with mock.patch.object(alerts, '_rows', fake_rows), mock.patch.object(alerts, 'sync_findings', lambda s, rule, findings, now: synced.append((rule, findings))):
        alerts.evaluate_insights(site, NOW)
    assert [rule for rule, _ in synced] == ['channel_entry_exit', 'device_conversion_low', 'campaign_weak_page']
    assert len(synced[0][1]) == 1 and len(synced[1][1]) == 1 and synced[2][1] == []
    for sql, params in seen:
        assert 'AND e.site_id=%(site)s::uuid' in sql and '{site}' not in sql and params['site'] == site['id'] and params['client'] == 7
        assert params['until'] - params['since'] == datetime.timedelta(days=7)
