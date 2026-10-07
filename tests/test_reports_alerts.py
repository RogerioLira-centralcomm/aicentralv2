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
    assert set(RULES) == {'page_down', 'collection_absent', 'conversion_drop', 'traffic_anomaly', 'conversion_anomaly', 'channel_entry_exit', 'device_conversion_low', 'campaign_weak_page'}
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


# ------------------------------------------------------------------------------------------------ central v2

def test_findings_carry_channel_kind_and_the_one_figure_the_table_shows():
    down = page_down_findings([check(1, page('offline', http=500)), check(6, page('offline', http=500))])[0]
    assert (down['channel'], down['kind'], down['impact']) == ('site', 'incident', {'value': 'erro 500', 'unit': 'text', 'label': 'página fora do ar'})
    assert page_down_findings([check(1, page('offline')), check(6, page('offline'))])[0]['impact']['value'] == 'sem resposta'
    assert collection_absent_findings('Site', 500, 7.2)[0]['impact'] == {'value': '7 h', 'unit': 'text', 'label': 'sem eventos'}
    drop = conversion_drop_findings([{'path': '/a', 'current': {'sessions': 90, 'session_conversion_rate': 7.0}, 'previous': {'sessions': 90, 'session_conversion_rate': 10.0}}])[0]
    assert drop['impact'] == {'value': -30.0, 'unit': 'percent', 'label': 'taxa de conversão'}
    # insights are opportunities, so the "Oportunidades" tab can trigger automation without mixing with incidents
    assert {key for key, rule in RULES.items() if rule['kind'] == 'opportunity'} == {'channel_entry_exit', 'device_conversion_low', 'campaign_weak_page'}
    assert all(rule['channel'] in alerts.CHANNELS for rule in RULES.values())
    assert channel_entry_findings([entry('google_ads', 40, 32), entry('direct', 30, 9)], LABELS)[0]['impact']['unit'] == 'percent'


def test_page_down_never_sends_a_second_email_because_the_flow_monitor_already_does():
    logged, send = run_notify(alert_row(rule='page_down'), {'REPORTS_ALERT_EMAILS': '1'})
    assert logged == [('notification_skipped', {'reason': 'flow_monitor'})] and not send.called
    assert run_notify(alert_row(rule='collection_absent'), {'REPORTS_ALERT_EMAILS': '1'})[0] == [('notified', {'recipients': 1})]


def test_investigate_and_resolve_move_the_alert_and_resolve_is_rejected_once_closed(client):
    assert post(client, 'investigate')[0].status_code == 200
    assert post(client, 'investigate', status='acknowledged')[0].status_code == 200
    assert post(client, 'investigate', status='investigating')[0].status_code == 409
    assert post(client, 'investigate', status='silenced')[0].status_code == 409
    response, updates = post(client, 'resolve', status='investigating')
    assert response.status_code == 200 and any(verb == 'UPDATE' for verb, _ in updates)
    assert post(client, 'resolve', status='resolved')[0].status_code == 409
    assert post(client, 'resolve', role='viewer')[0].status_code == 403


def bulk(client, body):
    rows_ = {a: {'id': a, 'status': st, 'client_id': 7} for a, st in (('11111111-1111-1111-1111-111111111111', 'open'), ('22222222-2222-2222-2222-222222222222', 'resolved'))}

    def rows(sql, params=()):
        return [rows_[params[0]]] if sql.startswith('SELECT * FROM cadu_reports_alerts') and params[0] in rows_ else []
    with mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'get_db'), mock.patch.object(alerts, '_write_guard'), \
         mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': 'admin', 'user_id': 42}):
        return client.post('/connect/api/v2/reports/alerts/bulk', json=body)


def test_bulk_applies_to_each_live_alert_and_counts_the_ones_it_skips(client):
    ok, resolved, missing = '11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', '33333333-3333-3333-3333-333333333333'
    response = bulk(client, {'ids': [ok, resolved, missing, 'nao-uuid', ok], 'action': 'resolve'})
    assert response.status_code == 200 and response.get_json()['done'] == 1 and response.get_json()['skipped'] == 3
    assert bulk(client, {'ids': [], 'action': 'resolve'}).status_code == 400
    assert bulk(client, {'ids': [ok], 'action': 'silence'}).status_code == 400          # only acknowledge, investigate and resolve run in bulk
    assert bulk(client, {'ids': [ok] * 1 + [str(uuid.uuid4()) for _ in range(alerts.BULK_LIMIT)], 'action': 'resolve'}).status_code == 400
    assert bulk(client, {'ids': [1], 'action': 'resolve'}).status_code == 400


def test_listing_validates_filters_before_touching_the_database(client):
    with mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': 'admin', 'user_id': 42}), \
         mock.patch.object(alerts, '_customer_scope', return_value=None), mock.patch.object(alerts, '_rows') as rows:
        for query in ('channel=tiktok', 'severity=critical', 'status=nope', 'kind=other', 'per_page=7', 'page=abc'):
            assert client.get(f'/connect/api/v2/reports/alerts?{query}').status_code == 400, query
        rows.assert_not_called()


def test_csv_cells_cannot_run_as_spreadsheet_formulas():
    assert alerts._cell('=HYPERLINK("x")') == "'=HYPERLINK(\"x\")" and alerts._cell('+1') == "'+1" and alerts._cell(None) == '' and alerts._cell('ok') == 'ok'


def test_a_client_level_alert_without_a_site_is_keyed_by_client_and_rule():
    seen = []

    def rows(sql, params=()):
        seen.append((sql, params))
        return [{'id': ALERT_ID, 'client_id': 7, 'severity': 'high', 'title': 'T', 'summary': 'S', 'assigned_to': None, 'last_notified_at': None}] if sql.lstrip().startswith('INSERT') else []
    finding = {'subject_key': 'c1', 'severity': 'high', 'title': 't', 'summary': 's', 'evidence': [], 'page_path': None, 'channel': 'google_ads', 'kind': 'incident'}
    with mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'notify_opened'):
        alerts.sync_findings({'id': None, 'client_id': 7}, 'collection_absent', [finding], NOW)
    select, insert = seen[0], next(item for item in seen if item[0].lstrip().startswith('INSERT'))
    assert 'IS NOT DISTINCT FROM' in select[0] and select[1] == (7, None, 'collection_absent')
    assert insert[1][2] is None and 'google_ads' in insert[1] and 'incident' in insert[1]


def test_unsilencing_an_alert_under_investigation_returns_it_to_investigating(client):
    def run(row_extra):
        row = {'id': ALERT_ID, 'status': 'silenced', 'client_id': 7, **row_extra}
        updates = []

        def rows(sql, params=()):
            if sql.startswith('SELECT * FROM cadu_reports_alerts'):
                return [row]
            updates.append((sql, params))
            return []
        with mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'get_db'), mock.patch.object(alerts, '_write_guard'), \
             mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': 'admin', 'user_id': 42}):
            assert client.post(f'/connect/api/v2/reports/alerts/{ALERT_ID}/unsilence', json={}).status_code == 200
        return next(params for sql, params in updates if sql.startswith('UPDATE'))[0]
    assert run({'investigating_at': NOW}) == 'investigating' and run({'investigating_at': None}) == 'open'


# ------------------------------------------------------------------------------------------------ Google Ads in the center

def gads_item(rule='cap_reached', key='1', severity='high', impact=('cost', 1234.5), action='Revise o teto.'):
    return {'id': f'{rule}:{key}', 'rule': rule, 'severity': severity, 'title': 'Teto de orçamento atingido', 'object': {'kind': 'campaign', 'label': 'Verão'},
            'summary': 'Gasto alcançou o teto.', 'action': action, 'impact': {'kind': impact[0], 'value': impact[1]}, 'evidence': [('Gasto', 'R$ 10')]}


def test_google_ads_recommendations_become_client_level_alerts_with_a_kind_and_an_action():
    from aicentralv2.cadu_connect import reports_alert_gads as gads
    found = gads.finding_from_recommendation(gads_item())
    assert found['rule'] == 'gads_cap_reached' and found['subject_key'] == 'cap_reached:1' and found['channel'] == 'google_ads' and found['kind'] == 'incident'
    assert found['title'] == 'Teto de orçamento atingido: Verão' and found['recommendations'] == ['Revise o teto.']
    assert found['impact'] == {'value': 'R$ 1.234,50', 'unit': 'text', 'label': 'gasto envolvido'}
    assert found['evidence'] == [{'label': 'Gasto', 'value': 'R$ 10', 'unit': 'text'}]
    assert gads.finding_from_recommendation(gads_item('add_keyword', impact=('none', 0)))['kind'] == 'opportunity'
    assert gads.finding_from_recommendation(gads_item('add_keyword', impact=('none', 0)))['impact'] is None


def test_every_google_ads_rule_is_synced_so_recovered_ones_close():
    from aicentralv2.cadu_connect import reports_alert_gads as gads
    from aicentralv2.cadu_connect.reports_google_ads_rules import RULES as GADS_RULES
    synced = {}
    count = gads.evaluate_google_ads(7, datetime.date(2026, 10, 7), lambda scope, previous: {'recommendations': [gads_item()]},
                                     lambda site, rule, findings, now: synced.setdefault(rule, (site, findings)), NOW)
    assert set(synced) == {f"gads_{item['rule']}" for item in GADS_RULES} and count == 1
    assert synced['gads_cap_reached'][0] == {'id': None, 'client_id': 7} and len(synced['gads_cap_reached'][1]) == 1
    assert synced['gads_script_stale'][1] == []         # nothing found this time: the sync auto-resolves what was open
    assert all(len(rule) <= 40 for rule in synced)       # the alerts.rule column is VARCHAR(40)


def test_the_catalog_lists_site_and_google_ads_rules_without_touching_the_site_rules():
    keys = {item['rule'] for item in alerts.rules_catalog()}
    assert set(RULES) < keys and 'gads_cap_reached' in keys and 'gads_cap_reached' not in RULES
    assert all(item['channel'] in alerts.CHANNELS and item['kind'] in ('incident', 'opportunity') for item in alerts.rules_catalog())


def test_recommendations_are_stored_with_the_alert_and_refreshed_on_every_sighting():
    seen = []

    def rows(sql, params=()):
        seen.append((sql, params))
        return [{'id': ALERT_ID, 'client_id': 7, 'severity': 'high', 'title': 'T', 'summary': 'S', 'assigned_to': None, 'last_notified_at': None}] if sql.lstrip().startswith('INSERT') else []
    finding = {'subject_key': 'c1', 'severity': 'high', 'title': 't', 'summary': 's', 'evidence': [], 'page_path': None, 'channel': 'google_ads', 'kind': 'incident',
               'recommendations': ['Faça isto.']}
    with mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'notify_opened'):
        alerts.sync_findings({'id': None, 'client_id': 7}, 'gads_cap_reached', [finding], NOW)
    insert = next(params for sql, params in seen if sql.lstrip().startswith('INSERT'))
    assert '["Faça isto."]' in [item for item in insert if isinstance(item, str)][-1] or '["Fa\\u00e7a isto."]' in insert


def test_google_ads_evaluation_survives_one_client_failing():
    app = Flask(__name__)
    calls = []

    def fake(client_id, today, analysis, sync, now, disabled=frozenset()):
        calls.append(client_id)
        if client_id == 1:
            raise RuntimeError('boom')
    from aicentralv2.cadu_connect import reports_google_ads as gads
    with app.app_context(), mock.patch.object(gads, '_ready', return_value=True), mock.patch.object(alerts, 'get_db'), \
         mock.patch.object(alerts, '_rows', return_value=[{'client_id': 1}, {'client_id': 2}]), \
         mock.patch('aicentralv2.cadu_connect.reports_alert_gads.evaluate_google_ads', fake):
        assert alerts.evaluate_google_ads_all(NOW) == 2
    assert calls == [1, 2]


def test_email_burst_is_capped_per_client_per_hour_and_the_skip_is_logged():
    on = {'REPORTS_ALERT_EMAILS': '1'}
    logged = []
    with mock.patch.object(alerts, '_log', lambda alert_id, kind, actor=None, detail=None: logged.append((kind, detail))), \
         mock.patch.object(alerts, '_recipients', return_value=['a@x.com']), \
         mock.patch.object(alerts, '_rows', return_value=[{'n': alerts.NOTIFY_BURST_LIMIT}]), \
         mock.patch('aicentralv2.services.cadu_email_connector.send_cadu_event', return_value={'success': True}) as send, \
         mock.patch.dict('os.environ', on, clear=False):
        alerts.notify_opened(alert_row(rule='gads_cap_reached'), NOW)
    assert logged == [('notification_skipped', {'reason': 'burst'})] and not send.called


def test_an_alert_held_back_by_the_hourly_cap_is_sent_on_a_later_cycle():
    current = {'id': ALERT_ID, 'client_id': 7, 'rule': 'gads_cap_reached', 'subject_key': 'c1', 'status': 'open', 'silenced_until': None, 'last_notified_at': None,
               'severity': 'high', 'assigned_to': None}
    finding = {'subject_key': 'c1', 'severity': 'high', 'title': 't', 'summary': 's', 'evidence': [], 'page_path': None}

    def run(last_event):
        notified = []

        def rows(sql, params=()):
            if sql.startswith('SELECT * FROM cadu_reports_alerts'):
                return [current]
            if 'FROM cadu_reports_alert_events' in sql:
                return last_event
            return []
        with mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'notify_opened', lambda alert, now, retry=False: notified.append(retry)):
            alerts.sync_findings({'id': None, 'client_id': 7}, 'gads_cap_reached', [finding], NOW)
        return notified
    assert run([{'kind': 'notification_skipped', 'detail': {'reason': 'burst'}}]) == [True]
    assert run([{'kind': 'notification_skipped', 'detail': {'reason': 'disabled'}}]) == []     # other skips are decisions, not delays
    assert run([{'kind': 'notified', 'detail': {}}]) == [] and run([]) == []


def test_a_quiet_retry_under_the_cap_never_writes_a_skip_to_the_history():
    logged = []
    with mock.patch.object(alerts, '_log', lambda alert_id, kind, actor=None, detail=None: logged.append(kind)), mock.patch.object(alerts, '_recipients', return_value=['a@x.com']), \
         mock.patch.object(alerts, '_rows', return_value=[{'n': alerts.NOTIFY_BURST_LIMIT}]), mock.patch.dict('os.environ', {'REPORTS_ALERT_EMAILS': '1'}, clear=False):
        assert alerts.notify_opened(alert_row(rule='gads_cap_reached'), NOW, retry=True) is None
    assert logged == []


# ------------------------------------------------------------------------------------------------ UTI of the monitored URLs

def reading(minutes_ago, *pages):
    return {'checked_at': NOW - datetime.timedelta(minutes=minutes_ago), 'pages': list(pages)}


def vpage(status, path='/lp', ms=400, http=200):
    return {'host': 'www.exemplo.com.br', 'path': path, 'label': 'LP', 'status': status, 'http_status': http, 'duration_ms': ms, 'detail': 'x'}


FLOW = {'id': 'f1', 'name': 'Fluxo', 'allowed_host': 'www.exemplo.com.br'}


def test_vitals_classify_each_url_and_keep_the_pulse_oldest_first():
    from aicentralv2.cadu_connect.reports_alert_vitals import summarize, url_vitals
    rows = url_vitals(FLOW, [reading(1, vpage('offline', http=503), vpage('online', '/ok', ms=3600)), reading(6, vpage('offline', http=503), vpage('online', '/ok', ms=3500)),
                             reading(11, vpage('online'), vpage('online', '/ok', ms=3800))])
    by = {row['path']: row for row in rows}
    assert by['/lp']['vital'] == 'critical' and by['/lp']['pulse'] == ['online', 'offline', 'offline'] and by['/lp']['streak'] == 2
    assert by['/lp']['down_since'] == NOW - datetime.timedelta(minutes=6) and by['/lp']['uptime'] == 33.3 and by['/lp']['http_status'] == 503
    assert by['/ok']['vital'] == 'attention' and by['/ok']['average_ms'] == 3633 and by['/ok']['down_since'] is None      # online now, but slow on average
    assert [row['vital'] for row in rows] == ['critical', 'attention'] and summarize(rows) == {'critical': 1, 'attention': 1, 'stable': 0, 'total': 2}
    steady = url_vitals(FLOW, [reading(1, vpage('online')), reading(6, vpage('online'))])[0]
    assert steady['vital'] == 'stable' and steady['uptime'] == 100.0
    assert url_vitals(FLOW, [reading(1, vpage('online'))] * 2 + [reading(11, vpage('offline'))] * 2)[0]['vital'] == 'attention'   # 50% of the recent readings


def test_the_degraded_state_is_attention_and_an_unknown_state_never_looks_healthy():
    from aicentralv2.cadu_connect.reports_alert_vitals import url_vitals
    assert url_vitals(FLOW, [reading(1, vpage('degraded'))])[0]['vital'] == 'attention'
    assert url_vitals(FLOW, [reading(1, {**vpage('online'), 'status': 'weird'})])[0]['state'] == 'degraded'
    assert url_vitals(FLOW, []) == [] and url_vitals(FLOW, [reading(1)]) == []


def test_the_ninety_day_heatmap_has_one_cell_per_day_oldest_first_with_gaps_left_empty():
    from aicentralv2.cadu_connect.reports_alert_vitals import HEAT_DAYS, attach_heat
    today = datetime.date(2026, 10, 7)
    url = {'flow_id': 'f1', 'host': 'h', 'path': '/lp'}
    day = lambda ago, checks, online, ms=400: {'flow_id': 'f1', 'host': 'h', 'path': '/lp', 'day': today - datetime.timedelta(days=ago), 'checks': checks, 'online': online, 'duration_ms_sum': checks * ms}
    out = attach_heat([url, {'flow_id': 'f1', 'host': 'h', 'path': '/other'}], [day(0, 288, 288), day(1, 288, 144, 900), day(89, 10, 10), day(90, 5, 0)], today)
    heat = out[0]['heat']
    assert len(heat) == HEAT_DAYS == 90 and heat[-1] == [100.0, 400] and heat[-2] == [50.0, 900] and heat[0] == [100.0, 400] and heat[10] is None
    assert out[0]['days_measured'] == 3 and out[0]['uptime_90'] == round(100 * (288 + 144 + 10 + 0) / (288 + 288 + 10 + 5), 1)   # day 90 is outside the window but its rows are counted
    assert out[1]['heat'] == [None] * 90 and out[1]['uptime_90'] is None and out[1]['days_measured'] == 0


# ------------------------------------------------------------------------------------------------ anomalies, series and causes

TODAY = datetime.date(2026, 10, 7)          # a Wednesday: the judged day is Tuesday 2026-10-06


def daily_series(**overrides):
    """Eight weeks of steady days (sessions 200, conversions 10), with chosen days replaced."""
    days = {TODAY - datetime.timedelta(days=offset): {'sessions': 200, 'conversions': 10} for offset in range(1, 57)}
    for offset, values in overrides.items():
        days[TODAY - datetime.timedelta(days=int(offset.lstrip('d')))] = values
    return days


def test_a_day_far_below_its_weekday_baseline_is_an_anomaly_with_a_series_and_a_range():
    from aicentralv2.cadu_connect.reports_alert_rules import ANOMALY_SERIES_DAYS, anomaly_findings
    found = anomaly_findings(daily_series(d1={'sessions': 90, 'conversions': 10}), TODAY, 'Loja')
    assert [item['rule'] for item in found] == ['traffic_anomaly'] and found[0]['subject_key'] == 'sessions'
    item = found[0]
    assert item['severity'] == 'medium' and item['impact'] == {'value': -55.0, 'unit': 'percent', 'label': 'sessões'} and 'abaixo do esperado' in item['summary']
    assert {e['label']: e['value'] for e in item['evidence']}['Esperado (mesmo dia da semana)'] == 200
    assert len(item['series']['labels']) == len(item['series']['current']) == len(item['series']['previous']) == ANOMALY_SERIES_DAYS
    assert item['series']['current'][-1] == 90 and item['series']['previous'][-1] == 200.0


def test_a_rise_is_reported_as_low_and_normal_wobble_never_alerts():
    from aicentralv2.cadu_connect.reports_alert_rules import anomaly_findings
    rise = anomaly_findings(daily_series(d1={'sessions': 420, 'conversions': 10}), TODAY, 'Loja')
    assert rise[0]['severity'] == 'low' and 'acima do esperado' in rise[0]['summary']
    assert anomaly_findings(daily_series(d1={'sessions': 160, 'conversions': 8}), TODAY, 'Loja') == []        # -20%: inside the tolerance
    assert anomaly_findings(daily_series(d1={'sessions': 200, 'conversions': 10}), TODAY, 'Loja') == []


def test_anomalies_need_a_trusted_baseline_and_leave_silence_to_the_tracking_rule():
    from aicentralv2.cadu_connect.reports_alert_rules import anomaly_findings
    quiet = {day: {'sessions': 20, 'conversions': 1} for day in daily_series()}
    quiet[TODAY - datetime.timedelta(days=1)] = {'sessions': 1, 'conversions': 0}
    assert anomaly_findings(quiet, TODAY, 'Loja') == []                                                            # expected 20/day is below the floor
    assert anomaly_findings(daily_series(d1={'sessions': 0, 'conversions': 0}), TODAY, 'Loja')[0]['rule'] == 'conversion_anomaly'   # zero sessions is collection_absent's job
    young = {day: values for day, values in daily_series().items() if (TODAY - day).days <= 10}
    young[TODAY - datetime.timedelta(days=1)] = {'sessions': 10, 'conversions': 0}
    assert anomaly_findings(young, TODAY, 'Loja') == []                                                            # fewer than 3 same-weekday weeks
    assert anomaly_findings({}, TODAY, 'Loja') == []
    noisy = daily_series(**{f'd{week * 7 + 1}': {'sessions': value, 'conversions': 10} for week, value in zip(range(1, 5), (80, 320, 120, 280))}, d1={'sessions': 110, 'conversions': 10})
    assert anomaly_findings(noisy, TODAY, 'Loja') == []                                                            # the baseline itself swings: a normal day for this weekday


def test_causes_only_state_facts_of_the_same_window():
    from aicentralv2.cadu_connect import reports_alert_causes as causes
    day = lambda ago, checks, online, ms: {'day': TODAY - datetime.timedelta(days=ago), 'checks': checks, 'online': online, 'duration_ms_sum': checks * ms}
    rows = [day(0, 288, 288, 2000), day(1, 288, 100, 2000), day(2, 288, 288, 2000), day(8, 288, 288, 400), day(9, 288, 288, 400)]
    found = causes.url_causes(rows, TODAY)
    assert any('abaixo de 95% de disponibilidade em 1 dia' in text and '35%' in text for text in found)
    assert any('subiu de 400 ms para 2000 ms (+400%)' in text for text in found)
    assert causes.url_causes([day(0, 288, 288, 450), day(8, 288, 288, 400)], TODAY) == []                       # a small slowdown is not a cause
    assert causes.url_causes([], TODAY) == []
    assert causes.traffic_cause(60, 100)[0].startswith('O tráfego da página caiu 40%') and causes.traffic_cause(95, 100) == [] and causes.traffic_cause(10, 0) == []
    assert len(causes.tracking_cause(True)) == 1 and causes.tracking_cause(False) == []
    assert causes.combine(['a', 'b'], ['b', 'c']) == ['a', 'b', 'c']
    assert causes.host_causes([day(1, 288, 100, 400), day(1, 288, 288, 400)], TODAY - datetime.timedelta(days=1), TODAY)[0].startswith('1 URL monitorada ficou')


def test_conversion_drop_gets_a_chart_figures_the_impacted_url_and_causes():
    page = {'path': '/lp', 'current': {'sessions': 90, 'converted_sessions': 6, 'session_conversion_rate': 6.7}, 'previous': {'sessions': 100, 'converted_sessions': 10, 'session_conversion_rate': 10.0}}
    finding = conversion_drop_findings([{**page, 'current': {**page['current'], 'session_conversion_rate': 6.7}}])[0]
    site = {'id': 's1', 'client_id': 7, 'allowed_host': 'loja.com', 'label': 'Loja'}
    rates = iter(range(1, 15))
    window = mock.Mock(side_effect=lambda site_id, path, since, until: ({'session_conversion_rate': float(next(rates))}, []))
    with mock.patch('aicentralv2.cadu_connect.reports_pages.window_metrics', window), mock.patch.object(alerts, '_monitor_rows', return_value=[]), mock.patch.object(alerts, '_tracking_gap', return_value=True):
        out = alerts.enrich_conversion_drop(site, finding, page, TODAY)
    assert window.call_count == 14 and out['series']['previous'] == [float(n) for n in range(1, 8)] and out['series']['current'] == [float(n) for n in range(8, 15)]
    assert out['series']['labels'][-1] == '2026-10-06' and out['series']['labels'][0] == '2026-09-30' and out['series']['unit'] == 'percent'   # ends on the last complete day
    assert [m['label'] for m in out['metrics']] == ['Taxa de conversão', 'Visitas', 'Conversões'] and out['metrics'][0]['change'] == -33.0 and out['metrics'][1]['change'] == -10.0
    assert out['impacted_urls'] == [{'path': '/lp', 'sessions': 90, 'conversions': 6, 'rate': 6.7, 'change': -33.0}]
    assert any('Super Tag' in text for text in out['causes'])


def test_the_panel_data_is_stored_with_the_alert():
    seen = []

    def rows(sql, params=()):
        seen.append((sql, params))
        return [{'id': ALERT_ID, 'client_id': 7, 'severity': 'high', 'title': 'T', 'summary': 'S', 'assigned_to': None, 'last_notified_at': None}] if sql.lstrip().startswith('INSERT') else []
    finding = {'subject_key': 'k', 'severity': 'medium', 'title': 't', 'summary': 's', 'evidence': [], 'page_path': None, 'channel': 'site', 'kind': 'incident',
               'series': {'labels': ['2026-10-07'], 'current': [1], 'previous': [2], 'unit': 'count'}, 'metrics': [{'label': 'x', 'value': 1, 'unit': 'count'}],
               'impacted_urls': [{'path': '/lp'}], 'causes': ['c']}
    with mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'notify_opened'):
        alerts.sync_findings({'id': 's1', 'client_id': 7}, 'traffic_anomaly', [finding], NOW)
    insert = next(params for sql, params in seen if sql.lstrip().startswith('INSERT'))
    strings = [item for item in insert if isinstance(item, str)]
    assert any('"labels"' in item for item in strings) and any('"label": "x"' in item for item in strings) and any('/lp' in item for item in strings) and '["c"]' in strings
    plain = {k: v for k, v in finding.items() if k not in ('series', 'metrics', 'impacted_urls', 'causes')}
    seen.clear()
    with mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'notify_opened'):
        alerts.sync_findings({'id': 's1', 'client_id': 7}, 'traffic_anomaly', [plain], NOW)
    assert None in next(params for sql, params in seen if sql.lstrip().startswith('INSERT'))                       # no series: stored as NULL, not as the string "null"


def test_anomalies_are_evaluated_per_site_and_closed_when_the_day_is_normal():
    site = {'id': 's1', 'client_id': 7, 'allowed_host': 'loja.com', 'label': 'Loja'}
    synced = {}
    rows = [{'day': day, 'sessions': v['sessions'], 'conversions': v['conversions']} for day, v in daily_series(d1={'sessions': 90, 'conversions': 10}).items()]
    with mock.patch.object(alerts, '_rows', return_value=rows), mock.patch.object(alerts, '_monitor_rows', return_value=[]), mock.patch.object(alerts, '_tracking_gap', return_value=False), \
         mock.patch.object(alerts, 'sync_findings', lambda s, rule, findings, now: synced.setdefault(rule, findings)):
        alerts.evaluate_anomalies(site, datetime.datetime(2026, 10, 7, 15, 0, tzinfo=datetime.timezone.utc))
    assert set(synced) == {'traffic_anomaly', 'conversion_anomaly'} and len(synced['traffic_anomaly']) == 1 and synced['conversion_anomaly'] == []


def test_a_failure_in_the_panel_work_never_discards_the_alerts_already_synced_for_the_site():
    site = {'id': 's1', 'client_id': 7, 'allowed_host': 'loja.com', 'label': 'Loja'}
    calls = []
    db = mock.Mock()
    db.commit.side_effect = lambda: calls.append('commit')
    db.rollback.side_effect = lambda: calls.append('rollback')
    page = {'path': '/lp', 'current': {'sessions': 90, 'converted_sessions': 6, 'session_conversion_rate': 6.7}, 'previous': {'sessions': 100, 'converted_sessions': 10, 'session_conversion_rate': 10.0}}
    app = Flask(__name__)

    def fake_rows(sql, params=()):
        if 'FROM cadu_reports_flow_monitor_checks' in sql:
            return []
        if 'MAX(occurred_at)' in sql:
            return [{'last_event': None, 'hours': None, 'baseline': 0}]
        return [{'path': '/lp'}] if 'GROUP BY 1 ORDER BY views' in sql else []
    window = mock.Mock(return_value=(page['current'], []))
    with app.app_context(), mock.patch.object(alerts, '_rows', fake_rows), mock.patch.object(alerts, 'get_db', return_value=db), mock.patch.object(alerts, 'sync_findings', lambda *a, **k: calls.append('sync')), \
         mock.patch('aicentralv2.cadu_connect.reports_pages.window_metrics', window), mock.patch.object(alerts, 'conversion_drop_findings', return_value=[{'subject_key': '/lp'}]), \
         mock.patch.object(alerts, 'enrich_conversion_drop', side_effect=RuntimeError('boom')), mock.patch.object(alerts, 'evaluate_anomalies'), mock.patch.object(alerts, 'evaluate_insights'):
        alerts.evaluate_site(site, heavy=True, now=NOW)
    # page_down and collection_absent are committed before the panel work can fail and roll back
    assert calls[:3] == ['sync', 'sync', 'commit'] and 'rollback' in calls
    assert 'commit' in calls[calls.index('rollback'):], 'the conversion_drop sync is committed even after the panel work failed'


# ------------------------------------------------------------------------------------------------ settings, AI, filters, impact

def test_settings_default_to_the_rule_and_only_accept_values_inside_the_bounds():
    from aicentralv2.cadu_connect import reports_alert_settings as cfg
    assert cfg.is_enabled({}, 'page_down') and cfg.threshold({}, 'page_down') == 2 and cfg.threshold({}, 'conversion_drop') == 30.0 and cfg.threshold({}, 'channel_entry_exit') is None
    row = lambda **kw: {'enabled': True, 'notify': True, 'params': {}, **kw}
    assert cfg.threshold({'page_down': row(params={'threshold': 5})}, 'page_down') == 5
    assert cfg.threshold({'page_down': row(params={'threshold': 99})}, 'page_down') == 2          # out of range: back to the default, never a broken rule
    assert cfg.threshold({'page_down': row(params={'threshold': True})}, 'page_down') == 2
    assert cfg.disabled_rules({'a': row(enabled=False), 'b': row(), '_client': row(enabled=False)}) == {'a'}
    assert cfg.conversion_value({'_client': row(params={'conversion_value': 120.5})}) == 120.5 and cfg.conversion_value({'_client': row(params={'conversion_value': 0})}) is None
    known = {'page_down', 'gads_cap_reached', 'conversion_drop'}
    assert cfg.parse({'rules': {'page_down': {'enabled': False, 'notify': False, 'threshold': 4}}, 'conversion_value': 80}, known) == ({'page_down': {'enabled': False, 'notify': False, 'threshold': 4}}, 80)
    assert cfg.parse({}, known) == ({}, ...) and cfg.parse({'conversion_value': None}, known)[1] is None
    for bad in ({'rules': {'nope': {}}}, {'rules': {'page_down': {'threshold': 1}}}, {'rules': {'page_down': {'threshold': 11}}}, {'rules': {'gads_cap_reached': {'threshold': 5}}},
                {'rules': {'page_down': {'enabled': 'yes'}}}, {'rules': {'page_down': {'threshold': True}}}, {'conversion_value': 0}, {'conversion_value': -3}, {'conversion_value': 'x'}, {'rules': {'page_down': 3}}):
        with pytest.raises(ValueError):
            cfg.parse(bad, known)
    described = {item['rule']: item for item in cfg.describe(alerts.rules_catalog(), {'conversion_drop': row(enabled=False, params={'threshold': 40})})}
    assert described['conversion_drop']['enabled'] is False and described['conversion_drop']['tunable']['value'] == 40 and described['page_down']['tunable']['default'] == 2
    assert described['gads_cap_reached']['tunable'] is None and described['gads_cap_reached']['notify'] is True


def test_a_disabled_rule_closes_its_alerts_and_a_tuned_threshold_changes_what_opens():
    site = {'id': 's1', 'client_id': 7, 'allowed_host': 'loja.com', 'label': 'Loja'}
    row = lambda **kw: {'enabled': True, 'notify': True, 'params': {}, **kw}

    def run(cfg, checks):
        synced = {}

        def rows(sql, params=()):
            if 'FROM cadu_reports_flow_monitor_checks' in sql:
                return checks
            if 'MAX(occurred_at)' in sql:
                return [{'last_event': None, 'hours': None, 'baseline': 0}]
            return []
        with mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'load_settings', return_value=cfg), mock.patch.object(alerts, 'get_db'), \
             mock.patch.object(alerts, 'sync_findings', lambda s, rule, findings, now: synced.setdefault(rule, findings)):
            alerts.evaluate_site(site, heavy=False, now=NOW)
        return synced
    down = [check(1, page('offline')), check(6, page('offline')), check(11, page('online'))]
    assert len(run({}, down)['page_down']) == 1                                                       # default: 2 failures in a row
    assert run({'page_down': row(params={'threshold': 3})}, down)['page_down'] == []                   # tuned to 3: not yet
    assert run({'page_down': row(enabled=False)}, down)['page_down'] == []                            # off: synced empty, so open alerts close
    assert 'collection_absent' in run({'collection_absent': row(enabled=False)}, down)


def test_the_rule_email_switch_mutes_only_the_email():
    on = {'REPORTS_ALERT_EMAILS': '1'}
    logged = []
    with mock.patch.object(alerts, '_log', lambda alert_id, kind, actor=None, detail=None: logged.append((kind, detail))), mock.patch.object(alerts, '_recipients', return_value=['a@x.com']), \
         mock.patch.object(alerts, '_rows', return_value=[{'notify': False}]), mock.patch('aicentralv2.services.cadu_email_connector.send_cadu_event', return_value={'success': True}) as send, \
         mock.patch.dict('os.environ', on, clear=False):
        alerts.notify_opened(alert_row(rule='conversion_drop', severity='high'), NOW)
    assert logged == [('notification_skipped', {'reason': 'rule_muted'})] and not send.called


def test_google_ads_rules_the_client_turned_off_are_synced_empty():
    from aicentralv2.cadu_connect import reports_alert_gads as gads
    synced = {}
    count = gads.evaluate_google_ads(7, datetime.date(2026, 10, 7), lambda scope, previous: {'recommendations': [gads_item()]}, lambda site, rule, findings, now: synced.setdefault(rule, findings), NOW,
                                     disabled=frozenset({'gads_cap_reached'}))
    assert synced['gads_cap_reached'] == [] and count == 0


def settings_client():
    app = Flask(__name__)
    app.secret_key = 't'
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    alerts.register(bp)
    app.register_blueprint(bp)
    http = app.test_client()
    with http.session_transaction() as s:
        s['user_id'] = 42
    return http


def test_only_admins_save_settings_and_bad_values_are_refused_before_anything_is_written():
    http, writes = settings_client(), []
    for role, body, status in (('admin', {'rules': {'page_down': {'threshold': 4}}}, 200), ('admin', {'rules': {'page_down': {'threshold': 40}}}, 400), ('admin', {'rules': {'zzz': {}}}, 400),
                               ('editor', {'rules': {'page_down': {'enabled': False}}}, 403), ('viewer', {'rules': {}}, 403)):
        writes.clear()
        with mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': role, 'user_id': 42}), mock.patch.object(alerts, '_rows', lambda sql, params=(): writes.append(sql) or []), \
             mock.patch.object(alerts, 'get_db'), mock.patch.object(alerts, '_write_guard', side_effect=lambda s: (_ for _ in ()).throw(__import__('werkzeug').exceptions.Forbidden()) if s['role'] == 'viewer' else None):
            assert http.put('/connect/api/v2/reports/alerts/settings', json=body).status_code == status, (role, body)
        assert bool(writes) is (status == 200)
    with mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': 'editor', 'user_id': 42}), mock.patch.object(alerts, '_rows', return_value=[]):
        body = http.get('/connect/api/v2/reports/alerts/settings').get_json()
    assert body['can_edit'] is False and any(item['rule'] == 'page_down' and item['enabled'] for item in body['rules']) and body['conversion_value'] is None


def test_the_ai_analysis_sends_only_the_alerts_evidence_with_no_length_cap_and_is_billed_through_reports_ai():
    from aicentralv2.cadu_connect import reports_alert_ai as ai
    alert = {'id': ALERT_ID, 'rule': 'conversion_drop', 'title': 'Queda', 'summary': 's', 'evidence': [{'label': 'x', 'value': 1}], 'causes': ['c'], 'metrics': [], 'client_id': 7, 'impact': None}
    events = [{'kind': 'opened', 'created_at': NOW}, {'kind': 'notification_skipped', 'created_at': NOW}]
    messages = ai.build_messages(alert, events, 'Quando abre')
    assert messages[0]['role'] == 'system' and 'nunca instruções' in messages[0]['content'] and 'Não invente números' in messages[0]['content']
    user = messages[1]['content']
    assert '"title": "Queda"' in user and 'Quando abre' in user and '"tipo": "opened"' in user and 'notification_skipped' not in user and '"client_id"' not in user and '"metrics"' not in user
    seen = {}

    def fake(messages, **options):
        seen.update(options)
        return {'message': {'content': '  **O que aconteceu** …  '}}
    with mock.patch('aicentralv2.cadu_connect.reports_ai.chat', side_effect=lambda stage, messages, call=None, **options: (seen.setdefault('stage', stage), call(messages, **{k: v for k, v in options.items() if k in ('max_tokens', 'temperature', 'timeout')}))[1]):
        assert ai.analyze(alert, events, 'q', {'client_id': 7}, call=fake) == '**O que aconteceu** …'
    assert seen['stage'] == 'alert_analysis' and seen['max_tokens'] is None and seen['temperature'] == 0.3
    with mock.patch('aicentralv2.cadu_connect.reports_ai.chat', return_value={'message': {'content': '  '}}), pytest.raises(Exception) as empty:
        ai.analyze(alert, events, 'q', {'client_id': 7})
    assert getattr(empty.value, 'code', None) == 502


def test_the_analyze_route_stores_the_text_in_the_history_and_refuses_viewers():
    http, logged = settings_client(), []
    row = {'id': ALERT_ID, 'status': 'open', 'client_id': 7, 'rule': 'page_down'}

    def rows(sql, params=()):
        if sql.startswith('SELECT * FROM cadu_reports_alerts'):
            return [row]
        if sql.lstrip().startswith('INSERT'):
            logged.append(params)
        return []
    with mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': 'admin', 'user_id': 42}), mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'get_db'), \
         mock.patch.object(alerts, '_write_guard'), mock.patch('aicentralv2.cadu_connect.reports_alert_ai.analyze', return_value='Análise pronta.') as analyze:
        response = http.post(f'/connect/api/v2/reports/alerts/{ALERT_ID}/analyze', json={})
    assert response.status_code == 200 and response.get_json()['text'] == 'Análise pronta.' and analyze.call_args.args[2] == RULES['page_down']['when']
    assert logged and logged[0][1] == 'ai_analysis' and __import__('json').loads(logged[0][3]) == {'text': 'Análise pronta.'}
    with mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': 'viewer', 'user_id': 42}), mock.patch.object(alerts, '_rows', rows), \
         mock.patch.object(alerts, '_write_guard', side_effect=__import__('werkzeug').exceptions.Forbidden()), mock.patch('aicentralv2.cadu_connect.reports_alert_ai.analyze') as spent:
        assert http.post(f'/connect/api/v2/reports/alerts/{ALERT_ID}/analyze', json={}).status_code == 403
    assert not spent.called


def test_the_extra_filters_are_validated_and_become_parameters():
    http, seen = settings_client(), []
    with mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': 'admin', 'user_id': 42}), mock.patch.object(alerts, '_customer_scope', return_value=None), \
         mock.patch.object(alerts, '_rows', lambda sql, params=(): seen.append((sql, params)) or [{'n': 0}]):
        for bad in ('assigned=other', 'seen=3', 'seen=x'):
            assert http.get(f'/connect/api/v2/reports/alerts?{bad}').status_code == 400, bad
        assert not seen
        assert http.get('/connect/api/v2/reports/alerts?assigned=me&seen=7').status_code == 200
        sql, params = seen[0]
        assert 'a.assigned_to=%s' in sql and "a.last_seen_at>=NOW()-%s*INTERVAL '1 day'" in sql and 42 in params and 7 in params
        seen.clear()
        http.get('/connect/api/v2/reports/alerts?assigned=none')
        assert 'a.assigned_to IS NULL' in seen[0][0]


def test_the_estimated_impact_needs_a_conversion_value_and_counts_only_lost_conversions():
    http = settings_client()
    metrics = [[{'label': 'Taxa', 'value': 1, 'previous': 2}, {'label': 'Conversões', 'value': 40, 'previous': 60}], [{'label': 'Conversões', 'value': 12.0, 'previous': 10.0}],
               [{'label': 'Conversões', 'value': 5, 'previous': 8.5}], []]

    def run(value):
        def rows(sql, params=()):
            if 'a.rule IN' in sql:
                return [{'metrics': item} for item in metrics]
            if 'FILTER (WHERE a.kind' in sql:
                return [{k: 0 for k in ('incidents', 'investigating', 'opportunities', 'opened_now', 'opened_before', 'resolved_today', 'resolved_yesterday')}]
            if 'jsonb_array_length' in sql:
                return [{'n': 0}]
            return [{'up_now': 0, 'all_now': 0, 'up_before': 0, 'all_before': 0}]
        with mock.patch.object(alerts, '_selection', return_value={'client_id': 7, 'role': 'admin', 'user_id': 42}), mock.patch.object(alerts, '_customer_scope', return_value=None), \
             mock.patch.object(alerts, '_rows', rows), mock.patch.object(alerts, 'load_settings', return_value={'_client': {'enabled': True, 'notify': True, 'params': {'conversion_value': value}}} if value else {}):
            return http.get('/connect/api/v2/reports/alerts/summary').get_json()
    body = run(100)
    assert body['estimated_impact'] == {'micros': 2_350_000_000, 'currency': 'BRL', 'lost_conversions': 23.5} and body['conversion_value_set'] is True    # (20 + 0 + 3.5) × R$ 100
    body = run(None)
    assert body['estimated_impact'] is None and body['conversion_value_set'] is False
