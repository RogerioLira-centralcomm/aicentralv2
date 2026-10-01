"""The flow document has one shape (v3). Older shapes are read once and never written back.

v3 keeps exactly the fields the editor and the collector use: nodes carry type, kind, title,
x, y and their own attributes; edges carry from, to and ports. There are no mirrored copies
(``data``, ``position``, ``source``/``target``, handles) and no placeholder paths.
"""

SCHEMA_VERSION = 3
DEFAULT_KINDS = {
    'source': 'traffic.source', 'page': 'page.generic', 'form': 'page.form',
    'event': 'event.custom', 'condition': 'logic.condition',
    'delay': 'logic.delay', 'segment': 'crm.segment',
    'conversion': 'conversion.generic', 'webhook': 'utility.webhook',
    'whatsapp': 'event.whatsapp', 'error': 'page.error', 'note': 'annotation.note',
}
KIND_TYPES = {kind: node_type for node_type, kind in DEFAULT_KINDS.items()}
MEASURED = {'page', 'form', 'event', 'conversion', 'whatsapp', 'error'}
# Drafts before v3 marked a step without a real address with a fake path.
PLACEHOLDER_PREFIX = '/configurar-'
MIRRORED_NODE_FIELDS = ('data', 'position')
MIRRORED_EDGE_FIELDS = ('source', 'target', 'source_handle', 'target_handle')


def _node_v3(node):
    item = {key: value for key, value in node.items() if key not in MIRRORED_NODE_FIELDS}
    data = node.get('data') if isinstance(node.get('data'), dict) else {}
    position = node.get('position') if isinstance(node.get('position'), dict) else {}
    tracking = data.get('tracking') if isinstance(data.get('tracking'), dict) else {}
    item.setdefault('type', KIND_TYPES.get(node.get('kind')))
    if item.get('title') in (None, ''):
        item['title'] = data.get('label')
    for axis in ('x', 'y'):
        if item.get(axis) is None and position.get(axis) is not None:
            item[axis] = position[axis]
    if not item.get('path') and data.get('url'):
        item['path'] = data['url']
    if not item.get('event_name') and tracking.get('event'):
        item['event_name'] = tracking['event']
    if isinstance(item.get('path'), str) and item['path'].startswith(PLACEHOLDER_PREFIX):
        del item['path']
        if item.get('type') in MEASURED:
            item.setdefault('status', 'planned')
    if not item.get('path'):
        item.pop('path', None)
    if not item.get('kind') and item.get('type') in DEFAULT_KINDS:
        item['kind'] = DEFAULT_KINDS[item['type']]
    return item


def _edge_v3(edge):
    item = {key: value for key, value in edge.items() if key not in MIRRORED_EDGE_FIELDS}
    item.setdefault('from', edge.get('source'))
    item.setdefault('to', edge.get('target'))
    if not item.get('from_port') and edge.get('source_handle'):
        item['from_port'] = edge['source_handle']
    if not item.get('to_port') and edge.get('target_handle'):
        item['to_port'] = edge['target_handle']
    item.setdefault('variant', 'planned' if edge.get('kind') == 'site_link' else 'direct')
    return item


def to_v3(config):
    """Return the canonical document; idempotent and never mutates its input."""
    source = config if isinstance(config, dict) else {}
    document = {key: value for key, value in source.items() if key not in ('nodes', 'edges')}
    document['schema_version'] = SCHEMA_VERSION
    document['nodes'] = [_node_v3(node) if isinstance(node, dict) else node for node in source.get('nodes', []) or []]
    document['edges'] = [_edge_v3(edge) if isinstance(edge, dict) else edge for edge in source.get('edges', []) or []]
    return document
