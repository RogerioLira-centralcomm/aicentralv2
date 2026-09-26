"""First-party Funnel Flow collection and URL-step mapping for Reports V1."""
import json
import re
import secrets
import string
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse, urlunparse

from flask import abort, jsonify, request, session

from ..auth import login_required_api
from ..db import get_db
from .reports_v1 import _rows, _selection, _write_guard

MAX_TAG_EVENTS_PER_MINUTE = 1200
MAX_DISCOVERY_PAGES = 60


def _host(value):
    value = str(value or '').strip().lower()
    if '://' in value:
        value = urlparse(value).hostname or ''
    value = value.rstrip('.')
    if not re.fullmatch(r'(?=.{1,253}$)[a-z0-9][a-z0-9.-]*[a-z0-9]', value) or '..' in value:
        abort(400, description='Informe um domínio válido, sem caminho.')
    return value


def _domain_root(host):
    return host[4:] if host.startswith('www.') else host


def _host_allowed(candidate, allowed_host):
    try:
        host = _host(candidate)
        root = _domain_root(_host(allowed_host))
        return host == root or host.endswith('.' + root)
    except Exception:
        return False


class _SitePageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.forms, self.form_fields = [], 0, []
        self.title_parts, self.h1_parts = [], []
        self.in_title = self.in_h1 = self.in_form = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'form':
            self.forms += 1
            self.in_form = True
        if tag in ('input','select','textarea') and self.in_form:
            field_name = attrs.get('name') or attrs.get('id') or ''
            field_type = attrs.get('type') or ('textarea' if tag == 'textarea' else tag)
            label = attrs.get('aria-label') or attrs.get('autocomplete') or field_name
            if field_type.lower() not in ('hidden','submit','button','reset','image','password'):
                if label and len(self.form_fields) < 30:
                    field = {'name': field_name[:80], 'label': label[:100],
                             'type': field_type[:32], 'required': 'required' in attrs}
                    if field not in self.form_fields:
                        self.form_fields.append(field)
        self.in_title = tag == 'title'
        self.in_h1 = tag == 'h1'

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag == 'h1': self.in_h1 = False
        if tag == 'form': self.in_form = False

    def handle_data(self, data):
        value = ' '.join(data.split())
        if value and self.in_title: self.title_parts.append(value)
        if value and self.in_h1: self.h1_parts.append(value)


def _canonical_page_url(url, base_url, allowed_host):
    parsed = urlparse(urljoin(base_url, url))
    if parsed.scheme not in ('http','https') or not parsed.hostname or not _host_allowed(parsed.hostname, allowed_host):
        return None
    try:
        if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            return None
    except ValueError:
        return None
    path = re.sub(r'/+', '/', unquote(parsed.path or '/'))
    if len(path) > 500 or any(part in ('.','..') for part in path.split('/')):
        return None
    # URLs with tracking/query state can include personal data; discovery uses
    # stable paths only and never persists query strings or fragments.
    return urlunparse(('https', parsed.hostname.lower().rstrip('.'), path, '', '', ''))


def _fetch_site_page(url, allowed_host):
    from .reports_link_tester import _fetch
    current = url
    for _ in range(4):
        parsed = urlparse(current)
        if not _host_allowed(parsed.hostname or '', allowed_host):
            return None
        status, headers, body = _fetch(current, body=True, accepted_types=('html','text/','xml'))
        if status in (301,302,303,307,308) and headers.get('Location'):
            current = _canonical_page_url(headers['Location'], current, allowed_host)
            if not current: return None
            continue
        if status != 200 or 'html' not in headers.get('Content-Type','').lower():
            return None
        parser = _SitePageParser()
        try: parser.feed(body)
        except Exception: pass
        return {'url': current, 'host': parsed.hostname.lower().rstrip('.'),
                'path': parsed.path or '/', 'title': ' '.join(parser.title_parts)[:500],
                'h1': ' '.join(parser.h1_parts)[:300], 'links': parser.links[:500],
                'forms': parser.forms, 'form_fields': parser.form_fields}
    return None


def _site_sitemap_urls(root_url, allowed_host):
    from .reports_link_tester import _fetch
    parsed = urlparse(root_url)
    base = f'{parsed.scheme}://{parsed.netloc}'
    sources = [urljoin(base, '/robots.txt'), urljoin(base, '/sitemap.xml'),
               urljoin(base, '/sitemap_index.xml')]
    sitemap_urls = []
    for source in sources:
        try:
            status, headers, body = _fetch(source, body=True, accepted_types=('xml','text/'))
        except Exception:
            continue
        if status != 200: continue
        if source.endswith('robots.txt'):
            sitemap_urls.extend(re.findall(r'(?im)^\s*Sitemap:\s*(\S+)', body))
        else:
            sitemap_urls.append(source)
    page_urls, pending = [], list(dict.fromkeys(sitemap_urls))[:8]
    for sitemap in pending:
        canonical = _canonical_page_url(sitemap, root_url, allowed_host)
        if not canonical: continue
        try:
            status, _, body = _fetch(canonical, body=True, accepted_types=('xml','text/'))
            if status != 200: continue
            locations = re.findall(r'<(?:\w+:)?loc[^>]*>\s*(.*?)\s*</(?:\w+:)?loc>', body, re.I | re.S)
            for location in locations:
                location = unquote(re.sub(r'&amp;', '&', location.strip()))
                item = _canonical_page_url(location, root_url, allowed_host)
                if item and item.lower().endswith('.xml') and item not in pending and len(pending) < 12:
                    pending.append(item)
                elif item:
                    page_urls.append(item)
        except Exception:
            continue
    return list(dict.fromkeys(page_urls))[:MAX_DISCOVERY_PAGES]


def _classify_discovered_page(page, root_host):
    source = f"{page['path']} {page['title']} {page.get('h1','')}".casefold()
    conversion = re.search(r'obrigad|thank.?you|/success(?:/|$)|confirmation|confirmad|pedido.?conclu|compra.?realizada|form.?sent|envio.?conclu', source)
    form_words = re.search(r'contato|contact|fale.?conosco|solicit(e|acao|ação)|orcamento|orçamento|inscri(c|ç)(a|ã)o|cadastro|formul(a|á)rio|consultor|proposal|request', source)
    if conversion:
        role, confidence = 'conversion', .91
        evidence = ['URL ou título indica confirmação/obrigado']
    elif form_words and page['forms']:
        role, confidence = 'form', .93
        evidence = ['formulário HTML detectado']
    elif form_words:
        role, confidence = 'intermediate', .48
        evidence = ['página sugere contato/cadastro; formulário não confirmado']
    elif page['forms']:
        role, confidence = 'intermediate', .62
        evidence = ['formulário detectado em elemento possivelmente global do site']
    elif page['path'].rstrip('/') in ('','/en','/pt','/pt-br') or page['host'] == root_host and page['path'] == '/':
        role, confidence = 'entry', .96
        evidence = ['página inicial do domínio']
    else:
        role, confidence = 'intermediate', .62
        evidence = ['link interno encontrado no site']
    if page['forms']:
        evidence.append(f"{page['forms']} formulário(s); apenas nomes e tipos de campos foram lidos")
    if page.get('h1'): evidence.append(f"título visível: {page['h1'][:180]}")
    return {'role': role, 'confidence': confidence, 'evidence': evidence}


def _discover_site(root_url, allowed_host):
    canonical_root = _canonical_page_url(root_url, root_url, allowed_host)
    if not canonical_root:
        abort(400, description='Use uma URL pública do domínio autorizado ou de um subdomínio dele.')
    seed_urls = [canonical_root, *_site_sitemap_urls(canonical_root, allowed_host)]
    found, queued = {}, list(dict.fromkeys(seed_urls))
    while queued and len(found) < MAX_DISCOVERY_PAGES:
        batch = []
        while queued and len(batch) < 10 and len(found) + len(batch) < MAX_DISCOVERY_PAGES:
            candidate = queued.pop(0)
            if candidate not in found and candidate not in batch: batch.append(candidate)
        if not batch: continue
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(_fetch_site_page, item, allowed_host): item for item in batch}
            pages = []
            for future in as_completed(futures):
                try: pages.append(future.result())
                except Exception: pages.append(None)
        for page in pages:
            if not page: continue
            key = (page['host'], page['path'])
            found[key] = page
            for link in page['links']:
                candidate = _canonical_page_url(link, page['url'], allowed_host)
                if candidate and candidate not in found and candidate not in queued and len(queued) < 300:
                    # Keep discovery useful: ignore common asset and auth routes.
                    if not re.search(r'\.(?:pdf|png|jpe?g|webp|svg|css|js|zip|mp4|woff2?)$', urlparse(candidate).path, re.I):
                        queued.append(candidate)
    root_host = _domain_root(_host(urlparse(canonical_root).hostname))
    results = []
    for page in found.values():
        classification = _classify_discovered_page(page, root_host)
        if classification['role'] == 'form' and not page['form_fields']:
            classification = {'role':'intermediate','confidence':.58,
                              'evidence':['formulário detectado; sem campos públicos legíveis']}
        results.append({**page, **classification})
    role_order = {'entry':0,'form':1,'conversion':2,'intermediate':3}
    return sorted(results, key=lambda page: (role_order[page['role']],page['host'],page['path']))


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
            if flow and _host_allowed(parsed.hostname or '', flow[0]['allowed_host']):
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
        steps = _rows('''SELECT s.id,s.tag_id,s.name,s.path_prefix,s.page_host,s.step_kind,s.is_entry,s.campaign_id,s.position,
            s.is_active,s.archived_at,
            c.name AS campaign_name FROM cadu_reports_flow_steps s
            LEFT JOIN cadu_reports_campaigns c ON c.id=s.campaign_id
            WHERE s.organization_id=%s AND s.client_id=%s AND s.is_active=TRUE
            ORDER BY s.is_entry DESC,s.position,s.id''', params)
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
            SELECT id,tag_id,LAG(id) OVER (PARTITION BY tag_id ORDER BY is_entry DESC,position,id) AS previous_id
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
        confirmed_time_filter = 'x.occurred_at > NOW() - (%s * INTERVAL \'1 day\')'
        confirmed_params = list(scope_params)
        if start_date or end_date:
            confirmed_time_filter = "x.occurred_at >= %s::date AND x.occurred_at < (%s::date + INTERVAL '1 day')"
            confirmed_params = [*params, parsed_start.isoformat(), parsed_end.isoformat(), *scope_params[3:]]
        confirmed = _rows('''SELECT x.conversion_kind,COUNT(*)::bigint AS total
            FROM cadu_reports_external_conversions x
            LEFT JOIN cadu_reports_campaigns c ON c.id=x.campaign_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
            WHERE x.organization_id=%s AND x.client_id=%s
                AND ''' + confirmed_time_filter + conversion_filter +
            ' GROUP BY x.conversion_kind ORDER BY x.conversion_kind', tuple(confirmed_params))
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

    @bp.post('/api/v1/reports/flow/flows/<flow_id>/discover')
    @login_required_api
    def reports_flow_discover_site(flow_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict): abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        root_url = str(payload.get('root_url') or f"https://{flow['allowed_host']}").strip()
        parsed = urlparse(root_url if '://' in root_url else 'https://' + root_url)
        if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
            abort(400, description='Informe a URL pública inicial do site.')
        root_url = _canonical_page_url(root_url if '://' in root_url else 'https://' + root_url,
                                       f"https://{flow['allowed_host']}", flow['allowed_host'])
        if not root_url:
            abort(400, description='O mapeamento só pode visitar o domínio autorizado e seus subdomínios.')
        pages = _discover_site(root_url, flow['allowed_host'])
        run_id = str(uuid.uuid4())
        status = 'partial' if len(pages) >= MAX_DISCOVERY_PAGES else 'completed' if pages else 'failed'
        _rows('''INSERT INTO cadu_reports_flow_discovery_runs
            (id,organization_id,client_id,tag_id,root_url,status,page_count,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (run_id, selected['organization_id'], selected['client_id'], flow['tag_id'],
             root_url, status, len(pages), session['user_id']))
        _rows('''UPDATE cadu_reports_flow_discovery_runs SET status='partial'
            WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND id<>%s
                AND status='completed' RETURNING id''',
            (flow['tag_id'],selected['organization_id'],selected['client_id'],run_id))
        mapped_steps = _rows('''SELECT id,page_host,path_prefix,step_kind,is_entry
            FROM cadu_reports_flow_steps WHERE tag_id=%s AND organization_id=%s AND client_id=%s
                AND is_active=TRUE AND step_kind IN ('page','form','conversion')''',
            (flow['tag_id'],selected['organization_id'],selected['client_id']))
        steps_by_page = {(step['page_host'],step['path_prefix']):step for step in mapped_steps}
        stored = []
        for page in pages:
            evidence = {'signals': page['evidence'], 'h1': page.get('h1','')}
            prior_step = steps_by_page.get((page['host'],page['path']))
            selected_kind = prior_step['step_kind'] if prior_step else None
            selected_as_entry = bool(prior_step and prior_step['is_entry'])
            row = _rows('''INSERT INTO cadu_reports_flow_discovered_pages
                (id,run_id,organization_id,client_id,tag_id,url,page_host,path_prefix,title,
                 suggested_role,confidence,evidence,form_count,form_fields,selected_kind,selected_as_entry,step_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (run_id,page_host,path_prefix) DO UPDATE SET
                    url=EXCLUDED.url,title=EXCLUDED.title,suggested_role=EXCLUDED.suggested_role,
                    confidence=EXCLUDED.confidence,evidence=EXCLUDED.evidence,
                    form_count=EXCLUDED.form_count,form_fields=EXCLUDED.form_fields
                RETURNING id,url,page_host,path_prefix,title,suggested_role,confidence,evidence,
                    form_count,form_fields,selected_kind,selected_as_entry,step_id''',
                (str(uuid.uuid4()),run_id,selected['organization_id'],selected['client_id'],
                 flow['tag_id'],page['url'],page['host'],page['path'],page['title'],page['role'],
                 page['confidence'],json.dumps(evidence),page['forms'],json.dumps(page['form_fields']),
                 selected_kind,selected_as_entry,prior_step['id'] if prior_step else None))[0]
            stored.append(row)
        get_db().commit()
        return jsonify(run={'id':run_id,'root_url':root_url,'status':status,'page_count':len(stored)},pages=stored)

    @bp.get('/api/v1/reports/flow/flows/<flow_id>/discoveries')
    @login_required_api
    def reports_flow_discoveries(flow_id):
        selected = _selection()
        flow = _flow_row(flow_id, selected)
        runs = _rows('''SELECT id,root_url,status,page_count,created_at
            FROM cadu_reports_flow_discovery_runs WHERE organization_id=%s AND client_id=%s AND tag_id=%s
            ORDER BY created_at DESC LIMIT 1''',
            (selected['organization_id'],selected['client_id'],flow['tag_id']))
        pages = []
        if runs:
            pages = _rows('''SELECT id,url,page_host,path_prefix,title,suggested_role,confidence,evidence,
                form_count,form_fields,selected_kind,selected_as_entry,step_id
                FROM cadu_reports_flow_discovered_pages WHERE run_id=%s AND organization_id=%s AND client_id=%s
                ORDER BY CASE suggested_role WHEN 'entry' THEN 0 WHEN 'form' THEN 1 WHEN 'conversion' THEN 2 ELSE 3 END,
                    page_host,path_prefix''', (runs[0]['id'],selected['organization_id'],selected['client_id']))
        return jsonify(run=runs[0] if runs else None,pages=pages)

    @bp.post('/api/v1/reports/flow/flows/<flow_id>/discoveries/<page_id>/select')
    @login_required_api
    def reports_flow_select_discovered_page(flow_id,page_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload,dict): abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id,selected)
        if flow['status']=='published':
            abort(409,description='Despublique o fluxo antes de alterar as etapas selecionadas.')
        pages = _rows('''SELECT * FROM cadu_reports_flow_discovered_pages
            WHERE id=%s AND tag_id=%s AND organization_id=%s AND client_id=%s FOR UPDATE''',
            (_uuid(page_id,'Página descoberta'),flow['tag_id'],selected['organization_id'],selected['client_id']))
        if not pages: abort(404,description='Página não encontrada nesta análise do site.')
        page=pages[0]
        choice=payload.get('selection')
        if choice not in ('ignore','entry','intermediate','form','conversion'):
            abort(400,description='Escolha entrada, etapa intermediária, formulário, conversão ou ignorar.')
        step_id=page['step_id']
        if not step_id and choice != 'ignore':
            existing=_rows('''SELECT id FROM cadu_reports_flow_steps
                WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND page_host=%s
                    AND path_prefix=%s AND is_active=TRUE ORDER BY id LIMIT 1''',
                (flow['tag_id'],selected['organization_id'],selected['client_id'],
                 page['page_host'],page['path_prefix']))
            step_id=existing[0]['id'] if existing else None
        if choice=='ignore':
            if not step_id:
                existing=_rows('''SELECT id FROM cadu_reports_flow_steps
                    WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND page_host=%s
                        AND path_prefix=%s AND is_active=TRUE ORDER BY id LIMIT 1''',
                    (flow['tag_id'],selected['organization_id'],selected['client_id'],
                     page['page_host'],page['path_prefix']))
                step_id=existing[0]['id'] if existing else None
            if step_id:
                _rows('''UPDATE cadu_reports_flow_steps SET is_active=FALSE,is_entry=FALSE,archived_at=NOW()
                    WHERE id=%s AND organization_id=%s AND client_id=%s RETURNING id''',
                    (step_id,selected['organization_id'],selected['client_id']))
            _rows('''UPDATE cadu_reports_flow_discovered_pages SET selected_kind=NULL,
                selected_as_entry=FALSE,step_id=NULL,selected_at=NOW()
                WHERE id=%s RETURNING id''',(page['id'],))
            config=flow['config'] if isinstance(flow['config'],dict) else {}
            config['nodes']=[node for node in config.get('nodes',[])
                if node.get('discoveryPageId')!=str(page['id'])
                and not (step_id and str(node.get('stepId'))==str(step_id))]
            config['edges']=[edge for edge in config.get('edges',[]) if edge.get('from') in {n.get('id') for n in config['nodes']} and edge.get('to') in {n.get('id') for n in config['nodes']}]
            _rows('UPDATE cadu_reports_flow_registry SET config=%s::jsonb,updated_at=NOW() WHERE id=%s RETURNING id',(json.dumps(config),flow['id']))
            get_db().commit()
            return jsonify(page_id=str(page['id']),selection='ignore',step=None)
        step_kind={'entry':'page','intermediate':'page','form':'form','conversion':'conversion'}[choice]
        name=' '.join(str(payload.get('name') or page['title'] or page['path_prefix']).split())[:120]
        is_entry=choice=='entry'
        if is_entry:
            _rows('''UPDATE cadu_reports_flow_steps SET is_entry=FALSE
                WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE AND is_entry=TRUE''',
                (flow['tag_id'],selected['organization_id'],selected['client_id']))
            _rows('''UPDATE cadu_reports_flow_steps SET position=position+1
                WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE
                    AND position < COALESCE((SELECT position FROM cadu_reports_flow_steps WHERE id=%s),0)''',
                (flow['tag_id'],selected['organization_id'],selected['client_id'],step_id or -1))
            _rows('''UPDATE cadu_reports_flow_discovered_pages SET selected_as_entry=FALSE
                WHERE tag_id=%s AND organization_id=%s AND client_id=%s''',
                (flow['tag_id'],selected['organization_id'],selected['client_id']))
        if step_id:
            changed=_rows('''UPDATE cadu_reports_flow_steps SET name=%s,path_prefix=%s,page_host=%s,
                step_kind=%s,is_entry=%s,position=%s,is_active=TRUE,archived_at=NULL
                WHERE id=%s AND organization_id=%s AND client_id=%s
                RETURNING id,name,path_prefix,page_host,step_kind,is_entry,position''',
                (name,page['path_prefix'],page['page_host'],step_kind,is_entry,
                 0 if is_entry else _rows('SELECT position FROM cadu_reports_flow_steps WHERE id=%s',(step_id,))[0]['position'],step_id,
                 selected['organization_id'],selected['client_id']))
            step=changed[0]
        else:
            position=_rows('''SELECT COALESCE(MAX(position),-1)+1 AS position FROM cadu_reports_flow_steps
                WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE''',
                (flow['tag_id'],selected['organization_id'],selected['client_id']))[0]['position']
            created=_rows('''INSERT INTO cadu_reports_flow_steps
                (organization_id,client_id,tag_id,name,path_prefix,page_host,step_kind,is_entry,position)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id,name,path_prefix,page_host,step_kind,is_entry,position''',
                (selected['organization_id'],selected['client_id'],flow['tag_id'],name,
                 page['path_prefix'],page['page_host'],step_kind,is_entry,0 if is_entry else position))
            step=created[0]
            step_id=step['id']
        _rows('''UPDATE cadu_reports_flow_discovered_pages SET selected_kind=%s,
            selected_as_entry=%s,step_id=%s,selected_at=NOW() WHERE id=%s RETURNING id''',
            (step_kind,is_entry,step_id,page['id']))
        config=flow['config'] if isinstance(flow['config'],dict) else {}
        nodes=config.get('nodes') if isinstance(config.get('nodes'),list) else []
        edges=config.get('edges') if isinstance(config.get('edges'),list) else []
        node=next((item for item in nodes if item.get('discoveryPageId')==str(page['id'])
                   or (step_id and str(item.get('stepId'))==str(step_id))),None)
        if not node:
            node={'id':str(uuid.uuid4()),'discoveryPageId':str(page['id']),
                  'x':100+(len(nodes)%4)*230,'y':80+(len(nodes)//4)*150}
            nodes.append(node)
        node.update({'discoveryPageId':str(page['id']),'type':step_kind if step_kind!='page' else 'page','title':name,
                     'path':page['path_prefix'],'host':page['page_host'],
                     'stepId':int(step_id),'isEntry':is_entry})
        config.update({'nodes':nodes,'edges':edges})
        _rows('UPDATE cadu_reports_flow_registry SET config=%s::jsonb,updated_at=NOW() WHERE id=%s RETURNING id',
              (json.dumps(config),flow['id']))
        get_db().commit()
        return jsonify(page_id=str(page['id']),selection=choice,step=step,node=node)

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
            test_host = _host(item.get('host') or flow['allowed_host'])
            if not _host_allowed(test_host,flow['allowed_host']):
                abort(400,description='O teste só aceita o domínio do fluxo ou seus subdomínios.')
            source = ' '.join(str(item.get('source') or '')[:160].split()) or None
            details = item.get('data') if isinstance(item.get('data'), dict) else {}
            if item['kind'] == 'custom_event':
                details['event_name'] = ' '.join(str(item.get('event_name') or 'Evento personalizado').split())[:120]
            details = {str(k)[:60]: str(v)[:180] for k, v in list(details.items())[:12]}
            row = _rows('''INSERT INTO cadu_reports_flow_events_test
                (organization_id,client_id,flow_id,flow_code,event_kind,page_host,page_path,source_label,session_id,payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                RETURNING id,event_kind,page_host,page_path,source_label,created_at''',
                (selected['organization_id'], selected['client_id'], flow['id'], flow['flow_code'],
                 item['kind'],test_host,path,source,session_id,json.dumps(details)))[0]
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
        page_host = _host(payload['page_host']) if payload.get('page_host') else None
        if page_host and not _host_allowed(page_host,tag['allowed_host']):
            abort(400,description='A etapa precisa usar o domínio autorizado ou um subdomínio dele.')
        is_entry=payload.get('is_entry',False)
        if not isinstance(is_entry,bool): abort(400,description='Informe se esta é a entrada do fluxo.')
        if is_entry:
            _rows('''UPDATE cadu_reports_flow_steps SET is_entry=FALSE WHERE tag_id=%s
                AND organization_id=%s AND client_id=%s RETURNING id''',
                (tag['id'],selected['organization_id'],selected['client_id']))
            _rows('''UPDATE cadu_reports_flow_steps SET position=position+1 WHERE tag_id=%s
                AND organization_id=%s AND client_id=%s AND is_active=TRUE AND position < %s''',
                (tag['id'],selected['organization_id'],selected['client_id'],position))
            position=0
        result = _rows('''INSERT INTO cadu_reports_flow_steps
            (organization_id,client_id,tag_id,name,path_prefix,page_host,step_kind,is_entry,campaign_id,position)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id,name,path_prefix,page_host,step_kind,is_entry,campaign_id,position''',
            (selected['organization_id'],selected['client_id'],tag['id'],name,path,page_host,
             kind,is_entry,campaign_id,position))
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
        found = _rows('''SELECT id,tag_id,name,path_prefix,page_host,step_kind,is_entry,campaign_id,position
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
        page_host = payload.get('page_host',current['page_host'])
        if page_host:
            page_host = _host(page_host)
            if not _host_allowed(page_host,tag['allowed_host']):
                abort(400,description='A etapa precisa usar o domínio autorizado ou um subdomínio dele.')
        is_entry = payload.get('is_entry',current['is_entry'])
        if not isinstance(is_entry,bool): abort(400,description='Informe se esta é a entrada do fluxo.')
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
        if is_entry:
            _rows('''UPDATE cadu_reports_flow_steps SET is_entry=FALSE WHERE tag_id=%s
                AND organization_id=%s AND client_id=%s AND id<>%s RETURNING id''',
                (tag['id'],selected['organization_id'],selected['client_id'],step_id))
            _rows('''UPDATE cadu_reports_flow_steps SET position=position+1 WHERE tag_id=%s
                AND organization_id=%s AND client_id=%s AND is_active=TRUE AND id<>%s AND position < %s''',
                (tag['id'],selected['organization_id'],selected['client_id'],step_id,position))
            position=0
        changed = _rows('''UPDATE cadu_reports_flow_steps SET name=%s,path_prefix=%s,page_host=%s,step_kind=%s,
                is_entry=%s,campaign_id=%s,position=%s WHERE id=%s AND organization_id=%s AND client_id=%s
                AND position=(SELECT position FROM cadu_reports_flow_steps
                    WHERE id=%s AND organization_id=%s AND client_id=%s FOR UPDATE)
            RETURNING id,tag_id,name,path_prefix,page_host,step_kind,is_entry,campaign_id,position''',
            (name,path,page_host,kind,is_entry,campaign_id,position,step_id,selected['organization_id'],selected['client_id'],
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
        if parsed_origin.scheme not in ('https', 'http') or not _host_allowed(parsed_origin.hostname or '',tag['allowed_host']):
            abort(403)
        page_url = urlparse(str(payload.get('url') or ''))
        page_host=(page_url.hostname or '').lower().rstrip('.')
        if not _host_allowed(page_host,tag['allowed_host']) or page_url.scheme not in ('https', 'http'):
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
        steps = _rows('''SELECT id,path_prefix,page_host,step_kind,campaign_id FROM cadu_reports_flow_steps
            WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE
            ORDER BY length(path_prefix) DESC,is_entry DESC,position,id''',
            (tag['id'], tag['organization_id'], tag['client_id']))
        matched = next((step for step in steps
                        if (not step['page_host'] or step['page_host'] == page_host)
                        and (step['path_prefix'] == '/'
                             or path == step['path_prefix']
                             or path.startswith(step['path_prefix'].rstrip('/') + '/'))), None)
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
            (organization_id,client_id,tag_id,visitor_id,session_id,event_kind,page_host,page_path,
             referrer_host,utm_source,utm_medium,utm_campaign,utm_id,click_id,step_id,campaign_id,attribution_method)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (tag['organization_id'], tag['client_id'], tag['id'], visitor, visit_session,
             event_kind,page_host,safe_path,referrer,attribution['utm_source'],attribution['utm_medium'],
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
        if parsed.scheme not in ('http', 'https') or not _host_allowed(parsed.hostname or '',flow['allowed_host']):
            abort(403)
        page_host = _host(payload.get('host') or parsed.hostname or '')
        if not _host_allowed(page_host,flow['allowed_host']):
            abort(400,description='Página fora do domínio autorizado.')
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
            and node.get('path') == path and (not node.get('host') or node.get('host')==page_host)
            and node.get('type') in ('page','form','event','conversion','whatsapp')), None)
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
                AND (page_host IS NULL OR page_host=%s)
                AND (path_prefix='/' OR %s=path_prefix OR %s LIKE rtrim(path_prefix,'/') || '/%%')
            ORDER BY length(path_prefix) DESC,position,id LIMIT 1''',
            (tag['id'],flow['organization_id'],flow['client_id'],page_host,safe_path,safe_path))
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
            (organization_id,client_id,tag_id,visitor_id,session_id,event_kind,event_name,page_host,page_path,
             referrer_host,utm_source,utm_medium,utm_campaign,utm_id,click_id,step_id,campaign_id,attribution_method)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (flow['organization_id'], flow['client_id'], tag['id'], visitor_id, visit_session,
             kind,event_name,page_host,safe_path,referrer,attribution_values['utm_source'],attribution_values['utm_medium'],
             attribution_values['utm_campaign'], attribution_values['utm_id'], attribution_values['click_id'],
             step_id, campaign_id, method))
        get_db().commit()
        return ('',204)
