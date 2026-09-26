"""Public-source portal directory projections and ingestion helpers."""
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from hashlib import sha256
from datetime import datetime, timezone
import ipaddress
import socket

from werkzeug.exceptions import BadRequest

from ..cadu_family import repository
from ..db import get_db


def catalog(query='', category='', sort='featured', limit=50, offset=0):
    """Return a bounded, server-paged portal catalog; audience is source-backed only."""
    try:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        raise BadRequest('Paginação inválida.')
    q = str(query or '').strip()[:120]
    category = str(category or '').strip()[:80]
    order = 'featured_rank ASC NULLS LAST, name ASC' if sort != 'name' else 'name ASC'
    params = []
    where = ['active = TRUE']
    if q:
        where.append("(name ILIKE %s OR domain ILIKE %s OR category ILIKE %s OR description ILIKE %s)")
        params.extend([f'%{q}%'] * 4)
    if category:
        where.append('category = %s')
        params.append(category)
    clause = ' AND '.join(where)
    total = repository.rows(f'SELECT COUNT(*) AS total FROM cadu_planner_portals WHERE {clause}', tuple(params))[0]['total']
    rows = repository.rows(f'''SELECT id, name, domain, category, description, audience_estimate,
                                      audience_period, audience_source_url, audience_checked_at,
                                      public_attributes, featured_rank, last_crawled_at
                                 FROM cadu_planner_portals WHERE {clause}
                                ORDER BY {order} LIMIT %s OFFSET %s''', tuple(params + [limit, offset]))
    for row in rows:
        row['public_attributes'] = row.get('public_attributes') or []
    return {'records': rows, 'total': total, 'limit': limit, 'offset': offset}


def catalog_facets():
    rows = repository.rows('''SELECT DISTINCT category FROM cadu_planner_portals
                               WHERE active = TRUE AND category IS NOT NULL ORDER BY category''')
    return {'categories': [row['category'] for row in rows]}


def detail(portal_id):
    try:
        portal_id = int(portal_id)
    except (TypeError, ValueError):
        raise BadRequest('Identificador de portal inválido.')
    rows = repository.rows('''SELECT id, name, domain, category, description, audience_estimate,
                                     audience_period, audience_source_url, audience_checked_at,
                                     public_attributes, featured_rank, last_crawled_at
                                FROM cadu_planner_portals WHERE id = %s AND active = TRUE''', (portal_id,))
    if not rows:
        from werkzeug.exceptions import NotFound
        raise NotFound('Portal indisponível.')
    return rows[0]


def score_public_evidence(portal):
    """Produce bounded TypeSafe judgments from scraped, public page evidence.

    Scores are advisory ranking signals only. Missing/ambiguous evidence stays
    explicitly reviewable and never becomes an audience claim or publication.
    """
    from ..services.typesafe_service import system_one

    if not isinstance(portal, dict):
        raise BadRequest('Portal inválido para avaliação.')
    state = {
        'portal': {
            'name': str(portal.get('name') or '')[:180],
            'domain': str(portal.get('domain') or '')[:255],
            'editorial_category': str(portal.get('category') or '')[:80],
            'curated_description': str(portal.get('description') or '')[:500],
            'homepage_title': str(portal.get('title') or '')[:180],
            'homepage_description': str(portal.get('crawled_description') or '')[:500],
            'public_source_url': str(portal.get('source_url') or '')[:2048],
        }
    }
    result = system_one(state, {
        'editorial_fit': {
            'type': 'score',
            'instructions': 'Avalie o quanto a evidência pública da página indica que este domínio é um portal editorial ativo, adequado ao catálogo de veículos do Planner. Use somente os dados em `portal`; ausência de evidência deve reduzir a avaliação.',
            'criteria': [
                'A evidência não demonstra um portal editorial ou é insuficiente.',
                'Há sinais parciais de conteúdo editorial, com escopo ou atividade incertos.',
                'A evidência pública demonstra um portal editorial ativo com escopo identificável.',
            ],
        },
        'audience_evidence': {
            'type': 'score',
            'instructions': 'Avalie a força da evidência pública presente em `portal` para caracterizar o público do veículo. Não estime audiência nem infira tamanho de público a partir da popularidade.',
            'criteria': [
                'Não há evidência pública suficiente para caracterizar o público.',
                'A evidência descreve parcialmente o público ou o tema editorial.',
                'A evidência descreve claramente o perfil ou tema do público, sem afirmar alcance numérico.',
            ],
        },
    })
    answers = result['answers']
    return {
        'model': 'jev-latest',
        'evidence_hash': str(portal.get('source_hash') or ''),
        'source_url': state['portal']['public_source_url'],
        'scores': {
            key: {
                'score': answers.get(key, {}).get('score'),
                'confidence': answers.get(key, {}).get('confidence'),
                'probabilities': answers.get(key, {}).get('probabilities'),
            }
            for key in ('editorial_fit', 'audience_evidence')
        },
        'needs_human_review': any(
            not isinstance(answers.get(key), dict)
            or answers[key].get('confidence', 0) < 0.65
            for key in ('editorial_fit', 'audience_evidence')
        ),
    }


def validate_source_url(value):
    parsed = urlparse(str(value or '').strip())
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise BadRequest('A fonte precisa ser uma URL HTTPS pública.')
    return parsed.geturl()


class _PublicMetadata(HTMLParser):
    """Extract only public metadata and links; never execute page scripts."""
    def __init__(self):
        super().__init__()
        self.title = False
        self.title_text = []
        self.meta = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == 'title':
            self.title = True
        elif tag.lower() == 'meta':
            key = (attrs.get('property') or attrs.get('name') or '').lower()
            value = attrs.get('content', '').strip()
            if key in {'description', 'og:description', 'og:title', 'og:site_name'} and value:
                self.meta[key] = value[:500]
        elif tag.lower() == 'a' and attrs.get('href'):
            self.links.append(attrs['href'][:2048])

    def handle_endtag(self, tag):
        if tag.lower() == 'title':
            self.title = False

    def handle_data(self, data):
        if self.title and data.strip():
            self.title_text.append(data.strip())


def crawl_public_metadata(domain, timeout=12):
    """Fetch public homepage metadata when robots.txt allows it; one host per call."""
    host = str(domain or '').strip().lower().rstrip('.')
    if not host or '/' in host or ':' in host or '@' in host:
        raise BadRequest('Domínio inválido.')
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            return {'domain': host, 'status': 'non_public_address'}
    except (socket.gaierror, ValueError):
        return {'domain': host, 'status': 'dns_failed'}
    base = f'https://{host}/'
    agent = 'CaduPlannerCatalogBot/1.0 (+https://cadu.ai/crawler)'
    robots_url = urljoin(base, '/robots.txt')
    try:
        robots_request = Request(robots_url, headers={'User-Agent': agent})
        with urlopen(robots_request, timeout=timeout) as response:
            robots_body = response.read(256_000).decode('utf-8', 'replace')
        parser = RobotFileParser(robots_url)
        parser.parse(robots_body.splitlines())
        if not parser.can_fetch(agent, base):
            return {'domain': host, 'status': 'robots_disallowed'}
    except HTTPError as error:
        if error.code not in (404, 410):
            return {'domain': host, 'status': 'robots_unavailable'}
    except (URLError, TimeoutError, OSError):
        return {'domain': host, 'status': 'robots_unavailable'}
    try:
        request = Request(base, headers={'User-Agent': agent, 'Accept': 'text/html'})
        with urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            parsed = urlparse(final_url)
            if parsed.scheme != 'https' or parsed.hostname != host:
                return {'domain': host, 'status': 'redirect_outside_domain'}
            content_type = response.headers.get_content_type()
            if content_type != 'text/html':
                return {'domain': host, 'status': 'not_html'}
            body = response.read(1_000_001)
            if len(body) > 1_000_000:
                return {'domain': host, 'status': 'page_too_large'}
        decoded = body.decode('utf-8', 'replace')
        document = _PublicMetadata()
        document.feed(decoded)
        return {'domain': host, 'status': 'ok', 'source_url': final_url,
                'source_hash': sha256(body).hexdigest(),
                'title': ' '.join(document.title_text)[:180],
                'description': document.meta.get('description') or document.meta.get('og:description', ''),
                'site_name': document.meta.get('og:site_name', ''),
                'collected_at': datetime.now(timezone.utc).isoformat(),
                'public_links': [urljoin(final_url, link) for link in document.links[:200]
                                 if urlparse(urljoin(final_url, link)).hostname == host]}
    except HTTPError as error:
        return {'domain': host, 'status': f'http_{error.code}'}
    except (URLError, TimeoutError, OSError):
        return {'domain': host, 'status': 'fetch_failed'}


def save_crawl_result(result):
    """Update public metadata only; never infer audience or editorial category."""
    if result.get('status') != 'ok':
        return False
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_planner_portals
                              SET description = COALESCE(NULLIF(%s, ''), description),
                                  source_url = %s, source_hash = %s,
                                  last_crawled_at = %s, updated_at = NOW()
                            WHERE domain = %s''', (result.get('description', ''), result['source_url'],
                                                   result['source_hash'], result['collected_at'], result['domain']))
            saved = cur.rowcount > 0
        conn.commit()
        return saved
    except Exception:
        conn.rollback()
        raise
