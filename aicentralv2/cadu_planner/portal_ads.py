"""ads.txt validation and programmatic-signal detection for catalog portals.

Everything here is read from public HTTPS responses: /ads.txt and the home page
HTML. Scripts are never executed, so tags injected only by JavaScript or a CMP
are not seen; a missing signal means "not detected", never "does not sell
programmatic". One host per call; redirects stay on host / www.host.
"""
import ipaddress
import re
import socket
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

AGENT = 'CaduPlannerCatalogBot/1.0 (+https://cadu.ai/crawler)'
ADS_TXT_MAX_BYTES = 2_000_000
HOME_MAX_BYTES = 1_500_000
VARIABLES = {'contact', 'subdomain', 'inventorypartnerdomain', 'ownerdomain', 'managerdomain'}
RELATIONSHIPS = {'DIRECT', 'RESELLER'}
_SYSTEM = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$')

# (signal, substrings searched in the lower-cased HTML, kind)
SIGNALS = (
    ('Google Ad Manager', ('securepubads.g.doubleclick.net', 'googletagservices.com/tag/js/gpt.js', 'googletag.defineslot', 'googletag.cmd'), 'adserver'),
    ('Google AdSense', ('pagead2.googlesyndication.com', 'adsbygoogle'), 'adsense'),
    ('Prebid', ('prebid', 'pbjs.'), 'header_bidding'),
    ('Amazon TAM/UAM', ('c.amazon-adsystem.com', 'apstag'), 'header_bidding'),
    ('Index Exchange', ('casalemedia.com', 'indexww.com'), 'header_bidding'),
    ('Magnite/Rubicon', ('rubiconproject.com', 'magnite.com'), 'header_bidding'),
    ('PubMatic', ('pubmatic.com',), 'header_bidding'),
    ('OpenX', ('openx.net',), 'header_bidding'),
    ('Xandr/AppNexus', ('adnxs.com',), 'header_bidding'),
    ('Criteo', ('criteo.com', 'criteo.net'), 'header_bidding'),
    ('Smart AdServer', ('smartadserver.com',), 'adserver'),
    ('Teads', ('teads.tv',), 'native_video'),
    ('Taboola', ('taboola.com',), 'native_video'),
    ('Outbrain', ('outbrain.com',), 'native_video'),
)


def _public_host(host):
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)
    except (socket.gaierror, ValueError):
        return False


def domain_resolves(host):
    """True when the host resolves to public addresses; checked twice so a network blip is not a dead domain."""
    if _public_host(host):
        return True
    time.sleep(2)
    return _public_host(host)


class _SiteRedirect(HTTPRedirectHandler):
    """Follow HTTPS redirects only between host and www.host, to public addresses."""
    def __init__(self, host):
        super().__init__()
        bare = host[4:] if host.startswith('www.') else host
        self.allowed = {bare, f'www.{bare}'}

    def redirect_request(self, request, fp, code, message, headers, new_url):
        parsed = urlparse(new_url)
        if parsed.scheme != 'https' or parsed.hostname not in self.allowed or parsed.port not in (None, 443):
            return None
        if not _public_host(parsed.hostname):
            return None
        return super().redirect_request(request, fp, code, message, headers, new_url)


def _fetch(host, path, limit, accept, timeout):
    """Return (status, content_type, text, final_url); status is 'ok' or a failure code."""
    opener = build_opener(_SiteRedirect(host))
    try:
        with opener.open(Request(f'https://{host}{path}', headers={'User-Agent': AGENT, 'Accept': accept}), timeout=timeout) as response:
            final = response.geturl()
            body = response.read(limit + 1)
            if body[:2] == b'\x1f\x8b':  # some hosts gzip even when it was not requested
                inflater = zlib.decompressobj(31)
                body = inflater.decompress(body, limit + 1)
            if len(body) > limit:
                return 'too_large', '', '', final
            return 'ok', response.headers.get_content_type(), body.decode('utf-8', 'replace'), final
    except HTTPError as error:
        return ('missing' if error.code in (404, 410) else f'http_{error.code}'), '', '', ''
    except (URLError, TimeoutError, OSError, zlib.error):
        return 'unreachable', '', '', ''


def parse_ads_txt(text):
    """Parse ads.txt into valid records and invalid-line count.

    A record is `ad_system_domain, publisher_id, DIRECT|RESELLER[, cert_id]`.
    Comments, blank lines and the IAB variables are ignored.
    """
    records, invalid = [], 0
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if '=' in line and line.split('=', 1)[0].strip().lower() in VARIABLES:
            continue
        parts = [part.strip() for part in line.split(',')]
        if len(parts) < 3 or len(parts) > 4:
            invalid += 1
            continue
        system, account, relationship = parts[0].lower(), parts[1], parts[2].upper()
        if not _SYSTEM.match(system) or not account or relationship not in RELATIONSHIPS:
            invalid += 1
            continue
        records.append({'system': system, 'account': account, 'relationship': relationship})
    return records, invalid


def check_ads_txt(host, timeout=12):
    """Classify /ads.txt: valid, partial, invalid, missing or unreachable."""
    status, content_type, text, final = _fetch(host, '/ads.txt', ADS_TXT_MAX_BYTES, 'text/plain,*/*;q=0.5', timeout)
    result = {'status': status, 'records': 0, 'sellers': []}
    if status != 'ok':
        return result
    head = text.lstrip()[:200].lower()
    if content_type in {'text/html', 'application/xhtml+xml'} or head.startswith(('<!doctype', '<html', '<?xml')):
        result['status'] = 'invalid'  # a soft-404 page, not an ads.txt file
        return result
    records, invalid = parse_ads_txt(text)
    result['records'] = len(records)
    if not records:
        result['status'] = 'empty' if not invalid else 'invalid'
        return result
    result['status'] = 'valid' if invalid <= max(1, len(records) // 20) else 'partial'
    systems = {}
    for record in records:
        entry = systems.setdefault(record['system'], {'system': record['system'], 'direct': 0, 'reseller': 0})
        entry['direct' if record['relationship'] == 'DIRECT' else 'reseller'] += 1
    result['sellers'] = sorted(systems.values(), key=lambda e: (-(e['direct'] + e['reseller']), e['system']))[:25]
    result['systems_total'] = len(systems)
    result['direct_total'] = sum(e['direct'] for e in systems.values())
    return result


class _Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self._title, self.title, self.icons = False, [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title':
            self._title = True
        elif tag == 'link' and attrs.get('href') and 'icon' in (attrs.get('rel') or '').lower():
            self.icons.append((attrs.get('rel', '').lower(), attrs['href'].strip(), attrs.get('sizes') or ''))

    def handle_endtag(self, tag):
        if tag == 'title':
            self._title = False

    def handle_data(self, data):
        if self._title and data.strip():
            self.title.append(data.strip())


def _icon(icons, base):
    """Prefer apple-touch / larger icons; resolve against the final page URL."""
    def weight(item):
        rel, _, sizes = item
        size = max([int(n) for n in re.findall(r'\d+', sizes)] or [0])
        return (('apple' in rel), size)
    for _, href, _ in sorted(icons, key=weight, reverse=True):
        url = urljoin(base, href)
        if urlparse(url).scheme == 'https':
            return url[:2048]
    return ''


def detect_programmatic(html):
    """Return (status, signals) from raw home-page HTML."""
    lowered = html.lower()
    found = [{'signal': name, 'kind': kind} for name, needles, kind in SIGNALS if any(n in lowered for n in needles)]
    kinds = {item['kind'] for item in found}
    if kinds & {'header_bidding', 'adserver'}:
        status = 'detected'
    elif found:
        status = 'adsense_native'
    else:
        status = 'not_detected'
    return status, found


def check_home(host, timeout=12):
    """Fetch the home page (robots.txt permitting) for title, favicon and ad tags."""
    base = f'https://{host}/'
    status, _, robots, _ = _fetch(host, '/robots.txt', 256_000, 'text/plain', timeout)
    if status == 'ok':
        parser = RobotFileParser(base + 'robots.txt')
        parser.parse(robots.splitlines())
        if not parser.can_fetch(AGENT, base):
            return {'status': 'robots_disallowed'}
    status, content_type, html, final = _fetch(host, '/', HOME_MAX_BYTES, 'text/html', timeout)
    if status != 'ok':
        return {'status': status}
    if content_type != 'text/html':
        return {'status': 'not_html'}
    head = _Head()
    head.feed(html)
    programmatic, signals = detect_programmatic(html)
    return {'status': 'ok', 'title': ' '.join(head.title)[:180], 'favicon_url': _icon(head.icons, final or base),
            'programmatic_status': programmatic, 'signals': signals}


def check_portal(domain, timeout=12):
    """Run both checks for one portal domain; never raises, so one bad host cannot stop a batch."""
    try:
        return _check_portal(domain, timeout)
    except Exception:  # e.g. http.client.IncompleteRead on a truncated response
        return {'domain': str(domain or '').strip().lower(), 'status': 'error'}


def _check_portal(domain, timeout):
    host = str(domain or '').strip().lower().rstrip('.')
    if not host or '/' in host or ':' in host or '@' in host:
        return {'domain': host, 'status': 'invalid_domain'}
    if not domain_resolves(host):
        return {'domain': host, 'status': 'dns_failed'}
    ads_txt, home = check_ads_txt(host, timeout), check_home(host, timeout)
    # Tags injected by JavaScript are invisible to a static fetch; a valid ads.txt
    # still proves the inventory is sold programmatically.
    if home.get('programmatic_status') == 'not_detected' and ads_txt['status'] in {'valid', 'partial'}:
        home['programmatic_status'] = 'ads_txt_declared'
    return {'domain': host, 'status': 'ok', 'ads_txt': ads_txt, 'home': home, 'checked_at': datetime.now(timezone.utc)}


def crawl_many(domains, workers=8, timeout=12):
    """Check many portals concurrently; each host is only ever hit by one worker."""
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 16))) as pool:
        yield from pool.map(lambda d: check_portal(d, timeout), domains)


NO_ADS_TXT = {'missing', 'empty', 'invalid'}


def deactivation_alert(ads_txt_status, programmatic_status, dns_failed=False):
    """Why a portal is a candidate to leave the catalog, or None.

    'dns_invalido' is conclusive (the site does not exist). 'sem_ads_txt' is the strong alert: no usable ads.txt
    and no programmatic tag, so the portal cannot be bought programmatically and only sells direct, if at all.
    Unreadable sites (403, redirects, robots) are never an alert: not being able to read is not being absent.
    """
    if dns_failed or ads_txt_status == 'dns_failed':
        return 'dns_invalido'
    if ads_txt_status in NO_ADS_TXT and programmatic_status in {'not_detected', 'adsense_native'}:
        return 'sem_ads_txt'
    return None


def _transient(status):
    """Failures that say nothing about the site's setup (network, DNS, 5xx, crash)."""
    status = str(status or '')
    return status in {'unreachable', 'dns_failed', 'robots_unavailable', 'error', 'too_large'} or status.startswith('http_5')


def save_result(result):
    """Persist one check; keeps previous title/favicon when the home page failed."""
    from psycopg.types.json import Json
    from ..db import get_db
    if result.get('status') != 'ok':
        ads = {'status': result.get('status'), 'records': 0, 'sellers': []}
        home, checked = {'status': result.get('status')}, datetime.now(timezone.utc)
    else:
        ads, home, checked = result['ads_txt'], result['home'], result['checked_at']
    ok_home = home.get('status') == 'ok'
    keep_ads, keep_home = _transient(ads['status']), not ok_home and _transient(home['status'])
    programmatic = home.get('programmatic_status') if ok_home else f"unavailable_{home['status']}"[:30]
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE cadu_planner_portals
                              SET ads_txt_status = CASE WHEN %(keep_ads)s THEN COALESCE(ads_txt_status, %(ads_status)s) ELSE %(ads_status)s END,
                                  ads_txt_records = CASE WHEN %(keep_ads)s THEN ads_txt_records ELSE %(records)s END,
                                  ads_txt_sellers = CASE WHEN %(keep_ads)s THEN ads_txt_sellers ELSE %(sellers)s::jsonb END,
                                  ads_txt_checked_at = %(checked)s,
                                  programmatic_status = CASE WHEN %(keep_home)s THEN COALESCE(programmatic_status, %(programmatic)s) ELSE %(programmatic)s END,
                                  programmatic_signals = CASE WHEN %(keep_home)s THEN programmatic_signals ELSE %(signals)s::jsonb END,
                                  programmatic_checked_at = %(checked)s,
                                  site_title = COALESCE(NULLIF(%(title)s, ''), site_title),
                                  favicon_url = COALESCE(NULLIF(%(favicon)s, ''), favicon_url),
                                  updated_at = NOW()
                            WHERE domain = %(domain)s''',
                        {'keep_ads': keep_ads, 'keep_home': keep_home, 'ads_status': ads['status'], 'records': ads['records'],
                         'sellers': Json(ads['sellers']), 'checked': checked, 'programmatic': programmatic,
                         'signals': Json(home.get('signals', []) if ok_home else []),
                         'title': home.get('title', '') if ok_home else '',
                         'favicon': home.get('favicon_url', '') if ok_home else '', 'domain': result['domain']})
            saved = cur.rowcount > 0
            if result.get('status') == 'dns_failed':
                # The domain does not resolve: the portal leaves the catalog (kept in the table, inactive).
                cur.execute('UPDATE cadu_planner_portals SET active = FALSE, featured_rank = NULL WHERE domain = %s', (result['domain'],))
        conn.commit()
        return saved
    except Exception:
        conn.rollback()
        raise
