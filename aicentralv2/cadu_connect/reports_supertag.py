"""Independent public Cadu Super Tag configuration and event collection."""
import json
import codecs
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
from werkzeug.exceptions import BadRequest, HTTPException

from ..auth import login_required_api
from ..db import get_db
from ..cadu_workspace.brand_site_inspector import (
    _public_addresses,
    _pinned_get,
    normalize_public_url,
)
from .reports_flow import _campaign_match, _host_allowed, _safe_path
from .reports_v1 import _rows, _selection, _write_guard
from . import reports_supertag_leads as leads

# Browsers cap first-party cookies at ~400 days, so the identifier stops at 395; event retention has no such cap.
AUDIENCE_DAYS_CHOICES = (30, 60, 90, 180, 365, 395)
RETENTION_DAYS_CHOICES = (30, 60, 90, 180, 365, 730, 1095, 1825)
DEFAULT_AUDIENCE_DAYS = 365
DEFAULT_RETENTION_DAYS = 365
MAX_BATCH_EVENTS = 25
MAX_BATCH_BYTES = 32 * 1024
MAX_SITE_EVENTS_PER_MINUTE = 10_000
MAX_IP_EVENTS_PER_MINUTE = 1_000
EVENT_KINDS = {'page_view', 'page_leave', 'heartbeat', 'click', 'whatsapp_click', 'form_submit',
               'visibility', 'scroll_depth', 'custom_event', 'conversion',
               'outbound_click', 'file_download', 'contact_click', 'video'}
# Enhanced measurement, like a GA4 data stream: one switch per automatic event family, all on by default (and for
# configs saved before the switches existed). `page_changes` only steers the tag (SPA page views look like any other).
ENHANCED_KEYS = ('page_changes', 'scroll', 'clicks', 'outbound', 'contacts', 'downloads', 'forms', 'video')
ENHANCED_BY_KIND = {'scroll_depth': 'scroll', 'click': 'clicks', 'outbound_click': 'outbound', 'contact_click': 'contacts',
                    'whatsapp_click': 'contacts', 'file_download': 'downloads', 'form_submit': 'forms', 'video': 'video'}
CLICK_DATA = {'x', 'y', 'element_id', 'dx', 'dy', 'dh'}
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


def _html_charset(content_type):
    match = re.search(r'charset\s*=\s*["\']?([A-Za-z0-9._-]+)', content_type or '', re.I)
    if match:
        try:
            return codecs.lookup(match.group(1)).name
        except LookupError:
            pass
    return 'utf-8'


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


def _snippet_title(site):
    """Name shown in the HTML comments around the snippet. A comment cannot hold "--" nor end in "-", and "<"/">" are
    dropped so a pasted label never breaks the comment or the page around it."""
    host = str(site.get('allowed_host') or '')
    label = ' '.join(str(site.get('label') or '').split())
    name = f'{label} ({host})' if label and host and label.casefold() != host.casefold() else (label or host)
    name = re.sub(r'[<>\x00-\x1f]', '', name)
    while '--' in name:
        name = name.replace('--', '-')
    name = name.strip(' -')[:120].rstrip(' -')
    return f'Cadu Super Tag · {name}' if name else 'Cadu Super Tag'


def _wrap_snippet(site, body):
    return f'<!-- {_snippet_title(site)} -->\n{body}\n<!-- End Cadu Super Tag -->'


def _supertag_snippet(site):
    """One tag, like GA4: the tag finds its config next to its own URL. Old snippets with data-cadu-config still work."""
    return _wrap_snippet(site, f'<script async src="{_base_url()}/v1/supertag.js" data-cadu-site="{site["public_id"]}"></script>')


def _supertag_gtm_snippet(site):
    """Custom HTML for Google Tag Manager: the same tag, injected by a tiny ES5 loader (GTM's editor rejects newer syntax).
    The id travels in data-cadu-site and in ?id= so the tag finds itself even if GTM rewrites the element."""
    public_id = site['public_id']
    source = f'{_base_url()}/v1/supertag.js?id={public_id}'
    loader = ('<script>\n(function (d) {\n'
              "  var s = d.createElement('script');\n"
              '  s.async = true;\n'
              f"  s.src = '{source}';\n"
              f"  s.setAttribute('data-cadu-site', '{public_id}');\n"
              "  (d.head || d.getElementsByTagName('head')[0]).appendChild(s);\n"
              '})(document);\n</script>')
    return _wrap_snippet(site, loader)


def _with_snippets(site):
    site['snippet'] = _supertag_snippet(site)
    site['snippet_gtm'] = _supertag_gtm_snippet(site)
    return site


def enhanced_settings(config):
    """Every switch resolved to a bool; a missing key (or a config older than the switches) means on."""
    saved = (config or {}).get('enhanced')
    saved = saved if isinstance(saved, dict) else {}
    return {key: saved.get(key) is not False for key in ENHANCED_KEYS}


def validate_enhanced(value):
    if not isinstance(value, dict) or not value or set(value) - set(ENHANCED_KEYS) or \
            any(not isinstance(item, bool) for item in value.values()):
        abort(400, description='Medição aprimorada inválida: use ligado ou desligado para cada item.')
    return dict(value)


def _event_params(data, clean_data):
    """Optional numeric value and currency of CaduSuperTag.event(name, {value, currency}); nothing else."""
    if 'value' in data:
        value = data['value']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1_000_000_000:
            abort(400, description='Valor do evento inválido.')
        clean_data['value'] = round(float(value), 2)
    if 'currency' in data:
        if not isinstance(data['currency'], str) or not re.fullmatch(r'[A-Z]{3}', data['currency']):
            abort(400, description='Moeda do evento inválida.')
        clean_data['currency'] = data['currency']


def ensure_supertag_site(selected, host, label):
    """Reuse or create the one browser installation shared by this client's flows."""
    canonical_host = host[4:] if host.startswith('www.') else host
    _rows('SELECT pg_advisory_xact_lock(hashtext(%s),hashtext(%s))',
          (f"reports-supertag:{selected['client_id']}", canonical_host))
    candidates = _rows('''SELECT id,client_id,public_id,label,allowed_host,enabled,config,
            config_version,created_at,updated_at,revoked_at
        FROM cadu_reports_supertag_sites WHERE client_id=%s
            AND enabled=TRUE AND revoked_at IS NULL ORDER BY created_at DESC''',
        (selected['client_id'],))
    site = next((item for item in candidates if _host_allowed(host, item['allowed_host'])), None)
    if site:
        _with_snippets(site)
        return site, False
    public_id = secrets.token_urlsafe(18).replace('-', 'a').replace('_', 'b')[:24]
    site = _rows('''INSERT INTO cadu_reports_supertag_sites
        (id,client_id,public_id,label,allowed_host,config,created_by)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
        RETURNING id,client_id,public_id,label,allowed_host,enabled,config,
            config_version,created_at,updated_at,revoked_at''',
        (str(uuid.uuid4()), selected['client_id'], public_id,
         label[:120], host,
         json.dumps({'audience_days': 90, 'retention_days': 90, 'visibility_enabled': True}),
         session.get('user_id')))[0]
    _with_snippets(site)
    return site, True


def _flow_listens_to(flow, site, nodes, page_host):
    if flow.get('site_id') == site['id'] and _host_allowed(page_host, flow['allowed_host']):
        return True
    return any(node.get('host') and _host_allowed(page_host, node['host']) and _host_allowed(node['host'], site['allowed_host'])
               for node in nodes if isinstance(node, dict))


def _fanout_flow_events(site, prepared, page_host):
    """Mirror Super Tag events into published flows on the same site."""
    flow_rows = _rows('''SELECT f.id,f.client_id,f.site_id,f.flow_code,f.config,t.id AS tag_id,t.allowed_host
        FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
        WHERE f.client_id=%s AND f.status='published' AND t.revoked_at IS NULL''',
        (site['client_id'],))
    from .reports_flow_versions import session_snapshot, match_version_step
    for flow in flow_rows:
        nodes = (flow.get('config') or {}).get('nodes', [])
        # A flow listens to its own site and to any other installation of the client that one of its steps lives on.
        if not _flow_listens_to(flow, site, nodes, page_host):
            continue
        for item in prepared:
            (event_id, _site_id, _client_id, visitor_id, session_id, kind,
             event_name, path, referrer, attribution_json, data_json, _width, _height,
             occurred_at) = item
            if kind == 'scroll_depth':
                # Landing pages measure "read half the page" as an in-page step. Mirror it only when
                # the flow has that step on this path, so ordinary scrolling never inflates flow events.
                depth = (json.loads(data_json or '{}') or {}).get('depth')
                if not isinstance(depth, (int, float)) or depth < 50 or not any(
                        node.get('event_name') == 'scroll_depth' and node.get('path') == _safe_path(path) for node in nodes):
                    continue
                kind, event_name = 'custom_event', 'scroll_depth'
            if kind not in {'page_view', 'page_leave', 'heartbeat', 'click', 'whatsapp_click',
                            'form_submit', 'custom_event', 'conversion'}:
                continue
            # The Flow schema requires a visitor id; when audience identity is absent,
            # preserve session-level aggregation instead of dropping events.
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
                {'client_id': flow['client_id']},
                attribution, step)
            duration_ms = event_data.get('duration_ms') if kind == 'page_leave' else None
            _rows('''INSERT INTO cadu_reports_flow_events
                (client_id,tag_id,visitor_id,session_id,event_kind,event_name,page_host,page_path,referrer_host,utm_source,utm_medium,utm_campaign,utm_id,click_id,step_id,campaign_id,attribution_method,duration_ms,occurred_at,flow_revision,source_event_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                (flow['client_id'], flow['tag_id'], flow_visitor_id, session_id,
                 mapped_kind, event_name, page_host, safe_path, referrer,
                 attribution.get('utm_source'), attribution.get('utm_medium'), attribution.get('utm_campaign'),
                 attribution.get('utm_id'), attribution.get('click_id'),
                 step.get('id') if step else None, campaign_id, method, duration_ms, occurred_at,snapshot['published_revision'],event_id))


def _base_url():
    return str(current_app.config.get('CONNECT_URL') or request.url_root).rstrip('/')


def _site_by_public_id(public_id):
    found = _rows('''SELECT id,client_id,public_id,label,allowed_host,
            enabled,config,config_version,created_at,updated_at,revoked_at
        FROM cadu_reports_supertag_sites WHERE public_id=%s AND enabled=TRUE AND revoked_at IS NULL''',
        (public_id,))
    if not found:
        abort(404)
    return found[0]


def _event(raw, site):
    # `consent` is still accepted (and ignored) because cached copies of the old tag keep sending it.
    if not isinstance(raw, dict) or set(raw) - {
            'event_id', 'visitor_id', 'session_id', 'kind', 'event_name', 'path', 'referrer_host',
            'attribution', 'data', 'viewport_width', 'viewport_height', 'occurred_at', 'consent'}:
        abort(400, description='Evento fora do contrato público da Super Tag.')
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
        'click': CLICK_DATA, 'whatsapp_click': CLICK_DATA,
        'visibility': {'element_id', 'ratio'}, 'scroll_depth': {'depth'},
        'form_submit': {'form_id', 'valid'}, 'custom_event': {'value', 'currency'}, 'conversion': {'value', 'currency'},
        'page_view': set(), 'page_leave': {'duration_ms'}, 'heartbeat': set(),
        'outbound_click': {'link_host'}, 'file_download': {'file_ext', 'link_host'}, 'contact_click': {'channel'},
        'video': {'action', 'percent'},
    }[kind]
    if set(data) - allowed_data:
        abort(400, description='Metadados não permitidos. Valores de campos não podem ser enviados.')
    # A switch turned off in the panel wins over a tag that still runs with a cached config: the event is dropped
    # (counted as rejected). A WhatsApp click without the contacts switch still feeds the click map as a plain click.
    enhanced = enhanced_settings(site.get('config'))
    switch = ENHANCED_BY_KIND.get(kind)
    if switch and not enhanced[switch]:
        if kind == 'whatsapp_click' and enhanced['clicks']:
            kind = 'click'
        else:
            abort(400, description='Medição desativada para este site.')
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
        # Contract v2: position inside the whole document (per-mille of its width/height) and the document height in px.
        # All three travel together or not at all; tags without them keep working and only feed the first-screen map.
        document = {key: data.get(key) for key in ('dx', 'dy', 'dh') if key in data}
        if document:
            if set(document) != {'dx', 'dy', 'dh'}:
                abort(400, description='Posição no documento incompleta.')
            for axis in ('dx', 'dy'):
                value = document[axis]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1000:
                    abort(400, description='Posição do clique no documento inválida.')
                clean_data[axis] = int(value)
            height = document['dh']
            if isinstance(height, bool) or not isinstance(height, (int, float)) or not 1 <= height <= 100000:
                abort(400, description='Altura do documento inválida.')
            clean_data['dh'] = int(height)
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
        if 'valid' in data:
            if not isinstance(data['valid'], bool):
                abort(400, description='Validade do formulário inválida.')
            clean_data['valid'] = data['valid']
    elif kind in ('custom_event', 'conversion'):
        _event_params(data, clean_data)
    elif kind in ('outbound_click', 'file_download'):
        # Only the host of the link: never its path, query string or fragment.
        link_host = data.get('link_host')
        if link_host is not None:
            if not isinstance(link_host, str) or len(link_host) > 253 or '@' in link_host:
                abort(400, description='Destino do link inválido.')
            clean_data['link_host'] = _host(link_host)
        elif kind == 'outbound_click':
            abort(400, description='Informe o domínio do link externo.')
        if kind == 'file_download' and data.get('file_ext') is not None:
            if not isinstance(data['file_ext'], str) or not re.fullmatch(r'[a-z0-9]{1,8}', data['file_ext']):
                abort(400, description='Tipo de arquivo inválido.')
            clean_data['file_ext'] = data['file_ext']
    elif kind == 'contact_click':
        # The channel only: the number or address of the link never leaves the browser.
        if data.get('channel') not in ('phone', 'email', 'whatsapp'):
            abort(400, description='Canal de contato inválido.')
        clean_data['channel'] = data['channel']
    elif kind == 'video':
        action, percent = data.get('action'), data.get('percent')
        if action not in ('start', 'progress', 'complete'):
            abort(400, description='Ação de vídeo inválida.')
        if action == 'progress':
            if isinstance(percent, bool) or percent not in (25, 50, 75):
                abort(400, description='Progresso do vídeo inválido.')
            clean_data = {'action': action, 'percent': percent}
        elif percent is not None:
            abort(400, description='Progresso só vale para a ação progress.')
        else:
            clean_data = {'action': action}
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
        _uuid(raw.get('event_id'), 'Evento'), site['id'], site['client_id'],
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
    """Aggregate sessions without exposing contact or IP identifiers."""
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
    @bp.get('/api/v2/reports/supertag/site-check')
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
                abort(400, description='O endereço redireciona; informe a URL final do site.')
            if response.status_code >= 400:
                abort(400, description=f'O site respondeu HTTP {response.status_code}. Confira a URL e tente novamente.')
            content_type = response.headers.get('Content-Type', '').lower()
            chunks, size = [], 0
            if 'html' in content_type:
                for chunk in response.iter_content(16_384):
                    size += len(chunk)
                    if size > SITE_CHECK_MAX_BYTES:
                        break
                    chunks.append(chunk)
            html = b''.join(chunks).decode(_html_charset(content_type), errors='replace')
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

    @bp.get('/api/v2/reports/supertag/sites/<uuid:site_id>/verify-install')
    @login_required_api
    def supertag_verify_install(site_id):
        """Looks for the tag in the site's HTML. A tag injected by GTM is invisible here, so absence is not failure."""
        selected = _selection()
        found = _rows('''SELECT public_id,allowed_host FROM cadu_reports_supertag_sites
            WHERE id=%s AND client_id=%s AND revoked_at IS NULL''', (str(site_id), selected['client_id']))
        if not found:
            abort(404)
        site = found[0]
        parsed, host, addresses = _check_site_url(f"https://{site['allowed_host']}/")
        response = None
        try:
            response = _pinned_get(parsed.geturl(), addresses, accept='text/html')
            response.max_bytes = SITE_CHECK_MAX_BYTES
            reachable = response.status_code < 400
            html = ''
            if reachable and 'html' in response.headers.get('Content-Type', '').lower():
                chunks, size = [], 0
                for chunk in response.iter_content(16_384):
                    size += len(chunk)
                    if size > SITE_CHECK_MAX_BYTES:
                        break
                    chunks.append(chunk)
                html = b''.join(chunks).decode(_html_charset(response.headers.get('Content-Type', '')), errors='replace')
            return jsonify(host=host, reachable=reachable, status=response.status_code,
                tag_in_html=site['public_id'] in html,
                gtm_detected='googletagmanager.com/gtm.js' in html or 'GTM-' in html,
                checked_at=datetime.now(timezone.utc).isoformat())
        except BadRequest:
            raise
        except (OSError, ValueError, urllib3.exceptions.HTTPError):
            return jsonify(host=host, reachable=False, status=None, tag_in_html=False, gtm_detected=False,
                checked_at=datetime.now(timezone.utc).isoformat())
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
        # `consent` stays accepted (and ignored) for cached copies of the old tag.
        allowed = {'visitor_id', 'session_id', 'name', 'email', 'phone', 'campaign', 'consent', 'path'}
        if not isinstance(payload, dict) or set(payload) - allowed:
            abort(400, description='Dados de identificação fora do contrato da Super Tag.')
        identify_path = payload.get('path') or '/'
        if not isinstance(identify_path, str) or not identify_path.startswith('/') or '?' in identify_path \
                or '#' in identify_path or len(identify_path) > 1000:
            abort(400, description='Caminho da página inválido.')
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
        retention_days = (site.get('config') or {}).get('retention_days', DEFAULT_RETENTION_DAYS)
        if isinstance(retention_days, bool) or retention_days not in RETENTION_DAYS_CHOICES:
            retention_days = DEFAULT_RETENTION_DAYS
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
        # The readable contact also goes to "Quem converteu", encrypted and with the same retention.
        lead_name, lead_email, lead_phone = leads.clean_contact(name, email, phone)
        leads.store_lead(site, source='identify', source_event_id=leads.identify_source_event(site['id'], session_id, identity_digest),
                         session_id=session_id, visitor_id=visitor_id, form_id=None,
                         page_path=_safe_path(identify_path)[:500], submitted_at=datetime.now(timezone.utc),
                         name=lead_name, email=lead_email, phone=lead_phone, fields={})
        get_db().commit()
        return jsonify(identified=True), 200

    @bp.get('/api/v2/reports/supertag/sites')
    @login_required_api
    def supertag_sites():
        selected = _selection()
        params = (selected['client_id'],)
        sites = _rows('''SELECT s.id,s.public_id,s.label,s.allowed_host,s.enabled,s.config,
                s.config_version,s.created_at,s.updated_at,s.revoked_at,
                COUNT(e.id)::bigint AS events_30d,
                COUNT(e.id) FILTER (WHERE e.event_kind='conversion')::bigint AS conversions_30d,
                (SELECT MAX(l.occurred_at) FROM cadu_reports_supertag_events l
                    WHERE l.site_id=s.id AND l.expires_at > NOW()) AS last_event_at
            FROM cadu_reports_supertag_sites s LEFT JOIN cadu_reports_supertag_events e
              ON e.site_id=s.id AND e.expires_at > NOW() AND e.occurred_at >= NOW() - INTERVAL '30 days'
            WHERE s.client_id=%s
            GROUP BY s.id ORDER BY s.created_at DESC''', params)
        base = _base_url()
        for site in sites:
            site['script_url'] = f'{base}/v1/supertag.js'
            _with_snippets(site)
        return jsonify(sites=sites)

    @bp.post('/api/v2/reports/supertag/sites')
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

    @bp.patch('/api/v2/reports/supertag/sites/<uuid:site_id>')
    @login_required_api
    def supertag_site_update(site_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict) or set(payload) - {'label', 'allowed_host', 'visibility_enabled', 'audience_days', 'retention_days',
                                                         'conversion_rules', 'conversion_defaults', 'form_capture', 'enhanced',
                                                         'client_id'}:
            abort(400, description='Configuração da Super Tag inválida.')
        selected = _selection(payload)
        _write_guard(selected)
        found = _rows('''SELECT id,label,allowed_host,config,config_version FROM cadu_reports_supertag_sites
            WHERE id=%s AND client_id=%s AND revoked_at IS NULL FOR UPDATE''',
            (str(site_id), selected['client_id']))
        if not found:
            abort(404)
        current = found[0]
        label = ' '.join(str(payload.get('label', current['label']) or '').split())[:120]
        host = _host(payload.get('allowed_host', current['allowed_host']))
        config = dict(current['config'] or {})
        # Consent is the website's job; old keys are dropped on the next save.
        config.pop('consent_mode', None)
        config.pop('consent_required', None)
        if 'conversion_rules' in payload:
            config['conversion_rules'] = leads.validate_conversion_rules(payload['conversion_rules'])
        if 'conversion_defaults' in payload:
            if not isinstance(payload['conversion_defaults'], bool):
                abort(400, description='Informe se as regras automáticas de página de obrigado ficam ativas.')
            config['conversion_defaults'] = payload['conversion_defaults']
        if 'form_capture' in payload:
            config['form_capture'] = {**(config.get('form_capture') or {}), **leads.validate_form_capture(payload['form_capture'])}
        if 'enhanced' in payload:
            config['enhanced'] = {**enhanced_settings(config), **validate_enhanced(payload['enhanced'])}
        if 'visibility_enabled' in payload:
            if not isinstance(payload['visibility_enabled'], bool):
                abort(400, description='Informe se a coleta de visibilidade está ativa.')
            config['visibility_enabled'] = payload['visibility_enabled']
        if 'audience_days' in payload:
            if isinstance(payload['audience_days'], bool) or payload['audience_days'] not in AUDIENCE_DAYS_CHOICES:
                abort(400, description='Escolha uma duração entre 30 e 395 dias.')
            config['audience_days'] = payload['audience_days']
        if 'retention_days' in payload:
            if isinstance(payload['retention_days'], bool) or payload['retention_days'] not in RETENTION_DAYS_CHOICES:
                abort(400, description='Escolha a retenção dos eventos entre 30 dias e 5 anos.')
            config['retention_days'] = payload['retention_days']
        updated = _rows('''UPDATE cadu_reports_supertag_sites SET label=%s,allowed_host=%s,
            config=%s::jsonb,config_version=config_version+1,updated_at=NOW()
            WHERE id=%s RETURNING id,public_id,label,allowed_host,enabled,config,config_version,created_at,updated_at,revoked_at''',
            (label, host, json.dumps(config), str(site_id)))[0]
        get_db().commit()
        base = _base_url()
        updated['script_url'] = f'{base}/v1/supertag.js'
        _with_snippets(updated)
        return jsonify(site=updated)

    @bp.post('/api/v2/reports/supertag/sites/<uuid:site_id>/revoke')
    @login_required_api
    def supertag_site_revoke(site_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        changed = _rows('''UPDATE cadu_reports_supertag_sites SET enabled=FALSE,revoked_at=NOW(),updated_at=NOW()
            WHERE id=%s AND client_id=%s AND revoked_at IS NULL RETURNING id''',
            (str(site_id), selected['client_id']))
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
            visibility_enabled=(site.get('config') or {}).get('visibility_enabled', True),
            form_capture=leads.public_form_capture(site.get('config')),
            enhanced=enhanced_settings(site.get('config')),
            audience_days=(site.get('config') or {}).get('audience_days', DEFAULT_AUDIENCE_DAYS)))
        response.headers['Cache-Control'] = 'public, max-age=300, stale-while-revalidate=3600'
        response.set_etag(f'{site["public_id"]}:{site["config_version"]}')
        return response.make_conditional(request)

    @bp.route('/public/supertag/v1/<public_id>/consent', methods=['POST', 'OPTIONS'])
    def supertag_public_consent(public_id):
        """Kept for cached copies of the old tag: acknowledges the choice and stores nothing."""
        site = _site_by_public_id(public_id)
        request._supertag_allowed_host = site['allowed_host']
        origin = request.headers.get('Origin') or ''
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http') or not _host_allowed(parsed.hostname or '', site['allowed_host']):
            abort(403)
        if request.method == 'OPTIONS':
            return ('', 204)
        payload = request.get_json(silent=True) or {}
        analytics = payload.get('analytics') if isinstance(payload, dict) else None
        response = make_response(jsonify(analytics=analytics if isinstance(analytics, bool) else None))
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
        # One bad event must not poison the batch: it is dropped and counted, the rest is stored, and the answer
        # stays 202 so the tag never resends the same batch forever.
        prepared, rejected = [], 0
        for item in events:
            try:
                prepared.append(_event(item, site))
            except HTTPException as exc:
                if exc.code != 400:
                    raise
                rejected += 1
        if not prepared:
            return jsonify(accepted=0, rejected=rejected), 202
        ip_digest = _ip_digest()
        retention_days = (site.get('config') or {}).get('retention_days', DEFAULT_RETENTION_DAYS)
        if isinstance(retention_days, bool) or retention_days not in RETENTION_DAYS_CHOICES:
            retention_days = DEFAULT_RETENTION_DAYS
        conn = get_db()
        try:
            # Sessions first, then events, each in sorted order: every batch takes the locks in the same order. The
            # session lock serializes two batches of one session, so the conversion dedupe below sees the other one.
            for session_id in sorted({str(item[4]) for item in prepared}):
                _rows('SELECT pg_advisory_xact_lock(hashtext(%s),hashtext(%s))',
                      (str(site['id']), f'session:{session_id}'))
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
            derived = leads.derive_conversions(site, new_events, leads.converted_pages(site['id'], new_events))
            # Same conversion of the same session within 5 min (thank-you page + trackConversion, another batch):
            # only the first one is stored; the others are counted as deduped and the batch still answers 202.
            candidates = [item for item in new_events if item[5] == 'conversion'] + derived
            kept, dropped = leads.dedupe_conversions(candidates, leads.recent_conversions(site['id'], candidates))
            dropped_ids = {str(item[0]) for item in dropped}
            derived = [item for item in derived if str(item[0]) not in dropped_ids]
            stored = [item for item in prepared if str(item[0]) not in dropped_ids]
            new_events = [item for item in new_events if str(item[0]) not in dropped_ids]
            with conn.cursor() as cursor:
                cursor.executemany('''INSERT INTO cadu_reports_supertag_events
                    (event_id,site_id,client_id,visitor_id,session_id,event_kind,event_name,page_path,referrer_host,attribution,event_data,viewport_width,viewport_height,occurred_at,expires_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,
                        NOW() + (%s * INTERVAL '1 day'))
                    ON CONFLICT (site_id,event_id) DO NOTHING''',
                    [(*event, retention_days) for event in stored + derived])
                session_rollup = {}
                for event in prepared:
                    session_id, visitor_id, occurred_at = event[4], event[3] or event[4], event[13]
                    attribution = json.loads(event[9] or '{}')
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
            # A deduped conversion still happened: it may confirm a lead the stored one is too far from.
            leads.confirm_leads(site['id'], kept + dropped)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        dropped_explicit = sum(1 for item in dropped if leads.conversion_origin(item[10]) == 'explicit')
        return jsonify(accepted=len(prepared) - dropped_explicit, rejected=rejected, conversions=len(derived),
                       deduped=len(dropped)), 202

    @bp.get('/api/v2/reports/supertag/sites/<uuid:site_id>/events')
    @login_required_api
    def supertag_site_events(site_id):
        selected = _selection()
        params = (str(site_id), selected['client_id'])
        site = _rows('''SELECT id,public_id,label,allowed_host,config FROM cadu_reports_supertag_sites
            WHERE id=%s AND client_id=%s''', params)
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
                (ARRAY_AGG(e.visitor_id ORDER BY e.occurred_at,e.id)
                    FILTER (WHERE e.visitor_id IS NOT NULL))[1] AS visitor_id,
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

    leads.register(bp)
