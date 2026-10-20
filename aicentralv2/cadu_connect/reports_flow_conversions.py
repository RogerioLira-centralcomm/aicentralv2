"""Conversion journeys of a flow and the pages that take part in them, drawn or not.

A conversion is a session that reached one of the flow's conversion nodes in the period: the same count the canvas
shows on those nodes. Its journey is every page of that session up to the conversion, including pages the flow does
not draw, plus the earlier sessions of the same visitor (30 days). Events come from the flow's own collection across
publications, matched to the drawing on screen (reports_flow_history), so the numbers here and on the canvas agree.

Everything is observed association: a page "taking part" in conversions is not proof that it caused them.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import abort, jsonify, request

from ..auth import login_required_api
from .reports_flow_history import matched_events_cte, node_match_json
from .reports_flow_lifecycle import is_measured
from .reports_flow_metrics import PLATFORM_LABELS, click_origin_sql, origin_platform
from .reports_page_identity import normalize_host, normalize_path, sql_normalized_path
from .reports_v1 import _rows, _selection

PRIOR_DAYS = 30            # earlier sessions of the same visitor that count as part of a journey
MAX_STEPS = 30             # longer journeys keep the first 10 and the last 19 steps
MAX_PRIOR_SESSIONS = 5
PRIOR_PAGES = 5
LIST_LIMIT = 200           # conversions listed per response, newest first
INFLUENCE_LIMIT = 2000     # conversions read to rank pages
MIN_ASSISTED = 2           # a page enters the off-flow ranking from this many conversions
MIN_RATE_SESSIONS = 20     # sessions with the page before its conversion rate is compared
MIN_RATE_CONVERSIONS = 10  # conversions in the period before any rate is compared
TOP_PATHS = 10
STEP_KINDS = ('page_view', 'conversion', 'error_view', 'form_submit', 'whatsapp_click', 'page_leave')

_ORIGIN = ("COALESCE('utm:'||NULLIF(LOWER(utm_source),'')||'|'||COALESCE(LOWER(utm_campaign),''),"
           + click_origin_sql('click_id') + ",'ref:'||NULLIF(LOWER(referrer_host),''))")
_COLUMNS = ('e.id,e.session_id,e.visitor_id,e.occurred_at,e.event_kind,e.event_name,e.page_host,e.page_path,'
            'e.duration_ms,e.utm_source,e.utm_campaign,e.click_id,e.referrer_host,e.flow_revision')


def conversion_node_ids(config):
    return [node['id'] for node in (config or {}).get('nodes', [])
            if isinstance(node, dict) and node.get('type') == 'conversion' and node.get('path') and is_measured(node)]


def off_flow_group(path):
    """Off-flow pages are summed by their first segment: '/blog/ctv' and '/blog/dooh' are '/blog/*'."""
    segments = [segment for segment in normalize_path(path).split('/') if segment]
    return '/' if not segments else f'/{segments[0]}' if len(segments) == 1 else f'/{segments[0]}/*'


def page_key(path, host=None):
    """Identity of a page in a journey: its path on the flow's own domain, ``host + path`` on another of the client's."""
    return f'{host}{normalize_path(path)}' if host else normalize_path(path)


def _other_host(host, site_host):
    host = normalize_host(host)
    return host if host and host != site_host else None


def collapse_steps(events, nodes_by_id, titles, conversion_id, site_host=''):
    """The visible steps of one converting session, up to and including the conversion event.

    Repeated views of the same page in a row are one step; page_leave only adds active time to the step it closes.
    A page on another of the client's domains keeps that domain in ``host`` and in its ``key``.
    """
    steps = []
    for event in events:
        key = page_key(event['page_path'], _other_host(event.get('page_host'), site_host))
        if event['event_kind'] == 'page_leave':
            if steps and steps[-1]['key'] == key and event.get('duration_ms'):
                steps[-1]['seconds'] = round((steps[-1].get('seconds') or 0) + event['duration_ms'] / 1000)
            continue
        node = nodes_by_id.get(event.get('node_id'))
        path, host = normalize_path(event['page_path']), _other_host(event.get('page_host'), site_host)
        kind = {'form_submit': 'form', 'whatsapp_click': 'whatsapp'}.get(event['event_kind'], 'page')
        if steps and steps[-1]['key'] == key and steps[-1]['kind'] == kind and steps[-1].get('node_id') == (node or {}).get('id'):
            if event['id'] == conversion_id:
                steps[-1]['goal'] = True
            continue
        step = {'path': path, 'host': host, 'key': key, 'kind': kind,
                'title': (node or {}).get('title') or (key if host else titles.get(path) or path),
                'node_id': node['id'] if node else None, 'off_flow': node is None}
        if event['id'] == conversion_id:
            step['goal'] = True
        steps.append(step)
        if event['id'] == conversion_id:
            break
    if len(steps) > MAX_STEPS:
        hidden = len(steps) - 29
        steps = steps[:10] + [{'kind': 'gap', 'hidden': hidden, 'path': None, 'host': None, 'key': None, 'title': f'+{hidden} passos', 'off_flow': True}] + steps[-19:]
    return steps


def journey_origins(session_origin, prior):
    """First contact, last non-direct contact and the origin of the converting session, as platform ids."""
    ordered = [item['platform'] for item in sorted(prior, key=lambda item: item['started_at'])] + [session_origin]
    paid_or_referred = [platform for platform in ordered if platform != 'direct']
    return {'first': ordered[0], 'last_non_direct': paid_or_referred[-1] if paid_or_referred else 'direct',
            'session': session_origin}


def path_signature(steps):
    """The steps of a journey as a comparable sequence: drawn pages by title, the rest by section."""
    signature = []
    for step in steps:
        if step['kind'] == 'gap':
            label = '…'
        elif step['off_flow']:
            label = (step.get('host') or '') + off_flow_group(step['path'])
        else:
            label = step['title']
        if not signature or signature[-1] != label:
            signature.append(label)
    return tuple(signature)


def top_paths(journeys):
    counts = Counter(path_signature(journey['steps']) for journey in journeys)
    return [{'steps': list(steps), 'conversions': count}
            for steps, count in counts.most_common(TOP_PATHS) if count >= 2]


def _position(index, length):
    if length == 1:
        return 'only'
    return 'start' if index == 0 else 'eve' if index == length - 1 else 'middle'


def page_influence(journeys, page_sessions, total_sessions, flow_paths, nodes_by_path, titles, compare=True):
    """Per page: conversions it took part in (same session or an earlier visit), share, position and rates.

    Pages are keyed by page_key: ``page_sessions``, ``flow_paths`` and ``nodes_by_path`` use the same keys. Rates are
    compared only on a sample large enough; below it the counts stand alone.
    """
    total = len(journeys)
    stats = {}
    for journey in journeys:
        pages = [step for step in journey['steps'] if step['kind'] == 'page' and not step.get('goal')]
        seen = set()
        for index, step in enumerate(pages):
            key = step.get('key') or step['path']
            if key in seen:
                continue
            seen.add(key)
            item = stats.setdefault(key, {'assisted': 0, 'assisted_prior': 0, 'positions': Counter(),
                                          'path': step['path'], 'host': step.get('host')})
            item['assisted'] += 1
            item['positions'][_position(index, len(pages))] += 1
        prior = {page for session in journey.get('prior_sessions', []) for page in session.get('page_keys', session.get('pages', []))} - seen
        for key in prior:
            host, _, rest = key.partition('/') if not key.startswith('/') else ('', '', key[1:])
            stats.setdefault(key, {'assisted': 0, 'assisted_prior': 0, 'positions': Counter(),
                                   'path': '/' + rest, 'host': host or None})['assisted_prior'] += 1
    # A capped read has fewer conversions than sessions show, so its rates would be understated.
    compare = compare and total >= MIN_RATE_CONVERSIONS
    rows = []
    for key, item in stats.items():
        sessions = int(page_sessions.get(key) or 0)
        node = nodes_by_path.get(key)
        row = {'key': key, 'path': item['path'], 'host': item['host'],
               'title': (node or {}).get('title') or (key if item['host'] else titles.get(item['path']) or item['path']),
               'node_id': node['id'] if node else None, 'in_flow': key in flow_paths,
               'assisted': item['assisted'], 'assisted_prior': item['assisted_prior'],
               'share': round(100 * item['assisted'] / total, 1) if total else None,
               'position': item['positions'].most_common(1)[0][0] if item['positions'] else None,
               'sessions': sessions, 'rate_with': None, 'rate_without': None}
        if compare and sessions >= MIN_RATE_SESSIONS and total_sessions > sessions:
            row['rate_with'] = round(100 * item['assisted'] / sessions, 1)
            row['rate_without'] = round(100 * max(0, total - item['assisted']) / (total_sessions - sessions), 1)
        rows.append(row)
    rows.sort(key=lambda row: (-(row['assisted'] + row['assisted_prior']), -(row['share'] or 0), row['key']))
    return rows


def _period():
    try:
        days = int(request.args.get('days', 30))
    except (TypeError, ValueError):
        abort(400, description='Período inválido.')
    if days not in (7, 30, 90):
        abort(400, description='Período inválido.')
    zone = ZoneInfo('America/Sao_Paulo')
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.astimezone(zone).date() - timedelta(days=days - 1), datetime.min.time(), zone)
    return days, start, now


def _titles(client_id, host):
    from .reports_site_pages import slug_name
    rows = _rows('SELECT path,name,title FROM cadu_reports_site_pages WHERE client_id=%s AND host=%s', (client_id, host))
    titles = {normalize_path(row['path']): row.get('title') or row.get('name') for row in rows}
    return lambda path: titles.get(path) or slug_name(path)


class _Titles(dict):
    def __init__(self, resolve):
        super().__init__()
        self._resolve = resolve

    def get(self, path, default=None):
        if path not in self:
            self[path] = self._resolve(path)
        return self[path] or default


def build_journeys(flow, client_id, start, end, limit, before=None):
    """The period's conversions of a flow, newest first, each with its steps, earlier visits and origins."""
    config = flow.get('active_config') or {}
    goal_ids = conversion_node_ids(config)
    nodes = [node for node in config.get('nodes', []) if isinstance(node, dict) and node.get('id')]
    nodes_by_id = {node['id']: node for node in nodes}
    titles = _Titles(_titles(client_id, flow['allowed_host']))
    site_host = normalize_host(flow['allowed_host'])
    if not goal_ids:
        return [], goal_ids, nodes_by_id, titles, False
    node_json = node_match_json(config)
    where = 'e.client_id=%s AND e.tag_id=%s AND e.occurred_at>=%s AND e.occurred_at<%s'
    scope = (node_json, client_id, flow['tag_id'], start, end)
    cursor_filter, cursor_params = '', ()
    if before:
        cursor_filter, cursor_params = ' AND (occurred_at,id)<(%s::timestamptz,%s::bigint)', before
    conversions = _rows(matched_events_cte(where, _COLUMNS) + f""", firsts AS (
            SELECT DISTINCT ON (session_id) id,session_id,visitor_id,occurred_at,node_id FROM mapped
            WHERE node_id=ANY(%s::text[]) AND event_kind<>'page_leave' ORDER BY session_id,occurred_at,id
        ) SELECT * FROM firsts WHERE TRUE{cursor_filter} ORDER BY occurred_at DESC,id DESC LIMIT %s""",
        (*scope, goal_ids, *cursor_params, limit + 1))
    more = len(conversions) > limit
    conversions = conversions[:limit]
    if not conversions:
        return [], goal_ids, nodes_by_id, titles, False
    sessions = [str(row['session_id']) for row in conversions]
    events = _rows(matched_events_cte(where + ' AND e.session_id=ANY(%s::uuid[]) AND e.event_kind=ANY(%s::text[])',
                                      _COLUMNS) + f" SELECT *,{_ORIGIN} AS origin FROM mapped ORDER BY session_id,occurred_at,id",
                   (*scope, sessions, list(STEP_KINDS)))
    by_session = {}
    for event in events:
        by_session.setdefault(str(event['session_id']), []).append(event)
    # Earlier visits: only a visitor id that is not the session itself identifies a returning person.
    visitors = sorted({str(row['visitor_id']) for row in conversions if row['visitor_id'] and row['visitor_id'] != row['session_id']})
    prior_rows = _rows(f"""SELECT session_id,visitor_id,page_host,page_path,event_kind,occurred_at,{_ORIGIN} AS origin
        FROM cadu_reports_flow_events
        WHERE client_id=%s AND tag_id=%s AND visitor_id=ANY(%s::uuid[])
          AND occurred_at>=%s AND occurred_at<%s AND event_kind IN ('page_view','conversion','error_view')
        ORDER BY session_id,occurred_at,id""",
        (client_id, flow['tag_id'], visitors, start - timedelta(days=PRIOR_DAYS), end)) if visitors else []
    prior_by_visitor = {}
    for row in prior_rows:
        visits = prior_by_visitor.setdefault(str(row['visitor_id']), {})
        visit = visits.setdefault(str(row['session_id']), {'started_at': row['occurred_at'], 'origin': row['origin'], 'pages': []})
        key = page_key(row['page_path'], _other_host(row.get('page_host'), site_host))
        if len(visit['pages']) < PRIOR_PAGES and (not visit['pages'] or visit['pages'][-1] != key):
            visit['pages'].append(key)
    journeys = []
    for row in conversions:
        session_events = by_session.get(str(row['session_id']), [])
        session_origin = origin_platform(next((event['origin'] for event in session_events), None))
        visitor = str(row['visitor_id']) if row['visitor_id'] and row['visitor_id'] != row['session_id'] else None
        prior = sorted((visit for visit in (prior_by_visitor.get(visitor) or {}).values()
                        if row['occurred_at'] - timedelta(days=PRIOR_DAYS) <= visit['started_at'] < session_events[0]['occurred_at']),
                       key=lambda visit: visit['started_at'])[-MAX_PRIOR_SESSIONS:] if visitor and session_events else []
        prior = [{'started_at': visit['started_at'], 'platform': origin_platform(visit['origin']), 'pages': visit['pages']} for visit in prior]
        node = nodes_by_id.get(row['node_id']) or {}
        journeys.append({'id': str(row['id']), 'session_id': str(row['session_id']), 'converted_at': row['occurred_at'],
                         'goal': {'node_id': row['node_id'], 'title': node.get('title') or 'Conversão'},
                         'identified': visitor is not None,
                         'origin': journey_origins(session_origin, prior),
                         'prior_sessions': prior,
                         'steps': collapse_steps(session_events, nodes_by_id, titles, row['id'], site_host)})
    return journeys, goal_ids, nodes_by_id, titles, more


def _serialize(journey):
    return {**journey, 'converted_at': journey['converted_at'].isoformat(),
            'prior_sessions': [{**visit, 'started_at': visit['started_at'].isoformat()} for visit in journey['prior_sessions']]}


def _labels(platforms):
    return {platform: PLATFORM_LABELS.get(platform, platform) for platform in platforms}


def _published(flow):
    return flow['status'] == 'published' and flow.get('published_revision') is not None and not flow.get('revoked_at')


NOTES = ['Conversão é uma sessão que chegou a um nó de conversão do fluxo, a mesma conta do mapa.',
         'O caminho inclui páginas que o fluxo não desenha; visitas anteriores só aparecem para visitantes identificados, até 30 dias antes.',
         'Os eventos vêm de todas as publicações do período, lidos com o desenho atual; antes da primeira publicação não há coleta.',
         'É associação observada, não prova de que o caminho ou a página causou a conversão.']


def register(bp):
    @bp.get('/api/v2/reports/flow/flows/<flow_id>/conversions')
    @login_required_api
    def reports_flow_conversions(flow_id):
        from .reports_flow import _flow_row
        selected = _selection()
        flow = _flow_row(flow_id, selected)
        days, start, end = _period()
        window = {'days': days, 'from': start.isoformat(), 'to': end.isoformat(), 'timezone': 'America/Sao_Paulo'}
        if not _published(flow):
            return jsonify(status='unavailable', window=window, journeys=[], top_paths=[], notes=NOTES)
        before = None
        raw_cursor = request.args.get('cursor', '')
        if raw_cursor:
            moment, _, event_id = raw_cursor.partition('|')
            try:
                before = (datetime.fromisoformat(moment).isoformat(), int(event_id))
            except ValueError:
                abort(400, description='Cursor inválido.')
        journeys, goal_ids, _, _, more = build_journeys(flow, selected['client_id'], start, end, LIST_LIMIT, before)
        if not goal_ids:
            return jsonify(status='no_goal', window=window, journeys=[], top_paths=[], notes=NOTES)
        platforms = {value for journey in journeys for value in journey['origin'].values()}
        last = journeys[-1] if more and journeys else None
        return jsonify(status='ready', window=window, revision=flow.get('published_revision'),
                       coverage={'conversions': len(journeys), 'identified': sum(journey['identified'] for journey in journeys),
                                 'complete': not more and not before},
                       journeys=[_serialize(journey) for journey in journeys], top_paths=top_paths(journeys) if not before else [],
                       origin_labels=_labels(platforms),
                       next_cursor=f"{last['converted_at'].isoformat()}|{last['id']}" if last else None, notes=NOTES)

    @bp.get('/api/v2/reports/flow/flows/<flow_id>/influence')
    @login_required_api
    def reports_flow_influence(flow_id):
        from .reports_flow import _flow_row
        selected = _selection()
        flow = _flow_row(flow_id, selected)
        days, start, end = _period()
        window = {'days': days, 'from': start.isoformat(), 'to': end.isoformat(), 'timezone': 'America/Sao_Paulo'}
        thresholds = {'min_assisted': MIN_ASSISTED, 'min_rate_sessions': MIN_RATE_SESSIONS, 'min_rate_conversions': MIN_RATE_CONVERSIONS}
        if not _published(flow):
            return jsonify(status='unavailable', window=window, pages=[], unused=[], thresholds=thresholds, notes=NOTES)
        journeys, goal_ids, nodes_by_id, titles, truncated = build_journeys(flow, selected['client_id'], start, end, INFLUENCE_LIMIT)
        if not goal_ids:
            return jsonify(status='no_goal', window=window, pages=[], unused=[], thresholds=thresholds, notes=NOTES)
        config = flow.get('active_config') or {}
        host = normalize_host(flow['allowed_host'])
        # Every drawn page, on any of the client's domains, keyed like the journey steps.
        page_nodes = [node for node in nodes_by_id.values() if node.get('type') in ('page', 'form', 'conversion', 'error') and node.get('path')]
        node_key = lambda node: page_key(node['path'], _other_host(node.get('host'), host))
        nodes_by_path = {}
        for node in sorted(page_nodes, key=lambda node: node.get('type') != 'page'):
            nodes_by_path.setdefault(node_key(node), node)
        flow_paths = set(nodes_by_path)
        counts = _rows(matched_events_cte('e.client_id=%s AND e.tag_id=%s AND e.occurred_at>=%s AND e.occurred_at<%s', _COLUMNS) +
                       ", views AS (SELECT session_id,REGEXP_REPLACE(LOWER(page_host),'^www[.]','') AS host," + sql_normalized_path('page_path') + """ AS path
                             FROM mapped WHERE event_kind IN ('page_view','conversion','error_view'))
                          SELECT host,path,COUNT(DISTINCT session_id)::bigint AS sessions,
                              (SELECT COUNT(DISTINCT session_id) FROM views)::bigint AS total
                          FROM views GROUP BY host,path""",
                       (node_match_json(config), selected['client_id'], flow['tag_id'], start, end))
        page_sessions = {}
        for row in counts:
            key = page_key(row['path'], _other_host(row['host'], host))
            page_sessions[key] = page_sessions.get(key, 0) + int(row['sessions'])
        total_sessions = int(counts[0]['total']) if counts else 0
        rows = page_influence(journeys, page_sessions, total_sessions, flow_paths, nodes_by_path, titles, compare=not truncated)
        off_flow = [row for row in rows if not row['in_flow'] and row['assisted'] + row['assisted_prior'] >= MIN_ASSISTED]
        used = {row['key'] for row in rows if row['in_flow']}
        conversion_keys = {node_key(nodes_by_id[node_id]) for node_id in goal_ids}
        unused = [{'node_id': node['id'], 'title': node.get('title') or node['path'], 'path': node['path'], 'host': node.get('host'),
                   'key': key, 'sessions': page_sessions.get(key, 0)}
                  for key, node in sorted(nodes_by_path.items()) if key not in used and key not in conversion_keys]
        # Where an off-flow page would go: after the drawn step that most often comes right before it.
        for row in off_flow:
            before = Counter()
            for journey in journeys:
                steps = [step for step in journey['steps'] if step['kind'] == 'page']
                for previous, step in zip(steps, steps[1:]):
                    if step.get('key') == row['key'] and previous.get('node_id'):
                        before[previous['node_id']] += 1
            row['after_node_id'] = before.most_common(1)[0][0] if before else None
        return jsonify(status='ready', window=window, revision=flow.get('published_revision'),
                       conversions=len(journeys), sessions=total_sessions, truncated=truncated,
                       compare_rates=not truncated and len(journeys) >= MIN_RATE_CONVERSIONS,
                       pages=[row for row in rows if row['in_flow']], off_flow=off_flow, unused=unused,
                       thresholds=thresholds, notes=NOTES)
