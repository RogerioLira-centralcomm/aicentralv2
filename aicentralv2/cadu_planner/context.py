"""Contexto de marca e projeto do workspace para ferramentas de planejamento.

Planejamento e Radar partem do que o cliente já registrou no workspace: o
perfil da marca (``cx_clients.brand_profile``) e o dossiê de direção do
projeto (``cadu_ci_projetos``). O resultado é enxuto e com limite de tamanho,
porque vai para a tela e, depois, para os prompts dos proposers.
"""
from __future__ import annotations

from ..cadu_family import repository

TEXT_LIMIT = 600
LIST_LIMIT = 8
# Campos do perfil da marca relevantes para planejar mídia e achar oportunidades.
BRAND_FIELDS = (
    ('brand_summary', 'Resumo da marca'), ('target_audience', 'Público-alvo'),
    ('positioning', 'Posicionamento'), ('products_services', 'Produtos e serviços'),
    ('differentiators', 'Diferenciais'), ('audience_segments', 'Segmentos de público'),
    ('personas', 'Personas'), ('competitors', 'Concorrentes'),
    ('campaign_opportunities', 'Oportunidades de campanha'), ('tone_of_voice', 'Tom de voz'),
)
PROJECT_FIELDS = ('description', 'audience', 'positioning', 'tone_of_voice', 'instructions')


def _short(value):
    if value in (None, '', [], {}):
        return None
    if isinstance(value, (list, tuple)):
        items = [_short(item) for item in value[:LIST_LIMIT]]
        return [item for item in items if item] or None
    if isinstance(value, dict):
        label = value.get('name') or value.get('nome') or value.get('title') or value.get('label')
        detail = value.get('description') or value.get('descricao') or value.get('summary')
        text = ' — '.join(str(part) for part in (label, detail) if part)
        return text[:TEXT_LIMIT] if text else None
    return str(value).strip()[:TEXT_LIMIT] or None


def _brand(client_id, brand_ref):
    if not str(brand_ref or '').startswith('studio:'):
        return None
    try:
        brand_id = int(str(brand_ref).split(':', 1)[1])
    except ValueError:
        return None
    rows = repository.rows('''SELECT id, name, sector, website_url, logo_url, primary_color,
                                     COALESCE(brand_profile, '{}'::jsonb) AS brand_profile
                                FROM cx_clients WHERE id = %s AND crm_client_id = %s''', (brand_id, int(client_id)))
    if not rows:
        return None
    row = rows[0]
    profile = row['brand_profile'] if isinstance(row['brand_profile'], dict) else {}
    fields = []
    for key, label in BRAND_FIELDS:
        value = _short(profile.get(key))
        if value:
            fields.append({'key': key, 'label': label, 'value': value})
    return {'ref': brand_ref, 'name': row['name'], 'sector': row.get('sector'), 'website_url': row.get('website_url'),
            'color': row.get('primary_color'), 'fields': fields}


def _project(client_id, project_ref):
    if not str(project_ref or '').startswith('ci:'):
        return None
    from ..cadu_workspace.project_context_service import ProjectContextError, context_items, get_context
    try:
        snapshot = get_context(int(client_id), project_ref)
    except ProjectContextError:
        return None
    standard = snapshot.get('standard_fields') or {}
    items = [item for item in context_items(snapshot)
             if item['field_kind'] == 'custom' or item['key'] in PROJECT_FIELDS]
    return {'ref': project_ref, 'name': standard.get('name'), 'color': standard.get('color'),
            'fields': [{'key': item['key'], 'label': item['label'], 'value': _short(item['display_value'])}
                       for item in items[:16]]}


def load_plan_context(client_id, brand_ref=None, project_ref=None) -> dict:
    """Marca e projeto já validados contra o inventário do cliente."""
    # Marcas antigas podem ser registros de cadu_ci_projetos com tipo 'marca'.
    brand = (_brand(client_id, brand_ref) or _project(client_id, brand_ref)) if brand_ref else None
    project = _project(client_id, project_ref) if project_ref else None
    return {'brand': brand, 'project': project, 'suggestions': plan_suggestions(brand, project)}


def plan_suggestions(brand, project) -> dict:
    """Pré-preenchimento de um novo planejamento, sempre editável pelo usuário."""
    def field(source, key):
        return next((item['value'] for item in (source or {}).get('fields') or [] if item['key'] == key), None)

    audience = field(project, 'audience') or field(brand, 'target_audience')
    notes = [part for part in (
        field(project, 'description'),
        f'Público: {audience}' if isinstance(audience, str) else None,
        f'Posicionamento: {field(project, "positioning") or field(brand, "positioning")}'
        if (field(project, 'positioning') or field(brand, 'positioning')) else None,
    ) if part]
    return {
        'advertiser_name': (brand or {}).get('name'),
        'campaign_name': (project or {}).get('name'),
        'notes': '\n'.join(notes)[:2000] or None,
    }
