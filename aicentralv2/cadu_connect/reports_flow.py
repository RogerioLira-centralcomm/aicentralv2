"""First-party Funnel Flow collection and URL-step mapping for Reports V1."""
import json
import re
import secrets
import uuid
from urllib.parse import urlparse

from flask import abort, jsonify, request, session

from ..auth import login_required_api
from ..db import get_db
from .reports_v1 import _rows, _selection, _write_guard

MAX_TAG_EVENTS_PER_MINUTE = 1200


def _host(value):
    value = str(value or '').strip().lower()
    if '://' in value:
        value = urlparse(value).hostname or ''
    value = value.rstrip('.')
    if not re.fullmatch(r'(?=.{1,253}$)[a-z0-9][a-z0-9.-]*[a-z0-9]', value) or '..' in value:
        abort(400, description='Informe um domínio válido, sem caminho.')
    return value


def _uuid(value, field):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        abort(400, description=f'{field} inválido.')


def _short(value, limit):
    return value[:limit] if isinstance(value, str) else ''


def _tag_for_client(tag_id, selected):
    found = _rows('''SELECT id,label,allowed_host,public_key,created_at,revoked_at
        FROM cadu_reports_site_tags WHERE id=%s AND organization_id=%s AND client_id=%s''',
        (_uuid(tag_id, 'Tag'), selected['organization_id'], selected['client_id']))
    if not found:
        abort(404)
    return found[0]


def _campaign_match(tag, attribution, matched_step):
    """Use only unique, explicit IDs or names; a shared landing page is not evidence."""
    params = (tag['organization_id'], tag['client_id'])
    if attribution.get('utm_id'):
        candidates = _rows('''SELECT id FROM cadu_reports_campaigns
            WHERE organization_id=%s AND client_id=%s AND external_id=%s LIMIT 2''',
            (*params, attribution['utm_id']))
        if len(candidates) == 1:
            return candidates[0]['id'], 'utm_id'
    if attribution.get('utm_campaign'):
        candidates = _rows('''SELECT id FROM cadu_reports_campaigns
            WHERE organization_id=%s AND client_id=%s AND lower(name)=lower(%s) LIMIT 2''',
            (*params, attribution['utm_campaign']))
        if len(candidates) == 1:
            return candidates[0]['id'], 'utm_campaign'
    if matched_step and matched_step.get('campaign_id'):
        return matched_step['campaign_id'], 'step'
    return None, None


def register(bp):
    @bp.get('/api/v1/reports/flow')
    @login_required_api
    def reports_flow():
        selected = _selection()
        params = (selected['organization_id'], selected['client_id'])
        try:
            days = int(request.args.get('days', 30))
        except (ValueError, TypeError):
            abort(400, description='Período inválido.')
        if days not in (7, 30, 90):
            abort(400, description='Período inválido.')
        scope_params = [*params, days]
        event_filter = ''
        conversion_filter = ''
        for field, column in (('account_id', 'a.id'), ('campaign_id', 'e.campaign_id')):
            value = request.args.get(field, '').strip()
            if value:
                try:
                    number = int(value)
                except ValueError:
                    abort(400, description=f'{field} inválido.')
                if number < 1:
                    abort(400, description=f'{field} inválido.')
                event_filter += f' AND {column}=%s'
                conversion_filter += f" AND {'a.id' if field == 'account_id' else 'x.campaign_id'}=%s"
                scope_params.append(number)
        platform = request.args.get('platform', '').strip()
        if platform:
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', platform):
                abort(400, description='Plataforma inválida.')
            event_filter += ' AND a.platform=%s'
            conversion_filter += ' AND a.platform=%s'
            scope_params.append(platform)
        scoped_events = '''WITH selected_events AS (
            SELECT e.* FROM cadu_reports_flow_events e
            LEFT JOIN cadu_reports_campaigns c ON c.id=e.campaign_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
            WHERE e.organization_id=%s AND e.client_id=%s
                AND e.occurred_at > NOW() - (%s * INTERVAL '1 day')''' + event_filter + ') '
        tags = _rows('''SELECT id,label,allowed_host,public_key,created_at,revoked_at
            FROM cadu_reports_site_tags WHERE organization_id=%s AND client_id=%s ORDER BY created_at DESC''', params)
        steps = _rows('''SELECT s.id,s.tag_id,s.name,s.path_prefix,s.step_kind,s.campaign_id,s.position,
            s.is_active,s.archived_at,
            c.name AS campaign_name FROM cadu_reports_flow_steps s
            LEFT JOIN cadu_reports_campaigns c ON c.id=s.campaign_id
            WHERE s.organization_id=%s AND s.client_id=%s AND s.is_active=TRUE
            ORDER BY s.position,s.id''', params)
        activity = _rows(scoped_events + '''SELECT e.tag_id,e.page_path,
            COUNT(*) FILTER (WHERE e.event_kind IN ('page_view','conversion')) AS views,
            COUNT(DISTINCT e.visitor_id) FILTER (WHERE e.event_kind IN ('page_view','conversion')) AS visitors,
            COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind IN ('page_view','conversion','heartbeat')
                AND e.occurred_at > NOW() - INTERVAL '90 seconds') AS online,
            COUNT(DISTINCT e.visitor_id) FILTER (WHERE e.event_kind='conversion') AS conversions
            FROM selected_events e
            GROUP BY e.tag_id,e.page_path ORDER BY views DESC LIMIT 100''', tuple(scope_params))
        totals = _rows(scoped_events + '''SELECT
            COUNT(DISTINCT session_id) FILTER (WHERE event_kind IN ('page_view','conversion','heartbeat')
                AND occurred_at > NOW() - INTERVAL '90 seconds') AS online,
            COUNT(DISTINCT visitor_id) FILTER (WHERE event_kind='conversion') AS conversions
            FROM selected_events''', tuple(scope_params))[0]
        progression = _rows(scoped_events + ''' , first_step AS (
            SELECT session_id,step_id,MIN(occurred_at) AS first_at
            FROM selected_events WHERE step_id IS NOT NULL
                AND event_kind IN ('page_view','conversion')
            GROUP BY session_id,step_id
        ), ordered AS (
            SELECT id,tag_id,LAG(id) OVER (PARTITION BY tag_id ORDER BY position,id) AS previous_id
            FROM cadu_reports_flow_steps WHERE organization_id=%s AND client_id=%s AND is_active=TRUE
        )
        SELECT o.id AS step_id,COUNT(DISTINCT f.session_id) AS reached,
            COUNT(DISTINCT f.session_id) FILTER (
                WHERE o.previous_id IS NULL OR p.first_at <= f.first_at) AS progressed
        FROM ordered o LEFT JOIN first_step f ON f.step_id=o.id
        LEFT JOIN first_step p ON p.step_id=o.previous_id AND p.session_id=f.session_id
        GROUP BY o.id''', tuple(scope_params) + params)
        progress_by_step = {row['step_id']: row for row in progression}
        for step in steps:
            progress = progress_by_step.get(step['id'], {})
            step['reached'] = progress.get('reached', 0)
            step['progressed'] = progress.get('progressed', 0)
        confirmed = _rows('''SELECT x.conversion_kind,COUNT(*)::bigint AS total
            FROM cadu_reports_external_conversions x
            LEFT JOIN cadu_reports_campaigns c ON c.id=x.campaign_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
            WHERE x.organization_id=%s AND x.client_id=%s
                AND x.occurred_at > NOW() - (%s * INTERVAL '1 day')''' + conversion_filter +
            ' GROUP BY x.conversion_kind ORDER BY x.conversion_kind', tuple(scope_params))
        return jsonify(tags=tags, steps=steps, activity=activity,
                       online=totals['online'], conversions=totals['conversions'],
                       confirmed=confirmed, period_days=days)

    @bp.post('/api/v1/reports/flow/tags')
    @login_required_api
    def reports_flow_create_tag():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        label = ' '.join(str(payload.get('label') or '').split())[:120]
        if not label:
            abort(400, description='Informe o nome da instalação.')
        host = _host(payload.get('allowed_host'))
        created = _rows('''INSERT INTO cadu_reports_site_tags
            (id,organization_id,client_id,label,allowed_host,public_key,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING id,label,allowed_host,public_key,created_at''',
            (str(uuid.uuid4()), selected['organization_id'], selected['client_id'], label,
             host, secrets.token_urlsafe(24), session['user_id']))
        get_db().commit()
        return jsonify(tag=created[0]), 201

    @bp.post('/api/v1/reports/flow/tags/<tag_id>/revoke')
    @login_required_api
    def reports_flow_revoke_tag(tag_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        tag = _tag_for_client(tag_id, selected)
        _rows('UPDATE cadu_reports_site_tags SET revoked_at=NOW() WHERE id=%s RETURNING id', (tag['id'],))
        get_db().commit()
        return jsonify(revoked=True)

    @bp.post('/api/v1/reports/flow/steps')
    @login_required_api
    def reports_flow_create_step():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        tag = _tag_for_client(payload.get('tag_id'), selected)
        if tag['revoked_at']:
            abort(400, description='A tag foi revogada.')
        name = ' '.join(str(payload.get('name') or '').split())[:120]
        path = str(payload.get('path_prefix') or '').strip()
        kind = payload.get('step_kind')
        if not name or not path.startswith('/') or len(path) > 500 or '?' in path or '#' in path:
            abort(400, description='Informe nome e caminho iniciado em /, sem parâmetros.')
        if kind not in ('page', 'conversion'):
            abort(400, description='Tipo de etapa inválido.')
        if kind == 'conversion' and path == '/':
            abort(400, description='A conversão precisa de uma página específica.')
        campaign_id = payload.get('campaign_id') or None
        if campaign_id:
            try:
                campaign_id = int(campaign_id)
            except (ValueError, TypeError):
                abort(400, description='Campanha inválida.')
            if not _rows('''SELECT id FROM cadu_reports_campaigns WHERE id=%s
                    AND organization_id=%s AND client_id=%s''',
                    (campaign_id, selected['organization_id'], selected['client_id'])):
                abort(404, description='Campanha não encontrada.')
        try:
            position = int(payload.get('position') or 0)
        except (ValueError, TypeError):
            abort(400, description='Posição inválida.')
        if position < 0 or position > 1000:
            abort(400, description='Posição inválida.')
        result = _rows('''INSERT INTO cadu_reports_flow_steps
            (organization_id,client_id,tag_id,name,path_prefix,step_kind,campaign_id,position)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id,name,path_prefix,step_kind,campaign_id,position''',
            (selected['organization_id'], selected['client_id'], tag['id'], name, path,
             kind, campaign_id, position))
        get_db().commit()
        return jsonify(step=result[0]), 201

    @bp.post('/api/v1/reports/flow/steps/<int:step_id>/archive')
    @login_required_api
    def reports_flow_archive_step(step_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        changed = _rows('''UPDATE cadu_reports_flow_steps SET is_active=FALSE,archived_at=NOW()
            WHERE id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE
            RETURNING id''', (step_id, selected['organization_id'], selected['client_id']))
        if not changed:
            abort(404)
        get_db().commit()
        return jsonify(archived=True)

    @bp.post('/api/v1/reports/flow/collect')
    def reports_flow_collect():
        if request.content_length is not None and request.content_length > 4096:
            abort(413)
        raw = request.get_data(cache=False)
        if len(raw) > 4096:
            abort(413)
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            abort(400)
        if not isinstance(payload, dict):
            abort(400)
        public_key = _short(payload.get('key'), 80)
        tag = _rows('''SELECT id,organization_id,client_id,allowed_host FROM cadu_reports_site_tags
            WHERE public_key=%s AND revoked_at IS NULL''', (public_key,))
        if not tag:
            abort(404)
        tag = tag[0]
        origin = request.headers.get('Origin') or request.headers.get('Referer') or ''
        parsed_origin = urlparse(origin)
        if parsed_origin.scheme not in ('https', 'http') or parsed_origin.hostname != tag['allowed_host']:
            abort(403)
        page_url = urlparse(str(payload.get('url') or ''))
        if page_url.hostname != tag['allowed_host'] or page_url.scheme not in ('https', 'http'):
            abort(400, description='Página fora do domínio autorizado.')
        path = _short(page_url.path or '/', 1000)
        kind = payload.get('kind')
        if kind not in ('page_view', 'heartbeat'):
            abort(400, description='Evento inválido.')
        visitor = _uuid(payload.get('visitor_id'), 'Visitante')
        visit_session = _uuid(payload.get('session_id'), 'Sessão')
        referrer = urlparse(str(payload.get('referrer') or '')).hostname
        if referrer:
            referrer = _short(referrer.lower(), 253)
        attribution = {field: _short(payload.get(field), 160) or None for field in
                       ('utm_source', 'utm_medium', 'utm_campaign', 'utm_id', 'click_id')}
        attribution = {field: value if value and '@' not in value else None
                       for field, value in attribution.items()}
        steps = _rows('''SELECT id,path_prefix,step_kind,campaign_id FROM cadu_reports_flow_steps
            WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE
            ORDER BY length(path_prefix) DESC,position,id''',
            (tag['id'], tag['organization_id'], tag['client_id']))
        matched = next((step for step in steps if step['path_prefix'] == '/'
                        or path == step['path_prefix']
                        or path.startswith(step['path_prefix'].rstrip('/') + '/')), None)
        safe_path = re.sub(r'(?<=/)[0-9a-f]{8}-[0-9a-f-]{27,36}(?=/|$)', ':id', path, flags=re.I)
        safe_path = re.sub(r'(?<=/)\d{5,}(?=/|$)', ':id', safe_path)
        safe_path = re.sub(r'(?<=/)[^/]*@[^/]*(?=/|$)', ':redacted', safe_path)
        event_kind = 'conversion' if kind == 'page_view' and matched and matched['step_kind'] == 'conversion' else kind
        campaign_id, method = _campaign_match(tag, attribution, matched)
        quota = _rows('''INSERT INTO cadu_reports_flow_rate_limits (tag_id,bucket_start,event_count)
            VALUES (%s,date_trunc('minute',NOW()),1)
            ON CONFLICT (tag_id,bucket_start) DO UPDATE
                SET event_count=cadu_reports_flow_rate_limits.event_count+1
                WHERE cadu_reports_flow_rate_limits.event_count < %s
            RETURNING event_count''', (tag['id'], MAX_TAG_EVENTS_PER_MINUTE))
        if not quota:
            abort(429, description='Limite temporário de eventos desta tag excedido.')
        _rows('''INSERT INTO cadu_reports_flow_events
            (organization_id,client_id,tag_id,visitor_id,session_id,event_kind,page_path,
             referrer_host,utm_source,utm_medium,utm_campaign,utm_id,click_id,step_id,campaign_id,attribution_method)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (tag['organization_id'], tag['client_id'], tag['id'], visitor, visit_session,
             event_kind, safe_path, referrer, attribution['utm_source'], attribution['utm_medium'],
             attribution['utm_campaign'], attribution['utm_id'], attribution['click_id'],
             matched['id'] if matched else None, campaign_id, method))
        get_db().commit()
        return ('', 204)
