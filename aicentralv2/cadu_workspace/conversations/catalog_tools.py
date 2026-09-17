"""Read-only catalog cards requested by an approved SmartPlanner workflow.

The provider may suggest a tool call but cannot select an arbitrary tool, SQL,
URL or customer context. This adapter recognizes a small, explicit allowlist.
"""
import json

from ...cadu_planner import catalog
from ...product_domains import product_url

ALIASES = {
    'channel_search': 'canais', 'channel_detail': 'canais',
    'canal_buscar': 'canais', 'canal_detalhe': 'canais',
    'format_search': 'formatos', 'format_detail': 'formatos',
    'formato_buscar': 'formatos', 'formato_detalhe': 'formatos',
    'interactive_search': 'interativos', 'interactive_detail': 'interativos',
    'interativo_buscar': 'interativos', 'interativo_detalhe': 'interativos',
    'audience_search': 'audiencias', 'audience_detail': 'audiencias',
    'place_search': 'places', 'place_detail': 'places',
}
DETAIL_ALIASES = {'channel_detail', 'canal_detalhe', 'format_detail', 'formato_detalhe',
                  'interactive_detail', 'interativo_detalhe', 'audience_detail'}
DOCUMENT_ALIASES = {'document_preview', 'smartdoc_preview', 'documento_previa'}
PLAN_LIST_ALIASES = {'plan_list', 'plans_list', 'plano_listar', 'planos_listar'}
PLAN_DETAIL_ALIASES = {'plan_detail', 'plano_detalhe'}

# Audience catalog records can contain commercial fields used elsewhere in the
# planner. Conversation cards are editorial/planning references, never rate
# cards, so keep this projection deliberately restricted.
AUDIENCE_CONVERSATION_FIELDS = (
    'id', 'name', 'description', 'audience', 'image_url', 'category',
    'subcategory', 'channel', 'platform', 'storytelling',
    'caso_uso_principal', 'insights_planejamento', 'perfil_socioeconomico',
    'perfil_consumo', 'momentos_chave', 'interesses_correlatos',
    'propensao_compra', 'tamanho',
)


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


def _audience_for_conversation(record):
    """Remove pricing and operational buying data from chat tool responses."""
    if not isinstance(record, dict):
        return {}
    return {key: record.get(key) for key in AUDIENCE_CONVERSATION_FIELDS
            if record.get(key) not in (None, '', [], {})}


def _channel_for_conversation(channel):
    """Project a catalog-owned channel dossier into a safe work object.

    Commercial terms are clearly labeled as a catalog reference. They are not
    availability, a quote, or a performance promise for the active client.
    """
    formats = channel.get('formatos') or channel.get('formatos_resumo') or []
    if isinstance(formats, str):
        formats = [formats]
    if not isinstance(formats, list):
        formats = []
    differences = channel.get('diferenciais') or []
    if isinstance(differences, str):
        differences = [differences]
    if not isinstance(differences, list):
        differences = []
    minimum = channel.get('investimento_minimo')
    return {
        'id': channel.get('id'), 'name': channel.get('name'), 'description': channel.get('descricao') or '',
        'category': channel.get('categoria') or '', 'logo_url': channel.get('logo_url') or '',
        'audience': channel.get('alcance') or '', 'formats': [str(item)[:160] for item in formats[:6]],
        'differences': [str(item)[:240] for item in differences[:4]],
        'buying_model': channel.get('modelo_compra') or '', 'lead_time': channel.get('prazo_entrega') or '',
        'budget_minimum': minimum if minimum not in (None, '') else '',
        'budget_status': 'Referência do catálogo Cadu — validar disponibilidade e condição comercial.' if minimum not in (None, '') else 'Não informado no catálogo. Validar com o comercial.',
        'detail_url': product_url('planner', '/canais/' + str(channel.get('id'))),
    }


def project(event, profile, client_id=None, actor_id=None):
    """Return a client-safe card or None. Exceptions stay local to the tool."""
    if profile not in {'planner', 'workspace'} or not isinstance(event, dict):
        return None
    raw_name = event.get('tool') or event.get('tool_name')
    if not isinstance(raw_name, str):
        return None
    params = _params(event.get('tool_input') if 'tool_input' in event else event.get('input'))
    if params is None:
        return None
    if raw_name in PLAN_LIST_ALIASES | PLAN_DETAIL_ALIASES:
        if not isinstance(client_id, int) or not isinstance(actor_id, int):
            return None
        try:
            from ...cadu_planner import plans
            if raw_name in PLAN_DETAIL_ALIASES:
                plan_id = str(params.get('id') or '')
                if not plan_id:
                    return None
                records = [plans.get_plan(client_id, actor_id, plan_id)]
            else:
                records = plans.list_plans(client_id, actor_id)
            # Never stream share tokens, allocations, briefing notes, or other
            # plan internals from a provider-initiated tool event.
            records = [{key: row.get(key) for key in ('id', 'title', 'objective', 'status', 'campaign_name', 'updated_at', 'item_count')}
                       for row in records[:10]]
        except Exception:
            return None
        return {'event': 'catalog', 'catalog_kind': 'planos', 'records': records}
    if raw_name in DOCUMENT_ALIASES:
        if profile != 'planner':
            return None
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
    if profile != 'planner' and kind != 'canais':
        return None
    try:
        if kind == 'canais' and raw_name in DETAIL_ALIASES:
            item_id = params.get('id')
            if item_id is None:
                return None
            from ...cadu_planner import channels
            return {'event': 'catalog', 'catalog_kind': 'canal',
                    'records': [_channel_for_conversation(channels.detail(item_id))]}
        if kind == 'places':
            from ...smart_planner.places_bridge import planner_place_catalog
            query = str(params.get('search', params.get('q', ''))).strip().lower()
            records = planner_place_catalog()
            if query:
                records = [item for item in records if query in ' '.join(str(item.get(key) or '') for key in ('title', 'code', 'city', 'state')).lower()]
            records = [{'name': item.get('title'), 'description': ' · '.join(filter(None, (item.get('city'), item.get('state')))),
                        'category': 'Place', 'audience': ', '.join((item.get('audiences') or [])[:2])}
                       for item in records[:10]]
            return {'event': 'catalog', 'catalog_kind': kind, 'records': records}
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
    if kind == 'audiencias':
        records = [_audience_for_conversation(record) for record in records]
    # `kind` is reserved by service.stream's SSE event helper.
    return {'event': 'catalog', 'catalog_kind': kind, 'records': records[:10]}
