"""Peças puras da pesquisa do Radar, usadas pelo pipeline de produção e pelo Lab.

Nada aqui chama rede paga nem banco: leitura de JSON de modelos, citações,
pacote de evidências numeradas, datas e checagem de link.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from html.parser import HTMLParser

import requests

UA = {'User-Agent': 'Mozilla/5.0 (compatible; CaduRadar/1.0; +https://centralcomm.media)'}
LIST_KEYS = ('opportunities', 'results', 'changes', 'fatos', 'buzz', 'angulos')


def json_loads(text):
    """JSON da resposta; se veio cortado no limite de tokens, salva os itens completos da lista principal."""
    text = str(text or '').strip()
    text = re.sub(r'^```(?:json)?|```$', '', text, flags=re.M).strip()
    match = re.search(r'\{.*\}', text, re.S)
    try:
        return json.loads(match.group(0) if match else text)
    except (ValueError, AttributeError):
        return _salvage(text)


def _salvage(text):
    decoder = json.JSONDecoder()
    for key in LIST_KEYS:
        found = re.search(r'"%s"\s*:\s*\[' % key, text)
        if not found:
            continue
        items, position = [], found.end()
        while True:
            start = text.find('{', position)
            if start < 0:
                break
            try:
                item, end = decoder.raw_decode(text, start)
            except ValueError:
                break
            items.append(item)
            position = end
        if items:
            return {key: items, '_salvaged': True}
    return {}


def citations(message):
    """URLs citadas, venham do Perplexity (_cadu_citations) ou de anotações url_citation."""
    found = []
    raw = (message or {}).get('_cadu_citations') or []
    if isinstance(raw, dict):
        raw = raw.get('search_results') or raw.get('citations') or []
    for item in raw if isinstance(raw, list) else []:
        url = item if isinstance(item, str) else (item.get('url') or item.get('link') or '') if isinstance(item, dict) else ''
        title = item.get('title') if isinstance(item, dict) else ''
        if url:
            found.append({'url': str(url), 'title': str(title or '')})
    for note in (message or {}).get('annotations') or []:
        cite = (note or {}).get('url_citation') if isinstance(note, dict) else None
        if isinstance(cite, dict) and cite.get('url'):
            found.append({'url': cite['url'], 'title': cite.get('title') or ''})
    seen, unique = set(), []
    for item in found:
        key = item['url'].split('#')[0].rstrip('/').split('?utm_')[0]
        if key not in seen:
            seen.add(key)
            unique.append({**item, 'url': key})
    return unique


def facts_from(message_text, cited):
    """Fatos do JSON do modelo; URLs novas dos fatos entram na lista de citações."""
    data = json_loads(message_text)
    facts = [item for item in (data.get('fatos') or []) if isinstance(item, dict) and item.get('fato')]
    known = {item['url'] for item in cited}
    for item in facts:
        if item.get('url') and item['url'] not in known:
            cited.append({'url': item['url'], 'title': item.get('veiculo') or ''})
            known.add(item['url'])
    return facts, cited


def build_packet(facts, pages, extra=(), limit=14):
    """Evidências numeradas S1..Sn: fato com URL, página lida ou item de busca."""
    by_url = {page.get('url'): page for page in pages}
    packet = []
    for item in [*facts, *extra]:
        url = item.get('url') or ''
        page = by_url.pop(url, None)
        packet.append({'url': url, 'title': item.get('title') or item.get('veiculo') or item.get('fato', '')[:120],
                       'published_at': item.get('published_at') or item.get('data') or (page or {}).get('published_at'),
                       'excerpt': str((page or {}).get('content') or item.get('excerpt') or item.get('fato') or '')[:1400]})
    for page in by_url.values():
        packet.append({'url': page.get('url'), 'title': page.get('title') or page.get('page_title'),
                       'published_at': page.get('published_at'), 'excerpt': str(page.get('content') or '')[:1400]})
    unique, seen = [], set()
    for item in packet:
        key = item['url'] or item['title']
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return [{'id': f'S{index + 1}', **item} for index, item in enumerate(unique[:limit])]


def parse_date(value):
    text = str(value or '').strip()
    if not text:
        return None
    for parse in (lambda v: datetime.fromisoformat(v.replace('Z', '+00:00')), parsedate_to_datetime):
        try:
            parsed = parse(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    match = re.search(r'(20\d\d)-(\d\d)-(\d\d)', text)
    return datetime(int(match[1]), int(match[2]), int(match[3]), tzinfo=timezone.utc) if match else None


def check_url(url):
    """'ok', 'bloqueado' (existe, mas recusa robô) ou 'quebrado'."""
    try:
        response = requests.get(url, headers=UA, timeout=10, allow_redirects=True, stream=True)
        response.close()
    except requests.RequestException:
        return 'quebrado'
    if response.status_code < 400:
        return 'ok'
    return 'bloqueado' if response.status_code in (401, 402, 403, 429, 451) else 'quebrado'


class _Text(HTMLParser):
    SKIP = {'script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'noscript'}

    def __init__(self):
        super().__init__()
        self.parts, self.depth, self.title, self._in_title = [], 0, '', False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1
        self._in_title = tag == 'title'

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1
        self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.depth and len(data.strip()) > 40:
            self.parts.append(' '.join(data.split()))


def python_read(url, limit=6000):
    """Leitura gratuita por HTTP + parser da biblioteca padrão (reserva do Firecrawl)."""
    response = requests.get(url, headers=UA, timeout=12, allow_redirects=True)
    response.raise_for_status()
    parser = _Text()
    parser.feed(response.text[:600_000])
    return {'title': parser.title.strip()[:220], 'content': '\n'.join(parser.parts)[:limit]}
