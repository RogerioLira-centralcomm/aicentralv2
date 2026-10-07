"""Alert center SQL against a real PostgreSQL: the v1+v2 migrations, dedup without a site, listing, summary and monitors.

Runs in a throwaway schema (search_path), so it never touches real tables. Skipped unless CX_TEST_DATABASE_URL points to a database made for tests.
"""
import datetime
import json
import os
import uuid
from pathlib import Path
from unittest import mock

import pytest
from flask import Blueprint, Flask

from aicentralv2.cadu_connect import reports_alerts as alerts
from aicentralv2.cadu_connect import reports_flow_monitor as monitor

ROOT = Path(__file__).resolve().parents[1]
SITE, CLIENT, USER = str(uuid.uuid4()), 7, 42
NOW = datetime.datetime.now(datetime.timezone.utc)

STUBS = '''
CREATE TABLE cadu_reports_supertag_sites(id UUID PRIMARY KEY, client_id BIGINT, customer_id BIGINT, label TEXT, allowed_host TEXT,
    enabled BOOL DEFAULT TRUE, revoked_at TIMESTAMPTZ);
CREATE TABLE tbl_contato_cliente(id_contato_cliente BIGINT PRIMARY KEY, nome_completo TEXT, email TEXT, status BOOL);
CREATE TABLE cadu_reports_supertag_events(site_id UUID, occurred_at TIMESTAMPTZ, expires_at TIMESTAMPTZ, session_id TEXT, event_kind TEXT);
CREATE TABLE cadu_reports_site_tags(id UUID PRIMARY KEY, allowed_host TEXT);
CREATE TABLE cadu_reports_flow_registry(id UUID PRIMARY KEY, client_id BIGINT, customer_id BIGINT, tag_id UUID, name TEXT, status TEXT, monitor_enabled BOOL,
    monitor_status TEXT, monitor_checked_at TIMESTAMPTZ, monitor_interval_minutes INT, monitor_down_since TIMESTAMPTZ);
CREATE TABLE cadu_reports_flow_monitor_checks(id BIGSERIAL PRIMARY KEY, flow_id UUID, client_id BIGINT, status TEXT, checked_at TIMESTAMPTZ, pages JSONB);
'''
PAGE = {'host': 'loja.com', 'path': '/orcamento', 'label': 'Orçamento', 'duration_ms': 400, 'http_status': 200}


import psycopg

_REAL_CONNECT = psycopg.connect   # the suite blocks psycopg.connect for every test; this one was captured at import


def _connect():
    """Only a database named explicitly for tests: the .env one may be production, which unit tests must never touch."""
    from psycopg.rows import dict_row
    url = os.getenv('CX_TEST_DATABASE_URL')
    if not url:
        raise RuntimeError('CX_TEST_DATABASE_URL não definida')
    return _REAL_CONNECT(url, row_factory=dict_row, connect_timeout=3, autocommit=True)


@pytest.fixture
def db():
    try:
        conn = _connect()
    except Exception as failure:
        pytest.skip(f'PostgreSQL indisponível: {type(failure).__name__}')
    schema = f'alerts_test_{uuid.uuid4().hex[:8]}'
    cur = conn.cursor()
    cur.execute(f'CREATE SCHEMA {schema}')
    cur.execute(f'SET search_path TO {schema}')
    cur.execute(STUBS)
    for name in ('add_reports_alerts_v1.sql', 'upgrade_reports_alerts_v2.sql'):
        cur.execute((ROOT / 'migrations' / name).read_text())
    cur.execute((ROOT / 'migrations' / 'upgrade_reports_alerts_v2.sql').read_text())   # replayable
    cur.execute("INSERT INTO cadu_reports_supertag_sites VALUES (%s,%s,1,'Loja','loja.com',TRUE,NULL)", (SITE, CLIENT))
    cur.execute("INSERT INTO tbl_contato_cliente VALUES (%s,'Apolo Lira','a@x.com',TRUE)", (USER,))
    cur.execute("INSERT INTO cadu_reports_supertag_events VALUES (%s,NOW()-INTERVAL '1 hour',NOW()+INTERVAL '1 day','s0','page_view')", (SITE,))
    tag, flow = str(uuid.uuid4()), str(uuid.uuid4())
    cur.execute("INSERT INTO cadu_reports_site_tags VALUES (%s,'loja.com')", (tag,))
    cur.execute("INSERT INTO cadu_reports_flow_registry VALUES (%s,%s,1,%s,'Fluxo A','published',TRUE,'offline',NOW(),5,NOW())", (flow, CLIENT, tag))
    pages = lambda status, code: json.dumps([{**PAGE, 'status': status, 'http_status': code}])
    cur.execute("INSERT INTO cadu_reports_flow_monitor_checks(flow_id,client_id,status,checked_at,pages) VALUES (%s,%s,'online',NOW(),%s),(%s,%s,'offline',NOW()-INTERVAL '5 minutes',%s)",
                (flow, CLIENT, pages('online', 200), flow, CLIENT, pages('offline', 503)))

    def rows(sql, params=()):
        cur.execute(sql, params)
        return list(cur.fetchall()) if cur.description else []
    rows.connection, rows.flow = conn, flow
    yield rows
    cur.execute(f'DROP SCHEMA {schema} CASCADE')
    conn.close()


def finding(rule, key, **extra):
    return {'rule': rule, 'subject_key': key, 'severity': 'high', 'title': f'T {key}', 'summary': 's', 'evidence': [], 'page_path': None, **extra}


@pytest.fixture
def api(db):
    app = Flask(__name__)
    app.secret_key = 't'
    bp = Blueprint('connect', __name__, url_prefix='/connect')
    alerts.register(bp)
    app.register_blueprint(bp)
    http = app.test_client()
    with http.session_transaction() as s:
        s['user_id'] = USER
    with app.app_context(), mock.patch.object(alerts, '_rows', db), mock.patch.object(alerts, 'get_db'), mock.patch.object(alerts, 'notify_opened'), \
         mock.patch.object(alerts, 'login_required_api', lambda f: f), mock.patch.object(alerts, '_write_guard'), \
         mock.patch.object(alerts, '_customer_scope', lambda selected: int(__import__('flask').request.args.get('customer_id') or 0) or None), \
         mock.patch.object(alerts, '_selection', return_value={'client_id': CLIENT, 'role': 'admin', 'user_id': USER}):
        yield http


def test_migration_is_replayable_and_dedupes_alerts_without_a_site(db):
    client_level = {'id': None, 'client_id': CLIENT}
    with mock.patch.object(alerts, '_rows', db), mock.patch.object(alerts, 'notify_opened'):
        gads = finding('gads_cap_reached', 'cap:1', channel='google_ads', kind='incident', recommendations=['Revise o teto.'])
        alerts.sync_findings(client_level, 'gads_cap_reached', [gads], NOW)
        alerts.sync_findings(client_level, 'gads_cap_reached', [{**gads, 'recommendations': ['Outra.']}], NOW)
        live = db("SELECT occurrences,recommendations,channel,kind,site_id FROM cadu_reports_alerts WHERE rule='gads_cap_reached'")
        assert len(live) == 1 and live[0]['occurrences'] == 2 and live[0]['recommendations'] == ['Outra.'] and live[0]['site_id'] is None
        alerts.sync_findings(client_level, 'gads_cap_reached', [], NOW)
        assert db("SELECT status,resolution FROM cadu_reports_alerts")[0] == {'status': 'resolved', 'resolution': 'auto'}
        alerts.sync_findings(client_level, 'gads_cap_reached', [gads], NOW)
        assert [row['status'] for row in db('SELECT status FROM cadu_reports_alerts ORDER BY first_seen_at')] == ['resolved', 'open']
    with pytest.raises(Exception):
        db("UPDATE cadu_reports_alerts SET causes='{}'::jsonb")   # the panel lists must stay arrays


def test_listing_filters_summary_and_monitors_run_on_the_real_schema(api, db):
    with mock.patch.object(alerts, 'notify_opened'):
        alerts.sync_findings({'id': SITE, 'client_id': CLIENT}, 'page_down', [finding('page_down', '/a', page_path='/a', channel='site', kind='incident',
                             impact={'value': 'erro 500', 'unit': 'text', 'label': 'página fora do ar'})], NOW)
        alerts.sync_findings({'id': SITE, 'client_id': CLIENT}, 'device_conversion_low', [finding('device_conversion_low', 'd', severity='low', channel='site', kind='opportunity')], NOW)
        alerts.sync_findings({'id': None, 'client_id': CLIENT}, 'gads_cap_reached', [finding('gads_cap_reached', 'c', channel='google_ads', kind='incident')], NOW)
    get = lambda url: api.get('/connect/api/v2/reports' + url)
    body = get('/alerts').get_json()
    assert body['total'] == 2 and {a['channel'] for a in body['alerts']} == {'site', 'google_ads'}
    assert next(a for a in body['alerts'] if a['channel'] == 'site')['impact']['value'] == 'erro 500'
    assert get('/alerts?kind=opportunity').get_json()['total'] == 1
    assert get('/alerts?channel=google_ads&severity=high&q=c').get_json()['total'] == 1
    assert get('/alerts?q=%25').get_json()['total'] == 0                    # a literal percent sign, not a wildcard
    assert get('/alerts?customer_id=2').get_json()['total'] == 1            # another advertiser: only the client-level alert remains
    summary = get('/alerts/summary').get_json()
    assert summary['tabs'] == {'incidents': 2, 'monitors': 2, 'opportunities': 1} and summary['uptime'] == 50.0
    assert get('/alerts/summary?customer_id=2').get_json()['tabs'] == {'incidents': 1, 'monitors': 0, 'opportunities': 0}
    # The "UTI": one row per monitored URL with its vital signs, and the 90-day heatmap fed by the daily summary.
    day = datetime.datetime.now(datetime.timezone.utc)
    for status in ('online', 'offline', 'online'):
        monitor.record_daily(db.connection, db.flow, [{**PAGE, 'status': status}], day)
    uti = get('/alerts/monitors').get_json()
    assert [(m['kind'], m['health']) for m in uti['monitors']] == [('collection', 'ok')]
    [url] = uti['urls']
    assert (url['path'], url['state'], url['vital'], url['http_status']) == ('/orcamento', 'online', 'attention', 200)   # one failure in the last 2 readings
    assert url['pulse'] == ['offline', 'online'] and url['uptime'] == 50.0 and len(url['heat']) == 90 and url['days_measured'] == 1
    assert url['heat'][-1] == [66.7, 400] and url['uptime_90'] == 66.7 and uti['summary'] == {'critical': 0, 'attention': 1, 'stable': 0, 'total': 1}
    assert get('/alerts/summary').get_json()['tabs']['monitors'] == 2          # 1 monitored URL (last check) + 1 Super Tag site
    assert get('/alerts/monitors?customer_id=2').get_json()['urls'] == []
    csv_body = get('/alerts/export').data.decode()
    assert csv_body.startswith('﻿Alerta,') and 'google_ads' in csv_body
    ids = [a['id'] for a in body['alerts']]
    post = lambda url, payload: api.post('/connect/api/v2/reports/alerts' + url, json=payload)
    assert post(f'/{ids[0]}/investigate', {}).status_code == 200 and post(f'/{ids[0]}/investigate', {}).status_code == 409
    assert post('/bulk', {'ids': ids + ['nao-uuid'], 'action': 'resolve'}).get_json()['done'] == 2
    assert get('/alerts/summary').get_json()['resolved_today'] == 2


def test_anomaly_causes_and_panel_data_run_on_the_real_schema(db):
    from zoneinfo import ZoneInfo
    sao_paulo = ZoneInfo('America/Sao_Paulo')
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.astimezone(sao_paulo).date()
    # 34 steady days of 200 sessions (noon, Sao Paulo) and yesterday with only 80: far below its weekday baseline.
    db("DELETE FROM cadu_reports_supertag_events")
    for ago in range(1, 35):
        sessions = 80 if ago == 1 else 200
        noon = datetime.datetime.combine(today - datetime.timedelta(days=ago), datetime.time(12), tzinfo=sao_paulo)
        db("INSERT INTO cadu_reports_supertag_events SELECT %s,%s,NOW()+INTERVAL '1 day','d'||%s||'-'||g,'page_view' FROM generate_series(1,%s) g", (SITE, noon, ago, sessions))
    # The monitor saw the site's pages down yesterday: it must show up as a cause.
    flow = db.flow
    day_before = today - datetime.timedelta(days=1)
    db("INSERT INTO cadu_reports_flow_monitor_daily VALUES (%s,'loja.com','/orcamento',%s,288,100,288*400,900)", (flow, day_before))
    site = {'id': SITE, 'client_id': CLIENT, 'allowed_host': 'loja.com', 'label': 'Loja'}
    with mock.patch.object(alerts, '_rows', db), mock.patch.object(alerts, 'get_db'), mock.patch.object(alerts, 'notify_opened'):
        alerts.evaluate_anomalies(site, now)
        [alert] = db("SELECT rule,severity,kind,impact,series,causes FROM cadu_reports_alerts WHERE rule='traffic_anomaly'")
        assert alert['kind'] == 'incident' and alert['severity'] == 'medium' and alert['impact']['value'] == -60.0
        assert alert['series']['current'][-1] == 80 and alert['series']['previous'][-1] == 200.0 and len(alert['series']['labels']) == 14
        assert any('abaixo de 95%' in cause and day_before.strftime('%d/%m') in cause for cause in alert['causes'])
        assert db("SELECT COUNT(*) AS n FROM cadu_reports_alerts WHERE rule='conversion_anomaly'")[0]['n'] == 0
        # A normal day closes it on the next evaluation.
        noon = datetime.datetime.combine(day_before, datetime.time(13), tzinfo=sao_paulo)
        db("INSERT INTO cadu_reports_supertag_events SELECT %s,%s,NOW()+INTERVAL '1 day','fix-'||g,'page_view' FROM generate_series(1,120) g", (SITE, noon))
        alerts.evaluate_anomalies(site, now)
        assert db("SELECT status,resolution FROM cadu_reports_alerts WHERE rule='traffic_anomaly'")[0] == {'status': 'resolved', 'resolution': 'auto'}
    # The URL-level cause query (normalized path, case-insensitive host) and the panel columns round-trip.
    rows = db(alerts._URL_DAILY_SQL, {'client': CLIENT, 'host': 'LOJA.com', 'path': '/orcamento', 'since': today - datetime.timedelta(days=15)})
    assert [row['checks'] for row in rows] == [288]
    finding = finding_with_panel()
    with mock.patch.object(alerts, '_rows', db), mock.patch.object(alerts, 'notify_opened'):
        alerts.sync_findings(site, 'conversion_drop', [finding], now)
    stored = db("SELECT metrics,series,impacted_urls,causes FROM cadu_reports_alerts WHERE rule='conversion_drop'")[0]
    assert stored['series']['unit'] == 'percent' and stored['metrics'][0]['change'] == -30.0 and stored['impacted_urls'][0]['path'] == '/lp' and stored['causes'] == ['c']


def finding_with_panel():
    return {**finding('conversion_drop', '/lp', channel='site', kind='incident', page_path='/lp'), 'series': {'labels': ['2026-10-06'], 'current': [1.0], 'previous': [1.4], 'unit': 'percent'},
            'metrics': [{'label': 'Taxa', 'value': 1.0, 'unit': 'percent', 'change': -30.0}], 'impacted_urls': [{'path': '/lp'}], 'causes': ['c']}


def test_settings_filters_muting_and_the_estimated_impact_run_on_the_real_schema(api, db):
    now = datetime.datetime.now(datetime.timezone.utc)
    put = lambda body: api.put('/connect/api/v2/reports/alerts/settings', json=body)
    get = lambda url: api.get('/connect/api/v2/reports' + url)
    assert put({'rules': {'page_down': {'threshold': 4, 'notify': False}}, 'conversion_value': 100}).status_code == 200
    assert put({'rules': {'page_down': {'enabled': False}}}).status_code == 200                         # a second save keeps what the first one stored
    assert put({'rules': {'page_down': {'threshold': 40}}}).status_code == 400
    assert put({'rules': {'nope': {'enabled': False}}}).status_code == 400
    settings = get('/alerts/settings').get_json()
    page_down = next(item for item in settings['rules'] if item['rule'] == 'page_down')
    assert (page_down['enabled'], page_down['notify'], page_down['tunable']['value']) == (False, False, 4) and settings['conversion_value'] == 100 and settings['can_edit'] is True
    assert db("SELECT enabled,notify,params FROM cadu_reports_alert_settings WHERE client_id=%s AND rule='page_down'", (CLIENT,))[0] == {'enabled': False, 'notify': False, 'params': {'threshold': 4}}
    assert db("SELECT params FROM cadu_reports_alert_settings WHERE client_id=%s AND rule='_client'", (CLIENT,))[0]['params'] == {'conversion_value': 100}
    assert alerts._rule_muted({'client_id': CLIENT, 'rule': 'page_down'}) is True and alerts._rule_muted({'client_id': CLIENT, 'rule': 'conversion_drop'}) is False
    assert put({'conversion_value': None}).status_code == 200 and get('/alerts/settings').get_json()['conversion_value'] is None
    assert put({'conversion_value': 100}).status_code == 200

    # Two conversion alerts lose 20 + 3.5 conversions; a rise and a closed alert do not count. At R$ 100 each the impact is R$ 2.350.
    def alert_with(rule, key, metrics, **extra):
        item = {**finding(rule, key, channel='site', kind='incident', page_path='/lp'), 'metrics': metrics, **extra}
        with mock.patch.object(alerts, '_rows', db), mock.patch.object(alerts, 'notify_opened'):
            alerts.sync_findings({'id': SITE, 'client_id': CLIENT}, rule, [item], now)
    alert_with('conversion_drop', '/lp', [{'label': 'Conversões', 'value': 40, 'previous': 60}])
    alert_with('conversion_anomaly', 'conversions', [{'label': 'Conversões', 'value': 5, 'previous': 8.5}])
    alert_with('traffic_anomaly', 'sessions', [{'label': 'Sessões', 'value': 10, 'previous': 100}])
    summary = get('/alerts/summary').get_json()
    assert summary['estimated_impact'] == {'micros': 2_350_000_000, 'currency': 'BRL', 'lost_conversions': 23.5} and summary['conversion_value_set'] is True
    assert get('/alerts/summary?customer_id=2').get_json()['estimated_impact']['micros'] == 0                  # these alerts belong to the site of advertiser 1
    assert get('/alerts/summary?customer_id=1').get_json()['estimated_impact']['micros'] == 2_350_000_000

    # Extra filters: owner and recency.
    db("UPDATE cadu_reports_alerts SET assigned_to=%s WHERE rule='conversion_drop'", (USER,))
    db("UPDATE cadu_reports_alerts SET last_seen_at=NOW()-INTERVAL '10 days' WHERE rule='conversion_anomaly'")
    titles = lambda query: sorted(item['rule'] for item in get('/alerts?' + query).get_json()['alerts'])
    assert titles('assigned=me') == ['conversion_drop'] and 'conversion_drop' not in titles('assigned=none') and len(titles('assigned=none')) == 2
    assert 'conversion_anomaly' not in titles('seen=7') and 'conversion_anomaly' in titles('seen=30') and 'conversion_anomaly' in titles('')
