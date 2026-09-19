"""Safe, bounded link analysis for the Planner Link Tester.

The reports share network evidence but never share a score: destination answers
whether an ad click arrives, media answers whether it can be measured and
converted, and agentic answers whether a domain is legible to AI.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import ssl
import uuid
from html import unescape
from time import monotonic
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from werkzeug.exceptions import BadRequest

MAX_REDIRECTS, TIMEOUT_SECONDS, MAX_HTML_BYTES = 5, 8, 1_000_000
MODES = {'destination', 'media', 'agentic'}
USER_AGENT = 'Cadu-Planner-LinkTester/2.0'


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


def _rendered_page(url):
    """Use the configured renderer for JavaScript evidence without making it mandatory."""
    try:
        from ..crm_v3_web_scout import _firecrawl_scrape
        data = _firecrawl_scrape(url, formats=['html', 'screenshot'], timeout_s=30)
    except Exception:
        return {'html': '', 'screenshot': None, 'source': 'http'}
    screenshot = data.get('screenshot')
    if isinstance(screenshot, dict):
        screenshot = screenshot.get('url') or screenshot.get('imageUrl')
    return {'html': str(data.get('html') or ''),
            'screenshot': screenshot if isinstance(screenshot, str) else None,
            'source': 'rendered'}


def _common(payload, mode):
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
    rendered = _rendered_page(final.geturl()) if mode in {'media', 'agentic'} else {'html': '', 'screenshot': None, 'source': 'http'}
    if rendered['html']:
        html = rendered['html']
    return {'original_url': original.geturl(), 'final_url': final.geturl(), 'final_parsed': final,
            'status': status, 'reachable': status < 400, 'elapsed_ms': round((monotonic() - started) * 1000),
            'redirects': chain, 'html': html, 'headers': final_headers,
            'capture': {'source': rendered['source'], 'screenshot': rendered['screenshot']}}


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
    requirements = {'Google': {'GTM', 'GA4', 'Google Ads'}, 'Meta': {'Meta Pixel'}, 'TikTok': {'TikTok Pixel'}, 'LinkedIn': {'LinkedIn Insight'}}
    return [{'name': name, 'detected': sorted(found & required), 'missing': sorted(required - found),
             'score': round(len(found & required) * 100 / len(required))} for name, required in requirements.items()]


def _media(common):
    html = common['html']
    capture = common.get('capture') or {}
    definitions = {'GTM': r'googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]+', 'GA4': r'gtag\s*\(|G-[A-Z0-9]+',
                   'Google Ads': r'AW-[A-Z0-9]+|googleadservices\.com', 'Meta Pixel': r'fbq\s*\(|fbevents\.js',
                   'TikTok Pixel': r'ttq\.|analytics\.tiktok\.com', 'LinkedIn Insight': r'snap\.licdn\.com|_linkedin_partner_id',
                   'Microsoft Clarity': r'clarity\.ms'}
    tags = [{'name': name, 'detected': bool(re.search(pattern, html, re.I))} for name, pattern in definitions.items()]
    whatsapp = bool(re.search(r'(?:wa\.me/|api\.whatsapp\.com|whatsapp:)', html, re.I))
    forms = len(re.findall(r'<form\b', html, re.I))
    phones = bool(re.search(r'href=["\']tel:', html, re.I))
    events = sorted(set(re.findall(r"(?:gtag\s*\(\s*['\"]event['\"]\s*,\s*|event\s*[:=]\s*['\"])([\w_-]+)", html, re.I)))
    consent = bool(re.search(r'cookie|consent|lgpd|privacidade|privacy', html, re.I))
    privacy = bool(re.search(r'(?:pol[ií]tica\s+de\s+privacidade|privacy\s+policy)', html, re.I))
    gaps = []
    if whatsapp and not any('whatsapp' in event.lower() for event in events): gaps.append('WhatsApp detectado sem evento específico.')
    if forms and not any('form' in event.lower() or 'lead' in event.lower() or 'submit' in event.lower() for event in events): gaps.append('Formulário detectado sem evento de conversão.')
    score = min(100, 20 + sum(tag['detected'] for tag in tags) * 12 + (15 if (whatsapp or forms) else 0) + (10 if events else 0) + (10 if consent else 0))
    return {'kind': 'media', 'score': score, 'status_label': 'Pronto para medir' if score >= 75 else 'Medição parcial' if score >= 45 else 'Sem base de medição',
            'summary': 'Tags, conversões e consentimento foram verificados separadamente do destino.',
            'evidence': {'tags': tags, 'conversion': {'whatsapp': whatsapp, 'forms': forms, 'phone': phones}, 'events': events,
                         'compliance': {'consent_detected': consent, 'privacy_policy_detected': privacy}, 'platforms': _platforms(tags),
                         'screenshot': capture.get('screenshot'), 'capture_source': capture.get('source', 'http')},
            'alerts': gaps + ([] if consent else ['Nenhum sinal de consentimento/cookies foi encontrado.'])}


def _agentic(common):
    final = common['final_parsed']; base = f'{final.scheme}://{final.netloc}/'
    capture = common.get('capture') or {}
    endpoints = {'robots.txt': 'robots.txt', 'llms.txt': 'llms.txt', 'llms-full.txt': 'llms-full.txt', 'sitemap.xml': 'sitemap.xml'}
    resources, bodies = {}, {}
    for name, path in endpoints.items():
        try:
            status, _, body = _fetch(urljoin(base, path), body=True)
            resources[name], bodies[name] = {'url': urljoin(base, path), 'status': status, 'available': status == 200}, body
        except (BadRequest, requests.RequestException):
            resources[name], bodies[name] = {'url': urljoin(base, path), 'status': None, 'available': False}, ''
    bots, robots = ['GPTBot', 'ChatGPT-User', 'OAI-SearchBot', 'ClaudeBot', 'PerplexityBot', 'Google-Extended'], bodies['robots.txt']
    bot_access = [{'name': bot, 'blocked': bool(re.search(rf'User-agent:\s*{re.escape(bot)}[\s\S]*?Disallow:\s*/\s*$', robots, re.I | re.M))} for bot in bots]
    schema_types = sorted(set(re.findall(r'"@type"\s*:\s*"([^" ]+)', common['html'], re.I)))
    llms_quality = {'has_title': bool(re.search(r'^#\s+.+', bodies['llms.txt'], re.M)), 'links': len(re.findall(r'\[[^]]+\]\([^)]+\)', bodies['llms.txt']))}
    score = 25 + (25 if resources['robots.txt']['available'] else 0) + (25 if resources['llms.txt']['available'] else 0) + (15 if resources['sitemap.xml']['available'] else 0) + min(10, len(schema_types) * 3)
    alerts = ([] if resources['llms.txt']['available'] else ['O domínio não publica llms.txt.'])
    if any(bot['blocked'] for bot in bot_access): alerts.append('Há agentes de IA bloqueados no robots.txt.')
    return {'kind': 'agentic', 'score': min(100, score), 'status_label': 'Base agêntica pronta' if score >= 75 else 'Preparação parcial' if score >= 45 else 'Não preparado',
            'summary': 'Esta auditoria considera a presença do domínio para agentes de IA, não a campanha.',
            'evidence': {'domain': final.hostname, 'resources': resources, 'bot_access': bot_access, 'schema_types': schema_types,
                         'llms_quality': llms_quality, 'screenshot': capture.get('screenshot')}, 'alerts': alerts}


def _save_run(client_id, actor_id, mode, result, project_ref=None):
    """Persist one independent report without coupling the analyzer to history UI."""
    if not client_id or not actor_id:
        return None
    from psycopg.types.json import Json
    from ..db import get_db
    conn = get_db()
    run_id, public_token = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_planner_link_test_runs
                           (id, client_id, created_by, project_ref, mode, original_url, final_url, score, status_label, result, public_token, shared_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())''',
                        (run_id, client_id, actor_id, project_ref, mode, result['original_url'], result['final_url'], result['score'],
                         result['status_label'], Json(result), public_token))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if project_ref:
        try:
            from ..cadu_workspace.project_resource_service import notify_change
            notify_change(client_id, project_ref, 'created', source_system='planner_link_tester',
                          source_id=run_id, actor_id=actor_id)
        except Exception:
            conn.rollback()
    return {'id': run_id, 'public_token': public_token}


def public_result(token):
    """Read an unguessable, independently shared report without tenant context."""
    try:
        from ..cadu_family import repository
        rows = repository.rows('''SELECT mode, original_url, final_url, score, status_label, result, created_at
                                    FROM cadu_planner_link_test_runs
                                   WHERE public_token = %s AND revoked_at IS NULL''', (str(token),))
    except Exception:
        return None
    return rows[0] if rows else None


def history(client_id, limit=18):
    from ..cadu_family import repository
    return repository.rows('''SELECT id, mode, final_url, score, status_label, public_token, created_at,
                                      result->'evidence'->>'screenshot' AS screenshot
                                 FROM cadu_planner_link_test_runs
                                WHERE client_id = %s
                                ORDER BY created_at DESC LIMIT %s''', (client_id, limit))


def detail(client_id, run_id):
    from ..cadu_family import repository
    rows = repository.rows('''SELECT id, mode, original_url, final_url, score, status_label, result, public_token, created_at
                                FROM cadu_planner_link_test_runs
                               WHERE id = %s AND client_id = %s''', (str(run_id), client_id))
    return rows[0] if rows else None


def test(payload, client_id=None, actor_id=None, project_ref=None):
    if not isinstance(payload, dict):
        raise BadRequest('Envie um link para testar.')
    mode = str(payload.get('mode') or 'destination').strip().lower()
    if mode not in MODES:
        raise BadRequest('Escolha uma análise válida.')
    common = _common(payload, mode)
    result = {'destination': _destination, 'media': _media, 'agentic': _agentic}[mode](common)
    result.update(original_url=common['original_url'], final_url=common['final_url'], elapsed_ms=common['elapsed_ms'])
    saved = _save_run(client_id, actor_id, mode, result, project_ref)
    result['run_id'] = saved['id'] if saved else None
    result['public_token'] = saved['public_token'] if saved else None
    return result
