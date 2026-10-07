"""Reports alert center: dedup, owner, snooze and audit trail around the pure rules in reports_alert_rules.

Evaluation runs inside the existing Reports monitor worker (see PeriodicRunner). E-mail is OFF unless
REPORTS_ALERT_EMAILS is set: sending outside the product is an explicit opt-in, and every decision to send or skip
is written to the alert's history.
"""
import csv
import io
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Response, abort, current_app, jsonify, request, session
from werkzeug.exceptions import HTTPException

from ..auth import login_required_api
from ..db import get_db
from .reports_alert_rules import (RULES, SILENT_AFTER_HOURS, campaign_page_findings, channel_entry_findings, collection_absent_findings, conversion_drop_findings,
                                  page_down_findings, tech_conversion_findings)
from .reports_page_identity import sql_normalized_path
from .reports_v1 import _customer_scope, _rows, _selection, _write_guard

NOTIFY_COOLDOWN = timedelta(hours=24)
SILENCE_CHOICES_HOURS = (1, 24, 168)
LIGHT_EVERY_SECONDS = 300
HEAVY_EVERY_SECONDS = 3600
TOP_PAGES_FOR_DROP = 10
_ACTIVE = ('open', 'acknowledged', 'investigating', 'silenced')
LIST_LIMIT = 200   # the screen shows every live alert at once; there is no paging UI
PAGE_SIZES = (10, 25, 50, LIST_LIMIT)
BULK_LIMIT = 100
CHANNELS = ('site', 'journey', 'google_ads', 'meta', 'reports')
SEVERITIES = ('high', 'medium', 'low')


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


_SEVERITY_LABELS = {'high': 'Alta', 'medium': 'Média', 'low': 'Baixa'}


def _send_alert_email(alert, recipients):
    """Modelo de marca do Reports (produto-atividade.html); True só com envio confirmado."""
    try:
        from ..services.cadu_email_connector import send_cadu_event
        base = os.environ.get('REPORTS_PUBLIC_BASE_URL', '').rstrip('/')
        details = [{'label': 'Severidade', 'value': _SEVERITY_LABELS.get(alert.get('severity'), alert.get('severity') or '—')}]
        if alert.get('page_path'):
            details.append({'label': 'Página', 'value': alert['page_path']})
        sent = True
        for email in recipients:
            result = send_cadu_event(
                product='connect', event='connect.reports_alert', template='produto-atividade.html',
                recipient=email, recipient_name='Equipe', subject=f"[Reports] {alert['title']}",
                client_id=alert.get('client_id'),
                params={'TITLE': alert['title'], 'EYEBROW': 'Alerta do Reports', 'DESCRIPTION': alert.get('summary') or '',
                        'DETAILS': details, 'CTA_LABEL': 'Abrir alertas' if base else '',
                        'CTA_URL': f'{base}/connect/app/alerts' if base else ''})
            sent = sent and bool((result or {}).get('success'))
        return sent
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Alerta %s: e-mail não enviado', alert.get('id'))
        return False


def notify_opened(alert, now):
    """One e-mail per new alert, never more than once per cooldown. Skips are logged, never silent."""
    if alert['severity'] == 'low':
        return _log(alert['id'], 'notification_skipped', detail={'reason': 'low_severity'})
    if alert.get('rule') == 'page_down':
        # The flow monitor already e-mails every outage cycle (7h-23h) and the recovery; a second e-mail would duplicate it.
        return _log(alert['id'], 'notification_skipped', detail={'reason': 'flow_monitor'})
    if not emails_enabled():
        return _log(alert['id'], 'notification_skipped', detail={'reason': 'disabled'})
    if alert.get('last_notified_at') and now - alert['last_notified_at'] < NOTIFY_COOLDOWN:
        return _log(alert['id'], 'notification_skipped', detail={'reason': 'cooldown'})
    recipients = _recipients(alert)
    if not recipients:
        return _log(alert['id'], 'notification_skipped', detail={'reason': 'no_recipients'})
    sent = _send_alert_email(alert, recipients)
    if sent:
        _rows('UPDATE cadu_reports_alerts SET last_notified_at=%s WHERE id=%s RETURNING id', (now, alert['id']))
    _log(alert['id'], 'notified' if sent else 'notification_failed', detail={'recipients': len(recipients)})


def sync_findings(site, rule, findings, now=None):
    """Make the stored alerts of (site, rule) match the findings: open new, refresh seen, auto-resolve recovered.

    site['id'] may be None for alerts that belong to the client and not to a Super Tag site (Google Ads, Meta, reports)."""
    now = now or datetime.now(timezone.utc)
    live = {row['subject_key']: row for row in _rows(
        'SELECT * FROM cadu_reports_alerts WHERE client_id=%s AND site_id IS NOT DISTINCT FROM %s::uuid AND rule=%s AND status<>\'resolved\'',
        (site['client_id'], site.get('id'), rule))}
    seen = set()
    for finding in findings:
        seen.add(finding['subject_key'])
        current = live.get(finding['subject_key'])
        impact = json.dumps(finding['impact']) if finding.get('impact') else None
        fields = (finding['severity'], finding['title'], finding['summary'], json.dumps(finding['evidence']), finding['page_path'], impact, now)
        if current:
            status = current['status']
            if status == 'silenced' and current['silenced_until'] and current['silenced_until'] <= now:
                status = 'investigating' if current.get('investigating_at') else 'open'
                _log(current['id'], 'unsilenced', detail={'reason': 'expired'})
            _rows('''UPDATE cadu_reports_alerts SET severity=%s,title=%s,summary=%s,evidence=%s::jsonb,page_path=%s,impact=%s::jsonb,last_seen_at=%s,
                occurrences=occurrences+1,status=%s,silenced_until=CASE WHEN %s='silenced' THEN silenced_until END WHERE id=%s RETURNING id''',
                  (*fields, status, status, current['id']))
            continue
        alert_id = str(uuid.uuid4())
        created = _rows('''INSERT INTO cadu_reports_alerts (id,client_id,site_id,rule,subject_key,severity,title,summary,evidence,page_path,impact,last_seen_at,channel,kind)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s) RETURNING *''',
                        (alert_id, site['client_id'], site.get('id'), rule, finding['subject_key'], finding['severity'], finding['title'],
                         finding['summary'], json.dumps(finding['evidence']), finding['page_path'], impact, now,
                         finding.get('channel') or RULES[rule]['channel'], finding.get('kind') or RULES[rule]['kind']))[0]
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


# Insights read the last 7 days of sessions with the same session table the Canais tab uses ({site} is filled in by evaluate_insights).
_INSIGHT_ENTRY_SQL = '''
    SELECT origin,path,COUNT(*)::bigint AS sessions,COUNT(*) FILTER (WHERE length=1)::bigint AS single_page FROM chan GROUP BY origin,path'''
_INSIGHT_TECH_SQL = '''
    SELECT 'device' AS kind,device AS value,COUNT(*)::bigint AS sessions,COUNT(*) FILTER (WHERE converted)::bigint AS converted
    FROM chan WHERE device<>'unknown' GROUP BY device
    UNION ALL
    SELECT 'resolution',resolution,COUNT(*)::bigint,COUNT(*) FILTER (WHERE converted)::bigint FROM chan WHERE resolution IS NOT NULL GROUP BY resolution
    UNION ALL
    SELECT 'overall','all',COUNT(*)::bigint,COUNT(*) FILTER (WHERE converted)::bigint FROM chan'''
_INSIGHT_CAMPAIGN_SQL = '''
    SELECT campaign,path,COUNT(*)::bigint AS sessions,COUNT(*) FILTER (WHERE length=1)::bigint AS single_page,
        COUNT(*) FILTER (WHERE converted)::bigint AS converted
    FROM chan WHERE campaign<>'' GROUP BY campaign,path'''


def evaluate_insights(site, now):
    """Advisory rules (severity low, never e-mailed) over the last 7 days of sessions of one site."""
    from .reports_journey import _CHANNELS_CTE, DEVICE_LABELS, ORIGIN_LABELS
    cte = _CHANNELS_CTE.replace('{site}', 'AND e.site_id=%(site)s::uuid')
    params = {'client': site['client_id'], 'since': now - timedelta(days=7), 'until': now, 'site': site['id']}
    tech = _rows(cte + _INSIGHT_TECH_SQL, params)
    sync_findings(site, 'channel_entry_exit', channel_entry_findings(_rows(cte + _INSIGHT_ENTRY_SQL, params), ORIGIN_LABELS), now)
    sync_findings(site, 'device_conversion_low', tech_conversion_findings(tech, DEVICE_LABELS), now)
    sync_findings(site, 'campaign_weak_page', campaign_page_findings(_rows(cte + _INSIGHT_CAMPAIGN_SQL, params), tech), now)


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
        # Committed first: a failing insight query must not undo the incident rules just synced.
        get_db().commit()
        try:
            evaluate_insights(site, now)
        except Exception:
            get_db().rollback()
            current_app.logger.exception('Falha ao avaliar insights do site %s', site['id'])


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
                current_app.logger.exception('Limpeza dos lotes do Google Ads falhou')
                try:
                    # With the database down, get_db() itself raises; the
                    # monitor loop must survive that too.
                    get_db().rollback()
                except Exception:
                    pass
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


def _handle_acknowledge(alert, payload, selected):
    if alert['status'] != 'open':
        abort(409, description='Só alertas abertos podem ser reconhecidos.')
    _rows("UPDATE cadu_reports_alerts SET status='acknowledged',acknowledged_by=%s,acknowledged_at=NOW() WHERE id=%s RETURNING id",
          (session['user_id'], alert['id']))
    _log(alert['id'], 'acknowledged', session['user_id'])


def _handle_assign(alert, payload, selected):
    mine = payload.get('assign') is True
    if not mine and payload.get('assign') is not False:
        abort(400, description='Informe assign verdadeiro (assumir) ou falso (liberar).')
    owner = session['user_id'] if mine else None
    _rows('UPDATE cadu_reports_alerts SET assigned_to=%s WHERE id=%s RETURNING id', (owner, alert['id']))
    _log(alert['id'], 'assigned' if mine else 'unassigned', session['user_id'])


def _handle_silence(alert, payload, selected):
    # Permanent: silenced with no end date ("não recomendar mais"). It still auto-resolves when the problem goes away.
    if payload.get('permanent') is True:
        _rows("UPDATE cadu_reports_alerts SET status='silenced',silenced_until=NULL WHERE id=%s RETURNING id", (alert['id'],))
        _log(alert['id'], 'silenced', session['user_id'], {'permanent': True})
        return
    hours = payload.get('hours')
    if hours not in SILENCE_CHOICES_HOURS:
        abort(400, description='Escolha silenciar por 1 hora, 24 horas, 7 dias ou sem prazo.')
    until = datetime.now(timezone.utc) + timedelta(hours=hours)
    _rows("UPDATE cadu_reports_alerts SET status='silenced',silenced_until=%s WHERE id=%s RETURNING id", (until, alert['id']))
    _log(alert['id'], 'silenced', session['user_id'], {'hours': hours})


def _handle_unsilence(alert, payload, selected):
    if alert['status'] != 'silenced':
        abort(409, description='Este alerta não está silenciado.')
    # An alert someone was already investigating goes back to that state, not to untouched.
    back = 'investigating' if alert.get('investigating_at') else 'open'
    _rows("UPDATE cadu_reports_alerts SET status=%s,silenced_until=NULL WHERE id=%s RETURNING id", (back, alert['id']))
    _log(alert['id'], 'unsilenced', session['user_id'], {'reason': 'manual'})


def _handle_investigate(alert, payload, selected):
    """Someone is looking at it: the alert keeps its owner, or the person who started the investigation becomes it."""
    if alert['status'] not in ('open', 'acknowledged'):
        abort(409, description='Só alertas abertos ou reconhecidos podem entrar em investigação.')
    _rows("UPDATE cadu_reports_alerts SET status='investigating',investigating_at=NOW(),assigned_to=COALESCE(assigned_to,%s) WHERE id=%s RETURNING id",
          (session['user_id'], alert['id']))
    _log(alert['id'], 'investigating', session['user_id'])


def _handle_resolve(alert, payload, selected):
    """Manual close. If the condition is still true, the next evaluation opens a new alert for it."""
    _rows("UPDATE cadu_reports_alerts SET status='resolved',resolution='manual',resolved_at=NOW(),silenced_until=NULL WHERE id=%s RETURNING id", (alert['id'],))
    _log(alert['id'], 'resolved', session['user_id'], {'resolution': 'manual'})


_ACTIONS = {'acknowledge': _handle_acknowledge, 'assign': _handle_assign, 'silence': _handle_silence, 'unsilence': _handle_unsilence,
            'investigate': _handle_investigate, 'resolve': _handle_resolve}
_BULK_ACTIONS = ('acknowledge', 'investigate', 'resolve')

_LIST_COLUMNS = '''a.id,a.rule,a.channel,a.kind,a.severity,a.status,a.resolution,a.title,a.summary,a.evidence,a.impact,a.page_path,a.occurrences,
    a.assigned_to,u.nome_completo AS assigned_name,a.acknowledged_at,a.investigating_at,a.silenced_until,a.first_seen_at,a.last_seen_at,a.resolved_at,
    a.site_id,s.label AS site_label,s.allowed_host,a.metrics,a.series,a.impacted_urls,a.causes,a.recommendations'''
_STATUS_WHERE = {'active': "a.status<>'resolved'", 'investigating': "a.status='investigating'", 'resolved': "a.status='resolved'", 'all': 'TRUE'}
_FROM = '''FROM cadu_reports_alerts a LEFT JOIN cadu_reports_supertag_sites s ON s.id=a.site_id
    LEFT JOIN tbl_contato_cliente u ON u.id_contato_cliente=a.assigned_to'''
_ORDER = "ORDER BY CASE a.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,a.last_seen_at DESC,a.id"
_UPTIME_SQL = '''
    SELECT COUNT(*) FILTER (WHERE p->>'status'='online' AND c.checked_at>=%(now)s-INTERVAL '7 days') AS up_now,
           COUNT(*) FILTER (WHERE c.checked_at>=%(now)s-INTERVAL '7 days') AS all_now,
           COUNT(*) FILTER (WHERE p->>'status'='online' AND c.checked_at<%(now)s-INTERVAL '7 days') AS up_before,
           COUNT(*) FILTER (WHERE c.checked_at<%(now)s-INTERVAL '7 days') AS all_before
    FROM cadu_reports_flow_monitor_checks c CROSS JOIN LATERAL jsonb_array_elements(c.pages) p
    WHERE c.client_id=%(client)s AND c.checked_at>=%(now)s-INTERVAL '14 days' '''
_COUNTS_SQL = '''
    SELECT COUNT(*) FILTER (WHERE kind='incident' AND status<>'resolved') AS incidents,
           COUNT(*) FILTER (WHERE kind='incident' AND status='investigating') AS investigating,
           COUNT(*) FILTER (WHERE kind='opportunity' AND status<>'resolved') AS opportunities,
           COUNT(*) FILTER (WHERE kind='incident' AND first_seen_at>=%(now)s-INTERVAL '7 days') AS opened_now,
           COUNT(*) FILTER (WHERE kind='incident' AND first_seen_at<%(now)s-INTERVAL '7 days' AND first_seen_at>=%(now)s-INTERVAL '14 days') AS opened_before,
           COUNT(*) FILTER (WHERE kind='incident' AND resolved_at>=%(day)s) AS resolved_today,
           COUNT(*) FILTER (WHERE kind='incident' AND resolved_at>=%(day)s-INTERVAL '1 day' AND resolved_at<%(day)s) AS resolved_yesterday
    FROM cadu_reports_alerts WHERE client_id=%(client)s'''
_MONITOR_COUNT_SQL = '''
    SELECT (SELECT COUNT(*) FROM cadu_reports_flow_registry WHERE client_id=%(c)s AND status='published' AND monitor_enabled=TRUE)
         + (SELECT COUNT(*) FROM cadu_reports_supertag_sites WHERE client_id=%(c)s AND enabled=TRUE AND revoked_at IS NULL) AS n'''
_MONITOR_FLOWS_SQL = '''
    SELECT f.id::text AS id,f.name,t.allowed_host,f.monitor_status,f.monitor_checked_at,f.monitor_interval_minutes,f.monitor_down_since
    FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
    WHERE f.client_id=%s AND f.status='published' AND f.monitor_enabled=TRUE ORDER BY lower(f.name),f.id'''
_MONITOR_SITES_SQL = '''
    SELECT s.id::text AS id,s.label,s.allowed_host,MAX(e.occurred_at) AS last_event_at,
        COUNT(e.*) FILTER (WHERE e.occurred_at>=NOW()-INTERVAL '24 hours') AS events_24h
    FROM cadu_reports_supertag_sites s LEFT JOIN cadu_reports_supertag_events e ON e.site_id=s.id AND e.expires_at>NOW()
    WHERE s.client_id=%s AND s.enabled=TRUE AND s.revoked_at IS NULL GROUP BY s.id ORDER BY lower(s.label),s.id'''
_FLOW_HEALTH = {'online': 'ok', 'degraded': 'warning', 'offline': 'down'}
_HEALTH_ORDER = {'down': 0, 'warning': 1, 'unknown': 2, 'ok': 3}


def _pct(part, whole):
    return round(100 * int(part) / int(whole), 1) if whole else None


def _filters(selected):
    """WHERE clause and params shared by the list and the CSV export."""
    kind, status = request.args.get('kind', 'incident'), request.args.get('status', 'active')
    channel, severity = request.args.get('channel', ''), request.args.get('severity', '')
    if kind not in ('incident', 'opportunity') or status not in _STATUS_WHERE:
        abort(400, description='Filtro inválido.')
    if (channel and channel not in CHANNELS) or (severity and severity not in SEVERITIES):
        abort(400, description='Filtro inválido.')
    customer = _customer_scope(selected)
    # Alerts without a site belong to the client as a whole (Google Ads, Meta, reports), so a customer filter never hides them.
    where = ['a.client_id=%s', 'a.kind=%s', _STATUS_WHERE[status], '(%s::bigint IS NULL OR a.site_id IS NULL OR s.customer_id=%s)']
    params = [selected['client_id'], kind, customer, customer]
    if channel:
        where.append('a.channel=%s')
        params.append(channel)
    if severity:
        where.append('a.severity=%s')
        params.append(severity)
    text = request.args.get('q', '').strip()[:80]
    if text:
        like = '%' + text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        where.append("(a.title ILIKE %s OR a.summary ILIKE %s OR COALESCE(a.page_path,'') ILIKE %s OR COALESCE(s.label,'') ILIKE %s)")
        params.extend([like] * 4)
    return ' AND '.join(where), params


def _cell(value):
    """CSV cells that start with a formula character are prefixed so a spreadsheet never runs them."""
    text = str(value if value is not None else '')
    return "'" + text if text[:1] in ('=', '+', '-', '@', '\t', '\r') else text


def register(bp):
    @bp.get('/api/v2/reports/alerts')
    @login_required_api
    def reports_alerts():
        selected = _selection()
        where, params = _filters(selected)
        try:
            per_page = int(request.args.get('per_page', LIST_LIMIT))
            page = max(int(request.args.get('page', 1)), 1)
        except ValueError:
            abort(400, description='Paginação inválida.')
        if per_page not in PAGE_SIZES:
            abort(400, description='Itens por página inválido.')
        total = _rows(f'SELECT COUNT(*) AS n {_FROM} WHERE {where}', params)[0]['n']
        rows = _rows(f'SELECT {_LIST_COLUMNS} {_FROM} WHERE {where} {_ORDER} LIMIT %s OFFSET %s', (*params, per_page, (page - 1) * per_page))
        return jsonify(alerts=rows, total=int(total), page=page, per_page=per_page, page_sizes=list(PAGE_SIZES), user_id=selected['user_id'],
                       emails_enabled=emails_enabled(), silence_choices=list(SILENCE_CHOICES_HOURS),
                       rules=[{'rule': key, **value} for key, value in RULES.items()])

    @bp.get('/api/v2/reports/alerts/summary')
    @login_required_api
    def reports_alerts_summary():
        selected = _selection()
        now = datetime.now(timezone.utc)
        today = now.astimezone(ZoneInfo('America/Sao_Paulo')).replace(hour=0, minute=0, second=0, microsecond=0)
        counts = _rows(_COUNTS_SQL, {'client': selected['client_id'], 'now': now, 'day': today})[0]
        uptime = _rows(_UPTIME_SQL, {'client': selected['client_id'], 'now': now})[0]
        monitors = _rows(_MONITOR_COUNT_SQL, {'c': selected['client_id']})[0]['n']
        resolved_today, resolved_yesterday = int(counts['resolved_today']), int(counts['resolved_yesterday'])
        uptime_now, uptime_before = _pct(uptime['up_now'], uptime['all_now']), _pct(uptime['up_before'], uptime['all_before'])
        return jsonify(
            tabs={'incidents': int(counts['incidents']), 'monitors': int(monitors), 'opportunities': int(counts['opportunities'])},
            active=int(counts['incidents']), opened_delta=int(counts['opened_now']) - int(counts['opened_before']),
            investigating=int(counts['investigating']),
            resolved_today=resolved_today, resolved_today_change=_pct(resolved_today - resolved_yesterday, resolved_yesterday),
            uptime=uptime_now, uptime_change=round(uptime_now - uptime_before, 1) if uptime_now is not None and uptime_before is not None else None,
            # Needs a value per conversion goal; until the flow goals carry one the KPI stays hidden instead of showing an invented figure.
            estimated_impact=None)

    @bp.get('/api/v2/reports/alerts/monitors')
    @login_required_api
    def reports_alert_monitors():
        selected = _selection()
        now = datetime.now(timezone.utc)
        items = [{'kind': 'url', 'id': row['id'], 'name': row['name'] or row['allowed_host'], 'target': row['allowed_host'],
                  'health': _FLOW_HEALTH.get(row['monitor_status'], 'unknown'), 'last_checked_at': row['monitor_checked_at'],
                  'every_minutes': row['monitor_interval_minutes'], 'down_since': row['monitor_down_since']}
                 for row in _rows(_MONITOR_FLOWS_SQL, (selected['client_id'],))]
        for row in _rows(_MONITOR_SITES_SQL, (selected['client_id'],)):
            hours = (now - row['last_event_at']).total_seconds() / 3600 if row['last_event_at'] else None
            health = 'unknown' if hours is None else 'warning' if hours >= SILENT_AFTER_HOURS else 'ok'
            items.append({'kind': 'collection', 'id': row['id'], 'name': row['label'], 'target': row['allowed_host'], 'health': health,
                          'last_checked_at': row['last_event_at'], 'events_24h': int(row['events_24h'] or 0)})
        return jsonify(monitors=sorted(items, key=lambda item: _HEALTH_ORDER[item['health']]), emails_enabled=emails_enabled(),
                       rules=[{'rule': key, **value} for key, value in RULES.items()])

    @bp.get('/api/v2/reports/alerts/export')
    @login_required_api
    def reports_alerts_export():
        selected = _selection()
        where, params = _filters(selected)
        rows = _rows(f'SELECT {_LIST_COLUMNS} {_FROM} WHERE {where} {_ORDER} LIMIT 5000', params)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(['Alerta', 'Resumo', 'Canal', 'Severidade', 'Status', 'Responsável', 'Página', 'Primeira ocorrência', 'Última ocorrência'])
        for row in rows:
            writer.writerow([_cell(row['title']), _cell(row['summary']), row['channel'], row['severity'], row['status'], _cell(row['assigned_name']),
                             _cell(row['page_path']), row['first_seen_at'], row['last_seen_at']])
        return Response('﻿' + out.getvalue(), mimetype='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="alertas.csv"'})

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

    def _route(action):
        def view(alert_id):
            return _act(alert_id, _ACTIONS[action])
        view.__name__ = f'reports_alert_{action}'
        return login_required_api(view)

    for action in _ACTIONS:
        bp.add_url_rule(f'/api/v2/reports/alerts/<alert_id>/{action}', view_func=_route(action), methods=['POST'])

    @bp.post('/api/v2/reports/alerts/bulk')
    @login_required_api
    def reports_alerts_bulk():
        payload = request.get_json(silent=True)
        payload = payload if isinstance(payload, dict) else {}
        selected = _selection(payload)
        _write_guard(selected)
        ids, action = payload.get('ids'), payload.get('action')
        if action not in _BULK_ACTIONS:
            abort(400, description='Ação em lote inválida.')
        if not isinstance(ids, list) or not ids or len(ids) > BULK_LIMIT or not all(isinstance(item, str) for item in ids):
            abort(400, description=f'Escolha de 1 a {BULK_LIMIT} alertas.')
        done = skipped = 0
        for alert_id in dict.fromkeys(ids):
            try:
                alert = _alert_for(selected, alert_id)
                if alert['status'] == 'resolved':
                    raise ValueError
                _ACTIONS[action](alert, payload, selected)
                done += 1
            except (HTTPException, ValueError):
                skipped += 1
        get_db().commit()
        return jsonify(ok=True, done=done, skipped=skipped)
