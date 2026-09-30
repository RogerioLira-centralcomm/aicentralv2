"""Deterministic live presence and direct transitions; no inferred people counts."""
from datetime import timedelta
from .reports_flow_matching import match_flow_node


def build_live_snapshot(events, nodes, edges, now):
    latest, previous, transitions, edge_activity = {}, {}, {}, {}
    nodes_by_path = {}
    for node in nodes:
        nodes_by_path.setdefault(node.get("path"), []).append(node)
    edges_by_pair = {}
    for edge in edges:
        edges_by_pair.setdefault((edge["from"], edge["to"]), []).append(edge)
    # Events are ordered by occurrence, with stable ingestion-ID tie breaking.
    for event in sorted(events, key=lambda e: (e['occurred_at'], int(e['id']))):
        session = event['session_id']
        latest[session] = event
        kind = event['event_kind']
        if kind in ('heartbeat', 'page_leave', 'click'):
            continue
        match = match_flow_node(nodes_by_path.get(event['page_path'], []), event['page_path'], event['page_host'], kind, event.get('event_name'))
        current = match['id'] if match else None
        old = previous.get(session)
        if old and current and old != current:
            for edge in edges_by_pair.get((old, current), []):
                edge_activity[edge['id']] = event['occurred_at'].isoformat()
                prior = transitions.get(edge['id'], 0)
                transitions[edge['id']] = max(prior, int(event['id']))
        # Unmapped page visits break a direct path, rather than inventing A → C.
        if current or kind in ('page_view', 'conversion', 'error_view'):
            previous[session] = current
    journeys = {}
    for event in sorted(events, key=lambda e: (e["occurred_at"], int(e["id"]))):
        if event["event_kind"] not in ("heartbeat", "page_leave", "click"):
            journeys.setdefault(str(event["session_id"]), []).append({"path":event["page_path"], "kind":event["event_kind"], "at":event["occurred_at"].isoformat()})
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
    sessions = [{"session_id":str(e['session_id']),"visitor_id":str(e.get('visitor_id') or e['session_id']),"page":e['page_path'],"host":e['page_host'],"last_seen_at":e['occurred_at'].isoformat(),"journey":journeys.get(str(e['session_id']), [])[-20:],"conversions":sum(item['kind']=='conversion' for item in journeys.get(str(e['session_id']), []))} for e in sorted(active,key=lambda e:e['occurred_at'],reverse=True)]
    return {'sessions':sessions[:100], 'sessions_truncated':len(sessions)>100, 'active_visitors':len({item['visitor_id'] for item in sessions}), 'active_sessions': len(active), 'active_window_seconds': 90,
            'sessions_on_conversion_pages': sum(locations[key] for key in conversion_pages),
            'node_presence': node_presence, 'transitions': {key: str(value) for key, value in transitions.items()},
            'edge_activity': edge_activity,
            'locations': [{'host': host, 'path': path, 'active_sessions': count}
                          for (host, path), count in locations.items()]}
