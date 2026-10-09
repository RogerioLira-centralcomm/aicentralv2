"""Public-source portal directory projections and ingestion helpers."""
from html.parser import HTMLParser
import csv
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import URLError, HTTPError
from hashlib import sha256
from datetime import datetime, timezone
import ipaddress
import socket

from werkzeug.exceptions import BadRequest


PORTAL_COLUMNS = """id, name, domain, category, description, audience_estimate,
                    audience_period, audience_source_url, audience_checked_at,
                    public_attributes, featured_rank, last_crawled_at,
                    COALESCE((to_jsonb(cadu_planner_portals)->>'discovered_pages_count')::INTEGER, 0) AS discovered_pages_count,
                    COALESCE((to_jsonb(cadu_planner_portals)->>'crawl_updates_count')::INTEGER, 0) AS crawl_updates_count,
                    to_jsonb(cadu_planner_portals)->>'scope' AS scope,
                    to_jsonb(cadu_planner_portals)->>'uf' AS uf,
                    to_jsonb(cadu_planner_portals)->>'site_title' AS site_title,
                    to_jsonb(cadu_planner_portals)->>'favicon_url' AS favicon_url,
                    (to_jsonb(cadu_planner_portals)->>'monthly_visits')::BIGINT AS monthly_visits,
                    (to_jsonb(cadu_planner_portals)->>'avg_time_seconds')::INTEGER AS avg_time_seconds,
                    to_jsonb(cadu_planner_portals)->>'metrics_period' AS metrics_period,
                    to_jsonb(cadu_planner_portals)->>'metrics_source_url' AS metrics_source_url,
                    to_jsonb(cadu_planner_portals)->>'ads_txt_status' AS ads_txt_status,
                    to_jsonb(cadu_planner_portals)->>'ads_txt_checked_at' AS ads_txt_checked_at,
                    (to_jsonb(cadu_planner_portals)->>'ads_txt_records')::INTEGER AS ads_txt_records,
                    COALESCE(to_jsonb(cadu_planner_portals)->'ads_txt_sellers', '[]'::jsonb) AS ads_txt_sellers,
                    to_jsonb(cadu_planner_portals)->>'programmatic_status' AS programmatic_status,
                    COALESCE(to_jsonb(cadu_planner_portals)->'programmatic_signals', '[]'::jsonb) AS programmatic_signals,
                    (to_jsonb(cadu_planner_portals)->>'popularity_rank')::INTEGER AS popularity_rank,
                    to_jsonb(cadu_planner_portals)->>'popularity_source' AS popularity_source,
                    to_jsonb(cadu_planner_portals)->>'traffic_tier' AS traffic_tier,
                    to_jsonb(cadu_planner_portals)->'demographics' AS demographics,
                    to_jsonb(cadu_planner_portals)->'ad_formats' AS ad_formats,
                    to_jsonb(cadu_planner_portals)->'site_sections' AS site_sections,
                    to_jsonb(cadu_planner_portals)->>'signals_checked_at' AS signals_checked_at"""
# Columns added by the programmatic migration are read through to_jsonb so a
# rolling deployment keeps working before that migration reaches the database.

SCOPES = {'nacional_premium', 'regional'}
# Editorial Top 10 of national portals (curated, not measured); `featured_rank` 1..10 marks it in the showcase.
TOP_PORTAL_DOMAINS = ('g1.globo.com', 'uol.com.br', 'oglobo.globo.com', 'folha.uol.com.br', 'estadao.com.br',
                      'cnnbrasil.com.br', 'r7.com', 'metropoles.com', 'terra.com.br', 'ge.globo.com')
TOP_FILTER = 'top10'
# Editorial profile of the Top 10: a commercial pitch without audience numbers, and the main sections of each portal.
TOP_PROFILES = {
    'g1.globo.com': ('Portal de notícias da Globo, com cobertura nacional e regional em tempo real, forte em política, economia, esportes e eleições, e vídeo ao vivo.',
                     ['Política', 'Economia', 'Mundo', 'Educação', 'Ciência e Saúde', 'Tecnologia', 'Pop & Arte', 'Esportes', 'Meio Ambiente', 'Carros', 'Turismo e Viagem', 'Agro']),
    'uol.com.br': ('Um dos maiores portais do Brasil: notícias, esporte, entretenimento, e-mail, vídeo e serviços em um só lugar, com marcas próprias como UOL Mail, Splash, Universa e Ecoa.',
                   ['Notícias', 'Esporte', 'Entretenimento', 'Economia', 'TV e Famosos', 'Tecnologia', 'Universa', 'Ecoa', 'Nossa', 'Viagem', 'Carros', 'UOL Mail']),
    'oglobo.globo.com': ('Jornal carioca de circulação nacional, com cobertura de política, economia, cidade do Rio e opinião, além de newsletters, podcasts e conteúdo de marca.',
                         ['Política', 'Economia', 'Brasil', 'Mundo', 'Rio', 'Esportes', 'Cultura', 'Sociedade', 'Ciência', 'Saúde', 'Opinião', 'Podcasts']),
    'folha.uol.com.br': ('Jornal paulistano de alcance nacional, conhecido pelo jornalismo analítico e pelas colunas de opinião, com forte cobertura de política, mercado e cotidiano.',
                         ['Poder', 'Mercado', 'Cotidiano', 'Mundo', 'Esporte', 'Ilustrada', 'Opinião', 'Tec', 'Ciência', 'Saúde', 'Educação', 'Ambiente']),
    'estadao.com.br': ('Um dos jornais mais tradicionais do país, de São Paulo, com cobertura de política, economia, cultura e marcas próprias como Paladar, Jornal do Carro e E-Investidor.',
                       ['Política', 'Economia', 'Internacional', 'Brasil', 'Esportes', 'Cultura', 'Saúde', 'Educação', 'Opinião', 'Paladar', 'Jornal do Carro', 'E-Investidor']),
    'cnnbrasil.com.br': ('Canal de notícias 24 horas, com transmissão ao vivo e cobertura de política, economia, internacional e esportes em vídeo e texto.',
                         ['Política', 'Nacional', 'Economia', 'Internacional', 'Pop', 'Esportes', 'Saúde', 'Tecnologia', 'Viagem & Gastronomia', 'Auto', 'Comportamento', 'Ao Vivo']),
    'r7.com': ('Portal do grupo Record, com notícias, esportes, entretenimento e vídeos, ligado à programação da emissora de TV.',
               ['Notícias', 'Esportes', 'Entretenimento', 'Economia', 'Vídeos', 'Tecnologia e Ciência', 'Saúde', 'Educação', 'Carros', 'Record']),
    'metropoles.com': ('Portal de notícias nascido em Brasília, com forte cobertura da política do Distrito Federal e do país, e colunas de opinião assinadas.',
                       ['Distrito Federal', 'Política', 'Brasil', 'Mundo', 'Esportes', 'Celebridades', 'Saúde', 'Tecnologia', 'Vida & Estilo', 'Dinheiro & Negócios', 'Colunas e blogs']),
    'terra.com.br': ('Portal de notícias, serviços e entretenimento, com esportes, vida e estilo, tecnologia, horóscopo e receitas.',
                     ['Notícias', 'Esportes', 'Futebol', 'Entretenimento', 'Economia', 'Vida e Estilo', 'Horóscopo', 'Receitas', 'Tecnologia', 'Planeta', 'Educação']),
    'ge.globo.com': ('Portal esportivo da Globo, com cobertura diária de futebol, campeonatos nacionais e estaduais, seleção brasileira e outras modalidades.',
                     ['Futebol', 'Brasileirão', 'Copa do Brasil', 'Libertadores', 'Seleção', 'Futebol internacional', 'Basquete', 'Vôlei', 'Automobilismo', 'Olimpíadas', 'Tênis', 'MMA']),
}
TOP_UF_FILTER = 'top10_uf'
TOP_UF_SIZE = 10
# Top 10 of each state among regional portals ranked on their own domain (a rank inherited from youtube.com or
# wordpress.com says nothing about the portal); lower rank = more popular.
TOP_UF_IDS_SQL = """SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (PARTITION BY to_jsonb(p)->>'uf' ORDER BY popularity_rank ASC, name ASC) AS position
          FROM cadu_planner_portals p
         WHERE active = TRUE AND to_jsonb(p)->>'scope' = 'regional' AND to_jsonb(p)->>'uf' IS NOT NULL
           AND popularity_rank IS NOT NULL AND popularity_source = 'tranco') ranked
    WHERE position <= %s"""
ADS_TXT_FILTERS = {'valid': ('valid',), 'partial': ('partial',), 'missing': ('missing', 'empty', 'invalid'),
                   'unchecked': (None,)}
PROGRAMMATIC_FILTERS = {'any': ('detected', 'ads_txt_declared'), 'detected': ('detected',),
                        'declared': ('ads_txt_declared',), 'adsense_native': ('adsense_native',),
                        'not_detected': ('not_detected',), 'unchecked': (None,)}
SORTS = {
    'featured': 'featured_rank ASC NULLS LAST, name ASC',
    'name': 'name ASC',
    'visits': "(to_jsonb(cadu_planner_portals)->>'monthly_visits')::BIGINT DESC NULLS LAST, name ASC",
}


def _filters(query, category, scope, uf, ads_txt, programmatic):
    """Shared WHERE builder; `category` may hold several comma-separated groups."""
    q = str(query or '').strip()[:120]
    categories = [item.strip()[:80] for item in str(category or '').split(',') if item.strip()][:30]
    where, params = ['active = TRUE'], []
    if q:
        where.append("(name ILIKE %s OR domain ILIKE %s OR category ILIKE %s OR description ILIKE %s)")
        params.extend([f'%{q}%'] * 4)
    if categories:
        where.append('category = ANY(%s)')
        params.append(categories)
    if scope == TOP_FILTER:
        where.append('featured_rank BETWEEN 1 AND %s')
        params.append(len(TOP_PORTAL_DOMAINS))
    elif scope == TOP_UF_FILTER:
        where.append(f'id IN ({TOP_UF_IDS_SQL})')
        params.append(TOP_UF_SIZE)
    elif scope:
        if scope not in SCOPES:
            raise BadRequest('Escopo inválido.')
        where.append("COALESCE(to_jsonb(cadu_planner_portals)->>'scope', 'regional') = %s")
        params.append(scope)
    ufs = [item.strip().upper() for item in str(uf or '').split(',') if item.strip()][:27]
    if ufs:
        if any(not re.fullmatch(r'[A-Z]{2}', item) for item in ufs):
            raise BadRequest('UF inválida.')
        where.append("to_jsonb(cadu_planner_portals)->>'uf' = ANY(%s)")
        params.append(ufs)
    for value, mapping, column in ((ads_txt, ADS_TXT_FILTERS, 'ads_txt_status'),
                                   (programmatic, PROGRAMMATIC_FILTERS, 'programmatic_status')):
        if not value:
            continue
        if value not in mapping:
            raise BadRequest('Filtro de verificação inválido.')
        statuses = mapping[value]
        if statuses == (None,):
            where.append(f"to_jsonb(cadu_planner_portals)->>'{column}' IS NULL")
        else:
            where.append(f"to_jsonb(cadu_planner_portals)->>'{column}' = ANY(%s)")
            params.append(list(statuses))
    return ' AND '.join(where), params


THUMBS_DIR = Path(__file__).resolve().parents[1] / 'static' / 'images' / 'portais' / 'thumbs'


def attach_thumbs(portals):
    """Illustrated 3D cover of the portal (static/images/portais/thumbs/{id}.webp) when one was generated."""
    try:
        available = {name[:-5] for name in os.listdir(THUMBS_DIR) if name.endswith('.webp')}
    except OSError:
        available = set()
    for row in portals:
        row['thumb_url'] = f"/static/images/portais/thumbs/{row['id']}.webp" if str(row.get('id')) in available else ''
    return portals


def attach_prints(portals, all_kinds=False):
    """Approved real screenshots per portal (newest first). Missing table or no print is never an error."""
    from ..cadu_family import repository
    ids = [row['id'] for row in portals if row.get('id')]
    for row in portals:
        row['prints'] = []
        row['print_url'] = ''
    if not ids:
        return portals
    try:
        found = repository.rows("""SELECT portal_id, kind, file_path, source_url, captured_at
                                     FROM cadu_planner_portal_prints
                                    WHERE portal_id = ANY(%s) AND status = 'aprovado'
                                 ORDER BY captured_at DESC""", (ids,))
    except Exception:
        return portals
    by_portal = {}
    for item in found:
        by_portal.setdefault(item['portal_id'], []).append({
            'kind': item['kind'], 'url': '/static/' + str(item['file_path']).lstrip('/'),
            'source_url': item['source_url'], 'captured_at': item['captured_at']})
    for row in portals:
        shots = by_portal.get(row['id'], [])
        row['prints'] = shots if all_kinds else shots[:1]
        row['print_url'] = next((shot['url'] for shot in shots if shot['kind'] == 'home'), '')
    return portals


def catalog(query='', category='', sort='featured', limit=50, offset=0,
            scope='', uf='', ads_txt='', programmatic=''):
    """Return a bounded, server-paged portal catalog; audience is source-backed only."""
    from ..cadu_family import repository
    try:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        raise BadRequest('Paginação inválida.')
    clause, params = _filters(query, category, scope, uf, ads_txt, programmatic)
    order = SORTS.get(sort, SORTS['featured'])
    if scope == TOP_UF_FILTER:
        order = "to_jsonb(cadu_planner_portals)->>'uf' ASC, popularity_rank ASC, name ASC"
    total = repository.rows(f'SELECT COUNT(*) AS total FROM cadu_planner_portals WHERE {clause}', tuple(params))[0]['total']
    rows = repository.rows(f'''SELECT {PORTAL_COLUMNS} FROM cadu_planner_portals WHERE {clause}
                                ORDER BY {order} LIMIT %s OFFSET %s''', tuple(params + [limit, offset]))
    for row in rows:
        row['public_attributes'] = row.get('public_attributes') or []
    top_uf = {row['id'] for row in repository.rows(TOP_UF_IDS_SQL, (TOP_UF_SIZE,))}
    for row in rows:
        row['uf_top'] = row['id'] in top_uf
    attach_thumbs(rows)
    return {'records': rows, 'total': total, 'limit': limit, 'offset': offset}


def catalog_ids(query='', category='', scope='', uf='', ads_txt='', programmatic='', limit=500):
    """Ids of every portal matching the filters, so a whole group can be selected at once."""
    from ..cadu_family import repository
    clause, params = _filters(query, category, scope, uf, ads_txt, programmatic)
    rows = repository.rows(f'SELECT id FROM cadu_planner_portals WHERE {clause} ORDER BY name ASC LIMIT %s',
                           tuple(params + [max(1, min(int(limit), 1000))]))
    return [row['id'] for row in rows]


def records(portal_ids):
    """Active portals by id in one query (bulk selection snapshots)."""
    from ..cadu_family import repository
    ids = []
    for value in portal_ids:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            raise BadRequest('Identificador de portal inválido.')
    if not ids:
        return []
    return repository.rows(f'SELECT {PORTAL_COLUMNS} FROM cadu_planner_portals WHERE id = ANY(%s) AND active = TRUE', (ids,))


def catalog_facets():
    from ..cadu_family import repository
    rows = repository.rows('''SELECT DISTINCT category FROM cadu_planner_portals
                               WHERE active = TRUE AND category IS NOT NULL ORDER BY category''')
    ufs = repository.rows("""SELECT DISTINCT to_jsonb(cadu_planner_portals)->>'uf' AS uf FROM cadu_planner_portals
                              WHERE active = TRUE AND to_jsonb(cadu_planner_portals)->>'uf' IS NOT NULL ORDER BY 1""")
    return {'categories': [row['category'] for row in rows], 'ufs': [row['uf'] for row in ufs]}


# Portals with formats of their own in the Formatos catalog (plataforma_slug), and how the page reader names map to IAB formats.
PORTAL_FORMAT_PLATFORM = {'g1.globo.com': 'g1', 'cnnbrasil.com.br': 'cnn', 'infomoney.com.br': 'infomoney'}
OBSERVED_TO_IAB = {'Vídeo in-stream (VAST/IMA)': 'pre-roll-vast', 'Nativo (recomendação)': 'native-content-recommendation',
                   'Vídeo outstream / in-read': 'outstream-video', 'Interstitial / tela cheia': 'interstitial-web',
                   'Sticky / rodapé fixo': 'adhesion-banner-sticky-bottom'}
MARKET_STANDARD = ('leaderboard-728x90', 'medium-rectangle-300x250', 'billboard-970x250', 'half-page-300x600',
                   'smartphone-banner-320x50', 'native-in-feed', 'pre-roll-vast', 'outstream-video')


def attach_formats(portal):
    """Formats of the portal in three groups taken from the Formatos catalog: its own, the ones seen on its home, the market standard."""
    from ..cadu_family import repository
    columns = 'id, slug, nome, tipo, dimensoes'
    rows_by_slug = {row['slug']: row for row in repository.rows(
        f"SELECT {columns} FROM cadu_formatos WHERE is_active IS TRUE AND plataforma_slug = 'programatica_iab'")}
    by_size = {}
    for row in rows_by_slug.values():
        match = re.search(r'(\d{2,4})x(\d{2,4})', str(row['nome']) + ' ' + str(row['dimensoes']))
        if match:
            by_size.setdefault(match.group(0), row)
    own = []
    platform = PORTAL_FORMAT_PLATFORM.get(str(portal.get('domain') or ''))
    if platform:
        own = repository.rows(f"SELECT {columns} FROM cadu_formatos WHERE is_active IS TRUE AND plataforma_slug = %s ORDER BY ordem", (platform,))
    observed, seen = [], set()
    for item in portal.get('ad_formats') or []:
        match = by_size.get(item.get('size') or '') if item.get('size') else rows_by_slug.get(OBSERVED_TO_IAB.get(item.get('format'), ''))
        label = item.get('format')
        key = match['id'] if match else label
        if key in seen:
            continue
        seen.add(key)
        observed.append({**(match or {}), 'label': label, 'size': item.get('size'), 'linked': bool(match)})
    taken = {row['id'] for row in own} | {row.get('id') for row in observed if row.get('id')}
    market = [rows_by_slug[slug] for slug in MARKET_STANDARD if slug in rows_by_slug and rows_by_slug[slug]['id'] not in taken][:6]
    portal['formats'] = {'own': own, 'observed': observed, 'market': market}
    return portal


def detail(portal_id):
    from ..cadu_family import repository
    try:
        portal_id = int(portal_id)
    except (TypeError, ValueError):
        raise BadRequest('Identificador de portal inválido.')
    rows = repository.rows(f'SELECT {PORTAL_COLUMNS} FROM cadu_planner_portals WHERE id = %s AND active = TRUE', (portal_id,))
    if not rows:
        from werkzeug.exceptions import NotFound
        raise NotFound('Portal indisponível.')
    from .portal_examples import attach_examples
    attach_examples(rows)
    attach_thumbs(rows)
    attach_formats(rows[0])
    rows[0]['formats'].pop('market', None)  # market defaults are not evidence about this portal
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


def _scope_and_metrics(row, line, attributes):
    """Optional scope/UF/metrics columns; UF falls back to the Atlas `localizacao` attribute."""
    scope = str(row.get('scope') or '').strip() or None
    if scope is not None and scope not in SCOPES:
        raise BadRequest(f'Linha {line}: scope deve ser nacional_premium ou regional.')
    uf = str(row.get('uf') or '').strip().upper() or None
    if uf is None:
        for entry in attributes:
            parts = str(entry.get('valor') or '').split(' · ') if isinstance(entry, dict) and entry.get('atributo') == 'localizacao' else []
            if len(parts) >= 2 and re.fullmatch(r'[A-Z]{2}', parts[1].strip()):
                uf = parts[1].strip()
    if uf is not None and not re.fullmatch(r'[A-Z]{2}', uf):
        raise BadRequest(f'Linha {line}: uf inválida.')
    values = {}
    for key in ('monthly_visits', 'avg_time_seconds'):
        raw = str(row.get(key) or '').strip()
        try:
            values[key] = int(raw) if raw else None
        except ValueError as exc:
            raise BadRequest(f'Linha {line}: {key} deve ser um inteiro.') from exc
        if values[key] is not None and values[key] < 0:
            raise BadRequest(f'Linha {line}: {key} não pode ser negativo.')
    source, period, checked_at = str(row.get('metrics_source_url') or '').strip(), str(row.get('metrics_period') or '').strip(), None
    if any(v is not None for v in values.values()):
        checked = str(row.get('metrics_checked_at') or '').strip()
        if not source or not checked:
            raise BadRequest(f'Linha {line}: métricas exigem metrics_source_url e metrics_checked_at.')
        source = validate_source_url(source)
        try:
            checked_at = datetime.fromisoformat(checked.replace('Z', '+00:00'))
        except ValueError as exc:
            raise BadRequest(f'Linha {line}: metrics_checked_at deve ser ISO-8601.') from exc
        if checked_at.tzinfo is None:
            raise BadRequest(f'Linha {line}: metrics_checked_at deve incluir fuso horário.')
    else:
        source = period = None
    return {'scope': scope, 'uf': uf, 'metrics_period': period, 'metrics_source': source,
            'metrics_checked_at': checked_at, **values}


def _validate_row(row, line, seen_domains, allow_pending, check_dns=False):
    name = str(row.get('name') or '').strip()
    domain = str(row.get('domain') or '').strip().lower().rstrip('.')
    category = str(row.get('category') or '').strip()
    if not name or not category or not re.fullmatch(r'[a-z0-9.-]{1,255}', domain):
        raise BadRequest(f'Linha {line}: nome, domínio ou categoria inválidos.')
    if domain.startswith('.') or domain.endswith('.') or '..' in domain or '/' in domain:
        raise BadRequest(f'Linha {line}: domínio inválido.')
    if domain in seen_domains:
        raise BadRequest(f'Linha {line}: domínio duplicado no CSV ({domain}).')
    if check_dns:
        from .portal_ads import domain_resolves
        if not domain_resolves(domain):
            raise BadRequest(f'Linha {line}: o domínio {domain} não resolve (DNS inválido).')
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
    if review != 'aprovado' and not allow_pending:
        raise BadRequest(f'Linha {line}: o registro ainda não foi aprovado pela curadoria editorial.')
    rank = str(row.get('featured_rank') or '').strip()
    try:
        featured_rank = int(rank) if rank else None
    except ValueError as exc:
        raise BadRequest(f'Linha {line}: featured_rank deve ser um número de 1 a 200.') from exc
    if featured_rank is not None and not 1 <= featured_rank <= 200:
        raise BadRequest(f'Linha {line}: featured_rank deve ser um número de 1 a 200.')

    return {
        'name': name[:180], 'domain': domain, 'category': category[:80],
        'description': str(row.get('description') or '').strip(),
        'audience': audience, 'period': period, 'source': source,
        'checked_at': checked_at, 'attributes': json.dumps(attributes, ensure_ascii=False),
        'featured_rank': featured_rank, 'approved': review == 'aprovado', **_scope_and_metrics(row, line, attributes),
    }


def import_curated_csv(file_obj, dry_run=False, allow_pending=False, check_dns=False):
    """Validate and import reviewed portal records from a UTF-8 CSV file.

    Audience figures require a public HTTPS source, a reporting period and an
    explicit observation date. Blank audience values never overwrite evidence.
    `allow_pending` also accepts candidates still awaiting editorial review (they
    keep their `status_curadoria` attribute); invalid rows are then skipped and
    reported instead of aborting the whole file. Optional columns: scope
    (nacional_premium|regional), uf, monthly_visits, avg_time_seconds,
    metrics_period, metrics_source_url, metrics_checked_at -- metrics need a source.
    `check_dns` rejects rows whose domain does not resolve (checked twice).
    """
    reader = csv.DictReader(file_obj)
    required = {'name', 'domain', 'category'}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise BadRequest('CSV precisa conter as colunas name, domain e category.')

    validated, skipped = [], []
    seen_domains = set()
    for line, row in enumerate(reader, start=2):
        try:
            item = _validate_row(row, line, seen_domains, allow_pending, check_dns)
        except BadRequest as exc:
            if not allow_pending:
                raise
            skipped.append(str(exc.description))
            continue
        validated.append(item)
    if not dry_run and validated:
        from ..db import get_db
        conn = get_db()
        try:
            with conn.cursor() as cur:
                for item in validated:
                    cur.execute('''INSERT INTO cadu_planner_portals
                        (name, domain, category, description, audience_estimate,
                         audience_period, audience_source_url, audience_checked_at,
                         public_attributes, featured_rank, scope, uf, monthly_visits,
                         avg_time_seconds, metrics_period, metrics_source_url, metrics_checked_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s,
                                COALESCE(%s, 'regional'), %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (domain) DO UPDATE SET
                          name = CASE WHEN cadu_planner_portals.scope = 'nacional_premium' AND %s::text IS DISTINCT FROM 'nacional_premium'
                                      THEN cadu_planner_portals.name ELSE EXCLUDED.name END,
                          category = CASE WHEN cadu_planner_portals.scope = 'nacional_premium' AND %s::text IS DISTINCT FROM 'nacional_premium'
                                          THEN cadu_planner_portals.category ELSE EXCLUDED.category END,
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
                          scope = CASE WHEN %s::text IS NULL THEN cadu_planner_portals.scope ELSE EXCLUDED.scope END,
                          uf = COALESCE(EXCLUDED.uf, cadu_planner_portals.uf),
                          monthly_visits = COALESCE(EXCLUDED.monthly_visits, cadu_planner_portals.monthly_visits),
                          avg_time_seconds = COALESCE(EXCLUDED.avg_time_seconds, cadu_planner_portals.avg_time_seconds),
                          metrics_period = COALESCE(EXCLUDED.metrics_period, cadu_planner_portals.metrics_period),
                          metrics_source_url = COALESCE(EXCLUDED.metrics_source_url, cadu_planner_portals.metrics_source_url),
                          metrics_checked_at = COALESCE(EXCLUDED.metrics_checked_at, cadu_planner_portals.metrics_checked_at),
                          active = TRUE, updated_at = NOW()
                        WHERE NOT ((cadu_planner_portals.scope = 'nacional_premium'
                                    OR cadu_planner_portals.public_attributes @> '[{"atributo": "status_curadoria", "valor": "aprovado"}]'::jsonb)
                                   AND %s::text IS DISTINCT FROM 'nacional_premium' AND NOT %s::boolean)''',
                        (item['name'], item['domain'], item['category'], item['description'],
                         item['audience'], item['period'], item['source'], item['checked_at'],
                         item['attributes'], item['featured_rank'], item['scope'], item['uf'],
                         item['monthly_visits'], item['avg_time_seconds'], item['metrics_period'],
                         item['metrics_source'], item['metrics_checked_at'],
                         item['scope'], item['scope'], item['scope'], item['scope'], item['approved']))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {'rows': len(validated), 'dry_run': bool(dry_run), 'skipped': skipped}


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


def crawl_public_metadata(domain, timeout=12, page_url=None):
    """Fetch one public HTTPS page when robots.txt allows it; one host per call."""
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
    target = str(page_url or base).strip()
    parsed_target = urlparse(target)
    if (parsed_target.scheme != 'https' or parsed_target.hostname != host
            or parsed_target.username or parsed_target.password or parsed_target.port not in (None, 443)):
        raise BadRequest('A página precisa pertencer ao domínio HTTPS informado.')
    agent = 'CaduPlannerCatalogBot/1.0 (+https://cadu.ai/crawler)'
    opener = build_opener(_SameHostHttpsRedirect(host))
    robots_url = urljoin(base, '/robots.txt')
    try:
        robots_request = Request(robots_url, headers={'User-Agent': agent})
        with opener.open(robots_request, timeout=timeout) as response:
            robots_body = response.read(256_000).decode('utf-8', 'replace')
        parser = RobotFileParser(robots_url)
        parser.parse(robots_body.splitlines())
        if not parser.can_fetch(agent, target):
            return {'domain': host, 'status': 'robots_disallowed'}
    except HTTPError as error:
        if error.code not in (404, 410):
            return {'domain': host, 'status': 'robots_unavailable'}
    except (URLError, TimeoutError, OSError):
        return {'domain': host, 'status': 'robots_unavailable'}
    try:
        request = Request(target, headers={'User-Agent': agent, 'Accept': 'text/html'})
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
            cur.execute('''SELECT COUNT(*) = 2 AS available
                             FROM information_schema.columns
                            WHERE table_schema = current_schema()
                              AND table_name = 'cadu_planner_portals'
                              AND column_name IN ('discovered_pages_count', 'crawl_updates_count')''')
            stats_available = cur.fetchone()['available']
            if stats_available:
                cur.execute('''UPDATE cadu_planner_portals
                                  SET description = COALESCE(NULLIF(%s, ''), description),
                                      source_url = %s, source_hash = %s,
                                      last_crawled_at = %s,
                                      discovered_pages_count = %s,
                                      crawl_updates_count = crawl_updates_count + 1,
                                      updated_at = NOW()
                                WHERE domain = %s''', (result.get('description', ''), result['source_url'],
                                                       result['source_hash'], result['collected_at'],
                                                       min(200, len(set(result.get('public_links') or [])) + 1),
                                                       result['domain']))
            else:
                # Keep pages and crawls working during a rolling deployment;
                # counters begin once the additive migration reaches this DB.
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


def apply_top_profiles():
    """Write the curated description and sections of the Top 10 and of the next curated portals (their catalog text is generic)."""
    from psycopg.types.json import Json
    from ..db import get_db
    conn = get_db()
    try:
        with conn.cursor() as cur:
            from .portal_profiles import PROFILES
            for domain, (description, sections) in {**PROFILES, **TOP_PROFILES}.items():
                cur.execute('UPDATE cadu_planner_portals SET description = %s, site_sections = %s WHERE domain = %s AND active = TRUE',
                            (description, Json(sections), domain))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def apply_top_ranking():
    """Write featured_rank 1..N for TOP_PORTAL_DOMAINS (in that order) and clear stale ranks in that range."""
    from ..db import get_db
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE cadu_planner_portals SET featured_rank = NULL WHERE featured_rank BETWEEN 1 AND %s '
                        'AND domain <> ALL(%s)', (len(TOP_PORTAL_DOMAINS), list(TOP_PORTAL_DOMAINS)))
            applied = []
            for rank, domain in enumerate(TOP_PORTAL_DOMAINS, start=1):
                cur.execute('UPDATE cadu_planner_portals SET featured_rank = %s WHERE domain = %s AND active = TRUE', (rank, domain))
                if cur.rowcount:
                    applied.append(domain)
        conn.commit()
        return applied
    except Exception:
        conn.rollback()
        raise
