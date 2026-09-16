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
    'interactive_search': 'interativos', 'interactive_detail': 'interativos',
    'interativo_buscar': 'interativos', 'interativo_detalhe': 'interativos',
    'audience_search': 'audiencias', 'audience_detail': 'audiencias',
}
DETAIL_ALIASES = {'channel_detail', 'canal_detalhe', 'format_detail', 'formato_detalhe',
                  'interactive_detail', 'interativo_detalhe', 'audience_detail'}
DOCUMENT_ALIASES = {'document_preview', 'smartdoc_preview', 'documento_previa'}


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


def project(event, profile, client_id=None, actor_id=None):
    """Return a client-safe card or None. Exceptions stay local to the tool."""
    if profile != 'planner' or not isinstance(event, dict):
        return None
    raw_name = event.get('tool') or event.get('tool_name')
    if not isinstance(raw_name, str):
        return None
    params = _params(event.get('tool_input') if 'tool_input' in event else event.get('input'))
    if params is None:
        return None
    if raw_name in DOCUMENT_ALIASES:
        if not isinstance(client_id, int) or not isinstance(actor_id, int):
            return None
        try:
            document_id = int(params.get('id'))
            if document_id < 1:
                return None
            from ...cadu_planner import docs
            document, preview = docs.document_preview(client_id, actor_id, document_id)
            return {'event': 'document', 'document': {
                key: document.get(key) for key in ('id', 'title', 'type', 'status', 'updated_at', 'is_owner')
            }, 'preview': preview[:3000]}
        except Exception:
            return None
    if raw_name not in ALIASES:
        return None
    kind = ALIASES[raw_name]
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
