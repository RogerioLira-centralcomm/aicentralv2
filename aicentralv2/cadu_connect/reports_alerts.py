"""Reports alert center: dedup, owner, snooze and audit trail around the pure rules in reports_alert_rules.

Evaluation runs inside the existing Reports monitor worker (see PeriodicRunner). E-mail is OFF unless
REPORTS_ALERT_EMAILS is set: sending outside the product is an explicit opt-in, and every decision to send or skip
is written to the alert's history.
"""
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

from flask import abort, current_app, jsonify, request, session

from ..auth import login_required_api
from ..db import get_db
from .reports_alert_rules import RULES, collection_absent_findings, conversion_drop_findings, page_down_findings
from .reports_page_identity import sql_normalized_path
from .reports_v1 import _rows, _selection, _write_guard

NOTIFY_COOLDOWN = timedelta(hours=24)
SILENCE_CHOICES_HOURS = (1, 24, 168)
LIGHT_EVERY_SECONDS = 300
HEAVY_EVERY_SECONDS = 3600
TOP_PAGES_FOR_DROP = 10
_ACTIVE = ('open', 'acknowledged', 'silenced')


def _log(alert_id, kind, actor=None, detail=None):
    _rows('INSERT INTO cadu_reports_alert_events (alert_id,kind,actor_user_id,detail) VALUES (%s,%s,%s,%s::jsonb) RETURNING id',
          (alert_id, kind, actor, json.dumps(detail or {}, default=str)))


def emails_enabled():
    return os.environ.get('REPORTS_ALERT_EMAILS', '').lower() in ('1', 'true', 'yes')


def _recipients(alert):
    if alert.get('assigned_to'):
        rows = _rows('SELECT email FROM tbl_contato_cliente WHERE id_contato_cliente=%s AND status=TRUE', (alert['assigned_to'],))
    else:
        rows = _rows('''SELECT u.email FROM cadu_reports_client_memberships m JOIN tbl_contato_cliente u ON u.id_contato_cliente=m.user_id
            WHERE m.client_id=%s AND m.role='admin' AND m.revoked_at IS NULL AND u.status=TRUE''', (alert['client_id'],))
    return sorted({row['email'] for row in rows if row.get('email')})


def notify_opened(alert, now):
    """One e-mail per new alert, never more than once per cooldown. Skips are logged, never silent."""
    if alert['severity'] == 'low':
        return _log(alert['id'], 'notification_skipped', detail={'reason': 'low_severity'})
    if not emails_enabled():
        return _log(alert['id'], 'notification_skipped', detail={'reason': 'disabled'})
    if alert.get('last_notified_at') and now - alert['last_notified_at'] < NOTIFY_COOLDOWN:
        return _log(alert['id'], 'notification_skipped', detail={'reason': 'cooldown'})
    recipients = _recipients(alert)
    if not recipients:
        return _log(alert['id'], 'notification_skipped', detail={'reason': 'no_recipients'})
    from ..email_service import send_email
    base = os.environ.get('REPORTS_PUBLIC_BASE_URL', '').rstrip('/')
    link = f'\n\nAbrir: {base}/connect/app/alerts' if base else ''
    sent = send_email(f"[Reports] {alert['title']}", recipients, text_body=f"{alert['summary']}{link}")
    if sent:
        _rows('UPDATE cadu_reports_alerts SET last_notified_at=%s WHERE id=%s RETURNING id', (now, alert['id']))
    _log(alert['id'], 'notified' if sent else 'notification_failed', detail={'recipients': len(recipients)})


def sync_findings(site, rule, findings, now=None):
    """Make the stored alerts of (site, rule) match the findings: open new, refresh seen, auto-resolve recovered."""
    now = now or datetime.now(timezone.utc)
    live = {row['subject_key']: row for row in _rows(
        'SELECT * FROM cadu_reports_alerts WHERE site_id=%s AND rule=%s AND status<>\'resolved\'', (site['id'], rule))}
    seen = set()
    for finding in findings:
        seen.add(finding['subject_key'])
        current = live.get(finding['subject_key'])
        fields = (finding['severity'], finding['title'], finding['summary'], json.dumps(finding['evidence']), finding['page_path'], now)
        if current:
            status = current['status']
            if status == 'silenced' and current['silenced_until'] and current['silenced_until'] <= now:
                status = 'open'
                _log(current['id'], 'unsilenced', detail={'reason': 'expired'})
            _rows('''UPDATE cadu_reports_alerts SET severity=%s,title=%s,summary=%s,evidence=%s::jsonb,page_path=%s,last_seen_at=%s,
                occurrences=occurrences+1,status=%s,silenced_until=CASE WHEN %s='silenced' THEN silenced_until END WHERE id=%s RETURNING id''',
                  (*fields, status, status, current['id']))
            continue
        alert_id = str(uuid.uuid4())
        created = _rows('''INSERT INTO cadu_reports_alerts (id,client_id,site_id,rule,subject_key,severity,title,summary,evidence,page_path,last_seen_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s) RETURNING *''',
                        (alert_id, site['client_id'], site['id'], rule, finding['subject_key'], finding['severity'], finding['title'],
                         finding['summary'], json.dumps(finding['evidence']), finding['page_path'], now))[0]
        _log(alert_id, 'opened', detail={'summary': finding['summary']})
        notify_opened(created, now)
    for subject, current in live.items():
        if subject in seen:
            continue
        _rows('''UPDATE cadu_reports_alerts SET status='resolved',resolution='auto',resolved_at=%s,silenced_until=NULL WHERE id=%s RETURNING id''',
              (now, current['id']))
        _log(current['id'], 'resolved', detail={'resolution': 'auto'})


_CHECKS_SQL = '''
    SELECT c.checked_at,c.pages FROM cadu_reports_flow_monitor_checks c JOIN cadu_reports_flow_registry f ON f.id=c.flow_id
    WHERE f.site_id=%s AND f.client_id=%s ORDER BY c.checked_at DESC LIMIT 40'''
_SILENCE_SQL = '''
    WITH last AS (SELECT MAX(occurred_at) AS at FROM cadu_reports_supertag_events WHERE site_id=%(site)s AND expires_at>NOW())
    SELECT last.at AS last_event,EXTRACT(EPOCH FROM (NOW()-last.at))/3600 AS hours,
        (SELECT COUNT(*) FROM cadu_reports_supertag_events e WHERE e.site_id=%(site)s AND e.expires_at>NOW()
            AND e.occurred_at>last.at-INTERVAL '7 days') AS baseline
    FROM last'''
_TOP_PAGES_SQL = f'''
    SELECT {sql_normalized_path('page_path')} AS path,COUNT(*) AS views FROM cadu_reports_supertag_events
    WHERE site_id=%(site)s AND expires_at>NOW() AND event_kind='page_view' AND occurred_at>=NOW()-INTERVAL '7 days'
    GROUP BY 1 ORDER BY views DESC LIMIT {TOP_PAGES_FOR_DROP}'''


def evaluate_site(site, heavy=False, now=None):
    now = now or datetime.now(timezone.utc)
    checks = _rows(_CHECKS_SQL, (site['id'], site['client_id']))
    sync_findings(site, 'page_down', page_down_findings(checks), now)
    silence = _rows(_SILENCE_SQL, {'site': site['id']})[0]
    hours = float(silence['hours']) if silence['hours'] is not None else None
    sync_findings(site, 'collection_absent', collection_absent_findings(site['label'], int(silence['baseline'] or 0), hours), now)
    if heavy:
        from .reports_pages import window_metrics
        pages = []
        for row in _rows(_TOP_PAGES_SQL, {'site': site['id']}):
            current = window_metrics(site['id'], row['path'], now - timedelta(days=7), now)[0]
            previous = window_metrics(site['id'], row['path'], now - timedelta(days=14), now - timedelta(days=7))[0]
            pages.append({'path': row['path'], 'current': current, 'previous': previous})
        sync_findings(site, 'conversion_drop', conversion_drop_findings(pages), now)


def evaluate_all(heavy=False):
    sites = _rows('SELECT id::text AS id,client_id,label,allowed_host FROM cadu_reports_supertag_sites WHERE enabled=TRUE AND revoked_at IS NULL')
    for site in sites:
        try:
            evaluate_site(site, heavy)
            get_db().commit()
        except Exception:
            get_db().rollback()
            current_app.logger.exception('Falha ao avaliar alertas do site %s', site['id'])
    return len(sites)


class PeriodicRunner:
    """Called from the monitor loop; keeps its own clocks so alerts never slow or break availability checks."""

    def __init__(self, light=LIGHT_EVERY_SECONDS, heavy=HEAVY_EVERY_SECONDS, clock=time.monotonic):
        self.light, self.heavy, self.clock = light, heavy, clock
        self.last_light = self.last_heavy = None

    def tick(self):
        now = self.clock()
        if self.last_light is not None and now - self.last_light < self.light:
            return False
        heavy = self.last_heavy is None or now - self.last_heavy >= self.heavy
        self.last_light = now
        if heavy:
            self.last_heavy = now
        try:
            evaluate_all(heavy=heavy)
        except Exception:
            current_app.logger.exception('Ciclo de alertas do Reports falhou')
        if heavy:
            try:
                from .reports_ingest_v2 import prune_chunk_runs
                prune_chunk_runs()
            except Exception:
                get_db().rollback()
                current_app.logger.exception('Limpeza dos lotes do Google Ads falhou')
        return True


# ---------------------------------------------------------------------------------------------- routes

def _alert_for(selected, alert_id):
    try:
        uuid.UUID(alert_id)
    except ValueError:
        abort(404)
    rows = _rows('SELECT * FROM cadu_reports_alerts WHERE id=%s AND client_id=%s', (alert_id, selected['client_id']))
    if not rows:
        abort(404)
    return rows[0]


def register(bp):
    @bp.get('/api/v2/reports/alerts')
    @login_required_api
    def reports_alerts():
        selected = _selection()
        status = request.args.get('status', 'active')
        if status not in ('active', 'resolved', 'all'):
            abort(400, description='Estado inválido.')
        where = {'active': "a.status<>'resolved'", 'resolved': "a.status='resolved'", 'all': 'TRUE'}[status]
        rows = _rows(f'''SELECT a.id,a.rule,a.severity,a.status,a.resolution,a.title,a.summary,a.evidence,a.page_path,a.occurrences,
                a.assigned_to,u.nome_completo AS assigned_name,a.acknowledged_at,a.silenced_until,a.first_seen_at,a.last_seen_at,a.resolved_at,
                a.site_id,s.label AS site_label,s.allowed_host
            FROM cadu_reports_alerts a JOIN cadu_reports_supertag_sites s ON s.id=a.site_id
            LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente=a.assigned_to
            WHERE a.client_id=%s AND {where}
            ORDER BY CASE a.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,a.last_seen_at DESC LIMIT 200''', (selected['client_id'],))
        return jsonify(alerts=rows, user_id=selected['user_id'], emails_enabled=emails_enabled(), silence_choices=list(SILENCE_CHOICES_HOURS),
                       rules=[{'rule': key, **value} for key, value in RULES.items()])

    @bp.get('/api/v2/reports/alerts/<alert_id>/events')
    @login_required_api
    def reports_alert_events(alert_id):
        selected = _selection()
        _alert_for(selected, alert_id)
        return jsonify(events=_rows('''SELECT e.kind,e.detail,e.created_at,u.nome_completo AS actor_name FROM cadu_reports_alert_events e
            LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente=e.actor_user_id WHERE e.alert_id=%s ORDER BY e.created_at DESC,e.id DESC LIMIT 100''',
                                    (alert_id,)))

    def _act(alert_id, handler):
        payload = request.get_json(silent=True)
        payload = payload if isinstance(payload, dict) else {}
        selected = _selection(payload)
        _write_guard(selected)
        alert = _alert_for(selected, alert_id)
        if alert['status'] == 'resolved':
            abort(409, description='Este alerta já foi resolvido.')
        handler(alert, payload, selected)
        get_db().commit()
        return jsonify(ok=True)

    @bp.post('/api/v2/reports/alerts/<alert_id>/acknowledge')
    @login_required_api
    def reports_alert_acknowledge(alert_id):
        def handler(alert, payload, selected):
            if alert['status'] != 'open':
                abort(409, description='Só alertas abertos podem ser reconhecidos.')
            _rows("UPDATE cadu_reports_alerts SET status='acknowledged',acknowledged_by=%s,acknowledged_at=NOW() WHERE id=%s RETURNING id",
                  (session['user_id'], alert['id']))
            _log(alert['id'], 'acknowledged', session['user_id'])
        return _act(alert_id, handler)

    @bp.post('/api/v2/reports/alerts/<alert_id>/assign')
    @login_required_api
    def reports_alert_assign(alert_id):
        def handler(alert, payload, selected):
            mine = payload.get('assign') is True
            if not mine and payload.get('assign') is not False:
                abort(400, description='Informe assign verdadeiro (assumir) ou falso (liberar).')
            owner = session['user_id'] if mine else None
            _rows('UPDATE cadu_reports_alerts SET assigned_to=%s WHERE id=%s RETURNING id', (owner, alert['id']))
            _log(alert['id'], 'assigned' if mine else 'unassigned', session['user_id'])
        return _act(alert_id, handler)

    @bp.post('/api/v2/reports/alerts/<alert_id>/silence')
    @login_required_api
    def reports_alert_silence(alert_id):
        def handler(alert, payload, selected):
            hours = payload.get('hours')
            if hours not in SILENCE_CHOICES_HOURS:
                abort(400, description='Escolha silenciar por 1 hora, 24 horas ou 7 dias.')
            until = datetime.now(timezone.utc) + timedelta(hours=hours)
            _rows("UPDATE cadu_reports_alerts SET status='silenced',silenced_until=%s WHERE id=%s RETURNING id", (until, alert['id']))
            _log(alert['id'], 'silenced', session['user_id'], {'hours': hours})
        return _act(alert_id, handler)

    @bp.post('/api/v2/reports/alerts/<alert_id>/unsilence')
    @login_required_api
    def reports_alert_unsilence(alert_id):
        def handler(alert, payload, selected):
            if alert['status'] != 'silenced':
                abort(409, description='Este alerta não está silenciado.')
            _rows("UPDATE cadu_reports_alerts SET status='open',silenced_until=NULL WHERE id=%s RETURNING id", (alert['id'],))
            _log(alert['id'], 'unsilenced', session['user_id'], {'reason': 'manual'})
        return _act(alert_id, handler)
