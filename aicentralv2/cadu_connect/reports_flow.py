"""First-party Funnel Flow collection and URL-step mapping for Reports V1."""
import json
import math
import re
import secrets
import string
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse, urlunparse

from flask import abort, current_app, jsonify, request, session

from ..auth import login_required_api
from ..db import get_db
from .reports_v1 import _rows, _selection, _write_guard

MAX_TAG_EVENTS_PER_MINUTE = 1200
MAX_DISCOVERY_PAGES = 60
MAX_DISCOVERY_SITEMAP_URLS = 50000


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
        self.links, self.script_sources, self.resource_sources, self.forms, self.form_fields = [], [], [], 0, []
        self.title_parts, self.h1_parts = [], []
        self.inline_scripts, self.inline_script_size = [], 0
        self.in_title = self.in_h1 = self.in_form = self.in_inline_script = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'script' and attrs.get('src') and len(self.script_sources) < 300:
            self.script_sources.append(attrs['src'])
        if tag == 'script':
            self.in_inline_script = not bool(attrs.get('src'))
        if tag in ('img', 'iframe') and attrs.get('src') and len(self.resource_sources) < 300:
            self.resource_sources.append(attrs['src'])
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
        if tag == 'script': self.in_inline_script = False

    def handle_data(self, data):
        value = ' '.join(data.split())
        if value and self.in_title: self.title_parts.append(value)
        if value and self.in_h1: self.h1_parts.append(value)
        if value and self.in_inline_script and self.inline_script_size < 150_000:
            chunk = value[:150_000-self.inline_script_size]
            self.inline_scripts.append(chunk)
            self.inline_script_size += len(chunk)


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
                'script_sources': parser.script_sources, 'resource_sources': parser.resource_sources,
                'inline_scripts': '\n'.join(parser.inline_scripts),
                'forms': parser.forms, 'form_fields': parser.form_fields}
    return None


_SITE_TRACKER_SIGNATURES = {
    'google_ads': (r'googleadservices\.com|google\.com/pagead|gtag(?:/js)?[^"\']*AW-[0-9]+|AW-[0-9]{6,}',
                   r'gtag\s*\(\s*["\']config["\']\s*,\s*["\']AW-[0-9]+'),
    'meta_ads': (r'connect\.facebook\.net/[^"\']*fbevents\.js|facebook\.com/tr',
                 r'fbq\s*\(\s*["\']init["\']'),
    'linkedin_ads': (r'snap\.licdn\.com/li\.lms-analytics|linkedin\.com/insight|px\.ads\.linkedin\.com/collect',
                     r'_linkedin_partner_id\s*='),
    'tiktok': (r'analytics\.tiktok\.com/i18n/pixel/events\.js|business-api\.tiktok\.com',
               r'_ttp\s*\('),
    'amazon_ads': (r'amazon-adsystem\.com|aax\.amazon-adsystem', r'amazon_ads'),
    'spotify_ads': (r'(?:pixel|ads)\.spotify\.com', r'spotify_ads'),
    'disney_ads': (r'(?:ads\.)?disneyadvertising\.com', r'disney_ads'),
    'email': (r'(?:chimpstatic|list-manage)\.com|(?:js\.)?hs-scripts\.com|rdstation\.com\.br|activecampaign\.com|klaviyo\.com',
              r'(?!)'),
}


def _detect_page_integrations(page):
    """Return exact third-party tracker/link evidence; never infer a campaign source from a logo."""
    resources = [urljoin(page['url'], value) for value in
                 [*page.get('script_sources', []), *page.get('resource_sources', [])]]
    resource_hosts = [(urlparse(source).hostname or '').lower() for source in resources]
    inline_scripts = str(page.get('inline_scripts') or '')
    matches = []
    for platform, (script_pattern, inline_pattern) in _SITE_TRACKER_SIGNATURES.items():
        evidence = None
        for source, host in zip(resources, resource_hosts):
            if re.search(script_pattern, source, re.I) or re.search(script_pattern, host, re.I):
                evidence = f'recurso de {host}'
                break
        if evidence is None and re.search(inline_pattern, inline_scripts, re.I):
            evidence = 'código de rastreamento na página'
        if evidence:
            matches.append({'platform': platform, 'signal': 'tracker', 'evidence': evidence,
                            'page': page['path']})
    for link in page.get('links', []):
        parsed = urlparse(urljoin(page['url'], link))
        host = (parsed.hostname or '').lower()
        if host == 'wa.me' or host.endswith(('.whatsapp.com', '.whatsapp.net')):
            matches.append({'platform': 'whatsapp', 'signal': 'site_link',
                            'evidence': f'link de WhatsApp em {page["path"]}', 'page': page['path']})
            break
    return matches


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
    unique_sitemaps = list(dict.fromkeys(sitemap_urls))
    page_urls, pending = [], unique_sitemaps[:8]
    pending_index, truncated = 0, len(unique_sitemaps) > 8
    while pending_index < len(pending) and pending_index < 12:
        sitemap = pending[pending_index]
        pending_index += 1
        canonical = _canonical_page_url(sitemap, root_url, allowed_host)
        if not canonical: continue
        try:
            status, _, body = _fetch(canonical, body=True, accepted_types=('xml','text/'))
            if status != 200: continue
            locations = re.findall(r'<(?:\w+:)?loc[^>]*>\s*(.*?)\s*</(?:\w+:)?loc>', body, re.I | re.S)
            for location in locations:
                location = unquote(re.sub(r'&amp;', '&', location.strip()))
                item = _canonical_page_url(location, root_url, allowed_host)
                if item and item.lower().endswith('.xml') and item not in pending:
                    if len(pending) < 12:
                        pending.append(item)
                    else:
                        truncated = True
                elif item:
                    if len(page_urls) < MAX_DISCOVERY_SITEMAP_URLS:
                        page_urls.append(item)
                    else:
                        truncated = True
        except Exception:
            continue
    if pending_index < len(pending):
        truncated = True
    return list(dict.fromkeys(page_urls)), truncated


def _classify_discovered_page(page, root_host):
    source = f"{page['path']} {page['title']} {page.get('h1','')}".casefold()
    error_page = re.search(r'(^|[/\s_-])(?:404|500|erro|error|falha|indispon[ií]vel|n[aã]o.?encontrad)', source)
    conversion = re.search(r'obrigad|thank.?you|/success(?:/|$)|confirmation|confirmad|pedido.?conclu|compra.?realizada|form.?sent|envio.?conclu', source)
    form_words = re.search(r'contato|contact|fale.?conosco|solicit(e|acao|ação)|orcamento|orçamento|inscri(c|ç)(a|ã)o|cadastro|formul(a|á)rio|consultor|proposal|request', source)
    if error_page:
        role, confidence = 'error', .88
        evidence = ['URL ou título indica página de erro']
    elif conversion:
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


def _discover_site(root_url, allowed_host, seed_urls=None, excluded_pages=None):
    canonical_root = _canonical_page_url(root_url, root_url, allowed_host)
    if not canonical_root:
        abort(400, description='Use uma URL pública do domínio autorizado ou de um subdomínio dele.')
    sitemap_truncated = False
    if seed_urls is None:
        sitemap_urls, sitemap_truncated = _site_sitemap_urls(canonical_root, allowed_host)
        seed_urls = [canonical_root, *sitemap_urls]
    excluded_pages = set(excluded_pages or ())
    found, queued = {}, []
    for candidate in dict.fromkeys(seed_urls):
        parsed_candidate = urlparse(candidate)
        key = ((parsed_candidate.hostname or '').lower().rstrip('.'), parsed_candidate.path or '/')
        if key not in excluded_pages:
            queued.append(candidate)
    attempted = 0
    while queued and len(found) < MAX_DISCOVERY_PAGES and attempted < MAX_DISCOVERY_PAGES:
        batch = []
        while (queued and len(batch) < 10
               and attempted + len(batch) < MAX_DISCOVERY_PAGES
               and len(found) + len(batch) < MAX_DISCOVERY_PAGES):
            candidate = queued.pop(0)
            if candidate not in found and candidate not in batch: batch.append(candidate)
        if not batch: continue
        attempted += len(batch)
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(_fetch_site_page, item, allowed_host): item for item in batch}
            pages = []
            for future in as_completed(futures):
                try: pages.append(future.result())
                except Exception: pages.append(None)
        for page in pages:
            if not page: continue
            page['integrations'] = _detect_page_integrations(page)
            page.pop('inline_scripts', None)
            key = (page['host'], page['path'])
            if key in excluded_pages:
                continue
            found[key] = page
            for link in page['links']:
                candidate = _canonical_page_url(link, page['url'], allowed_host)
                candidate_parsed = urlparse(candidate) if candidate else None
                candidate_key = ((candidate_parsed.hostname or '').lower().rstrip('.'), candidate_parsed.path or '/') if candidate_parsed else None
                if (candidate and candidate_key not in excluded_pages and candidate not in found
                        and candidate not in queued and len(queued) < MAX_DISCOVERY_SITEMAP_URLS + 300):
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
    role_order = {'entry':0,'form':1,'conversion':2,'error':3,'intermediate':4}
    remaining = []
    queued_seen = set()
    for candidate in queued:
        parsed_candidate = urlparse(candidate)
        key = ((parsed_candidate.hostname or '').lower().rstrip('.'), parsed_candidate.path or '/')
        if key not in excluded_pages and key not in found and candidate not in queued_seen:
            queued_seen.add(candidate)
            remaining.append(candidate)
    return sorted(results, key=lambda page: (role_order[page['role']],page['host'],page['path'])), remaining, sitemap_truncated


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


def _normalize_flow_config(config, allowed_host):
    if not isinstance(config, dict):
        abort(400, description='A configuração do fluxo precisa ser um objeto.')
    nodes, edges = config.get('nodes', []), config.get('edges', [])
    known_types = {'source','page','form','event','condition','delay','segment','conversion','webhook','whatsapp','error'}
    measured_types = {'page','form','event','conversion','whatsapp','error'}
    if not isinstance(nodes, list) or len(nodes) > 100 or not isinstance(edges, list) or len(edges) > 300:
        abort(400, description='O fluxo aceita até 100 blocos e 300 conexões.')
    normalized, ids = [], set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or node.get('type') not in known_types:
            abort(400, description='O fluxo contém um bloco inválido.')
        node_id = node.get('id')
        if not isinstance(node_id, str) or not node_id or len(node_id) > 80 or node_id in ids:
            abort(400, description='Cada bloco precisa ter um identificador único.')
        ids.add(node_id)
        node_type = node['type']
        title = ' '.join(str(node.get('title') or node_type).split())[:120]
        path = node.get('path', '')
        if node_type in measured_types and (not isinstance(path, str) or not path.startswith('/')
                or '?' in path or '#' in path or len(path) > 500):
            abort(400, description='Cada etapa medida precisa de um caminho interno válido.')
        host = node.get('host') or None
        if host:
            host = _host(host)
            if not _host_allowed(host, allowed_host):
                abort(400, description='O bloco precisa usar o domínio autorizado ou um subdomínio dele.')
        event_name = str(node.get('event_name') or node.get('event') or
                         ('evento_personalizado' if node_type == 'event' else ''))[:80]
        if node_type == 'event' and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', event_name):
            abort(400, description='Configure um nome válido para cada evento personalizado.')
        position = {}
        for axis, default in (('x', 80 + (index % 3) * 220), ('y', 60 + (index // 3) * 130)):
            value = node.get(axis, default)
            if isinstance(value, bool):
                abort(400, description='A posição de um bloco é inválida.')
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                abort(400, description='A posição de um bloco é inválida.')
            if not math.isfinite(numeric) or not 0 <= numeric <= 10000:
                abort(400, description='Mantenha os blocos dentro da área do editor.')
            position[axis] = round(numeric)
        item = {'id': node_id, 'type': node_type, 'title': title,
                'x': position['x'], 'y': position['y']}
        if isinstance(path, str) and path:
            item['path'] = path
        if host:
            item['host'] = host
        if event_name:
            item['event_name'] = event_name
        for field in ('source','event','discoveryPageId','stepId'):
            if isinstance(node.get(field), str):
                item[field] = node[field][:120]
        if isinstance(node.get('fields'), list):
            item['fields'] = [{'name':str(field.get('name') or '')[:80],
                'label':str(field.get('label') or '')[:100],
                'required':bool(field.get('required'))}
                for field in node['fields'][:30] if isinstance(field, dict)]
        if isinstance(node.get('isEntry'), bool):
            item['isEntry'] = node['isEntry']
        normalized.append(item)
    normalized_edges = []
    for edge in edges:
        if not isinstance(edge, dict):
            abort(400, description='O fluxo contém uma conexão inválida.')
        source, target = edge.get('from'), edge.get('to')
        if not isinstance(source, str) or not isinstance(target, str) or source not in ids or target not in ids or source == target:
            abort(400, description='Conecte blocos existentes e diferentes.')
        normalized_edges.append({'id':str(edge.get('id') or uuid.uuid4())[:80],
                                 'from':source,'to':target,
                                 'label':' '.join(str(edge.get('label') or 'Próximo').split())[:80]})
    result = {**config, 'nodes':normalized, 'edges':normalized_edges}
    if len(json.dumps(result, ensure_ascii=False)) > 256_000:
        abort(413, description='A configuração do fluxo excede o limite de armazenamento.')
    return result, any(node['type'] in measured_types for node in normalized)


def _client_tag_urls(client_id):
    client_id = int(client_id)
    base = str(current_app.config.get('CONNECT_URL') or request.url_root).rstrip('/')
    return {
        'flow': f'{base}/v2/flow.js?client={client_id}',
        'supertag': f'{base}/v1/supertag.js',
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
        requested_flow_id = request.args.get('flow_id', '').strip()
        selected_flow = _flow_row(requested_flow_id, selected) if requested_flow_id else None
        try:
            days = int(request.args.get('days', 30))
        except (ValueError, TypeError):
            abort(400, description='Período inválido.')
        if days not in (7, 30, 90):
            abort(400, description='Período inválido.')
        scope_params = [*params, days]
        conversion_params = [*params, days]
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
                conversion_params.append(number)
        platform = request.args.get('platform', '').strip()
        if platform:
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', platform):
                abort(400, description='Plataforma inválida.')
            event_filter += ' AND a.platform=%s'
            conversion_filter += ' AND a.platform=%s'
            scope_params.append(platform)
            conversion_params.append(platform)
        if selected_flow:
            event_filter += ' AND e.tag_id=%s'
            conversion_filter += ''' AND x.campaign_id IN (
                SELECT campaign_id FROM cadu_reports_flow_steps
                WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND campaign_id IS NOT NULL)'''
            scope_params.append(selected_flow['tag_id'])
            conversion_params.extend((selected_flow['tag_id'],selected['organization_id'],
                                      selected['client_id']))
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
        if start_date and end_date:
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
        elif start_date or end_date:
            abort(400, description='Informe as duas datas do intervalo.')
        event_scoped_events = '''WITH selected_events AS (
            SELECT e.* FROM cadu_reports_flow_events e
            LEFT JOIN cadu_reports_campaigns c ON c.id=e.campaign_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
            WHERE e.organization_id=%s AND e.client_id=%s
            ''' + event_period_filter + event_filter + event_date_filter + ') '
        # Older Reports databases may not have the custom-event column yet.
        # Check before issuing the query: a caught PostgreSQL error still marks
        # the transaction as failed, so retrying in the same transaction returns
        # another 500.
        has_event_name = _rows('''SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='cadu_reports_flow_events'
              AND column_name='event_name') AS ready''')[0]['ready']
        event_name_expr = "COALESCE(NULLIF(event_name,''),event_kind)" if has_event_name else 'event_kind'
        canvas_event_name_expr = 'e.event_name' if has_event_name else "''::text"
        tags = _rows('''SELECT id,label,allowed_host,public_key,created_at,revoked_at,tag_kind
            FROM cadu_reports_site_tags WHERE organization_id=%s AND client_id=%s
                AND (%s::uuid IS NULL OR id=%s::uuid) ORDER BY created_at DESC''',
            (*params,selected_flow['tag_id'] if selected_flow else None,
             selected_flow['tag_id'] if selected_flow else None))
        steps = _rows('''SELECT s.id,s.tag_id,s.name,s.path_prefix,s.page_host,s.step_kind,s.is_entry,s.campaign_id,s.position,
            s.is_active,s.archived_at,
            c.name AS campaign_name FROM cadu_reports_flow_steps s
            LEFT JOIN cadu_reports_campaigns c ON c.id=s.campaign_id
            WHERE s.organization_id=%s AND s.client_id=%s AND s.is_active=TRUE
                AND (%s::uuid IS NULL OR s.tag_id=%s::uuid)
            ORDER BY s.is_entry DESC,s.position,s.id''',
            (*params,selected_flow['tag_id'] if selected_flow else None,
             selected_flow['tag_id'] if selected_flow else None))
        supertag_sites = _rows('''SELECT id,public_id,label,allowed_host,enabled,revoked_at
            FROM cadu_reports_supertag_sites WHERE organization_id=%s AND client_id=%s
                AND enabled=TRUE AND revoked_at IS NULL ORDER BY created_at DESC''', params)
        from .reports_supertag import _supertag_snippet
        for site in supertag_sites:
            site['snippet'] = _supertag_snippet(site)
        flows = _rows('''SELECT f.id,f.flow_code,f.name,f.status,f.config,f.tag_id,t.label AS tag_label,
                t.allowed_host,t.public_key,t.revoked_at,f.created_at,f.updated_at,f.published_at,
                f.monitor_enabled,f.monitor_interval_minutes,f.monitor_status,f.monitor_checked_at,
                (SELECT STRING_AGG(DISTINCT c.name, ' · ' ORDER BY c.name)
                    FROM cadu_reports_flow_steps s
                    JOIN cadu_reports_campaigns c ON c.id=s.campaign_id
                        AND c.organization_id=s.organization_id AND c.client_id=s.client_id
                    WHERE s.tag_id=f.tag_id AND s.organization_id=f.organization_id
                        AND s.client_id=f.client_id AND s.is_active=TRUE) AS campaign_names
            FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
            WHERE f.organization_id=%s AND f.client_id=%s ORDER BY f.created_at DESC''', params)
        view = request.args.get('view', 'monitor')
        if view in {'create', 'edit'}:
            return jsonify(tags=tags,steps=steps,flows=flows,events=[],event_group_count=0,
                event_summary={},tag_urls=_client_tag_urls(selected['client_id']),activity=[],
                online=0,conversions=0,site_pages=[],page_transitions=[],confirmed=[],period_days=days,
                canvas_nodes=[],canvas_edges=[],monitor_checks=[],supertag_sites=supertag_sites,
                performance_mode='configuration')
        if view not in {'monitor', 'create', 'edit'}:
            abort(400,description='Área de fluxos inválida.')
        activity = _rows(scoped_events + '''SELECT e.tag_id,e.page_path,
            COUNT(*) FILTER (WHERE e.event_kind IN ('page_view','conversion','error_view')) AS views,
            COUNT(*) FILTER (WHERE e.event_kind='form_submit') AS form_submissions,
            COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click')) AS clicks,
            COUNT(DISTINCT e.visitor_id) FILTER (WHERE e.event_kind IN ('page_view','conversion','error_view')) AS visitors,
            COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind IN ('page_view','conversion','error_view','heartbeat','form_submit','click','whatsapp_click','page_leave')
                AND e.occurred_at > NOW() - INTERVAL '90 seconds') AS online,
            COUNT(DISTINCT e.visitor_id) FILTER (WHERE e.event_kind='conversion') AS conversions
            FROM selected_events e
            GROUP BY e.tag_id,e.page_path ORDER BY views DESC LIMIT 100''', tuple(scope_params))
        site_pages = _rows(event_scoped_events + ''', page_events AS (
            SELECT e.*,COALESCE(s.step_kind,'') AS mapped_kind,
                ROW_NUMBER() OVER (PARTITION BY e.session_id ORDER BY e.occurred_at,e.id) AS page_order
            FROM selected_events e LEFT JOIN cadu_reports_flow_steps s ON s.id=e.step_id
            WHERE e.event_kind IN ('page_view','conversion','error_view')
        ), outcomes AS (
            SELECT session_id,
                MIN(occurred_at) FILTER (WHERE event_kind='form_submit') AS first_form_at,
                MIN(occurred_at) FILTER (WHERE event_kind='conversion') AS first_conversion_at
            FROM selected_events GROUP BY session_id
        ), dwell AS (
            SELECT page_host,page_path,ROUND(AVG(duration_ms)::numeric/1000,1) AS avg_seconds,
                COUNT(*)::bigint AS measured_visits
            FROM selected_events WHERE event_kind='page_leave' AND duration_ms IS NOT NULL
            GROUP BY page_host,page_path
        ), form_actions AS (
            SELECT page_host,page_path,COUNT(*)::bigint AS submissions,
                COUNT(DISTINCT session_id)::bigint AS submit_sessions
            FROM selected_events WHERE event_kind='form_submit' GROUP BY page_host,page_path
        )
        SELECT p.page_host,p.page_path,COUNT(*)::bigint AS views,
            COUNT(DISTINCT p.visitor_id)::bigint AS visitors,
            COUNT(DISTINCT p.session_id)::bigint AS sessions,
            COUNT(DISTINCT p.session_id) FILTER (WHERE p.page_order=1)::bigint AS entry_sessions,
            COALESCE(d.avg_seconds,0) AS avg_seconds,COALESCE(d.measured_visits,0) AS measured_visits,
            COALESCE(f.submissions,0) AS form_submissions,
            COUNT(DISTINCT p.session_id) FILTER (WHERE o.first_form_at>=p.occurred_at)::bigint AS sessions_to_form,
            COUNT(DISTINCT p.session_id) FILTER (WHERE o.first_conversion_at>=p.occurred_at)::bigint AS sessions_to_conversion,
            COUNT(*) FILTER (WHERE p.event_kind='error_view')::bigint AS error_views,
            BOOL_OR(p.mapped_kind='form') AS is_form_page,
            BOOL_OR(p.event_kind='conversion' OR p.mapped_kind='conversion') AS is_conversion_page,
            BOOL_OR(p.event_kind='error_view' OR p.mapped_kind='error') AS is_error_page,
            ARRAY_AGG(DISTINCT COALESCE(NULLIF(p.utm_source,''),p.referrer_host,'Direto')) AS sources
        FROM page_events p LEFT JOIN outcomes o ON o.session_id=p.session_id
        LEFT JOIN dwell d ON d.page_host=p.page_host AND d.page_path=p.page_path
        LEFT JOIN form_actions f ON f.page_host=p.page_host AND f.page_path=p.page_path
        GROUP BY p.page_host,p.page_path,d.avg_seconds,d.measured_visits,f.submissions
        ORDER BY views DESC LIMIT 200''', tuple(event_scope_params))
        page_transitions = _rows(event_scoped_events + ''', ordered_pages AS (
            SELECT e.session_id,e.page_host,e.page_path,e.occurred_at,
                LEAD(e.page_host) OVER (PARTITION BY e.session_id ORDER BY e.occurred_at,e.id) AS next_host,
                LEAD(e.page_path) OVER (PARTITION BY e.session_id ORDER BY e.occurred_at,e.id) AS next_path
            FROM selected_events e WHERE e.event_kind IN ('page_view','conversion','error_view')
        ) SELECT page_host,page_path,next_host,next_path,COUNT(DISTINCT session_id)::bigint AS sessions
          FROM ordered_pages WHERE next_path IS NOT NULL
          GROUP BY page_host,page_path,next_host,next_path ORDER BY sessions DESC LIMIT 300''',
          tuple(event_scope_params))
        totals = _rows(scoped_events + '''SELECT
            COUNT(DISTINCT session_id) FILTER (WHERE event_kind IN ('page_view','conversion','error_view','heartbeat','form_submit','click','whatsapp_click','page_leave')
                AND occurred_at > NOW() - INTERVAL '90 seconds') AS online,
            COUNT(DISTINCT visitor_id) FILTER (WHERE event_kind='conversion') AS conversions
            FROM selected_events''', tuple(scope_params))[0]
        event_inventory_query = event_scoped_events + f'''SELECT event_kind,{event_name_expr} AS event_name,page_path,
            COALESCE(utm_source,referrer_host,'Website') AS source_label,
            MAX(occurred_at) AS last_occurred_at,COUNT(*)::bigint AS total,
            COUNT(*) FILTER (WHERE step_id IS NOT NULL)::bigint AS mapped,
            COUNT(*) OVER() AS group_count
            FROM selected_events
            GROUP BY event_kind,{event_name_expr},page_path,COALESCE(utm_source,referrer_host,'Website')
            ORDER BY last_occurred_at DESC LIMIT 300'''
        event_inventory = _rows(event_inventory_query, tuple(event_scope_params))
        event_summary = _rows(event_scoped_events + '''SELECT COUNT(*)::bigint AS total,
            COUNT(*) FILTER (WHERE event_kind='form_submit')::bigint AS form_submissions,
            COUNT(*) FILTER (WHERE event_kind='conversion')::bigint AS conversions,
            COUNT(*) FILTER (WHERE event_kind='error_view')::bigint AS error_views,
            COUNT(*) FILTER (WHERE event_kind='page_leave')::bigint AS page_leave_count,
            ROUND((AVG(duration_ms) FILTER (WHERE event_kind='page_leave'))/1000,1) AS avg_active_seconds,
            COUNT(*) FILTER (WHERE utm_source IS NOT NULL OR referrer_host IS NOT NULL)::bigint AS attributed
            FROM selected_events''', tuple(event_scope_params))[0]
        progression = _rows(scoped_events + ''' , first_step AS (
            SELECT session_id,step_id,MIN(occurred_at) AS first_at
            FROM selected_events WHERE step_id IS NOT NULL
                AND event_kind IN ('page_view','conversion','error_view')
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
        canvas_nodes = []
        if selected_flow and isinstance(selected_flow.get('config'), dict):
            configured_nodes = [node for node in selected_flow['config'].get('nodes', [])
                if isinstance(node, dict) and node.get('type') in ('page','form','event','conversion','whatsapp','error')
                and isinstance(node.get('path'), str) and node['path'].startswith('/')]
            configured_nodes = configured_nodes[:100]
            configured_edges = [edge for edge in selected_flow['config'].get('edges', [])
                if isinstance(edge, dict) and isinstance(edge.get('from'), str)
                and isinstance(edge.get('to'), str)]
            if configured_nodes:
                node_json = json.dumps([{'node_id': str(node.get('id') or ''),
                    'node_type': node['type'], 'path': _safe_path(node['path']),
                    'host': _host(node.get('host')) if node.get('host') else None,
                    'event_name': str(node.get('event_name') or '')[:120]} for node in configured_nodes])
                edge_json = json.dumps([{'source_id': edge['from'], 'target_id': edge['to']}
                    for edge in configured_edges if edge['from'] != edge['to']])
                canvas_nodes = _rows(event_scoped_events + f''', configured_nodes AS (
                    SELECT * FROM jsonb_to_recordset(%s::jsonb) AS n(
                        node_id TEXT,node_type TEXT,path TEXT,host TEXT,event_name TEXT)
                ), matched AS (
                    SELECT e.session_id,n.node_id,e.occurred_at FROM selected_events e
                    JOIN configured_nodes n ON (n.host IS NULL OR n.host=e.page_host)
                        AND (n.path='/' OR e.page_path=n.path OR
                             e.page_path LIKE rtrim(n.path,'/') || '/%%')
                    WHERE (n.node_type='page' AND e.event_kind IN ('page_view','conversion','error_view'))
                       OR (n.node_type='conversion' AND e.event_kind='conversion')
                       OR (n.node_type='error' AND e.event_kind='error_view')
                       OR (n.node_type='form' AND e.event_kind='form_submit')
                       OR (n.node_type='whatsapp' AND e.event_kind='whatsapp_click')
                       OR (n.node_type='event' AND e.event_kind='custom_event'
                           AND (n.event_name='' OR n.event_name={canvas_event_name_expr}))
                ), configured_edges AS (
                    SELECT * FROM jsonb_to_recordset(%s::jsonb) AS x(source_id TEXT,target_id TEXT)
                ), reached AS (
                    SELECT node_id,COUNT(DISTINCT session_id)::bigint AS reached
                    FROM matched GROUP BY node_id
                ), progressed AS (
                    SELECT edge.target_id AS node_id,
                        COUNT(DISTINCT target.session_id)::bigint AS progressed
                    FROM configured_edges edge
                    JOIN matched source ON source.node_id=edge.source_id
                    JOIN matched target ON target.node_id=edge.target_id
                        AND target.session_id=source.session_id AND target.occurred_at>=source.occurred_at
                    GROUP BY edge.target_id
                )
                SELECT n.node_id AS id,COALESCE(r.reached,0) AS reached,
                    COALESCE(p.progressed,0) AS progressed
                FROM configured_nodes n LEFT JOIN reached r USING(node_id)
                LEFT JOIN progressed p USING(node_id)''',
                    tuple(event_scope_params) + (node_json, edge_json))
                metrics_by_node = {item['id']: item for item in canvas_nodes}
                for node in configured_nodes:
                    metric = metrics_by_node.get(str(node.get('id') or ''), {})
                    node['reached'] = metric.get('reached', 0)
                    node['progressed'] = metric.get('progressed', 0)
                canvas_nodes = configured_nodes
        confirmed_time_filter = 'x.occurred_at > NOW() - (%s * INTERVAL \'1 day\')'
        confirmed_params = list(conversion_params)
        if start_date and end_date:
            confirmed_time_filter = "x.occurred_at >= %s::date AND x.occurred_at < (%s::date + INTERVAL '1 day')"
            confirmed_params = [*params, parsed_start.isoformat(), parsed_end.isoformat(), *conversion_params[3:]]
        confirmed = _rows('''SELECT x.conversion_kind,COUNT(*)::bigint AS total
            FROM cadu_reports_external_conversions x
            LEFT JOIN cadu_reports_campaigns c ON c.id=x.campaign_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
            WHERE x.organization_id=%s AND x.client_id=%s
                AND ''' + confirmed_time_filter + conversion_filter +
            ' GROUP BY x.conversion_kind ORDER BY x.conversion_kind', tuple(confirmed_params))
        monitor_checks = []
        if selected_flow:
            monitor_checks = _rows('''SELECT id,status,checked_at,duration_ms,pages
                FROM cadu_reports_flow_monitor_checks WHERE flow_id=%s
                AND organization_id=%s AND client_id=%s ORDER BY checked_at DESC LIMIT 20''',
                (selected_flow['id'], *params))
        return jsonify(tags=tags, steps=steps, flows=flows, events=event_inventory,
                       event_group_count=event_inventory[0]['group_count'] if event_inventory else 0,
                       event_summary=event_summary,
                       tag_urls=_client_tag_urls(selected['client_id']), activity=activity,
                       online=totals['online'], conversions=totals['conversions'],
                       site_pages=site_pages,page_transitions=page_transitions,
                       confirmed=confirmed, period_days=days,
                       supertag_sites=supertag_sites,
                       canvas_nodes=canvas_nodes if selected_flow else [],
                       canvas_edges=(selected_flow.get('config') or {}).get('edges', []) if selected_flow else [],
                       monitor_checks=monitor_checks)

    @bp.patch('/api/v1/reports/flow/flows/<flow_id>/monitor')
    @login_required_api
    def reports_flow_configure_monitor(flow_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        enabled = payload.get('enabled')
        interval = payload.get('interval_minutes', 15)
        if not isinstance(enabled, bool) or isinstance(interval, bool) or not isinstance(interval, int) or interval not in (5, 15, 30, 60):
            abort(400, description='Informe a ativação e um intervalo de 5, 15, 30 ou 60 minutos.')
        if enabled and flow['status'] != 'published':
            abort(409, description='Publique o fluxo antes de ativar o monitoramento.')
        changed = _rows('''UPDATE cadu_reports_flow_registry SET monitor_enabled=%s,
                monitor_interval_minutes=%s,monitor_status=CASE WHEN %s THEN monitor_status ELSE 'unknown' END,
                monitor_next_check_at=CASE WHEN %s THEN NOW() ELSE NULL END,updated_at=NOW()
            WHERE id=%s AND organization_id=%s AND client_id=%s
            RETURNING id,monitor_enabled,monitor_interval_minutes,monitor_status,monitor_checked_at''',
            (enabled, interval, enabled, enabled, flow['id'], selected['organization_id'], selected['client_id']))
        get_db().commit()
        return jsonify(flow=changed[0])

    @bp.post('/api/v1/reports/flow/flows/<flow_id>/monitor/check')
    @login_required_api
    def reports_flow_check_monitor(flow_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        if flow['status'] != 'published':
            abort(409, description='Publique o fluxo antes de verificar suas páginas.')
        from .reports_flow_monitor import check_flow
        result = check_flow(flow['id'], selected['organization_id'], selected['client_id'])
        if result is None:
            abort(409, description='A tag do fluxo foi revogada ou não está disponível.')
        return jsonify(check=result)

    @bp.post('/api/v1/reports/flow/flows/<flow_id>/discover')
    @login_required_api
    def reports_flow_discover_site(flow_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict): abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        requested_run_id = payload.get('run_id')
        active_run, excluded_pages, seed_urls = None, set(), None
        if requested_run_id:
            run_id = _uuid(requested_run_id, 'Varredura')
            runs = _rows('''SELECT id,root_url,status,page_count,pending_urls,pending_truncated
                FROM cadu_reports_flow_discovery_runs
                WHERE id=%s AND organization_id=%s AND client_id=%s AND tag_id=%s FOR UPDATE''',
                (run_id,selected['organization_id'],selected['client_id'],flow['tag_id']))
            if not runs:
                abort(404,description='Varredura não encontrada neste fluxo.')
            active_run = runs[0]
            if active_run['status']!='partial':
                abort(409,description='Esta varredura já terminou. Inicie um novo mapeamento do site.')
            seed_urls = active_run['pending_urls'] if isinstance(active_run['pending_urls'],list) else []
            if not seed_urls:
                abort(409,description='O sitemap excedeu o limite seguro de URLs; divida o sitemap para continuar.')
            root_url = active_run['root_url']
            seen_pages = _rows('''SELECT page_host,path_prefix FROM cadu_reports_flow_discovered_pages
                WHERE run_id=%s AND organization_id=%s AND client_id=%s''',
                (run_id,selected['organization_id'],selected['client_id']))
            excluded_pages = {(page['page_host'],page['path_prefix']) for page in seen_pages}
        else:
            root_url = str(payload.get('root_url') or f"https://{flow['allowed_host']}").strip()
            parsed = urlparse(root_url if '://' in root_url else 'https://' + root_url)
            if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:
                abort(400, description='Informe a URL pública inicial do site.')
            root_url = _canonical_page_url(root_url if '://' in root_url else 'https://' + root_url,
                                           f"https://{flow['allowed_host']}", flow['allowed_host'])
            if not root_url:
                abort(400, description='O mapeamento só pode visitar o domínio autorizado e seus subdomínios.')
            run_id = str(uuid.uuid4())
            _rows('''INSERT INTO cadu_reports_flow_discovery_runs
                (id,organization_id,client_id,tag_id,root_url,status,page_count,created_by)
                VALUES (%s,%s,%s,%s,%s,'partial',0,%s) RETURNING id''',
                (run_id,selected['organization_id'],selected['client_id'],flow['tag_id'],
                 root_url,session['user_id']))
        pages, pending_urls, sitemap_truncated = _discover_site(
            root_url,flow['allowed_host'],seed_urls=seed_urls,excluded_pages=excluded_pages)
        pending_truncated = bool(sitemap_truncated or (active_run and active_run['pending_truncated']))
        mapped_steps = _rows('''SELECT id,page_host,path_prefix,step_kind,is_entry
            FROM cadu_reports_flow_steps WHERE tag_id=%s AND organization_id=%s AND client_id=%s
                AND is_active=TRUE AND step_kind IN ('page','form','conversion','error')''',
            (flow['tag_id'],selected['organization_id'],selected['client_id']))
        steps_by_page, wildcard_steps = {}, {}
        for step in mapped_steps:
            if step['page_host']:
                steps_by_page[(step['page_host'],step['path_prefix'])] = step
            else:
                wildcard_steps.setdefault(step['path_prefix'], []).append(step)
        stored = []
        for page in pages:
            evidence = {'signals': page['evidence'], 'h1': page.get('h1',''),
                        'integrations': page.get('integrations', [])}
            prior_step = steps_by_page.get((page['host'],page['path']))
            if prior_step is None:
                wildcard_matches = wildcard_steps.get(page['path'], [])
                if len(wildcard_matches) == 1:
                    prior_step = wildcard_matches[0]
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
        run_counts = _rows('''SELECT COUNT(*)::integer AS page_count FROM cadu_reports_flow_discovered_pages
            WHERE run_id=%s AND organization_id=%s AND client_id=%s''',
            (run_id,selected['organization_id'],selected['client_id']))[0]
        status='partial' if pending_urls or pending_truncated else 'completed' if run_counts['page_count'] else 'failed'
        _rows('''UPDATE cadu_reports_flow_discovery_runs SET status=%s,page_count=%s,
                pending_urls=%s::jsonb,pending_truncated=%s
            WHERE id=%s AND organization_id=%s AND client_id=%s RETURNING id''',
            (status,run_counts['page_count'],json.dumps(pending_urls),pending_truncated,
             run_id,selected['organization_id'],selected['client_id']))
        get_db().commit()
        return jsonify(run={'id':run_id,'root_url':root_url,'status':status,
                            'page_count':run_counts['page_count'],'pending_count':len(pending_urls),
                            'pending_truncated':pending_truncated},pages=stored)

    @bp.get('/api/v1/reports/flow/flows/<flow_id>/discoveries')
    @login_required_api
    def reports_flow_discoveries(flow_id):
        selected = _selection()
        flow = _flow_row(flow_id, selected)
        runs = _rows('''SELECT id,root_url,status,page_count,created_at,
                jsonb_array_length(pending_urls) AS pending_count,pending_truncated
            FROM cadu_reports_flow_discovery_runs WHERE organization_id=%s AND client_id=%s AND tag_id=%s
            ORDER BY created_at DESC LIMIT 1''',
            (selected['organization_id'],selected['client_id'],flow['tag_id']))
        pages = []
        if runs:
            pages = _rows('''SELECT p.id,p.url,p.page_host,p.path_prefix,p.title,p.suggested_role,p.confidence,p.evidence,
                p.form_count,p.form_fields,p.selected_kind,p.selected_as_entry,p.step_id,s.campaign_id
                FROM cadu_reports_flow_discovered_pages p
                LEFT JOIN cadu_reports_flow_steps s ON s.id=p.step_id AND s.organization_id=p.organization_id
                    AND s.client_id=p.client_id
                WHERE p.run_id=%s AND p.organization_id=%s AND p.client_id=%s
                ORDER BY CASE suggested_role WHEN 'entry' THEN 0 WHEN 'form' THEN 1 WHEN 'conversion' THEN 2 ELSE 3 END,
                    p.page_host,p.path_prefix''', (runs[0]['id'],selected['organization_id'],selected['client_id']))
        integration_summary = {}
        scanned_pages = 0
        for page in pages:
            evidence = page.get('evidence') or {}
            if isinstance(evidence, dict) and 'integrations' in evidence:
                scanned_pages += 1
                for signal in evidence['integrations'] or []:
                    key = (signal.get('platform'), signal.get('signal'))
                    summary = integration_summary.setdefault(key, {'platform':key[0], 'signal':key[1],
                        'pages':0, 'evidence':[]})
                    summary['pages'] += 1
                    if len(summary['evidence']) < 3:
                        summary['evidence'].append(signal.get('evidence'))
        return jsonify(run=runs[0] if runs else None,pages=pages,
                       platform_integrations=list(integration_summary.values()),
                       integration_scan_pages=scanned_pages)

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
        if choice not in ('ignore','entry','intermediate','form','conversion','error'):
            abort(400,description='Escolha entrada, etapa intermediária, formulário, conversão ou ignorar.')
        campaign_id=payload.get('campaign_id') or None
        if campaign_id is not None:
            if isinstance(campaign_id,bool): abort(400,description='Campanha inválida.')
            try: campaign_id=int(campaign_id)
            except (TypeError,ValueError): abort(400,description='Campanha inválida.')
            if choice=='ignore': abort(400,description='Inclua a página no fluxo antes de associar uma campanha.')
            if not _rows('''SELECT id FROM cadu_reports_campaigns WHERE id=%s
                    AND organization_id=%s AND client_id=%s''',
                    (campaign_id,selected['organization_id'],selected['client_id'])):
                abort(404,description='Campanha não encontrada neste cliente.')
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
        step_kind={'entry':'page','intermediate':'page','form':'form','conversion':'conversion','error':'error'}[choice]
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
                step_kind=%s,is_entry=%s,position=%s,campaign_id=%s,is_active=TRUE,archived_at=NULL
                WHERE id=%s AND organization_id=%s AND client_id=%s
                RETURNING id,name,path_prefix,page_host,step_kind,is_entry,position,campaign_id''',
                (name,page['path_prefix'],page['page_host'],step_kind,is_entry,
                 0 if is_entry else _rows('SELECT position FROM cadu_reports_flow_steps WHERE id=%s',(step_id,))[0]['position'],campaign_id,step_id,
                 selected['organization_id'],selected['client_id']))
            step=changed[0]
        else:
            position=_rows('''SELECT COALESCE(MAX(position),-1)+1 AS position FROM cadu_reports_flow_steps
                WHERE tag_id=%s AND organization_id=%s AND client_id=%s AND is_active=TRUE''',
                (flow['tag_id'],selected['organization_id'],selected['client_id']))[0]['position']
            created=_rows('''INSERT INTO cadu_reports_flow_steps
                (organization_id,client_id,tag_id,name,path_prefix,page_host,step_kind,is_entry,position,campaign_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id,name,path_prefix,page_host,step_kind,is_entry,position,campaign_id''',
                (selected['organization_id'],selected['client_id'],flow['tag_id'],name,
                 page['path_prefix'],page['page_host'],step_kind,is_entry,0 if is_entry else position,campaign_id))
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
        return jsonify(page_id=str(page['id']),selection=choice,step=step,node=node,campaign_id=campaign_id)

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
        from .reports_supertag import ensure_supertag_site
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
        requested_host = _host(payload.get('allowed_host') or (tag or {}).get('allowed_host'))
        supertag_site, _ = ensure_supertag_site(selected, requested_host, name)
        if not tag:
            label = ' '.join(str(payload.get('tag_label') or name).split())[:120]
            host = requested_host
            tag = _rows('''INSERT INTO cadu_reports_site_tags
                (id,organization_id,client_id,label,allowed_host,public_key,created_by,tag_kind)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'flow')
                RETURNING id,label,allowed_host,public_key,created_at,revoked_at,tag_kind''',
                (str(uuid.uuid4()), selected['organization_id'], selected['client_id'],
                 label, host, secrets.token_urlsafe(24), session['user_id']))[0]
        config, _ = _normalize_flow_config(
            payload.get('config') if isinstance(payload.get('config'), dict) else {}, tag['allowed_host'])
        flow_id = str(uuid.uuid4())
        flow_code = _new_flow_code()
        created = _rows('''INSERT INTO cadu_reports_flow_registry
            (id,organization_id,client_id,flow_code,tag_id,name,config,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
            RETURNING id,flow_code,name,status,config,tag_id,created_at,updated_at''',
            (flow_id, selected['organization_id'], selected['client_id'], flow_code,
             tag['id'], name, json.dumps(config), session['user_id']))[0]
        get_db().commit()
        return jsonify(flow=created, tag=tag, supertag_site=supertag_site,
                       tag_urls=_client_tag_urls(selected['client_id'])), 201

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
        config, _ = _normalize_flow_config(config, current['allowed_host'])
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
        config, has_measured_steps = _normalize_flow_config(flow.get('config') or {}, flow['allowed_host'])
        if not has_measured_steps:
            abort(409, description='Adicione ao menos uma página, formulário, evento, conversão ou clique de WhatsApp antes de publicar.')
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
        if kind not in ('page', 'conversion', 'form', 'event', 'whatsapp', 'error'):
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
        if kind not in ('page', 'conversion', 'form', 'event', 'whatsapp', 'error') or (kind == 'conversion' and path == '/'):
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
        shared_site = _rows('''SELECT allowed_host FROM cadu_reports_supertag_sites
            WHERE organization_id=%s AND client_id=%s AND enabled=TRUE AND revoked_at IS NULL''',
            (tag['organization_id'], tag['client_id']))
        if any(_host_allowed(tag['allowed_host'], item['allowed_host']) for item in shared_site):
            abort(410, description='Este domínio usa a Super Tag compartilhada. Remova a tag antiga de Fluxos.')
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
        shared_site = _rows('''SELECT allowed_host FROM cadu_reports_supertag_sites
            WHERE organization_id=%s AND client_id=%s AND enabled=TRUE AND revoked_at IS NULL''',
            (flow['organization_id'], flow['client_id']))
        if any(_host_allowed(flow['allowed_host'], item['allowed_host']) for item in shared_site):
            abort(410, description='Este domínio usa a Super Tag compartilhada. Remova a tag antiga de Fluxos.')
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
        if kind not in ('page_view','page_leave','form_submit','click','whatsapp_click','conversion','heartbeat','custom_event'):
            abort(400)
        event_name = ' '.join(str(payload.get('event_name') or '').split()) or None
        if kind == 'custom_event' and (not event_name or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', event_name)):
            abort(400, description='Use um nome de evento iniciado por letra, com letras, números ou _.')
        duration_ms = payload.get('duration_ms')
        if kind == 'page_leave':
            if isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float)) or not math.isfinite(duration_ms):
                abort(400, description='A duração informada para a página é inválida.')
            duration_ms = max(0, min(600000, round(duration_ms)))
        else:
            duration_ms = None
        path = str(payload.get('path') or '/')
        if not path.startswith('/') or '?' in path or '#' in path or len(path) > 500:
            abort(400)
        attribution = payload.get('attribution') if isinstance(payload.get('attribution'), dict) else {}
        session_id = _uuid(payload.get('session_id'), 'Sessão')
        configured_nodes = (flow.get('config') or {}).get('nodes', []) if isinstance(flow.get('config'), dict) else []
        matched_node = next((node for node in configured_nodes if isinstance(node, dict)
            and node.get('path') == path and (not node.get('host') or node.get('host')==page_host)
            and node.get('type') in ('page','form','event','conversion','whatsapp','error')
            and (node.get('type') != 'event' or
                 (kind == 'custom_event' and node.get('event_name') == event_name))), None)
        if kind == 'page_view' and matched_node and matched_node.get('type') == 'conversion':
            kind = 'conversion'
        if kind == 'page_view' and matched_node and matched_node.get('type') == 'error':
            kind = 'error_view'
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
        node_step_kind = {'form': 'form', 'event': 'event', 'whatsapp': 'whatsapp', 'conversion': 'conversion', 'error': 'error'}
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
        if kind == 'page_view' and matched_step and matched_step[0]['step_kind'] == 'error':
            kind = 'error_view'
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
             referrer_host,utm_source,utm_medium,utm_campaign,utm_id,click_id,step_id,campaign_id,attribution_method,duration_ms)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (flow['organization_id'], flow['client_id'], tag['id'], visitor_id, visit_session,
             kind,event_name,page_host,safe_path,referrer,attribution_values['utm_source'],attribution_values['utm_medium'],
             attribution_values['utm_campaign'], attribution_values['utm_id'], attribution_values['click_id'],
             step_id, campaign_id, method, duration_ms))
        get_db().commit()
        return ('',204)
