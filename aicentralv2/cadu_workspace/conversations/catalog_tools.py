"""Read-only catalog cards requested by an approved SmartPlanner workflow.

The provider may suggest a tool call but cannot select an arbitrary tool, SQL,
URL or customer context. This adapter recognizes a small, explicit allowlist.
"""
import json

from ...cadu_planner import catalog

ALIASES = {
    'channel_search': 'canais', 'channel_detail': 'canais',
    'canal_buscar': 'canais', 'canal_detalhe': 'canais',
    'format_search': 'formatos', 'format_detail': 'formatos',
    'formato_buscar': 'formatos', 'formato_detalhe': 'formatos',
    'audience_search': 'audiencias', 'audience_detail': 'audiencias',
}
DETAIL_ALIASES = {'channel_detail', 'canal_detalhe', 'format_detail', 'formato_detalhe', 'audience_detail'}


def _params(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        parsed = json.loads(value)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def project(event, profile):
    """Return a client-safe card or None. Exceptions stay local to the tool."""
    if profile != 'planner' or not isinstance(event, dict):
        return None
    raw_name = event.get('tool') or event.get('tool_name')
    if not isinstance(raw_name, str) or raw_name not in ALIASES:
        return None
    kind = ALIASES[raw_name]
    params = _params(event.get('tool_input') if 'tool_input' in event else event.get('input'))
    if params is None:
        return None
    try:
        if raw_name in DETAIL_ALIASES:
            item_id = params.get('id')
            if item_id is None:
                return None
            records = [catalog.detail(kind, item_id)]
        else:
            query = params.get('search', params.get('q', params.get('nome', '')))
            records = catalog.query(kind, query if isinstance(query, str) else '', params.get('limit', 10))
    except Exception:
        # A catalog miss must not break or leak through the generation stream.
        return None
    # `kind` is reserved by service.stream's SSE event helper.
    return {'event': 'catalog', 'catalog_kind': kind, 'records': records[:10]}
