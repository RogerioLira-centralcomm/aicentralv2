"""Shared deterministic event matching for ingestion and live monitoring."""
from .reports_flow_lifecycle import is_measured


def normalize_path(path):
    """Compare URLs by what the visitor sees: /obrigado, /obrigado/ and /Obrigado are the same page."""
    return (str(path or '/').rstrip('/') or '/').lower()


def normalize_host(host):
    host = str(host or '').lower()
    return host[4:] if host.startswith('www.') else host


def match_flow_node(candidates, path, host, kind, event_name=None):
    expected = {'form_submit':'form','custom_event':'event','whatsapp_click':'whatsapp',
                'conversion':'conversion','error_view':'error'}.get(kind)
    nodes = [node for node in candidates
             if is_measured(node) and normalize_path(node.get('path')) == normalize_path(path)
             and (not node.get('host') or normalize_host(node['host']) == normalize_host(host))
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
