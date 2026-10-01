"""Shared deterministic event matching for ingestion and live monitoring."""
from .reports_flow_lifecycle import is_measured


def match_flow_node(candidates, path, host, kind, event_name=None):
    expected = {'form_submit':'form','custom_event':'event','whatsapp_click':'whatsapp',
                'conversion':'conversion','error_view':'error'}.get(kind)
    nodes = [node for node in candidates
             if is_measured(node) and node.get('path') == path and (not node.get('host') or node['host'] == host)
             and (node.get('type') == expected if expected else
                  node.get('type') in ('page','conversion','error'))
             and (node.get('type') != 'event' or node.get('event_name') == event_name)
             and (node.get('type') != 'conversion' or
                  (kind == 'page_view' and not node.get('event_name')) or
                  (kind == 'conversion' and (not node.get('event_name') or node.get('event_name') == event_name)))]
    if not nodes:
        return None
    # Conversion/error page rules outrank a generic page at the same URL.
    return sorted(nodes, key=lambda n: (
        n.get('type') == 'page',
        kind == 'conversion' and n.get('type') == 'conversion' and not n.get('event_name')))[0]
