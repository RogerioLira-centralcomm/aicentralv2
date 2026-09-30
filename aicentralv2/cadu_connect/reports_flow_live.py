"""Deterministic live presence and direct transitions; no inferred people counts."""
from datetime import timedelta


def build_live_snapshot(events, nodes, edges, now):
    latest, previous, transitions = {}, {}, {}
    # Events are ordered by occurrence, with stable ingestion-ID tie breaking.
    for event in sorted(events, key=lambda e: (e['occurred_at'], int(e['id']))):
        session = event['session_id']
        latest[session] = event
        kind = event['event_kind']
        if kind in ('heartbeat', 'page_leave', 'click'):
            continue
        matches = [n for n in nodes if n.get('path') == event['page_path']
                   and (not n.get('host') or n['host'] == event['page_host'])
                   and ((n['type'] == 'page' and kind in ('page_view', 'conversion', 'error_view'))
                        or (n['type'] == 'form' and kind == 'form_submit')
                        or (n['type'] == 'error' and kind == 'error_view')
                        or (n['type'] == 'whatsapp' and kind == 'whatsapp_click')
                        or (n['type'] in ('event', 'conversion')
                            and kind == ('custom_event' if n['type'] == 'event' else 'conversion')
                            and (n.get('event_name') or '') == (event.get('event_name') or '')
                            or (n['type'] == 'conversion' and kind == 'conversion' and not n.get('event_name'))))]
        # Prefer a specific action over its generic page at the same URL.
        matches.sort(key=lambda n: (n['type'] == 'page', str(n['id'])))
        current = matches[0]['id'] if matches else None
        old = previous.get(session)
        if old and current and old != current:
            for edge in edges:
                if edge['from'] == old and edge['to'] == current:
                    prior = transitions.get(edge['id'], 0)
                    transitions[edge['id']] = max(prior, int(event['id']))
        # Unmapped page visits break a direct path, rather than inventing A → C.
        if current or kind in ('page_view', 'conversion', 'error_view'):
            previous[session] = current
    active = [e for e in latest.values() if e['occurred_at'] > now - timedelta(seconds=90)
              and e['event_kind'] != 'page_leave']
    locations = {}
    for event in active:
        key = (event['page_host'], event['page_path'])
        locations[key] = locations.get(key, 0) + 1
    node_presence = {}
    for node in nodes:
        if node['type'] != 'page':
            continue
        node_presence[node['id']] = sum(count for (host, path), count in locations.items()
            if path == node.get('path') and (not node.get('host') or node['host'] == host))
    conversion_pages = {(e['page_host'], e['page_path']) for e in active
                        if any(n['type'] == 'conversion' and not n.get('event_name')
                               and n.get('path') == e['page_path'] and
                               (not n.get('host') or n['host'] == e['page_host']) for n in nodes)}
    return {'active_sessions': len(active), 'active_window_seconds': 90,
            'sessions_on_conversion_pages': sum(locations[key] for key in conversion_pages),
            'node_presence': node_presence, 'transitions': {key: str(value) for key, value in transitions.items()},
            'locations': [{'host': host, 'path': path, 'active_sessions': count}
                          for (host, path), count in locations.items()]}
