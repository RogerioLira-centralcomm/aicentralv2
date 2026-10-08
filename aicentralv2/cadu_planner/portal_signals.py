"""What a portal really shows: ad formats on the rendered home page and the sections of its menu.

The page is fetched already rendered (Firecrawl, the key the app stores), because ad slots and menus are built by
JavaScript. Nothing is clicked or submitted; only what a visitor sees on the home is read. A format listed here was
seen on the page; the absence of a format means "not seen", never "not sold".
"""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

# IAB / common Brazilian display sizes -> commercial name.
SIZE_NAMES = {
    (970, 250): 'Billboard', (970, 90): 'Super leaderboard', (728, 90): 'Leaderboard', (970, 66): 'Pushdown',
    (300, 250): 'Retângulo médio', (336, 280): 'Retângulo grande', (300, 600): 'Half page', (300, 1050): 'Portrait',
    (160, 600): 'Arranha-céu', (120, 600): 'Arranha-céu estreito', (320, 50): 'Mobile banner', (320, 100): 'Mobile banner grande',
    (320, 480): 'Interstitial mobile', (300, 100): 'Banner pequeno', (468, 60): 'Banner full', (980, 120): 'Panorama', (1000, 250): 'Panorama largo',
}
SLOT_SIZES = re.compile(r'\[\s*(\d{2,4})\s*,\s*(\d{2,4})\s*\]')
SIZE_TOKEN = re.compile(r'(?<![\d.])(\d{3,4})\s*[x×]\s*(\d{2,4})(?![\d])')
DEFINE_SLOT = re.compile(r'defineSlot\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*(\[.*?\])\s*,\s*[\'"]', re.S)
FORMAT_MARKERS = (
    ('Vídeo in-stream (VAST/IMA)', ('imasdk.googleapis.com', 'vast.xml', 'ima3.js', 'googleads.g.doubleclick.net/pagead/ads?')),
    ('Nativo (recomendação)', ('taboola.com', 'outbrain.com', 'revcontent.com', 'mgid.com')),
    ('Vídeo outstream / in-read', ('teads.tv', 'outstream', 'inread', 'primis.tech', 'connatix.com')),
    ('Interstitial / tela cheia', ('interstitial', 'googletag.enums.outofpageformat')),
    ('Sticky / rodapé fixo', ('sticky-footer', 'anchor-ad', 'adhesion', 'sticky_ad', 'sticky-ad')),
    ('Branded content / publieditorial', ('publieditorial', 'conteudo-patrocinado', 'conteúdo patrocinado', 'branded-content', 'patrocinado')),
)


class _Menu(HTMLParser):
    """Collects the link texts of the first navigation/header menu that has several same-site links."""
    def __init__(self, host):
        super().__init__(convert_charrefs=True)
        self.host, self.depth, self.href, self.buffer = host, 0, None, []
        self.groups, self.current = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('nav', 'header'):
            self.depth += 1
            self.current = []
        if tag == 'a' and self.depth:
            self.href, self.buffer = attrs.get('href') or '', []

    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None and self.depth:
            text = ' '.join(''.join(self.buffer).split())
            target = urlparse(self.href)
            if 2 <= len(text) <= 26 and (not target.netloc or target.netloc.endswith(self.host)) and not text.lower().startswith(('menu', 'buscar', 'entrar', 'assine')):
                self.current.append(text)
            self.href = None
        if tag in ('nav', 'header') and self.depth:
            self.depth -= 1
            if self.current:
                self.groups.append(self.current)
            self.current = []

    def handle_data(self, data):
        if self.href is not None:
            self.buffer.append(data)


def ad_formats(html):
    """[{'format': name, 'size': '970x250' | None, 'count': n}] ordered by how often the slot appears."""
    lowered = str(html or '').lower()
    counts = {}
    for block in DEFINE_SLOT.findall(str(html or '')):
        for width, height in SLOT_SIZES.findall(block):
            counts[(int(width), int(height))] = counts.get((int(width), int(height)), 0) + 1
    for width, height in SIZE_TOKEN.findall(str(html or '')):
        key = (int(width), int(height))
        if key in SIZE_NAMES:
            counts[key] = counts.get(key, 0) + 1
    found = [{'format': SIZE_NAMES[key], 'size': f'{key[0]}x{key[1]}', 'count': count}
             for key, count in sorted(counts.items(), key=lambda item: -item[1]) if key in SIZE_NAMES]
    for name, markers in FORMAT_MARKERS:
        if any(marker in lowered for marker in markers):
            found.append({'format': name, 'size': None, 'count': 1})
    seen, unique = set(), []
    for item in found:
        if item['format'] not in seen:
            seen.add(item['format'])
            unique.append(item)
    return unique[:12]


def menu_sections(html, host):
    parser = _Menu(str(host or '').lower().removeprefix('www.'))
    parser.feed(str(html or ''))
    groups = [group for group in parser.groups if len(group) >= 4]
    best = max(groups, key=len) if groups else []
    seen, result = set(), []
    for text in best:
        text = re.sub(r'^Site(?=[A-ZÁÉÍÓÚ])', '', text).strip()
        key = text.lower()
        if key not in seen:
            seen.add(key)
            result.append(text)
    return result[:14]


def rendered_html(domain, key, timeout=120):
    response = requests.post('https://api.firecrawl.dev/v2/scrape', timeout=timeout,
                             headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                             json={'url': f'https://{domain}', 'formats': ['rawHtml'], 'waitFor': 4000})
    response.raise_for_status()
    data = response.json()
    return (data.get('data') or data).get('rawHtml') or ''


def read(domain, key):
    html = rendered_html(domain, key)
    return {'ad_formats': ad_formats(html), 'site_sections': menu_sections(html, domain), 'html_bytes': len(html)}


def save(portal_id, values):
    from datetime import datetime, timezone
    from psycopg.types.json import Json
    from ..db import get_db
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_planner_portals SET ad_formats = %s, site_sections = %s, signals_checked_at = %s WHERE id = %s''',
                        (Json(values['ad_formats']), Json(values['site_sections']), datetime.now(timezone.utc), portal_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
