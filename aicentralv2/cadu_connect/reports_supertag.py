"""Independent public Cadu Super Tag configuration and event collection."""
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from flask import abort, current_app, jsonify, make_response, request, session

from ..auth import login_required_api
from ..db import get_db
from .reports_flow import _safe_path
from .reports_v1 import _rows, _selection, _write_guard

MAX_BATCH_EVENTS = 25
MAX_BATCH_BYTES = 32 * 1024
MAX_SITE_EVENTS_PER_MINUTE = 10_000
EVENT_KINDS = {'page_view', 'click', 'whatsapp_click', 'form_submit',
               'visibility', 'scroll_depth', 'custom_event', 'conversion'}


def _host(value):
    parsed = urlparse(value if '://' in str(value or '') else f'https://{value or ""}')
    host = (parsed.hostname or '').lower().rstrip('.')
    if parsed.path not in ('', '/') or parsed.query or parsed.fragment or not re.fullmatch(
            r'(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) or '..' in host:
        abort(400, description='Informe um domínio válido, sem caminho ou protocolo.')
    return host


def _uuid(value, field, *, optional=False):
    if optional and value in (None, ''):
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        abort(400, description=f'{field} inválido.')


def _public_id():
    return secrets.token_urlsafe(18).replace('-', 'a').replace('_', 'b')[:24]


def _base_url():
    return str(current_app.config.get('CONNECT_URL') or request.url_root).rstrip('/')


def _site_by_public_id(public_id):
    found = _rows('''SELECT id,organization_id,client_id,public_id,label,allowed_host,
            enabled,config,config_version,created_at,updated_at,revoked_at
        FROM cadu_reports_supertag_sites WHERE public_id=%s AND enabled=TRUE AND revoked_at IS NULL''',
        (public_id,))
    if not found:
        abort(404)
    return found[0]


def _event(raw, site):
    if not isinstance(raw, dict) or set(raw) - {
            'event_id', 'visitor_id', 'session_id', 'kind', 'event_name', 'path', 'referrer_host',
            'attribution', 'data', 'viewport_width', 'viewport_height', 'occurred_at', 'consent'}:
        abort(400, description='Evento fora do contrato público da Super Tag.')
    if raw.get('consent') != 'granted':
        abort(403, description='Consentimento de analytics não confirmado.')
    kind = raw.get('kind')
    if kind not in EVENT_KINDS:
        abort(400, description='Tipo de evento inválido.')
    path = raw.get('path')
    if not isinstance(path, str) or not path.startswith('/') or '?' in path or '#' in path or len(path) > 1000:
        abort(400, description='Caminho da página inválido.')
    event_name = raw.get('event_name') or None
    if event_name is not None and (not isinstance(event_name, str) or
            not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', event_name)):
        abort(400, description='Nome de evento inválido.')
    if kind in ('custom_event', 'conversion') and not event_name:
        abort(400, description='Informe o nome do evento.')
    data = raw.get('data') or {}
    if not isinstance(data, dict):
        abort(400, description='Metadados do evento inválidos.')
    allowed_data = {
        'click': {'x', 'y', 'element_id'}, 'whatsapp_click': {'x', 'y', 'element_id'},
        'visibility': {'element_id', 'ratio'}, 'scroll_depth': {'depth'},
        'form_submit': {'form_id'}, 'custom_event': set(), 'conversion': set(), 'page_view': set(),
    }[kind]
    if set(data) - allowed_data:
        abort(400, description='Metadados não permitidos. Valores de campos não podem ser enviados.')
    clean_data = {}
    if kind in ('click', 'whatsapp_click'):
        for axis in ('x', 'y'):
            value = data.get(axis)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1000:
                abort(400, description='Coordenada de clique inválida.')
            clean_data[axis] = int(value)
        element_id = data.get('element_id')
        if element_id is not None:
            if not isinstance(element_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', element_id):
                abort(400, description='Identificador de elemento inválido.')
            clean_data['element_id'] = element_id
    elif kind == 'visibility':
        element_id = data.get('element_id')
        ratio = data.get('ratio')
        if not isinstance(element_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', element_id):
            abort(400, description='Identificador de elemento inválido.')
        if isinstance(ratio, bool) or ratio not in (25, 50, 75, 100):
            abort(400, description='Faixa de visibilidade inválida.')
        clean_data = {'element_id': element_id, 'ratio': ratio}
    elif kind == 'scroll_depth':
        if data.get('depth') not in (25, 50, 75, 100):
            abort(400, description='Profundidade de rolagem inválida.')
        clean_data = {'depth': data['depth']}
    elif kind == 'form_submit':
        form_id = data.get('form_id')
        if form_id is not None:
            if not isinstance(form_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', form_id):
                abort(400, description='Identificador de formulário inválido.')
            clean_data['form_id'] = form_id
    try:
        occurred_at = datetime.fromisoformat(str(raw.get('occurred_at', '')).replace('Z', '+00:00'))
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        abort(400, description='Horário do evento inválido.')
    now = datetime.now(timezone.utc)
    occurred_at = min(max(occurred_at.astimezone(timezone.utc), now - timedelta(days=30)), now + timedelta(minutes=5))
    referrer_host = raw.get('referrer_host') or None
    if referrer_host is not None:
        if not isinstance(referrer_host, str) or len(referrer_host) > 253 or '@' in referrer_host:
            abort(400, description='Origem de navegação inválida.')
        referrer_host = _host(referrer_host)
    attribution = raw.get('attribution') or {}
    if not isinstance(attribution, dict) or set(attribution) - {'utm_source', 'utm_medium', 'utm_campaign', 'utm_id', 'click_id'}:
        abort(400, description='Atribuição inválida.')
    clean_attribution = {}
    for key, value in attribution.items():
        if value in (None, ''):
            continue
        if not isinstance(value, str) or len(value) > 160 or '@' in value:
            abort(400, description='Atribuição inválida.')
        clean_attribution[key] = value
    config = site.get('config') or {}
    if kind == 'visibility' and not config.get('visibility_enabled', True):
        abort(400, description='Coleta de visibilidade desativada para este site.')
    return (
        _uuid(raw.get('event_id'), 'Evento'), site['id'], site['organization_id'], site['client_id'],
        _uuid(raw.get('visitor_id'), 'Visitante', optional=True), _uuid(raw.get('session_id'), 'Sessão'),
        kind, event_name, _safe_path(path)[:500], referrer_host, json.dumps(clean_attribution),
        json.dumps(clean_data), _bounded_int(raw.get('viewport_width'), 0, 10000),
        _bounded_int(raw.get('viewport_height'), 0, 10000), occurred_at,
    )


def _bounded_int(value, low, high):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        abort(400, description='Dimensão de viewport inválida.')
    return value


def register(bp):
    @bp.after_request
    def supertag_public_cors(response):
        if not request.path.startswith('/connect/public/supertag/v1/'):
            return response
        public_id = request.path.split('/')[5] if len(request.path.split('/')) > 5 else ''
        origin = request.headers.get('Origin') or ''
        if not public_id or not origin:
            return response
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http'):
            return response
        site = _rows('''SELECT allowed_host FROM cadu_reports_supertag_sites
            WHERE public_id=%s AND enabled=TRUE AND revoked_at IS NULL''', (public_id,))
        if site and (parsed.hostname or '').lower().rstrip('.') == site[0]['allowed_host']:
            response.headers['Access-Control-Allow-Origin'] = f'{parsed.scheme}://{parsed.netloc}'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Access-Control-Max-Age'] = '86400'
            response.headers['Vary'] = 'Origin'
        return response

    @bp.get('/api/v1/reports/supertag/sites')
    @login_required_api
    def supertag_sites():
        selected = _selection()
        params = (selected['organization_id'], selected['client_id'])
        sites = _rows('''SELECT s.id,s.public_id,s.label,s.allowed_host,s.enabled,s.config,
                s.config_version,s.created_at,s.updated_at,s.revoked_at,
                COUNT(e.id)::bigint AS events_30d,
                COUNT(e.id) FILTER (WHERE e.event_kind='conversion')::bigint AS conversions_30d
            FROM cadu_reports_supertag_sites s LEFT JOIN cadu_reports_supertag_events e
              ON e.site_id=s.id AND e.occurred_at >= NOW() - INTERVAL '30 days'
            WHERE s.organization_id=%s AND s.client_id=%s
            GROUP BY s.id ORDER BY s.created_at DESC''', params)
        base = _base_url()
        for site in sites:
            site['script_url'] = f'{base}/static/cadu_connect/cadu-supertag-v1.js'
            site['snippet'] = (f'<script async src="{site["script_url"]}" '
                f'data-cadu-site="{site["public_id"]}" '
                f'data-cadu-config="{base}/connect/public/supertag/v1/{site["public_id"]}/config.json"></script>')
        return jsonify(sites=sites)

    @bp.post('/api/v1/reports/supertag/sites')
    @login_required_api
    def supertag_site_create():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict) or set(payload) != {'label', 'allowed_host'}:
            abort(400, description='Informe o nome da instalação e o domínio permitido.')
        selected = _selection(payload)
        _write_guard(selected)
        label = ' '.join(str(payload['label'] or '').split())[:120]
        if not label:
            abort(400, description='Informe o nome da instalação.')
        host = _host(payload['allowed_host'])
        site_id = str(uuid.uuid4())
        public_id = _public_id()
        site = _rows('''INSERT INTO cadu_reports_supertag_sites
            (id,organization_id,client_id,public_id,label,allowed_host,config,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            RETURNING id,public_id,label,allowed_host,enabled,config,config_version,created_at,updated_at,revoked_at''',
            (site_id, selected['organization_id'], selected['client_id'], public_id, label, host,
             json.dumps({'consent_required': True, 'audience_days': 90, 'visibility_enabled': True}),
             session['user_id']))[0]
        get_db().commit()
        base = _base_url()
        site['script_url'] = f'{base}/static/cadu_connect/cadu-supertag-v1.js'
        site['snippet'] = (f'<script async src="{site["script_url"]}" data-cadu-site="{public_id}" '
            f'data-cadu-config="{base}/connect/public/supertag/v1/{public_id}/config.json"></script>')
        return jsonify(site=site), 201

    @bp.patch('/api/v1/reports/supertag/sites/<uuid:site_id>')
    @login_required_api
    def supertag_site_update(site_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict) or set(payload) - {'label', 'allowed_host', 'visibility_enabled', 'audience_days'}:
            abort(400, description='Configuração da Super Tag inválida.')
        selected = _selection(payload)
        _write_guard(selected)
        found = _rows('''SELECT id,label,allowed_host,config,config_version FROM cadu_reports_supertag_sites
            WHERE id=%s AND organization_id=%s AND client_id=%s AND revoked_at IS NULL FOR UPDATE''',
            (str(site_id), selected['organization_id'], selected['client_id']))
        if not found:
            abort(404)
        current = found[0]
        label = ' '.join(str(payload.get('label', current['label']) or '').split())[:120]
        host = _host(payload.get('allowed_host', current['allowed_host']))
        config = dict(current['config'] or {})
        if 'visibility_enabled' in payload:
            if not isinstance(payload['visibility_enabled'], bool):
                abort(400, description='Informe se a coleta de visibilidade está ativa.')
            config['visibility_enabled'] = payload['visibility_enabled']
        if 'audience_days' in payload:
            if isinstance(payload['audience_days'], bool) or payload['audience_days'] not in (30, 60, 90, 180, 365):
                abort(400, description='Escolha uma retenção entre 30 e 365 dias.')
            config['audience_days'] = payload['audience_days']
        updated = _rows('''UPDATE cadu_reports_supertag_sites SET label=%s,allowed_host=%s,
            config=%s::jsonb,config_version=config_version+1,updated_at=NOW()
            WHERE id=%s RETURNING id,public_id,label,allowed_host,enabled,config,config_version,created_at,updated_at,revoked_at''',
            (label, host, json.dumps(config), str(site_id)))[0]
        get_db().commit()
        base = _base_url()
        updated['script_url'] = f'{base}/static/cadu_connect/cadu-supertag-v1.js'
        updated['snippet'] = (f'<script async src="{updated["script_url"]}" data-cadu-site="{updated["public_id"]}" '
            f'data-cadu-config="{base}/connect/public/supertag/v1/{updated["public_id"]}/config.json"></script>')
        return jsonify(site=updated)

    @bp.post('/api/v1/reports/supertag/sites/<uuid:site_id>/revoke')
    @login_required_api
    def supertag_site_revoke(site_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        changed = _rows('''UPDATE cadu_reports_supertag_sites SET enabled=FALSE,revoked_at=NOW(),updated_at=NOW()
            WHERE id=%s AND organization_id=%s AND client_id=%s AND revoked_at IS NULL RETURNING id''',
            (str(site_id), selected['organization_id'], selected['client_id']))
        if not changed:
            abort(404)
        get_db().commit()
        return jsonify(revoked=True)

    @bp.get('/public/supertag/v1/<public_id>/config.json')
    def supertag_public_config(public_id):
        site = _site_by_public_id(public_id)
        origin = request.headers.get('Origin') or ''
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http') or (parsed.hostname or '').lower().rstrip('.') != site['allowed_host']:
            abort(403)
        request._supertag_public_id = public_id
        response = make_response(jsonify(site_id=site['public_id'], config_version=site['config_version'],
            consent_required=True, visibility_enabled=(site.get('config') or {}).get('visibility_enabled', True),
            audience_days=(site.get('config') or {}).get('audience_days', 90)))
        response.headers['Cache-Control'] = 'public, max-age=300, stale-while-revalidate=3600'
        response.set_etag(f'{site["public_id"]}:{site["config_version"]}')
        return response.make_conditional(request)

    @bp.route('/public/supertag/v1/<public_id>/collect', methods=['POST', 'OPTIONS'])
    def supertag_public_collect(public_id):
        if request.method == 'OPTIONS':
            return ('', 204)
        if request.content_length is not None and request.content_length > MAX_BATCH_BYTES:
            abort(413)
        raw = request.stream.read(MAX_BATCH_BYTES + 1)
        if len(raw) > MAX_BATCH_BYTES:
            abort(413)
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            abort(400, description='Lote JSON inválido.')
        if not isinstance(payload, dict) or set(payload) != {'events'} or not isinstance(payload['events'], list):
            abort(400, description='Envie um lote de eventos.')
        events = payload['events']
        if not events or len(events) > MAX_BATCH_EVENTS:
            abort(400, description=f'Envie de 1 a {MAX_BATCH_EVENTS} eventos por lote.')
        site = _site_by_public_id(public_id)
        origin = request.headers.get('Origin') or ''
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http') or (parsed.hostname or '').lower().rstrip('.') != site['allowed_host']:
            abort(403)
        request._supertag_public_id = public_id
        prepared = [_event(item, site) for item in events]
        conn = get_db()
        try:
            quota = _rows('''INSERT INTO cadu_reports_supertag_rate_limits (site_id,bucket_start,event_count)
                VALUES (%s,date_trunc('minute',NOW()),%s)
                ON CONFLICT (site_id,bucket_start) DO UPDATE
                    SET event_count=cadu_reports_supertag_rate_limits.event_count+EXCLUDED.event_count
                    WHERE cadu_reports_supertag_rate_limits.event_count+EXCLUDED.event_count <= %s
                RETURNING event_count''', (site['id'], len(prepared), MAX_SITE_EVENTS_PER_MINUTE))
            if not quota:
                abort(429, description='Limite temporário desta instalação excedido.')
            with conn.cursor() as cursor:
                cursor.executemany('''INSERT INTO cadu_reports_supertag_events
                    (event_id,site_id,organization_id,client_id,visitor_id,session_id,event_kind,event_name,
                     page_path,referrer_host,attribution,event_data,viewport_width,viewport_height,occurred_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                    ON CONFLICT (site_id,event_id) DO NOTHING''', prepared)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return jsonify(accepted=len(prepared)), 202

    @bp.get('/api/v1/reports/supertag/sites/<uuid:site_id>/events')
    @login_required_api
    def supertag_site_events(site_id):
        selected = _selection()
        params = (str(site_id), selected['organization_id'], selected['client_id'])
        site = _rows('''SELECT id,public_id,label,allowed_host,config FROM cadu_reports_supertag_sites
            WHERE id=%s AND organization_id=%s AND client_id=%s''', params)
        if not site:
            abort(404)
        summary = _rows('''SELECT event_kind,COUNT(*)::bigint AS total,
                COUNT(DISTINCT visitor_id)::bigint AS visitors
            FROM cadu_reports_supertag_events WHERE site_id=%s
              AND occurred_at >= NOW() - INTERVAL '30 days' GROUP BY event_kind ORDER BY event_kind''',
            (str(site_id),))
        pages = _rows('''SELECT page_path,COUNT(*) FILTER (WHERE event_kind='page_view')::bigint AS views,
                COUNT(*) FILTER (WHERE event_kind='form_submit')::bigint AS form_submissions,
                COUNT(*) FILTER (WHERE event_kind IN ('click','whatsapp_click'))::bigint AS clicks,
                COUNT(*) FILTER (WHERE event_kind='conversion')::bigint AS conversions,
                COUNT(*) FILTER (WHERE event_kind='visibility')::bigint AS visibility_events,
                COUNT(*) FILTER (WHERE event_kind='scroll_depth')::bigint AS scroll_events
            FROM cadu_reports_supertag_events WHERE site_id=%s
              AND occurred_at >= NOW() - INTERVAL '30 days'
            GROUP BY page_path ORDER BY views DESC LIMIT 100''', (str(site_id),))
        heatmap = _rows('''SELECT page_path,event_kind,event_data->>'element_id' AS element_id,
                event_data->>'x' AS x,event_data->>'y' AS y,event_data->>'ratio' AS ratio,
                event_data->>'depth' AS depth,COUNT(*)::bigint AS total
            FROM cadu_reports_supertag_events WHERE site_id=%s
              AND occurred_at >= NOW() - INTERVAL '30 days'
              AND event_kind IN ('click','whatsapp_click','visibility','scroll_depth')
            GROUP BY page_path,event_kind,event_data->>'element_id',event_data->>'x',event_data->>'y',
                event_data->>'ratio',event_data->>'depth' ORDER BY total DESC LIMIT 500''', (str(site_id),))
        return jsonify(site=site[0], summary=summary, pages=pages, heatmap=heatmap)
