"""First-party Funnel Flow collection and URL-step mapping for Reports V1."""
import json
import re
import secrets
import string
import uuid
from datetime import date
from urllib.parse import unquote, urlparse

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


def _safe_path(value):
    """Keep useful URL paths while removing identifiers and contact details."""
    safe_segments = []
    for segment in str(value or '/').split('/'):
        decoded = unquote(segment)
        if '@' in decoded or re.search(r'(?i)\b[^\s/]+@[^\s/]+\b', decoded):
            safe_segments.append(':redacted')
        elif re.fullmatch(r'[0-9a-f]{8}-[0-9a-f-]{27,36}', decoded, flags=re.I):
            safe_segments.append(':id')
        elif decoded.isdigit() and len(decoded) >= 5:
            safe_segments.append(':id')
        elif re.fullmatch(r'[+()0-9 .-]{8,}', decoded) and sum(char.isdigit() for char in decoded) >= 9:
            safe_segments.append(':redacted')
        else:
            safe_segments.append(segment)
    return '/'.join(safe_segments) or '/'


def _flow_code():
    # CF_ followed by 7 base-36 symbols: compact, internal, and collision-safe.
    alphabet = string.ascii_uppercase + string.digits
    return 'CF_' + ''.join(secrets.choice(alphabet) for _ in range(7))


def _new_flow_code():
    for _ in range(5):
        code = _flow_code()
        if not _rows('SELECT 1 FROM cadu_reports_flow_registry WHERE flow_code=%s', (code,)):
            return code
    abort(503, description='Não foi possível reservar o código do fluxo. Tente novamente.')


def _client_tag_urls(client_id):
    client_id = int(client_id)
    base = request.url_root.rstrip('/')
    return {
        'flow': f'{base}/static/cadu_connect/cadu-flow-tag.js?client={client_id}',
        'supertag': None,
    }


def _flow_row(flow_id, selected):
    found = _rows('''SELECT f.id,f.flow_code,f.name,f.status,f.config,f.created_at,f.updated_at,
            f.published_at,t.id AS tag_id,t.label AS tag_label,t.allowed_host,t.public_key,t.revoked_at
        FROM cadu_reports_flow_registry f
        JOIN cadu_reports_site_tags t ON t.id=f.tag_id
        WHERE f.id=%s AND f.organization_id=%s AND f.client_id=%s''',
        (flow_id, selected['organization_id'], selected['client_id']))
    if not found:
        abort(404, description='Fluxo não encontrado neste cliente.')
    return found[0]


def _tag_for_client(tag_id, selected):
    found = _rows('''SELECT id,label,allowed_host,public_key,created_at,revoked_at,tag_kind
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
    @bp.after_request
    def reports_flow_collection_cors(response):
        origin = request.headers.get('Origin') or request.headers.get('Referer') or ''
        parsed = urlparse(origin)
        if request.path.startswith('/connect/api/v1/reports/flow/collect/') and parsed.scheme in ('https','http'):
            flow_code = request.path.rsplit('/',1)[-1]
            flow = _rows("""SELECT t.allowed_host FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
                WHERE f.flow_code=%s AND f.status='published' AND t.revoked_at IS NULL AND t.public_key=%s AND t.client_id=%s""",
                (flow_code,request.args.get('key',''),request.args.get('client_id',type=int)))
            if flow and (parsed.hostname or '').lower().rstrip('.') == flow[0]['allowed_host']:
                response.headers['Access-Control-Allow-Origin'] = f'{parsed.scheme}://{parsed.netloc}'
                response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
                response.headers['Vary'] = 'Origin'
        return response

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
        event_scope_params = list(scope_params)
        event_period_filter = ' AND e.occurred_at > NOW() - (%s * INTERVAL \'1 day\')'
        event_date_filter = ''
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        if start_date or end_date:
            try:
                parsed_start = date.fromisoformat(start_date)
                parsed_end = date.fromisoformat(end_date)
            except ValueError:
                abort(400, description='Intervalo de datas inválido.')
            if parsed_start > parsed_end or (parsed_end - parsed_start).days > 366:
                abort(400, description='Escolha um intervalo de até 367 dias.')
            event_period_filter = ''
            event_date_filter = ' AND e.occurred_at >= %s::date AND e.occurred_at < (%s::date + INTERVAL \'1 day\')'
            event_scope_params = [*params, *scope_params[3:], parsed_start.isoformat(), parsed_end.isoformat()]
        event_scoped_events = '''WITH selected_events AS (
            SELECT e.* FROM cadu_reports_flow_events e
            LEFT JOIN cadu_reports_campaigns c ON c.id=e.campaign_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
            WHERE e.organization_id=%s AND e.client_id=%s
            ''' + event_period_filter + event_filter + event_date_filter + ') '
        tags = _rows('''SELECT id,label,allowed_host,public_key,created_at,revoked_at,tag_kind
            FROM cadu_reports_site_tags WHERE organization_id=%s AND client_id=%s ORDER BY created_at DESC''', params)
        steps = _rows('''SELECT s.id,s.tag_id,s.name,s.path_prefix,s.step_kind,s.campaign_id,s.position,
            s.is_active,s.archived_at,
            c.name AS campaign_name FROM cadu_reports_flow_steps s
            LEFT JOIN cadu_reports_campaigns c ON c.id=s.campaign_id
            WHERE s.organization_id=%s AND s.client_id=%s AND s.is_active=TRUE
            ORDER BY s.position,s.id''', params)
        activity = _rows(scoped_events + '''SELECT e.tag_id,e.page_path,
            COUNT(*) FILTER (WHERE e.event_kind IN ('page_view','conversion')) AS views,
            COUNT(*) FILTER (WHERE e.event_kind='form_submit') AS form_submissions,
            COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click')) AS clicks,
            COUNT(DISTINCT e.visitor_id) FILTER (WHERE e.event_kind IN ('page_view','conversion')) AS visitors,
            COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind IN ('page_view','conversion','heartbeat','form_submit','click','whatsapp_click')
                AND e.occurred_at > NOW() - INTERVAL '90 seconds') AS online,
            COUNT(DISTINCT e.visitor_id) FILTER (WHERE e.event_kind='conversion') AS conversions
            FROM selected_events e
            GROUP BY e.tag_id,e.page_path ORDER BY views DESC LIMIT 100''', tuple(scope_params))
        totals = _rows(scoped_events + '''SELECT
            COUNT(DISTINCT session_id) FILTER (WHERE event_kind IN ('page_view','conversion','heartbeat','form_submit','click','whatsapp_click')
                AND occurred_at > NOW() - INTERVAL '90 seconds') AS online,
            COUNT(DISTINCT visitor_id) FILTER (WHERE event_kind='conversion') AS conversions
            FROM selected_events''', tuple(scope_params))[0]
        event_inventory = _rows(event_scoped_events + '''SELECT event_kind,COALESCE(NULLIF(event_name,''),event_kind) AS event_name,page_path,
            COALESCE(utm_source,referrer_host,'Website') AS source_label,
            MAX(occurred_at) AS last_occurred_at,COUNT(*)::bigint AS total,
            COUNT(*) FILTER (WHERE step_id IS NOT NULL)::bigint AS mapped,
            COUNT(*) OVER() AS group_count
            FROM selected_events
            GROUP BY event_kind,COALESCE(NULLIF(event_name,''),event_kind),page_path,COALESCE(utm_source,referrer_host,'Website')
            ORDER BY last_occurred_at DESC LIMIT 300''', tuple(event_scope_params))
        event_summary = _rows(event_scoped_events + '''SELECT COUNT(*)::bigint AS total,
            COUNT(*) FILTER (WHERE event_kind='form_submit')::bigint AS form_submissions,
            COUNT(*) FILTER (WHERE event_kind='conversion')::bigint AS conversions,
            COUNT(*) FILTER (WHERE utm_source IS NOT NULL OR referrer_host IS NOT NULL)::bigint AS attributed
            FROM selected_events''', tuple(event_scope_params))[0]
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
        flows = _rows('''SELECT f.id,f.flow_code,f.name,f.status,f.config,f.tag_id,t.label AS tag_label,
                t.allowed_host,t.public_key,t.revoked_at,f.created_at,f.updated_at,f.published_at
            FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
            WHERE f.organization_id=%s AND f.client_id=%s ORDER BY f.created_at DESC''', params)
        return jsonify(tags=tags, steps=steps, flows=flows, events=event_inventory,
                       event_group_count=event_inventory[0]['group_count'] if event_inventory else 0,
                       event_summary=event_summary,
                       tag_urls=_client_tag_urls(selected['client_id']), activity=activity,
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
            (id,organization_id,client_id,label,allowed_host,public_key,created_by,tag_kind)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'supertag')
            RETURNING id,label,allowed_host,public_key,created_at,revoked_at,tag_kind''',
            (str(uuid.uuid4()), selected['organization_id'], selected['client_id'], label,
             host, secrets.token_urlsafe(24), session['user_id']))
        get_db().commit()
        return jsonify(tag=created[0]), 201

    @bp.post('/api/v1/reports/flow/flows')
    @login_required_api
    def reports_flow_create_flow():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        name = ' '.join(str(payload.get('name') or '').split())[:120]
        tag_id = payload.get('tag_id')
        tag = _tag_for_client(tag_id, selected) if tag_id else None
        if not name:
            abort(400, description='Informe o nome do fluxo.')
        if not tag:
            label = ' '.join(str(payload.get('tag_label') or name).split())[:120]
            host = _host(payload.get('allowed_host'))
            tag = _rows('''INSERT INTO cadu_reports_site_tags
                (id,organization_id,client_id,label,allowed_host,public_key,created_by,tag_kind)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'flow')
                RETURNING id,label,allowed_host,public_key,created_at,revoked_at,tag_kind''',
                (str(uuid.uuid4()), selected['organization_id'], selected['client_id'],
                 label, host, secrets.token_urlsafe(24), session['user_id']))[0]
        config = payload.get('config') if isinstance(payload.get('config'), dict) else {}
        flow_id = str(uuid.uuid4())
        flow_code = _new_flow_code()
        created = _rows('''INSERT INTO cadu_reports_flow_registry
            (id,organization_id,client_id,flow_code,tag_id,name,config,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            RETURNING id,flow_code,name,status,config,tag_id,created_at,updated_at''',
            (flow_id, selected['organization_id'], selected['client_id'], flow_code,
             tag['id'], name, json.dumps(config), session['user_id']))[0]
        get_db().commit()
        return jsonify(flow=created, tag=tag, tag_urls=_client_tag_urls(selected['client_id'])), 201

    @bp.patch('/api/v1/reports/flow/flows/<flow_id>')
    @login_required_api
    def reports_flow_update_flow(flow_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        current = _flow_row(flow_id, selected)
        name = ' '.join(str(payload.get('name', current['name']) or '').split())[:120]
        config = payload.get('config', current['config'])
        if not name or not isinstance(config, dict):
            abort(400, description='Nome e configuração do fluxo são obrigatórios.')
        updated = _rows('''UPDATE cadu_reports_flow_registry SET name=%s,config=%s::jsonb,updated_at=NOW()
            WHERE id=%s AND organization_id=%s AND client_id=%s AND status <> 'published'
            RETURNING id,flow_code,name,status,config,tag_id,created_at,updated_at,published_at''',
            (name, json.dumps(config), current['id'], selected['organization_id'], selected['client_id']))
        if not updated:
            abort(409, description='Despublique o fluxo antes de editar sua configuração.')
        get_db().commit()
        return jsonify(flow=updated[0])

    @bp.post('/api/v1/reports/flow/flows/<flow_id>/publish')
    @login_required_api
    def reports_flow_publish_flow(flow_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        changed = _rows('''UPDATE cadu_reports_flow_registry SET status='published',published_at=NOW(),updated_at=NOW()
            WHERE id=%s AND organization_id=%s AND client_id=%s
            RETURNING id,flow_code,name,status,published_at''',
            (flow['id'], selected['organization_id'], selected['client_id']))[0]
        get_db().commit()
        return jsonify(flow=changed, tag_url=_client_tag_urls(selected['client_id'])['flow'],
                       supertag_url=_client_tag_urls(selected['client_id'])['supertag'],
                       code=flow['flow_code'])

    @bp.post('/api/v1/reports/flow/flows/<flow_id>/unpublish')
    @login_required_api
    def reports_flow_unpublish_flow(flow_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        changed = _rows('''UPDATE cadu_reports_flow_registry SET status='draft',updated_at=NOW()
            WHERE id=%s AND organization_id=%s AND client_id=%s
            RETURNING id,flow_code,name,status,published_at''',
            (flow['id'], selected['organization_id'], selected['client_id']))[0]
        get_db().commit()
        return jsonify(flow=changed)

    @bp.post('/api/v1/reports/flow/flows/<flow_id>/test')
    @login_required_api
    def reports_flow_test_flow(flow_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        events = payload.get('events')
        if not isinstance(events, list) or not events or len(events) > 30:
            abort(400, description='Envie até 30 eventos fictícios para o teste.')
        if flow['status'] == 'published':
            abort(409, description='Despublique o fluxo para executar testes fictícios.')
        session_id = str(uuid.uuid4())
        accepted = []
        for item in events:
            if not isinstance(item, dict) or item.get('kind') not in ('page_view','form_submit','click','whatsapp_click','conversion','custom_event'):
                abort(400, description='Tipo de evento de teste inválido.')
            path = str(item.get('path') or '/')
            if not path.startswith('/') or '?' in path or '#' in path or len(path) > 500:
                abort(400, description='Use somente caminhos internos, sem query string.')
            source = ' '.join(str(item.get('source') or '')[:160].split()) or None
            details = item.get('data') if isinstance(item.get('data'), dict) else {}
            if item['kind'] == 'custom_event':
                details['event_name'] = ' '.join(str(item.get('event_name') or 'Evento personalizado').split())[:120]
            details = {str(k)[:60]: str(v)[:180] for k, v in list(details.items())[:12]}
            row = _rows('''INSERT INTO cadu_reports_flow_events_test
                (organization_id,client_id,flow_id,flow_code,event_kind,page_path,source_label,session_id,payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                RETURNING id,event_kind,page_path,source_label,created_at''',
                (selected['organization_id'], selected['client_id'], flow['id'], flow['flow_code'],
                 item['kind'], path, source, session_id, json.dumps(details)))[0]
            accepted.append(row)
        get_db().commit()
        return jsonify(flow_code=flow['flow_code'], simulated=True, session_id=session_id, events=accepted)

    @bp.patch('/api/v1/reports/flow/tags/<tag_id>')
    @login_required_api
    def reports_flow_update_tag(tag_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        tag = _tag_for_client(tag_id, selected)
        label = ' '.join(str(payload.get('label', tag['label']) or '').split())[:120]
        if not label:
            abort(400, description='Informe o nome da instalação.')
        host = _host(payload.get('allowed_host', tag['allowed_host']))
        changed = _rows('''UPDATE cadu_reports_site_tags SET label=%s,allowed_host=%s
            WHERE id=%s AND organization_id=%s AND client_id=%s
                AND tag_kind=%s
            RETURNING id,label,allowed_host,public_key,created_at,revoked_at,tag_kind''',
            (label, host, tag['id'], selected['organization_id'], selected['client_id'], tag['tag_kind']))
        get_db().commit()
        return jsonify(tag=changed[0])

    @bp.post('/api/v1/reports/flow/tags/<tag_id>/revoke')
    @login_required_api
    def reports_flow_revoke_tag(tag_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        tag = _tag_for_client(tag_id, selected)
        _rows('UPDATE cadu_reports_site_tags SET revoked_at=NOW() WHERE id=%s AND organization_id=%s AND client_id=%s RETURNING id',
              (tag['id'], selected['organization_id'], selected['client_id']))
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
        if kind not in ('page', 'conversion', 'form', 'event', 'whatsapp'):
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

    @bp.patch('/api/v1/reports/flow/steps/<int:step_id>')
    @login_required_api
    def reports_flow_update_step(step_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        found = _rows('''SELECT id,tag_id,name,path_prefix,step_kind,campaign_id,position
            FROM cadu_reports_flow_steps WHERE id=%s AND organization_id=%s AND client_id=%s
                AND is_active=TRUE FOR UPDATE''', (step_id, selected['organization_id'], selected['client_id']))
        if not found:
            abort(404)
        current = found[0]
        tag = _tag_for_client(current['tag_id'], selected)
        if tag['revoked_at']:
            abort(400, description='Reative a instalação criando uma nova tag antes de editar etapas.')
        name = ' '.join(str(payload.get('name', current['name']) or '').split())[:120]
        path = str(payload.get('path_prefix', current['path_prefix']) or '').strip()
        kind = payload.get('step_kind', current['step_kind'])
        if not name or not path.startswith('/') or len(path) > 500 or '?' in path or '#' in path:
            abort(400, description='Informe nome e caminho iniciado em /, sem parâmetros.')
        if kind not in ('page', 'conversion', 'form', 'event', 'whatsapp') or (kind == 'conversion' and path == '/'):
            abort(400, description='Tipo de etapa ou caminho de conversão inválido.')
        campaign_id = payload.get('campaign_id', current['campaign_id'])
        try:
            campaign_id = int(campaign_id) if campaign_id not in (None, '') else None
        except (TypeError, ValueError):
            abort(400, description='Campanha inválida.')
        if campaign_id is not None and not _rows('''SELECT id FROM cadu_reports_campaigns
                WHERE id=%s AND organization_id=%s AND client_id=%s''',
                (campaign_id, selected['organization_id'], selected['client_id'])):
            abort(404, description='Campanha não encontrada.')
        try:
            position = int(payload.get('position', current['position']))
        except (ValueError, TypeError):
            abort(400, description='Posição inválida.')
        if position < 0 or position > 1000:
            abort(400, description='Posição inválida.')
        changed = _rows('''UPDATE cadu_reports_flow_steps SET name=%s,path_prefix=%s,step_kind=%s,
                campaign_id=%s,position=%s WHERE id=%s AND organization_id=%s AND client_id=%s
                AND position=(SELECT position FROM cadu_reports_flow_steps
                    WHERE id=%s AND organization_id=%s AND client_id=%s FOR UPDATE)
            RETURNING id,tag_id,name,path_prefix,step_kind,campaign_id,position''',
            (name, path, kind, campaign_id, position, step_id, selected['organization_id'], selected['client_id'],
             step_id, selected['organization_id'], selected['client_id']))
        if not changed:
            get_db().rollback()
            abort(409, description='A etapa foi alterada ao mesmo tempo. Atualize o funil e tente novamente.')
        get_db().commit()
        return jsonify(step=changed[0])

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
        raw = request.stream.read(4097)
        if len(raw) > 4096:
            abort(413)
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            abort(400)
        if not isinstance(payload, dict):
            abort(400)
        public_key = _short(payload.get('key'), 80) or _short(request.args.get('key'), 80)
        tag = _rows('''SELECT id,organization_id,client_id,allowed_host FROM cadu_reports_site_tags
            WHERE public_key=%s AND revoked_at IS NULL AND client_id=%s''',
            (public_key, request.args.get('client_id', type=int)))
        if not tag:
            abort(404)
        tag = tag[0]
        request._cadu_flow_cors_tag = [{'allowed_host': tag['allowed_host']}]
        origin = request.headers.get('Origin') or request.headers.get('Referer') or ''
        parsed_origin = urlparse(origin)
        if parsed_origin.scheme not in ('https', 'http') or (parsed_origin.hostname or '').lower().rstrip('.') != tag['allowed_host']:
            abort(403)
        page_url = urlparse(str(payload.get('url') or ''))
        if page_url.hostname != tag['allowed_host'] or page_url.scheme not in ('https', 'http'):
            abort(400, description='Página fora do domínio autorizado.')
        path = _short(page_url.path or '/', 1000)
        kind = payload.get('kind')
        if kind not in ('page_view', 'heartbeat', 'form_submit', 'click'):
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
        safe_path = _safe_path(path)
        event_kind = 'conversion' if kind == 'page_view' and matched and matched['step_kind'] == 'conversion' else kind
        campaign_id, method = _campaign_match(tag, attribution, matched)
        if not campaign_id and matched and matched.get('campaign_id'):
            campaign_id, method = matched['campaign_id'], 'step'
        if kind in ('form_submit', 'click'):
            event_kind = kind
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

    @bp.route('/api/v1/reports/flow/collect/<flow_code>', methods=['POST','OPTIONS'])
    def reports_flow_collect_code(flow_code):
        if request.method == 'OPTIONS':
            return ('', 204)
        if request.content_length is not None and request.content_length > 4096:
            abort(413)
        flow = _rows('''SELECT f.id,f.organization_id,f.client_id,f.flow_code,f.status,f.config,t.allowed_host
            FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
            WHERE f.flow_code=%s AND f.status='published' AND t.revoked_at IS NULL
                AND t.public_key=%s AND t.client_id=%s''',
            (flow_code, request.args.get('key',''), request.args.get('client_id', type=int)))
        if not flow:
            abort(404)
        flow = flow[0]
        request._cadu_flow_cors_tag = [{'allowed_host': flow['allowed_host']}]
        raw = request.stream.read(4097)
        if len(raw) > 4096:
            abort(413)
        try:
            payload = json.loads(raw or b'{}')
        except (ValueError, UnicodeDecodeError):
            abort(400, description='JSON inválido.')
        if not isinstance(payload, dict):
            abort(400)
        origin = request.headers.get('Origin') or request.headers.get('Referer') or ''
        parsed = urlparse(origin)
        if parsed.scheme not in ('http', 'https') or (parsed.hostname or '').lower().rstrip('.') != flow['allowed_host']:
            abort(403)
        kind = payload.get('kind')
        if kind not in ('page_view','form_submit','click','whatsapp_click','conversion','heartbeat','custom_event'):
            abort(400)
        event_name = ' '.join(str(payload.get('event_name') or '').split()) or None
        if kind == 'custom_event' and (not event_name or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', event_name)):
            abort(400, description='Use um nome de evento iniciado por letra, com letras, números ou _.')
        path = str(payload.get('path') or '/')
        if not path.startswith('/') or '?' in path or '#' in path or len(path) > 500:
            abort(400)
        attribution = payload.get('attribution') if isinstance(payload.get('attribution'), dict) else {}
        session_id = _uuid(payload.get('session_id'), 'Sessão')
        configured_nodes = (flow.get('config') or {}).get('nodes', []) if isinstance(flow.get('config'), dict) else []
        matched_node = next((node for node in configured_nodes if isinstance(node, dict)
            and node.get('path') == path and node.get('type') in ('page','form','event','conversion','whatsapp')), None)
        if kind == 'page_view' and matched_node and matched_node.get('type') == 'conversion':
            kind = 'conversion'
        tag = _rows('''SELECT t.id FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
            WHERE f.id=%s AND f.organization_id=%s AND f.client_id=%s''',
            (flow['id'], flow['organization_id'], flow['client_id']))[0]
        visitor_id = _uuid(payload.get('visitor_id'), 'Visitante')
        safe_path = _safe_path(path)
        visit_session = _uuid(session_id, 'Sessão')
        referrer = urlparse(str(payload.get('referrer') or '')).hostname
        if referrer:
            referrer = _short(referrer.lower(), 253)
        attribution_values = {field: _short(attribution.get(field), 160) or None for field in
                              ('utm_source', 'utm_medium', 'utm_campaign', 'utm_id', 'click_id')}
        attribution_values = {field: value if value and '@' not in value else None
                              for field, value in attribution_values.items()}
        matched_step = _rows('''SELECT id,step_kind,campaign_id FROM cadu_reports_flow_steps
            WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE
                AND (path_prefix='/' OR %s=path_prefix OR %s LIKE rtrim(path_prefix,'/') || '/%%')
            ORDER BY length(path_prefix) DESC,position,id LIMIT 1''',
            (tag['id'], flow['organization_id'], flow['client_id'], safe_path, safe_path))
        node_step_kind = {'form': 'form', 'event': 'event', 'whatsapp': 'whatsapp', 'conversion': 'conversion'}
        step_kind = node_step_kind.get(matched_node.get('type')) if matched_node else None
        event_step_kind = {'form_submit': 'form', 'event': 'event', 'whatsapp_click': 'whatsapp', 'custom_event': 'event'}.get(kind)
        desired_step_kind = step_kind or event_step_kind
        if desired_step_kind:
            _rows('SELECT pg_advisory_xact_lock(hashtext(%s),hashtext(%s))',
                  (str(tag['id']), f'{safe_path}:{desired_step_kind}'))
            mapped = _rows('''SELECT id,campaign_id FROM cadu_reports_flow_steps
                WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE
                    AND path_prefix=%s AND step_kind=%s ORDER BY position,id LIMIT 1''',
                (tag['id'], flow['organization_id'], flow['client_id'], safe_path, desired_step_kind))
            if mapped:
                matched_step = [{'id': mapped[0]['id'], 'campaign_id': mapped[0]['campaign_id'], 'step_kind': desired_step_kind}]
            else:
                created_step = _rows('''INSERT INTO cadu_reports_flow_steps
                    (organization_id,client_id,tag_id,name,path_prefix,step_kind,position)
                    VALUES (%s,%s,%s,%s,%s,%s,0) RETURNING id,campaign_id,step_kind''',
                    (flow['organization_id'], flow['client_id'], tag['id'],
                     str((matched_node or {}).get('title') or desired_step_kind)[:120], safe_path, desired_step_kind))
                matched_step = [created_step[0]]
        campaign_id, method = _campaign_match(
            {'organization_id': flow['organization_id'], 'client_id': flow['client_id']},
            attribution_values, matched_step[0] if matched_step else None)
        if kind == 'page_view' and matched_step and matched_step[0]['step_kind'] == 'conversion':
            kind = 'conversion'
        quota = _rows('''INSERT INTO cadu_reports_flow_rate_limits (tag_id,bucket_start,event_count)
            VALUES (%s,date_trunc('minute',NOW()),1)
            ON CONFLICT (tag_id,bucket_start) DO UPDATE
                SET event_count=cadu_reports_flow_rate_limits.event_count+1
                WHERE cadu_reports_flow_rate_limits.event_count < %s RETURNING event_count''',
            (tag['id'], MAX_TAG_EVENTS_PER_MINUTE))
        if not quota:
            abort(429, description='Limite temporário de eventos desta tag excedido.')
        step_id = matched_step[0]['id'] if matched_step else None
        if kind in ('form_submit', 'click', 'whatsapp_click') and matched_step:
            step_id = matched_step[0]['id']
        _rows('''INSERT INTO cadu_reports_flow_events
            (organization_id,client_id,tag_id,visitor_id,session_id,event_kind,event_name,page_path,
             referrer_host,utm_source,utm_medium,utm_campaign,utm_id,click_id,step_id,campaign_id,attribution_method)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (flow['organization_id'], flow['client_id'], tag['id'], visitor_id, visit_session,
             kind, event_name, safe_path, referrer, attribution_values['utm_source'], attribution_values['utm_medium'],
             attribution_values['utm_campaign'], attribution_values['utm_id'], attribution_values['click_id'],
             step_id, campaign_id, method))
        get_db().commit()
        return ('',204)
