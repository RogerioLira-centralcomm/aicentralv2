"""Pages of a flow, read for the people who manage the site: a usage score per page and the pages nobody visits.

Numbers come from the site's Super Tag events (the same source as Página 360 and Navegação), so a page is read the
same way everywhere, whatever revision of the flow is published. The score only uses what the tag observes about
use — active time, scroll, moving on to the next step and leaving the site — and is withheld on a small sample.
"""
from flask import abort, jsonify

from ..auth import login_required_api
from ..db import get_db
from .reports_page_identity import normalize_host, normalize_path, sql_normalized_path
from .reports_pages import EVENT_TABLE, _window
from .reports_v1 import _rows, _selection

MIN_SCORE_SESSIONS = 20      # below this a page shows its numbers but no score
IDLE_SITE_LIMIT = 300        # sitemap pages listed without traffic (the total is always returned)
PAGE_TYPES = ('page', 'form', 'conversion', 'error')
# Weights of each signal; a signal that does not apply (no next step, no scroll events) is left out and the rest
# are renormalised, so a page is never punished for what cannot be measured on it.
WEIGHTS = {'time': 25, 'scroll': 25, 'advance': 30, 'exit': 20}
TIME_FULL_SECONDS = 45       # median active time that earns the full time component
ADVANCE_FULL_RATE = .5       # half of the visits moving on to a next step earns the full advance component

_PATH = sql_normalized_path('e.page_path')
_EVENTS = ('WITH ev AS (SELECT e.id,e.session_id,e.event_kind,' + _PATH + ''' AS path,e.occurred_at,
        CASE WHEN e.event_data->>'duration_ms' ~ '^[0-9]{1,9}$' THEN (e.event_data->>'duration_ms')::numeric END AS dur,
        CASE WHEN e.event_data->>'depth' ~ '^[0-9]{1,3}$' THEN (e.event_data->>'depth')::numeric END AS depth
    FROM ''' + EVENT_TABLE + ''' e
    WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s
      AND e.event_kind IN ('page_view','page_leave','scroll_depth')
), views AS (
    SELECT session_id,path,ROW_NUMBER() OVER w AS position,COUNT(*) OVER (PARTITION BY session_id) AS length,
        LEAD(path) OVER w AS next_path
    FROM ev WHERE event_kind='page_view' WINDOW w AS (PARTITION BY session_id ORDER BY occurred_at,id)
)''')
_PAGES_SQL = _EVENTS + '''
    SELECT path,COUNT(*)::bigint AS views,COUNT(DISTINCT session_id)::bigint AS sessions,
        COUNT(*) FILTER (WHERE position=1)::bigint AS entries,COUNT(*) FILTER (WHERE position=length)::bigint AS exits,
        COUNT(*) FILTER (WHERE position=1 AND length=1)::bigint AS single_page
    FROM views GROUP BY path ORDER BY views DESC LIMIT 5000'''
_ENGAGEMENT_SQL = _EVENTS + '''
    SELECT path,PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dur) FILTER (WHERE event_kind='page_leave') AS median_active_ms,
        COUNT(*) FILTER (WHERE event_kind='page_leave' AND dur IS NOT NULL)::bigint AS measured_visits,
        COUNT(DISTINCT session_id) FILTER (WHERE event_kind='scroll_depth')::bigint AS scrolled,
        COUNT(DISTINCT session_id) FILTER (WHERE event_kind='scroll_depth' AND depth>=50)::bigint AS scroll_50,
        COUNT(DISTINCT session_id) FILTER (WHERE event_kind='scroll_depth' AND depth>=75)::bigint AS scroll_75
    FROM ev WHERE path=ANY(%(paths)s) GROUP BY path'''
_TRANSITIONS_SQL = _EVENTS + '''
    SELECT path,next_path,COUNT(DISTINCT session_id)::bigint AS sessions FROM views
    WHERE path=ANY(%(paths)s) AND next_path IS NOT NULL AND next_path<>path GROUP BY path,next_path'''


def _rate(part, base):
    return round(part * 100 / base, 1) if base else None


def usage_score(sessions, median_active_seconds=None, scroll_50=None, scroll_75=None, advance_rate=None, exit_rate=None):
    """0–100 from the signals that apply to the page; rates are percentages. None when the sample is small or no
    signal is measurable. Returns (score, components) where each component is 0–100."""
    if not sessions or sessions < MIN_SCORE_SESSIONS:
        return None, {}
    parts = {}
    if median_active_seconds is not None:
        parts['time'] = min(100.0, median_active_seconds * 100 / TIME_FULL_SECONDS)
    if scroll_50 is not None:
        parts['scroll'] = .6 * scroll_50 + .4 * (scroll_75 if scroll_75 is not None else scroll_50)
    if advance_rate is not None:
        parts['advance'] = min(100.0, advance_rate / ADVANCE_FULL_RATE)
    if exit_rate is not None:
        parts['exit'] = max(0.0, 100 - exit_rate)
    if not parts:
        return None, {}
    weight = sum(WEIGHTS[key] for key in parts)
    score = round(sum(parts[key] * WEIGHTS[key] for key in parts) / weight)
    return score, {key: round(value) for key, value in parts.items()}


def grade(score):
    if score is None:
        return None
    return 'good' if score >= 70 else 'attention' if score >= 40 else 'critical'


def _site_for(flow, client_id):
    """The Super Tag site whose events describe this flow's pages: the flow's own site, else the one on its domain."""
    rows = _rows('''SELECT id,allowed_host FROM cadu_reports_supertag_sites WHERE client_id=%s AND revoked_at IS NULL
        AND (id=%s OR LOWER(REGEXP_REPLACE(allowed_host,'^www\\.',''))=%s) ORDER BY (id=%s) DESC LIMIT 1''',
                 (client_id, flow.get('site_id'), normalize_host(flow.get('allowed_host')), flow.get('site_id')))
    return rows[0] if rows else None


def flow_page_rows(config, host, pages, engagement, transitions):
    """One line per page step of the flow (a group's pages each keep their own line)."""
    nodes = [node for node in (config.get('nodes') or []) if node.get('type') in PAGE_TYPES]
    by_id = {node['id']: node for node in config.get('nodes') or []}
    next_paths = {}
    for edge in config.get('edges') or []:
        target = by_id.get(edge.get('to'))
        if target and target.get('path') and normalize_host(target.get('host') or host) == host:
            next_paths.setdefault(edge.get('from'), []).append((normalize_path(target['path']), target))
    out = []
    for node in nodes:
        external = bool(node.get('host')) and normalize_host(node['host']) != host
        path = normalize_path(node['path']) if node.get('path') else None
        base = {'node_id': node['id'], 'title': node.get('title') or 'Página', 'type': node['type'], 'path': node.get('path'),
                'host': node.get('host') or host, 'group_id': node.get('groupId'), 'planned': node.get('status') == 'planned'}
        if external or not path:
            out.append({**base, 'status': 'external' if external else 'no_address', 'sessions': None, 'score': None})
            continue
        page, extra = pages.get(path, {}), engagement.get(path, {})
        views, sessions = int(page.get('views') or 0), int(page.get('sessions') or 0)
        entries, exits = int(page.get('entries') or 0), int(page.get('exits') or 0)
        median = float(extra['median_active_ms']) / 1000 if extra.get('median_active_ms') is not None else None
        scrolled = int(extra.get('scrolled') or 0)
        scroll_50 = _rate(int(extra.get('scroll_50') or 0), sessions) if scrolled else None
        scroll_75 = _rate(int(extra.get('scroll_75') or 0), sessions) if scrolled else None
        followers = next_paths.get(node['id'], [])
        advanced = sum(transitions.get((path, target_path), 0) for target_path, _ in followers)
        advance_rate = _rate(advanced, sessions) if followers and sessions else None
        exit_rate = _rate(exits, views)
        # A thank-you page is where a visit should end: it is read by its conversions, not by a usage score.
        score, components = (None, {}) if node['type'] == 'conversion' else usage_score(sessions, median, scroll_50, scroll_75, advance_rate, exit_rate)
        out.append({**base, 'status': 'idle' if not sessions else 'measured', 'sessions': sessions, 'views': views,
                    'median_active_seconds': round(median, 1) if median is not None else None,
                    'scroll_50': scroll_50, 'scroll_75': scroll_75, 'advance_rate': advance_rate,
                    'next_steps': [target.get('title') or target_path for target_path, target in followers],
                    'exit_rate': exit_rate, 'bounce_rate': _rate(int(page.get('single_page') or 0), entries),
                    'score': score, 'grade': grade(score), 'components': components,
                    'small_sample': 0 < sessions < MIN_SCORE_SESSIONS})
    return out


def register(bp):
    @bp.get('/api/v2/reports/flow/flows/<flow_id>/pages')
    @login_required_api
    def reports_flow_pages(flow_id):
        from .reports_flow import _flow_row
        selected = _selection()
        flow = _flow_row(flow_id, selected)
        since, until, days = _window()
        window = {'from': since.isoformat(), 'to': until.isoformat(), 'days': days}
        site = _site_for(flow, selected['client_id'])
        if not site:
            return jsonify(status='no_site', window=window, pages=[], idle={'flow': [], 'site': [], 'site_total': 0, 'catalog': False})
        host = normalize_host(site['allowed_host'])
        config = flow.get('config') or {}
        flow_paths = sorted({normalize_path(node['path']) for node in config.get('nodes') or []
                             if node.get('type') in PAGE_TYPES and node.get('path')})
        scope = {'site': str(site['id']), 'since': since, 'until': until, 'paths': flow_paths or ['']}
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '15s'")
        try:
            pages = {row['path']: row for row in _rows(_PAGES_SQL, scope)}
            engagement = {row['path']: row for row in _rows(_ENGAGEMENT_SQL, scope)} if flow_paths else {}
            transitions = {(row['path'], row['next_path']): int(row['sessions']) for row in _rows(_TRANSITIONS_SQL, scope)} if flow_paths else {}
        except Exception as failure:
            db.rollback()
            if 'statement timeout' in str(failure).lower() or 'canceling statement' in str(failure).lower():
                abort(503, description='A leitura das páginas demorou demais. Tente um período menor.')
            raise
        rows = flow_page_rows(config, host, pages, engagement, transitions)
        catalog = _rows('SELECT path,name,title FROM cadu_reports_site_pages WHERE client_id=%s AND host=%s',
                        (selected['client_id'], site['allowed_host']))
        in_flow = set(flow_paths)
        idle_site = sorted((row for row in catalog if normalize_path(row['path']) not in pages and normalize_path(row['path']) not in in_flow),
                           key=lambda row: (row['path'].count('/'), len(row['path']), row['path']))
        return jsonify(status='ready', window=window, site_id=str(site['id']), host=site['allowed_host'],
                       min_sessions=MIN_SCORE_SESSIONS, weights=WEIGHTS, pages=rows,
                       idle={'flow': [row for row in rows if row['status'] == 'idle'],
                             'site': idle_site[:IDLE_SITE_LIMIT], 'site_total': len(idle_site), 'catalog': bool(catalog)})
