"""Safe, bounded link analysis owned by the Reports Link Tester.

The reports share network evidence but never share a score: destination answers
whether an ad click arrives, media answers whether it can be measured and
converted, and agentic answers whether a domain is legible to AI.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import ssl
import logging
import uuid
from pathlib import Path
from html import unescape
from time import monotonic
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from . import reports_ai
from werkzeug.exceptions import BadRequest, HTTPException

logger = logging.getLogger(__name__)

MAX_REDIRECTS, TIMEOUT_SECONDS, MAX_HTML_BYTES = 5, 8, 1_000_000
MODES = {'destination', 'media', 'agentic'}
USER_AGENT = 'Cadu-Reports-LinkTester/2.0'


def _url(value):
    raw = str(value or '').strip()
    if len(raw) > 2048:
        raise BadRequest('O link pode ter no máximo 2.048 caracteres.')
    if '://' not in raw:
        raw = 'https://' + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise BadRequest('Informe uma URL HTTP ou HTTPS pública e completa.')
    return parsed


def _public_host(parsed):
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        raise BadRequest('Não foi possível localizar o domínio informado.')
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise BadRequest('O Link Tester aceita apenas destinos públicos.')


def _read_body(response, accepted_types=('html', 'text/', 'xml', 'json')):
    content_type = response.headers.get('Content-Type', '').lower()
    if not any(token in content_type for token in accepted_types):
        return ''
    chunks, total = [], 0
    for chunk in response.iter_content(32768):
        total += len(chunk)
        if total > MAX_HTML_BYTES:
            break
        chunks.append(chunk)
    return b''.join(chunks).decode(response.encoding or 'utf-8', errors='replace')


def _fetch(url, body=False, accepted_types=('html', 'text/', 'xml', 'json')):
    parsed = _url(url)
    _public_host(parsed)
    response = requests.get(parsed.geturl(), allow_redirects=False, stream=True, timeout=TIMEOUT_SECONDS,
                            headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'})
    try:
        return response.status_code, dict(response.headers), _read_body(response, accepted_types) if body else ''
    finally:
        response.close()


def _title(html):
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
    return re.sub(r'\s+', ' ', unescape(match.group(1))).strip() if match else None


def _meta(html, name):
    pattern = rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)'
    match = re.search(pattern, html, re.I)
    return unescape(match.group(1)).strip() if match else None


def _certificate(parsed):
    if parsed.scheme != 'https':
        return {'valid': False, 'message': 'O destino final não usa HTTPS.'}
    try:
        context = ssl.create_default_context()
        with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=TIMEOUT_SECONDS) as raw:
            with context.wrap_socket(raw, server_hostname=parsed.hostname) as wrapped:
                cert = wrapped.getpeercert()
        issuer = ', '.join('='.join(item) for group in cert.get('issuer', ()) for item in group)
        return {'valid': True, 'expires_at': cert.get('notAfter'), 'issuer': issuer or None}
    except (OSError, ssl.SSLError) as error:
        return {'valid': False, 'message': str(error)}


def _rendered_page(url, actor=None):
    """Rendered DOM and screenshot from Firecrawl (one scrape, billed to the client). Never mandatory: on any failure the
    analysis goes on with the plain HTTP evidence and says why the screenshot is missing."""
    empty = {'html': '', 'screenshot': None, 'source': 'http'}
    if actor is None:
        return {**empty, 'error': 'Print não gerado: análise sem cliente e usuário para cobrar a captura.'}
    try:
        from ..crm_v3_web_scout import _firecrawl_scrape
        data = reports_ai.firecrawl_scrape('link_tester_render', url, call=_firecrawl_scrape, actor=actor,
                                           formats=['rawHtml', 'screenshot'], timeout_s=30,
                                           location={'country': 'BR', 'languages': ['pt-BR', 'pt']})
    except HTTPException as error:  # 409: no token balance or no price in the client's plan
        return {**empty, 'error': f'Print não gerado: {error.description}'}
    except Exception as error:
        logger.warning('Firecrawl falhou no Link Tester para %s: %s', url, error)
        return {**empty, 'error': 'Print não gerado: o serviço de captura não respondeu.'}
    screenshot = data.get('screenshot')
    if isinstance(screenshot, dict):
        screenshot = screenshot.get('url') or screenshot.get('imageUrl')
    # rawHtml keeps <script> tags (GTM, pixels, Super Tag); Firecrawl's cleaned "html" drops them.
    return {'html': str(data.get('rawHtml') or data.get('html') or ''), 'screenshot': screenshot if isinstance(screenshot, str) else None,
            'source': 'rendered', 'error': None if screenshot else 'Print não gerado: a captura voltou sem imagem.'}


def _common(payload, mode, actor=None):
    original = _url(payload.get('url'))
    current, chain, html, final_headers = original.geturl(), [], '', {}
    started = monotonic()
    try:
        for _ in range(MAX_REDIRECTS + 1):
            status, headers, possible_html = _fetch(current, body=True, accepted_types=('html',))
            chain.append({'url': current, 'status': status})
            location = headers.get('Location') or headers.get('location')
            if 300 <= status < 400 and location:
                current = urljoin(current, location)
                continue
            html, final_headers = possible_html, headers
            break
        else:
            raise BadRequest('O link excede o limite de redirecionamentos.')
    except requests.RequestException:
        raise BadRequest('Não foi possível acessar este destino agora.')
    final = _url(current)
    elapsed_ms = round((monotonic() - started) * 1000)  # the site's own response time, before any rendering
    # Every analysis ships a screenshot; the rendered DOM only replaces the raw HTML for tag detection (media).
    rendered = _rendered_page(final.geturl(), actor)
    raw_html = html
    if rendered['html'] and mode != 'agentic':
        html = rendered['html']
    return {'original_url': original.geturl(), 'final_url': final.geturl(), 'final_parsed': final,
            'status': status, 'reachable': status < 400, 'elapsed_ms': elapsed_ms,
            'redirects': chain, 'html': html, 'raw_html': raw_html, 'rendered_html': rendered['html'], 'headers': final_headers,
            'capture': {'source': rendered['source'], 'screenshot': rendered['screenshot'], 'error': rendered.get('error')}}


def _destination(common):
    original, final = _url(common['original_url']), common['final_parsed']
    capture = common.get('capture') or {}
    query = parse_qs(original.query, keep_blank_values=True)
    utms = {key: values for key, values in query.items() if key.lower().startswith('utm_')}
    alerts = []
    if not utms:
        alerts.append('Sem parâmetros UTM no link informado.')
    if any(not value or not value[0].strip() for value in utms.values()):
        alerts.append('Há parâmetros UTM sem valor.')
    if common['status'] >= 400:
        alerts.append('O destino respondeu com erro.')
    cert = _certificate(final)
    if not cert['valid']:
        alerts.append('O certificado HTTPS não pôde ser validado.')
    score = 100 - (45 if common['status'] >= 400 else 0) - min(20, max(0, len(common['redirects']) - 1) * 7)
    score -= 15 if not cert['valid'] else 0
    score -= 10 if not utms else 0
    return {'kind': 'destination', 'score': max(0, score), 'status_label': 'Pronto' if score >= 85 else 'Atenção' if score >= 55 else 'Bloqueado',
            'summary': 'O clique chega ao destino.' if score >= 85 else 'Há pendências antes de publicar a mídia.',
            'evidence': {'url': common['original_url'], 'final_url': common['final_url'], 'http_status': common['status'],
                         'elapsed_ms': common['elapsed_ms'], 'redirects': common['redirects'], 'utm': utms,
                         'ssl': cert, 'title': _title(common['html']), 'description': _meta(common['html'], 'description'),
                         'og_image': _meta(common['html'], 'og:image'), 'screenshot': capture.get('screenshot')}, 'alerts': alerts}


def _platforms(tags):
    found = {tag['name'] for tag in tags if tag['detected']}
    requirements = {'Cadu Reports': {'Cadu Super Tag'}, 'Google': {'GTM', 'GA4', 'Google Ads'}, 'Meta': {'Meta Pixel'}, 'TikTok': {'TikTok Pixel'}, 'LinkedIn': {'LinkedIn Insight'}}
    return [{'name': name, 'detected': sorted(found & required), 'missing': sorted(required - found),
             'score': round(len(found & required) * 100 / len(required))} for name, required in requirements.items()]


SUPERTAG_PATTERN = r'/supertag\.js|data-cadu-site|Cadu Super Tag|CaduSuperTag'
SUPERTAG_ID = re.compile(r"""data-cadu-site["']?\s*[=,]\s*["']([A-Za-z0-9_-]{6,40})|supertag\.js\?id=([A-Za-z0-9_-]{6,40})""")


def supertag_evidence(raw_html, rendered_html):
    """The Cadu Super Tag as an installed tag: where it was seen (page code, or only after GTM ran) and which site id it carries."""
    def ids(html):
        return sorted({next(group for group in match.groups() if group) for match in SUPERTAG_ID.finditer(html or '')})
    in_code = bool(re.search(SUPERTAG_PATTERN, raw_html or '', re.I))
    in_page = in_code or bool(re.search(SUPERTAG_PATTERN, rendered_html or '', re.I))
    return {'detected': in_page, 'via': 'code' if in_code else 'gtm' if in_page else None,
            'public_ids': ids(raw_html) or ids(rendered_html), 'registered': None, 'site_label': None, 'host_matches': None}


def _same_site(host, allowed_host):
    host, allowed = (host or '').lower().removeprefix('www.'), (allowed_host or '').lower().lstrip('.').removeprefix('www.')
    return bool(allowed) and (host == allowed or host.endswith('.' + allowed))


def _match_supertag(result, client_id, final_host):
    """Tie a detected Super Tag to the client's registered sites, and flag a registered site whose tag is missing."""
    supertag = (result.get('evidence') or {}).get('supertag')
    if supertag is None or not client_id:
        return
    try:
        from ..cadu_family import repository
        sites = repository.rows('''SELECT public_id,label,allowed_host FROM cadu_reports_supertag_sites
            WHERE client_id=%s AND enabled=TRUE AND revoked_at IS NULL''', (client_id,))
    except Exception:
        logger.info('Sites da Super Tag indisponíveis para o Link Tester.', exc_info=True)
        return
    same_host = [site for site in sites if _same_site(final_host, site['allowed_host'])]
    mine = [site for site in sites if site['public_id'] in supertag['public_ids']]
    if supertag['detected']:
        supertag.update(registered=bool(mine), site_label=mine[0]['label'] if mine else None,
                        host_matches=bool(mine) and _same_site(final_host, mine[0]['allowed_host']))
        if supertag['public_ids'] and not mine:
            result['alerts'].append('Há uma Super Tag na página, mas ela não pertence a um site ativo deste cliente.')
        elif mine and not supertag['host_matches']:
            result['alerts'].append(f'A Super Tag da página é do site "{mine[0]["label"]}", cadastrado para outro domínio.')
    elif same_host:
        supertag.update(registered=True, site_label=same_host[0]['label'])
        result['alerts'].append(f'A Super Tag de "{same_host[0]["label"]}" está cadastrada para este domínio, mas não foi encontrada na página.')


INVENTORY_TAGS = {'Google Tag Manager': 'GTM', 'Google Analytics 4': 'GA4', 'Google Ads': 'Google Ads', 'Meta Pixel': 'Meta Pixel',
                  'TikTok Pixel': 'TikTok Pixel', 'LinkedIn Insight': 'LinkedIn Insight', 'Microsoft Clarity': 'Microsoft Clarity',
                  'Cadu Super Tag': 'Cadu Super Tag'}


def _media(common):
    # Tags may sit in the delivered code or appear only after GTM runs: look at both.
    html = common['html'] + ('\n' + common['raw_html'] if common.get('raw_html') and common['raw_html'] != common['html'] else '')
    capture = common.get('capture') or {}
    definitions = {'GTM': r'googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]+', 'GA4': r'gtag\s*\(|G-[A-Z0-9]+',
                   'Google Ads': r'AW-[A-Z0-9]+|googleadservices\.com', 'Meta Pixel': r'fbq\s*\(|fbevents\.js',
                   'TikTok Pixel': r'ttq\.|analytics\.tiktok\.com', 'LinkedIn Insight': r'snap\.licdn\.com|_linkedin_partner_id',
                   'Microsoft Clarity': r'clarity\.ms', 'Cadu Super Tag': SUPERTAG_PATTERN}
    inventory = common.get('inventory')
    if inventory is not None:  # precise detection (IDs and script hosts) instead of loose patterns
        seen = {INVENTORY_TAGS.get(item['name']) for item in inventory['platforms']}
        tags = [{'name': name, 'detected': name in seen} for name in definitions]
    else:
        tags = [{'name': name, 'detected': bool(re.search(pattern, html, re.I))} for name, pattern in definitions.items()]
    supertag = supertag_evidence(common.get('raw_html') or html, html)
    whatsapp = bool(re.search(r'(?:wa\.me/|api\.whatsapp\.com|whatsapp:)', html, re.I))
    forms = len(re.findall(r'<form\b', html, re.I))
    phones = bool(re.search(r'href=["\']tel:', html, re.I))
    events = sorted(set(re.findall(r"(?:gtag\s*\(\s*['\"]event['\"]\s*,\s*|event\s*[:=]\s*['\"])([\w_-]+)", html, re.I)))
    if inventory is not None:
        events = sorted({name for names in inventory['events'].values() for name in names})
    consent = bool(re.search(r'cookie|consent|lgpd|privacidade|privacy', html, re.I))
    privacy = bool(re.search(r'(?:pol[ií]tica\s+de\s+privacidade|privacy\s+policy)', html, re.I))
    gaps = []
    if whatsapp and not any('whatsapp' in event.lower() for event in events): gaps.append('WhatsApp detectado sem evento específico.')
    if forms and not any('form' in event.lower() or 'lead' in event.lower() or 'submit' in event.lower() for event in events): gaps.append('Formulário detectado sem evento de conversão.')
    score = min(100, 20 + sum(tag['detected'] for tag in tags) * 12 + (15 if (whatsapp or forms) else 0) + (10 if events else 0) + (10 if consent else 0))
    return {'kind': 'media', 'score': score, 'status_label': 'Pronto para medir' if score >= 75 else 'Medição parcial' if score >= 45 else 'Sem base de medição',
            'summary': 'Tags, conversões e consentimento foram verificados separadamente do destino.',
            'evidence': {'tags': tags, 'supertag': supertag, 'conversion': {'whatsapp': whatsapp, 'forms': forms, 'phone': phones}, 'events': events,
                         'compliance': {'consent_detected': consent, 'privacy_policy_detected': privacy}, 'platforms': _platforms(tags),
                         'screenshot': capture.get('screenshot'), 'capture_source': capture.get('source', 'http')},
            'alerts': gaps + ([] if consent else ['Nenhum sinal de consentimento/cookies foi encontrado.'])}


def _agentic(common):
    from . import reports_link_agentic
    return reports_link_agentic.analyze(common)


def _save_run(client_id, actor_id, mode, result, run_id=None, public_token=None):
    """Persist one independent report without coupling the analyzer to history UI."""
    if not client_id or not actor_id:
        return None
    from psycopg.types.json import Json
    from ..db import get_db
    conn = get_db()
    run_id, public_token = run_id or str(uuid.uuid4()), public_token or str(uuid.uuid4())
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_reports_link_test_runs
                           (id, client_id, created_by, mode, original_url, final_url, score, status_label, result, public_token, shared_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())''',
                        (run_id, client_id, actor_id, mode, result['original_url'], result['final_url'], result['score'],
                         result['status_label'], Json(result), public_token))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {'id': run_id, 'public_token': public_token}


def public_result(token):
    """Read an unguessable, independently shared report without tenant context."""
    try:
        from ..cadu_family import repository
        rows = repository.rows('''SELECT mode, original_url, final_url, score, status_label, result, created_at
                                    FROM cadu_reports_link_test_runs
                                   WHERE public_token = %s AND revoked_at IS NULL''', (str(token),))
    except Exception:
        return None
    return rows[0] if rows else None


def history(client_id, limit=18):
    from ..cadu_family import repository
    return repository.rows('''SELECT id, mode, final_url, score, status_label, public_token, created_at,
                                      result->'evidence'->>'screenshot' AS screenshot
                                 FROM cadu_reports_link_test_runs
                                WHERE client_id = %s
                                ORDER BY created_at DESC LIMIT %s''', (client_id, limit))


def detail(client_id, run_id):
    from ..cadu_family import repository
    rows = repository.rows('''SELECT id, mode, original_url, final_url, score, status_label, result, public_token, created_at
                                FROM cadu_reports_link_test_runs
                               WHERE id = %s AND client_id = %s''', (str(run_id), client_id))
    return rows[0] if rows else None


def screenshot_path(token):
    from flask import current_app
    return Path(current_app.instance_path) / 'reports-link-tests' / f'{uuid.UUID(str(token))}.webp'


def _store_screenshot(token, remote_url):
    """Keep the provider's screenshot on our disk: its URL expires and the public page only allows same-origin images."""
    if not remote_url:
        return False
    try:
        from flask import current_app
        from .reports_page_captures import _download, process_image
        data, _, _ = process_image(_download(remote_url), 'desktop')
        target = screenshot_path(token)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return True
    except Exception:
        try:
            current_app.logger.warning('Print do Link Tester não pôde ser guardado.', exc_info=True)
        except Exception:
            pass
        return False


def _highlights(result):
    """Up to five preliminary findings for the e-mail and the public page: problems first, then what is already right."""
    evidence, points = result.get('evidence') or {}, []
    if result['kind'] == 'agentic':
        points += [{'tone': 'bad' if item['severity'] == 'critical' else 'warn', 'text': item['title']}
                   for item in evidence.get('findings', []) if item['severity'] in {'critical', 'warning'}]
        points += [{'tone': 'ok', 'text': item['title']} for item in evidence.get('findings', []) if item['severity'] == 'ok']
    else:
        points += [{'tone': 'warn', 'text': alert} for alert in result.get('alerts', [])]
        if result['kind'] == 'destination':
            if (evidence.get('http_status') or 500) < 400:
                points.append({'tone': 'ok', 'text': f'A página respondeu (HTTP {evidence["http_status"]}) em {evidence.get("elapsed_ms", "–")} ms.'})
            if evidence.get('utm'):
                points.append({'tone': 'ok', 'text': f'{len(evidence["utm"])} parâmetro(s) UTM no link.'})
            if (evidence.get('ssl') or {}).get('valid'):
                points.append({'tone': 'ok', 'text': 'Certificado HTTPS válido.'})
        else:
            supertag = evidence.get('supertag') or {}
            if supertag.get('detected'):
                where = ' via Google Tag Manager' if supertag.get('via') == 'gtm' else ' no código da página'
                points.append({'tone': 'ok', 'text': f'Cadu Super Tag instalada{where}' + (f' ({supertag["site_label"]}).' if supertag.get('site_label') else '.')})
            found = [tag['name'] for tag in evidence.get('tags', []) if tag['detected'] and tag['name'] != 'Cadu Super Tag']
            if found:
                points.append({'tone': 'ok', 'text': 'Tags detectadas: ' + ', '.join(found[:5]) + '.'})
            for platform in evidence.get('platforms', []):
                if platform['score'] >= 100:
                    points.append({'tone': 'ok', 'text': f'{platform["name"]}: medição completa.'})
    return points[:5]


def test(payload, client_id=None, actor_id=None):
    if not isinstance(payload, dict):
        raise BadRequest('Envie um link para testar.')
    mode = str(payload.get('mode') or 'destination').strip().lower()
    if mode not in MODES:
        raise BadRequest('Escolha uma análise válida.')
    actor = None
    if client_id and actor_id:
        from ..cadu_credit_connector import CreditActor
        actor = CreditActor.from_values(client_id, actor_id)
    common = _common(payload, mode, actor)
    common['client_id'] = client_id
    # Clean inventory (scripts by origin, platforms with IDs, events, forms): kept instead of the HTML, read by the
    # reviewer, and the single source of tag detection for the media analysis.
    from . import reports_link_inventory
    inventory = reports_link_inventory.build(common.get('raw_html') or common['html'], common.get('rendered_html'), common['final_url'])
    common['inventory'] = inventory
    result = {'destination': _destination, 'media': _media, 'agentic': _agentic}[mode](common)
    result.update(original_url=common['original_url'], final_url=common['final_url'], elapsed_ms=common['elapsed_ms'])
    result['evidence']['inventory'] = inventory
    if mode == 'media':
        _match_supertag(result, client_id, common['final_parsed'].hostname)
        tag_findings = reports_link_inventory.checks(inventory)
        result['evidence']['tag_findings'] = tag_findings
        result['alerts'] += [item['title'] for item in tag_findings if item['severity'] == 'warning']
    run_id, token = str(uuid.uuid4()), str(uuid.uuid4())
    remote = (result.get('evidence') or {}).get('screenshot')
    stored = _store_screenshot(token, remote) if client_id and actor_id else False
    result['evidence']['screenshot'] = f'/connect/public/link-tests/{token}/screenshot' if stored else None
    result['evidence']['capture_note'] = None if stored else ((common.get('capture') or {}).get('error') or 'Print não gerado: a imagem da captura não pôde ser guardada.')
    result['highlights'] = _highlights(result)
    saved = _save_run(client_id, actor_id, mode, result, run_id, token)
    result['run_id'] = saved['id'] if saved else None
    result['public_token'] = saved['public_token'] if saved else None
    return result
