"""Independent public Cadu Super Tag configuration and event collection."""
import json
import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import urljoin, urlparse

import urllib3
from flask import abort, current_app, jsonify, make_response, request, session
from werkzeug.exceptions import BadRequest

from ..auth import login_required_api
from ..db import get_db
from ..cadu_workspace.brand_site_inspector import (
    _public_addresses,
    _pinned_get,
    normalize_public_url,
)
from .reports_flow import _campaign_match, _host_allowed, _safe_path
from .reports_v1 import _rows, _selection, _write_guard

MAX_BATCH_EVENTS = 25
MAX_BATCH_BYTES = 32 * 1024
MAX_SITE_EVENTS_PER_MINUTE = 10_000
MAX_IP_EVENTS_PER_MINUTE = 1_000
EVENT_KINDS = {'page_view', 'page_leave', 'heartbeat', 'click', 'whatsapp_click', 'form_submit',
               'visibility', 'scroll_depth', 'custom_event', 'conversion'}
SITE_CHECK_MAX_BYTES = 256_000


def _check_site_url(value):
    try:
        normalized = normalize_public_url(value, label='site')
        parsed = urlparse(normalized)
        host = (parsed.hostname or '').lower().rstrip('.')
        addresses = _public_addresses(normalized)
    except BadRequest as exc:
        abort(400, description=getattr(exc, 'description', 'Informe uma URL pública HTTP ou HTTPS válida.'))
    return parsed, host, addresses


def _site_preview(html):
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
    title = re.sub(r'\s+', ' ', unescape(match.group(1))).strip()[:200] if match else ''
    icon = re.search(r'<link[^>]+rel=["\'](?:shortcut )?icon["\'][^>]+href=["\']([^"\']+)', html, re.I)
    return title, icon.group(1)[:1000] if icon else '/favicon.ico'


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


def _supertag_snippet(site):
    base = _base_url()
    public_id = site['public_id']
    return (f'<script async src="{base}/v1/supertag.js" '
            f'data-cadu-site="{public_id}" '
            f'data-cadu-config="{base}/connect/public/supertag/v1/{public_id}/config.json" '
            f'data-cadu-consent="auto"></script>')


def ensure_supertag_site(selected, host, label):
    """Reuse or create the one browser installation shared by this client's flows."""
    canonical_host = host[4:] if host.startswith('www.') else host
    _rows('SELECT pg_advisory_xact_lock(hashtext(%s),hashtext(%s))',
          (f"reports-supertag:{selected['organization_id']}:{selected['client_id']}", canonical_host))
    candidates = _rows('''SELECT id,organization_id,client_id,public_id,label,allowed_host,enabled,config,
            config_version,created_at,updated_at,revoked_at
        FROM cadu_reports_supertag_sites WHERE organization_id=%s AND client_id=%s
            AND enabled=TRUE AND revoked_at IS NULL ORDER BY created_at DESC''',
        (selected['organization_id'], selected['client_id']))
    site = next((item for item in candidates if _host_allowed(host, item['allowed_host'])), None)
    if site:
        site['snippet'] = _supertag_snippet(site)
        return site, False
    public_id = secrets.token_urlsafe(18).replace('-', 'a').replace('_', 'b')[:24]
    site = _rows('''INSERT INTO cadu_reports_supertag_sites
        (id,organization_id,client_id,public_id,label,allowed_host,config,created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
        RETURNING id,organization_id,client_id,public_id,label,allowed_host,enabled,config,
            config_version,created_at,updated_at,revoked_at''',
        (str(uuid.uuid4()), selected['organization_id'], selected['client_id'], public_id,
         label[:120], host,
         json.dumps({'consent_required': True, 'consent_mode': 'auto', 'audience_days': 90,
                     'retention_days': 90, 'visibility_enabled': True}), session.get('user_id')))[0]
    site['snippet'] = _supertag_snippet(site)
    return site, True


def _fanout_flow_events(site, prepared, page_host):
    """Mirror consented Super Tag events into published flows on the same site."""
    flow_rows = _rows('''SELECT f.id,f.organization_id,f.client_id,f.flow_code,f.config,t.id AS tag_id,t.allowed_host
        FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
        WHERE f.organization_id=%s AND f.client_id=%s AND f.status='published' AND t.revoked_at IS NULL''',
        (site['organization_id'], site['client_id']))
    from .reports_flow_versions import session_snapshot, match_version_step
    for flow in flow_rows:
        if not _host_allowed(page_host, flow['allowed_host']):
            continue
        nodes = (flow.get('config') or {}).get('nodes', [])
        for item in prepared:
            (event_id, _site_id, _org_id, _client_id, visitor_id, session_id, kind,
             event_name, path, referrer, attribution_json, data_json, _width, _height,
             occurred_at) = item
            if kind not in {'page_view', 'page_leave', 'heartbeat', 'click', 'whatsapp_click',
                            'form_submit', 'custom_event', 'conversion'}:
                continue
            # The Flow schema requires a visitor id; when audience identity is absent,
            # preserve session-level aggregation instead of dropping consented events.
            flow_visitor_id = visitor_id or session_id
            quota = _rows('''INSERT INTO cadu_reports_flow_rate_limits (tag_id,bucket_start,event_count)
                VALUES (%s,date_trunc('minute',NOW()),1)
                ON CONFLICT (tag_id,bucket_start) DO UPDATE
                    SET event_count=cadu_reports_flow_rate_limits.event_count+1
                    WHERE cadu_reports_flow_rate_limits.event_count < 1200
                RETURNING event_count''', (flow['tag_id'],))
            if not quota:
                continue
            attribution = json.loads(attribution_json or '{}')
            event_data = json.loads(data_json or '{}')
            safe_path = _safe_path(path)
            snapshot = session_snapshot(flow, session_id)
            step = match_version_step(snapshot, safe_path, page_host, kind, event_name)
            mapped_kind = kind
            if mapped_kind == 'page_view' and step and step.get('step_kind') == 'conversion':
                mapped_kind = 'conversion'
            elif mapped_kind == 'page_view' and step and step.get('step_kind') == 'error':
                mapped_kind = 'error_view'
            campaign_id, method = _campaign_match(
                {'organization_id': flow['organization_id'], 'client_id': flow['client_id']},
                attribution, step)
            duration_ms = event_data.get('duration_ms') if kind == 'page_leave' else None
            _rows('''INSERT INTO cadu_reports_flow_events
                (organization_id,client_id,tag_id,visitor_id,session_id,event_kind,event_name,page_host,page_path,
                 referrer_host,utm_source,utm_medium,utm_campaign,utm_id,click_id,step_id,campaign_id,attribution_method,duration_ms,occurred_at,flow_revision)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (flow['organization_id'], flow['client_id'], flow['tag_id'], flow_visitor_id, session_id,
                 mapped_kind, event_name, page_host, safe_path, referrer,
                 attribution.get('utm_source'), attribution.get('utm_medium'), attribution.get('utm_campaign'),
                 attribution.get('utm_id'), attribution.get('click_id'),
                 step.get('id') if step else None, campaign_id, method, duration_ms, occurred_at,snapshot['published_revision']))


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
        'page_leave': {'duration_ms'}, 'heartbeat': set(),
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
    elif kind == 'page_leave':
        duration_ms = data.get('duration_ms')
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float)) or not 0 <= duration_ms <= 600000:
            abort(400, description='Duração da página inválida.')
        clean_data = {'duration_ms': int(duration_ms)}
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


def _ip_digest():
    """Return a non-reversible per-deployment digest; never trust client XFF here."""
    address = request.remote_addr or ''
    secret = current_app.config.get('SECRET_KEY')
    if not address or not secret:
        abort(503, description='Limite por origem temporariamente indisponível.')
    key = secret.encode() if isinstance(secret, str) else secret
    return hmac.new(key, address.encode(), hashlib.sha256).hexdigest()


def _known_identity_digest(site, campaign_scope, kind, value):
    secret = current_app.config.get('SECRET_KEY')
    if not secret:
        abort(503, description='Identificação temporariamente indisponível.')
    key = secret.encode() if isinstance(secret, str) else secret
    payload = f"supertag:v1:{site['id']}:{campaign_scope}:{kind}:{value}".encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def _branding_metrics(site_id):
    """Aggregate consented sessions without exposing contact or IP identifiers."""
    rows = _rows('''WITH session_events AS (
            SELECT session_id,
                COUNT(*) FILTER (WHERE event_kind='page_view')::bigint AS page_views,
                COUNT(*) FILTER (WHERE event_kind='conversion')::bigint AS conversions,
                COUNT(*) FILTER (WHERE event_kind='form_submit')::bigint AS forms,
                COUNT(*) FILTER (WHERE event_kind='whatsapp_click')::bigint AS whatsapp_clicks,
                COUNT(*) FILTER (WHERE event_kind='page_leave')::bigint AS measured_pages,
                COALESCE(SUM((event_data->>'duration_ms')::integer)
                    FILTER (WHERE event_kind='page_leave'),0)::bigint AS active_ms,
                MAX((event_data->>'depth')::integer)
                    FILTER (WHERE event_kind='scroll_depth') AS deepest_scroll
            FROM cadu_reports_supertag_events
            WHERE site_id=%s AND expires_at>NOW()
                AND occurred_at>=NOW()-INTERVAL '30 days'
            GROUP BY session_id
        ), measured AS (
            SELECT s.campaign_scope,s.visitor_id,s.last_seen_at,e.*
            FROM cadu_reports_supertag_sessions s JOIN session_events e ON e.session_id=s.session_id
            WHERE s.site_id=%s AND s.expires_at>NOW() AND e.page_views>0
        ) SELECT GROUPING(campaign_scope)::integer AS all_campaigns,campaign_scope,
            COUNT(*)::bigint AS sessions,COUNT(DISTINCT visitor_id)::bigint AS visitors,
            COUNT(*) FILTER (WHERE page_views>=2 OR active_ms>=10000 OR conversions>0)::bigint AS engaged_sessions,
            COUNT(*) FILTER (WHERE page_views=1)::bigint AS single_page_sessions,
            COUNT(*) FILTER (WHERE measured_pages>0)::bigint AS measured_sessions,
            COUNT(*) FILTER (WHERE last_seen_at<NOW()-INTERVAL '30 minutes')::bigint AS closed_sessions,
            ROUND(AVG(active_ms) FILTER (WHERE measured_pages>0)/1000,1) AS avg_active_seconds,
            ROUND(AVG(page_views),1) AS avg_pages,
            COUNT(*) FILTER (WHERE deepest_scroll>=75)::bigint AS deep_scroll_sessions,
            SUM(conversions)::bigint AS conversions,SUM(forms)::bigint AS forms,
            SUM(whatsapp_clicks)::bigint AS whatsapp_clicks
        FROM measured GROUP BY GROUPING SETS ((),(campaign_scope))
        ORDER BY all_campaigns DESC,sessions DESC''', (site_id, site_id))
    overall = next((row for row in rows if row['all_campaigns']), None)
    campaigns = [row for row in rows if not row['all_campaigns']]
    cohorts = _rows('''WITH first_visits AS (
            SELECT campaign_scope,visitor_id,MIN(started_at) AS first_at
            FROM cadu_reports_supertag_sessions
            WHERE site_id=%s AND expires_at>NOW()
            GROUP BY campaign_scope,visitor_id
        ), mature AS (
            SELECT f.campaign_scope,f.visitor_id,f.first_at,
                EXISTS (SELECT 1 FROM cadu_reports_supertag_sessions later
                    WHERE later.site_id=%s AND later.campaign_scope=f.campaign_scope
                        AND later.visitor_id=f.visitor_id AND later.expires_at>NOW()
                        AND later.started_at>=f.first_at+INTERVAL '1 day'
                        AND later.started_at<=f.first_at+INTERVAL '7 days') AS returned_7d
            FROM first_visits f
            WHERE f.first_at>=NOW()-INTERVAL '56 days'
                AND f.first_at<NOW()-INTERVAL '7 days'
        ) SELECT campaign_scope,DATE_TRUNC('week',first_at)::date AS cohort_week,
            COUNT(*)::bigint AS visitors,
            COUNT(*) FILTER (WHERE returned_7d)::bigint AS returned_7d
        FROM mature GROUP BY campaign_scope,DATE_TRUNC('week',first_at)::date
        ORDER BY cohort_week DESC,visitors DESC LIMIT 80''', (site_id, site_id))
    return {'overall': overall, 'campaigns': campaigns, 'cohorts': cohorts}


def _bounded_int(value, low, high):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        abort(400, description='Dimensão de viewport inválida.')
    return value


def register(bp):
    @bp.get('/api/v1/reports/supertag/site-check')
    @login_required_api
    def supertag_site_check():
        selected = _selection()
        parsed, host, addresses = _check_site_url(request.args.get('url'))
        response = None
        try:
            response = _pinned_get(parsed.geturl(), addresses, accept='text/html')
            response.max_bytes = SITE_CHECK_MAX_BYTES
            if response.status_code in {301, 302, 303, 307, 308}:
                target = urlparse(response.headers.get('Location') or '')
                if target.hostname and target.hostname.lower().rstrip('.') != host:
                    abort(400, description='O site redireciona para outro domínio; informe a URL final que será autorizada.')
            content_type = response.headers.get('Content-Type', '').lower()
            chunks, size = [], 0
            if 'html' in content_type:
                for chunk in response.iter_content(16_384):
                    size += len(chunk)
                    if size > SITE_CHECK_MAX_BYTES:
                        break
                    chunks.append(chunk)
            html = b''.join(chunks).decode(response.encoding or 'utf-8', errors='replace')
            title, icon = _site_preview(html)
            return jsonify(host=host, status=response.status_code, title=title,
                favicon=urljoin(parsed.geturl(), icon),
                client_id=selected['client_id'])
        except BadRequest:
            raise
        except (OSError, ValueError, urllib3.exceptions.HTTPError):
            abort(400, description='O site não respondeu. Confira a URL e tente novamente.')
        finally:
            if response is not None:
                response.close()

    @bp.after_request
    def supertag_public_cors(response):
        if not request.path.startswith('/connect/public/supertag/v1/'):
            return response
        allowed_host = getattr(request, '_supertag_allowed_host', None)
        origin = request.headers.get('Origin') or ''
        if not allowed_host or not origin:
            return response
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http'):
            return response
        if _host_allowed(parsed.hostname or '', allowed_host):
            response.headers['Access-Control-Allow-Origin'] = f'{parsed.scheme}://{parsed.netloc}'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Access-Control-Max-Age'] = '86400'
            response.headers['Vary'] = 'Origin'
        return response

    @bp.route('/public/supertag/v1/<public_id>/identify', methods=['POST', 'OPTIONS'])
    def supertag_public_identify(public_id):
        site = _site_by_public_id(public_id)
        request._supertag_allowed_host = site['allowed_host']
        origin = request.headers.get('Origin') or ''
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http') or not _host_allowed(parsed.hostname or '', site['allowed_host']):
            abort(403)
        if request.method == 'OPTIONS':
            return ('', 204)
        payload = request.get_json(silent=True) or {}
        allowed = {'visitor_id', 'session_id', 'name', 'email', 'phone', 'campaign', 'consent'}
        if not isinstance(payload, dict) or set(payload) - allowed:
            abort(400, description='Dados de identificação fora do contrato da Super Tag.')
        if payload.get('consent') != 'granted':
            abort(403, description='Consentimento de analytics não confirmado.')
        visitor_id = _uuid(payload.get('visitor_id'), 'Visitante')
        session_id = _uuid(payload.get('session_id'), 'Sessão')
        name = payload.get('name') or ''
        email = payload.get('email') or ''
        phone = payload.get('phone') or ''
        if not isinstance(name, str) or len(name.strip()) > 120:
            abort(400, description='Nome inválido.')
        if not isinstance(email, str) or len(email.strip()) > 254 or (email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip())):
            abort(400, description='E-mail inválido.')
        if not isinstance(phone, str) or len(phone) > 40 or (phone and not re.fullmatch(r'\+?[0-9(). -]{7,40}', phone.strip())):
            abort(400, description='Telefone inválido.')
        normalized_email = email.strip().casefold()
        normalized_phone = re.sub(r'[^0-9+]', '', phone.strip())
        campaign = payload.get('campaign') or ''
        if not isinstance(campaign, str) or len(campaign.strip()) > 160 or '@' in campaign:
            abort(400, description='Campanha inválida.')
        campaign_scope = campaign.strip().casefold()
        if not normalized_email and not normalized_phone:
            abort(400, description='Informe e-mail ou telefone para reconhecer o visitante.')
        kind, value = ('email', normalized_email) if normalized_email else ('phone', normalized_phone)
        identity_digest = _known_identity_digest(site, campaign_scope, kind, value)
        retention_days = (site.get('config') or {}).get('retention_days', 90)
        if isinstance(retention_days, bool) or retention_days not in (30, 60, 90, 180, 365):
            retention_days = 90
        session_row = _rows('''INSERT INTO cadu_reports_supertag_sessions
                (site_id,session_id,visitor_id,ip_digest,started_at,last_seen_at,campaign_scope,expires_at)
            VALUES (%s,%s,%s,%s,NOW(),NOW(),%s,NOW() + (%s * INTERVAL '1 day'))
            ON CONFLICT (site_id,session_id) DO UPDATE SET
                ip_digest=NULL,last_seen_at=NOW(),expires_at=EXCLUDED.expires_at,
                campaign_scope=COALESCE(NULLIF(cadu_reports_supertag_sessions.campaign_scope,''),EXCLUDED.campaign_scope)
            RETURNING visitor_id''', (site['id'], session_id, visitor_id, _ip_digest(), campaign_scope, retention_days))
        if str(session_row[0]['visitor_id']) != visitor_id:
            abort(409, description='A sessão não corresponde ao visitante atual.')
        ip_quota = _rows('''INSERT INTO cadu_reports_supertag_ip_rate_limits
                (site_id,ip_digest,bucket_start,event_count)
            VALUES (%s,%s,date_trunc('minute',NOW()),1)
            ON CONFLICT (site_id,ip_digest,bucket_start) DO UPDATE
                SET event_count=cadu_reports_supertag_ip_rate_limits.event_count+1
                WHERE cadu_reports_supertag_ip_rate_limits.event_count < %s
            RETURNING event_count''', (site['id'], _ip_digest(), MAX_IP_EVENTS_PER_MINUTE))
        if not ip_quota:
            abort(429, description='Limite temporário de identificação atingido para esta origem.')
        identity = _rows('''INSERT INTO cadu_reports_supertag_known_visitors
                (id,site_id,campaign_scope,identity_digest,identity_kind,display_name,expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,NOW() + (%s * INTERVAL '1 day'))
            ON CONFLICT (site_id,campaign_scope,identity_digest) DO UPDATE SET
                identity_kind=EXCLUDED.identity_kind,
                display_name=COALESCE(NULLIF(EXCLUDED.display_name,''),cadu_reports_supertag_known_visitors.display_name),
                expires_at=EXCLUDED.expires_at,updated_at=NOW()
            RETURNING id''', (str(uuid.uuid4()), site['id'], campaign_scope,
                identity_digest, kind, ' '.join(name.split()), retention_days))[0]
        _rows('''INSERT INTO cadu_reports_supertag_visitor_sessions
                (site_id,session_id,campaign_scope,visitor_id,known_visitor_id,expires_at)
            VALUES (%s,%s,%s,%s,%s,NOW() + (%s * INTERVAL '1 day'))
            ON CONFLICT (site_id,session_id,campaign_scope) DO UPDATE SET
                visitor_id=EXCLUDED.visitor_id,known_visitor_id=EXCLUDED.known_visitor_id,
                expires_at=EXCLUDED.expires_at,last_seen_at=NOW()''',
            (site['id'], session_id, campaign_scope, visitor_id, identity['id'], retention_days))
        _rows('''UPDATE cadu_reports_supertag_sessions SET ip_digest=NULL
            WHERE site_id=%s AND session_id=%s''', (site['id'], session_id))
        get_db().commit()
        return jsonify(identified=True), 200

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
              ON e.site_id=s.id AND e.expires_at > NOW() AND e.occurred_at >= NOW() - INTERVAL '30 days'
            WHERE s.organization_id=%s AND s.client_id=%s
            GROUP BY s.id ORDER BY s.created_at DESC''', params)
        base = _base_url()
        for site in sites:
            site['script_url'] = f'{base}/v1/supertag.js'
            site['snippet'] = (f'<script async src="{site["script_url"]}" '
                f'data-cadu-site="{site["public_id"]}" '
                f'data-cadu-config="{base}/connect/public/supertag/v1/{site["public_id"]}/config.json" '
                f'data-cadu-consent="{(site.get("config") or {}).get("consent_mode", "auto")}"></script>')
        return jsonify(sites=sites)

    @bp.post('/api/v1/reports/supertag/sites')
    @login_required_api
    def supertag_site_create():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict) or set(payload) - {'label', 'allowed_host', 'client_id'} or not {'label', 'allowed_host'} <= set(payload):
            abort(400, description='Informe o nome da instalação e o domínio permitido.')
        selected = _selection(payload)
        _write_guard(selected)
        label = ' '.join(str(payload['label'] or '').split())[:120]
        if not label:
            abort(400, description='Informe o nome da instalação.')
        host = _host(payload['allowed_host'])
        site, created = ensure_supertag_site(selected, host, label)
        get_db().commit()
        base = _base_url()
        site['script_url'] = f'{base}/v1/supertag.js'
        return jsonify(site=site, reused=not created), 201 if created else 200

    @bp.patch('/api/v1/reports/supertag/sites/<uuid:site_id>')
    @login_required_api
    def supertag_site_update(site_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict) or set(payload) - {'label', 'allowed_host', 'visibility_enabled', 'audience_days', 'retention_days', 'consent_mode', 'client_id'}:
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
        if 'consent_mode' in payload:
            if payload['consent_mode'] not in ('auto', 'manual'):
                abort(400, description='Escolha o modo de consentimento disponível.')
            config['consent_mode'] = payload['consent_mode']
        if 'visibility_enabled' in payload:
            if not isinstance(payload['visibility_enabled'], bool):
                abort(400, description='Informe se a coleta de visibilidade está ativa.')
            config['visibility_enabled'] = payload['visibility_enabled']
        if 'audience_days' in payload:
            if isinstance(payload['audience_days'], bool) or payload['audience_days'] not in (30, 60, 90, 180, 365):
                abort(400, description='Escolha uma retenção entre 30 e 365 dias.')
            config['audience_days'] = payload['audience_days']
        if 'retention_days' in payload:
            if isinstance(payload['retention_days'], bool) or payload['retention_days'] not in (30, 60, 90, 180, 365):
                abort(400, description='Escolha a retenção dos eventos entre 30 e 365 dias.')
            config['retention_days'] = payload['retention_days']
        updated = _rows('''UPDATE cadu_reports_supertag_sites SET label=%s,allowed_host=%s,
            config=%s::jsonb,config_version=config_version+1,updated_at=NOW()
            WHERE id=%s RETURNING id,public_id,label,allowed_host,enabled,config,config_version,created_at,updated_at,revoked_at''',
            (label, host, json.dumps(config), str(site_id)))[0]
        get_db().commit()
        base = _base_url()
        updated['script_url'] = f'{base}/v1/supertag.js'
        updated['snippet'] = (f'<script async src="{updated["script_url"]}" data-cadu-site="{updated["public_id"]}" '
            f'data-cadu-config="{base}/connect/public/supertag/v1/{updated["public_id"]}/config.json" '
            f'data-cadu-consent="{config.get("consent_mode", "auto")}"></script>')
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
        request._supertag_allowed_host = site['allowed_host']
        origin = request.headers.get('Origin') or ''
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http') or not _host_allowed(parsed.hostname or '', site['allowed_host']):
            abort(403)
        response = make_response(jsonify(site_id=site['public_id'], config_version=site['config_version'],
            consent_required=True, consent_mode=(site.get('config') or {}).get('consent_mode', 'auto'),
            visibility_enabled=(site.get('config') or {}).get('visibility_enabled', True),
            audience_days=(site.get('config') or {}).get('audience_days', 90)))
        response.headers['Cache-Control'] = 'public, max-age=300, stale-while-revalidate=3600'
        response.set_etag(f'{site["public_id"]}:{site["config_version"]}')
        return response.make_conditional(request)

    @bp.route('/public/supertag/v1/<public_id>/consent', methods=['POST', 'OPTIONS'])
    def supertag_public_consent(public_id):
        site = _site_by_public_id(public_id)
        request._supertag_allowed_host = site['allowed_host']
        origin = request.headers.get('Origin') or ''
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http') or not _host_allowed(parsed.hostname or '', site['allowed_host']):
            abort(403)
        if request.method == 'OPTIONS':
            return ('', 204)
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict) or set(payload) != {'analytics'} or not isinstance(payload['analytics'], bool):
            abort(400, description='Informe uma escolha válida para analytics.')
        response = make_response(jsonify(analytics=payload['analytics']))
        response.headers['Cache-Control'] = 'no-store'
        return response

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
        request._supertag_allowed_host = site['allowed_host']
        origin = request.headers.get('Origin') or ''
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http') or not _host_allowed(parsed.hostname or '', site['allowed_host']):
            abort(403)
        prepared = [_event(item, site) for item in events]
        ip_digest = _ip_digest()
        retention_days = (site.get('config') or {}).get('retention_days', 90)
        if isinstance(retention_days, bool) or retention_days not in (30, 60, 90, 180, 365):
            retention_days = 90
        conn = get_db()
        try:
            for event_id in sorted(str(item[0]) for item in prepared):
                _rows('SELECT pg_advisory_xact_lock(hashtext(%s),hashtext(%s))',
                      (str(site['id']), event_id))
            existing_events = _rows('''SELECT event_id FROM cadu_reports_supertag_events
                WHERE site_id=%s AND event_id = ANY(%s::uuid[])''',
                (site['id'], [item[0] for item in prepared]))
            existing_ids = {str(item['event_id']) for item in existing_events}
            new_events = []
            for item in prepared:
                event_id = str(item[0])
                if event_id not in existing_ids:
                    new_events.append(item)
                    existing_ids.add(event_id)
            quota = _rows('''INSERT INTO cadu_reports_supertag_rate_limits (site_id,bucket_start,event_count)
                VALUES (%s,date_trunc('minute',NOW()),%s)
                ON CONFLICT (site_id,bucket_start) DO UPDATE
                    SET event_count=cadu_reports_supertag_rate_limits.event_count+EXCLUDED.event_count
                    WHERE cadu_reports_supertag_rate_limits.event_count+EXCLUDED.event_count <= %s
                RETURNING event_count''', (site['id'], len(prepared), MAX_SITE_EVENTS_PER_MINUTE))
            if not quota:
                abort(429, description='Limite temporário desta instalação excedido.')
            ip_quota = _rows('''INSERT INTO cadu_reports_supertag_ip_rate_limits
                    (site_id,ip_digest,bucket_start,event_count)
                VALUES (%s,%s,date_trunc('minute',NOW()),%s)
                ON CONFLICT (site_id,ip_digest,bucket_start) DO UPDATE
                    SET event_count=cadu_reports_supertag_ip_rate_limits.event_count+EXCLUDED.event_count
                    WHERE cadu_reports_supertag_ip_rate_limits.event_count+EXCLUDED.event_count <= %s
                RETURNING event_count''', (site['id'], ip_digest, len(prepared), MAX_IP_EVENTS_PER_MINUTE))
            if not ip_quota:
                abort(429, description='Limite temporário de envio atingido para esta origem.')
            with conn.cursor() as cursor:
                cursor.executemany('''INSERT INTO cadu_reports_supertag_events
                    (event_id,site_id,organization_id,client_id,visitor_id,session_id,event_kind,event_name,
                     page_path,referrer_host,attribution,event_data,viewport_width,viewport_height,occurred_at,expires_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,
                        NOW() + (%s * INTERVAL '1 day'))
                    ON CONFLICT (site_id,event_id) DO NOTHING''',
                    [(*event, retention_days) for event in prepared])
                session_rollup = {}
                for event in prepared:
                    session_id, visitor_id, occurred_at = event[5], event[4] or event[5], event[14]
                    attribution = json.loads(event[10] or '{}')
                    campaign_scope = (attribution.get('utm_id') or attribution.get('utm_campaign') or '').strip().casefold()
                    current = session_rollup.get(session_id)
                    if current:
                        current[2] = min(current[2], occurred_at)
                        current[3] = max(current[3], occurred_at)
                        if not current[4] and campaign_scope:
                            current[4] = campaign_scope
                    else:
                        session_rollup[session_id] = [visitor_id, ip_digest, occurred_at, occurred_at, campaign_scope]
                cursor.executemany('''INSERT INTO cadu_reports_supertag_sessions
                        (site_id,session_id,visitor_id,ip_digest,started_at,last_seen_at,campaign_scope,expires_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,NOW() + (%s * INTERVAL '1 day'))
                    ON CONFLICT (site_id,session_id) DO UPDATE SET
                        visitor_id=EXCLUDED.visitor_id,
                        campaign_scope=COALESCE(NULLIF(cadu_reports_supertag_sessions.campaign_scope,''),EXCLUDED.campaign_scope),
                        ip_digest=CASE WHEN EXISTS (
                            SELECT 1 FROM cadu_reports_supertag_visitor_sessions vs
                            WHERE vs.site_id=EXCLUDED.site_id AND vs.session_id=EXCLUDED.session_id
                              AND vs.expires_at > NOW()) THEN NULL ELSE EXCLUDED.ip_digest END,
                        started_at=LEAST(cadu_reports_supertag_sessions.started_at,EXCLUDED.started_at),
                        last_seen_at=GREATEST(cadu_reports_supertag_sessions.last_seen_at,EXCLUDED.last_seen_at),
                        expires_at=EXCLUDED.expires_at''',
                    [(site['id'], str(session_id), str(visitor_id), digest, started, latest, campaign, retention_days)
                     for session_id, (visitor_id, digest, started, latest, campaign) in session_rollup.items()])
            _fanout_flow_events(site, new_events, parsed.hostname.lower().rstrip('.'))
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
            FROM cadu_reports_supertag_events WHERE site_id=%s AND expires_at > NOW()
              AND occurred_at >= NOW() - INTERVAL '30 days' GROUP BY event_kind ORDER BY event_kind''',
            (str(site_id),))
        pages = _rows('''WITH latest_page AS (
                SELECT DISTINCT ON (session_id) session_id,page_path
                FROM cadu_reports_supertag_events
                WHERE site_id=%s AND expires_at>NOW()
                    AND occurred_at>=NOW()-INTERVAL '30 days' AND event_kind='page_view'
                ORDER BY session_id,occurred_at DESC,id DESC
            ), exits AS (
                SELECT p.page_path,COUNT(*)::bigint AS total
                FROM latest_page p JOIN cadu_reports_supertag_sessions s
                    ON s.site_id=%s AND s.session_id=p.session_id
                WHERE s.expires_at>NOW() AND s.last_seen_at<NOW()-INTERVAL '30 minutes'
                GROUP BY p.page_path
            ) SELECT e.page_path,
                COUNT(*) FILTER (WHERE e.event_kind='page_view')::bigint AS views,
                COALESCE(MAX(x.total),0)::bigint AS exits,
                COUNT(*) FILTER (WHERE e.event_kind='form_submit')::bigint AS form_submissions,
                COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click'))::bigint AS clicks,
                COUNT(*) FILTER (WHERE e.event_kind='conversion')::bigint AS conversions,
                COUNT(*) FILTER (WHERE e.event_kind='visibility')::bigint AS visibility_events,
                COUNT(*) FILTER (WHERE e.event_kind='scroll_depth')::bigint AS scroll_events,
                ROUND(AVG((e.event_data->>'duration_ms')::integer)
                    FILTER (WHERE e.event_kind='page_leave')/1000,1) AS avg_active_seconds,
                COUNT(*) FILTER (WHERE e.event_kind='page_leave')::bigint AS measured_visits
            FROM cadu_reports_supertag_events e LEFT JOIN exits x ON x.page_path=e.page_path
            WHERE e.site_id=%s AND e.expires_at>NOW()
                AND e.occurred_at>=NOW()-INTERVAL '30 days'
            GROUP BY e.page_path ORDER BY views DESC LIMIT 100''',
            (str(site_id),str(site_id),str(site_id)))
        sessions = _rows('''WITH session_campaign AS (
                SELECT site_id,session_id,COALESCE((ARRAY_AGG(TRIM(LOWER(COALESCE(
                        NULLIF(attribution->>'utm_id',''),NULLIF(attribution->>'utm_campaign',''),'')))
                    ORDER BY occurred_at,id) FILTER (WHERE event_kind='page_view'))[1],'') AS campaign_scope
                FROM cadu_reports_supertag_events
                WHERE site_id=%s AND expires_at > NOW()
                  AND occurred_at >= NOW() - INTERVAL '30 days'
                GROUP BY site_id,session_id
            ) SELECT e.session_id,
                MIN(e.visitor_id) FILTER (WHERE e.visitor_id IS NOT NULL) AS visitor_id,
                MIN(e.occurred_at) AS started_at,MAX(e.occurred_at) AS last_activity_at,
                COUNT(*)::bigint AS event_count,
                CASE WHEN MAX(session_state.last_seen_at)<NOW()-INTERVAL '30 minutes' THEN
                    (ARRAY_AGG(e.page_path ORDER BY e.occurred_at DESC,e.id DESC)
                        FILTER (WHERE e.event_kind='page_view'))[1] END AS exit_page,
                COALESCE(NULLIF(session_campaign.campaign_scope,''),'Sem campanha') AS campaign,
                CASE WHEN %s THEN known.display_name END AS known_name,known.identity_kind,
                JSONB_AGG(JSONB_BUILD_OBJECT('kind',e.event_kind,'page',e.page_path,
                    'occurred_at',e.occurred_at,'duration_ms',e.event_data->>'duration_ms')
                    ORDER BY e.occurred_at,e.id)
                    FILTER (WHERE e.event_kind IN ('page_view','page_leave','form_submit','conversion')) AS journey
            FROM cadu_reports_supertag_events e
            JOIN cadu_reports_supertag_sessions session_state
              ON session_state.site_id=e.site_id AND session_state.session_id=e.session_id
            JOIN session_campaign ON session_campaign.site_id=e.site_id
              AND session_campaign.session_id=e.session_id
            LEFT JOIN cadu_reports_supertag_visitor_sessions known_session
              ON known_session.site_id=e.site_id AND known_session.session_id=e.session_id
              AND known_session.campaign_scope=session_campaign.campaign_scope
              AND known_session.expires_at > NOW()
            LEFT JOIN cadu_reports_supertag_known_visitors known
              ON known.id=known_session.known_visitor_id AND known.site_id=e.site_id
              AND known.expires_at > NOW()
            WHERE e.site_id=%s AND e.expires_at > NOW()
              AND e.occurred_at >= NOW() - INTERVAL '30 days'
            GROUP BY e.session_id,session_campaign.campaign_scope,known.display_name,known.identity_kind
            ORDER BY MAX(e.occurred_at) DESC LIMIT 100''',
            (str(site_id),selected['role'] != 'viewer',str(site_id)))
        known_sessions = _rows('''WITH session_campaign AS (
                SELECT site_id,session_id,COALESCE((ARRAY_AGG(TRIM(LOWER(COALESCE(
                        NULLIF(attribution->>'utm_id',''),NULLIF(attribution->>'utm_campaign',''),'')))
                    ORDER BY occurred_at,id) FILTER (WHERE event_kind='page_view'))[1],'') AS campaign_scope
                FROM cadu_reports_supertag_events
                WHERE site_id=%s AND expires_at > NOW()
                  AND occurred_at >= NOW() - INTERVAL '30 days'
                GROUP BY site_id,session_id
            ) SELECT COUNT(DISTINCT e.session_id)::bigint AS total
            FROM cadu_reports_supertag_events e
            JOIN session_campaign ON session_campaign.site_id=e.site_id
              AND session_campaign.session_id=e.session_id
            JOIN cadu_reports_supertag_visitor_sessions vs
              ON vs.site_id=e.site_id AND vs.session_id=e.session_id
              AND vs.campaign_scope=session_campaign.campaign_scope AND vs.expires_at > NOW()
            JOIN cadu_reports_supertag_known_visitors kv
              ON kv.id=vs.known_visitor_id AND kv.site_id=e.site_id AND kv.expires_at > NOW()
            WHERE e.site_id=%s AND e.expires_at > NOW()
              AND e.occurred_at >= NOW() - INTERVAL '30 days' ''', (str(site_id),str(site_id)))[0]['total']
        heatmap = _rows('''SELECT page_path,event_kind,event_data->>'element_id' AS element_id,
                CASE WHEN event_kind IN ('click','whatsapp_click')
                    THEN (floor(LEAST((event_data->>'x')::numeric,999) / 50) * 50)::integer END AS x,
                CASE WHEN event_kind IN ('click','whatsapp_click')
                    THEN (floor(LEAST((event_data->>'y')::numeric,999) / 50) * 50)::integer END AS y,
                event_data->>'ratio' AS ratio,
                event_data->>'depth' AS depth,COUNT(*)::bigint AS total
            FROM cadu_reports_supertag_events WHERE site_id=%s AND expires_at > NOW()
              AND occurred_at >= NOW() - INTERVAL '30 days'
              AND event_kind IN ('click','whatsapp_click','visibility','scroll_depth')
            GROUP BY page_path,event_kind,event_data->>'element_id',
                CASE WHEN event_kind IN ('click','whatsapp_click')
                    THEN (floor(LEAST((event_data->>'x')::numeric,999) / 50) * 50)::integer END,
                CASE WHEN event_kind IN ('click','whatsapp_click')
                    THEN (floor(LEAST((event_data->>'y')::numeric,999) / 50) * 50)::integer END,
                event_data->>'ratio',event_data->>'depth' ORDER BY total DESC LIMIT 500''', (str(site_id),))
        return jsonify(site=site[0], summary=summary, pages=pages, sessions=sessions,
                       known_sessions=known_sessions, heatmap=heatmap,
                       branding=_branding_metrics(str(site_id)))
