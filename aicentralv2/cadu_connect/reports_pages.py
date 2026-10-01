"""Página 360: one monitored page with its numbers, paid origin and health.

Numbers come from Super Tag events scoped by site and by the canonical page identity; the paid side comes from the
Google Ads engine v2 landing-page data joined on the same ``(host, path)`` key. The two are returned side by side and
never summed: the platform counts what it billed, the tag counts what it observed.
"""
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import abort, jsonify, request

from ..auth import login_required_api
from .reports_flow_metrics import PLATFORM_LABELS, origin_platform
from .reports_page_identity import canonical_page, sql_normalized_path
from .reports_page_suggestions import MIN_TERM_CLICKS, build_suggestions
from .reports_page_metrics import (
    DEVICE_LABELS, DEVICES, DICTIONARY, MIN_RELIABLE_CLICKS, RETENTION_DAYS, breakdown, build_conversion_map, build_document_grid, build_elements,
    build_grid, build_metrics, compare, device_bucket, pct, sum_groups)
from .reports_v1 import _rows, _selection

HEALTH_TIMELINE = 30
EVENT_TABLE = 'cadu_reports_supertag_events'
_NORM_E = sql_normalized_path('e.page_path')

_COUNTS_SQL = f'''
    SELECT COUNT(*) FILTER (WHERE event_kind='page_view')::bigint AS views,
        COUNT(DISTINCT session_id) FILTER (WHERE event_kind='page_view')::bigint AS sessions,
        COUNT(DISTINCT visitor_id) FILTER (WHERE event_kind='page_view')::bigint AS visitors,
        COUNT(*) FILTER (WHERE event_kind IN ('click','whatsapp_click'))::bigint AS clicks,
        COUNT(*) FILTER (WHERE event_kind='form_submit')::bigint AS form_submits,
        COUNT(*) FILTER (WHERE event_kind='conversion')::bigint AS conversions_on_page,
        COUNT(*) FILTER (WHERE event_kind='page_leave' AND dur IS NOT NULL)::bigint AS measured_visits,
        AVG(dur) FILTER (WHERE event_kind='page_leave') AS avg_active_ms,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dur) FILTER (WHERE event_kind='page_leave') AS median_active_ms,
        COUNT(DISTINCT session_id) FILTER (WHERE event_kind='scroll_depth' AND depth>=25)::bigint AS scroll_25,
        COUNT(DISTINCT session_id) FILTER (WHERE event_kind='scroll_depth' AND depth>=50)::bigint AS scroll_50,
        COUNT(DISTINCT session_id) FILTER (WHERE event_kind='scroll_depth' AND depth>=75)::bigint AS scroll_75,
        COUNT(DISTINCT session_id) FILTER (WHERE event_kind='scroll_depth' AND depth>=100)::bigint AS scroll_100
    FROM (SELECT e.session_id,e.visitor_id,e.event_kind,
            CASE WHEN e.event_data->>'duration_ms' ~ '^[0-9]{{1,9}}$' THEN (e.event_data->>'duration_ms')::numeric END AS dur,
            CASE WHEN e.event_data->>'depth' ~ '^[0-9]{{1,3}}$' THEN (e.event_data->>'depth')::numeric END AS depth
          FROM {EVENT_TABLE} e
          WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s
            AND {_NORM_E}=%(path)s) x'''

# One row per (origin, device, campaign) group of the sessions that viewed the page.
_GROUPS_SQL = f'''
    WITH ps AS (
        SELECT DISTINCT e.session_id FROM {EVENT_TABLE} e
        WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.event_kind='page_view'
            AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s AND {_NORM_E}=%(path)s
    ), pv AS (
        SELECT e.session_id,e.occurred_at,e.id,{_NORM_E} AS np,e.attribution,e.referrer_host,e.viewport_width
        FROM {EVENT_TABLE} e JOIN ps ON ps.session_id=e.session_id
        WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.event_kind='page_view'
            AND e.occurred_at>=%(since)s - INTERVAL '1 day' AND e.occurred_at<%(until)s + INTERVAL '1 day'
    ), bounds AS (
        SELECT session_id,
            (ARRAY_AGG(np ORDER BY occurred_at,id))[1] AS first_np,
            (ARRAY_AGG(np ORDER BY occurred_at DESC,id DESC))[1] AS last_np,
            COUNT(*) AS pages,
            (ARRAY_AGG(COALESCE(NULLIF('utm:'||LOWER(COALESCE(attribution->>'utm_source','')),'utm:'),
                NULLIF('ref:'||COALESCE(referrer_host,''),'ref:')) ORDER BY occurred_at,id))[1] AS origin,
            (ARRAY_AGG(viewport_width ORDER BY occurred_at,id))[1] AS width,
            (ARRAY_AGG(LOWER(COALESCE(NULLIF(attribution->>'utm_id',''),NULLIF(attribution->>'utm_campaign',''),''))
                ORDER BY occurred_at,id))[1] AS campaign
        FROM pv GROUP BY session_id
    ), converted AS (
        SELECT DISTINCT e.session_id FROM {EVENT_TABLE} e JOIN ps ON ps.session_id=e.session_id
        WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.event_kind='conversion'
            AND e.occurred_at>=%(since)s - INTERVAL '1 day' AND e.occurred_at<%(until)s + INTERVAL '1 day'
    )
    SELECT b.origin,
        CASE WHEN b.width IS NULL THEN 'unknown' WHEN b.width<768 THEN 'mobile' WHEN b.width<1024 THEN 'tablet' ELSE 'desktop' END AS device,
        b.campaign,COUNT(*)::bigint AS sessions,
        COUNT(*) FILTER (WHERE b.first_np=%(path)s)::bigint AS entrances,
        COUNT(*) FILTER (WHERE b.last_np=%(path)s AND st.last_seen_at<NOW()-INTERVAL '30 minutes')::bigint AS exits,
        COUNT(*) FILTER (WHERE b.pages=1)::bigint AS single_page,
        COUNT(c.session_id)::bigint AS converted
    FROM bounds b
    LEFT JOIN cadu_reports_supertag_sessions st ON st.site_id=%(site)s AND st.session_id=b.session_id
    LEFT JOIN converted c ON c.session_id=b.session_id
    GROUP BY b.origin,device,b.campaign ORDER BY sessions DESC LIMIT 500'''

_PAID_SQL = '''
    SELECT l.account_id,a.name AS account_name,a.currency,l.campaign_external_id,
        (ARRAY_AGG(l.campaign_name ORDER BY l.metric_date DESC))[1] AS campaign_name,
        SUM(l.impressions)::bigint AS impressions,SUM(l.clicks)::bigint AS clicks,SUM(l.cost_micros)::bigint AS cost_micros,
        SUM(l.conversions) AS conversions,SUM(l.conversion_value_micros)::bigint AS conversion_value_micros,
        MAX(l.metric_date) AS last_date
    FROM cadu_reports_gads_landing_page_daily l JOIN cadu_reports_accounts a ON a.id=l.account_id
    WHERE l.client_id=%(client)s AND l.page_host=%(host)s AND l.page_path=%(path)s
        AND l.metric_date>=%(since_date)s AND l.metric_date<=%(until_date)s
    GROUP BY l.account_id,a.name,a.currency,l.campaign_external_id ORDER BY cost_micros DESC LIMIT 50'''

_TERMS_SQL = '''
    SELECT t.search_term,(ARRAY_AGG(t.term_status ORDER BY t.metric_date DESC))[1] AS status,
        SUM(t.impressions)::bigint AS impressions,SUM(t.clicks)::bigint AS clicks,SUM(t.cost_micros)::bigint AS cost_micros,
        SUM(t.conversions) AS conversions
    FROM cadu_reports_gads_search_term_daily t
    WHERE t.client_id=%(client)s AND t.metric_date>=%(since_date)s AND t.metric_date<=%(until_date)s
        AND (t.account_id,t.campaign_external_id) IN (SELECT u.a,u.c FROM unnest(%(accounts)s::bigint[],%(campaigns)s::text[]) AS u(a,c))
    GROUP BY t.term_hash,t.search_term ORDER BY cost_micros DESC LIMIT 10'''

_KEYWORDS_SQL = '''
    SELECT k.keyword_text,k.match_type,
        (ARRAY_AGG(k.quality_score ORDER BY k.metric_date DESC) FILTER (WHERE k.quality_score IS NOT NULL))[1] AS quality_score,
        SUM(k.impressions)::bigint AS impressions,SUM(k.clicks)::bigint AS clicks,SUM(k.cost_micros)::bigint AS cost_micros,
        SUM(k.conversions) AS conversions
    FROM cadu_reports_gads_keyword_daily k
    WHERE k.client_id=%(client)s AND k.metric_date>=%(since_date)s AND k.metric_date<=%(until_date)s
        AND (k.account_id,k.campaign_external_id) IN (SELECT u.a,u.c FROM unnest(%(accounts)s::bigint[],%(campaigns)s::text[]) AS u(a,c))
    GROUP BY k.criterion_external_id,k.keyword_text,k.match_type ORDER BY cost_micros DESC LIMIT 10'''

_HEALTH_SQL = '''
    SELECT c.checked_at,c.status,c.pages FROM cadu_reports_flow_monitor_checks c
    JOIN cadu_reports_flow_registry f ON f.id=c.flow_id
    WHERE f.site_id=%(site)s AND f.client_id=%(client)s ORDER BY c.checked_at DESC LIMIT 100'''


_DEVICE_SQL = {
    'all': 'TRUE', 'mobile': 'e.viewport_width<768', 'tablet': 'e.viewport_width>=768 AND e.viewport_width<1024',
    'desktop': 'e.viewport_width>=1024',
}
_INTERACTION_BASE = f'''
    FROM {EVENT_TABLE} e
    WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s
        AND {_NORM_E}=%(path)s AND ({{device}})'''
_ELEMENTS_SQL = '''
    SELECT e.event_data->>'element_id' AS element_id,
        COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click'))::bigint AS clicks,
        COUNT(*) FILTER (WHERE e.event_kind='whatsapp_click')::bigint AS whatsapp_clicks,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind IN ('click','whatsapp_click'))::bigint AS click_sessions,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='visibility')::bigint AS seen_sessions''' + _INTERACTION_BASE + '''
        AND e.event_kind IN ('click','whatsapp_click','visibility') AND e.event_data->>'element_id' IS NOT NULL
    GROUP BY 1 HAVING COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click'))>0 ORDER BY clicks DESC LIMIT 50'''
_GRID_SQL = '''
    SELECT (FLOOR(LEAST((e.event_data->>'x')::numeric,999)/100))::int AS cx,
        (FLOOR(LEAST((e.event_data->>'y')::numeric,999)/100))::int AS cy, COUNT(*)::bigint AS clicks''' + _INTERACTION_BASE + '''
        AND e.event_kind IN ('click','whatsapp_click') AND e.event_data->>'x' ~ '^[0-9]{1,4}$' AND e.event_data->>'y' ~ '^[0-9]{1,4}$'
    GROUP BY 1,2'''
_CLICK_TOTALS_SQL = '''
    SELECT COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click'))::bigint AS clicks,
        COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click') AND e.event_data->>'element_id' IS NULL)::bigint AS unidentified,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='page_view')::bigint AS sessions,
        COUNT(*) FILTER (WHERE e.event_kind='visibility')::bigint AS visibility_events''' + _INTERACTION_BASE
_DOC_GRID_SQL = '''
    SELECT (FLOOR(LEAST((e.event_data->>'dx')::numeric,999)/100))::int AS cx,
        (FLOOR(LEAST((e.event_data->>'dy')::numeric,999)/50))::int AS cy, COUNT(*)::bigint AS clicks''' + _INTERACTION_BASE + '''
        AND e.event_kind IN ('click','whatsapp_click') AND e.event_data->>'dx' ~ '^[0-9]{1,4}$' AND e.event_data->>'dy' ~ '^[0-9]{1,4}$'
    GROUP BY 1,2'''
_DOC_TOTALS_SQL = '''
    SELECT COUNT(*)::bigint AS clicks,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (e.event_data->>'dh')::numeric) FILTER (WHERE e.event_data->>'dh' ~ '^[0-9]{1,6}$') AS median_height''' + _INTERACTION_BASE + '''
        AND e.event_kind IN ('click','whatsapp_click') AND e.event_data->>'dx' ~ '^[0-9]{1,4}$' AND e.event_data->>'dy' ~ '^[0-9]{1,4}$'
    '''
_DEVICE_CLICKS_SQL = f'''
    SELECT CASE WHEN e.viewport_width IS NULL THEN 'unknown' WHEN e.viewport_width<768 THEN 'mobile'
        WHEN e.viewport_width<1024 THEN 'tablet' ELSE 'desktop' END AS device, COUNT(*)::bigint AS clicks
    FROM {EVENT_TABLE} e WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s
        AND {_NORM_E}=%(path)s AND e.event_kind IN ('click','whatsapp_click') GROUP BY 1'''


_CONVERSION_MAP_SQL = f'''
    WITH ps AS (
        SELECT e.session_id,MIN(e.occurred_at) AS first_view FROM {EVENT_TABLE} e
        WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.event_kind='page_view'
            AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s AND {_NORM_E}=%(path)s GROUP BY e.session_id
    ), first_event AS (
        SELECT DISTINCT ON (e.session_id) e.session_id,e.visitor_id,
            COALESCE(NULLIF('utm:'||LOWER(COALESCE(e.attribution->>'utm_source','')),'utm:'),
                NULLIF('ref:'||COALESCE(e.referrer_host,''),'ref:')) AS origin
        FROM {EVENT_TABLE} e JOIN ps ON ps.session_id=e.session_id
        WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.event_kind='page_view'
            AND e.occurred_at>=%(since)s - INTERVAL '1 day' AND e.occurred_at<%(until)s + INTERVAL '1 day'
        ORDER BY e.session_id,e.occurred_at,e.id
    ), visitor AS (
        SELECT e.session_id,(ARRAY_AGG(e.visitor_id ORDER BY e.occurred_at,e.id) FILTER (WHERE e.visitor_id IS NOT NULL))[1] AS visitor_id
        FROM {EVENT_TABLE} e JOIN ps ON ps.session_id=e.session_id
        WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.occurred_at>=%(since)s - INTERVAL '1 day'
            AND e.occurred_at<%(until)s + INTERVAL '1 day' GROUP BY e.session_id
    ), nxt AS (
        SELECT DISTINCT ON (e.session_id) e.session_id,
            CASE WHEN e.event_kind='page_view' THEN 'page' WHEN e.event_kind='form_submit' THEN 'form' ELSE 'whatsapp' END AS kind,
            CASE WHEN e.event_kind='page_view' THEN {_NORM_E} END AS next_path
        FROM {EVENT_TABLE} e JOIN ps ON ps.session_id=e.session_id
        WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.occurred_at>ps.first_view AND e.occurred_at<%(until)s + INTERVAL '1 day'
            AND ((e.event_kind='page_view' AND {_NORM_E}<>%(path)s) OR e.event_kind IN ('form_submit','whatsapp_click'))
        ORDER BY e.session_id,e.occurred_at,e.id
    ), conv AS (
        SELECT DISTINCT e.session_id FROM {EVENT_TABLE} e JOIN ps ON ps.session_id=e.session_id
        WHERE e.site_id=%(site)s AND e.expires_at>NOW() AND e.event_kind='conversion' AND e.occurred_at>=ps.first_view
            AND e.occurred_at<%(until)s + INTERVAL '1 day'
    ), ses AS (
        SELECT ps.session_id,ps.first_view,f.origin,v.visitor_id,n.kind,n.next_path,
            (c.session_id IS NOT NULL) AS converted,(st.last_seen_at<NOW()-INTERVAL '30 minutes') AS ended
        FROM ps JOIN first_event f ON f.session_id=ps.session_id JOIN visitor v ON v.session_id=ps.session_id
        LEFT JOIN nxt n ON n.session_id=ps.session_id LEFT JOIN conv c ON c.session_id=ps.session_id
        LEFT JOIN cadu_reports_supertag_sessions st ON st.site_id=%(site)s AND st.session_id=ps.session_id
    )
    SELECT s.origin,COALESCE(s.kind,CASE WHEN s.ended THEN 'exit' ELSE 'active' END) AS kind,s.next_path,s.converted,
        COUNT(*)::bigint AS sessions,{{crm}}
    FROM ses s GROUP BY 1,2,3,4 ORDER BY sessions DESC LIMIT 300'''
_CRM_COLUMNS = '''
        COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM cadu_reports_external_conversions x WHERE x.client_id=%(client)s
            AND x.visitor_id=s.visitor_id AND x.conversion_kind='lead' AND x.occurred_at>=s.first_view
            AND x.occurred_at<s.first_view+INTERVAL '30 days'))::bigint AS lead,
        COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM cadu_reports_external_conversions x WHERE x.client_id=%(client)s
            AND x.visitor_id=s.visitor_id AND x.conversion_kind='qualified_lead' AND x.occurred_at>=s.first_view
            AND x.occurred_at<s.first_view+INTERVAL '30 days'))::bigint AS qualified,
        COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM cadu_reports_external_conversions x WHERE x.client_id=%(client)s
            AND x.visitor_id=s.visitor_id AND x.conversion_kind='sale' AND x.occurred_at>=s.first_view
            AND x.occurred_at<s.first_view+INTERVAL '30 days'))::bigint AS sale'''
_NO_CRM_COLUMNS = "0::bigint AS lead,0::bigint AS qualified,0::bigint AS sale"
_CRM_COVERAGE_SQL = '''
    SELECT COUNT(*)::bigint AS events,COUNT(*) FILTER (WHERE visitor_id IS NOT NULL)::bigint AS with_visitor
    FROM cadu_reports_external_conversions WHERE client_id=%(client)s AND occurred_at>=%(since)s'''


_CANDIDATE_TERMS_SQL = '''
    SELECT t.account_id,a.currency,t.campaign_external_id,(ARRAY_AGG(t.campaign_name ORDER BY t.metric_date DESC))[1] AS campaign_name,
        t.ad_group_external_id,t.term_hash,(ARRAY_AGG(t.search_term ORDER BY t.metric_date DESC))[1] AS search_term,
        SUM(t.clicks)::bigint AS clicks,SUM(t.cost_micros)::bigint AS cost_micros,SUM(t.conversions) AS conversions
    FROM cadu_reports_gads_search_term_daily t JOIN cadu_reports_accounts a ON a.id=t.account_id
    WHERE t.client_id=%(client)s AND t.metric_date>=%(since_date)s AND t.metric_date<=%(until_date)s AND t.term_status='NONE'
        AND (t.account_id,t.campaign_external_id) IN (SELECT u.a,u.c FROM unnest(%(accounts)s::bigint[],%(campaigns)s::text[]) AS u(a,c))
    GROUP BY t.account_id,a.currency,t.campaign_external_id,t.ad_group_external_id,t.term_hash
    HAVING SUM(t.clicks)>=%(min_clicks)s AND COALESCE(SUM(t.conversions),0)=0 ORDER BY cost_micros DESC LIMIT 200'''
_ACTIVE_NEGATIVES_SQL = '''
    SELECT account_id,level,campaign_external_id,ad_group_external_id,attached_campaign_ids,keyword_text,match_type
    FROM cadu_reports_gads_negative_keywords WHERE client_id=%(client)s AND removed_at IS NULL AND account_id=ANY(%(accounts)s)'''
_NEGATIVE_SNAPSHOT_SQL = '''
    SELECT DISTINCT a.id FROM cadu_reports_source_runs r
    JOIN cadu_reports_accounts a ON a.client_id=r.client_id AND a.platform='google_ads' AND a.external_id=r.metadata->>'account_id'
    WHERE r.client_id=%(client)s AND r.source_kind='google_ads_engine_v2_chunk' AND r.metadata->>'dataset'='negative_keywords'
        AND r.status='completed' AND a.id=ANY(%(accounts)s)'''


def _table_exists(name):
    return bool(_rows('SELECT to_regclass(%s) IS NOT NULL AS ok', (f'public.{name}',))[0]['ok'])


def _number(value):
    return None if value is None else float(value)


def _paid_rows(rows):
    return [{**row, 'conversions': _number(row.get('conversions')),
             'cost_per_conversion_micros': round(row['cost_micros'] / float(row['conversions']))
             if row.get('conversions') and float(row['conversions']) > 0 else None} for row in rows]


def window_metrics(site_id, path, since, until):
    params = {'site': site_id, 'path': path, 'since': since, 'until': until}
    counts = _rows(_COUNTS_SQL, params)[0]
    groups = _rows(_GROUPS_SQL, params)
    return build_metrics(counts, sum_groups(groups)), groups


def paid_origin(client_id, host, path, since, until, groups):
    """Google Ads side for this page plus the Super Tag's own view of the same campaigns."""
    if not _table_exists('cadu_reports_gads_landing_page_daily'):
        return {'available': False, 'reason': 'Dados de páginas de destino do Google Ads ainda não foram recebidos. Reinstale o script v2.'}
    params = {'client': client_id, 'host': host, 'path': path, 'since_date': since.date(), 'until_date': until.date()}
    campaigns = _paid_rows(_rows(_PAID_SQL, params))
    terms = keywords = []
    if campaigns:
        pair = {**params, 'accounts': [c['account_id'] for c in campaigns], 'campaigns': [c['campaign_external_id'] for c in campaigns]}
        terms = [{**row, 'conversions': _number(row['conversions'])} for row in _rows(_TERMS_SQL, pair)]
        keywords = [{**row, 'conversions': _number(row['conversions'])} for row in _rows(_KEYWORDS_SQL, pair)]
    by_id = {c['campaign_external_id']: c for c in campaigns}
    by_name = {str(c['campaign_name']).strip().lower(): c for c in campaigns}
    observed = []
    for campaign, totals in breakdown(groups, lambda row: row.get('campaign') or '', 15):
        if not campaign:
            continue
        match = by_id.get(campaign) or by_name.get(campaign)
        observed.append({'utm_campaign': campaign, 'sessions': totals['sessions'], 'converted_sessions': totals['converted'],
                         'matched_campaign_id': match['campaign_external_id'] if match else None})
    return {'available': True, 'campaigns': campaigns, 'observed_campaigns': observed, 'search_terms': terms, 'keywords': keywords,
            'note': 'Campanhas ligadas à página pela URL de destino dos anúncios. O Google Ads informa a página por campanha, '
                    'não por palavra-chave: os termos e palavras-chave listados são das campanhas que apontam para esta página.'}


def page_health(site_id, client_id, host, path):
    timeline, latest = [], None
    for check in _rows(_HEALTH_SQL, {'site': site_id, 'client': client_id}):
        for page in check.get('pages') or []:
            if canonical_page(page.get('host'), page.get('path')) != (host, path):
                continue
            entry = {'checked_at': check['checked_at'], 'status': page.get('status'), 'http_status': page.get('http_status'),
                     'duration_ms': page.get('duration_ms'), 'detail': page.get('detail')}
            latest = latest or entry
            if len(timeline) < HEALTH_TIMELINE:
                timeline.append(entry)
            break
    return {'monitored': latest is not None, 'latest': latest, 'timeline': timeline}


def _site(site_id, client_id):
    rows = _rows('''SELECT id,label,allowed_host FROM cadu_reports_supertag_sites
        WHERE id=%s AND client_id=%s AND revoked_at IS NULL''', (site_id, client_id))
    if not rows:
        abort(404)
    return rows[0]


def _request_params():
    try:
        site_id = str(uuid.UUID(request.args.get('site_id', '')))
    except ValueError:
        abort(400, description='Informe site_id.')
    raw_path = request.args.get('path', '')
    if not raw_path.startswith('/') or len(raw_path) > 500 or re.search(r'\s', raw_path):
        abort(400, description='Informe o caminho da página começando por /.')
    try:
        days = int(request.args.get('days', 30))
    except ValueError:
        abort(400, description='Período inválido.')
    if not 1 <= days <= RETENTION_DAYS:
        abort(400, description=f'O período vai de 1 a {RETENTION_DAYS} dias.')
    return site_id, raw_path.split('?')[0].split('#')[0], days


def _device_param():
    device = request.args.get('device', 'all')
    if device not in DEVICES:
        abort(400, description='Dispositivo inválido.')
    return device



_DOMAIN_TOTALS_SQL = f'''
    SELECT e.site_id,
        COUNT(*) FILTER (WHERE e.event_kind='page_view')::bigint AS views,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='page_view')::bigint AS sessions,
        COUNT(DISTINCT e.visitor_id) FILTER (WHERE e.event_kind='page_view')::bigint AS visitors,
        COUNT(*) FILTER (WHERE e.event_kind IN ('click','whatsapp_click'))::bigint AS clicks,
        COUNT(*) FILTER (WHERE e.event_kind='form_submit')::bigint AS form_submits,
        COUNT(*) FILTER (WHERE e.event_kind='conversion')::bigint AS conversions,
        AVG(CASE WHEN e.event_data->>'duration_ms' ~ '^[0-9]{{1,9}}$' THEN (e.event_data->>'duration_ms')::numeric END)
            FILTER (WHERE e.event_kind='page_leave') AS avg_active_ms,
        MAX(e.occurred_at) AS last_event_at
    FROM {EVENT_TABLE} e JOIN cadu_reports_supertag_sites s ON s.id=e.site_id
    WHERE s.client_id=%(client)s AND s.revoked_at IS NULL AND e.expires_at>NOW()
        AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s
    GROUP BY e.site_id'''

_DOMAIN_DAILY_SQL = f'''
    SELECT e.site_id,(e.occurred_at AT TIME ZONE 'America/Sao_Paulo')::date AS day,
        COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='page_view')::bigint AS sessions,
        COUNT(*) FILTER (WHERE e.event_kind='conversion')::bigint AS conversions
    FROM {EVENT_TABLE} e JOIN cadu_reports_supertag_sites s ON s.id=e.site_id
    WHERE s.client_id=%(client)s AND s.revoked_at IS NULL AND e.expires_at>NOW()
        AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s
    GROUP BY e.site_id,day ORDER BY day'''

_DOMAIN_PAGES_SQL = f'''
    SELECT * FROM (
        SELECT e.site_id,{_NORM_E} AS path,
            COUNT(*) FILTER (WHERE e.event_kind='page_view')::bigint AS views,
            COUNT(DISTINCT e.session_id) FILTER (WHERE e.event_kind='page_view')::bigint AS sessions,
            COUNT(*) FILTER (WHERE e.event_kind='conversion')::bigint AS conversions,
            AVG(CASE WHEN e.event_data->>'duration_ms' ~ '^[0-9]{{1,9}}$' THEN (e.event_data->>'duration_ms')::numeric END)
                FILTER (WHERE e.event_kind='page_leave') AS avg_active_ms,
            ROW_NUMBER() OVER (PARTITION BY e.site_id ORDER BY COUNT(*) FILTER (WHERE e.event_kind='page_view') DESC) AS rn
        FROM {EVENT_TABLE} e JOIN cadu_reports_supertag_sites s ON s.id=e.site_id
        WHERE s.client_id=%(client)s AND s.revoked_at IS NULL AND e.expires_at>NOW()
            AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s
        GROUP BY e.site_id,{_NORM_E}) ranked
    WHERE rn<=%(limit)s AND views>0 ORDER BY site_id,rn'''

# First page view of each session decides where the visit came from and on what device.
_DOMAIN_SESSIONS_SQL = f'''
    SELECT site_id,origin,
        CASE WHEN width IS NULL THEN 'unknown' WHEN width<768 THEN 'mobile' WHEN width<1024 THEN 'tablet' ELSE 'desktop' END AS device,
        COUNT(*)::bigint AS sessions
    FROM (SELECT e.site_id,e.session_id,
            (ARRAY_AGG(COALESCE(NULLIF('utm:'||LOWER(COALESCE(e.attribution->>'utm_source','')),'utm:'),
                NULLIF('ref:'||COALESCE(e.referrer_host,''),'ref:')) ORDER BY e.occurred_at,e.id))[1] AS origin,
            (ARRAY_AGG(e.viewport_width ORDER BY e.occurred_at,e.id))[1] AS width
        FROM {EVENT_TABLE} e JOIN cadu_reports_supertag_sites s ON s.id=e.site_id
        WHERE s.client_id=%(client)s AND s.revoked_at IS NULL AND e.expires_at>NOW() AND e.event_kind='page_view'
            AND e.occurred_at>=%(since)s AND e.occurred_at<%(until)s
        GROUP BY e.site_id,e.session_id) first_view
    GROUP BY site_id,origin,device'''

DOMAIN_TOP_PAGES = 8


def _domain_metrics(row):
    row = row or {}
    sessions = int(row.get('sessions') or 0)
    conversions = int(row.get('conversions') or 0)
    avg_ms = row.get('avg_active_ms')
    return {'sessions': sessions, 'visitors': int(row.get('visitors') or 0), 'views': int(row.get('views') or 0),
            'clicks': int(row.get('clicks') or 0), 'form_submits': int(row.get('form_submits') or 0),
            'conversions': conversions, 'conversion_rate': pct(conversions, sessions),
            'avg_active_seconds': round(float(avg_ms) / 1000, 1) if avg_ms is not None else None}


def _window():
    """Rolling days by default; an explicit start/end date pair is read as whole days in São Paulo."""
    zone = ZoneInfo('America/Sao_Paulo')
    start_arg, end_arg = request.args.get('start_date'), request.args.get('end_date')
    if start_arg or end_arg:
        try:
            first, last = date.fromisoformat(start_arg or ''), date.fromisoformat(end_arg or '')
        except ValueError:
            abort(400, description='Informe as duas datas do intervalo.')
        if first > last or (last - first).days + 1 > RETENTION_DAYS:
            abort(400, description=f'O período vai de 1 a {RETENTION_DAYS} dias.')
        return (datetime.combine(first, time.min, zone), datetime.combine(last + timedelta(days=1), time.min, zone),
                (last - first).days + 1)
    try:
        days = int(request.args.get('days', 30))
    except ValueError:
        abort(400, description='Período inválido.')
    if not 1 <= days <= RETENTION_DAYS:
        abort(400, description=f'O período vai de 1 a {RETENTION_DAYS} dias.')
    today = datetime.now(zone).date()
    return (datetime.combine(today - timedelta(days=days - 1), time.min, zone),
            datetime.combine(today + timedelta(days=1), time.min, zone), days)


def register(bp):
    @bp.get('/api/v2/reports/pages/domains')
    @login_required_api
    def reports_pages_domains():
        """One card per monitored domain: totals, trend, top pages, origins and devices for the window."""
        selected = _selection()
        client = selected['client_id']
        since, until, days = _window()
        span = until - since
        scope = {'client': client, 'since': since, 'until': until}
        previous_scope = {'client': client, 'since': since - span, 'until': since}
        has_previous = (datetime.now(timezone.utc) - (since - span)).days < RETENTION_DAYS
        sites = _rows('''SELECT id,label,allowed_host,enabled FROM cadu_reports_supertag_sites
            WHERE client_id=%s AND revoked_at IS NULL ORDER BY allowed_host''', (client,))
        current = {str(row['site_id']): row for row in _rows(_DOMAIN_TOTALS_SQL, scope)}
        previous = {str(row['site_id']): row for row in _rows(_DOMAIN_TOTALS_SQL, previous_scope)} if has_previous else {}
        daily, pages, origins, devices = {}, {}, {}, {}
        for row in _rows(_DOMAIN_DAILY_SQL, scope):
            daily.setdefault(str(row['site_id']), {})[row['day']] = row
        for row in _rows(_DOMAIN_PAGES_SQL, {**scope, 'limit': DOMAIN_TOP_PAGES}):
            pages.setdefault(str(row['site_id']), []).append(row)
        for row in _rows(_DOMAIN_SESSIONS_SQL, scope):
            key = str(row['site_id'])
            platform = origin_platform(row.get('origin'))
            origins.setdefault(key, {})[platform] = origins.get(key, {}).get(platform, 0) + int(row['sessions'])
            devices.setdefault(key, {})[row['device']] = devices.get(key, {}).get(row['device'], 0) + int(row['sessions'])
        first_day = since.astimezone(ZoneInfo('America/Sao_Paulo')).date()
        out = []
        for site in sites:
            key = str(site['id'])
            metrics = _domain_metrics(current.get(key))
            before = _domain_metrics(previous[key]) if key in previous else (_domain_metrics(None) if has_previous else None)
            series = daily.get(key, {})
            out.append({
                'site_id': key, 'label': site['label'], 'host': site['allowed_host'], 'enabled': site['enabled'],
                'metrics': metrics, 'previous': before, 'change': compare(metrics, before),
                'last_event_at': (current.get(key) or {}).get('last_event_at'),
                'daily': [{'date': (first_day + timedelta(days=offset)).isoformat(),
                           'sessions': int((series.get(first_day + timedelta(days=offset)) or {}).get('sessions') or 0),
                           'conversions': int((series.get(first_day + timedelta(days=offset)) or {}).get('conversions') or 0)}
                          for offset in range(days)],
                'top_pages': [{'path': row['path'], 'views': int(row['views']), 'sessions': int(row['sessions']),
                               'conversions': int(row['conversions']),
                               'avg_active_seconds': round(float(row['avg_active_ms']) / 1000, 1) if row['avg_active_ms'] is not None else None}
                              for row in pages.get(key, [])],
                'sources': [{'platform': platform, 'label': PLATFORM_LABELS.get(platform, platform), 'sessions': total}
                            for platform, total in sorted(origins.get(key, {}).items(), key=lambda item: -item[1])[:6]],
                'devices': [{'device': name, 'label': DEVICE_LABELS[name], 'sessions': total}
                            for name, total in sorted(devices.get(key, {}).items(), key=lambda item: -item[1])],
            })
        return jsonify(window={'days': days, 'since': since, 'until': until, 'timezone': 'America/Sao_Paulo'},
                       previous_available=has_previous, domains=out)

    @bp.get('/api/v2/reports/pages/overview')
    @login_required_api
    def reports_page_overview():
        selected = _selection()
        site_id, raw_path, days = _request_params()
        site = _site(site_id, selected['client_id'])
        host, path = canonical_page(site['allowed_host'], raw_path)
        until = datetime.now(timezone.utc)
        since = until - timedelta(days=days)
        current, groups = window_metrics(site_id, path, since, until)
        # The previous window only exists while its events are still inside the retention period.
        previous = None
        previous_reason = None
        if days * 2 <= RETENTION_DAYS:
            previous, _ = window_metrics(site_id, path, since - timedelta(days=days), since)
        else:
            previous_reason = f'Os eventos ficam {RETENTION_DAYS} dias; o período anterior equivalente já não está disponível.'
        sources = [{'platform': platform, 'label': PLATFORM_LABELS.get(platform, platform),
                    'sessions': totals['sessions'], 'converted_sessions': totals['converted']}
                   for platform, totals in breakdown(groups, lambda row: origin_platform(row.get('origin')))]
        devices = [{'device': key, 'label': DEVICE_LABELS[key], 'sessions': totals['sessions'], 'converted_sessions': totals['converted']}
                   for key, totals in breakdown(groups, lambda row: row.get('device') or device_bucket(None))]
        return jsonify(
            page={'site_id': site_id, 'site_label': site['label'], 'host': host, 'path': path},
            window={'days': days, 'since': since, 'until': until, 'timezone': 'America/Sao_Paulo', 'rolling': True},
            has_data=current['sessions'] > 0 or current['views'] > 0,
            metrics=current, previous=previous, previous_unavailable=previous_reason, change=compare(current, previous),
            sources=sources, devices=devices,
            paid=paid_origin(selected['client_id'], host, path, since, until, groups),
            health=page_health(site_id, selected['client_id'], host, path),
            dictionary=DICTIONARY)

    @bp.get('/api/v2/reports/pages/interactions')
    @login_required_api
    def reports_page_interactions():
        selected = _selection()
        site_id, raw_path, days = _request_params()
        device = _device_param()
        site = _site(site_id, selected['client_id'])
        host, path = canonical_page(site['allowed_host'], raw_path)
        until = datetime.now(timezone.utc)
        since = until - timedelta(days=days)
        params = {'site': site_id, 'path': path, 'since': since, 'until': until}
        scope = _DEVICE_SQL[device]
        totals = _rows(_CLICK_TOTALS_SQL.replace('{device}', scope), params)[0]
        elements = build_elements(_rows(_ELEMENTS_SQL.replace('{device}', scope), params), int(totals['sessions'] or 0))
        grid = build_grid(_rows(_GRID_SQL.replace('{device}', scope), params))
        by_device = {row['device']: int(row['clicks']) for row in _rows(_DEVICE_CLICKS_SQL, params)}
        doc_totals = _rows(_DOC_TOTALS_SQL.replace('{device}', scope), params)[0]
        document = build_document_grid(_rows(_DOC_GRID_SQL.replace('{device}', scope), params), doc_totals['clicks'] or 0, totals['clicks'] or 0, doc_totals['median_height'])
        clicks = int(totals['clicks'] or 0)
        return jsonify(
            page={'site_id': site_id, 'host': host, 'path': path},
            window={'days': days, 'since': since, 'until': until, 'timezone': 'America/Sao_Paulo', 'rolling': True},
            device=device,
            devices=[{'device': key, 'label': DEVICE_LABELS[key], 'clicks': by_device.get(key, 0)}
                     for key in ('mobile', 'tablet', 'desktop') if key in by_device or key == device],
            mixed_layouts=device == 'all' and sum(1 for key in ('mobile', 'tablet', 'desktop') if by_device.get(key)) > 1,
            clicks=clicks, unidentified_clicks=int(totals['unidentified'] or 0), sessions=int(totals['sessions'] or 0),
            reliable=clicks >= MIN_RELIABLE_CLICKS, has_data=clicks > 0,
            marked_elements=len(elements) > 0, visibility_tracked=int(totals['visibility_events'] or 0) > 0,
            elements=elements, grid=grid, document=document,
            notes=['Cada clique é posicionado na parte da página visível no momento do clique (viewport), não na página inteira.',
                   'Só elementos marcados com data-cadu-element têm nome; os demais cliques aparecem apenas na grade.',
                   'A visão da página inteira usa só cliques com posição no documento, enviados por tags atualizadas, e não tem imagem da página: são faixas proporcionais à altura.',
                   'Layouts de celular, tablet e computador são diferentes: compare um dispositivo por vez.'])

    @bp.get('/api/v2/reports/pages/conversion-map')
    @login_required_api
    def reports_page_conversion_map():
        selected = _selection()
        site_id, raw_path, days = _request_params()
        site = _site(site_id, selected['client_id'])
        host, path = canonical_page(site['allowed_host'], raw_path)
        until = datetime.now(timezone.utc)
        since = until - timedelta(days=days)
        params = {'site': site_id, 'path': path, 'since': since, 'until': until, 'client': selected['client_id']}
        coverage = {'events': 0, 'with_visitor': 0}
        if _table_exists('cadu_reports_external_conversions'):
            coverage = _rows(_CRM_COVERAGE_SQL, params)[0]
        crm_available = int(coverage['with_visitor'] or 0) > 0
        sql = _CONVERSION_MAP_SQL.replace('{crm}', _CRM_COLUMNS if crm_available else _NO_CRM_COLUMNS)
        rows = _rows(sql, params)
        result = build_conversion_map(
            [{**row, 'origin': origin_platform(row.get('origin'))} for row in rows],
            lambda platform: PLATFORM_LABELS.get(platform, platform), crm_available)
        return jsonify(
            page={'site_id': site_id, 'host': host, 'path': path},
            window={'days': days, 'since': since, 'until': until, 'timezone': 'America/Sao_Paulo', 'rolling': True},
            has_data=result['total'] > 0, **result,
            crm_coverage={'events': int(coverage['events'] or 0), 'with_visitor': int(coverage['with_visitor'] or 0)},
            notes=['Cada faixa é um número de sessões. As colunas somam o mesmo total.',
                   'O próximo passo é o primeiro evento depois da primeira visualização desta página: outra página, formulário ou WhatsApp.',
                   '"Converteu no site" é uma conversão da Super Tag na mesma sessão, depois de ver a página.',
                   'Lead, qualificado e venda vêm do CRM, ligados pelo visitante, em até 30 dias depois da primeira visualização. '
                   'Conversões do CRM sem identificação do visitante não entram aqui.',
                   'É associação observada, não prova de que a página causou a conversão.'])

    @bp.get('/api/v2/reports/pages/suggestions')
    @login_required_api
    def reports_page_suggestions():
        selected = _selection()
        site_id, raw_path, days = _request_params()
        site = _site(site_id, selected['client_id'])
        host, path = canonical_page(site['allowed_host'], raw_path)
        until = datetime.now(timezone.utc)
        since = until - timedelta(days=days)
        current, groups = window_metrics(site_id, path, since, until)
        previous = window_metrics(site_id, path, since - timedelta(days=days), since)[0] if days * 2 <= RETENTION_DAYS else None
        paid = paid_origin(selected['client_id'], host, path, since, until, groups)
        accounts = sorted({c['account_id'] for c in paid.get('campaigns') or []})
        pair = {'client': selected['client_id'], 'accounts': accounts, 'campaigns': [c['campaign_external_id'] for c in paid.get('campaigns') or []],
                'since_date': since.date(), 'until_date': until.date(), 'min_clicks': MIN_TERM_CLICKS}
        terms = negatives = []
        snapshots = set()
        if accounts and _table_exists('cadu_reports_gads_negative_keywords'):
            snapshots = {row['id'] for row in _rows(_NEGATIVE_SNAPSHOT_SQL, pair)}
            if snapshots:
                negatives = _rows(_ACTIVE_NEGATIVES_SQL, pair)
                terms = [{**row, 'conversions': _number(row['conversions'])} for row in _rows(_CANDIDATE_TERMS_SQL, pair)]
        google_sessions = sum(totals['sessions'] for platform, totals in breakdown(groups, lambda row: origin_platform(row.get('origin'))) if platform == 'google')
        result = build_suggestions({
            'metrics': current, 'previous': previous, 'paid': paid, 'health': page_health(site_id, selected['client_id'], host, path),
            'google_sessions': google_sessions, 'candidate_terms': terms, 'negatives': negatives, 'accounts_with_negatives': snapshots})
        return jsonify(page={'site_id': site_id, 'host': host, 'path': path},
                       window={'days': days, 'since': since, 'until': until, 'timezone': 'America/Sao_Paulo', 'rolling': True},
                       **result)
