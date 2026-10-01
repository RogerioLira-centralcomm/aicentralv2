"""First-party Funnel Flow collection and URL-step mapping for Reports V1."""
import json
import math
import re
import secrets
import string
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse, urlunparse

from werkzeug.exceptions import BadRequest
from flask import abort, current_app, jsonify, request, session

from ..auth import login_required_api
from ..db import get_db
from .reports_v1 import _rows, _selection, _write_guard, _customer_id, _optional_positive_id
from .reports_flow_versions import expected_revision, lock_flow, save_draft, publish_draft, session_snapshot, match_version_step
from .reports_flow_schema import LEGACY_KINDS, legacy_projection, migrate_v1_to_v2
from .reports_flow_validation import MAX_FLOW_PAGES, validate_flow_config
from .reports_flow_stage import normalize_stage_position
from .reports_flow_metrics import apply_engagement, apply_session_bounds, edge_observation, origin_summary

MAX_TAG_EVENTS_PER_MINUTE = 1200
MAX_DISCOVERY_PAGES = 60
MAX_DISCOVERY_TOTAL_PAGES = 100


def _discovery_budget(already_found, requested=None):
    """Pages this call may crawl: a bounded batch, never past the total cap per mapping."""
    try:
        per_call = min(MAX_DISCOVERY_PAGES, max(1, int(requested))) if requested else MAX_DISCOVERY_PAGES
    except (TypeError, ValueError):
        per_call = MAX_DISCOVERY_PAGES
    return max(0, min(per_call, MAX_DISCOVERY_TOTAL_PAGES - max(0, int(already_found or 0))))
MAX_DISCOVERY_SITEMAP_URLS = 500


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
        self.structure=[]
        self.canonical=None
        self.hreflang={}
        self.noindex=False
        self.links, self.script_sources, self.resource_sources, self.forms, self.form_fields = [], [], [], 0, []
        self.title_parts, self.h1_parts = [], []
        self.inline_scripts, self.inline_script_size = [], 0
        self.in_title = self.in_h1 = self.in_form = self.in_inline_script = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('h1','h2','h3','main','article','section','form') and len(self.structure)<100:self.structure.append(tag)
        if tag=='link' and attrs.get('rel')=='canonical':self.canonical=attrs.get('href')
        if tag=='link' and 'alternate' in str(attrs.get('rel') or '').split() and attrs.get('hreflang') and attrs.get('href'):
            self.hreflang[attrs['hreflang']]=attrs['href']
        if tag=='meta' and str(attrs.get('name') or '').lower()=='robots' and 'noindex' in str(attrs.get('content') or '').lower():
            self.noindex=True
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
                'forms': parser.forms, 'form_fields': parser.form_fields,
                'structure_signature': '|'.join(parser.structure),
                'canonical': _canonical_page_url(parser.canonical,current,allowed_host) if parser.canonical else None,
                'hreflang': {locale: target for locale, href in parser.hreflang.items()
                             if (target := _canonical_page_url(href,current,allowed_host))},
                'noindex':parser.noindex or 'noindex' in str(headers.get('X-Robots-Tag','')).lower()}
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


def _discover_site(root_url, allowed_host, seed_urls=None, excluded_pages=None, max_pages=None, checkpoint=None, extra_urls=None):
    page_limit=min(500, max_pages or MAX_DISCOVERY_PAGES)
    canonical_root = _canonical_page_url(root_url, root_url, allowed_host)
    if not canonical_root:
        abort(400, description='Use uma URL pública do domínio autorizado ou de um subdomínio dele.')
    sitemap_truncated = False
    if seed_urls is None:
        sitemap_urls, sitemap_truncated = _site_sitemap_urls(canonical_root, allowed_host)
        seed_urls = [canonical_root, *sitemap_urls]
    seed_urls=[*seed_urls,*(extra_urls or [])]
    excluded_pages = set(excluded_pages or ())
    found, queued = {}, []
    for candidate in dict.fromkeys(seed_urls):
        parsed_candidate = urlparse(candidate)
        key = ((parsed_candidate.hostname or '').lower().rstrip('.'), parsed_candidate.path or '/')
        if key not in excluded_pages and len([part for part in parsed_candidate.path.split('/') if part])<=4:
            queued.append(candidate)
    attempted = 0
    visited_urls = set()
    while queued and len(found) < page_limit and attempted < page_limit:
        if checkpoint and not checkpoint():break
        batch = []
        while (queued and len(batch) < 10
               and attempted + len(batch) < page_limit
               and len(found) + len(batch) < page_limit):
            candidate = queued.pop(0)
            if candidate not in visited_urls and candidate not in batch:
                batch.append(candidate)
                visited_urls.add(candidate)
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
                if (candidate and len([p for p in candidate_parsed.path.split('/') if p])<=4 and candidate_key not in excluded_pages and candidate not in visited_urls
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


def _discovery_flow_groups(pages):
    primary, groups = [], {}
    for page in pages:
        path = page['path_prefix'].strip('/')
        section = path.split('/')[0] if path else ''
        landing = bool(re.search(r'^(lp|landing|landing-page|campanha|campaign|oferta|promo)([-/]|$)', path, re.I))
        if not landing and (not path or page['suggested_role'] in ('entry', 'form', 'conversion')
                            or section in ('contato', 'contact', 'sobre', 'about', 'servicos', 'services', 'produtos', 'products')):
            primary.append(page)
        else:
            if landing:
                section = '/'.join(path.split('/')[:2])
            key = f"{page['page_host']}/{section}"
            item = groups.setdefault(key, {'id': key, 'name': f"{'Landing pages' if landing else 'Páginas'} · {section}",
                                          'kind': 'landing' if landing else 'section', 'pages': []})
            item['pages'].append(page)
    return primary, list(groups.values())


def _assemble_discovered_flow(config, pages, allowed_host, max_pages=None):
    """Add verified pages and observed hyperlinks without replacing authored nodes.

    max_pages caps the page nodes of the resulting flow; the rest stays in the explorer."""
    nodes = [dict(node) for node in config.get('nodes', [])]
    edges = [dict(edge) for edge in config.get('edges', [])]
    by_page = {(node.get('host') or allowed_host, node.get('path')): node
               for node in nodes if node.get('type') in ('page', 'form', 'conversion', 'error')}
    groups = list(dict.fromkeys(node.get('pageGroup') for node in nodes if node.get('pageGroup')))
    omitted = 0
    for page in pages:
        key = (page['page_host'], page['path_prefix'])
        if key in by_page:
            continue
        page_count = sum(1 for node in nodes if node.get('type') in ('page', 'form', 'conversion', 'error'))
        if len(nodes) >= 200 or (max_pages is not None and page_count >= max_pages):
            omitted += 1
            continue
        path = page['path_prefix']
        section = path.strip('/').split('/')[0] if path.strip('/') else 'Início'
        group = f"{page['page_host']} · {section}"
        if group not in groups:
            groups.append(group)
        # Reserve a free rectangle, including authored positions and previous batches.
        preferred_column = min(groups.index(group), 31)
        columns = [preferred_column, *[col for col in range(32) if col != preferred_column]]
        position = next(((80 + col * 300, 100 + row * 240)
                         for col in columns for row in range(40)
                         if all(abs(float(node.get('x', 0)) - (80 + col * 300)) >= 280
                                or abs(float(node.get('y', 0)) - (100 + row * 240)) >= 220
                                for node in nodes)), None)
        if position is None:
            omitted += 1
            continue
        role = page['suggested_role']
        node = {'id': str(uuid.uuid4()), 'type': 'page', 'suggestedRole': role,
                'title': (page['title'] or path)[:120], 'path': path, 'host': page['page_host'],
                'isEntry': role == 'entry', 'discoveryPageId': str(page['id']),
                'pageGroup': group, 'x': position[0],
                'y': position[1], 'fields': page.get('form_fields') or []}
        nodes.append(node)
        by_page[key] = node
    pairs = {(edge['from'], edge['to']) for edge in edges}
    for page in pages:
        source = by_page.get((page['page_host'], page['path_prefix']))
        if not source:
            continue
        evidence = page.get('evidence') or {}
        for url in evidence.get('links', []):
            parsed = urlparse(url)
            target = by_page.get((parsed.hostname, parsed.path or '/'))
            pair = (source['id'], target['id']) if target else None
            if target and target != source and pair not in pairs and len(edges) < 300:
                edges.append({'id': str(uuid.uuid4()), 'from': pair[0], 'to': pair[1],
                              'label': 'Link no site', 'kind': 'site_link'})
                pairs.add(pair)
    return {**config, 'nodes': nodes, 'edges': edges}, omitted


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
    if config.get('schema_version', 1) not in (1, 2):
        abort(400, description='Versão de fluxo não suportada.')
    if config.get('schema_version') == 2:
        config = legacy_projection(config)
    nodes, edges = config.get('nodes', []), config.get('edges', [])
    known_types = {'source','page','form','event','condition','delay','segment','conversion','webhook','whatsapp','error'}
    measured_types = {'page','form','event','conversion','whatsapp','error'}
    if not isinstance(nodes, list) or len(nodes) > 200 or not isinstance(edges, list) or len(edges) > 300:
        abort(400, description='O fluxo aceita até 200 nós e 300 conexões.')
    normalized, ids = [], set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or node.get('type') not in known_types:
            abort(400, description='O fluxo contém um nó inválido.')
        node_id = node.get('id')
        if not isinstance(node_id, str) or not node_id or len(node_id) > 80 or node_id in ids:
            abort(400, description='Cada nó precisa ter um identificador único.')
        ids.add(node_id)
        node_type = node['type']
        title = ' '.join(str(node.get('title') or node_type).split())[:120]
        path = node.get('path', '')
        if node_type in measured_types and (not isinstance(path, str) or not path.startswith('/')
                or '?' in path or '#' in path or len(path) > 500):
            abort(400, description='Cada nó medido precisa de um caminho interno válido.')
        host = node.get('host') or None
        if host:
            host = _host(host)
            if not _host_allowed(host, allowed_host):
                abort(400, description='O nó precisa usar o domínio autorizado ou um subdomínio dele.')
        event_name = str(node.get('event_name') or node.get('event') or '')[:80]
        if event_name and node_type in ('event','conversion') and not re.fullmatch(
                r'[A-Za-z][A-Za-z0-9_]{0,79}', event_name):
            abort(400, description='Configure um nome válido para cada evento personalizado.')
        position = {}
        for axis, default in (('x', 80 + (index % 3) * 220), ('y', 60 + (index // 3) * 130)):
            value = node.get(axis, default)
            if isinstance(value, bool):
                abort(400, description='A posição de um nó é inválida.')
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                abort(400, description='A posição de um nó é inválida.')
            if not math.isfinite(numeric) or not 0 <= numeric <= 10000:
                abort(400, description='Mantenha os nós dentro da área do editor.')
            position[axis] = round(numeric)
        item = {'id': node_id, 'type': node_type, 'title': title,
                'x': position['x'], 'y': position['y']}
        if config.get('schema_version') == 2:
            kind = node.get('kind') or LEGACY_KINDS.get(node_type)
            if not isinstance(kind, str) or len(kind) > 80:
                abort(400, description='Tipo visual de nó inválido.')
            if 'data' in node and not isinstance(node['data'], dict):
                abort(400, description='Dados de nó inválidos.')
            item['kind'] = kind
            item['data'] = node.get('data') or {}
        if isinstance(path, str) and path:
            item['path'] = path
        if host:
            item['host'] = host
        if event_name:
            item['event_name'] = event_name
        if 'kind' not in item and isinstance(node.get('kind'), str) and re.fullmatch(r'[a-z_]+\.[a-z0-9_]+', node['kind']):
            item['kind'] = node['kind'][:80]
        for field in ('source','event','discoveryPageId','stepId','pageGroup','suggestedRole','groupId','stage','role','origin','role_source','pageType','pageTypeStatus'):
            if isinstance(node.get(field), str):
                item[field] = node[field][:120]
        # Persist the complete authored document, including visual and future
        # rule metadata. These fields do not imply an automation executor.
        for field in ('description','thumbnail_asset_id','platform_id'):
            if field in node:
                if not isinstance(node[field], str) or len(node[field]) > 2000:
                    abort(400, description='Propriedade de nó inválida.')
                item[field] = node[field]
        for field in ('appearance','condition','duration','segment_ref','growth','action'):
            if field in node:
                if not isinstance(node[field], dict):
                    abort(400, description='A configuração do nó precisa ser um objeto.')
                item[field] = node[field]
        for field in ('width','height'):
            if field in node:
                value = node[field]
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 40 <= value <= 2000:
                    abort(400, description='Dimensão de nó inválida.')
                item[field] = round(value)
        for field in ('stepId','campaign_id'):
            value = node.get(field)
            if field == 'campaign_id' and field in node and value is None:
                item[field] = None
            if value is not None:
                if isinstance(value, bool):
                    abort(400, description='Referência de nó inválida.')
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    abort(400, description='Referência de nó inválida.')
                if value < 1:
                    abort(400, description='Referência de nó inválida.')
                item[field] = value
        if isinstance(node.get('fields'), list):
            item['fields'] = [{'name':str(field.get('name') or '')[:80],
                'label':str(field.get('label') or '')[:100],
                'required':bool(field.get('required'))}
                for field in node['fields'][:30] if isinstance(field, dict)]
        if node.get('stage') and node['stage'] not in ('source','entry','exploration','intent','conversion','support'):
            abort(400, description='Etapa do funil inválida.')
        if node.get('pageType') and node['pageType'] not in ('home','service','institutional','contact','case','content','other'):
            abort(400, description='Tipo de página inválido.')
        if node.get('pageTypeStatus') and node['pageTypeStatus'] not in ('confirmed','unresolved'):
            abort(400, description='Estado do Tipo de página inválido.')
        for flag in ('locked','manuallyEdited'):
            if isinstance(node.get(flag), bool):item[flag]=node[flag]
        if isinstance(node.get('evidence'), str):item['evidence']=node['evidence'][:2000]
        if isinstance(node.get('isEntry'), bool):
            item['isEntry'] = node['isEntry']
        normalized.append(normalize_stage_position(item))
    normalized_edges = []
    edge_ids = set()
    for edge in edges:
        if not isinstance(edge, dict):
            abort(400, description='O fluxo contém uma conexão inválida.')
        source, target = edge.get('from'), edge.get('to')
        if not isinstance(source, str) or not isinstance(target, str) or source not in ids or target not in ids or source == target:
            abort(400, description='Conecte nós existentes e diferentes.')
        edge_id = str(edge.get('id') or uuid.uuid4())
        if not edge_id or len(edge_id) > 80 or edge_id in edge_ids:
            abort(400, description='Cada conexão precisa de um identificador único.')
        edge_ids.add(edge_id)
        normalized_edge = {'id':edge_id, 'from':source,'to':target,
                           'label':' '.join(str(edge.get('label') or 'Próximo').split())[:80]}
        if config.get('schema_version') == 2:
            if edge.get('variant', 'direct') not in ('direct', 'planned'):
                abort(400, description='Tipo visual de conexão inválido.')
            normalized_edge['variant'] = edge.get('variant', 'direct')
        for field in ('from_port','to_port','kind','condition_ref','origin','evidence'):
            if field in edge:
                if not isinstance(edge[field], str) or len(edge[field]) > 120:
                    abort(400, description='Propriedade de conexão inválida.')
                normalized_edge[field] = edge[field]
        normalized_edges.append(normalized_edge)
    identities = {}
    for node in normalized:
        if node['type'] not in measured_types:
            continue
        identity = (node['type'],node.get('host') or allowed_host,node.get('path'),node.get('event_name'))
        if identity in identities and node['type'] != 'page':
            failure=BadRequest('Dois nós observam o mesmo evento na mesma página. Use um nó com várias conexões ou eventos com nomes diferentes.')
            failure.flow_code='duplicate_event';failure.node_ids=[identities[identity],node['id']]
            raise failure
        identities[identity]=node['id']
    groups=config.get('groups',[])
    if not isinstance(groups,list) or len(groups)>50:
        abort(400,description='O fluxo aceita até 50 grupos.')
    clean_groups=[];group_ids=set();members=set()
    for group in groups:
        if not isinstance(group,dict):abort(400,description='Grupo inválido.')
        group_id=group.get('id');bounds=group.get('bounds');member_ids=group.get('memberIds')
        if not isinstance(group_id,str) or not group_id or len(group_id)>80 or group_id in group_ids or group_id in ids:
            abort(400,description='Identificador de grupo inválido.')
        if not isinstance(member_ids,list) or not member_ids or any(not isinstance(n,str) or n not in ids or n in members for n in member_ids) or len(set(member_ids))!=len(member_ids):
            abort(400,description='Cada nó pode pertencer a um único grupo válido.')
        if not isinstance(bounds,dict) or any(isinstance(bounds.get(k),bool) or not isinstance(bounds.get(k),(float,int)) or not math.isfinite(bounds[k]) or not 0<=bounds[k]<=10000 for k in ('x','y','width','height')) or bounds['width']<100 or bounds['height']<100:
            abort(400,description='Dimensões de grupo inválidas.')
        group_ids.add(group_id);members.update(member_ids)
        clean_groups.append({'id':group_id,'name':str(group.get('name') or 'Grupo')[:60],
                             'bounds':{k:round(bounds[k]) for k in ('x','y','width','height')},'memberIds':member_ids})
    membership={member:g['id'] for g in clean_groups for member in g['memberIds']}
    for node in normalized:
        if node.get('groupId') and membership.get(node['id'])!=node['groupId']:
            abort(400,description='A nó referencia um grupo incompatível.')
        if node['id'] in membership:node['groupId']=membership[node['id']]
    result = {**config, 'nodes':normalized, 'edges':normalized_edges, 'groups':clean_groups}
    if result.get('site_kind') not in (None, 'landing', 'institucional', 'multipagina', 'ecommerce'):
        abort(400, description='Tipo de site inválido.')
    if config.get('schema_version') == 2:
        result = migrate_v1_to_v2(result)
    try:
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, RecursionError):
        abort(400, description='A configuração contém valores inválidos.')
    if len(encoded) > 256_000:
        abort(413, description='A configuração do fluxo excede o limite de armazenamento.')
    return result, any(node['type'] in measured_types for node in normalized)


def _validate_flow_references(config, selected):
    for node in config.get('nodes', []):
        for field, table in (('campaign_id','cadu_reports_campaigns'), ('stepId','cadu_reports_flow_steps')):
            if node.get(field) is not None and not _rows(
                    f'SELECT id FROM {table} WHERE id=%s AND client_id=%s',
                    (node[field],selected['client_id'])):
                abort(400, description='O nó referencia um item indisponível neste cliente.')


def _client_tag_urls(client_id):
    client_id = int(client_id)
    base = str(current_app.config.get('CONNECT_URL') or request.url_root).rstrip('/')
    return {
        'flow': f'{base}/v2/flow.js?client={client_id}',
        'supertag': f'{base}/v1/supertag.js',
    }


def _flow_associations(payload, selected, current=None):
    customer_id = (_customer_id(selected, payload.get('customer_id'))
                   if current is None or 'customer_id' in payload else current.get('customer_id'))
    campaign_id = (_optional_positive_id(payload.get('campaign_id'), 'Campanha')
                   if current is None or 'campaign_id' in payload else current.get('campaign_id'))
    if campaign_id and (current is None or 'customer_id' in payload or 'campaign_id' in payload):
        campaign = _rows('''SELECT customer_id FROM cadu_reports_campaigns
            WHERE id=%s AND client_id=%s''', (campaign_id, selected['client_id']))
        if not campaign:
            abort(404, description='Campanha indisponível neste cliente.')
        campaign_customer = campaign[0]['customer_id']
        if customer_id and campaign_customer and customer_id != campaign_customer:
            abort(400, description='A campanha pertence a outro cliente/anunciante.')
        if not customer_id:
            customer_id = campaign_customer
    return customer_id, campaign_id


def _flow_row(flow_id, selected):
    found = _rows('''SELECT f.id,f.site_id,f.flow_code,f.name,f.status,f.customer_id,f.campaign_id,f.draft_config AS config,f.config AS active_config,
            f.draft_revision,f.published_revision,f.created_at,f.updated_at,
            f.published_at,t.id AS tag_id,t.label AS tag_label,t.allowed_host,t.public_key,t.revoked_at
        FROM cadu_reports_flow_registry f
        JOIN cadu_reports_site_tags t ON t.id=f.tag_id
        WHERE f.id=%s AND f.client_id=%s''',
        (flow_id, selected['client_id']))
    if not found:
        abort(404, description='Fluxo não encontrado neste cliente.')
    if _rows('SELECT id FROM cadu_reports_flow_registry WHERE tag_id=%s AND id<>%s LIMIT 1',
             (found[0]['tag_id'], found[0]['id'])):
        abort(409, description='Aplique a migração de isolamento das tags para acessar este fluxo com métricas confiáveis.')
    return found[0]


def _tag_for_client(tag_id, selected):
    found = _rows('''SELECT id,label,allowed_host,public_key,created_at,revoked_at,tag_kind
        FROM cadu_reports_site_tags WHERE id=%s AND client_id=%s''',
        (_uuid(tag_id, 'Tag'), selected['client_id']))
    if not found:
        abort(404)
    return found[0]


def _campaign_match(tag, attribution, matched_step):
    """Use only unique, explicit IDs or names; a shared landing page is not evidence."""
    params = (tag['client_id'],)
    if attribution.get('utm_id'):
        candidates = _rows('''SELECT id FROM cadu_reports_campaigns
            WHERE client_id=%s AND external_id=%s LIMIT 2''',
            (*params, attribution['utm_id']))
        if len(candidates) == 1:
            return candidates[0]['id'], 'utm_id'
    if attribution.get('utm_campaign'):
        candidates = _rows('''SELECT id FROM cadu_reports_campaigns
            WHERE client_id=%s AND lower(name)=lower(%s) LIMIT 2''',
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

    @bp.get('/api/v2/reports/flow/events')
    @login_required_api
    def reports_flow_events():
        selected = _selection()
        if not _rows("SELECT to_regclass('public.cadu_reports_flow_events') IS NOT NULL AS ready")[0]['ready']:
            return jsonify(error='Eventos indisponíveis: aplique add_reports_operations_v1.sql.'), 503
        try:
            days = int(request.args.get('days', 30))
        except (TypeError, ValueError):
            abort(400, description='Período inválido.')
        if days not in (7, 30, 90):
            abort(400, description='Período inválido.')
        where = ['e.client_id=%s']
        params = [selected['client_id']]
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        if start_date or end_date:
            if not start_date or not end_date:
                abort(400, description='Informe as duas datas do intervalo.')
            try:
                parsed_start, parsed_end = date.fromisoformat(start_date), date.fromisoformat(end_date)
            except ValueError:
                abort(400, description='Intervalo de datas inválido.')
            if parsed_start > parsed_end or (parsed_end - parsed_start).days > 366:
                abort(400, description='Escolha um intervalo de até 367 dias.')
            where.extend(['e.occurred_at >= %s::date', "e.occurred_at < (%s::date + INTERVAL '1 day')"])
            params.extend([start_date, end_date])
        else:
            where.append("e.occurred_at > NOW() - (%s * INTERVAL '1 day')")
            params.append(days)
        for key, column in (('account_id', 'a.id'), ('campaign_id', 'e.campaign_id')):
            value = request.args.get(key, '').strip()
            if value:
                try:
                    number = int(value)
                except ValueError:
                    abort(400, description=f'{key} inválido.')
                if number < 1:
                    abort(400, description=f'{key} inválido.')
                where.append(f'{column}=%s')
                params.append(number)
        platform = request.args.get('platform', '').strip()
        if platform:
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', platform):
                abort(400, description='Plataforma inválida.')
            where.append('a.platform=%s')
            params.append(platform)
        has_event_name = _rows('''SELECT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='cadu_reports_flow_events'
              AND column_name='event_name') AS ready''')[0]['ready']
        event_name = "COALESCE(NULLIF(event_name,''),event_kind)" if has_event_name else 'event_kind'
        scoped = '''WITH selected_events AS (SELECT e.*,
            COALESCE(NULLIF(e.utm_source,''),NULLIF(e.referrer_host,''),'Website') AS source_label
            FROM cadu_reports_flow_events e
            LEFT JOIN cadu_reports_campaigns c ON c.id=e.campaign_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
            WHERE ''' + ' AND '.join(where) + ') '
        events = _rows(scoped + f'''SELECT event_kind,{event_name} AS event_name,page_path,
            source_label,MAX(occurred_at) AS last_occurred_at,COUNT(*)::bigint AS total,
            COUNT(*) FILTER (WHERE step_id IS NOT NULL)::bigint AS mapped,
            COUNT(*) OVER() AS group_count
            FROM selected_events GROUP BY event_kind,{event_name},page_path,source_label
            ORDER BY last_occurred_at DESC LIMIT 300''', tuple(params))
        summary = _rows(scoped + '''SELECT COUNT(*)::bigint AS total,
            COUNT(*) FILTER (WHERE event_kind='form_submit')::bigint AS form_submissions,
            COUNT(*) FILTER (WHERE event_kind='conversion')::bigint AS conversions,
            COUNT(*) FILTER (WHERE utm_source IS NOT NULL OR referrer_host IS NOT NULL)::bigint AS attributed
            FROM selected_events''', tuple(params))[0]
        return jsonify(events=events, event_summary=summary,
                       event_group_count=events[0]['group_count'] if events else 0)

    @bp.get('/api/v2/reports/flow')
    @login_required_api
    def reports_flow():
        selected = _selection()
        schema = _rows('''SELECT
            to_regclass('public.cadu_reports_flow_versions') IS NOT NULL AS versions_ready,
            EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
                AND table_name='cadu_reports_flow_registry' AND column_name='draft_config') AS draft_ready,
            EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
                AND table_name='cadu_reports_flow_registry' AND column_name='published_revision') AS published_ready,
            EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public'
                AND table_name='cadu_reports_flow_steps' AND column_name='flow_revision') AS steps_ready''')[0]
        if not all(schema.values()):
            return jsonify(error='Fluxos indisponíveis: aplique add_reports_flow_versions_v1.sql e '
                         'add_reports_flow_integrity_v1.sql antes de abrir esta área.'), 503
        params = (selected['client_id'],)
        requested_flow_id = request.args.get('flow_id', '').strip()
        selected_flow = _flow_row(requested_flow_id, selected) if requested_flow_id else None
        if selected_flow and request.args.get('revision'):
            try:
                revision = int(request.args['revision'])
            except ValueError:
                abort(400,description='Versão inválida.')
            snapshots = _rows("""SELECT config FROM cadu_reports_flow_versions
                WHERE flow_id=%s AND client_id=%s AND revision=%s""",
                (selected_flow['id'],*params,revision))
            if not snapshots:
                abort(404,description='Versão não encontrada neste cliente.')
            selected_flow['historical_view'] = revision != selected_flow['published_revision']
            selected_flow['active_config'] = snapshots[0]['config']
            selected_flow['published_revision'] = revision
        view = request.args.get('view', 'monitor')
        if view not in {'monitor', 'create', 'edit'}:
            abort(400, description='Área de fluxos inválida.')
        try:
            days = int(request.args.get('days', 30))
        except (ValueError, TypeError):
            abort(400, description='Período inválido.')
        if days not in (7, 30, 90):
            abort(400, description='Período inválido.')
        # The editor only needs definitions and tags. Do not touch the event,
        # version, or monitoring schemas until the user opens analytics; those
        # features may be deployed independently on older Reports databases.
        if view in {'create', 'edit'}:
            tags = _rows('''SELECT id,label,allowed_host,public_key,created_at,revoked_at,tag_kind
                FROM cadu_reports_site_tags WHERE client_id=%s
                    AND (%s::uuid IS NULL OR id=%s::uuid) ORDER BY created_at DESC''',
                (*params,selected_flow['tag_id'] if selected_flow else None,
                 selected_flow['tag_id'] if selected_flow else None))
            steps = _rows('''SELECT s.id,s.tag_id,s.name,s.path_prefix,s.page_host,s.step_kind,s.is_entry,s.campaign_id,s.position,
                s.is_active,s.archived_at,c.name AS campaign_name
                FROM cadu_reports_flow_steps s
                LEFT JOIN cadu_reports_campaigns c ON c.id=s.campaign_id
                WHERE s.client_id=%s
                    AND ((%s::uuid IS NULL AND s.is_active=TRUE) OR (s.tag_id=%s::uuid AND s.flow_revision=%s))
                ORDER BY s.is_entry DESC,s.position,s.id''',
                (*params,selected_flow['tag_id'] if selected_flow else None,
                 selected_flow['tag_id'] if selected_flow else None,
                 selected_flow['published_revision'] if selected_flow else None))
            flows = _rows('''SELECT f.id,f.site_id,f.flow_code,f.name,f.status,f.customer_id,f.campaign_id,f.draft_config AS config,f.draft_revision,f.published_revision,f.tag_id,
                    t.label AS tag_label,t.allowed_host,t.public_key,t.revoked_at,f.created_at,f.updated_at,f.published_at,
                    (SELECT STRING_AGG(DISTINCT c.name, ' · ' ORDER BY c.name)
                        FROM cadu_reports_flow_steps s
                        JOIN cadu_reports_campaigns c ON c.id=s.campaign_id
                            AND c.client_id=s.client_id
                        WHERE s.tag_id=f.tag_id AND s.client_id=f.client_id AND s.is_active=TRUE) AS campaign_names
                FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
                WHERE f.client_id=%s ORDER BY f.created_at DESC''', params)
            supertag_sites = _rows('''SELECT id,public_id,label,allowed_host,enabled,revoked_at
                FROM cadu_reports_supertag_sites WHERE client_id=%s
                    AND enabled=TRUE AND revoked_at IS NULL ORDER BY created_at DESC''', params)
            from .reports_supertag import _supertag_snippet
            for site in supertag_sites:
                site['snippet'] = _supertag_snippet(site)
            return jsonify(tags=tags,steps=steps,flows=flows,events=[],event_group_count=0,
                event_summary={},tag_urls=_client_tag_urls(selected['client_id'],),activity=[],
                online=0,conversions=0,site_pages=[],page_transitions=[],confirmed=[],period_days=days,
                canvas_nodes=[],canvas_edges=[],monitor_checks=[],supertag_sites=supertag_sites,
                performance_mode='configuration')

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
                WHERE tag_id=%s AND client_id=%s AND campaign_id IS NOT NULL)'''
            scope_params.append(selected_flow['tag_id'])
            conversion_params.extend((selected_flow['tag_id'],selected['client_id']))
        if selected_flow:
            event_filter += ' AND e.flow_revision=%s'
            scope_params.append(selected_flow['published_revision'])
        scoped_events = '''WITH selected_events AS (
            SELECT e.* FROM cadu_reports_flow_events e
            LEFT JOIN cadu_reports_campaigns c ON c.id=e.campaign_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
            WHERE e.client_id=%s
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
            WHERE e.client_id=%s
            ''' + event_period_filter + event_filter + event_date_filter + ') '
        scoped_events = event_scoped_events
        scope_params = event_scope_params
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
            FROM cadu_reports_site_tags WHERE client_id=%s
                AND (%s::uuid IS NULL OR id=%s::uuid) ORDER BY created_at DESC''',
            (*params,selected_flow['tag_id'] if selected_flow else None,
             selected_flow['tag_id'] if selected_flow else None))
        steps = _rows('''SELECT s.id,s.tag_id,s.name,s.path_prefix,s.page_host,s.step_kind,s.is_entry,s.campaign_id,s.position,
            s.is_active,s.archived_at,
            c.name AS campaign_name FROM cadu_reports_flow_steps s
            LEFT JOIN cadu_reports_campaigns c ON c.id=s.campaign_id
            WHERE s.client_id=%s
                AND ((%s::uuid IS NULL AND s.is_active=TRUE) OR (s.tag_id=%s::uuid AND s.flow_revision=%s))
            ORDER BY s.is_entry DESC,s.position,s.id''',
            (*params,selected_flow['tag_id'] if selected_flow else None,
             selected_flow['tag_id'] if selected_flow else None,
             selected_flow['published_revision'] if selected_flow else None))
        supertag_sites = _rows('''SELECT id,public_id,label,allowed_host,enabled,revoked_at
            FROM cadu_reports_supertag_sites WHERE client_id=%s
                AND enabled=TRUE AND revoked_at IS NULL ORDER BY created_at DESC''', params)
        from .reports_supertag import _supertag_snippet
        for site in supertag_sites:
            site['snippet'] = _supertag_snippet(site)
        flows = _rows('''SELECT f.id,f.site_id,f.flow_code,f.name,f.status,f.customer_id,f.campaign_id,f.draft_config AS config,f.draft_revision,f.published_revision,f.tag_id,t.label AS tag_label,
                t.allowed_host,t.public_key,t.revoked_at,f.created_at,f.updated_at,f.published_at,
                f.monitor_enabled,f.monitor_interval_minutes,f.monitor_status,f.monitor_checked_at,
                (SELECT STRING_AGG(DISTINCT c.name, ' · ' ORDER BY c.name)
                    FROM cadu_reports_flow_steps s
                    JOIN cadu_reports_campaigns c ON c.id=s.campaign_id
                        AND c.client_id=s.client_id
                    WHERE s.tag_id=f.tag_id AND s.client_id=f.client_id AND s.is_active=TRUE) AS campaign_names
            FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
            WHERE f.client_id=%s ORDER BY f.created_at DESC''', params)
        flows = [{**item, 'config': migrate_v1_to_v2(item['config'])} for item in flows]
        activity = _rows(scoped_events + '''SELECT e.tag_id,e.page_path,
            COUNT(*) FILTER (WHERE e.event_kind IN ('page_view','conversion','error_view')) AS views,
            COUNT(*) FILTER (WHERE e.event_kind='form_submit') AS form_submissions,
            COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click')) AS clicks,
            COUNT(DISTINCT e.visitor_id) FILTER (WHERE e.event_kind IN ('page_view','conversion','error_view')) AS visitors,
            COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind IN ('page_view','conversion','error_view','heartbeat','form_submit','click','whatsapp_click','page_leave')
                AND e.occurred_at > NOW() - INTERVAL '90 seconds') AS online,
            COUNT(*) FILTER (WHERE e.event_kind='conversion') AS conversions
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
            COUNT(*) FILTER (WHERE event_kind='conversion') AS conversions
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
            FROM cadu_reports_flow_steps WHERE client_id=%s AND id=ANY(%s::bigint[])
        )
        SELECT o.id AS step_id,COUNT(DISTINCT f.session_id) AS reached,
            COUNT(DISTINCT f.session_id) FILTER (
                WHERE o.previous_id IS NULL OR p.first_at <= f.first_at) AS progressed
        FROM ordered o LEFT JOIN first_step f ON f.step_id=o.id
        LEFT JOIN first_step p ON p.step_id=o.previous_id AND p.session_id=f.session_id
        GROUP BY o.id''', tuple(scope_params) + (*params,[step['id'] for step in steps]))
        progress_by_step = {row['step_id']: row for row in progression}
        for step in steps:
            progress = progress_by_step.get(step['id'], {})
            step['reached'] = progress.get('reached', 0)
            step['progressed'] = progress.get('progressed', 0)
        canvas_nodes = []
        if selected_flow:
            selected_flow['config'] = selected_flow.get('active_config') or {}
        if selected_flow and isinstance(selected_flow.get('config'), dict):
            configured_nodes = [node for node in selected_flow['config'].get('nodes', [])
                if isinstance(node, dict) and node.get('type') in ('page','form','event','conversion','whatsapp','error')
                and isinstance(node.get('path'), str) and node['path'].startswith('/')]
            configured_nodes = configured_nodes[:200]
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
                        AND e.page_path=n.path
                    WHERE e.flow_revision=%s AND ((n.node_type='page' AND e.event_kind IN ('page_view','conversion','error_view'))
                       OR (n.node_type='conversion' AND e.event_kind='conversion'
                           AND (n.event_name='' OR n.event_name={canvas_event_name_expr}))
                       OR (n.node_type='error' AND e.event_kind='error_view')
                       OR (n.node_type='form' AND e.event_kind='form_submit')
                       OR (n.node_type='whatsapp' AND e.event_kind='whatsapp_click')
                       OR (n.node_type='event' AND e.event_kind='custom_event'
                           AND (n.event_name='' OR n.event_name={canvas_event_name_expr})))
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
                        AND target.session_id=source.session_id AND target.occurred_at>source.occurred_at
                    GROUP BY edge.target_id
                )
                SELECT n.node_id AS id,COALESCE(r.reached,0) AS reached,
                    COALESCE(p.progressed,0) AS progressed
                FROM configured_nodes n LEFT JOIN reached r USING(node_id)
                LEFT JOIN progressed p USING(node_id)''',
                    tuple(event_scope_params) + (node_json, selected_flow['published_revision'], edge_json))
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
            WHERE x.client_id=%s
                AND ''' + confirmed_time_filter + conversion_filter +
            ' GROUP BY x.conversion_kind ORDER BY x.conversion_kind', tuple(confirmed_params))
        monitor_checks = []
        if selected_flow:
            monitor_checks = _rows('''SELECT id,status,checked_at,duration_ms,pages
                FROM cadu_reports_flow_monitor_checks WHERE flow_id=%s
                AND client_id=%s ORDER BY checked_at DESC LIMIT 20''',
                (selected_flow['id'], *params))
        # Live collection health is deliberately independent of historical report filters.
        tracking_health = {'status': 'waiting', 'reason': 'Aguardando publicação', 'window_seconds': 900}
        if selected_flow:
            signals = _rows("""SELECT page_host,page_path,MAX(occurred_at) AS last_received_at,
                    BOOL_OR(occurred_at >= NOW() - INTERVAL '15 minutes') AS recent
                FROM cadu_reports_flow_events
                WHERE client_id=%s AND tag_id=%s
                    AND occurred_at >= NOW() - INTERVAL '24 hours' AND flow_revision=%s
                GROUP BY page_host,page_path""", (*params,selected_flow['tag_id'],selected_flow['published_revision']))
            healthy = any(signal['recent'] for signal in signals)
            active = selected_flow['status'] == 'published' and not selected_flow.get('revoked_at')
            tracking_health = {'status': 'healthy' if active and healthy else 'warning',
                'reason': 'Sinais recebidos nos últimos 15 min' if active and healthy else
                    'Fluxo não publicado ou tag revogada' if not active else
                    'Sem sinais há 15 min; pode não haver visitantes',
                'window_seconds': 900,
                'last_received_at': max((row['last_received_at'] for row in signals), default=None)}
            measured_ids = {node['id'] for node in canvas_nodes}
            canvas_nodes.extend(dict(node, reached=None, progressed=None)
                for node in (selected_flow.get('config') or {}).get('nodes', [])
                if node.get('id') not in measured_ids)
            for node in canvas_nodes:
                if not node.get('path'):
                    node['tracking_status'] = tracking_health['status']
                    node['tracking_reason'] = tracking_health['reason'] + ' · estado geral da coleta'
                    continue
                recent = any(row['recent'] and
                    (not node.get('host') or row['page_host'] == node['host']) and
                    row['page_path'] == node['path']
                    for row in signals)
                latest_check = monitor_checks[0] if monitor_checks else None
                checked_at = latest_check.get('checked_at') if latest_check else None
                fresh_check = bool(not selected_flow.get('historical_view') and checked_at and (datetime.now(timezone.utc) - checked_at).total_seconds() <= 1800
                                   and (not selected_flow.get('published_at') or checked_at >= selected_flow['published_at']))
                checks = (latest_check.get('pages') or []) if fresh_check else []
                broken = any(page.get('status') in ('offline','degraded') and
                    page.get('path') == node.get('path') and
                    page.get('host') == (node.get('host') or selected_flow['allowed_host'])
                    for page in checks)
                node['tracking_status'] = 'warning' if broken or not active else 'healthy' if recent else 'quiet'
                node['tracking_reason'] = 'Falha na última verificação da página' if broken else                     'Sinais recentes da tag' if active and recent else                     tracking_health['reason'] if not active else 'Sem sinais nesta página há 15 min; pode não haver visitas'
        canvas_edges = (selected_flow.get('config') or {}).get('edges', []) if selected_flow else []
        # Live presence has its own time window, independent of historical filters.
        live = {'status': 'unavailable', 'active_sessions': None, 'node_presence': {},
                'transitions': {}, 'sessions_on_conversion_pages': None, 'locations': []}
        generated_at = datetime.now(timezone.utc)
        if selected_flow and not selected_flow.get('historical_view') and selected_flow['status'] == 'published':
            from .reports_flow_live import build_live_snapshot
            recent = _rows(f"""SELECT id,session_id,page_host,page_path,event_kind,
                    {"event_name" if has_event_name else "NULL::text"} AS event_name,occurred_at
                FROM cadu_reports_flow_events
                WHERE client_id=%s AND tag_id=%s AND flow_revision=%s
                  AND occurred_at>NOW()-INTERVAL '15 minutes' AND occurred_at<=NOW()
                ORDER BY occurred_at DESC,id DESC LIMIT 5001""",
                (*params,selected_flow['tag_id'],selected_flow['published_revision']))
            if len(recent) <= 5000:
                live = {**build_live_snapshot(recent, canvas_nodes, canvas_edges, generated_at), 'status': 'ready'}
            else:
                live['status'] = 'capacity_exceeded'
        live.update(schema_version=1, generated_at=generated_at.isoformat(), poll_interval_ms=15000,
                    flow_id=str(selected_flow['id']) if selected_flow else None,
                    revision=selected_flow['published_revision'] if selected_flow else None,
                    scope='current_publication_all_sources')
        for node in canvas_nodes:
            node['active_sessions_here'] = live['node_presence'].get(node['id']) if live['status']=='ready' else None
        for row in activity:
            row['online'] = (sum(item['active_sessions'] for item in live['locations']
                                if item['path'] == row['page_path']) if live['status']=='ready' else None)
        canvas_edges = [{**edge, 'last_transition_id':live['transitions'].get(edge.get('id'))}
                        for edge in canvas_edges]
        return jsonify(tags=tags, steps=steps, flows=flows, events=event_inventory,
                       event_group_count=event_inventory[0]['group_count'] if event_inventory else 0,
                       event_summary=event_summary,
                       tag_urls=_client_tag_urls(selected['client_id'],), activity=activity,
                       online=live['active_sessions'], conversions=totals['conversions'], live=live,
                       site_pages=site_pages,page_transitions=page_transitions,
                       confirmed=confirmed, period_days=days,
                       supertag_sites=supertag_sites,
                       canvas_nodes=canvas_nodes if selected_flow else [],
                       canvas_edges=canvas_edges,
                       monitor_checks=monitor_checks,tracking_health=tracking_health,
                       metrics_revision=selected_flow['published_revision'] if selected_flow else None)

    @bp.patch('/api/v2/reports/flow/flows/<flow_id>/monitor')
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
            WHERE id=%s AND client_id=%s
            RETURNING id,monitor_enabled,monitor_interval_minutes,monitor_status,monitor_checked_at''',
            (enabled, interval, enabled, enabled, flow['id'], selected['client_id']))
        get_db().commit()
        return jsonify(flow=changed[0])

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/monitor/check')
    @login_required_api
    def reports_flow_check_monitor(flow_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        if flow['status'] != 'published':
            abort(409, description='Publique o fluxo antes de verificar suas páginas.')
        from .reports_flow_monitor import check_flow
        result = check_flow(flow['id'], selected['client_id'])
        if result is None:
            abort(409, description='A tag do fluxo foi revogada ou não está disponível.')
        return jsonify(check=result)

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/discover')
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
                WHERE id=%s AND client_id=%s AND tag_id=%s FOR UPDATE''',
                (run_id,selected['client_id'],flow['tag_id']))
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
                WHERE run_id=%s AND client_id=%s''',
                (run_id,selected['client_id']))
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
                (id,client_id,tag_id,root_url,status,page_count,created_by)
                VALUES (%s,%s,%s,%s,'partial',0,%s) RETURNING id''',
                (run_id,selected['client_id'],flow['tag_id'],
                 root_url,session['user_id']))
        budget = _discovery_budget(active_run['page_count'] if active_run else 0, payload.get('max_pages'))
        if budget <= 0:
            abort(409, description=f'Limite de {MAX_DISCOVERY_TOTAL_PAGES} páginas por mapeamento atingido. Remova páginas que não importam ou inicie um novo mapeamento.')
        pages, pending_urls, sitemap_truncated = _discover_site(
            root_url,flow['allowed_host'],seed_urls=seed_urls,excluded_pages=excluded_pages,max_pages=budget)
        pending_truncated = bool(sitemap_truncated or (active_run and active_run['pending_truncated']))
        mapped_steps = _rows('''SELECT id,page_host,path_prefix,step_kind,is_entry
            FROM cadu_reports_flow_steps WHERE tag_id=%s AND client_id=%s
                AND is_active=TRUE AND step_kind IN ('page','form','conversion','error')''',
            (flow['tag_id'],selected['client_id']))
        steps_by_page, wildcard_steps = {}, {}
        for step in mapped_steps:
            if step['page_host']:
                steps_by_page[(step['page_host'],step['path_prefix'])] = step
            else:
                wildcard_steps.setdefault(step['path_prefix'], []).append(step)
        from .reports_page_paths import normalize_page_path
        previous_keys={ (item['page_host'],item['path_prefix']):item['translation_key'] for item in _rows('''
            SELECT DISTINCT ON (page_host,path_prefix) page_host,path_prefix,translation_key
            FROM cadu_reports_flow_discovered_pages
            WHERE client_id=%s AND tag_id=%s AND translation_key IS NOT NULL
            ORDER BY page_host,path_prefix,created_at DESC''',
            (selected['client_id'],flow['tag_id'])) }
        stored = []
        for page in pages:
            normalized=normalize_page_path(page['path'])
            evidence = {'signals': page['evidence'], 'h1': page.get('h1',''), 'structure_signature': page.get('structure_signature'), 'canonical':page.get('canonical'),
                        'hreflang': page.get('hreflang', {}),
                        'integrations': page.get('integrations', []),
                        'links': list(dict.fromkeys(url for link in page.get('links', [])
                            if (url := _canonical_page_url(link, page['url'], flow['allowed_host']))))}
            prior_step = steps_by_page.get((page['host'],page['path']))
            if prior_step is None:
                wildcard_matches = wildcard_steps.get(page['path'], [])
                if len(wildcard_matches) == 1:
                    prior_step = wildcard_matches[0]
            selected_kind = prior_step['step_kind'] if prior_step else None
            selected_as_entry = bool(prior_step and prior_step['is_entry'])
            row = _rows('''INSERT INTO cadu_reports_flow_discovered_pages
                (id,run_id,client_id,tag_id,url,page_host,path_prefix,locale,normalized_path,translation_key,page_status,title,suggested_role,confidence,evidence,form_count,form_fields,selected_kind,selected_as_entry,step_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (run_id,page_host,path_prefix) DO UPDATE SET
                    url=EXCLUDED.url,locale=EXCLUDED.locale,normalized_path=EXCLUDED.normalized_path,page_status=EXCLUDED.page_status,
                    translation_key=COALESCE(cadu_reports_flow_discovered_pages.translation_key,EXCLUDED.translation_key),
                    title=EXCLUDED.title,suggested_role=EXCLUDED.suggested_role,
                    confidence=EXCLUDED.confidence,evidence=EXCLUDED.evidence,
                    form_count=EXCLUDED.form_count,form_fields=EXCLUDED.form_fields
                RETURNING id,url,page_host,path_prefix,title,suggested_role,confidence,evidence,
                    form_count,form_fields,selected_kind,selected_as_entry,step_id''',
                (str(uuid.uuid4()),run_id,selected['client_id'],
                 flow['tag_id'],page['url'],page['host'],page['path'],normalized['locale'],normalized['path'],
                 previous_keys.get((page['host'],page['path'])),'noindex' if page.get('noindex') else 'valida',page['title'],page['role'],
                 page['confidence'],json.dumps(evidence),page['forms'],json.dumps(page['form_fields']),
                 selected_kind,selected_as_entry,prior_step['id'] if prior_step else None))[0]
            stored.append(row)
        run_counts = _rows('''SELECT COUNT(*)::integer AS page_count FROM cadu_reports_flow_discovered_pages
            WHERE run_id=%s AND client_id=%s''',
            (run_id,selected['client_id']))[0]
        cap_reached = run_counts['page_count'] >= MAX_DISCOVERY_TOTAL_PAGES
        status='partial' if (pending_urls or pending_truncated) and not cap_reached else 'completed' if run_counts['page_count'] else 'failed'
        _rows('''UPDATE cadu_reports_flow_discovery_runs SET status=%s,page_count=%s,
                pending_urls=%s::jsonb,pending_truncated=%s
            WHERE id=%s AND client_id=%s RETURNING id''',
            (status,run_counts['page_count'],json.dumps(pending_urls),pending_truncated,
             run_id,selected['client_id']))
        updated, omitted, suggestions = None, 0, []
        if payload.get('assemble') is True:
            revision = expected_revision(payload)
            locked = lock_flow(flow_id, selected, revision)
            all_pages = _rows('''SELECT * FROM cadu_reports_flow_discovered_pages
                WHERE run_id=%s AND client_id=%s
                ORDER BY page_host,path_prefix''',
                (run_id,selected['client_id']))
            primary, groups = _discovery_flow_groups(all_pages)
            suggestions = [{'id': group['id'], 'name': group['name'], 'kind': group['kind'],
                            'page_count': len(group['pages'])} for group in groups]
            config, omitted = _assemble_discovered_flow(locked['draft_config'] or {}, primary, flow['allowed_host'], max_pages=MAX_FLOW_PAGES)
            config, _ = _normalize_flow_config(config, flow['allowed_host'])
            updated = save_draft(flow_id, selected, revision, locked['name'], config)
        get_db().commit()
        return jsonify(flow=updated, suggestions=suggestions, omitted_pages=omitted, run={'id':run_id,'root_url':root_url,'status':status,
                            'page_count':run_counts['page_count'],'pending_count':len(pending_urls),
                            'pending_truncated':pending_truncated},
                       limit={'cap':MAX_DISCOVERY_TOTAL_PAGES,'reached':cap_reached,'more_available':bool((pending_urls or pending_truncated) and cap_reached)},
                       pages=stored)

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/discovery-flows')
    @login_required_api
    def reports_flow_create_discovered_flows(flow_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict): abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        lock_flow(flow_id, selected, expected_revision(payload))
        run_id = _uuid(payload.get('run_id'), 'Varredura')
        requested = payload.get('groups')
        if not isinstance(requested, list) or not requested or any(not isinstance(key, str) for key in requested):
            abort(400, description='Selecione os fluxos que deseja criar.')
        pages = _rows("""SELECT * FROM cadu_reports_flow_discovered_pages
            WHERE run_id=%s AND tag_id=%s AND client_id=%s
            ORDER BY page_host,path_prefix""", (run_id, flow['tag_id'], selected['client_id']))
        _, groups = _discovery_flow_groups(pages)
        available = {group['id']: group for group in groups}
        if any(key not in available for key in requested):
            abort(400, description='O grupo não pertence a este mapeamento.')
        created = []
        for key in dict.fromkeys(requested):
            origin = f"{flow_id}:{key}"
            existing = _rows("""SELECT id,name FROM cadu_reports_flow_registry
                WHERE client_id=%s AND draft_config->>'discovery_origin'=%s""",
                (selected['client_id'], origin))
            if existing:
                created.extend(existing)
                continue
            group = available[key]
            config, omitted = _assemble_discovered_flow({'discovery_origin': origin}, group['pages'], flow['allowed_host'])
            if omitted:
                abort(400, description='Este grupo excede 200 páginas. Divida-o antes de criar o fluxo.')
            config, _ = _normalize_flow_config(config, flow['allowed_host'])
            private_tag = _rows('''INSERT INTO cadu_reports_site_tags
                (id,client_id,label,allowed_host,public_key,created_by,tag_kind)
                VALUES (%s,%s,%s,%s,%s,%s,'flow') RETURNING id''',
                (str(uuid.uuid4()), selected['client_id'], group['name'][:120],
                 flow['allowed_host'], secrets.token_urlsafe(24), session['user_id']))[0]
            created.extend(_rows("""INSERT INTO cadu_reports_flow_registry
                (id,client_id,flow_code,tag_id,name,draft_config,created_by,site_id)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s) RETURNING id,name""",
                (str(uuid.uuid4()), selected['client_id'], _new_flow_code(),
                 private_tag['id'], group['name'][:120], json.dumps(config), session['user_id'],flow['site_id'])))
        get_db().commit()
        return jsonify(flows=created), 201

    @bp.get('/api/v2/reports/flow/flows/<flow_id>/discoveries')
    @login_required_api
    def reports_flow_discoveries(flow_id):
        selected = _selection()
        flow = _flow_row(flow_id, selected)
        runs = _rows('''SELECT id,root_url,status,page_count,created_at,
                jsonb_array_length(pending_urls) AS pending_count,pending_truncated
            FROM cadu_reports_flow_discovery_runs WHERE client_id=%s AND tag_id=%s
            ORDER BY created_at DESC LIMIT 1''',
            (selected['client_id'],flow['tag_id']))
        pages = []
        if runs:
            pages = _rows('''SELECT p.id,p.url,p.page_host,p.path_prefix,p.locale,p.normalized_path,p.translation_key,p.page_status,
                p.title,p.suggested_role,p.confidence,p.evidence,
                p.form_count,p.form_fields,p.selected_kind,p.selected_as_entry,p.step_id,s.campaign_id
                FROM cadu_reports_flow_discovered_pages p
                LEFT JOIN cadu_reports_flow_steps s ON s.id=p.step_id AND s.client_id=p.client_id
                WHERE p.run_id=%s AND p.client_id=%s
                ORDER BY CASE suggested_role WHEN 'entry' THEN 0 WHEN 'form' THEN 1 WHEN 'conversion' THEN 2 ELSE 3 END,
                    p.page_host,p.path_prefix''', (runs[0]['id'],selected['client_id']))
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
        from .reports_flow_catalog import build_catalog, catalog_groups, catalog_summary
        catalog=build_catalog(pages,flow['allowed_host'],(flow.get('config') or {}).get('nodes',[]))
        return jsonify(catalog=catalog,groups=catalog_groups(catalog),limit={'cap':MAX_DISCOVERY_TOTAL_PAGES},summary=catalog_summary(pages,catalog),run=runs[0] if runs else None,pages=pages,
                       platform_integrations=list(integration_summary.values()),
                       integration_scan_pages=scanned_pages)

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/translations')
    @login_required_api
    def reports_flow_link_translation(flow_id):
        from .reports_page_paths import normalize_page_path
        payload=request.get_json(silent=True) or {}
        selected=_selection(payload)
        _write_guard(selected)
        flow=_flow_row(flow_id,selected)
        identifiers=[payload.get('page_id'),payload.get('translation_page_id')]
        if not all(isinstance(value,str) for value in identifiers) or identifiers[0]==identifiers[1]:
            abort(400,description='Selecione duas páginas diferentes.')
        pages=_rows('''SELECT id,path_prefix,locale,normalized_path,translation_key
            FROM cadu_reports_flow_discovered_pages
            WHERE id=ANY(%s::uuid[]) AND client_id=%s AND tag_id=%s
              AND run_id=(SELECT id FROM cadu_reports_flow_discovery_runs
                WHERE client_id=%s AND tag_id=%s ORDER BY created_at DESC LIMIT 1)
            FOR UPDATE''',(identifiers,selected['client_id'],flow['tag_id'],selected['client_id'],flow['tag_id']))
        if len(pages)!=2:abort(404,description='Página fora do inventário atual.')
        by_id={str(page['id']):page for page in pages}
        first,second=(by_id[identifier] for identifier in identifiers)
        source=normalize_page_path(first['path_prefix'])
        target=normalize_page_path(second['path_prefix'])
        if source['locale']==target['locale']:
            abort(400,description='Escolha páginas de idiomas diferentes.')
        key=(first if source['locale']=='pt' else second if target['locale']=='pt' else first)
        key_path=normalize_page_path(key['path_prefix'])['path']
        _rows('''UPDATE cadu_reports_flow_discovered_pages SET translation_key=%s
            WHERE id=ANY(%s::uuid[]) AND client_id=%s AND tag_id=%s''',
            (key_path,identifiers,selected['client_id'],flow['tag_id']))
        get_db().commit()
        return jsonify(translation_key=key_path,page_ids=identifiers)

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/discoveries/<page_id>/suggest')
    @login_required_api
    def reports_flow_suggest_page(flow_id, page_id):
        from .reports_flow_suggestions import suggest
        from ..services.typesafe_service import TypeSafeError
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        pages = _rows("""SELECT id,title,path_prefix,form_count,evidence
            FROM cadu_reports_flow_discovered_pages
            WHERE id=%s AND tag_id=%s AND client_id=%s""",
            (_uuid(page_id,'Página descoberta'),flow['tag_id'],
             selected['client_id']))
        if not pages:
            abort(404, description='Página não encontrada neste cliente.')
        try:
            suggestion = suggest(flow, pages[0], selected)
        except TypeSafeError:
            return jsonify(error='A sugestão está indisponível. Selecione a função do nó manualmente.'), 503
        return jsonify(suggestion)

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/discoveries/<page_id>/select')
    @login_required_api
    def reports_flow_select_discovered_page(flow_id,page_id):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload,dict): abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id,selected)
        revision = expected_revision(payload)
        locked = lock_flow(flow_id, selected, revision)
        pages = _rows("""SELECT * FROM cadu_reports_flow_discovered_pages
            WHERE id=%s AND tag_id=%s AND client_id=%s""",
            (_uuid(page_id, 'Página descoberta'), flow['tag_id'],
             selected['client_id']))
        if not pages:
            abort(404, description='Página não encontrada neste cliente.')
        page = pages[0]
        choice = payload.get('selection')
        if choice not in ('ignore','entry','intermediate','form','conversion','error'):
            abort(400, description='Escolha uma função válida para a página.')
        page_type_choice = payload.get('page_type_selection')
        if page_type_choice is not None and not payload.get('suggestion_id'):
            abort(400, description='A revisão do Tipo de página exige uma sugestão válida.')
        if payload.get('suggestion_id'):
            from .reports_flow_suggestions import validate_application
            accepted_suggestion = validate_application(payload['suggestion_id'],flow_id,page,selected,revision,choice,page_type_choice)
        else:
            accepted_suggestion = None
        campaign_id = payload.get('campaign_id') or None
        if campaign_id is not None:
            if isinstance(campaign_id, bool):
                abort(400, description='Campanha inválida.')
            try:
                campaign_id = int(campaign_id)
            except (TypeError, ValueError):
                abort(400, description='Campanha inválida.')
            if not _rows("""SELECT id FROM cadu_reports_campaigns
                    WHERE id=%s AND client_id=%s""",
                    (campaign_id,selected['client_id'])):
                abort(404, description='Campanha não encontrada neste cliente.')
        config = locked['draft_config'] or {}
        nodes = config.get('nodes', [])
        existing = next((node for node in nodes
                         if node.get('discoveryPageId') == str(page['id'])), None)
        if choice == 'ignore':
            nodes = [node for node in nodes if node is not existing]
        else:
            kind = {'entry':'page','intermediate':'page'}.get(choice, choice)
            node = existing or {'id':str(uuid.uuid4()), 'x':100+(len(nodes)%4)*230,
                                'y':80+(len(nodes)//4)*150}
            node.update({'type':kind,'title':str(payload.get('name') or page['title'] or page['path_prefix'])[:120],
                         'path':page['path_prefix'],'host':page['page_host'],
                         'isEntry':choice=='entry','discoveryPageId':str(page['id']),
                         'campaign_id':campaign_id})
            if existing is None:
                node.update(stage={'entry':'entry','intermediate':'exploration','form':'intent',
                                   'conversion':'conversion','error':'support'}[choice],
                            pageType='other',suggestedRole=choice)
                nodes.append(node)
            if accepted_suggestion:
                reviewed_type = page_type_choice if page_type_choice is not None else accepted_suggestion.get('page_type')
                if reviewed_type in ('home','service','institutional','contact','case','content','other'):
                    node['pageType'] = reviewed_type
                    node['pageTypeStatus'] = 'confirmed'
                else:
                    node['pageTypeStatus'] = 'unresolved'
        ids = {node['id'] for node in nodes}
        config.update(nodes=nodes, edges=[edge for edge in config.get('edges', [])
                      if edge['from'] in ids and edge['to'] in ids])
        config, _ = _normalize_flow_config(config, flow['allowed_host'])
        updated = save_draft(flow_id, selected, revision, locked['name'], config)
        get_db().commit()
        return jsonify(page_id=str(page['id']),selection=choice,flow=updated)

    @bp.post('/api/v2/reports/flow/tags')
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
            (id,client_id,label,allowed_host,public_key,created_by,tag_kind)
            VALUES (%s,%s,%s,%s,%s,%s,'supertag')
            RETURNING id,label,allowed_host,public_key,created_at,revoked_at,tag_kind''',
            (str(uuid.uuid4()), selected['client_id'], label,
             host, secrets.token_urlsafe(24), session['user_id']))
        get_db().commit()
        return jsonify(tag=created[0]), 201

    @bp.get('/api/v2/reports/flow/templates')
    @login_required_api
    def reports_flow_templates():
        _selection()
        return jsonify(templates=[
            {'id': 'blank', 'label': 'Começar em branco'},
            {'id': 'lead', 'label': 'Captação de leads'},
            {'id': 'commerce', 'label': 'Compra no site'},
            {'id': 'webinar', 'label': 'Inscrição em webinar'},
            {'id': 'whatsapp', 'label': 'Contato pelo WhatsApp'},
        ])

    @bp.post('/api/v2/reports/flow/flows')
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
        customer_id, campaign_id = _flow_associations(payload, selected)
        requested_host = _host(payload.get('allowed_host') or (tag or {}).get('allowed_host'))
        supertag_site, _ = ensure_supertag_site(selected, requested_host, name)
        # Each flow owns an internal tag, even when created from an existing site tag.
        label = ' '.join(str(payload.get('tag_label') or name).split())[:120]
        host = requested_host
        tag = _rows('''INSERT INTO cadu_reports_site_tags
            (id,client_id,label,allowed_host,public_key,created_by,tag_kind)
            VALUES (%s,%s,%s,%s,%s,%s,'flow')
            RETURNING id,label,allowed_host,public_key,created_at,revoked_at,tag_kind''',
            (str(uuid.uuid4()), selected['client_id'],
             label, host, secrets.token_urlsafe(24), session['user_id']))[0]
        config, _ = _normalize_flow_config(
            payload.get('config') if isinstance(payload.get('config'), dict) else {}, tag['allowed_host'])
        _validate_flow_references(config, selected)
        flow_id = str(uuid.uuid4())
        flow_code = _new_flow_code()
        created = _rows('''INSERT INTO cadu_reports_flow_registry
            (id,client_id,flow_code,tag_id,name,draft_config,created_by,site_id,customer_id,campaign_id)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
            RETURNING id,site_id,flow_code,name,status,customer_id,campaign_id,draft_config AS config,draft_revision,published_revision,tag_id,created_at,updated_at''',
            (flow_id, selected['client_id'], flow_code,
             tag['id'], name, json.dumps(config), session['user_id'],supertag_site['id'],customer_id,campaign_id))[0]
        get_db().commit()
        return jsonify(flow=created, tag=tag, supertag_site=supertag_site,
                       tag_urls=_client_tag_urls(selected['client_id'],)), 201

    @bp.patch('/api/v2/reports/flow/flows/<flow_id>/associations')
    @login_required_api
    def reports_flow_update_associations(flow_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) - {'client_id', 'customer_id', 'campaign_id'}:
            abort(400, description='Associação do fluxo inválida.')
        selected = _selection(payload)
        _write_guard(selected)
        current = _flow_row(flow_id, selected)
        customer_id, campaign_id = _flow_associations(payload, selected, current)
        updated = _rows('''UPDATE cadu_reports_flow_registry
            SET customer_id=%s,campaign_id=%s,updated_at=NOW()
            WHERE id=%s AND client_id=%s
            RETURNING id,customer_id,campaign_id,updated_at''',
            (customer_id,campaign_id,current['id'],selected['client_id']))[0]
        get_db().commit()
        return jsonify(flow=updated)

    @bp.patch('/api/v2/reports/flow/flows/<flow_id>')
    @login_required_api
    def reports_flow_update_flow(flow_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        current = _flow_row(flow_id, selected)
        customer_id, campaign_id = _flow_associations(payload, selected, current)
        name = ' '.join(str(payload.get('name', current['name']) or '').split())[:120]
        config = payload.get('config', current['config'])
        if not name or not isinstance(config, dict):
            abort(400, description='Nome e configuração do fluxo são obrigatórios.')
        config, _ = _normalize_flow_config(config, current['allowed_host'])
        _validate_flow_references(config, selected)
        updated = save_draft(current['id'], selected, expected_revision(payload), name, config)
        if (customer_id, campaign_id) != (current['customer_id'], current['campaign_id']):
            _rows('''UPDATE cadu_reports_flow_registry SET customer_id=%s,campaign_id=%s
                WHERE id=%s AND client_id=%s''', (customer_id,campaign_id,current['id'],selected['client_id']))
            updated['customer_id'], updated['campaign_id'] = customer_id, campaign_id
        get_db().commit()
        return jsonify(flow=updated)

    @bp.get('/api/v2/reports/flow/flows/<flow_id>/readiness')
    @login_required_api
    def reports_flow_readiness(flow_id):
        selected=_selection();flow=_flow_row(flow_id,selected)
        ready=bool(flow.get('site_id') and _rows("""SELECT EXISTS(SELECT 1 FROM cadu_reports_supertag_events
          WHERE client_id=%s AND site_id=%s AND occurred_at>NOW()-INTERVAL '24 hours'
          AND expires_at>NOW()) AS ready""",(selected['client_id'],flow['site_id']))[0]['ready'])
        issues=validate_flow_config(flow.get('config') or {},flow['allowed_host'])
        if not ready:issues.append({'severity':'warning','code':'tracking_not_ready','message':'Super Tag sem eventos recebidos nas últimas 24 horas. Verifique a instalação.'})
        return jsonify(issues=issues,tracking_ready=ready,draft_revision=flow['draft_revision'])

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/publish')
    @login_required_api
    def reports_flow_publish_flow(flow_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        lock_flow(flow_id, selected, expected_revision(payload))
        flow = _flow_row(flow_id, selected)
        config, has_measured_steps = _normalize_flow_config(flow.get('config') or {}, flow['allowed_host'])
        blocking = [issue for issue in validate_flow_config(config, flow['allowed_host']) if issue['severity'] == 'error']
        if not has_measured_steps:
            blocking.insert(0, {'severity': 'error', 'code': 'no_measured_steps',
                                'message': 'Adicione ao menos uma página, formulário, evento, conversão ou clique de WhatsApp antes de publicar.'})
        if blocking:
            return jsonify(error='pendencias_bloqueantes',
                           description=f"Resolva {len(blocking)} pendência(s) bloqueante(s) antes de publicar.",
                           items=blocking), 422
        _validate_flow_references(config, selected)
        changed = publish_draft(flow['id'], selected, expected_revision(payload), session['user_id'])
        get_db().commit()
        return jsonify(flow=changed, tag_url=_client_tag_urls(selected['client_id'],)['flow'],
                       supertag_url=_client_tag_urls(selected['client_id'],)['supertag'],
                       code=flow['flow_code'])

    @bp.get('/api/v2/reports/flow/flows/<flow_id>/versions')
    @login_required_api
    def reports_flow_versions(flow_id):
        selected = _selection()
        _flow_row(flow_id, selected)
        versions = _rows("""SELECT revision,name,created_by,created_at
            FROM cadu_reports_flow_versions WHERE flow_id=%s AND client_id=%s
            ORDER BY revision DESC LIMIT 100""",
            (flow_id,selected['client_id']))
        return jsonify(versions=versions)

    @bp.get('/api/v2/reports/flow/flows/<flow_id>/versions/<int:revision>')
    @login_required_api
    def reports_flow_version_detail(flow_id, revision):
        selected = _selection()
        _flow_row(flow_id, selected)
        versions = _rows("""SELECT revision,name,config,created_at
            FROM cadu_reports_flow_versions WHERE flow_id=%s AND client_id=%s AND revision=%s""",
            (flow_id, selected['client_id'], revision))
        if not versions:
            abort(404, description='Versão não encontrada neste cliente.')
        return jsonify(version=versions[0])

    @bp.get('/api/v2/reports/flow/flows/<flow_id>/live')
    @login_required_api
    def reports_flow_live(flow_id):
        from .reports_flow_live import build_live_across_revisions
        selected = _selection()
        flow = _flow_row(flow_id, selected)
        now = datetime.now(timezone.utc)
        since = request.args.get('since', '')
        if since and not re.fullmatch(r'[0-9]{1,20}', since):
            abort(400, description='Cursor inválido.')
        identity_filter = request.args.get('identity', 'all')
        if identity_filter not in ('all', 'known', 'anonymous', 'unavailable'):
            abort(400, description='Filtro de identificação inválido.')
        revision = flow.get('published_revision')
        unavailable = dict(status='unavailable', active_sessions=None, node_presence={},
                           transitions={}, generated_at=now.isoformat(), revision=revision,
                           active_window_seconds=90, next_cursor=since or None)
        if flow['status'] != 'published' or flow.get('revoked_at') or revision is None:
            return jsonify(**unavailable)
        events = _rows("""SELECT id,visitor_id,session_id,page_host,page_path,event_kind,event_name,occurred_at,flow_revision
            FROM cadu_reports_flow_events WHERE client_id=%s
              AND tag_id=%s AND flow_revision IS NOT NULL
              AND occurred_at>NOW()-INTERVAL '15 minutes' AND occurred_at<=NOW()
            ORDER BY occurred_at DESC,id DESC LIMIT 5001""",
            (selected['client_id'],flow['tag_id']))
        if len(events)>5000:
            return jsonify(**dict(unavailable,status='capacity_exceeded'))
        revisions={item['flow_revision'] for item in events}
        configs={revision:flow.get('active_config') or {}}
        if revisions-{revision}:
            versions=_rows("""SELECT revision,config FROM cadu_reports_flow_versions
                WHERE flow_id=%s AND client_id=%s
                  AND revision=ANY(%s::bigint[])""",
                (flow_id,selected['client_id'],list(revisions-{revision})))
            configs.update({row['revision']:row['config'] for row in versions})
        snapshot=build_live_across_revisions(events,configs,revision,flow['allowed_host'],now)
        # Identity is explicit and scoped to the site, session, visitor and campaign.
        identities = {}
        identity_available = bool(_rows("SELECT to_regclass('cadu_reports_supertag_visitor_sessions') AS table_name")[0]['table_name'])
        sessions = snapshot['sessions']
        if identity_available and sessions:
            links = _rows("""SELECT vs.session_id,vs.visitor_id,kv.id,kv.display_name,s.allowed_host
                FROM cadu_reports_supertag_visitor_sessions vs
                JOIN cadu_reports_supertag_sites s ON s.id=vs.site_id
                JOIN cadu_reports_supertag_sessions ss ON ss.site_id=vs.site_id AND ss.session_id=vs.session_id
                  AND ss.visitor_id=vs.visitor_id AND ss.campaign_scope=vs.campaign_scope AND ss.expires_at>NOW()
                JOIN cadu_reports_supertag_known_visitors kv ON kv.id=vs.known_visitor_id
                  AND kv.site_id=vs.site_id AND kv.campaign_scope=vs.campaign_scope AND kv.expires_at>NOW()
                WHERE s.client_id=%s AND s.id=%s AND s.enabled=TRUE AND s.revoked_at IS NULL
                  AND vs.expires_at>NOW() AND vs.session_id=ANY(%s::uuid[])""",
                (selected['client_id'],flow['site_id'],[item['session_id'] for item in sessions]))
            for link in links:
                if _host_allowed(flow['allowed_host'],link['allowed_host']):
                    identities.setdefault((str(link['session_id']),str(link['visitor_id'])),{})[str(link['id'])]=link
        for item in sessions:
            matches=identities.get((item['session_id'],item['visitor_id']),{})
            known=next(iter(matches.values())) if len(matches)==1 else None
            item['identity_status']='known' if known else 'anonymous' if identity_available and not matches else 'unavailable'
            item['display_name']=known['display_name'] if known and selected['role']!='viewer' else None
            del item['visitor_id']
        snapshot['identity_available']=identity_available
        filtered_sessions=[item for item in sessions if identity_filter=='all' or item['identity_status']==identity_filter]
        snapshot['sessions_total']=len(filtered_sessions)
        snapshot['sessions_truncated']=len(filtered_sessions)>100
        snapshot['sessions']=filtered_sessions[:100]
        snapshot['identity_filter']=identity_filter
        cursor=max([int(since or 0),*(int(value) for value in snapshot['transitions'].values())])
        if since:
            snapshot['transitions']={key:value for key,value in snapshot['transitions'].items() if int(value)>int(since)}
        return jsonify(**snapshot,status='ready',generated_at=now.isoformat(),revision=revision,
                       next_cursor=str(cursor),poll_interval_ms=15000,scope='all_pinned_publications_current_graph',
                       tracking_health={'status':'healthy' if any(item['flow_revision']==revision for item in events) else 'quiet',
                                        'window_seconds':900})

    @bp.get('/api/v2/reports/flow/flows/<flow_id>/journey')
    @login_required_api
    def reports_flow_journey(flow_id):
        selected = _selection()
        flow = _flow_row(flow_id, selected)
        try:
            days = int(request.args.get('days', 30))
        except (TypeError, ValueError):
            abort(400, description='Período inválido.')
        if days not in (7, 30, 90):
            abort(400, description='Período inválido.')
        revision = flow.get('published_revision')
        config = flow.get('active_config') or {}
        if flow['status'] != 'published' or revision is None or flow.get('revoked_at'):
            return jsonify(status='unavailable', revision=revision, period_days=days, config=None,
                           nodes=[], edges=[], suggestions=[])
        requested_revision=request.args.get('revision','')
        if requested_revision:
            try:
                revision=int(requested_revision)
            except ValueError:
                abort(400,description='Publicação inválida.')
            versions=_rows("""SELECT config FROM cadu_reports_flow_versions WHERE flow_id=%s
                AND client_id=%s AND revision=%s""",
                (flow_id,selected['client_id'],revision))
            if not versions:
                abort(404,description='Publicação não encontrada neste cliente.')
            config=versions[0]['config']
        now=datetime.now(timezone.utc)
        zone=ZoneInfo('America/Sao_Paulo')
        start_arg=request.args.get('start_date') or request.args.get('from')
        end_arg=request.args.get('end_date') or request.args.get('to')
        try:
            if start_arg or end_arg:
                start_day=date.fromisoformat(start_arg or '')
                end_day=date.fromisoformat(end_arg or '')
                if start_day>end_day or (end_day-start_day).days>366:
                    raise ValueError()
                start=datetime.combine(start_day,datetime.min.time(),zone)
                end=datetime.combine(end_day+timedelta(days=1),datetime.min.time(),zone)
            else:
                start=datetime.combine(now.astimezone(zone).date()-timedelta(days=days-1),datetime.min.time(),zone)
                end=now
        except ValueError:
            abort(400,description='Informe um intervalo válido de até 367 dias.')
        scope=[selected['client_id'],flow['tag_id'],revision,start,end]
        extra=''
        for field,column in [('account_id','c.account_id'),('campaign_id','e.campaign_id')]:
            raw=request.args.get(field,'')
            if raw:
                try:
                    number=int(raw)
                    if number<1: raise ValueError()
                except ValueError:
                    abort(400,description='Filtro inválido.')
                extra+=f' AND {column}=%s'
                scope.append(number)
        platform=request.args.get('platform','')
        if platform:
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}',platform):
                abort(400,description='Plataforma inválida.')
            extra+=' AND a.platform=%s';scope.append(platform)
        # Keep unmapped visits in the sequence. Match IDs were frozen at ingestion.
        visits_cte="""WITH visits AS (
            SELECT e.id,e.session_id,e.occurred_at,s.node_id,
                COALESCE('utm:'||NULLIF(LOWER(e.utm_source),''),'ref:'||NULLIF(LOWER(e.referrer_host),'')) AS origin
            FROM cadu_reports_flow_events e
            LEFT JOIN cadu_reports_flow_steps s ON s.id=e.step_id
              AND s.client_id=e.client_id
              AND s.flow_revision=e.flow_revision
            LEFT JOIN cadu_reports_campaigns c ON c.id=e.campaign_id
              AND c.client_id=e.client_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id
              AND a.client_id=e.client_id
            WHERE e.client_id=%s AND e.tag_id=%s AND e.flow_revision=%s
              AND e.occurred_at >= %s AND e.occurred_at < %s
              AND (e.event_kind IN ('page_view','conversion','error_view')
                OR (s.node_id IS NOT NULL AND e.event_kind NOT IN ('heartbeat','page_leave','click')))
        """+extra+"""), hits AS (
            SELECT node_id,session_id,COUNT(*)::bigint AS events FROM visits
            WHERE node_id IS NOT NULL GROUP BY node_id,session_id
        ) """
        hits_cte=visits_cte
        node_rows = _rows(hits_cte + """SELECT node_id,COUNT(*)::bigint AS sessions,
            SUM(events)::bigint AS events FROM hits GROUP BY node_id""", scope)
        node_totals = {str(row['node_id']): row for row in node_rows}
        collection = _rows(visits_cte + """SELECT COUNT(*)::bigint AS event_count,
            COUNT(*) FILTER (WHERE node_id IS NOT NULL)::bigint AS mapped_event_count,
            MAX(occurred_at) AS last_event_at FROM visits""", scope)[0]
        has_events = bool(collection['event_count'])
        measured_nodes = [node for node in config.get('nodes', []) if isinstance(node, dict)
                          and node.get('id') and node.get('type') in {'page', 'form', 'event', 'conversion', 'whatsapp', 'error'}]
        measured_ids = {node['id'] for node in measured_nodes}
        incoming_measured = {edge.get('to') for edge in config.get('edges', [])
                             if isinstance(edge, dict) and edge.get('from') in measured_ids}
        entry_ids = [node['id'] for node in measured_nodes
                     if node.get('isEntry') or node['id'] not in incoming_measured]
        if not entry_ids and measured_nodes:
            entry_ids = [measured_nodes[0]['id']]
        conversion_ids = [node['id'] for node in measured_nodes if node.get('type') == 'conversion']
        funnel = _rows(visits_cte + """, entered AS (
            SELECT DISTINCT ON (session_id) session_id,occurred_at,id FROM visits
            WHERE node_id=ANY(%s::text[]) ORDER BY session_id,occurred_at,id
        ) SELECT (SELECT COUNT(*) FROM entered)::bigint AS entries,
            (SELECT COUNT(DISTINCT v.session_id) FROM visits v JOIN entered e USING(session_id)
                WHERE v.node_id=ANY(%s::text[]) AND (v.occurred_at,v.id)>(e.occurred_at,e.id))::bigint AS conversions""",
            (*scope, entry_ids, conversion_ids))[0]
        authored_edges = [edge for edge in config.get('edges', [])
            if isinstance(edge, dict) and edge.get('from') and edge.get('to')]
        transitions = _rows(visits_cte + """, numbered AS (
            SELECT *,LAG(node_id) OVER w AS previous_node,ROW_NUMBER() OVER w AS visit_number
            FROM visits WINDOW w AS (PARTITION BY session_id ORDER BY occurred_at,id)
        ), collapsed AS (
            SELECT * FROM numbered WHERE visit_number=1 OR node_id IS DISTINCT FROM previous_node
        ), ordered AS (
            SELECT node_id AS source_id,session_id,
                LEAD(node_id) OVER (PARTITION BY session_id ORDER BY occurred_at,id) AS target_id
            FROM collapsed
        ) SELECT source_id,target_id,COUNT(DISTINCT session_id)::bigint AS sessions
          FROM ordered WHERE source_id IS NOT NULL AND target_id IS NOT NULL AND source_id<>target_id
          GROUP BY source_id,target_id ORDER BY sessions DESC""", tuple(scope))
        # An authored edge represents a direct passage. Counting any later hit
        # at the target would attribute skipped pages to edges never traversed.
        transition_totals = {(row['source_id'], row['target_id']): int(row['sessions'])
                             for row in transitions}
        authored_pairs = {(edge['from'], edge['to']) for edge in authored_edges}
        nodes = [{'id': node['id'], 'sessions': int(node_totals.get(node['id'], {}).get('sessions') or 0) if node['id'] in measured_ids else None,
                  'events': int(node_totals.get(node['id'], {}).get('events') or 0) if node['id'] in measured_ids else None}
                 for node in config.get('nodes', []) if isinstance(node, dict) and node.get('id')]
        edges = [{'id': edge['id'], 'from': edge['from'], 'to': edge['to'],
                  'sessions': transition_totals.get((edge['from'], edge['to']), 0) if edge['from'] in measured_ids and edge['to'] in measured_ids else None,
                  'rate': round(100 * transition_totals.get((edge['from'], edge['to']), 0) /
                                int(node_totals[edge['from']]['sessions']), 1) if node_totals.get(edge['from'], {}).get('sessions') else None,
                  'observation': edge_observation(edge,measured_ids,node_totals,transition_totals,has_events)}
                 for edge in authored_edges if edge.get('id')]
        suggestions = [{'from': row['source_id'], 'to': row['target_id'],
                        'sessions': int(row['sessions'])}
                       for row in transitions if (row['source_id'], row['target_id']) not in authored_pairs][:20]
        # Distinct sessions over the union of members, never the sum of page totals.
        group_map={member:group['id'] for group in config.get('groups',[]) for member in group.get('memberIds',[])}
        group_nodes=[];group_edges=[]
        if group_map:
            projection=json.dumps(group_map)
            projected_cte=visits_cte+""", projected AS (
                SELECT *,COALESCE(%s::jsonb->>node_id,node_id) AS visual_id FROM visits
            ), numbered_groups AS (
                SELECT *,LAG(visual_id) OVER w AS prior,ROW_NUMBER() OVER w AS sequence
                FROM projected WINDOW w AS (PARTITION BY session_id ORDER BY occurred_at,id)
            ), collapsed_groups AS (
                SELECT * FROM numbered_groups WHERE sequence=1 OR visual_id IS DISTINCT FROM prior
            ), paths_groups AS (
                SELECT visual_id AS source,session_id,
                  LEAD(visual_id) OVER (PARTITION BY session_id ORDER BY occurred_at,id) AS target
                FROM collapsed_groups
            ) """
            group_nodes=_rows(projected_cte+"SELECT visual_id AS id,COUNT(DISTINCT session_id)::bigint AS sessions,COUNT(*)::bigint AS events FROM projected WHERE visual_id IS NOT NULL GROUP BY visual_id",(*scope,projection))
            group_edges=_rows(projected_cte+"SELECT source AS \"from\",target AS \"to\",COUNT(DISTINCT session_id)::bigint AS sessions FROM paths_groups WHERE source IS NOT NULL AND target IS NOT NULL AND source<>target GROUP BY source,target",(*scope,projection))
            denominators={row['id']:row['sessions'] for row in group_nodes}
            for edge in group_edges:edge['rate']=round(100*edge['sessions']/denominators[edge['from']],1) if denominators.get(edge['from']) else None
        # First and last mapped page of each session: where people land, where they leave, and from which origin.
        bounds = _rows(visits_cte + """, bounds AS (
            SELECT session_id,
                (ARRAY_AGG(node_id ORDER BY occurred_at,id))[1] AS first_node,
                (ARRAY_AGG(node_id ORDER BY occurred_at DESC,id DESC))[1] AS last_node,
                (ARRAY_AGG(origin ORDER BY occurred_at,id))[1] AS origin
            FROM visits WHERE node_id IS NOT NULL GROUP BY session_id
        ) SELECT first_node,last_node,origin,COUNT(*)::bigint AS sessions
          FROM bounds GROUP BY first_node,last_node,origin""", tuple(scope))
        apply_session_bounds(config, nodes, edges, bounds, measured_ids)
        # Engagement, for sites read by attention rather than a single conversion:
        # active time per page (page_leave carries it) and distinct pages per session.
        active = _rows("""SELECT s.node_id,AVG(e.duration_ms)::bigint AS avg_active_ms,COUNT(*)::bigint AS leaves
            FROM cadu_reports_flow_events e
            JOIN cadu_reports_flow_steps s ON s.id=e.step_id AND s.client_id=e.client_id AND s.flow_revision=e.flow_revision
            LEFT JOIN cadu_reports_campaigns c ON c.id=e.campaign_id AND c.client_id=e.client_id
            LEFT JOIN cadu_reports_accounts a ON a.id=c.account_id AND a.client_id=e.client_id
            WHERE e.client_id=%s AND e.tag_id=%s AND e.flow_revision=%s
              AND e.occurred_at >= %s AND e.occurred_at < %s
              AND e.event_kind='page_leave' AND e.duration_ms>0"""+extra+"""
            GROUP BY s.node_id""", tuple(scope))
        depth = _rows(visits_cte + """SELECT AVG(pages)::numeric(10,2) AS pages_per_session FROM (
            SELECT session_id,COUNT(DISTINCT node_id) AS pages FROM visits WHERE node_id IS NOT NULL GROUP BY session_id) per_session""",
            tuple(scope))[0]
        engagement = apply_engagement(nodes, active, depth, measured_ids)
        origins = origin_summary(bounds)
        entries = int(funnel['entries'] or 0)
        conversions = int(funnel['conversions'] or 0)
        return jsonify(status='ready', revision=revision, period_days=days, config=migrate_v1_to_v2(config),
                       timezone='America/Sao_Paulo',generated_at=now.isoformat(),
                       collection={'status':'observed' if has_events else 'no_data',
                                   'event_count':int(collection['event_count']),
                                   'mapped_event_count':int(collection['mapped_event_count']),
                                   'coverage_percent':round(100*collection['mapped_event_count']/collection['event_count'],1) if has_events else None,
                                   'last_event_at':collection['last_event_at'].isoformat() if collection['last_event_at'] else None,
                                   'source':'Super Tag deste fluxo'},
                       scope={'from':start.isoformat(),'to':end.isoformat(),'revision':revision,
                              'account_id':request.args.get('account_id'),'campaign_id':request.args.get('campaign_id'),'platform':platform},
                       nodes=nodes, edges=edges, origins=origins, engagement=engagement, suggestions=suggestions,group_nodes=group_nodes,group_edges=group_edges,
                       funnel={'entries': entries, 'conversions': conversions,
                               'rate': round(100 * conversions / entries, 1) if entries else None})

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/versions/<int:revision>/restore')
    @login_required_api
    def reports_flow_restore(flow_id, revision):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        current = _flow_row(flow_id, selected)
        versions = _rows("""SELECT name,config FROM cadu_reports_flow_versions
            WHERE flow_id=%s AND client_id=%s AND revision=%s""",
            (flow_id,selected['client_id'],revision))
        if not versions:
            abort(404, description='Versão não encontrada neste cliente.')
        config, _ = _normalize_flow_config(versions[0]['config'], current['allowed_host'])
        _validate_flow_references(config, selected)
        updated = save_draft(flow_id,selected,expected_revision(payload),versions[0]['name'],config)
        get_db().commit()
        return jsonify(flow=updated)

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/unpublish')
    @login_required_api
    def reports_flow_unpublish_flow(flow_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        changed = _rows('''UPDATE cadu_reports_flow_registry SET status='draft',updated_at=NOW()
            WHERE id=%s AND client_id=%s
            RETURNING id,flow_code,name,status,published_at''',
            (flow['id'], selected['client_id']))[0]
        get_db().commit()
        return jsonify(flow=changed)

    @bp.post('/api/v2/reports/flow/flows/<flow_id>/test')
    @login_required_api
    def reports_flow_test_flow(flow_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        flow = _flow_row(flow_id, selected)
        events = payload.get('events')
        if not isinstance(events, list) or not events or len(events) > 30:
            abort(400, description='Envie até 30 eventos fictícios para o teste.')
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
                (client_id,flow_id,flow_code,event_kind,page_host,page_path,source_label,session_id,payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                RETURNING id,event_kind,page_host,page_path,source_label,created_at''',
                (selected['client_id'], flow['id'], flow['flow_code'],
                 item['kind'],test_host,path,source,session_id,json.dumps(details)))[0]
            accepted.append(row)
        get_db().commit()
        return jsonify(flow_code=flow['flow_code'], simulated=True, session_id=session_id, events=accepted)

    @bp.patch('/api/v2/reports/flow/tags/<tag_id>')
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
            WHERE id=%s AND client_id=%s
                AND tag_kind=%s
            RETURNING id,label,allowed_host,public_key,created_at,revoked_at,tag_kind''',
            (label, host, tag['id'], selected['client_id'], tag['tag_kind']))
        get_db().commit()
        return jsonify(tag=changed[0])

    @bp.post('/api/v2/reports/flow/tags/<tag_id>/revoke')
    @login_required_api
    def reports_flow_revoke_tag(tag_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        tag = _tag_for_client(tag_id, selected)
        _rows('UPDATE cadu_reports_site_tags SET revoked_at=NOW() WHERE id=%s AND client_id=%s RETURNING id',
              (tag['id'], selected['client_id']))
        get_db().commit()
        return jsonify(revoked=True)

    @bp.post('/api/v2/reports/flow/steps')
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
                    AND client_id=%s''',
                    (campaign_id, selected['client_id'])):
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
                AND client_id=%s RETURNING id''',
                (tag['id'],selected['client_id']))
            _rows('''UPDATE cadu_reports_flow_steps SET position=position+1 WHERE tag_id=%s
                AND client_id=%s AND is_active=TRUE AND position < %s''',
                (tag['id'],selected['client_id'],position))
            position=0
        result = _rows('''INSERT INTO cadu_reports_flow_steps
            (client_id,tag_id,name,path_prefix,page_host,step_kind,is_entry,campaign_id,position)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id,name,path_prefix,page_host,step_kind,is_entry,campaign_id,position''',
            (selected['client_id'],tag['id'],name,path,page_host,
             kind,is_entry,campaign_id,position))
        get_db().commit()
        return jsonify(step=result[0]), 201

    @bp.patch('/api/v2/reports/flow/steps/<int:step_id>')
    @login_required_api
    def reports_flow_update_step(step_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            abort(400)
        selected = _selection(payload)
        _write_guard(selected)
        found = _rows('''SELECT id,tag_id,name,path_prefix,page_host,step_kind,is_entry,campaign_id,position
            FROM cadu_reports_flow_steps WHERE id=%s AND client_id=%s
                AND is_active=TRUE FOR UPDATE''', (step_id, selected['client_id']))
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
                WHERE id=%s AND client_id=%s''',
                (campaign_id, selected['client_id'])):
            abort(404, description='Campanha não encontrada.')
        try:
            position = int(payload.get('position', current['position']))
        except (ValueError, TypeError):
            abort(400, description='Posição inválida.')
        if position < 0 or position > 1000:
            abort(400, description='Posição inválida.')
        if is_entry:
            _rows('''UPDATE cadu_reports_flow_steps SET is_entry=FALSE WHERE tag_id=%s
                AND client_id=%s AND id<>%s RETURNING id''',
                (tag['id'],selected['client_id'],step_id))
            _rows('''UPDATE cadu_reports_flow_steps SET position=position+1 WHERE tag_id=%s
                AND client_id=%s AND is_active=TRUE AND id<>%s AND position < %s''',
                (tag['id'],selected['client_id'],step_id,position))
            position=0
        changed = _rows('''UPDATE cadu_reports_flow_steps SET name=%s,path_prefix=%s,page_host=%s,step_kind=%s,
                is_entry=%s,campaign_id=%s,position=%s WHERE id=%s AND client_id=%s
                AND position=(SELECT position FROM cadu_reports_flow_steps
                    WHERE id=%s AND client_id=%s FOR UPDATE)
            RETURNING id,tag_id,name,path_prefix,page_host,step_kind,is_entry,campaign_id,position''',
            (name,path,page_host,kind,is_entry,campaign_id,position,step_id,selected['client_id'],
             step_id, selected['client_id']))
        if not changed:
            get_db().rollback()
            abort(409, description='A etapa foi alterada ao mesmo tempo. Atualize o funil e tente novamente.')
        get_db().commit()
        return jsonify(step=changed[0])

    @bp.post('/api/v2/reports/flow/steps/<int:step_id>/archive')
    @login_required_api
    def reports_flow_archive_step(step_id):
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        changed = _rows('''UPDATE cadu_reports_flow_steps SET is_active=FALSE,archived_at=NOW()
            WHERE id=%s AND client_id=%s AND is_active=TRUE
            RETURNING id''', (step_id, selected['client_id']))
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
        tag = _rows('''SELECT id,client_id,allowed_host FROM cadu_reports_site_tags
            WHERE public_key=%s AND revoked_at IS NULL AND client_id=%s''',
            (public_key, request.args.get('client_id', type=int)))
        if not tag:
            abort(404)
        tag = tag[0]
        request._cadu_flow_cors_tag = [{'allowed_host': tag['allowed_host']}]
        shared_site = _rows('''SELECT allowed_host FROM cadu_reports_supertag_sites
            WHERE client_id=%s AND enabled=TRUE AND revoked_at IS NULL''',
            (tag['client_id'],))
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
            WHERE tag_id=%s AND client_id=%s AND is_active=TRUE
            ORDER BY length(path_prefix) DESC,is_entry DESC,position,id''',
            (tag['id'], tag['client_id']))
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
            (client_id,tag_id,visitor_id,session_id,event_kind,page_host,page_path,referrer_host,utm_source,utm_medium,utm_campaign,utm_id,click_id,step_id,campaign_id,attribution_method)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (tag['client_id'], tag['id'], visitor, visit_session,
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
        flow = _rows('''SELECT f.id,f.client_id,f.flow_code,f.status,f.config,t.allowed_host
            FROM cadu_reports_flow_registry f JOIN cadu_reports_site_tags t ON t.id=f.tag_id
            WHERE f.flow_code=%s AND f.status='published' AND t.revoked_at IS NULL
                AND t.public_key=%s AND t.client_id=%s''',
            (flow_code, request.args.get('key',''), request.args.get('client_id', type=int)))
        if not flow:
            abort(404)
        flow = flow[0]
        request._cadu_flow_cors_tag = [{'allowed_host': flow['allowed_host']}]
        shared_site = _rows('''SELECT allowed_host FROM cadu_reports_supertag_sites
            WHERE client_id=%s AND enabled=TRUE AND revoked_at IS NULL''',
            (flow['client_id'],))
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
        tag = _rows('SELECT tag_id AS id FROM cadu_reports_flow_registry WHERE id=%s AND client_id=%s',
                    (flow['id'],flow['client_id']))[0]
        flow = session_snapshot({**flow,'tag_id':tag['id']}, session_id)
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
        step = match_version_step(flow,safe_path,page_host,kind,event_name)
        matched_step = [step] if step else []
        campaign_id, method = _campaign_match(
            {'client_id': flow['client_id']},
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
            (client_id,tag_id,visitor_id,session_id,event_kind,event_name,page_host,page_path,referrer_host,utm_source,utm_medium,utm_campaign,utm_id,click_id,step_id,campaign_id,attribution_method,duration_ms,flow_revision)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (flow['client_id'], tag['id'], visitor_id, visit_session,
             kind,event_name,page_host,safe_path,referrer,attribution_values['utm_source'],attribution_values['utm_medium'],
             attribution_values['utm_campaign'], attribution_values['utm_id'], attribution_values['click_id'],
             step_id, campaign_id, method, duration_ms,flow['published_revision']))
        get_db().commit()
        return ('',204)
