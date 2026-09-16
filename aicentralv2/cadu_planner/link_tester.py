"""Safe, bounded destination checks for planning links."""
from __future__ import annotations

import ipaddress
import socket
from time import monotonic
from urllib.parse import parse_qs, urlparse

import requests
from werkzeug.exceptions import BadRequest

MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 8


def _url(value):
    raw = str(value or '').strip()
    if len(raw) > 2048:
        raise BadRequest('O link pode ter no máximo 2.048 caracteres.')
    parsed = urlparse(raw)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise BadRequest('Informe uma URL HTTP ou HTTPS pública e completa.')
    return parsed


def _public_host(parsed):
    try:
        addresses = {entry[4][0] for entry in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        raise BadRequest('Não foi possível localizar o domínio informado.')
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise BadRequest('O Link Tester aceita apenas destinos públicos.')


def _alerts(parsed, final_url, status):
    query = parse_qs(parsed.query, keep_blank_values=True)
    alerts = []
    if not any(key.lower().startswith('utm_') for key in query):
        alerts.append('Sem parâmetros UTM no link informado.')
    if status >= 400:
        alerts.append('O destino respondeu com erro.')
    final = urlparse(final_url)
    if final.scheme != 'https':
        alerts.append('O destino final não usa HTTPS.')
    return alerts


def test(payload):
    if not isinstance(payload, dict):
        raise BadRequest('Envie um link para testar.')
    original = _url(payload.get('url'))
    current = original.geturl()
    chain = []
    started = monotonic()
    try:
        for _ in range(MAX_REDIRECTS + 1):
            parsed = _url(current)
            _public_host(parsed)
            response = requests.get(current, allow_redirects=False, stream=True,
                                    timeout=TIMEOUT_SECONDS, headers={'User-Agent': 'Cadu-LinkTester/1.0'})
            try:
                chain.append({'url': current, 'status': response.status_code})
                location = response.headers.get('Location')
                if response.is_redirect and location:
                    current = requests.compat.urljoin(current, location)
                    continue
                final_url, status = current, response.status_code
                break
            finally:
                response.close()
        else:
            raise BadRequest('O link excede o limite de redirecionamentos.')
    except requests.RequestException:
        raise BadRequest('Não foi possível acessar este destino agora.')
    elapsed_ms = round((monotonic() - started) * 1000)
    return {'original_url': original.geturl(), 'final_url': final_url, 'status': status,
            'reachable': status < 400, 'elapsed_ms': elapsed_ms, 'redirects': chain,
            'alerts': _alerts(original, final_url, status)}
