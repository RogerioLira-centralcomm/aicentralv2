"""Site & Jornada: client-wide navigation and conversions read from the Super Tag events.

Both endpoints use the same window and event table as the Páginas domain overview, so the numbers of every Site &
Jornada tab agree. They only aggregate what is already collected; no new pipeline is involved.
"""
from flask import jsonify

from ..auth import login_required_api
from .reports_flow_metrics import PLATFORM_LABELS, origin_platform
from .reports_page_identity import sql_normalized_path
from .reports_pages import EVENT_TABLE, _window
from .reports_v1 import _column_exists, _rows, _selection

NAVIGATION_LIMIT = 25
PAGES_LIMIT = 100
_PATH = sql_normalized_path('e.page_path')
_SCOPE = f'''FROM {EVENT_TABLE} e JOIN cadu_reports_supertag_sites s ON s.id=e.site_id
    WHERE s.client_id=%(client)s AND s.revoked_at IS NULL AND e.expires_at>NOW()
        AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s'''

# Page views in order inside each session; the first is the entry, the last the exit.
_VIEWS_CTE = f'''WITH views AS (
    SELECT e.site_id,s.allowed_host AS host,e.session_id,e.visitor_id,{_PATH} AS path,e.occurred_at,
        ROW_NUMBER() OVER (PARTITION BY e.site_id,e.session_id ORDER BY e.occurred_at,e.id) AS position,
        COUNT(*) OVER (PARTITION BY e.site_id,e.session_id) AS length,
        LEAD({_PATH}) OVER (PARTITION BY e.site_id,e.session_id ORDER BY e.occurred_at,e.id) AS next_path
    {_SCOPE} AND e.event_kind='page_view')'''

_NAV_TOTALS_SQL = _VIEWS_CTE + '''
    SELECT COUNT(DISTINCT (site_id,session_id))::bigint AS sessions,
        COUNT(*)::bigint AS views,
        COUNT(DISTINCT (site_id,session_id)) FILTER (WHERE length=1)::bigint AS single_page_sessions
    FROM views'''

_NAV_PAGES_SQL = _VIEWS_CTE + f''', outcomes AS (
        SELECT e.site_id,{_PATH} AS path,
            COUNT(*) FILTER (WHERE e.event_kind='conversion')::bigint AS conversions,
            AVG(CASE WHEN e.event_data->>'duration_ms' ~ '^[0-9]{{1,9}}$' THEN (e.event_data->>'duration_ms')::numeric END)
                FILTER (WHERE e.event_kind='page_leave') AS avg_active_ms
        {_SCOPE} AND e.event_kind IN ('conversion','page_leave') GROUP BY e.site_id,{_PATH}
    ), pages AS (
        SELECT site_id,host,path,COUNT(*)::bigint AS views,COUNT(DISTINCT visitor_id)::bigint AS visitors,
            COUNT(*) FILTER (WHERE position=1)::bigint AS entries,
            COUNT(*) FILTER (WHERE position=length)::bigint AS exits,
            COUNT(*) FILTER (WHERE position=1 AND length=1)::bigint AS single_page
        FROM views GROUP BY site_id,host,path
    )
    SELECT p.*,COALESCE(o.conversions,0)::bigint AS conversions,
        ROUND(o.avg_active_ms/1000,1) AS avg_active_seconds
    FROM pages p LEFT JOIN outcomes o ON o.site_id=p.site_id AND o.path=p.path
    ORDER BY p.views DESC LIMIT %(pages)s'''

_NAV_PATHS_SQL = _VIEWS_CTE + '''
    SELECT host,path AS from_path,next_path AS to_path,COUNT(DISTINCT session_id)::bigint AS sessions
    FROM views WHERE next_path IS NOT NULL AND next_path<>path
    GROUP BY host,path,next_path ORDER BY sessions DESC LIMIT %(limit)s'''

# Where each session came from (first page view) and the page it landed on.
_NAV_ORIGINS_SQL = f'''
    SELECT origin,COUNT(*)::bigint AS sessions FROM (
        SELECT (ARRAY_AGG(COALESCE(NULLIF('utm:'||LOWER(COALESCE(e.attribution->>'utm_source','')),'utm:'),
            NULLIF('ref:'||COALESCE(e.referrer_host,''),'ref:')) ORDER BY e.occurred_at,e.id))[1] AS origin
        {_SCOPE} AND e.event_kind='page_view' GROUP BY e.site_id,e.session_id) first_view
    GROUP BY origin'''

_CONVERSION_KINDS = ('conversion', 'form_submit', 'whatsapp_click')
# Custom names come from event_name when the column exists; older databases group by kind only.
_CONV_GROUPS_SQL = f'''
    SELECT e.event_kind AS kind,{{name}} AS name,s.allowed_host AS host,
        {_PATH} AS path,COUNT(*)::bigint AS total,COUNT(DISTINCT e.session_id)::bigint AS sessions,
        MAX(e.occurred_at) AS last_at
    {_SCOPE} AND e.event_kind IN ('conversion','form_submit','whatsapp_click')
    GROUP BY e.event_kind,{{name}},s.allowed_host,{_PATH}
    ORDER BY total DESC LIMIT 100'''

_CONV_DAILY_SQL = f'''
    SELECT (e.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date AS day,
        COUNT(*) FILTER (WHERE e.event_kind='conversion')::bigint AS conversions,
        COUNT(*) FILTER (WHERE e.event_kind='form_submit')::bigint AS form_submits,
        COUNT(*) FILTER (WHERE e.event_kind='whatsapp_click')::bigint AS whatsapp
    {_SCOPE} AND e.event_kind IN ('conversion','form_submit','whatsapp_click')
    GROUP BY day ORDER BY day'''

# Session origin for each converting session, so conversions can be read by source.
_CONV_ORIGINS_SQL = f'''
    WITH firsts AS (
        SELECT e.site_id,e.session_id,
            (ARRAY_AGG(COALESCE(NULLIF('utm:'||LOWER(COALESCE(e.attribution->>'utm_source','')),'utm:'),
                NULLIF('ref:'||COALESCE(e.referrer_host,''),'ref:')) ORDER BY e.occurred_at,e.id))[1] AS origin
        {_SCOPE} AND e.event_kind='page_view' GROUP BY e.site_id,e.session_id
    ), converted AS (
        SELECT DISTINCT e.site_id,e.session_id {_SCOPE} AND e.event_kind='conversion'
    )
    SELECT f.origin,COUNT(*)::bigint AS sessions,COUNT(c.session_id)::bigint AS converted
    FROM firsts f LEFT JOIN converted c ON c.site_id=f.site_id AND c.session_id=f.session_id
    GROUP BY f.origin'''

_CRM_SQL = '''SELECT conversion_kind AS kind,COUNT(*)::bigint AS total
    FROM cadu_reports_external_conversions
    WHERE client_id=%(client)s AND occurred_at>=%(since)s AND occurred_at<%(until)s
    GROUP BY conversion_kind'''


def _by_platform(rows, *fields):
    out = {}
    for row in rows:
        platform = origin_platform(row.get('origin'))
        bucket = out.setdefault(platform, {'platform': platform, 'label': PLATFORM_LABELS.get(platform, platform),
                                           **{field: 0 for field in fields}})
        for field in fields:
            bucket[field] += int(row.get(field) or 0)
    return sorted(out.values(), key=lambda item: -item[fields[0]])


def _window_json(since, until, days):
    return {'days': days, 'since': since, 'until': until, 'timezone': 'America/Sao_Paulo'}


def register(bp):
    @bp.get('/api/v2/reports/journey/navigation')
    @login_required_api
    def reports_journey_navigation():
        """Every page with entries, exits and conversions, the most common page-to-page steps and the visit origins."""
        selected = _selection()
        since, until, days = _window()
        scope = {'client': selected['client_id'], 'since': since, 'until': until, 'limit': NAVIGATION_LIMIT,
                 'pages': PAGES_LIMIT}
        totals = _rows(_NAV_TOTALS_SQL, scope)[0]
        pages = _rows(_NAV_PAGES_SQL, scope)
        for page in pages:
            views = int(page['views']) or 1
            page['exit_rate'] = round(int(page['exits']) * 100 / views, 1)
            page['site_id'] = str(page['site_id'])
        return jsonify(window=_window_json(since, until, days), totals=totals, pages=pages,
                       paths=_rows(_NAV_PATHS_SQL, scope),
                       origins=_by_platform(_rows(_NAV_ORIGINS_SQL, scope), 'sessions'))

    @bp.get('/api/v2/reports/journey/conversions')
    @login_required_api
    def reports_journey_conversions():
        """Conversions observed on the site (by type, page and origin) next to the ones confirmed by the CRM."""
        selected = _selection()
        since, until, days = _window()
        scope = {'client': selected['client_id'], 'since': since, 'until': until}
        name = ("COALESCE(NULLIF(e.event_name,''),e.event_kind)" if _column_exists(EVENT_TABLE, 'event_name')
                else 'e.event_kind')
        groups = _rows(_CONV_GROUPS_SQL.format(name=name), scope)
        daily = _rows(_CONV_DAILY_SQL, scope)
        totals = {kind: sum(int(row['total']) for row in groups if row['kind'] == kind) for kind in _CONVERSION_KINDS}
        crm_ready = _rows("SELECT to_regclass('public.cadu_reports_external_conversions') IS NOT NULL AS ready")[0]['ready']
        return jsonify(window=_window_json(since, until, days), totals=totals, groups=groups, daily=daily,
                       origins=_by_platform(_rows(_CONV_ORIGINS_SQL, scope), 'sessions', 'converted'),
                       confirmed=_rows(_CRM_SQL, scope) if crm_ready else [])
