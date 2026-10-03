"""Site & Jornada: client-wide navigation and conversions read from the Super Tag events.

Both endpoints use the same window and event table as the Páginas domain overview, so the numbers of every Site &
Jornada tab agree. They only aggregate what is already collected; no new pipeline is involved.
"""
import re
import uuid
from datetime import datetime, timedelta

from flask import abort, jsonify, request

from ..auth import login_required_api
from .reports_page_metrics import RETENTION_DAYS, pct
from .reports_flow_metrics import (NOT_SEARCH, PLATFORM_ALIASES, PLATFORM_LABELS, SEARCH_ENGINES, origin_platform, parse_origin,
                                   search_engine_for_host, search_engine_label)
from .reports_page_identity import sql_normalized_path
from .reports_pages import EVENT_TABLE, _window
from .reports_v1 import _column_exists, _rows, _selection

NAVIGATION_LIMIT = 25
PAGES_LIMIT = 100
SEQUENCE_DEPTH = 5          # pages kept per visit in "Caminhos completos"
SEQUENCES_LIMIT = 20
MIN_SESSIONS = 30           # below this the tab says the sample is small
RATE_MIN_BASE = 10          # a page rate needs at least this many views, entries or sessions behind it
_PATH = sql_normalized_path('e.page_path')
_SCOPE = f'''FROM {EVENT_TABLE} e JOIN cadu_reports_supertag_sites s ON s.id=e.site_id
    WHERE s.client_id=%(client)s AND s.revoked_at IS NULL AND e.expires_at>NOW()
        AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s'''

# Device class from the viewport width of the first view (the tag does not collect the user agent): phone < 768 px,
# tablet < 1024 px (the same line the heatmap uses between phone and desktop), desktop above; no width = unknown.
CHANNEL_DEVICES = ('mobile', 'tablet', 'desktop', 'unknown')
DEVICE_LABELS = {'mobile': 'Celular', 'tablet': 'Tablet', 'desktop': 'Computador', 'unknown': 'Não identificado'}
DEVICE_SQL = ("CASE WHEN {width} IS NULL OR {width}<=0 THEN 'unknown' WHEN {width}<768 THEN 'mobile' "
              "WHEN {width}<1024 THEN 'tablet' ELSE 'desktop' END")
CHANNEL_CAMPAIGNS = 5       # campaigns kept per channel
CHANNEL_LANDINGS = 3        # landing pages kept per channel
ROLE_MIN_VIEWS = 5          # a page needs this many views before it is given a role

# Origin of a session, read from its first page view. The groups answer "where did this visit come from?" without
# mixing two very different cases: Direto (no campaign tag, no click id and no referrer at all) and Origem desconhecida
# (the first view we have was referred by the site itself, so the real landing — and its origin — was not captured:
# the session started before the period, the landing view was lost or the tag only runs on some pages).
ORIGIN_GROUPS = ('direct', 'google_ads', 'organic', 'social', 'referral', 'other', 'unknown')
ORIGIN_LABELS = {'direct': 'Direto', 'google_ads': 'Google Ads', 'organic': 'Orgânico', 'social': 'Social',
                 'referral': 'Referência', 'other': 'Outros', 'unknown': 'Origem desconhecida'}
ORIGIN_HINTS = {
    'direct': 'Sem UTM, sem identificador de clique e sem site de origem: endereço digitado, favorito ou app que esconde a origem.',
    'google_ads': 'utm_source do Google (exceto medium orgânico), gclid/gbraid/wbraid ou referência de googleadservices/doubleclick.',
    'organic': 'Vindo de um buscador (Google, Bing…) sem marca de anúncio, ou utm_medium organic/seo.',
    'social': 'Redes sociais, por UTM (facebook, instagram, linkedin…), fbclid ou referência dessas redes.',
    'referral': 'Outro site com link para o seu, sem UTM.',
    'other': 'Campanhas com UTM fora dos grupos acima (e-mail, WhatsApp, SMS, parceiros…).',
    'unknown': 'A primeira página vista na sessão veio do próprio site: a entrada real não foi registrada (sessão iniciada antes do período ou página sem a Super Tag).',
}
_GOOGLE_SOURCES = frozenset(PLATFORM_ALIASES['google'])
_SOCIAL_SOURCES = frozenset(set().union(*(PLATFORM_ALIASES[key] for key in ('meta', 'tiktok', 'linkedin', 'youtube')))
                            | {'twitter', 'x', 'pinterest', 'threads', 'reddit', 'kwai'})
_ORGANIC_MEDIUMS = frozenset({'organic', 'organico', 'seo'})
_SOCIAL_MEDIUMS = frozenset({'social', 'social-media', 'social_media', 'socialmedia', 'paid_social', 'paid-social', 'paidsocial', 'sm'})
_GOOGLE_ADS_DOMAINS = ('googleadservices.com', 'doubleclick.net', 'googlesyndication.com', 'syndicatedsearch.goog')
_SEARCH_DOMAINS = tuple(domain for _, domains in SEARCH_ENGINES.values() for domain in domains)
_SEARCH_APPS = ('com.google.android.googlequicksearchbox',)
_SOCIAL_DOMAINS = ('facebook.com', 'fb.com', 'fb.me', 'messenger.com', 'instagram.com', 'linkedin.com', 'lnkd.in', 't.co',
                   'twitter.com', 'x.com', 'tiktok.com', 'youtube.com', 'youtu.be', 'pinterest.com', 'threads.net', 'reddit.com')


def _bare_origin_host(value):
    return str(value or '').lower().strip(' .').removeprefix('www.')


def _domain_in(host, domains):
    return any(host == domain or host.endswith('.' + domain) for domain in domains)


def _host_origin(host, site_host=''):
    if site_host and (host == site_host or host.endswith('.' + site_host) or site_host.endswith('.' + host)):
        return 'unknown'
    if _domain_in(host, _GOOGLE_ADS_DOMAINS):
        return 'google_ads'
    if (_domain_in(host, _SEARCH_DOMAINS) and not host.startswith(NOT_SEARCH)) or host in _SEARCH_APPS:
        return 'organic'
    if _domain_in(host, _SOCIAL_DOMAINS):
        return 'social'
    return 'referral'


def origin_group(utm_source=None, utm_medium=None, click_id=None, referrer_host=None, site_host=None):
    """Origin group of a session from its first page view. Mirrored in SQL by origin_group_sql (keep both in step)."""
    source, medium = str(utm_source or '').strip().lower(), str(utm_medium or '').strip().lower()
    if source or medium:
        if source in _GOOGLE_SOURCES:
            return 'organic' if medium in _ORGANIC_MEDIUMS else 'google_ads'
        if source in _SOCIAL_SOURCES or medium in _SOCIAL_MEDIUMS:
            return 'social'
        if medium in _ORGANIC_MEDIUMS:
            return 'organic'
        # utm_source=chatgpt.com or utm_medium=referral: the source names a site, so it reads like a referrer.
        if medium == 'referral' or (not medium and '.' in source):
            return _host_origin(_bare_origin_host(source))
        return 'other'
    click = str(click_id or '').strip()
    if click:
        return 'social' if click.startswith('Iw') else 'google_ads'   # fbclid values start with "Iw"; gclid-like otherwise
    referrer = _bare_origin_host(referrer_host)
    if referrer:
        return _host_origin(referrer, _bare_origin_host(site_host))
    return 'direct'


def _sql_in(values):
    return ','.join("'" + value.replace("'", "''") + "'" for value in sorted(values))


def _sql_domains(domains):
    return "'(^|\\.)(" + '|'.join(re.escape(domain) for domain in domains) + ")$'"


def _sql_bare(expression):
    return f"REGEXP_REPLACE(BTRIM(LOWER(COALESCE({expression},'')),' .'),'^www\\.','')"


def _sql_host_origin(host, site=None):
    own = (f"WHEN {site}<>'' AND ({host}={site} OR RIGHT({host},LENGTH({site})+1)='.'||{site} "
           f"OR RIGHT({site},LENGTH({host})+1)='.'||{host}) THEN 'unknown' ") if site else ''
    not_search = "'^(" + '|'.join(re.escape(prefix.rstrip('.')) for prefix in NOT_SEARCH) + ")\\.'"
    return (f"CASE {own}WHEN {host} ~ {_sql_domains(_GOOGLE_ADS_DOMAINS)} THEN 'google_ads' "
            f"WHEN ({host} ~ {_sql_domains(_SEARCH_DOMAINS)} AND {host} !~ {not_search}) OR {host} IN ({_sql_in(_SEARCH_APPS)}) THEN 'organic' "
            f"WHEN {host} ~ {_sql_domains(_SOCIAL_DOMAINS)} THEN 'social' ELSE 'referral' END")


def origin_group_sql(attribution='attribution', referrer='referrer_host', site_host='site_host'):
    """SQL twin of origin_group over a first page view's columns."""
    source = f"LOWER(BTRIM(COALESCE({attribution}->>'utm_source','')))"
    medium = f"LOWER(BTRIM(COALESCE({attribution}->>'utm_medium','')))"
    click = f"BTRIM(COALESCE({attribution}->>'click_id',''))"
    referrer_bare, site_bare = _sql_bare(referrer), _sql_bare(site_host)
    return (f"CASE WHEN {source}<>'' OR {medium}<>'' THEN CASE "
            f"WHEN {source} IN ({_sql_in(_GOOGLE_SOURCES)}) THEN CASE WHEN {medium} IN ({_sql_in(_ORGANIC_MEDIUMS)}) THEN 'organic' ELSE 'google_ads' END "
            f"WHEN {source} IN ({_sql_in(_SOCIAL_SOURCES)}) OR {medium} IN ({_sql_in(_SOCIAL_MEDIUMS)}) THEN 'social' "
            f"WHEN {medium} IN ({_sql_in(_ORGANIC_MEDIUMS)}) THEN 'organic' "
            f"WHEN {medium}='referral' OR ({medium}='' AND POSITION('.' IN {source})>0) THEN {_sql_host_origin(_sql_bare(source))} "
            f"ELSE 'other' END "
            f"WHEN {click}<>'' THEN CASE WHEN {click} ~ '^Iw' THEN 'social' ELSE 'google_ads' END "
            f"WHEN {referrer_bare}<>'' THEN {_sql_host_origin(referrer_bare, site_bare)} "
            f"ELSE 'direct' END")


# Sessions of the period with their origin, length (page views) and whether they converted. {site} narrows to one site;
# %(origin)s (NULL = every origin) keeps only the sessions of one origin group in `scoped`.
_SESSIONS_CTE = f'''WITH ev AS (
    SELECT e.id,e.site_id,s.allowed_host AS site_host,e.session_id,e.visitor_id,e.event_kind,{_PATH} AS path,e.occurred_at,
        e.referrer_host,e.attribution,e.event_data
    {_SCOPE} AND e.event_kind IN ('page_view','conversion','page_leave') {{site}}
), firsts AS (
    SELECT DISTINCT ON (site_id,session_id) site_id,session_id,site_host,referrer_host,attribution
    FROM ev WHERE event_kind='page_view' ORDER BY site_id,session_id,occurred_at,id
), stats AS (
    SELECT site_id,session_id,COUNT(*) FILTER (WHERE event_kind='page_view') AS length,BOOL_OR(event_kind='conversion') AS converted
    FROM ev GROUP BY site_id,session_id
), sess AS (
    SELECT f.site_id,f.session_id,{origin_group_sql()} AS origin,t.length,t.converted
    FROM firsts f JOIN stats t ON t.site_id=f.site_id AND t.session_id=f.session_id
), scoped AS (SELECT * FROM sess WHERE %(origin)s::text IS NULL OR origin=%(origin)s)'''

# Page views in order inside each kept session; the first is the entry, the last the exit.
_VIEWS_CTE = _SESSIONS_CTE + ''', views AS (
    SELECT v.site_id,v.site_host AS host,v.session_id,v.visitor_id,v.path,x.length,x.converted,x.origin,
        ROW_NUMBER() OVER w AS position,LEAD(v.path) OVER w AS next_path,LAG(v.path) OVER w AS prev_path
    FROM ev v JOIN scoped x ON x.site_id=v.site_id AND x.session_id=v.session_id
    WHERE v.event_kind='page_view'
    WINDOW w AS (PARTITION BY v.site_id,v.session_id ORDER BY v.occurred_at,v.id))'''

# One line per origin group: the selector, the origin bars and (filtered in Python) the period totals.
_NAV_SUMMARY_SQL = _SESSIONS_CTE + '''
    SELECT origin,COUNT(*)::bigint AS sessions,SUM(length)::bigint AS views,
        COUNT(*) FILTER (WHERE length=1)::bigint AS single_page_sessions,
        COUNT(*) FILTER (WHERE converted)::bigint AS converted_sessions
    FROM sess GROUP BY origin'''

_NAV_PAGES_SQL = _VIEWS_CTE + ''', outcomes AS (
        SELECT v.site_id,v.path,COUNT(*) FILTER (WHERE v.event_kind='conversion')::bigint AS conversions,
            AVG(CASE WHEN v.event_data->>'duration_ms' ~ '^[0-9]{1,9}$' THEN (v.event_data->>'duration_ms')::numeric END)
                FILTER (WHERE v.event_kind='page_leave') AS avg_active_ms
        FROM ev v JOIN scoped x ON x.site_id=v.site_id AND x.session_id=v.session_id
        WHERE v.event_kind IN ('conversion','page_leave') GROUP BY v.site_id,v.path
    ), pages AS (
        SELECT site_id,host,path,COUNT(*)::bigint AS views,COUNT(DISTINCT visitor_id)::bigint AS visitors,
            COUNT(DISTINCT session_id)::bigint AS sessions,
            COUNT(DISTINCT session_id) FILTER (WHERE converted)::bigint AS converted_sessions,
            COUNT(*) FILTER (WHERE position=1)::bigint AS entries,
            COUNT(*) FILTER (WHERE position=length)::bigint AS exits,
            COUNT(*) FILTER (WHERE position=1 AND length=1)::bigint AS single_page
        FROM views GROUP BY site_id,host,path
    )
    SELECT p.*,COALESCE(o.conversions,0)::bigint AS conversions,
        ROUND(o.avg_active_ms/1000,1) AS avg_active_seconds
    FROM pages p LEFT JOIN outcomes o ON o.site_id=p.site_id AND o.path=p.path
    ORDER BY p.views DESC,p.path LIMIT %(pages)s'''

# Sessions that saw each page, by the origin group of the session: the "where do its visitors come from" split.
_NAV_PAGE_ORIGINS_SQL = _VIEWS_CTE + '''
    SELECT site_id,path,origin,COUNT(DISTINCT session_id)::bigint AS sessions
    FROM views GROUP BY site_id,path,origin'''

# Channels: one row per session with the origin, campaign, device class and landing page of its first view.
_CHANNELS_CTE = f'''WITH ev AS (
    SELECT e.site_id,s.allowed_host AS site_host,e.session_id,e.event_kind,{_PATH} AS path,e.occurred_at,e.id,
        e.referrer_host,e.attribution,e.viewport_width
    {_SCOPE} AND e.event_kind IN ('page_view','conversion') {{site}}
), firsts AS (
    SELECT DISTINCT ON (site_id,session_id) site_id,session_id,site_host,path,referrer_host,attribution,viewport_width
    FROM ev WHERE event_kind='page_view' ORDER BY site_id,session_id,occurred_at,id
), stats AS (
    SELECT site_id,session_id,COUNT(*) FILTER (WHERE event_kind='page_view') AS length,BOOL_OR(event_kind='conversion') AS converted
    FROM ev GROUP BY site_id,session_id
), chan AS (
    SELECT f.site_id,f.site_host AS host,f.path,{origin_group_sql()} AS origin,
        LOWER(BTRIM(COALESCE(f.attribution->>'utm_campaign',''))) AS campaign,
        {DEVICE_SQL.format(width='f.viewport_width')} AS device,t.length,t.converted
    FROM firsts f JOIN stats t ON t.site_id=f.site_id AND t.session_id=f.session_id
)'''
_CHANNELS_SUMMARY_SQL = _CHANNELS_CTE + '''
    SELECT origin,COUNT(*)::bigint AS sessions,SUM(length)::bigint AS views,
        COUNT(*) FILTER (WHERE length=1)::bigint AS single_page_sessions,
        COUNT(*) FILTER (WHERE converted)::bigint AS converted_sessions
    FROM chan GROUP BY origin'''
_CHANNELS_DEVICES_SQL = _CHANNELS_CTE + '''
    SELECT origin,device,COUNT(*)::bigint AS sessions,COUNT(*) FILTER (WHERE converted)::bigint AS converted_sessions
    FROM chan GROUP BY origin,device'''
_CHANNELS_CAMPAIGNS_SQL = _CHANNELS_CTE + '''
    SELECT origin,campaign,COUNT(*)::bigint AS sessions,COUNT(*) FILTER (WHERE converted)::bigint AS converted_sessions
    FROM chan WHERE campaign<>'' GROUP BY origin,campaign'''
_CHANNELS_LANDINGS_SQL = _CHANNELS_CTE + '''
    SELECT origin,site_id,host,path,COUNT(*)::bigint AS sessions,COUNT(*) FILTER (WHERE converted)::bigint AS converted_sessions
    FROM chan GROUP BY origin,site_id,host,path'''

_NAV_PATHS_SQL = _VIEWS_CTE + '''
    SELECT host,path AS from_path,next_path AS to_path,COUNT(DISTINCT (site_id,session_id))::bigint AS sessions
    FROM views WHERE next_path IS NOT NULL AND next_path<>path
    GROUP BY host,path,next_path ORDER BY sessions DESC,from_path,to_path LIMIT %(limit)s'''

# Whole visits as page sequences: reloads of the same page collapse into one step, the first %(depth)s steps are kept
# and sessions that went further count as `continued`. Conversion = the session converted at some point.
_NAV_SEQUENCES_SQL = _VIEWS_CTE + ''', steps AS (
        SELECT site_id,host,session_id,converted,path,ROW_NUMBER() OVER (PARTITION BY site_id,session_id ORDER BY position) AS step
        FROM views WHERE prev_path IS DISTINCT FROM path
    ), journeys AS (
        SELECT site_id,host,session_id,BOOL_OR(converted) AS converted,COUNT(*) AS steps,
            ARRAY_AGG(path ORDER BY step) FILTER (WHERE step<=%(depth)s) AS pages
        FROM steps GROUP BY site_id,host,session_id HAVING COUNT(*)>=2
    )
    SELECT site_id,host,pages,COUNT(*)::bigint AS sessions,COUNT(*) FILTER (WHERE converted)::bigint AS converted_sessions,
        COUNT(*) FILTER (WHERE steps>%(depth)s)::bigint AS continued
    FROM journeys GROUP BY site_id,host,pages ORDER BY sessions DESC,converted_sessions DESC,pages LIMIT %(sequences)s'''

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

# Conteúdos: a site section (first path segment) is the editorial unit until content gets its own entity.
_SECTION = "CASE WHEN {path}='/' THEN '/' ELSE '/'||SPLIT_PART(LTRIM({path},'/'),'/',1) END"
_CONTENT_SQL = f'''WITH ev AS (
        SELECT e.site_id,s.allowed_host AS host,{_PATH} AS path,e.session_id,e.visitor_id,e.event_kind
        {_SCOPE} AND e.event_kind IN ('page_view','conversion')
    ), converted AS (SELECT DISTINCT site_id,session_id FROM ev WHERE event_kind='conversion'
    ), sections AS (
        SELECT site_id,host,{_SECTION.format(path='path')} AS section,path,session_id,visitor_id FROM ev WHERE event_kind='page_view'
    ), ranked AS (
        SELECT site_id,section,path,ROW_NUMBER() OVER (PARTITION BY site_id,section ORDER BY COUNT(*) DESC) AS rn
        FROM sections GROUP BY site_id,section,path
    )
    SELECT x.site_id,x.host,x.section,COUNT(*)::bigint AS views,COUNT(DISTINCT x.session_id)::bigint AS sessions,
        COUNT(DISTINCT x.visitor_id)::bigint AS visitors,COUNT(DISTINCT x.path)::int AS pages,
        COUNT(DISTINCT x.session_id) FILTER (WHERE c.session_id IS NOT NULL)::bigint AS converted_sessions,
        (SELECT r.path FROM ranked r WHERE r.site_id=x.site_id AND r.section=x.section AND r.rn=1) AS top_path
    FROM sections x LEFT JOIN converted c ON c.site_id=x.site_id AND c.session_id=x.session_id
    GROUP BY x.site_id,x.host,x.section ORDER BY views DESC LIMIT 60'''
_CONTENT_PAID_SQL = f'''SELECT l.page_host AS host,{_SECTION.format(path="NULLIF(RTRIM(LOWER(l.page_path),'/'),'')")} AS section,
        ARRAY_AGG(DISTINCT l.campaign_name) AS campaigns,SUM(l.clicks)::bigint AS clicks,SUM(l.cost_micros)::bigint AS cost_micros
    FROM cadu_reports_gads_landing_page_daily l
    WHERE l.client_id=%(client)s AND l.metric_date>=%(since)s::date AND l.metric_date<%(until)s::date
    GROUP BY 1,2'''

_CRM_SQL = '''SELECT conversion_kind AS kind,COUNT(*)::bigint AS total
    FROM cadu_reports_external_conversions
    WHERE client_id=%(client)s AND occurred_at>=%(since)s AND occurred_at<%(until)s
    GROUP BY conversion_kind'''


# Heatmap: one device class at a time. Celular groups phones and tablets (viewport < 1024 px), because the capture taken
# for it is the phone layout and tablets are too few to deserve a tab of their own; Computador is >= 1024 px. Events
# without a viewport width are left out (no device to place them on).
HEATMAP_DEVICES = {'desktop': 'e.viewport_width>=1024', 'mobile': 'e.viewport_width<1024'}
_DEPTH = "CASE WHEN e.event_data->>'depth' ~ '^[0-9]{1,3}$' THEN (e.event_data->>'depth')::int END"
_HEATMAP_PAGES_SQL = f'''SELECT * FROM (
    SELECT e.site_id,s.allowed_host AS host,{_PATH} AS path,
        COUNT(*) FILTER (WHERE e.event_kind='page_view')::bigint AS views,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='page_view')::bigint AS sessions,
        COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click'))::bigint AS clicks,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='scroll_depth' AND {_DEPTH}>=25)::bigint AS scroll_25,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='scroll_depth' AND {_DEPTH}>=50)::bigint AS scroll_50,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='scroll_depth' AND {_DEPTH}>=75)::bigint AS scroll_75,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='scroll_depth' AND {_DEPTH}>=100)::bigint AS scroll_100
    {_SCOPE} AND e.event_kind IN ('page_view','click','whatsapp_click','scroll_depth') AND ({{device}}) {{site}}
    GROUP BY e.site_id,s.allowed_host,{_PATH}) pages
    WHERE views>0 AND clicks>0
    ORDER BY clicks DESC,views DESC,path LIMIT %(pages)s'''


def heatmap_pages(rows):
    """Pages with both views and clicks on the device; the scroll reach is a share of the sessions that viewed the page."""
    out = []
    for row in rows:
        views, clicks, sessions = int(row.get('views') or 0), int(row.get('clicks') or 0), int(row.get('sessions') or 0)
        if views <= 0 or clicks <= 0:
            continue
        out.append({'site_id': str(row['site_id']), 'host': row['host'], 'path': row['path'], 'views': views, 'sessions': sessions,
                    'clicks': clicks, **{f'scroll_{depth}': pct(int(row.get(f'scroll_{depth}') or 0), sessions) for depth in (25, 50, 75, 100)}})
    return sorted(out, key=lambda item: (-item['clicks'], -item['views'], item['path']))


HEAT_COLUMNS, HEAT_ROWS = 40, 120       # whole-document click grid of the heatmap: ~32 px columns at 1280 px, ~25 px rows on a 3000 px page
TOP_ELEMENTS = 10
ZONES = (('Topo', '0–25%'), ('Meio alto', '25–50%'), ('Meio baixo', '50–75%'), ('Fim', '75–100%'))
DEVICE_CLASSES = (('desktop', 'Computador'), ('mobile', 'Celular'), ('tablet', 'Tablet'))
ELEMENT_KIND_LABELS = {'link': 'Link', 'button': 'Botão', 'icon': 'Ícone', 'image': 'Imagem', 'element': 'Elemento'}

_ONE_PAGE = f"{_SCOPE} AND e.site_id=%(site)s::uuid AND {_PATH}=%(path)s"
_HEAT_SUMMARY_SQL = f'''SELECT COUNT(*) FILTER (WHERE e.event_kind='page_view')::bigint AS views,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='page_view')::bigint AS sessions,
        COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click'))::bigint AS clicks,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='scroll_depth' AND {_DEPTH}>=25)::bigint AS scroll_25,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='scroll_depth' AND {_DEPTH}>=50)::bigint AS scroll_50,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='scroll_depth' AND {_DEPTH}>=75)::bigint AS scroll_75,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='scroll_depth' AND {_DEPTH}>=100)::bigint AS scroll_100
    {_ONE_PAGE} AND e.event_kind IN ('page_view','click','whatsapp_click','scroll_depth') AND ({{device}})'''
_HEAT_GRID_SQL = f'''SELECT FLOOR((e.event_data->>'dx')::numeric*{HEAT_COLUMNS}/1001)::int AS cx,
        FLOOR((e.event_data->>'dy')::numeric*{HEAT_ROWS}/1001)::int AS cy, COUNT(*)::bigint AS clicks
    {_ONE_PAGE} AND e.event_kind IN ('click','whatsapp_click') AND ({{device}})
        AND e.event_data->>'dx' ~ '^[0-9]{{1,4}}$' AND e.event_data->>'dy' ~ '^[0-9]{{1,4}}$'
    GROUP BY 1,2'''
_HEAT_ELEMENTS_SQL = f'''SELECT e.event_data->>'element_id' AS element_id,e.event_data->>'el_label' AS label,
        e.event_data->>'el_kind' AS kind,COUNT(*)::bigint AS clicks
    {_ONE_PAGE} AND e.event_kind IN ('click','whatsapp_click') AND ({{device}})
    GROUP BY 1,2,3'''
_HEAT_DEVICES_SQL = f'''SELECT CASE WHEN e.viewport_width<768 THEN 'mobile' WHEN e.viewport_width<1024 THEN 'tablet'
        ELSE 'desktop' END AS device,
        COUNT(*) FILTER (WHERE e.event_kind='page_view')::bigint AS views,
        COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click'))::bigint AS clicks
    {_ONE_PAGE} AND e.event_kind IN ('page_view','click','whatsapp_click') AND e.viewport_width IS NOT NULL
    GROUP BY 1'''


def heat_grid(rows):
    """Sparse whole-document grid: [column, row, clicks] for every non-empty cell, the peak and the total."""
    cells = {}
    for row in rows:
        x, y = int(row['cx']), int(row['cy'])
        if 0 <= x < HEAT_COLUMNS and 0 <= y < HEAT_ROWS:
            cells[(x, y)] = cells.get((x, y), 0) + int(row['clicks'])
    points = [[x, y, value] for (x, y), value in sorted(cells.items())]
    return {'columns': HEAT_COLUMNS, 'rows': HEAT_ROWS, 'points': points,
            'peak': max(cells.values(), default=0), 'total': sum(cells.values())}


def heat_zones(grid):
    """Clicks in each quarter of the page height, so the zones and the scroll reach read on the same scale."""
    per_zone = [0] * len(ZONES)
    for _, y, value in grid['points']:
        per_zone[min(y * len(ZONES) // grid['rows'], len(ZONES) - 1)] += value
    return [{'label': label, 'range': span, 'clicks': clicks, 'share': pct(clicks, grid['total'])}
            for (label, span), clicks in zip(ZONES, per_zone)]


def heat_elements(rows, total_clicks):
    """Most clicked elements: a marked element (data-cadu-element) by its id, any other by its name and type.

    Clicks without a name (older tags, or a name dropped as personal data) are only counted, never guessed.
    """
    groups, unnamed = {}, 0
    for row in rows:
        clicks = int(row['clicks'])
        element_id, label, kind = row.get('element_id'), (row.get('label') or '').strip(), row.get('kind')
        if not element_id and not label:
            unnamed += clicks
            continue
        key = ('id', element_id) if element_id else ('label', label, kind)
        item = groups.setdefault(key, {'element_id': element_id, 'label': label or element_id, 'kind': kind, 'clicks': 0})
        item['clicks'] += clicks
        if label and item['label'] == element_id:
            item['label'] = label
    items = sorted(groups.values(), key=lambda item: (-item['clicks'], item['label']))
    for item in items:
        item['kind_label'] = ELEMENT_KIND_LABELS.get(item['kind'])
        item['share'] = pct(item['clicks'], total_clicks)
    return {'items': items[:TOP_ELEMENTS], 'named': len(items), 'unnamed_clicks': unnamed, 'unnamed_share': pct(unnamed, total_clicks)}


def heat_devices(rows):
    """Views and clicks of the page on each device class, in a fixed order and with zeros."""
    by_device = {row['device']: row for row in rows}
    views_total = sum(int(row['views'] or 0) for row in rows)
    out = []
    for key, label in DEVICE_CLASSES:
        row = by_device.get(key, {})
        views, clicks = int(row.get('views') or 0), int(row.get('clicks') or 0)
        out.append({'device': key, 'label': label, 'views': views, 'clicks': clicks, 'share': pct(views, views_total),
                    'clicks_per_view': round(clicks / views, 2) if views else None})
    return out


def heat_summary(row):
    sessions = int(row.get('sessions') or 0)
    return {'views': int(row.get('views') or 0), 'sessions': sessions, 'clicks': int(row.get('clicks') or 0),
            **{f'scroll_{depth}': pct(int(row.get(f'scroll_{depth}') or 0), sessions) for depth in (25, 50, 75, 100)}}


def _rate(part, base):
    """Percent of a base big enough to mean something; None below RATE_MIN_BASE (the count is still shown)."""
    return pct(part, base) if base >= RATE_MIN_BASE else None


def origin_groups(rows):
    """Every origin group, in a fixed order and with zeros, so Direto and Origem desconhecida are always explicit."""
    by_origin = {row.get('origin'): row for row in rows}
    total = sum(int(row.get('sessions') or 0) for row in rows)
    out = []
    for group in ORIGIN_GROUPS:
        row = by_origin.get(group, {})
        sessions, converted = int(row.get('sessions') or 0), int(row.get('converted_sessions') or 0)
        out.append({'origin': group, 'label': ORIGIN_LABELS[group], 'hint': ORIGIN_HINTS[group], 'sessions': sessions,
                    'converted_sessions': converted, 'share': pct(sessions, total), 'conversion_rate': _rate(converted, sessions)})
    return out


def navigation_totals(rows, origin=None):
    """Totals of one origin group (or all) from the per-origin summary."""
    keys = ('sessions', 'views', 'single_page_sessions', 'converted_sessions')
    kept = [row for row in rows if origin is None or row.get('origin') == origin]
    return {key: sum(int(row.get(key) or 0) for row in kept) for key in keys}


def previous_window(since, until):
    """The period of the same length right before [since, until)."""
    return since - (until - since), since


def _change(current, previous):
    return round((current - previous) * 100 / previous, 1) if previous else None


def navigation_changes(totals, previous):
    """Change against the previous period, only when both periods have a usable sample."""
    if not previous or totals['sessions'] < MIN_SESSIONS or previous['sessions'] < MIN_SESSIONS:
        return None
    ratio = lambda data, key: data[key] / data['sessions']
    return {'sessions': _change(totals['sessions'], previous['sessions']),
            'views_per_session': _change(ratio(totals, 'views'), ratio(previous, 'views')),
            'single_page_rate': _change(ratio(totals, 'single_page_sessions'), ratio(previous, 'single_page_sessions')),
            'conversion_rate': _change(ratio(totals, 'converted_sessions'), ratio(previous, 'converted_sessions'))}


def navigation_pages(rows, totals):
    """Pages with exit and entry-bounce rates on a usable base; `leak` marks pages that lose many visits and convert little:
    exit rate above the site's (sessions / views) and session conversion under half of the site's."""
    sessions, views = totals.get('sessions') or 0, totals.get('views') or 0
    site_exit = sessions / views if views else None
    site_conversion = (totals.get('converted_sessions') or 0) / sessions if sessions else None
    out = []
    for row in rows:
        page_views, entries, exits = int(row.get('views') or 0), int(row.get('entries') or 0), int(row.get('exits') or 0)
        page_sessions, converted = int(row.get('sessions') or 0), int(row.get('converted_sessions') or 0)
        item = {**row, 'site_id': str(row['site_id']), 'views': page_views, 'entries': entries, 'exits': exits,
                'sessions': page_sessions, 'converted_sessions': converted, 'single_page': int(row.get('single_page') or 0),
                'conversions': int(row.get('conversions') or 0),
                'avg_active_seconds': float(row['avg_active_seconds']) if row.get('avg_active_seconds') is not None else None,
                # exit_rate stays a number for the pages list; small_base says whether it can be read.
                'exit_rate': round(exits * 100 / (page_views or 1), 1), 'small_base': page_views < RATE_MIN_BASE,
                'bounce_rate': _rate(int(row.get('single_page') or 0), entries),
                'conversion_rate': _rate(converted, page_sessions)}
        item['leak'] = bool(not item['small_base'] and exits >= RATE_MIN_BASE // 2 and site_exit is not None
                            and exits / page_views > site_exit and site_conversion is not None
                            and page_sessions and converted / page_sessions < site_conversion / 2)
        out.append(item)
    return out


def page_role(item):
    """What the page does in a visit: converts, opens visits, closes them or just passes people along. None on a small base."""
    views, entries, exits = item['views'], item['entries'], item['exits']
    if views < ROLE_MIN_VIEWS:
        return None
    if item['conversions'] or item['converted_sessions']:
        return 'conversion'
    if entries * 2 >= views:
        return 'entry'
    if exits * 2 >= views:
        return 'exit'
    return 'transit'


def attach_page_origins(pages, rows):
    """Adds `origins` (sessions of the page by origin group, biggest first) and the page's role."""
    by_page = {}
    for row in rows:
        by_page.setdefault((str(row['site_id']), row['path']), []).append(row)
    for page in pages:
        lines = sorted(by_page.get((page['site_id'], page['path']), []), key=lambda row: -int(row['sessions']))
        total = sum(int(row['sessions']) for row in lines)
        page['origins'] = [{'origin': row['origin'], 'label': ORIGIN_LABELS.get(row['origin'], row['origin']),
                            'sessions': int(row['sessions']), 'share': pct(int(row['sessions']), total)} for row in lines[:3]]
        page['role'] = page_role(page)
    return pages


def channel_rows(summary, devices, campaigns, landings):
    """One entry per origin group (fixed order, zeros kept): volume, conversion, device split, campaigns and landing pages."""
    total = sum(int(row.get('sessions') or 0) for row in summary)
    by_origin = {row['origin']: row for row in summary}
    out = []
    for group in ORIGIN_GROUPS:
        row = by_origin.get(group, {})
        sessions = int(row.get('sessions') or 0)
        converted, single = int(row.get('converted_sessions') or 0), int(row.get('single_page_sessions') or 0)
        mine = lambda rows: [item for item in rows if item.get('origin') == group]
        device_lines = {item['device']: item for item in mine(devices)}
        out.append({
            'origin': group, 'label': ORIGIN_LABELS[group], 'hint': ORIGIN_HINTS[group], 'sessions': sessions,
            'share': pct(sessions, total), 'converted_sessions': converted, 'conversion_rate': _rate(converted, sessions),
            'views_per_session': round(int(row.get('views') or 0) / sessions, 1) if sessions else None,
            'single_page_rate': _rate(single, sessions),
            'devices': [{'device': device, 'label': DEVICE_LABELS[device], 'sessions': int(device_lines[device]['sessions']),
                         'share': pct(int(device_lines[device]['sessions']), sessions)}
                        for device in CHANNEL_DEVICES if device in device_lines],
            'campaigns': [{'name': item['campaign'], 'sessions': int(item['sessions']), 'converted_sessions': int(item['converted_sessions']),
                           'conversion_rate': _rate(int(item['converted_sessions']), int(item['sessions']))}
                          for item in sorted(mine(campaigns), key=lambda item: (-int(item['sessions']), item['campaign']))[:CHANNEL_CAMPAIGNS]],
            'landings': [{'site_id': str(item['site_id']), 'host': item['host'], 'path': item['path'], 'sessions': int(item['sessions']),
                          'converted_sessions': int(item['converted_sessions'])}
                         for item in sorted(mine(landings), key=lambda item: (-int(item['sessions']), item['path']))[:CHANNEL_LANDINGS]],
        })
    return out


def path_sequences(rows, sessions):
    """Most common whole visits (2 to SEQUENCE_DEPTH pages) with their share of sessions and conversion."""
    out = []
    for row in rows:
        pages = [str(path) for path in (row.get('pages') or [])]
        if len(pages) < 2:
            continue
        count, converted = int(row.get('sessions') or 0), int(row.get('converted_sessions') or 0)
        out.append({'site_id': str(row['site_id']), 'host': row['host'], 'pages': pages, 'sessions': count,
                    'converted_sessions': converted, 'continued': int(row.get('continued') or 0),
                    'share': pct(count, sessions), 'conversion_rate': _rate(converted, count)})
    return out


def _site_param():
    raw = request.args.get('site_id', '').strip()
    if not raw:
        return None
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        abort(400, description='Site inválido.')


def _one_site(sql, site):
    """Narrows a query built on ``_SCOPE`` to one site."""
    return sql.replace(_SCOPE, _SCOPE + ' AND e.site_id=%(site)s::uuid') if site else sql


def _by_platform(rows, *fields):
    """Sessions per platform; organic search also keeps one line per engine (Google, Bing…)."""
    out = {}
    for row in rows:
        platform = origin_platform(row.get('origin'))
        bucket = out.setdefault(platform, {'platform': platform, 'label': PLATFORM_LABELS.get(platform, platform),
                                           **{field: 0 for field in fields}})
        for field in fields:
            bucket[field] += int(row.get(field) or 0)
        if platform == 'organic':
            engine = search_engine_for_host(parse_origin(row.get('origin'))[1]) or 'other'
            line = bucket.setdefault('engines', {}).setdefault(engine, {'engine': engine, 'label': search_engine_label(engine) if engine != 'other' else 'Outros buscadores',
                                                                      **{field: 0 for field in fields}})
            for field in fields:
                line[field] += int(row.get(field) or 0)
    for bucket in out.values():
        if 'engines' in bucket:
            bucket['engines'] = sorted(bucket['engines'].values(), key=lambda item: -item[fields[0]])
    return sorted(out.values(), key=lambda item: -item[fields[0]])


def _window_json(since, until, days):
    return {'days': days, 'since': since, 'until': until, 'timezone': 'America/Sao_Paulo'}


def _bare_host(host):
    return (host or '').lower().removeprefix('www.')


def register(bp):
    @bp.get('/api/v2/reports/journey/content')
    @login_required_api
    def reports_journey_content():
        """Sections of each site with reach, conversion influence and the paid campaigns that land on them."""
        selected = _selection()
        since, until, days = _window()
        site = _site_param()
        scope = {'client': selected['client_id'], 'since': since, 'until': until, 'site': site}
        sections = _rows(_one_site(_CONTENT_SQL, site), scope)
        paid_ready = _rows("SELECT to_regclass('public.cadu_reports_gads_landing_page_daily') IS NOT NULL AS ready")[0]['ready']
        paid = {(_bare_host(row['host']), row['section'] or '/'): row for row in (_rows(_CONTENT_PAID_SQL, scope) if paid_ready else [])}
        for row in sections:
            row['site_id'] = str(row['site_id'])
            match = paid.get((_bare_host(row['host']), row['section']))
            row['campaigns'] = sorted(match['campaigns'])[:5] if match else []
            row['paid_clicks'] = int(match['clicks']) if match else 0
        return jsonify(window=_window_json(since, until, days), sections=sections)

    @bp.get('/api/v2/reports/journey/navigation')
    @login_required_api
    def reports_journey_navigation():
        """Pages with entries and exits, steps and whole visits, read for every origin or one origin group, with the
        previous period of the same length for the totals."""
        selected = _selection()
        since, until, days = _window()
        origin = request.args.get('origin', '').strip() or None
        if origin is not None and origin not in ORIGIN_GROUPS:
            abort(400, description='Origem inválida.')
        site = _site_param()
        scope = {'client': selected['client_id'], 'since': since, 'until': until, 'limit': NAVIGATION_LIMIT,
                 'pages': PAGES_LIMIT, 'depth': SEQUENCE_DEPTH, 'sequences': SEQUENCES_LIMIT, 'origin': origin, 'site': site}
        narrow = (lambda sql: sql.replace('{site}', 'AND e.site_id=%(site)s::uuid' if site else ''))
        summary = _rows(narrow(_NAV_SUMMARY_SQL), scope)
        totals = navigation_totals(summary, origin)
        previous_since, previous_until = previous_window(since, until)
        previous = None
        if previous_since >= datetime.now(since.tzinfo) - timedelta(days=RETENTION_DAYS):
            previous = navigation_totals(_rows(narrow(_NAV_SUMMARY_SQL), {**scope, 'since': previous_since, 'until': previous_until}), origin)
        pages = attach_page_origins(navigation_pages(_rows(narrow(_NAV_PAGES_SQL), scope), totals),
                                    _rows(narrow(_NAV_PAGE_ORIGINS_SQL), scope))
        groups = origin_groups(summary)
        return jsonify(window=_window_json(since, until, days),
                       previous_window=_window_json(previous_since, previous_until, days) if previous else None,
                       origin=origin, origin_groups=groups,
                       origins=[{**item, 'platform': item['origin']} for item in sorted(groups, key=lambda item: -item['sessions']) if item['sessions']],
                       totals=totals, previous=previous, changes=navigation_changes(totals, previous),
                       quality={'min_sessions': MIN_SESSIONS, 'rate_min_base': RATE_MIN_BASE, 'low_sample': totals['sessions'] < MIN_SESSIONS},
                       pages=pages, paths=_rows(narrow(_NAV_PATHS_SQL), scope),
                       sequences=path_sequences(_rows(narrow(_NAV_SEQUENCES_SQL), scope), totals['sessions']))

    @bp.get('/api/v2/reports/journey/channels')
    @login_required_api
    def reports_journey_channels():
        """Where visits come from: per origin group, sessions, conversion, device split, campaigns and landing pages."""
        selected = _selection()
        since, until, days = _window()
        site = _site_param()
        scope = {'client': selected['client_id'], 'since': since, 'until': until, 'site': site}
        narrow = (lambda sql: sql.replace('{site}', 'AND e.site_id=%(site)s::uuid' if site else ''))
        summary = _rows(narrow(_CHANNELS_SUMMARY_SQL), scope)
        channels = channel_rows(summary, _rows(narrow(_CHANNELS_DEVICES_SQL), scope),
                                _rows(narrow(_CHANNELS_CAMPAIGNS_SQL), scope), _rows(narrow(_CHANNELS_LANDINGS_SQL), scope))
        sessions = sum(item['sessions'] for item in channels)
        converted = sum(item['converted_sessions'] for item in channels)
        return jsonify(window=_window_json(since, until, days), channels=channels,
                       totals={'sessions': sessions, 'converted_sessions': converted, 'conversion_rate': _rate(converted, sessions)},
                       quality={'min_sessions': MIN_SESSIONS, 'rate_min_base': RATE_MIN_BASE, 'low_sample': sessions < MIN_SESSIONS})

    @bp.get('/api/v2/reports/journey/conversions')
    @login_required_api
    def reports_journey_conversions():
        """Conversions observed on the site (by type, page and origin) next to the ones confirmed by the CRM."""
        selected = _selection()
        since, until, days = _window()
        site = _site_param()
        scope = {'client': selected['client_id'], 'since': since, 'until': until, 'site': site}
        name = ("COALESCE(NULLIF(e.event_name,''),e.event_kind)" if _column_exists(EVENT_TABLE, 'event_name')
                else 'e.event_kind')
        groups = _rows(_one_site(_CONV_GROUPS_SQL.format(name=name), site), scope)
        daily = [{**row, 'day': row['day'].isoformat()} for row in _rows(_one_site(_CONV_DAILY_SQL, site), scope)]
        totals = {kind: sum(int(row['total']) for row in groups if row['kind'] == kind) for kind in _CONVERSION_KINDS}
        crm_ready = _rows("SELECT to_regclass('public.cadu_reports_external_conversions') IS NOT NULL AS ready")[0]['ready']
        return jsonify(window=_window_json(since, until, days), totals=totals, groups=groups, daily=daily,
                       origins=_by_platform(_rows(_one_site(_CONV_ORIGINS_SQL, site), scope), 'sessions', 'converted'),
                       confirmed=_rows(_CRM_SQL, scope) if crm_ready else [])

    @bp.get('/api/v2/reports/journey/heatmap-detail')
    @login_required_api
    def reports_journey_heatmap_detail():
        """One page on one device in the period: fine click grid, zones, most clicked elements and device split.

        Same window and device split as heatmap-pages, so the side panel and the numbers above the capture agree.
        """
        selected = _selection()
        since, until, days = _window()
        device = request.args.get('device', 'desktop')
        if device not in HEATMAP_DEVICES:
            abort(400, description='Escolha computador ou celular.')
        site = _site_param()
        path = request.args.get('path', '')
        if not site or not path.startswith('/') or len(path) > 500 or re.search(r'\s', path):
            abort(400, description='Informe o site e o caminho da página.')
        scope = {'client': selected['client_id'], 'since': since, 'until': until, 'site': site, 'path': path}
        on_device = HEATMAP_DEVICES[device]
        summary = heat_summary((_rows(_HEAT_SUMMARY_SQL.replace('{device}', on_device), scope) or [{}])[0])
        grid = heat_grid(_rows(_HEAT_GRID_SQL.replace('{device}', on_device), scope))
        elements = heat_elements(_rows(_HEAT_ELEMENTS_SQL.replace('{device}', on_device), scope), summary['clicks'])
        return jsonify(window=_window_json(since, until, days), device=device, page={'site_id': site, 'path': path},
                       summary=summary, heat=grid, positioned_share=pct(grid['total'], summary['clicks']), zones=heat_zones(grid),
                       elements=elements, devices=heat_devices(_rows(_HEAT_DEVICES_SQL, scope)))

    @bp.get('/api/v2/reports/journey/heatmap-pages')
    @login_required_api
    def reports_journey_heatmap_pages():
        """Pages of the period with views and clicks on one device class, most clicked first, plus the price of a capture."""
        from .reports_page_captures import capture_cost_tokens
        selected = _selection()
        since, until, days = _window()
        device = request.args.get('device', 'desktop')
        if device not in HEATMAP_DEVICES:
            abort(400, description='Escolha computador ou celular.')
        site = _site_param()
        scope = {'client': selected['client_id'], 'since': since, 'until': until, 'pages': PAGES_LIMIT, 'site': site}
        sql = _HEATMAP_PAGES_SQL.replace('{device}', HEATMAP_DEVICES[device]).replace(
            '{site}', 'AND e.site_id=%(site)s::uuid' if site else '')
        return jsonify(window=_window_json(since, until, days), device=device, pages=heatmap_pages(_rows(sql, scope)),
                       cost_tokens=capture_cost_tokens(selected['client_id']))
