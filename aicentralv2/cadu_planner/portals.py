"""Public-source portal directory projections and ingestion helpers."""
from html.parser import HTMLParser
import csv
import json
import re
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import URLError, HTTPError
from hashlib import sha256
from datetime import datetime, timezone
import ipaddress
import socket

from werkzeug.exceptions import BadRequest


def catalog(query='', category='', sort='featured', limit=50, offset=0):
    """Return a bounded, server-paged portal catalog; audience is source-backed only."""
    from ..cadu_family import repository
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
    from ..cadu_family import repository
    rows = repository.rows('''SELECT DISTINCT category FROM cadu_planner_portals
                               WHERE active = TRUE AND category IS NOT NULL ORDER BY category''')
    return {'categories': [row['category'] for row in rows]}


def detail(portal_id):
    from ..cadu_family import repository
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


def import_curated_csv(file_obj, dry_run=False):
    """Validate and import reviewed portal records from a UTF-8 CSV file.

    Audience figures require a public HTTPS source, a reporting period and an
    explicit observation date. Blank audience values never overwrite evidence.
    """
    reader = csv.DictReader(file_obj)
    required = {'name', 'domain', 'category'}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise BadRequest('CSV precisa conter as colunas name, domain e category.')

    validated = []
    seen_domains = set()
    for line, row in enumerate(reader, start=2):
        name = str(row.get('name') or '').strip()
        domain = str(row.get('domain') or '').strip().lower().rstrip('.')
        category = str(row.get('category') or '').strip()
        if not name or not category or not re.fullmatch(r'[a-z0-9.-]{1,255}', domain):
            raise BadRequest(f'Linha {line}: nome, domínio ou categoria inválidos.')
        if domain.startswith('.') or domain.endswith('.') or '..' in domain or '/' in domain:
            raise BadRequest(f'Linha {line}: domínio inválido.')
        if domain in seen_domains:
            raise BadRequest(f'Linha {line}: domínio duplicado no CSV ({domain}).')
        seen_domains.add(domain)

        audience = str(row.get('audience_estimate') or '').strip()
        period = str(row.get('audience_period') or '').strip()
        source = str(row.get('audience_source_url') or '').strip()
        checked = str(row.get('audience_checked_at') or '').strip()
        if audience:
            if not source or not period or not checked:
                raise BadRequest(f'Linha {line}: estimativa exige fonte, período e data de verificação.')
            source = validate_source_url(source)
            try:
                checked_at = datetime.fromisoformat(checked.replace('Z', '+00:00'))
            except ValueError as exc:
                raise BadRequest(f'Linha {line}: audience_checked_at deve ser ISO-8601.') from exc
            if checked_at.tzinfo is None:
                raise BadRequest(f'Linha {line}: audience_checked_at deve incluir fuso horário.')
        else:
            audience = period = source = None
            checked_at = None

        attributes_raw = str(row.get('public_attributes') or '[]').strip()
        try:
            attributes = json.loads(attributes_raw)
        except json.JSONDecodeError as exc:
            raise BadRequest(f'Linha {line}: public_attributes deve ser JSON válido.') from exc
        if not isinstance(attributes, list):
            raise BadRequest(f'Linha {line}: public_attributes deve ser uma lista JSON.')
        review = next((item.get('valor') for item in attributes
                       if isinstance(item, dict) and item.get('atributo') == 'status_curadoria'), None)
        if review != 'aprovado':
            raise BadRequest(f'Linha {line}: o registro ainda não foi aprovado pela curadoria editorial.')
        rank = str(row.get('featured_rank') or '').strip()
        try:
            featured_rank = int(rank) if rank else None
        except ValueError as exc:
            raise BadRequest(f'Linha {line}: featured_rank deve ser um número de 1 a 200.') from exc
        if featured_rank is not None and not 1 <= featured_rank <= 200:
            raise BadRequest(f'Linha {line}: featured_rank deve ser um número de 1 a 200.')

        validated.append({
            'name': name[:180], 'domain': domain, 'category': category[:80],
            'description': str(row.get('description') or '').strip(),
            'audience': audience, 'period': period, 'source': source,
            'checked_at': checked_at, 'attributes': json.dumps(attributes, ensure_ascii=False),
            'featured_rank': featured_rank,
        })

    if not dry_run and validated:
        conn = get_db()
        try:
            with conn.cursor() as cur:
                for item in validated:
                    cur.execute('''INSERT INTO cadu_planner_portals
                        (name, domain, category, description, audience_estimate,
                         audience_period, audience_source_url, audience_checked_at,
                         public_attributes, featured_rank)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (domain) DO UPDATE SET
                          name = EXCLUDED.name, category = EXCLUDED.category,
                          description = CASE WHEN EXCLUDED.description <> '' THEN EXCLUDED.description
                                             ELSE cadu_planner_portals.description END,
                          audience_estimate = COALESCE(EXCLUDED.audience_estimate, cadu_planner_portals.audience_estimate),
                          audience_period = COALESCE(EXCLUDED.audience_period, cadu_planner_portals.audience_period),
                          audience_source_url = COALESCE(EXCLUDED.audience_source_url, cadu_planner_portals.audience_source_url),
                          audience_checked_at = COALESCE(EXCLUDED.audience_checked_at, cadu_planner_portals.audience_checked_at),
                          public_attributes = CASE WHEN EXCLUDED.public_attributes = '[]'::jsonb
                                                   THEN cadu_planner_portals.public_attributes
                                                   ELSE EXCLUDED.public_attributes END,
                          featured_rank = COALESCE(EXCLUDED.featured_rank, cadu_planner_portals.featured_rank),
                          active = TRUE, updated_at = NOW()''',
                        (item['name'], item['domain'], item['category'], item['description'],
                         item['audience'], item['period'], item['source'], item['checked_at'],
                         item['attributes'], item['featured_rank']))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {'rows': len(validated), 'dry_run': bool(dry_run)}


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


class _SameHostHttpsRedirect(HTTPRedirectHandler):
    """Only follow HTTPS redirects that remain on the originally checked host."""
    def __init__(self, host):
        super().__init__()
        self.host = host

    def redirect_request(self, request, fp, code, message, headers, new_url):
        parsed = urlparse(new_url)
        if parsed.scheme != 'https' or parsed.hostname != self.host or parsed.port not in (None, 443):
            return None
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)}
            if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
                return None
        except (socket.gaierror, ValueError):
            return None
        return super().redirect_request(request, fp, code, message, headers, new_url)


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
    opener = build_opener(_SameHostHttpsRedirect(host))
    robots_url = urljoin(base, '/robots.txt')
    try:
        robots_request = Request(robots_url, headers={'User-Agent': agent})
        with opener.open(robots_request, timeout=timeout) as response:
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
        with opener.open(request, timeout=timeout) as response:
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
    from ..db import get_db
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
