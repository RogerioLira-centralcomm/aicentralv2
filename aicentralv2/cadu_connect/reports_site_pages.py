"""Page catalog per client and domain: search the pages of a site without a flow and without crawling it."""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import BoundedSemaphore
from urllib.parse import unquote, urlparse

from flask import abort, jsonify, request

from ..auth import login_required_api
from ..db import get_db
from .reports_page_identity import normalize_host
from .reports_v1 import _rows, _selection, _write_guard

CATALOG_MAX_PAGES = 5000
CATALOG_TTL = timedelta(hours=24)
SEARCH_LIMIT = 30
TITLE_BATCH = 8
_slots = BoundedSemaphore(2)


def slug_name(path):
    """A readable name from the address: '/audiencia/empresarios-pro' -> 'Audiencia · Empresarios Pro'."""
    segments = [segment for segment in unquote(path or '/').split('/') if segment]
    if not segments:
        return 'Página inicial'
    words = lambda segment: ' '.join(word.capitalize() for word in re.split(r'[-_+\s]+', re.sub(r'\.[a-z0-9]{2,5}$', '', segment)) if word)
    return ' · '.join(filter(None, (words(segment) for segment in segments[-3:])))[:200] or 'Página'


def client_hosts(client_id):
    """Domains the client owns: its Super Tag installations. Only these are crawled for a sitemap."""
    rows = _rows('''SELECT DISTINCT allowed_host FROM cadu_reports_supertag_sites
        WHERE client_id=%s AND enabled=TRUE AND revoked_at IS NULL ORDER BY allowed_host''', (client_id,))
    return [row['allowed_host'] for row in rows]


def _host_param(client_id):
    hosts = client_hosts(client_id)
    host = (request.args.get('host') or (request.get_json(silent=True) or {}).get('host') or '').strip().lower().rstrip('.')
    if host:
        # 'www.' is the same site: answer with the domain as the client registered it.
        match = next((item for item in hosts if normalize_host(item) == normalize_host(host)), None)
        if match is None:
            abort(400, description='Esse domínio não está entre os sites do cliente.')
        host = match
    return host or (hosts[0] if hosts else ''), hosts


def refresh_catalog(client_id, host):
    """Read the sitemap of an owned domain and store its paths with a name derived from the address."""
    from .reports_flow import _site_sitemap_urls
    if not _slots.acquire(blocking=False):
        abort(429, description='Há outras atualizações em andamento. Tente novamente em instantes.')
    try:
        urls, truncated = _site_sitemap_urls(f'https://{host}/', host, limit=CATALOG_MAX_PAGES)
    finally:
        _slots.release()
    paths = list(dict.fromkeys(['/'] + [urlparse(url).path or '/' for url in urls]))[:CATALOG_MAX_PAGES]
    paths = [path for path in paths if len(path) <= 500]
    _rows('''INSERT INTO cadu_reports_site_pages (client_id,host,path,name)
        SELECT %s,%s,item.path,item.name FROM unnest(%s::text[],%s::text[]) AS item(path,name)
        ON CONFLICT (client_id,host,path) DO UPDATE SET updated_at=NOW()''',
          (client_id, host, paths, [slug_name(path) for path in paths]))
    _rows('DELETE FROM cadu_reports_site_pages WHERE client_id=%s AND host=%s AND NOT (path=ANY(%s))', (client_id, host, paths))
    _rows('''INSERT INTO cadu_reports_site_catalogs (client_id,host,page_count,truncated) VALUES (%s,%s,%s,%s)
        ON CONFLICT (client_id,host) DO UPDATE SET refreshed_at=NOW(),page_count=EXCLUDED.page_count,truncated=EXCLUDED.truncated''',
          (client_id, host, len(paths), bool(truncated)))
    get_db().commit()
    return len(paths), bool(truncated)


def _catalog_state(client_id, host):
    row = _rows('SELECT refreshed_at,page_count,truncated,(NOW()-refreshed_at) AS age FROM cadu_reports_site_catalogs WHERE client_id=%s AND host=%s',
                (client_id, host))
    return row[0] if row else None


def search_pages(client_id, host, query, limit=SEARCH_LIMIT):
    tokens = [token for token in re.split(r'\s+', query.strip().lower()) if token][:5]
    clauses = ' AND '.join("(LOWER(name) LIKE %s OR LOWER(COALESCE(title,'')) LIKE %s OR LOWER(path) LIKE %s)" for _ in tokens)
    params = [client_id, host]
    for token in tokens:
        like = f"%{token.replace('%', '').replace('_', ' ')}%"
        params += [like, like, like]
    rows = _rows(f'''SELECT host,path,name,title FROM cadu_reports_site_pages WHERE client_id=%s AND host=%s
        {('AND ' + clauses) if clauses else ''} ORDER BY (path='/') DESC, LENGTH(path), path LIMIT {int(limit)}''', tuple(params))
    return [{**row, 'url': f"https://{row['host']}{'' if row['path'] == '/' else row['path']}"} for row in rows]


NEXT_PAGE_HINTS = {
    'form': re.compile(r'contato|contact|orcamento|agendar|agende|cadastro|inscri|fale|formulario|lead', re.I),
    'conversion': re.compile(r'obrigad|thank|sucesso|success|confirma|concluid|pedido-recebido', re.I),
}


def observed_next_pages(client_id, host, path, limit=8):
    """Pages people actually opened right after `path` in the last 30 days (Super Tag page views of this client)."""
    if not path:
        return []
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '4s'")
        return _rows('''WITH recent AS (
                SELECT session_id,page_path,occurred_at,id FROM cadu_reports_flow_events
                WHERE client_id=%s AND event_kind IN ('page_view','conversion')
                  AND occurred_at > NOW() - INTERVAL '30 days'
                  AND LOWER(REGEXP_REPLACE(COALESCE(page_host,''),'^www\\.',''))=%s
            ), ordered AS (
                SELECT page_path,LEAD(page_path) OVER (PARTITION BY session_id ORDER BY occurred_at,id) AS next_path FROM recent
            ) SELECT next_path AS path,COUNT(*)::bigint AS passes FROM ordered
              WHERE page_path=%s AND next_path IS NOT NULL AND next_path<>page_path
              GROUP BY next_path ORDER BY passes DESC LIMIT %s''', (client_id, normalize_host(host), path, int(limit)))
    except Exception:  # a slow or missing event table only removes the observed hint
        db.rollback()
        return []


def suggest_next_pages(client_id, host, after, kind, exclude, observed, limit=5):
    """Rank candidates for a new step: observed navigation first, then the address pattern of the step type, then
    the catalog. `confidence` is the share of observed passes, so the editor only fills a page on its own when the
    traffic clearly points to it."""
    exclude = set(exclude)
    total = sum(int(row['passes']) for row in observed) or 0
    known = {row['path']: row for row in _rows(
        'SELECT host,path,name,title FROM cadu_reports_site_pages WHERE client_id=%s AND host=%s AND path=ANY(%s)',
        (client_id, host, [row['path'] for row in observed] or ['']))}
    hint = NEXT_PAGE_HINTS.get(kind)
    ranked, seen = [], set()

    def push(path, name, title, reason, passes=None):
        if path in exclude or path in seen or len(ranked) >= limit:
            return
        seen.add(path)
        ranked.append({'host': host, 'path': path, 'name': name, 'title': title, 'reason': reason, 'passes': passes,
                       'confidence': round(passes / total, 3) if passes and total else 0})

    for row in observed:
        if hint and not hint.search(row['path']) and kind != 'page':
            continue
        page = known.get(row['path']) or {}
        push(row['path'], page.get('name') or slug_name(row['path']), page.get('title'), 'observed', int(row['passes']))
    if hint:
        for page in _rows('''SELECT path,name,title FROM cadu_reports_site_pages WHERE client_id=%s AND host=%s
                AND (path ~* %s OR LOWER(COALESCE(title,'')) ~* %s) ORDER BY LENGTH(path),path LIMIT 20''',
                          (client_id, host, hint.pattern, hint.pattern)):
            push(page['path'], page['name'], page['title'], 'pattern')
    if not after or after == '/':
        for page in _rows('''SELECT path,name,title FROM cadu_reports_site_pages WHERE client_id=%s AND host=%s AND path<>'/'
                ORDER BY array_length(string_to_array(trim(both '/' from path),'/'),1),LENGTH(path),path LIMIT 20''', (client_id, host)):
            push(page['path'], page['name'], page['title'], 'catalog')
    return ranked


def register(bp):
    @bp.get('/api/v2/reports/flow/site-pages/next')
    @login_required_api
    def reports_site_pages_next():
        """Suggestions for the page of a step just added after `after`; empty when the client has no catalog."""
        selected = _selection()
        client_id = selected['client_id']
        host, _ = _host_param(client_id)
        kind = request.args.get('type') if request.args.get('type') in ('page', 'form', 'conversion', 'error') else 'page'
        after = (request.args.get('after') or '')[:500]
        exclude = [path for path in (request.args.get('exclude') or '').split(',') if path.startswith('/')][:200]
        if not host or _catalog_state(client_id, host) is None:
            return jsonify(host=host, pages=[], catalog=False)
        observed = observed_next_pages(client_id, host, after) if after.startswith('/') else []
        return jsonify(host=host, catalog=True, observed_total=sum(int(row['passes']) for row in observed),
                       pages=suggest_next_pages(client_id, host, after, kind, exclude, observed))

    @bp.get('/api/v2/reports/flow/site-pages')
    @login_required_api
    def reports_site_pages():
        selected = _selection()
        client_id = selected['client_id']
        host, hosts = _host_param(client_id)
        if not host:
            return jsonify(hosts=[], host='', pages=[], notice='Este cliente ainda não tem um site com Super Tag. Cole a URL da página.')
        state, notice = _catalog_state(client_id, host), ''
        if state is None or state['age'] > CATALOG_TTL:
            try:
                refresh_catalog(client_id, host)
                state = _catalog_state(client_id, host)
            except Exception as failure:  # a stale catalog still answers; an empty one explains itself
                if state is None:
                    notice = 'Não foi possível ler o sitemap deste site agora. Cole a URL da página.'
                if getattr(failure, 'code', None) == 429:
                    notice = 'Atualizando o catálogo; tente novamente em instantes.'
        pages = search_pages(client_id, host, (request.args.get('q') or '')[:120])
        return jsonify(hosts=hosts, host=host, pages=pages, notice=notice,
                       page_count=state['page_count'] if state else 0, truncated=bool(state and state['truncated']))

    @bp.post('/api/v2/reports/flow/site-pages/refresh')
    @login_required_api
    def reports_site_pages_refresh():
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        host, _ = _host_param(selected['client_id'])
        if not host:
            abort(400, description='Informe um domínio do cliente.')
        count, truncated = refresh_catalog(selected['client_id'], host)
        return jsonify(host=host, page_count=count, truncated=truncated)

    @bp.post('/api/v2/reports/flow/site-pages/titles')
    @login_required_api
    def reports_site_pages_titles():
        """Fetch the real title of a few visible pages; the catalog keeps it for the next search."""
        from .reports_flow import _fetch_site_page
        payload = request.get_json(silent=True) or {}
        selected = _selection(payload)
        _write_guard(selected)
        client_id = selected['client_id']
        host, _ = _host_param(client_id)
        paths = payload.get('paths')
        if not host or not isinstance(paths, list) or not paths or len(paths) > TITLE_BATCH \
                or any(not isinstance(path, str) or not path.startswith('/') or len(path) > 500 for path in paths):
            abort(400, description='Informe até 8 caminhos do domínio.')
        known = {row['path'] for row in _rows('SELECT path FROM cadu_reports_site_pages WHERE client_id=%s AND host=%s AND path=ANY(%s) AND title_checked_at IS NULL',
                                              (client_id, host, paths))}
        todo = [path for path in paths if path in known]

        def title_of(path):
            try:
                page = _fetch_site_page(f"https://{host}{'' if path == '/' else path}", host)
            except Exception:
                page = None
            return path, ' '.join(((page or {}).get('title') or (page or {}).get('h1') or '').split())[:500]

        results = []
        if todo and _slots.acquire(blocking=False):
            try:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(title_of, todo))
            finally:
                _slots.release()
        for path, title in results:
            _rows('UPDATE cadu_reports_site_pages SET title=%s,title_checked_at=NOW() WHERE client_id=%s AND host=%s AND path=%s',
                  (title or None, client_id, host, path))
        get_db().commit()
        rows = _rows('SELECT host,path,name,title FROM cadu_reports_site_pages WHERE client_id=%s AND host=%s AND path=ANY(%s)', (client_id, host, paths))
        return jsonify(pages=[{**row, 'url': f"https://{row['host']}{'' if row['path'] == '/' else row['path']}"} for row in rows])
