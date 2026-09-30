"""Add a versioned editor view while preserving the collector's v1 fields.

The v2 document deliberately retains type/title/x/y and from/to. Published
collectors and immutable session snapshots still consume those fields.
"""

LEGACY_KINDS = {
    'source': 'traffic.source', 'page': 'page.generic', 'form': 'page.form',
    'event': 'event.custom', 'condition': 'logic.condition',
    'delay': 'logic.delay', 'segment': 'crm.segment',
    'conversion': 'conversion.generic', 'webhook': 'utility.webhook',
    'whatsapp': 'event.whatsapp', 'error': 'page.error',
}
KIND_TYPES = {kind: legacy for legacy, kind in LEGACY_KINDS.items()}


def legacy_projection(config):
    """Accept either v2-only fields or a hybrid document without changing v1 readers."""
    projected = dict(config)
    nodes = []
    for node in config.get('nodes', []):
        if not isinstance(node, dict):
            nodes.append(node)
            continue
        item = dict(node)
        data = item.get('data') if isinstance(item.get('data'), dict) else {}
        position = item.get('position') if isinstance(item.get('position'), dict) else {}
        tracking = data.get('tracking') if isinstance(data.get('tracking'), dict) else {}
        item.setdefault('type', KIND_TYPES.get(item.get('kind')))
        item.setdefault('title', data.get('label'))
        item.setdefault('x', position.get('x'))
        item.setdefault('y', position.get('y'))
        item.setdefault('path', data.get('url'))
        item.setdefault('event_name', tracking.get('event'))
        nodes.append(item)
    edges = []
    for edge in config.get('edges', []):
        if not isinstance(edge, dict):
            edges.append(edge)
            continue
        item = dict(edge)
        item.setdefault('from', item.get('source'))
        item.setdefault('to', item.get('target'))
        item.setdefault('from_port', item.get('source_handle'))
        item.setdefault('to_port', item.get('target_handle'))
        edges.append(item)
    projected.update(nodes=nodes, edges=edges)
    return projected


def migrate_v1_to_v2(config):
    """Return a non-mutating, idempotent editor document with legacy projection."""
    source = config if isinstance(config, dict) else {}
    nodes = []
    for node in source.get('nodes', []):
        if not isinstance(node, dict):
            continue
        item = dict(node)
        data = dict(item.get('data') or {}) if isinstance(item.get('data'), dict) else {}
        tracking = dict(data.get('tracking') or {}) if isinstance(data.get('tracking'), dict) else {}
        tracking['event'] = item.get('event_name') or tracking.get('event') or ''
        tracking['params'] = tracking.get('params') if isinstance(tracking.get('params'), dict) else {}
        data.update(label=item.get('title') or data.get('label') or item.get('type') or 'Etapa',
                    url=item.get('path') or data.get('url') or '',
                    tracking=tracking)
        item.update(kind=item.get('kind') or LEGACY_KINDS.get(item.get('type'), 'utility.unknown'),
                    position={'x': item.get('x', 0), 'y': item.get('y', 0)}, data=data)
        nodes.append(item)
    edges = []
    for edge in source.get('edges', []):
        if not isinstance(edge, dict):
            continue
        item = dict(edge)
        item.update(source=item.get('from'), target=item.get('to'),
                    source_handle=item.get('from_port') or 'right-out',
                    target_handle=item.get('to_port') or 'left-in',
                    variant=item.get('variant') or ('planned' if item.get('kind') == 'site_link' else 'direct'))
        edges.append(item)
    return {**source, 'schema_version': 2, 'nodes': nodes, 'edges': edges,
            'viewport': source.get('viewport') if isinstance(source.get('viewport'), dict)
            else {'x': 0, 'y': 0, 'zoom': 1},
            'settings': source.get('settings') if isinstance(source.get('settings'), dict)
            else {'edge_style': 'bezier', 'grid': True}}
